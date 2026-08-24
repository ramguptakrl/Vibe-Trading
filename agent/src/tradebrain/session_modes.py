"""Deterministic India-equity operating modes for the TradeBrain BSE profile.

This module controls *when* the resident advisory brain may observe, advise,
flatten DAY exposure, or run after-market research. It never places orders and
it never mutates champion policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

from src.tradebrain.profile import tradebrain_bse_policy

__all__ = [
    "OperatingMode",
    "OperatingPermissions",
    "OperatingState",
    "resolve_operating_state",
]


class OperatingMode(str, Enum):
    MARKET_ACTIVE = "market_active"
    DAY_EXIT_WINDOW = "day_exit_window"
    AFTER_MARKET = "after_market"
    OFF_HOURS = "off_hours"


@dataclass(frozen=True)
class OperatingPermissions:
    observe_market: bool
    publish_advisory: bool
    fresh_day_entry_allowed: bool
    day_exit_priority: bool
    replay_allowed: bool
    challenger_research_allowed: bool
    production_mutation_allowed: bool
    broker_order_write_allowed: bool
    auto_promotion_allowed: bool


@dataclass(frozen=True)
class OperatingState:
    mode: OperatingMode
    as_of: str
    timezone: str
    is_trading_day: bool
    market_open: str
    fresh_day_entry_cutoff: str
    day_flat_by: str
    market_close: str
    after_market_end: str
    permissions: OperatingPermissions


def _permissions(
    mode: OperatingMode,
    *,
    after_day_flat: bool = False,
) -> OperatingPermissions:
    if mode is OperatingMode.MARKET_ACTIVE:
        return OperatingPermissions(
            observe_market=True,
            publish_advisory=True,
            fresh_day_entry_allowed=not after_day_flat,
            day_exit_priority=after_day_flat,
            replay_allowed=False,
            challenger_research_allowed=False,
            production_mutation_allowed=False,
            broker_order_write_allowed=False,
            auto_promotion_allowed=False,
        )
    if mode is OperatingMode.DAY_EXIT_WINDOW:
        return OperatingPermissions(
            observe_market=True,
            publish_advisory=True,
            fresh_day_entry_allowed=False,
            day_exit_priority=True,
            replay_allowed=False,
            challenger_research_allowed=False,
            production_mutation_allowed=False,
            broker_order_write_allowed=False,
            auto_promotion_allowed=False,
        )
    if mode is OperatingMode.AFTER_MARKET:
        return OperatingPermissions(
            observe_market=False,
            publish_advisory=False,
            fresh_day_entry_allowed=False,
            day_exit_priority=False,
            replay_allowed=True,
            challenger_research_allowed=True,
            production_mutation_allowed=False,
            broker_order_write_allowed=False,
            auto_promotion_allowed=False,
        )
    return OperatingPermissions(
        observe_market=False,
        publish_advisory=False,
        fresh_day_entry_allowed=False,
        day_exit_priority=False,
        replay_allowed=True,
        challenger_research_allowed=True,
        production_mutation_allowed=False,
        broker_order_write_allowed=False,
        auto_promotion_allowed=False,
    )


def resolve_operating_state(
    at: datetime,
    *,
    is_trading_day: bool,
    market_open: time = time(9, 15),
    market_close: time = time(15, 30),
    after_market_end: time = time(20, 0),
) -> OperatingState:
    """Resolve the deterministic operating mode in Asia/Kolkata.

    ``is_trading_day`` deliberately comes from the caller. Production callers
    must bind it to a verified exchange calendar; tests can pass a fixed value
    without embedding a stale holiday table in policy code.
    """

    policy = tradebrain_bse_policy()
    tz = ZoneInfo(policy.day.timezone)
    local = at.replace(tzinfo=tz) if at.tzinfo is None else at.astimezone(tz)
    clock = local.timetz().replace(tzinfo=None)
    cutoff = policy.day.fresh_entry_cutoff
    flat_by = policy.day.flat_by

    if not is_trading_day:
        mode = OperatingMode.OFF_HOURS
        after_day_flat = False
    elif market_open <= clock < cutoff:
        mode = OperatingMode.MARKET_ACTIVE
        after_day_flat = False
    elif cutoff <= clock < flat_by:
        mode = OperatingMode.DAY_EXIT_WINDOW
        after_day_flat = False
    elif flat_by <= clock < market_close:
        # Exchange is still open. DAY must already be flat, while SWING and
        # market observation remain active.
        mode = OperatingMode.MARKET_ACTIVE
        after_day_flat = True
    elif market_close <= clock < after_market_end:
        mode = OperatingMode.AFTER_MARKET
        after_day_flat = False
    else:
        mode = OperatingMode.OFF_HOURS
        after_day_flat = False

    return OperatingState(
        mode=mode,
        as_of=local.isoformat(),
        timezone=policy.day.timezone,
        is_trading_day=is_trading_day,
        market_open=market_open.isoformat(timespec="minutes"),
        fresh_day_entry_cutoff=cutoff.isoformat(timespec="minutes"),
        day_flat_by=flat_by.isoformat(timespec="minutes"),
        market_close=market_close.isoformat(timespec="minutes"),
        after_market_end=after_market_end.isoformat(timespec="minutes"),
        permissions=_permissions(mode, after_day_flat=after_day_flat),
    )
