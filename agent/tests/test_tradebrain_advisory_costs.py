from dataclasses import dataclass, replace
from decimal import Decimal

import pytest

from src.tradebrain.advisory_costs import (
    AdviceCostValidationError,
    AdviceDirection,
    AdviceSettlementClass,
    AdviceTradeMode,
    SlippageAssumption,
    build_equity_advice_position,
    calculate_equity_trade_economics,
    required_exit_price_for_net_target,
    zerodha_equity_schedule_2026_08_21,
    zerodha_nri_nonpis_brokerage_2026_08_21,
    zerodha_resident_brokerage_2026_08_21,
)
from src.tradebrain.advisory_cost_context import (
    build_advice_costed_crash_case,
    build_advice_costed_plan_snapshot,
    cost_resolved_advice_outcome,
)

def slip(entry="0", exit="0"):
    return SlippageAssumption("advice-slip-v1", entry, exit, "explicit test assumption")


def pos(mode="day", direction="long", qty=100, price="1000", s=None):
    return build_equity_advice_position(
        qualified_symbol="NSE:BSE", exchange="NSE", mode=mode, direction=direction,
        quantity=qty, entry_reference_price=price, slippage=s or slip(),
    )


def test_current_equity_schedule_matches_verified_intraday_and_delivery_contract():
    s = zerodha_equity_schedule_2026_08_21()
    assert s.stt_delivery_rate == Decimal("0.001")
    assert s.stt_intraday_sell_rate == Decimal("0.00025")
    assert s.stamp_delivery_buy_rate == Decimal("0.00015")
    assert s.stamp_intraday_buy_rate == Decimal("0.00003")
    assert s.nse_equity_transaction_rate == Decimal("0.0000307")
    assert s.bse_equity_transaction_rate == Decimal("0.0000375")
    assert s.auto_squareoff_base_rupees == Decimal("50")
    assert len(s.sha256) == 64


def test_resident_and_nri_nonpis_are_fee_profiles_not_advice_eligibility_gates():
    resident = zerodha_resident_brokerage_2026_08_21()
    nri = zerodha_nri_nonpis_brokerage_2026_08_21()
    assert resident.intraday_rate == Decimal("0.0003")
    assert resident.intraday_cap_rupees == Decimal("20")
    assert resident.delivery_rate == Decimal("0")
    assert nri.intraday_rate == Decimal("0.005")
    assert nri.intraday_cap_rupees == Decimal("50")
    # Building DAY/SWING advice positions does not consult residency/account eligibility.
    assert pos("day", "long").mode is AdviceTradeMode.DAY
    assert pos("swing", "long").mode is AdviceTradeMode.SWING


def test_day_long_uses_intraday_stt_sell_only_stamp_buy_and_no_dp():
    e = calculate_equity_trade_economics(
        pos("day", "long"), entry_at="2026-08-21T10:00:00+05:30",
        exit_at="2026-08-21T14:00:00+05:30", exit_reference_price="1010",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
    )
    assert e.settlement_class is AdviceSettlementClass.INTRADAY
    assert e.charges.entry_brokerage == Decimal("20.00")
    assert e.charges.exit_brokerage == Decimal("20.00")
    assert e.charges.entry_stt == Decimal("0.00")
    assert e.charges.exit_stt > 0
    assert e.charges.buy_stamp_duty > 0
    assert e.charges.dp_charge == Decimal("0.00")


def test_day_short_puts_stt_on_entry_sell_and_stamp_on_cover_buy():
    e = calculate_equity_trade_economics(
        pos("day", "short"), entry_at="2026-08-21T10:00:00+05:30",
        exit_at="2026-08-21T14:00:00+05:30", exit_reference_price="990",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
    )
    assert e.gross_pnl == Decimal("1000.00")
    assert e.charges.entry_stt > 0
    assert e.charges.exit_stt == Decimal("0.00")
    assert e.charges.buy_stamp_duty > 0
    assert e.net_pnl < e.gross_pnl


def test_day_advice_cost_requires_same_indian_date():
    with pytest.raises(AdviceCostValidationError, match="same-session"):
        calculate_equity_trade_economics(
            pos("day", "long"), entry_at="2026-08-21T10:00:00+05:30",
            exit_at="2026-08-22T10:00:00+05:30", exit_reference_price="1010",
            schedule=zerodha_equity_schedule_2026_08_21(),
            brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
        )


def test_swing_overnight_uses_delivery_costs_and_dp():
    e = calculate_equity_trade_economics(
        pos("swing", "long"), entry_at="2026-08-21T10:00:00+05:30",
        exit_at="2026-08-25T10:00:00+05:30", exit_reference_price="1040",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
    )
    assert e.settlement_class is AdviceSettlementClass.DELIVERY
    assert e.charges.entry_brokerage == Decimal("0.00")
    assert e.charges.exit_brokerage == Decimal("0.00")
    assert e.charges.entry_stt > 0 and e.charges.exit_stt > 0
    assert e.charges.dp_charge == Decimal("15.34")


def test_swing_idea_closed_same_day_is_costed_intraday_not_delivery():
    e = calculate_equity_trade_economics(
        pos("swing", "long"), entry_at="2026-08-21T10:00:00+05:30",
        exit_at="2026-08-21T14:00:00+05:30", exit_reference_price="1010",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
    )
    assert e.settlement_class is AdviceSettlementClass.INTRADAY
    assert e.charges.dp_charge == Decimal("0.00")
    assert e.charges.entry_brokerage == Decimal("20.00")


def test_swing_short_remains_blocked_by_strategy_policy_not_account_type():
    with pytest.raises(AdviceCostValidationError, match="LONG-only"):
        pos("swing", "short")


