from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.tradebrain.final_guidance import HistoricalReliabilitySummary
from src.tradebrain.journal import TradeBrainJournalStore
from src.tradebrain.kite_readonly import KiteConfiguration, KiteReadOnlyAdapter
from src.tradebrain.market_calendar import load_exchange_calendar, resolve_trading_day
from src.tradebrain.validation_readiness import assess_validation_readiness


IST = ZoneInfo("Asia/Kolkata")


def test_verified_calendar_is_explicit_and_fail_closed(tmp_path: Path):
    path = tmp_path / "nse_calendar.json"
    missing = resolve_trading_day(datetime(2026, 8, 24, 10, 0, tzinfo=IST), path)
    assert missing.verified is False
    assert missing.is_trading_day is False
    assert missing.blocker == "verified_nse_exchange_calendar_missing"

    path.write_text(
        json.dumps(
            {
                "exchange": "NSE",
                "timezone": "Asia/Kolkata",
                "valid_from": "2026-08-24",
                "valid_to": "2026-08-28",
                "trading_dates": ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"],
                "source_name": "NSE official session calendar fixture",
                "source_url": "https://www.nseindia.com/",
                "source_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    snapshot = load_exchange_calendar(path)
    assert len(snapshot.snapshot_sha256) == 64
    verified = resolve_trading_day(datetime(2026, 8, 24, 10, 0, tzinfo=IST), path)
    assert verified.verified is True
    assert verified.is_trading_day is True
    assert verified.blocker is None

    outside = resolve_trading_day(datetime(2026, 8, 31, 10, 0, tzinfo=IST), path)
    assert outside.verified is False
    assert outside.is_trading_day is False
    assert outside.blocker == "verified_nse_exchange_calendar_out_of_range"


def test_validation_readiness_requires_real_oos_walkforward_costed_history_and_shadow():
    historical = HistoricalReliabilitySummary(
        sample_count=120,
        out_of_sample=True,
        walk_forward=True,
        real_history=True,
        no_lookahead_verified=True,
        costs_complete=True,
        expectancy_net_r=0.12,
        hit_rate=0.55,
        max_drawdown_net_r=-4.2,
        source_sha256="b" * 64,
    )
    pre_live = assess_validation_readiness(
        historical,
        live_market_data_connected=False,
        shadow_sample_count=0,
    )
    assert pre_live.ready_for_candidate_guidance is True
    assert pre_live.ready_for_live_shadow is False
    assert pre_live.ready_for_production_review is False

    production_review = assess_validation_readiness(
        historical,
        live_market_data_connected=True,
        shadow_sample_count=25,
        min_shadow_samples=20,
    )
    assert production_review.ready_for_candidate_guidance is True
    assert production_review.ready_for_live_shadow is True
    assert production_review.ready_for_production_review is True
    assert production_review.blockers == ()


def test_kite_adapter_surface_has_no_broker_write_methods():
    adapter = KiteReadOnlyAdapter(KiteConfiguration(api_key=None, access_token=None))
    assert adapter.credential.read_only is True
    assert adapter.credential.affects_target_persona is False
    assert adapter.readiness.read_only is True
    assert adapter.readiness.broker_order_write_allowed is False
    for method in adapter.forbidden_write_methods():
        assert not hasattr(adapter, method)


def test_journal_rejects_swing_short_and_invalid_sha(tmp_path: Path):
    store = TradeBrainJournalStore(tmp_path / "journal.json")
    with pytest.raises(ValueError, match="SHA-256"):
        store.create_shadow_advisory(
            advisory_id="bad-sha",
            guidance_sha256="not-a-sha",
            mode="day",
            direction="long",
            entry=100,
            target=110,
            stop=95,
        )
    with pytest.raises(ValueError, match="SWING SHORT"):
        store.create_shadow_advisory(
            advisory_id="bad-swing",
            guidance_sha256="c" * 64,
            mode="swing",
            direction="short",
            entry=100,
            target=90,
            stop=105,
        )
