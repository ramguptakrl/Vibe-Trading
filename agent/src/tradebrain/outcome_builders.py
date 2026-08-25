"""Phase-6 immutable BSE plan and replay-batch builders."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Iterable

from src.tradebrain.market_data import OHLCVBar
from src.tradebrain.profile import tradebrain_bse_policy
from src.tradebrain.structure_context import BSEStructureRiskContext
from src.tradebrain.outcome_models import (
    BSEPlanSnapshot, Direction, OutcomeValidationError, PlanMode, ReplayBarBatch,
    _aware, _bars_hash, _enum, _normalize_direction, _normalize_mode,
    _sha256_payload, _validate_price, validate_plan_snapshot_integrity,
)

__all__ = ["build_bse_plan_snapshot", "build_replay_bar_batch"]

def build_bse_plan_snapshot(
    phase5: BSEStructureRiskContext,
    *,
    setup_id: str,
    mode: PlanMode | str,
    direction: Direction | str,
    entry: float,
    target: float,
    stop: float,
    known_data_gaps: Iterable[str] = (),
) -> BSEPlanSnapshot:
    """Freeze an externally-defined BSE plan without generating one.

    The caller supplies entry/target/stop.  Phase 6 validates geometry and binds
    the plan to the exact Phase-5 point-in-time context.  This is an activated
    plan record, not an order-fill simulator.
    """

    setup_id = str(setup_id or "").strip()
    if not setup_id:
        raise OutcomeValidationError("setup_id is required")
    readiness = phase5.readiness
    if not readiness.market_structure_ready:
        raise OutcomeValidationError("Phase-5 market structure/risk context is not ready")

    policy = tradebrain_bse_policy()
    foundation = phase5.phase4.foundation
    if foundation.profile_name != policy.profile_name:
        raise OutcomeValidationError("plan context is not the tradebrain_bse profile")
    if not foundation.advisory_only or foundation.auto_execution:
        raise OutcomeValidationError("tradebrain_bse plan snapshots require advisory-only policy")

    mode_value = _normalize_mode(mode)
    direction_value = _normalize_direction(direction)
    if mode_value is PlanMode.DAY:
        if direction_value is Direction.LONG and not policy.day.long_allowed:
            raise OutcomeValidationError("DAY LONG is disabled by policy")
        if direction_value is Direction.SHORT and not policy.day.short_allowed:
            raise OutcomeValidationError("DAY SHORT is disabled by policy")
    else:
        if direction_value is Direction.LONG and not policy.swing.long_allowed:
            raise OutcomeValidationError("SWING LONG is disabled by policy")
        if direction_value is Direction.SHORT:
            raise OutcomeValidationError("SWING/POSITION remains LONG-only")

    entry_value = _validate_price(entry, "entry")
    target_value = _validate_price(target, "target")
    stop_value = _validate_price(stop, "stop")
    if direction_value is Direction.LONG:
        if not stop_value < entry_value < target_value:
            raise OutcomeValidationError("LONG geometry must satisfy stop < entry < target")
        risk = entry_value - stop_value
        reward = target_value - entry_value
    else:
        if not target_value < entry_value < stop_value:
            raise OutcomeValidationError("SHORT geometry must satisfy target < entry < stop")
        risk = stop_value - entry_value
        reward = entry_value - target_value

    structure = phase5.structure
    market = phase5.phase4.market_data
    intel = phase5.phase4.intelligence
    if market.frame_sha256 != structure.source_frame_sha256:
        raise OutcomeValidationError("Phase-5 structure is not bound to its Phase-4 market hash")
    if structure.native_bar_count <= 0 or structure.native_bar_count > len(market.bars):
        raise OutcomeValidationError("invalid Phase-5 native bar boundary")
    boundary_bar = market.bars[structure.native_bar_count - 1]
    if boundary_bar.timestamp != structure.native_latest_timestamp:
        raise OutcomeValidationError("Phase-5 native boundary does not match Phase-4 bars")

    decision = _aware(structure.as_of, "structure.as_of")
    intelligence_as_of = _aware(intel.as_of, "intelligence.as_of")
    if intelligence_as_of > decision:
        raise OutcomeValidationError("intelligence snapshot is later than the decision timestamp")

    gaps = tuple(dict.fromkeys(str(item).strip() for item in known_data_gaps if str(item).strip()))
    structure_versions = tuple(
        sorted({item.config_version for item in structure.timeframes})
    )

    policy_hash = _sha256_payload(policy)
    structure_hash = _sha256_payload(structure)
    crash_hash = _sha256_payload(phase5.crash_guard)
    intelligence_hash = _sha256_payload(intel)
    common = {
        "setup_id": setup_id,
        "schema_version": "phase6-plan-v1",
        "decision_at": decision.isoformat(),
        "mode": mode_value,
        "direction": direction_value,
        "isin": foundation.identity.isin,
        "qualified_symbol": foundation.identity.qualified_symbol,
        "vibe_symbol": foundation.identity.vibe_symbol,
        "interval": structure.native_interval,
        "entry": entry_value,
        "target": target_value,
        "stop": stop_value,
        "risk_per_share": risk,
        "reward_per_share": reward,
        "gross_rr": reward / risk,
        "net_rr": None,
        "cost_model_version": None,
        "decision_reference_price": boundary_bar.close,
        "profile_name": foundation.profile_name,
        "advisory_only": foundation.advisory_only,
        "auto_execution": foundation.auto_execution,
        "policy_sha256": policy_hash,
        "market_data_source_name": market.source_name,
        "market_data_frame_sha256": market.frame_sha256,
        "structure_as_of": structure.as_of,
        "structure_native_bar_count": structure.native_bar_count,
        "structure_native_latest_timestamp": structure.native_latest_timestamp,
        "structure_config_versions": structure_versions,
        "structure_sha256": structure_hash,
        "crash_guard_state": _enum(phase5.crash_guard.state),
        "crash_guard_reasons": tuple(phase5.crash_guard.reasons),
        "crash_guard_config_version": phase5.crash_guard.config_version,
        "crash_guard_config_learned": phase5.crash_guard.config_learned,
        "crash_guard_sha256": crash_hash,
        "intelligence_as_of": intel.as_of,
        "intelligence_event_count": len(intel.events),
        "intelligence_sha256": intelligence_hash,
        "known_data_gaps": gaps,
    }
    digest = _sha256_payload(common)
    return BSEPlanSnapshot(**common, snapshot_sha256=digest)


def _validate_bars(bars: tuple[OHLCVBar, ...]) -> None:
    last: datetime | None = None
    for bar in bars:
        current = _aware(bar.timestamp, "replay bar timestamp")
        if last is not None and current <= last:
            raise OutcomeValidationError("replay bars must be strictly ascending and unique")
        last = current
        values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
        if any(not math.isfinite(float(value)) for value in values):
            raise OutcomeValidationError("replay bars must contain finite OHLCV")
        if bar.volume < 0:
            raise OutcomeValidationError("replay volume cannot be negative")
        if bar.high < max(bar.open, bar.close, bar.low):
            raise OutcomeValidationError("replay high is inconsistent with OHLC")
        if bar.low > min(bar.open, bar.close, bar.high):
            raise OutcomeValidationError("replay low is inconsistent with OHLC")


def build_replay_bar_batch(
    setup: BSEPlanSnapshot,
    *,
    bars: Iterable[OHLCVBar],
    source_name: str,
    retrieved_at: str | datetime,
    declared_gaps: Iterable[str] = (),
) -> ReplayBarBatch:
    """Build a tamper-evident replay observation set linked to ``setup``."""

    validate_plan_snapshot_integrity(setup)
    items = tuple(bars)
    if not items:
        data_as_of = _aware(retrieved_at, "retrieved_at").isoformat()
    else:
        _validate_bars(items)
        data_as_of = items[-1].timestamp
    source = str(source_name or "").strip()
    if not source:
        raise OutcomeValidationError("replay source_name is required")
    retrieved = _aware(retrieved_at, "retrieved_at")
    if items and _aware(items[-1].timestamp, "data_as_of") > retrieved:
        raise OutcomeValidationError("replay data cannot be later than retrieved_at")
    gaps = tuple(dict.fromkeys(str(item).strip() for item in declared_gaps if str(item).strip()))
    return ReplayBarBatch(
        isin=setup.isin,
        qualified_symbol=setup.qualified_symbol,
        vibe_symbol=setup.vibe_symbol,
        interval=setup.interval,
        source_name=source,
        decision_source_frame_sha256=setup.market_data_frame_sha256,
        frame_sha256=_bars_hash(items),
        retrieved_at=retrieved.isoformat(),
        data_as_of=data_as_of,
        bars=items,
        declared_gaps=gaps,
    )


def _validate_replay_binding(setup: BSEPlanSnapshot, replay: ReplayBarBatch) -> None:
    validate_plan_snapshot_integrity(setup)
    exact = (
        replay.isin == setup.isin
        and replay.qualified_symbol == setup.qualified_symbol
        and replay.vibe_symbol == setup.vibe_symbol
        and replay.interval.lower() == setup.interval.lower()
        and replay.source_name == setup.market_data_source_name
        and replay.decision_source_frame_sha256 == setup.market_data_frame_sha256
    )
    if not exact:
        raise OutcomeValidationError(
            "replay observations do not match the setup identity/source/interval lineage"
        )
    _validate_bars(replay.bars)
    if _bars_hash(replay.bars) != replay.frame_sha256:
        raise OutcomeValidationError("replay frame SHA-256 does not match replay bars")


