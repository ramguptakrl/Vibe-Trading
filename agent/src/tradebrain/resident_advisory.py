"""Canonical resident-persona boundary for TradeBrain BSE advisory economics.

The strategy is designed for a resident-individual trader.  Authentication used
only to read historical/live market data is deliberately separate: a Zerodha/Kite
credential may belong to an NRI account, but that fact must never select NRI
brokerage, product eligibility, or advice policy for the target resident trader.

No secret/API key is stored in these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.tradebrain.advisory_cost_context import (
    AdviceCostedPlanOutcome,
    AdviceCostedPlanSnapshot,
    build_advice_costed_plan_snapshot,
    cost_resolved_advice_outcome,
)
from src.tradebrain.advisory_costs import (
    EquityAdvicePosition,
    EquityBrokerageProfile,
    SlippageAssumption,
    ZerodhaEquityChargeSchedule,
    zerodha_resident_brokerage_2026_08_21,
)

__all__ = [
    "TARGET_TRADER_PERSONA",
    "DataCredentialUse",
    "ReadOnlyMarketDataCredential",
    "build_resident_advice_costed_plan_snapshot",
    "cost_resolved_resident_advice_outcome",
    "validate_resident_brokerage_profile",
]

TARGET_TRADER_PERSONA = "resident_individual"
_RESIDENT_BROKERAGE_PREFIX = "zerodha-resident-equity-"


class DataCredentialUse(str, Enum):
    BACKTEST = "backtest"
    HISTORICAL = "historical"
    LIVE = "live"


@dataclass(frozen=True)
class ReadOnlyMarketDataCredential:
    """Metadata about a data-login context; never the actual secret/token."""

    provider: str
    account_class: str
    uses: tuple[DataCredentialUse, ...]
    read_only: bool = True
    affects_target_persona: bool = False

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip()
        account_class = str(self.account_class or "").strip().lower()
        if not provider:
            raise ValueError("data credential provider is required")
        if not account_class:
            raise ValueError("data credential account_class is required")
        normalized: list[DataCredentialUse] = []
        for item in self.uses:
            use = item if isinstance(item, DataCredentialUse) else DataCredentialUse(str(item))
            if use not in normalized:
                normalized.append(use)
        if not normalized:
            raise ValueError("data credential requires at least one read-only market-data use")
        if not self.read_only:
            raise ValueError("TradeBrain data credential context must remain read_only")
        if self.affects_target_persona:
            raise ValueError("data credential account class cannot affect resident target persona")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "account_class", account_class)
        object.__setattr__(self, "uses", tuple(normalized))


def validate_resident_brokerage_profile(profile: EquityBrokerageProfile) -> None:
    """Reject any fee persona that is not explicitly the resident Zerodha path."""

    if not profile.version.startswith(_RESIDENT_BROKERAGE_PREFIX):
        raise ValueError(
            "TradeBrain BSE target trader is resident_individual; "
            "market-data credential account type must not select another brokerage persona"
        )


def _resident_profile(profile: EquityBrokerageProfile | None) -> EquityBrokerageProfile:
    selected = zerodha_resident_brokerage_2026_08_21() if profile is None else profile
    validate_resident_brokerage_profile(selected)
    return selected


def build_resident_advice_costed_plan_snapshot(
    base_setup: object,
    *,
    position: EquityAdvicePosition,
    schedule: ZerodhaEquityChargeSchedule,
    slippage: SlippageAssumption,
    brokerage: EquityBrokerageProfile | None = None,
    data_credential: ReadOnlyMarketDataCredential | None = None,
) -> AdviceCostedPlanSnapshot:
    """Build the canonical resident cost overlay; data-login class is irrelevant."""

    if data_credential is not None and not data_credential.read_only:
        raise ValueError("market-data credential must be read_only")
    selected = _resident_profile(brokerage)
    return build_advice_costed_plan_snapshot(
        base_setup,
        position=position,
        schedule=schedule,
        brokerage=selected,
        slippage=slippage,
    )


def cost_resolved_resident_advice_outcome(
    setup: AdviceCostedPlanSnapshot,
    base_outcome: object,
    *,
    entry_at,
    exit_at,
    schedule: ZerodhaEquityChargeSchedule,
    slippage: SlippageAssumption,
    brokerage: EquityBrokerageProfile | None = None,
    include_dp_charge: bool = True,
    female_primary_holder: bool = False,
    auto_squareoff_order_count: int = 0,
) -> AdviceCostedPlanOutcome:
    """Apply resolved costs using the resident persona frozen into the setup."""

    selected = _resident_profile(brokerage)
    return cost_resolved_advice_outcome(
        setup,
        base_outcome,
        entry_at=entry_at,
        exit_at=exit_at,
        schedule=schedule,
        brokerage=selected,
        slippage=slippage,
        include_dp_charge=include_dp_charge,
        female_primary_holder=female_primary_holder,
        auto_squareoff_order_count=auto_squareoff_order_count,
    )
