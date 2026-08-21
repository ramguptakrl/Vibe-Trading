"""Phase-6 deterministic TP/SL outcome evaluator for BSE plans."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.tradebrain.market_data import OHLCVBar
from src.tradebrain.profile import tradebrain_bse_policy
from src.tradebrain.outcome_builders import _validate_replay_binding
from src.tradebrain.outcome_models import (
    BSEPlanSnapshot, Direction, OutcomeState, OutcomeValidationError,
    PlanMode, PlanOutcome, ReplayBarBatch, _aware, _parse_interval_minutes,
)

__all__ = ["evaluate_plan_outcome"]

def _intraday_gaps(
    bars: tuple[OHLCVBar, ...],
    *,
    decision: datetime,
    interval_minutes: int,
    timezone_name: str,
) -> tuple[str, ...]:
    """Detect holes inside a DAY session without pretending overnight gaps are data loss."""

    tz = ZoneInfo(timezone_name)
    local_decision = decision.astimezone(tz)
    same_day = [
        _aware(bar.timestamp, "bar timestamp").astimezone(tz)
        for bar in bars
        if _aware(bar.timestamp, "bar timestamp").astimezone(tz).date()
        == local_decision.date()
    ]
    gaps: list[str] = []
    if same_day:
        first_delay = same_day[0] - local_decision
        if first_delay > timedelta(minutes=interval_minutes):
            gaps.append(
                f"intraday_gap_after_decision:{local_decision.isoformat()}->{same_day[0].isoformat()}"
            )
    for previous, current in zip(same_day, same_day[1:]):
        if current - previous > timedelta(minutes=interval_minutes):
            gaps.append(f"intraday_gap:{previous.isoformat()}->{current.isoformat()}")
    return tuple(gaps)


def evaluate_plan_outcome(
    setup: BSEPlanSnapshot,
    replay: ReplayBarBatch,
    *,
    evaluation_end: str | datetime | None = None,
) -> PlanOutcome:
    """Evaluate TP-first/SL-first/neither on complete post-decision bars only."""

    _validate_replay_binding(setup, replay)
    decision = _aware(setup.decision_at, "decision_at")
    interval_minutes = _parse_interval_minutes(setup.interval)
    if setup.mode is PlanMode.DAY and interval_minutes >= 1440:
        raise OutcomeValidationError("DAY outcome replay requires intraday bars")

    requested_end = (
        _aware(evaluation_end, "evaluation_end") if evaluation_end is not None else None
    )
    if requested_end is not None and requested_end <= decision:
        raise OutcomeValidationError("evaluation_end must be after decision_at")

    horizon_end = requested_end
    capped = False
    policy = tradebrain_bse_policy()
    if setup.mode is PlanMode.DAY:
        tz = ZoneInfo(policy.day.timezone)
        local_decision = decision.astimezone(tz)
        day_flat = datetime.combine(local_decision.date(), policy.day.flat_by, tzinfo=tz)
        if decision >= day_flat:
            return PlanOutcome(
                setup_id=setup.setup_id,
                setup_sha256=setup.snapshot_sha256,
                state=OutcomeState.DATA_INSUFFICIENT,
                decision_at=setup.decision_at,
                evaluation_end=day_flat.isoformat(),
                resolution_timestamp=None,
                bars_examined=0,
                first_future_timestamp=None,
                last_future_timestamp=None,
                time_to_target_seconds=None,
                time_to_stop_seconds=None,
                mae_r=None,
                mfe_r=None,
                realized_gross_r=None,
                terminal_mark_r=None,
                gross_rr=setup.gross_rr,
                net_rr=None,
                replay_source_frame_sha256=replay.frame_sha256,
                decision_context_gaps=setup.known_data_gaps,
                replay_data_gaps=tuple(dict.fromkeys(replay.declared_gaps + ("decision_at_or_after_day_flat",))),
                horizon_capped_by_day_flat=True,
                complete_observation=False,
            )
        if horizon_end is None or horizon_end > day_flat:
            horizon_end = day_flat
            capped = requested_end is None or requested_end > day_flat

    future: list[OHLCVBar] = []
    for bar in replay.bars:
        start = _aware(bar.timestamp, "replay bar timestamp")
        end = start + timedelta(minutes=interval_minutes)
        if start < decision:
            continue
        if horizon_end is not None and end > horizon_end:
            continue
        future.append(bar)

    future_bars = tuple(future)
    gaps = list(replay.declared_gaps)
    if setup.mode is PlanMode.DAY:
        gaps.extend(
            _intraday_gaps(
                future_bars,
                decision=decision,
                interval_minutes=interval_minutes,
                timezone_name=policy.day.timezone,
            )
        )

    if not future_bars:
        gaps.append("no_complete_future_bars")
        unique_gaps = tuple(dict.fromkeys(gaps))
        return PlanOutcome(
            setup_id=setup.setup_id,
            setup_sha256=setup.snapshot_sha256,
            state=OutcomeState.DATA_INSUFFICIENT,
            decision_at=setup.decision_at,
            evaluation_end=horizon_end.isoformat() if horizon_end else None,
            resolution_timestamp=None,
            bars_examined=0,
            first_future_timestamp=None,
            last_future_timestamp=None,
            time_to_target_seconds=None,
            time_to_stop_seconds=None,
            mae_r=None,
            mfe_r=None,
            realized_gross_r=None,
            terminal_mark_r=None,
            gross_rr=setup.gross_rr,
            net_rr=None,
            replay_source_frame_sha256=replay.frame_sha256,
            decision_context_gaps=setup.known_data_gaps,
            replay_data_gaps=unique_gaps,
            horizon_capped_by_day_flat=capped,
            complete_observation=False,
        )

    risk = setup.risk_per_share
    max_favorable = 0.0
    max_adverse = 0.0
    target_time: datetime | None = None
    stop_time: datetime | None = None
    resolution: datetime | None = None
    state = OutcomeState.NEITHER
    examined: list[OHLCVBar] = []

    for bar in future_bars:
        examined.append(bar)
        stamp = _aware(bar.timestamp, "replay bar timestamp")
        completion = stamp + timedelta(minutes=interval_minutes)
        if setup.direction is Direction.LONG:
            favorable = max(0.0, bar.high - setup.entry) / risk
            adverse = max(0.0, setup.entry - bar.low) / risk
            target_hit = bar.high >= setup.target
            stop_hit = bar.low <= setup.stop
        else:
            favorable = max(0.0, setup.entry - bar.low) / risk
            adverse = max(0.0, bar.high - setup.entry) / risk
            target_hit = bar.low <= setup.target
            stop_hit = bar.high >= setup.stop

        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)
        if target_hit and target_time is None:
            target_time = completion
        if stop_hit and stop_time is None:
            stop_time = completion

        if target_hit and stop_hit:
            state = OutcomeState.AMBIGUOUS_SAME_BAR
            resolution = completion
            break
        if target_hit:
            state = OutcomeState.TP_FIRST
            resolution = completion
            break
        if stop_hit:
            state = OutcomeState.SL_FIRST
            resolution = completion
            break

    # Any known gap before/inside the observed evaluation horizon means a
    # missing segment could have contained TP or SL. Preserve observed
    # excursions but fail closed on the categorical result.
    unique_gaps = tuple(dict.fromkeys(gaps))
    if unique_gaps:
        state = OutcomeState.DATA_INSUFFICIENT
        resolution = None

    last_bar = examined[-1]
    terminal_r = (
        (last_bar.close - setup.entry) / risk
        if setup.direction is Direction.LONG
        else (setup.entry - last_bar.close) / risk
    )
    realized = None
    if state is OutcomeState.TP_FIRST:
        realized = setup.gross_rr
    elif state is OutcomeState.SL_FIRST:
        realized = -1.0

    return PlanOutcome(
        setup_id=setup.setup_id,
        setup_sha256=setup.snapshot_sha256,
        state=state,
        decision_at=setup.decision_at,
        evaluation_end=horizon_end.isoformat() if horizon_end else None,
        resolution_timestamp=resolution.isoformat() if resolution else None,
        bars_examined=len(examined),
        first_future_timestamp=examined[0].timestamp,
        last_future_timestamp=examined[-1].timestamp,
        time_to_target_seconds=(
            (target_time - decision).total_seconds() if target_time else None
        ),
        time_to_stop_seconds=(
            (stop_time - decision).total_seconds() if stop_time else None
        ),
        mae_r=max_adverse,
        mfe_r=max_favorable,
        realized_gross_r=realized,
        terminal_mark_r=terminal_r,
        gross_rr=setup.gross_rr,
        net_rr=None,
        replay_source_frame_sha256=replay.frame_sha256,
        decision_context_gaps=setup.known_data_gaps,
        replay_data_gaps=unique_gaps,
        horizon_capped_by_day_flat=capped,
        complete_observation=state is not OutcomeState.DATA_INSUFFICIENT,
    )
