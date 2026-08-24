from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.tradebrain.journal import ManualTradeStatus, ShadowStatus, TradeBrainJournalStore
from src.tradebrain.session_modes import OperatingMode, resolve_operating_state


IST = ZoneInfo("Asia/Kolkata")


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 8, 24, hour, minute, tzinfo=IST)


def test_operating_modes_and_safety_boundaries():
    active = resolve_operating_state(_dt(10, 0), is_trading_day=True)
    assert active.mode is OperatingMode.MARKET_ACTIVE
    assert active.permissions.fresh_day_entry_allowed is True
    assert active.permissions.broker_order_write_allowed is False
    assert active.permissions.auto_promotion_allowed is False

    exit_window = resolve_operating_state(_dt(15, 12), is_trading_day=True)
    assert exit_window.mode is OperatingMode.DAY_EXIT_WINDOW
    assert exit_window.permissions.fresh_day_entry_allowed is False
    assert exit_window.permissions.day_exit_priority is True

    post_flat = resolve_operating_state(_dt(15, 20), is_trading_day=True)
    assert post_flat.mode is OperatingMode.MARKET_ACTIVE
    assert post_flat.permissions.fresh_day_entry_allowed is False
    assert post_flat.permissions.day_exit_priority is True

    research = resolve_operating_state(_dt(17, 0), is_trading_day=True)
    assert research.mode is OperatingMode.AFTER_MARKET
    assert research.permissions.replay_allowed is True
    assert research.permissions.challenger_research_allowed is True
    assert research.permissions.production_mutation_allowed is False

    closed = resolve_operating_state(_dt(10, 0), is_trading_day=False)
    assert closed.mode is OperatingMode.OFF_HOURS


def test_manual_trade_journal_round_trip(tmp_path: Path):
    store = TradeBrainJournalStore(tmp_path / "journal.json")
    opened = store.create_manual_trade(
        advisory_id="adv-1",
        guidance_sha256="a" * 64,
        mode="day",
        direction="long",
        planned_entry=100,
        planned_target=110,
        planned_stop=95,
        actual_entry=101,
        quantity=10,
    )
    assert opened.status is ManualTradeStatus.OPEN
    assert len(store.list_manual_trades()) == 1

    closed = store.close_manual_trade(
        opened.trade_id,
        actual_exit=108,
        costs=5,
        exit_reason="manual target capture",
        actual_outcome="profit",
        predicted_outcome="tp_first",
    )
    assert closed.status is ManualTradeStatus.CLOSED
    assert closed.realized_pnl == pytest.approx(65.0)
    assert closed.record_sha256 != opened.record_sha256

    with pytest.raises(ValueError, match="already closed"):
        store.close_manual_trade(
            opened.trade_id,
            actual_exit=108,
            costs=5,
            exit_reason="duplicate",
            actual_outcome="profit",
        )


def test_shadow_advisory_round_trip(tmp_path: Path):
    store = TradeBrainJournalStore(tmp_path / "journal.json")
    pending = store.create_shadow_advisory(
        advisory_id="adv-2",
        guidance_sha256="b" * 64,
        mode="swing",
        direction="long",
        entry=100,
        target=120,
        stop=90,
    )
    assert pending.status is ShadowStatus.PENDING

    resolved = store.resolve_shadow_advisory(
        pending.shadow_id,
        outcome="tp_first",
        gross_r=2.0,
    )
    assert resolved.status is ShadowStatus.RESOLVED
    assert resolved.gross_r == pytest.approx(2.0)
