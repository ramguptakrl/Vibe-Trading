from dataclasses import dataclass

import pytest

from src.tradebrain.advisory_costs import (
    EquityBrokerageProfile,
    SlippageAssumption,
    build_equity_advice_position,
    zerodha_equity_schedule_2026_08_21,
    zerodha_resident_brokerage_2026_08_21,
)
from src.tradebrain.resident_advisory import (
    TARGET_TRADER_PERSONA,
    DataCredentialUse,
    ReadOnlyMarketDataCredential,
    build_resident_advice_costed_plan_snapshot,
)


@dataclass(frozen=True)
class Setup:
    setup_id: str = "R1"
    snapshot_sha256: str = "a" * 64
    decision_at: str = "2026-08-21T10:00:00+05:30"
    qualified_symbol: str = "NSE:BSE"
    entry: float = 1000.0
    target: float = 1010.0
    stop: float = 995.0
    risk_per_share: float = 5.0
    gross_rr: float = 2.0
    mode: str = "day"
    direction: str = "long"


def _slip():
    return SlippageAssumption("resident-persona-test", 0, 0, "test")


def _position():
    return build_equity_advice_position(
        qualified_symbol="NSE:BSE",
        exchange="NSE",
        mode="day",
        direction="long",
        quantity=10,
        entry_reference_price=1000,
        slippage=_slip(),
    )


def test_nri_kite_credential_is_read_only_data_only_and_does_not_change_resident_cost_persona():
    credential = ReadOnlyMarketDataCredential(
        provider="zerodha_kite",
        account_class="nri",
        uses=(DataCredentialUse.BACKTEST, DataCredentialUse.HISTORICAL, DataCredentialUse.LIVE),
    )
    costed = build_resident_advice_costed_plan_snapshot(
        Setup(),
        position=_position(),
        schedule=zerodha_equity_schedule_2026_08_21(),
        slippage=_slip(),
        data_credential=credential,
    )
    assert TARGET_TRADER_PERSONA == "resident_individual"
    assert credential.account_class == "nri"
    assert credential.read_only is True
    assert credential.affects_target_persona is False
    assert costed.brokerage_profile_version == zerodha_resident_brokerage_2026_08_21().version


def test_resident_wrapper_rejects_nri_brokerage_even_if_data_login_is_nri():
    credential = ReadOnlyMarketDataCredential(
        provider="zerodha_kite", account_class="nri", uses=(DataCredentialUse.LIVE,)
    )
    nonresident_fee_profile = EquityBrokerageProfile(
        version="zerodha-nri-nonpis-equity-2026-08-21-v1",
        applicable_from="2026-08-21",
        verified_at="2026-08-21T19:28:00+00:00",
        source_urls=("https://zerodha.com/charges/",),
        intraday_rate=0.005,
        intraday_cap_rupees=50,
        delivery_rate=0.005,
        delivery_cap_rupees=50,
    )
    with pytest.raises(ValueError, match="resident_individual"):
        build_resident_advice_costed_plan_snapshot(
            Setup(),
            position=_position(),
            schedule=zerodha_equity_schedule_2026_08_21(),
            slippage=_slip(),
            brokerage=nonresident_fee_profile,
            data_credential=credential,
        )


def test_data_credential_contract_rejects_write_capability_or_persona_influence():
    with pytest.raises(ValueError, match="read_only"):
        ReadOnlyMarketDataCredential(
            provider="zerodha_kite",
            account_class="nri",
            uses=(DataCredentialUse.LIVE,),
            read_only=False,
        )
    with pytest.raises(ValueError, match="cannot affect"):
        ReadOnlyMarketDataCredential(
            provider="zerodha_kite",
            account_class="nri",
            uses=(DataCredentialUse.LIVE,),
            affects_target_persona=True,
        )