def test_nri_nonpis_fee_profile_can_cost_advice_without_mtf_gate():
    e = calculate_equity_trade_economics(
        pos("day", "long", qty=10), entry_at="2026-08-21T10:00:00+05:30",
        exit_at="2026-08-21T14:00:00+05:30", exit_reference_price="1010",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_nri_nonpis_brokerage_2026_08_21(), slippage=slip(),
    )
    assert e.charges.entry_brokerage == Decimal("50.00")
    assert e.charges.exit_brokerage == Decimal("50.00")


def test_current_advice_schedule_refuses_historical_backfill():
    with pytest.raises(AdviceCostValidationError, match="historical source-dated"):
        calculate_equity_trade_economics(
            pos("day", "long"), entry_at="2026-08-20T10:00:00+05:30",
            exit_at="2026-08-20T14:00:00+05:30", exit_reference_price="1010",
            schedule=zerodha_equity_schedule_2026_08_21(),
            brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
        )


def test_long_break_even_solver_meets_zero_net_on_tick_grid():
    p = pos("day", "long")
    kwargs = dict(
        entry_at="2026-08-21T10:00:00+05:30", exit_at="2026-08-21T14:00:00+05:30",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(), tick_size="0.05",
    )
    be = required_exit_price_for_net_target(p, **kwargs)
    e = calculate_equity_trade_economics(p, exit_reference_price=be, **kwargs)
    assert e.net_pnl >= 0
    lower = be - Decimal("0.05")
    assert calculate_equity_trade_economics(p, exit_reference_price=lower, **kwargs).net_pnl < 0


def test_short_net_target_solver_meets_requested_profit():
    p = pos("day", "short")
    kwargs = dict(
        entry_at="2026-08-21T10:00:00+05:30", exit_at="2026-08-21T14:00:00+05:30",
        schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(), tick_size="0.05",
    )
    target = required_exit_price_for_net_target(p, net_target_rupees="500", **kwargs)
    e = calculate_equity_trade_economics(p, exit_reference_price=target, **kwargs)
    assert e.net_pnl >= Decimal("500")


def test_auto_squareoff_charge_is_explicit_for_day_advice():
    common = dict(
        entry_at="2026-08-21T10:00:00+05:30", exit_at="2026-08-21T15:20:00+05:30",
        exit_reference_price="1010", schedule=zerodha_equity_schedule_2026_08_21(),
        brokerage=zerodha_resident_brokerage_2026_08_21(), slippage=slip(),
    )
    normal = calculate_equity_trade_economics(pos("day", "long"), **common)
    forced = calculate_equity_trade_economics(pos("day", "long"), auto_squareoff_order_count=1, **common)
    assert forced.charges.auto_squareoff_charge == Decimal("59.00")
    assert forced.net_pnl == normal.net_pnl - Decimal("59.00")


@dataclass(frozen=True)
class BaseSetup:
    setup_id: str = "A1"
    snapshot_sha256: str = "a" * 64
    decision_at: str = "2026-08-21T10:00:00+05:30"
    direction: str = "long"
    isin: str = "INE118H01025"
    qualified_symbol: str = "NSE:BSE"
    entry: float = 1000.0
    target: float = 1010.0
    stop: float = 995.0
    risk_per_share: float = 5.0
    gross_rr: float = 2.0
    mode: str = "day"


@dataclass(frozen=True)
class BaseOutcome:
    setup_id: str = "A1"
    setup_sha256: str = "a" * 64
    state: str = "tp_first"
    replay_source_frame_sha256: str = "b" * 64
    realized_gross_r: float | None = 2.0
    mae_r: float | None = 0.5
    mfe_r: float | None = 2.1
    time_to_target_seconds: float | None = 1200.0
    terminal_mark_r: float | None = None
    cost_model_applied: bool = False


@dataclass(frozen=True)
class BaseCrash:
    setup_id: str = "A1"
    setup_sha256: str = "a" * 64
    label: str = "no_stress"
    replay_source_frame_sha256: str = "b" * 64


def make_advice_costed(mode="day"):
    setup = replace(BaseSetup(), mode=mode, target=1040.0, stop=980.0, risk_per_share=20.0, gross_rr=2.0) if mode == "swing" else BaseSetup()
    p = pos(mode, "long", qty=100, price="1000")
    schedule = zerodha_equity_schedule_2026_08_21()
    brokerage = zerodha_resident_brokerage_2026_08_21()
    cs = build_advice_costed_plan_snapshot(setup, position=p, schedule=schedule, brokerage=brokerage, slippage=slip())
    end = "2026-08-25T10:00:00+05:30" if mode == "swing" else "2026-08-21T14:00:00+05:30"
    outcome = replace(BaseOutcome(), realized_gross_r=2.0)
    co = cost_resolved_advice_outcome(
        cs, outcome, entry_at=setup.decision_at, exit_at=end,
        schedule=schedule, brokerage=brokerage, slippage=slip(),
    )
    crash = build_advice_costed_crash_case(cs, BaseCrash())
    return cs, co, crash


def test_advisory_overlay_costs_day_plan_without_mtf_account_context():
    setup, outcome, crash = make_advice_costed("day")
    assert setup.costs_known is True
    assert outcome.cost_model_applied is True
    assert outcome.realized_net_r is not None
    assert outcome.realized_net_r < outcome.realized_gross_r
    assert outcome.setup_sha256 == setup.snapshot_sha256 == crash.setup_sha256


def test_advisory_overlay_costs_swing_cash_plan_without_mtf():
    setup, outcome, _ = make_advice_costed("swing")
    assert outcome.economics.settlement_class is AdviceSettlementClass.DELIVERY
    assert outcome.realized_net_r is not None
    assert "phase8-advice" in setup.cost_model_version


