"""Immutable policy contract for the opt-in ``tradebrain_bse`` profile.

The profile is advisory-only. Hard owner boundaries are explicit and are not
learnable parameters. The target trader is a resident individual; broker
credentials used only for data do not alter this policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Mapping

from src.config.tradebrain import TRADEBRAIN_PROFILE_ENV, get_tradebrain_profile_value

TRADEBRAIN_BSE_PROFILE = "tradebrain_bse"


@dataclass(frozen=True)
class SecurityTarget:
    company_name: str
    exchange: str
    symbol: str
    market: str

    @property
    def instrument(self) -> str:
        return f"{self.exchange}:{self.symbol}"


@dataclass(frozen=True)
class DayPolicy:
    long_allowed: bool
    short_allowed: bool
    flat_by: time
    timezone: str
    fresh_entry_cutoff: time = time(hour=15, minute=10)


@dataclass(frozen=True)
class SwingPolicy:
    long_allowed: bool
    short_allowed: bool
    funding_mechanism: str
    mtf_allowed: bool
    mtf_required: bool


@dataclass(frozen=True)
class AIPolicy:
    context_allowed: bool
    hard_rule_override_allowed: bool


@dataclass(frozen=True)
class LegacyPolicy:
    l1_l2_l3_enabled: bool
    rescue_averaging_enabled: bool


@dataclass(frozen=True)
class TradeBrainBSEPolicy:
    profile_name: str
    advisory_only: bool
    auto_execution: bool
    market_focus: str
    primary_security: SecurityTarget
    day: DayPolicy
    swing: SwingPolicy
    ai: AIPolicy
    legacy: LegacyPolicy
    target_trader_persona: str = "resident_individual"


_POLICY = TradeBrainBSEPolicy(
    profile_name=TRADEBRAIN_BSE_PROFILE,
    advisory_only=True,
    auto_execution=False,
    market_focus="india_equity",
    primary_security=SecurityTarget(
        company_name="BSE Ltd",
        exchange="NSE",
        symbol="BSE",
        market="India",
    ),
    day=DayPolicy(
        long_allowed=True,
        short_allowed=True,
        flat_by=time(hour=15, minute=15),
        timezone="Asia/Kolkata",
        fresh_entry_cutoff=time(hour=15, minute=10),
    ),
    swing=SwingPolicy(
        long_allowed=True,
        short_allowed=False,
        funding_mechanism="ZERODHA_MTF_ONLY",
        mtf_allowed=True,
        mtf_required=True,
    ),
    ai=AIPolicy(
        context_allowed=True,
        hard_rule_override_allowed=False,
    ),
    legacy=LegacyPolicy(
        l1_l2_l3_enabled=False,
        rescue_averaging_enabled=False,
    ),
)


def tradebrain_bse_policy() -> TradeBrainBSEPolicy:
    return _POLICY


def active_profile_name(environ: Mapping[str, str] | None = None) -> str | None:
    value = get_tradebrain_profile_value(environ)
    if value == TRADEBRAIN_BSE_PROFILE:
        return TRADEBRAIN_BSE_PROFILE
    return None


def get_active_tradebrain_policy(
    environ: Mapping[str, str] | None = None,
) -> TradeBrainBSEPolicy | None:
    if active_profile_name(environ) == TRADEBRAIN_BSE_PROFILE:
        return _POLICY
    return None
