"""Deterministic BSE plan-outcome memory for TradeBrain Phase 6.

Phase 6 records what happened after an already-defined plan.  It does not create
entries, targets, stops, orders or execution fills.  Outcome evaluation is
strictly point-in-time: only complete bars after the decision timestamp are
eligible, and ambiguous same-bar TP/SL touches are preserved as ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping

from src.tradebrain.market_data import OHLCVBar

__all__ = [
    "BSEPlanSnapshot",
    "Direction",
    "OutcomeState",
    "PlanMode",
    "PlanOutcome",
    "ReplayBarBatch",
    "OutcomeValidationError",
    "validate_plan_snapshot_integrity",
]


class OutcomeValidationError(ValueError):
    """Raised when a plan or replay observation cannot be trusted."""


class PlanMode(str, Enum):
    DAY = "day"
    SWING = "swing"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class OutcomeState(str, Enum):
    TP_FIRST = "tp_first"
    SL_FIRST = "sl_first"
    NEITHER = "neither"
    AMBIGUOUS_SAME_BAR = "ambiguous_same_bar"
    DATA_INSUFFICIENT = "data_insufficient"


def _aware(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise OutcomeValidationError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutcomeValidationError(f"{field_name} must be timezone-aware")
    return parsed


def _enum(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return _canonical(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return _canonical(value.dict())
    return str(value)


def _sha256_payload(payload: object) -> str:
    body = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256(body.encode("utf-8")).hexdigest()


def _bars_hash(bars: Iterable[OHLCVBar]) -> str:
    canonical = "\n".join(
        "|".join(
            (
                bar.timestamp,
                format(bar.open, ".12g"),
                format(bar.high, ".12g"),
                format(bar.low, ".12g"),
                format(bar.close, ".12g"),
                format(bar.volume, ".12g"),
            )
        )
        for bar in bars
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _parse_interval_minutes(interval: str) -> int:
    raw = str(interval or "").strip()
    lowered = raw.lower()
    if lowered.endswith("min"):
        number = lowered[:-3]
        unit = 1
    elif lowered.endswith("m"):
        number = lowered[:-1]
        unit = 1
    elif lowered.endswith("h"):
        number = lowered[:-1]
        unit = 60
    elif lowered.endswith("d"):
        number = lowered[:-1]
        unit = 1440
    else:
        raise OutcomeValidationError(f"unsupported replay interval {interval!r}")
    try:
        value = int(number)
    except ValueError as exc:
        raise OutcomeValidationError(f"invalid replay interval {interval!r}") from exc
    if value <= 0:
        raise OutcomeValidationError("replay interval must be positive")
    return value * unit


def _normalize_mode(value: PlanMode | str) -> PlanMode:
    if isinstance(value, PlanMode):
        return value
    try:
        return PlanMode(str(value).strip().lower())
    except ValueError as exc:
        raise OutcomeValidationError(f"unsupported plan mode {value!r}") from exc


def _normalize_direction(value: Direction | str) -> Direction:
    if isinstance(value, Direction):
        return value
    try:
        return Direction(str(value).strip().lower())
    except ValueError as exc:
        raise OutcomeValidationError(f"unsupported direction {value!r}") from exc


@dataclass(frozen=True)
class BSEPlanSnapshot:
    """Immutable record of a BSE plan exactly as known at decision time."""

    setup_id: str
    schema_version: str
    decision_at: str
    mode: PlanMode
    direction: Direction
    isin: str
    qualified_symbol: str
    vibe_symbol: str
    interval: str
    entry: float
    target: float
    stop: float
    risk_per_share: float
    reward_per_share: float
    gross_rr: float
    net_rr: float | None
    cost_model_version: str | None
    decision_reference_price: float
    profile_name: str
    advisory_only: bool
    auto_execution: bool
    policy_sha256: str
    market_data_source_name: str
    market_data_frame_sha256: str
    structure_as_of: str
    structure_native_bar_count: int
    structure_native_latest_timestamp: str
    structure_config_versions: tuple[str, ...]
    structure_sha256: str
    crash_guard_state: str
    crash_guard_reasons: tuple[str, ...]
    crash_guard_config_version: str
    crash_guard_config_learned: bool
    crash_guard_sha256: str
    intelligence_as_of: str
    intelligence_event_count: int
    intelligence_sha256: str
    known_data_gaps: tuple[str, ...]
    snapshot_sha256: str

    @property
    def costs_known(self) -> bool:
        return self.net_rr is not None and self.cost_model_version is not None


def validate_plan_snapshot_integrity(setup: BSEPlanSnapshot) -> None:
    """Reject a plan whose fields no longer match its creation-time SHA-256."""

    payload = {
        field.name: getattr(setup, field.name)
        for field in fields(setup)
        if field.name != "snapshot_sha256"
    }
    if _sha256_payload(payload) != setup.snapshot_sha256:
        raise OutcomeValidationError("plan snapshot SHA-256 does not match its fields")


@dataclass(frozen=True)
class ReplayBarBatch:
    """Future observation set explicitly linked to one decision-time source."""

    isin: str
    qualified_symbol: str
    vibe_symbol: str
    interval: str
    source_name: str
    decision_source_frame_sha256: str
    frame_sha256: str
    retrieved_at: str
    data_as_of: str
    bars: tuple[OHLCVBar, ...]
    declared_gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanOutcome:
    """Deterministic ex-post observation for one immutable plan."""

    setup_id: str
    setup_sha256: str
    state: OutcomeState
    decision_at: str
    evaluation_end: str | None
    resolution_timestamp: str | None
    bars_examined: int
    first_future_timestamp: str | None
    last_future_timestamp: str | None
    time_to_target_seconds: float | None
    time_to_stop_seconds: float | None
    mae_r: float | None
    mfe_r: float | None
    realized_gross_r: float | None
    terminal_mark_r: float | None
    gross_rr: float
    net_rr: float | None
    replay_source_frame_sha256: str
    decision_context_gaps: tuple[str, ...]
    replay_data_gaps: tuple[str, ...]
    horizon_capped_by_day_flat: bool
    complete_observation: bool
    cost_model_applied: bool = False

    @property
    def usable_for_history(self) -> bool:
        return self.state is not OutcomeState.DATA_INSUFFICIENT


def _validate_price(value: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeValidationError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise OutcomeValidationError(f"{name} must be finite and positive")
    return number


