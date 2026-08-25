"""Phase-6 deterministic Crash Guard replay and false-positive measurement.

The replay label is deliberately provisional.  It measures whether a declared
future downside threshold occurred; it is not universal "market truth" and it
never mutates/promotes Phase-5 Crash Guard thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable

from src.tradebrain.crash_guard import CrashGuardState
from src.tradebrain.historical_outcomes import (
    BSEPlanSnapshot, ReplayBarBatch, OutcomeValidationError,
)
from src.tradebrain.outcome_models import _aware, _parse_interval_minutes
from src.tradebrain.outcome_builders import _validate_replay_binding
from src.tradebrain.outcome_evaluator import _intraday_gaps
from src.tradebrain.profile import tradebrain_bse_policy

__all__ = [
    "CrashReplayCase",
    "CrashReplayConfusion",
    "CrashReplayLabel",
    "CrashReplayLabelConfig",
    "CrashReplaySummary",
    "evaluate_crash_replay_case",
    "summarize_crash_replay",
]


class CrashReplayLabel(str, Enum):
    STRESS = "stress"
    NO_STRESS = "no_stress"
    DATA_INSUFFICIENT = "data_insufficient"


class CrashReplayConfusion(str, Enum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    TRUE_NEGATIVE = "true_negative"
    EXCLUDED_DATA_INSUFFICIENT = "excluded_data_insufficient"


@dataclass(frozen=True)
class CrashReplayLabelConfig:
    """Provisional ex-post label definition, never a promoted Crash Guard rule."""

    version: str = "phase6-provisional-label-v1"
    learned: bool = False
    adverse_move_threshold_pct: float = -0.05
    horizon_bars: int = 6

    def __post_init__(self) -> None:
        if self.learned:
            raise ValueError("Phase-6 replay labels are provisional, not learned")
        if not self.version.strip():
            raise ValueError("replay label version is required")
        if not -1.0 < self.adverse_move_threshold_pct < 0.0:
            raise ValueError("adverse_move_threshold_pct must be between -1 and 0")
        if self.horizon_bars < 1:
            raise ValueError("horizon_bars must be >= 1")


@dataclass(frozen=True)
class CrashReplayCase:
    setup_id: str
    setup_sha256: str
    crash_guard_state: str
    predicted_severe: bool
    label: CrashReplayLabel
    confusion: CrashReplayConfusion
    reference_price: float
    worst_future_low: float | None
    adverse_move_pct: float | None
    bars_required: int
    bars_observed: int
    label_config_version: str
    label_config_learned: bool
    replay_source_frame_sha256: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrashReplaySummary:
    label_config_version: str
    cases_total: int
    cases_included: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    excluded_data_insufficient: int
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    severe_precision_denominator: int
    negative_class_denominator: int


def evaluate_crash_replay_case(
    setup: BSEPlanSnapshot,
    replay: ReplayBarBatch,
    *,
    config: CrashReplayLabelConfig | None = None,
) -> CrashReplayCase:
    """Apply one declared ex-post stress label to one frozen decision snapshot."""

    config = CrashReplayLabelConfig() if config is None else config
    _validate_replay_binding(setup, replay)
    decision = _aware(setup.decision_at, "decision_at")
    interval_minutes = _parse_interval_minutes(setup.interval)

    future = []
    policy = tradebrain_bse_policy()
    day_flat = None
    if setup.mode.value == "day":
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(policy.day.timezone)
        local_decision = decision.astimezone(tz)
        day_flat = datetime.combine(local_decision.date(), policy.day.flat_by, tzinfo=tz)

    for bar in replay.bars:
        stamp = _aware(bar.timestamp, "replay bar timestamp")
        end = stamp + timedelta(minutes=interval_minutes)
        if stamp < decision:
            continue
        if day_flat is not None and end > day_flat:
            continue
        future.append(bar)
        if len(future) >= config.horizon_bars:
            break

    predicted = setup.crash_guard_state == CrashGuardState.SEVERE.value
    limitations: list[str] = []
    if replay.declared_gaps:
        limitations.extend(replay.declared_gaps)
    if setup.mode.value == "day" and future:
        limitations.extend(
            _intraday_gaps(
                tuple(future),
                decision=decision,
                interval_minutes=interval_minutes,
                timezone_name=policy.day.timezone,
            )
        )
    if len(future) < config.horizon_bars:
        limitations.append("incomplete_replay_horizon")
    if limitations:
        return CrashReplayCase(
            setup_id=setup.setup_id,
            setup_sha256=setup.snapshot_sha256,
            crash_guard_state=setup.crash_guard_state,
            predicted_severe=predicted,
            label=CrashReplayLabel.DATA_INSUFFICIENT,
            confusion=CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT,
            reference_price=setup.decision_reference_price,
            worst_future_low=min((bar.low for bar in future), default=None),
            adverse_move_pct=None,
            bars_required=config.horizon_bars,
            bars_observed=len(future),
            label_config_version=config.version,
            label_config_learned=config.learned,
            replay_source_frame_sha256=replay.frame_sha256,
            limitations=tuple(dict.fromkeys(limitations)),
        )

    worst_low = min(bar.low for bar in future)
    adverse = worst_low / setup.decision_reference_price - 1.0
    stress = adverse <= config.adverse_move_threshold_pct
    label = CrashReplayLabel.STRESS if stress else CrashReplayLabel.NO_STRESS
    if setup.crash_guard_state == CrashGuardState.DATA_INSUFFICIENT.value:
        confusion = CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT
        limitations = ["crash_guard_data_insufficient"]
    elif predicted and stress:
        confusion = CrashReplayConfusion.TRUE_POSITIVE
    elif predicted and not stress:
        confusion = CrashReplayConfusion.FALSE_POSITIVE
    elif not predicted and stress:
        confusion = CrashReplayConfusion.FALSE_NEGATIVE
    else:
        confusion = CrashReplayConfusion.TRUE_NEGATIVE

    return CrashReplayCase(
        setup_id=setup.setup_id,
        setup_sha256=setup.snapshot_sha256,
        crash_guard_state=setup.crash_guard_state,
        predicted_severe=predicted,
        label=label,
        confusion=confusion,
        reference_price=setup.decision_reference_price,
        worst_future_low=worst_low,
        adverse_move_pct=adverse,
        bars_required=config.horizon_bars,
        bars_observed=len(future),
        label_config_version=config.version,
        label_config_learned=config.learned,
        replay_source_frame_sha256=replay.frame_sha256,
        limitations=tuple(limitations),
    )


def summarize_crash_replay(
    cases: Iterable[CrashReplayCase],
    *,
    config: CrashReplayLabelConfig | None = None,
) -> CrashReplaySummary:
    """Aggregate a confusion matrix without changing any Crash Guard parameter."""

    config = CrashReplayLabelConfig() if config is None else config
    items = tuple(cases)
    for item in items:
        if item.label_config_version != config.version:
            raise OutcomeValidationError("replay cases use a different label-config version")
        if item.label_config_learned:
            raise OutcomeValidationError("learned replay labels are not allowed in Phase 6")

    counts = {kind: 0 for kind in CrashReplayConfusion}
    for item in items:
        counts[item.confusion] += 1

    tp = counts[CrashReplayConfusion.TRUE_POSITIVE]
    fp = counts[CrashReplayConfusion.FALSE_POSITIVE]
    fn = counts[CrashReplayConfusion.FALSE_NEGATIVE]
    tn = counts[CrashReplayConfusion.TRUE_NEGATIVE]
    excluded = counts[CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT]
    severe_den = tp + fp
    negative_den = fp + tn
    stress_den = tp + fn

    return CrashReplaySummary(
        label_config_version=config.version,
        cases_total=len(items),
        cases_included=len(items) - excluded,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        excluded_data_insufficient=excluded,
        precision=tp / severe_den if severe_den else None,
        recall=tp / stress_den if stress_den else None,
        false_positive_rate=fp / negative_den if negative_den else None,
        severe_precision_denominator=severe_den,
        negative_class_denominator=negative_den,
    )
