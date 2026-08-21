"""Immutable policy contract for the opt-in ``tradebrain_bse`` profile.

Phase 1 deliberately stops at the policy boundary. This module does not patch,
wrap, or register any existing Vibe-Trading tool, broker, backtest engine, API
route, CLI command, or frontend component. Therefore normal Vibe behavior stays
unchanged unless a future integration point explicitly calls
:func:`get_active_tradebrain_policy` and enforces the returned policy.

The hard values here come from the TradeBrain/BSE master specification and are
not learnable parameters. Future backtesting may challenge soft strategy inputs,
but it must not silently rewrite these boundaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from typing import Mapping

TRADEBRAIN_PROFILE_ENV = "VIBE_TRADING_PROFILE"
TRADEBRAIN_BSE_PROFILE = "tradebrain_bse"


@dataclass(frozen=True)
class SecurityTarget:
    """Human-readable primary security target for the BSE profile."""

    company_name: str
    exchange: str
    symbol: str
    market: str

    @property
    def instrument(self) -> str:
        return f"{self.exchange}:{self.symbol}"


@dataclass(frozen=True)
class DayPolicy:
    """Immutable DAY-mode boundaries."""

    long_allowed: bool
    short_allowed: bool
    flat_by: time
    timezone: str


@dataclass(frozen=True)
class SwingPolicy:
    """Immutable SWING/POSITION boundaries for the current architecture."""

    long_allowed: bool
    short_allowed: bool
    funding_mechanism: str


@dataclass(frozen=True)
class AIPolicy:
    """Authority boundary for LLM/agent input."""

    context_allowed: bool
    hard_rule_override_allowed: bool


@dataclass(frozen=True)
class LegacyPolicy:
    """Retired strategy components that must not re-enter active logic."""

    l1_l2_l3_enabled: bool
    rescue_averaging_enabled: bool


@dataclass(frozen=True)
class TradeBrainBSEPolicy:
    """Phase-1 policy envelope for future BSE-specific integration points."""

    profile_name: str
    advisory_only: bool
    auto_execution: bool
    market_focus: str
    primary_security: SecurityTarget
    day: DayPolicy
    swing: SwingPolicy
    ai: AIPolicy
    legacy: LegacyPolicy


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
    ),
    swing=SwingPolicy(
        long_allowed=True,
        short_allowed=False,
        funding_mechanism="MTF",
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
    """Return the immutable BSE policy contract."""

    return _POLICY


def active_profile_name(environ: Mapping[str, str] | None = None) -> str | None:
    """Resolve the opt-in TradeBrain profile without changing upstream defaults.

    Only the exact value ``tradebrain_bse`` activates the profile. Missing,
    blank, unknown, or misspelled values all remain disabled, which preserves
    normal Vibe-Trading behavior and fails closed with respect to custom policy
    activation.
    """

    source = os.environ if environ is None else environ
    value = str(source.get(TRADEBRAIN_PROFILE_ENV, "")).strip().lower()
    if value == TRADEBRAIN_BSE_PROFILE:
        return TRADEBRAIN_BSE_PROFILE
    return None


def get_active_tradebrain_policy(
    environ: Mapping[str, str] | None = None,
) -> TradeBrainBSEPolicy | None:
    """Return the BSE policy only when explicitly opted in.

    Phase 1 intentionally provides no automatic wiring into existing Vibe code.
    Future phases must call this function at narrow, tested integration points.
    """

    if active_profile_name(environ) == TRADEBRAIN_BSE_PROFILE:
        return _POLICY
    return None
