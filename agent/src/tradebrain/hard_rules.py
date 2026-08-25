"""Authoritative BSE hard-rule arbiter for TradeBrain Phase 10.

The arbiter is deterministic and advisory-only.  It enforces owner policy,
known mode boundaries, DAY time exits, mandatory plan geometry, and Crash Guard
long blocks.  It never creates a SHORT merely because Crash Guard is severe.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Mapping
from zoneinfo import ZoneInfo

from src.tradebrain.bse_context import BSE_LTD_ISIN
from src.tradebrain.outcome_models import Direction, PlanMode
from src.tradebrain.profile import tradebrain_bse_policy
from src.tradebrain.structure_context import BSEStructureRiskContext

__all__ = [
    "AdvisoryPlanRequest",
    "HardRuleAssessment",
    "HardRuleCode",
    "HardRuleState",
    "RuleIntent",
    "evaluate_bse_hard_rules",
]


class RuleIntent(str, Enum):
    NEW_ENTRY = "new_entry"
    EXISTING_POSITION = "existing_position"


class HardRuleState(str, Enum):
    ALLOW = "allow"
    BLOCKED = "blocked"
    EXIT_REQUIRED = "exit_required"
    DATA_INSUFFICIENT = "data_insufficient"


class HardRuleCode(str, Enum):
    CORE_CONTEXT_NOT_READY = "core_context_not_ready"
    PROFILE_NOT_ADVISORY = "profile_not_advisory"
    IDENTITY_MISMATCH = "identity_mismatch"
    LEGACY_RESCUE_ENABLED = "legacy_rescue_enabled"
    DAY_LONG_DISABLED = "day_long_disabled"
    DAY_SHORT_DISABLED = "day_short_disabled"
    SWING_LONG_DISABLED = "swing_long_disabled"
    SWING_SHORT_FORBIDDEN = "swing_short_forbidden"
    DAY_NO_FRESH_ENTRY_WINDOW = "day_no_fresh_entry_window"
    DAY_FLAT_BY_REACHED = "day_flat_by_reached"
    CRASH_GUARD_BLOCKS_DAY_LONG = "crash_guard_blocks_day_long"
    CRASH_GUARD_BLOCKS_SWING_LONG = "crash_guard_blocks_swing_long"
    INVALID_GEOMETRY = "invalid_geometry"


def _enum(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _canon(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: _canon(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canon(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return float(f"{value:.15g}")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _hash(value: object) -> str:
    body = json.dumps(_canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(body.encode("utf-8")).hexdigest()


def _aware(value: str | datetime, name: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} must be ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return dt


@dataclass(frozen=True)
class AdvisoryPlanRequest:
    mode: PlanMode | str
    direction: Direction | str
    entry: float
    target: float
    stop: float
    intent: RuleIntent | str = RuleIntent.NEW_ENTRY

    def __post_init__(self) -> None:
        mode = self.mode if isinstance(self.mode, PlanMode) else PlanMode(str(self.mode).lower())
        direction = (
            self.direction
            if isinstance(self.direction, Direction)
            else Direction(str(self.direction).lower())
        )
        intent = self.intent if isinstance(self.intent, RuleIntent) else RuleIntent(str(self.intent))
        for name in ("entry", "target", "stop"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "intent", intent)

    @property
    def risk_per_share(self) -> float:
        if self.direction is Direction.LONG:
            return self.entry - self.stop
        return self.stop - self.entry

    @property
    def reward_per_share(self) -> float:
        if self.direction is Direction.LONG:
            return self.target - self.entry
        return self.entry - self.target

    @property
    def gross_rr(self) -> float | None:
        risk = self.risk_per_share
        reward = self.reward_per_share
        if risk <= 0 or reward <= 0:
            return None
        return reward / risk

    @property
    def request_sha256(self) -> str:
        return _hash(self)


@dataclass(frozen=True)
class HardRuleAssessment:
    state: HardRuleState
    as_of: str
    request_sha256: str
    codes: tuple[HardRuleCode, ...]
    reasons: tuple[str, ...]
    hard_rules_clear: bool
    advisory_only: bool
    auto_execution_allowed: bool
    assessment_sha256: str


def _geometry_valid(request: AdvisoryPlanRequest) -> bool:
    if request.direction is Direction.LONG:
        return request.stop < request.entry < request.target
    return request.target < request.entry < request.stop


def evaluate_bse_hard_rules(
    phase5: BSEStructureRiskContext,
    request: AdvisoryPlanRequest,
    *,
    as_of: str | datetime,
) -> HardRuleAssessment:
    """Evaluate owner/exchange/profile hard boundaries for one plan request."""

    policy = tradebrain_bse_policy()
    now = _aware(as_of, "as_of")
    codes: list[HardRuleCode] = []
    reasons: list[str] = []

    readiness = phase5.readiness
    core_ready = (
        readiness.identity_verified
        and readiness.market_data_ready
        and readiness.intelligence_ready
        and readiness.market_structure_ready
    )
    if not core_ready:
        codes.append(HardRuleCode.CORE_CONTEXT_NOT_READY)
        reasons.append("identity/market-data/intelligence/structure context is not fully ready")

    foundation = phase5.phase4.foundation
    if (
        foundation.profile_name != policy.profile_name
        or not policy.advisory_only
        or policy.auto_execution
        or not foundation.advisory_only
        or foundation.auto_execution
    ):
        codes.append(HardRuleCode.PROFILE_NOT_ADVISORY)
        reasons.append("tradebrain_bse must remain advisory-only with auto execution disabled")

    identity = foundation.identity
    if identity.isin != BSE_LTD_ISIN or identity.qualified_symbol != "NSE:BSE":
        codes.append(HardRuleCode.IDENTITY_MISMATCH)
        reasons.append("hard-rule arbiter is bound only to canonical BSE Ltd / NSE:BSE")

    if policy.legacy.l1_l2_l3_enabled or policy.legacy.rescue_averaging_enabled:
        codes.append(HardRuleCode.LEGACY_RESCUE_ENABLED)
        reasons.append("retired L1/L2/L3 or rescue-averaging architecture cannot be active")

    if not _geometry_valid(request):
        codes.append(HardRuleCode.INVALID_GEOMETRY)
        reasons.append("plan must include valid entry/target/stop geometry")

    local = now.astimezone(ZoneInfo(policy.day.timezone))
    local_time = local.timetz().replace(tzinfo=None)

    exit_required = False
    if request.mode is PlanMode.DAY:
        if request.direction is Direction.LONG and not policy.day.long_allowed:
            codes.append(HardRuleCode.DAY_LONG_DISABLED)
            reasons.append("DAY LONG is disabled by owner policy")
        if request.direction is Direction.SHORT and not policy.day.short_allowed:
            codes.append(HardRuleCode.DAY_SHORT_DISABLED)
            reasons.append("DAY SHORT is disabled by owner policy")

        if request.intent is RuleIntent.EXISTING_POSITION and local_time >= policy.day.flat_by:
            codes.append(HardRuleCode.DAY_FLAT_BY_REACHED)
            reasons.append("DAY position is at/after the hard 15:15 IST flat boundary")
            exit_required = True
        elif request.intent is RuleIntent.NEW_ENTRY:
            if local_time >= policy.day.flat_by:
                codes.append(HardRuleCode.DAY_FLAT_BY_REACHED)
                reasons.append("no fresh DAY entry at/after the hard 15:15 IST flat boundary")
            elif local_time >= policy.day.fresh_entry_cutoff:
                codes.append(HardRuleCode.DAY_NO_FRESH_ENTRY_WINDOW)
                reasons.append("no fresh DAY entry at/after 15:10 IST")

        if request.direction is Direction.LONG and phase5.crash_guard.block_day_long:
            codes.append(HardRuleCode.CRASH_GUARD_BLOCKS_DAY_LONG)
            reasons.append("Crash Guard blocks fresh/continued DAY LONG risk under severe stress")
    else:
        if request.direction is Direction.SHORT:
            codes.append(HardRuleCode.SWING_SHORT_FORBIDDEN)
            reasons.append("SWING/POSITION remains LONG-only")
        elif not policy.swing.long_allowed:
            codes.append(HardRuleCode.SWING_LONG_DISABLED)
            reasons.append("SWING LONG is disabled by owner policy")
        if request.direction is Direction.LONG and phase5.crash_guard.block_swing_long:
            codes.append(HardRuleCode.CRASH_GUARD_BLOCKS_SWING_LONG)
            reasons.append("Crash Guard blocks fresh SWING LONG risk under severe stress")

    if exit_required:
        state = HardRuleState.EXIT_REQUIRED
    elif HardRuleCode.CORE_CONTEXT_NOT_READY in codes:
        state = HardRuleState.DATA_INSUFFICIENT
    elif codes:
        state = HardRuleState.BLOCKED
    else:
        state = HardRuleState.ALLOW

    core = {
        "state": state,
        "as_of": now.isoformat(),
        "request_sha256": request.request_sha256,
        "codes": tuple(codes),
        "reasons": tuple(reasons),
        "hard_rules_clear": state is HardRuleState.ALLOW,
        "advisory_only": True,
        "auto_execution_allowed": False,
    }
    return HardRuleAssessment(
        **core,
        assessment_sha256=_hash(core),
    )
