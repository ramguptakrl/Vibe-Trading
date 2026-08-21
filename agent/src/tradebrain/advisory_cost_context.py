"""Immutable Phase-8 advisory cost overlay for DAY/SWING BSE plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.tradebrain.advisory_costs import (
    AdviceDirection,
    AdviceTradeMode,
    EquityAdvicePosition,
    EquityBrokerageProfile,
    EquityTradeEconomics,
    SlippageAssumption,
    ZerodhaEquityChargeSchedule,
    _hash,
    calculate_equity_trade_economics,
)

__all__ = [
    "AdviceCostedPlanSnapshot",
    "AdviceCostedPlanOutcome",
    "AdviceCostedCrashCase",
    "build_advice_costed_plan_snapshot",
    "build_advice_costed_crash_case",
    "cost_resolved_advice_outcome",
]


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value)).lower()


@dataclass(frozen=True)
class AdviceCostedPlanSnapshot:
    base_setup: object
    position: EquityAdvicePosition
    charge_schedule_version: str
    charge_schedule_sha256: str
    brokerage_profile_version: str
    brokerage_profile_sha256: str
    slippage_version: str
    slippage_sha256: str
    snapshot_sha256: str

    @property
    def setup_id(self):
        return getattr(self.base_setup, "setup_id")

    @property
    def decision_at(self):
        return getattr(self.base_setup, "decision_at")

    @property
    def direction(self):
        return getattr(self.base_setup, "direction")

    @property
    def entry(self):
        return getattr(self.base_setup, "entry")

    @property
    def target(self):
        return getattr(self.base_setup, "target")

    @property
    def stop(self):
        return getattr(self.base_setup, "stop")

    @property
    def risk_per_share(self):
        return getattr(self.base_setup, "risk_per_share")

    @property
    def gross_rr(self):
        return getattr(self.base_setup, "gross_rr")

    @property
    def cost_model_version(self):
        return (
            f"phase8-advice:{self.charge_schedule_version}:"
            f"{self.brokerage_profile_version}:{self.slippage_version}"
        )

    @property
    def costs_known(self) -> bool:
        return True


@dataclass(frozen=True)
class AdviceCostedCrashCase:
    base_crash_case: object
    setup_id: str
    setup_sha256: str
    label: object
    replay_source_frame_sha256: str
    crash_case_sha256: str


@dataclass(frozen=True)
class AdviceCostedPlanOutcome:
    base_outcome: object
    setup_id: str
    setup_sha256: str
    state: object
    replay_source_frame_sha256: str
    realized_gross_r: float | None
    realized_net_r: float | None
    mae_r: float | None
    mfe_r: float | None
    time_to_target_seconds: float | None
    terminal_mark_r: float | None
    cost_model_applied: bool
    cost_model_version: str
    economics: EquityTradeEconomics | None
    outcome_sha256: str


def build_advice_costed_plan_snapshot(
    base_setup: object,
    *,
    position: EquityAdvicePosition,
    schedule: ZerodhaEquityChargeSchedule,
    brokerage: EquityBrokerageProfile,
    slippage: SlippageAssumption,
) -> AdviceCostedPlanSnapshot:
    base_sha = str(getattr(base_setup, "snapshot_sha256", "")).strip()
    if not base_sha:
        raise ValueError("base setup must expose snapshot_sha256")
    if position.slippage_sha256 != slippage.sha256:
        raise ValueError("position was built with a different slippage assumption")
    setup_symbol = str(getattr(base_setup, "qualified_symbol", position.qualified_symbol))
    if setup_symbol != position.qualified_symbol:
        raise ValueError("position identity does not match base setup")
    setup_entry = Decimal(str(getattr(base_setup, "entry", position.entry_reference_price)))
    if setup_entry != position.entry_reference_price:
        raise ValueError("position entry reference price must equal frozen plan entry")
    mode = _enum_value(getattr(base_setup, "mode", ""))
    direction = _enum_value(getattr(base_setup, "direction", ""))
    if mode != position.mode.value or direction != position.direction.value:
        raise ValueError("position mode/direction do not match frozen plan")
    if position.mode is AdviceTradeMode.SWING and position.direction is AdviceDirection.SHORT:
        raise ValueError("SWING/POSITION remains LONG-only")
    core = {
        "base_setup_sha256": base_sha,
        "position_sha256": position.position_sha256,
        "charge_schedule_version": schedule.version,
        "charge_schedule_sha256": schedule.sha256,
        "brokerage_profile_version": brokerage.version,
        "brokerage_profile_sha256": brokerage.sha256,
        "slippage_version": slippage.version,
        "slippage_sha256": slippage.sha256,
    }
    return AdviceCostedPlanSnapshot(
        base_setup=base_setup,
        position=position,
        charge_schedule_version=schedule.version,
        charge_schedule_sha256=schedule.sha256,
        brokerage_profile_version=brokerage.version,
        brokerage_profile_sha256=brokerage.sha256,
        slippage_version=slippage.version,
        slippage_sha256=slippage.sha256,
        snapshot_sha256=_hash(core),
    )


def build_advice_costed_crash_case(
    setup: AdviceCostedPlanSnapshot, base_crash_case: object
) -> AdviceCostedCrashCase:
    base_sha = str(getattr(setup.base_setup, "snapshot_sha256", ""))
    if str(getattr(base_crash_case, "setup_sha256", "")) != base_sha:
        raise ValueError("base Crash replay case does not belong to base setup")
    if str(getattr(base_crash_case, "setup_id", "")) != setup.setup_id:
        raise ValueError("base Crash replay setup_id does not match costed setup")
    core = {
        "setup_id": setup.setup_id,
        "setup_sha256": setup.snapshot_sha256,
        "base_crash_setup_sha256": base_sha,
        "label": getattr(base_crash_case, "label", None),
        "replay_source_frame_sha256": str(getattr(base_crash_case, "replay_source_frame_sha256", "")),
    }
    return AdviceCostedCrashCase(
        base_crash_case=base_crash_case,
        setup_id=setup.setup_id,
        setup_sha256=setup.snapshot_sha256,
        label=getattr(base_crash_case, "label"),
        replay_source_frame_sha256=str(getattr(base_crash_case, "replay_source_frame_sha256", "")),
        crash_case_sha256=_hash(core),
    )


def cost_resolved_advice_outcome(
    setup: AdviceCostedPlanSnapshot,
    base_outcome: object,
    *,
    entry_at: str | datetime,
    exit_at: str | datetime,
    schedule: ZerodhaEquityChargeSchedule,
    brokerage: EquityBrokerageProfile,
    slippage: SlippageAssumption,
    include_dp_charge: bool = True,
    female_primary_holder: bool = False,
    auto_squareoff_order_count: int = 0,
) -> AdviceCostedPlanOutcome:
    base_setup_sha = str(getattr(setup.base_setup, "snapshot_sha256", ""))
    if str(getattr(base_outcome, "setup_sha256", "")) != base_setup_sha:
        raise ValueError("base outcome does not belong to base setup")
    if schedule.version != setup.charge_schedule_version or schedule.sha256 != setup.charge_schedule_sha256:
        raise ValueError("charge schedule does not match frozen costed setup")
    if brokerage.version != setup.brokerage_profile_version or brokerage.sha256 != setup.brokerage_profile_sha256:
        raise ValueError("brokerage profile does not match frozen costed setup")
    if slippage.version != setup.slippage_version or slippage.sha256 != setup.slippage_sha256:
        raise ValueError("slippage assumption does not match frozen costed setup")

    state = _enum_value(getattr(base_outcome, "state", ""))
    if state == "tp_first":
        exit_ref = Decimal(str(getattr(setup.base_setup, "target")))
    elif state == "sl_first":
        exit_ref = Decimal(str(getattr(setup.base_setup, "stop")))
    else:
        core = {
            "setup_sha256": setup.snapshot_sha256,
            "base_outcome_setup_sha256": str(getattr(base_outcome, "setup_sha256", "")),
            "state": state,
            "cost_model_applied": False,
        }
        return AdviceCostedPlanOutcome(
            base_outcome=base_outcome, setup_id=setup.setup_id,
            setup_sha256=setup.snapshot_sha256, state=getattr(base_outcome, "state"),
            replay_source_frame_sha256=str(getattr(base_outcome, "replay_source_frame_sha256", "")),
            realized_gross_r=getattr(base_outcome, "realized_gross_r", None), realized_net_r=None,
            mae_r=getattr(base_outcome, "mae_r", None), mfe_r=getattr(base_outcome, "mfe_r", None),
            time_to_target_seconds=getattr(base_outcome, "time_to_target_seconds", None),
            terminal_mark_r=getattr(base_outcome, "terminal_mark_r", None),
            cost_model_applied=False, cost_model_version=setup.cost_model_version,
            economics=None, outcome_sha256=_hash(core),
        )

    economics = calculate_equity_trade_economics(
        setup.position, entry_at=entry_at, exit_at=exit_at, exit_reference_price=exit_ref,
        schedule=schedule, brokerage=brokerage, slippage=slippage,
        include_dp_charge=include_dp_charge, female_primary_holder=female_primary_holder,
        auto_squareoff_order_count=auto_squareoff_order_count,
    )
    risk_rupees = Decimal(str(getattr(setup.base_setup, "risk_per_share"))) * setup.position.quantity
    net_r = float(economics.net_pnl / risk_rupees) if risk_rupees else None
    core = {
        "setup_sha256": setup.snapshot_sha256,
        "base_outcome_setup_sha256": str(getattr(base_outcome, "setup_sha256", "")),
        "state": state,
        "economics_sha256": economics.economics_sha256,
        "realized_net_r": net_r,
    }
    return AdviceCostedPlanOutcome(
        base_outcome=base_outcome, setup_id=setup.setup_id,
        setup_sha256=setup.snapshot_sha256, state=getattr(base_outcome, "state"),
        replay_source_frame_sha256=str(getattr(base_outcome, "replay_source_frame_sha256", "")),
        realized_gross_r=getattr(base_outcome, "realized_gross_r", None), realized_net_r=net_r,
        mae_r=getattr(base_outcome, "mae_r", None), mfe_r=getattr(base_outcome, "mfe_r", None),
        time_to_target_seconds=getattr(base_outcome, "time_to_target_seconds", None),
        terminal_mark_r=getattr(base_outcome, "terminal_mark_r", None),
        cost_model_applied=True, cost_model_version=setup.cost_model_version,
        economics=economics, outcome_sha256=_hash(core),
    )
