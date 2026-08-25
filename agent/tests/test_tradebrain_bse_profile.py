"""Regression tests for the opt-in TradeBrain BSE profile boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import time

import pytest

from src.tradebrain.profile import (
    TRADEBRAIN_BSE_PROFILE,
    TRADEBRAIN_PROFILE_ENV,
    active_profile_name,
    get_active_tradebrain_policy,
    tradebrain_bse_policy,
)

pytestmark = pytest.mark.unit


def test_profile_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TRADEBRAIN_PROFILE_ENV, raising=False)
    assert active_profile_name() is None
    assert get_active_tradebrain_policy() is None


def test_unknown_profile_does_not_enable_tradebrain() -> None:
    environ = {TRADEBRAIN_PROFILE_ENV: "some_other_profile"}
    assert active_profile_name(environ) is None
    assert get_active_tradebrain_policy(environ) is None


def test_exact_opt_in_enables_tradebrain_bse() -> None:
    environ = {TRADEBRAIN_PROFILE_ENV: "  TRADEBRAIN_BSE  "}
    assert active_profile_name(environ) == TRADEBRAIN_BSE_PROFILE
    assert get_active_tradebrain_policy(environ) is tradebrain_bse_policy()


def test_bse_profile_is_resident_advisory_only_and_auto_execution_off() -> None:
    policy = tradebrain_bse_policy()
    assert policy.advisory_only is True
    assert policy.auto_execution is False
    assert policy.target_trader_persona == "resident_individual"


def test_bse_profile_targets_bse_ltd_on_nse() -> None:
    policy = tradebrain_bse_policy()
    assert policy.market_focus == "india_equity"
    assert policy.primary_security.company_name == "BSE Ltd"
    assert policy.primary_security.instrument == "NSE:BSE"


def test_day_hard_boundaries() -> None:
    day = tradebrain_bse_policy().day
    assert day.long_allowed is True
    assert day.short_allowed is True
    assert day.fresh_entry_cutoff == time(15, 10)
    assert day.flat_by == time(15, 15)
    assert day.timezone == "Asia/Kolkata"


def test_swing_hard_boundaries() -> None:
    swing = tradebrain_bse_policy().swing
    assert swing.long_allowed is True
    assert swing.short_allowed is False
    assert swing.mtf_allowed is False
    assert swing.mtf_required is False
    assert swing.funding_mechanism == "CASH_DELIVERY_OWN_FUNDS_ONLY"


def test_ai_cannot_override_hard_rules() -> None:
    ai = tradebrain_bse_policy().ai
    assert ai.context_allowed is True
    assert ai.hard_rule_override_allowed is False


def test_retired_rescue_architecture_stays_disabled() -> None:
    legacy = tradebrain_bse_policy().legacy
    assert legacy.l1_l2_l3_enabled is False
    assert legacy.rescue_averaging_enabled is False


def test_policy_contract_is_immutable() -> None:
    policy = tradebrain_bse_policy()
    with pytest.raises(FrozenInstanceError):
        policy.auto_execution = True  # type: ignore[misc]
