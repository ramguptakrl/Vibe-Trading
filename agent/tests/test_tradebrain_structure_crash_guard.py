from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.tradebrain.market_data import BSEMarketDataSnapshot, FreshnessStatus, OHLCVBar
from src.tradebrain.structure import (
    CoverageState,
    StructureConfig,
    StructureValidationError,
    TrendState,
    build_multi_timeframe_structure,
    build_timeframe_structure,
    derive_higher_timeframe_bars,
)
from src.tradebrain.crash_guard import (
    CrashGuardConfig,
    CrashGuardState,
    evaluate_crash_guard,
)
from src.tradebrain.structure_context import build_bse_structure_risk_context
from src.tradebrain.data_intelligence import BSEDataIntelligenceContext

IST = ZoneInfo("Asia/Kolkata")
ISIN = "INE118H01025"


def bars(n=80, *, start=None, step=0.2, interval_minutes=5, last_shock=None):
    if start is None:
        start = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
    out = []
    for i in range(n):
        close = 100 + step * i
        op = close - 0.05 if step >= 0 else close + 0.05
        high = max(op, close) + 0.2
        low = min(op, close) - 0.2
        vol = 1000.0
        out.append(
            OHLCVBar(
                (start + timedelta(minutes=interval_minutes * i)).isoformat(),
                op,
                high,
                low,
                close,
                vol,
            )
        )
    if last_shock is not None:
        p = out[-1]
        close, op, high, low, vol = last_shock
        out[-1] = OHLCVBar(p.timestamp, op, high, low, close, vol)
    return tuple(out)


def snapshot(bs, *, interval="5m", freshness=FreshnessStatus.FRESH):
    return BSEMarketDataSnapshot(
        isin=ISIN,
        qualified_symbol="NSE:BSE",
        vibe_symbol="BSE.NS",
        market="india_equity",
        interval=interval,
        source_name="test",
        requested_start="2026-01-01",
        requested_end="2026-08-21",
        retrieved_at="2026-08-21T12:00:00+05:30",
        data_as_of=bs[-1].timestamp,
        age_seconds=0,
        freshness=freshness,
        frame_sha256="a" * 64,
        bars=tuple(bs),
        evidence=object(),
    )


def test_native_partial_bar_excluded():
    bs = bars(2)
    snap = snapshot(bs)
    derived = derive_higher_timeframe_bars(
        snap, target_interval="5m", as_of=bs[-1].timestamp
    )
    assert len(derived) == 1
    assert derived[-1].timestamp == bs[0].timestamp


def test_resample_only_complete_buckets():
    bs = bars(10)
    snap = snapshot(bs)
    asof = datetime(2026, 8, 21, 9, 55, tzinfo=IST)
    derived = derive_higher_timeframe_bars(snap, target_interval="15m", as_of=asof)
    assert [x.timestamp for x in derived] == [
        datetime(2026, 8, 21, 9, 15, tzinfo=IST).isoformat(),
        datetime(2026, 8, 21, 9, 30, tzinfo=IST).isoformat(),
    ]


def test_resample_rejects_holey_bucket():
    bs = list(bars(6))
    del bs[1]
    snap = snapshot(bs)
    derived = derive_higher_timeframe_bars(
        snap,
        target_interval="15m",
        as_of=datetime(2026, 8, 21, 9, 45, tzinfo=IST),
    )
    assert len(derived) == 1
    assert derived[0].timestamp.endswith("09:30:00+05:30")


def test_cannot_derive_finer_interval():
    snap = snapshot(bars(30), interval="5m")
    with pytest.raises(StructureValidationError, match="finer"):
        derive_higher_timeframe_bars(
            snap,
            target_interval="1m",
            as_of=datetime(2026, 8, 21, 13, 0, tzinfo=IST),
        )


def test_swing_requires_right_confirmation_no_lookahead():
    start = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
    highs = [101, 102, 105, 102, 101]
    bs = []
    for i, h in enumerate(highs):
        bs.append(
            OHLCVBar(
                (start + timedelta(minutes=5 * i)).isoformat(),
                100,
                h,
                99,
                100,
                1000,
            )
        )
    early = build_timeframe_structure(
        bs,
        interval="5m",
        as_of=bs[3].timestamp,
        config=StructureConfig(ema_fast=2, ema_slow=3, ema_long=4),
    )
    final = build_timeframe_structure(
        bs,
        interval="5m",
        as_of=bs[4].timestamp,
        config=StructureConfig(ema_fast=2, ema_slow=3, ema_long=4),
    )
    assert early.confirmed_swing_highs == ()
    assert final.confirmed_swing_highs == ((bs[2].timestamp, 105),)


def test_window_high_not_claimed_as_ath_without_complete_history():
    bs = bars(30)
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp)
    assert s.observed_range.coverage is CoverageState.OBSERVED_WINDOW
    assert s.observed_range.all_time_high is None


def test_complete_history_may_expose_ath():
    bs = bars(30)
    s = build_timeframe_structure(
        bs, interval="5m", as_of=bs[-1].timestamp, history_complete=True
    )
    assert s.observed_range.coverage is CoverageState.COMPLETE_HISTORY
    assert s.observed_range.all_time_high == max(x.high for x in bs)


def test_52_week_only_with_sufficient_daily_history():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    bs = bars(252, start=start, step=0.1, interval_minutes=1440)
    s = build_timeframe_structure(bs, interval="1d", as_of=bs[-1].timestamp)
    assert s.observed_range.fifty_two_week_high == max(x.high for x in bs)
    short = build_timeframe_structure(bs[:251], interval="1d", as_of=bs[250].timestamp)
    assert short.observed_range.fifty_two_week_high is None


def test_ema_insufficient_is_none_not_fake_value():
    bs = bars(10)
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp)
    assert s.ema_fast is None and s.ema_slow is None and s.ema_long is None
    assert s.trend is TrendState.UNKNOWN


def test_uptrend_classification():
    bs = bars(80, step=0.2)
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp)
    assert s.trend is TrendState.UP


def test_downtrend_classification():
    bs = bars(80, step=-0.2)
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp)
    assert s.trend is TrendState.DOWN


def test_sideways_classification():
    start = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
    bs = []
    for i in range(80):
        c = 100 + (0.01 if i % 2 else -0.01)
        bs.append(
            OHLCVBar(
                (start + timedelta(minutes=5 * i)).isoformat(),
                c,
                c + 0.1,
                c - 0.1,
                c,
                1000,
            )
        )
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp)
    assert s.trend is TrendState.SIDEWAYS


def test_structural_levels_are_deterministic_and_clustered():
    start = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
    highs = [101, 103, 105, 103, 101, 103, 105.2, 103, 101]
    lows = [99, 98, 97, 98, 99, 98, 97.1, 98, 99]
    bs = [
        OHLCVBar(
            (start + timedelta(minutes=5 * i)).isoformat(),
            100,
            highs[i],
            lows[i],
            100,
            1000,
        )
        for i in range(len(highs))
    ]
    cfg = StructureConfig(
        ema_fast=2, ema_slow=3, ema_long=4, cluster_tolerance_pct=0.005
    )
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp, config=cfg)
    assert any(level.touches >= 2 and level.kind == "resistance" for level in s.levels)
    assert any(level.touches >= 2 and level.kind == "support" for level in s.levels)


def test_volume_ratio_uses_prior_baseline():
    bs = list(bars(30))
    p = bs[-1]
    bs[-1] = OHLCVBar(p.timestamp, p.open, p.high, p.low, p.close, 2000)
    cfg = StructureConfig(volume_window=20)
    s = build_timeframe_structure(bs, interval="5m", as_of=bs[-1].timestamp, config=cfg)
    assert s.volume_ratio == pytest.approx(2.0)


def test_multi_timeframe_uses_single_snapshot_hash_and_no_finer_fetch():
    bs = bars(80)
    snap = snapshot(bs)
    ctx = build_multi_timeframe_structure(
        snap,
        as_of=datetime(2026, 8, 21, 15, 0, tzinfo=IST),
        requested_intervals=("5m", "15m", "30m"),
    )
    assert ctx.source_frame_sha256 == snap.frame_sha256
    assert {x.interval for x in ctx.timeframes} == {"5m", "15m", "30m"}


def test_multi_timeframe_requires_fresh_phase4_snapshot():
    snap = snapshot(bars(40), freshness=FreshnessStatus.STALE)
    with pytest.raises(StructureValidationError, match="fresh"):
        build_multi_timeframe_structure(
            snap, as_of=datetime(2026, 8, 21, 13, 0, tzinfo=IST)
        )


def test_structure_config_is_provisional_and_frozen():
    cfg = StructureConfig()
    assert cfg.learned is False
    with pytest.raises(ValueError, match="not learned"):
        StructureConfig(learned=True)
    with pytest.raises(FrozenInstanceError):
        cfg.ema_fast = 10


def structure_for(snap, asof=None, intervals=("5m",)):
    if asof is None:
        asof = datetime.fromisoformat(snap.bars[-1].timestamp) + timedelta(minutes=5)
    return build_multi_timeframe_structure(
        snap, as_of=asof, requested_intervals=intervals
    )


def test_crash_guard_data_insufficient_not_normal():
    snap = snapshot(bars(10))
    st = structure_for(snap)
    result = evaluate_crash_guard(snap, st)
    assert result.state is CrashGuardState.DATA_INSUFFICIENT
    assert result.usable is False


def test_crash_guard_normal_does_not_block():
    snap = snapshot(bars(40, step=0.05))
    st = structure_for(snap)
    result = evaluate_crash_guard(snap, st)
    assert result.state is CrashGuardState.NORMAL
    assert not result.block_day_long
    assert not result.block_swing_long
    assert result.create_short_signal is False


def test_crash_guard_elevated_does_not_hard_block():
    bs = list(bars(40, step=0))
    prev = bs[-2].close
    p = bs[-1]
    close = prev * 0.975
    bs[-1] = OHLCVBar(p.timestamp, prev * 0.99, prev * 1.001, close * 0.999, close, 1000)
    snap = snapshot(bs)
    st = structure_for(snap)
    result = evaluate_crash_guard(snap, st)
    assert result.state is CrashGuardState.ELEVATED
    assert not result.block_day_long
    assert result.create_short_signal is False


def test_crash_guard_severe_blocks_longs_but_never_creates_short():
    bs = list(bars(40, step=0))
    p = bs[-1]
    bs[-1] = OHLCVBar(p.timestamp, 97, 99, 89, 90, 3500)
    snap = snapshot(bs)
    st = structure_for(snap)
    result = evaluate_crash_guard(snap, st)
    assert result.state is CrashGuardState.SEVERE
    assert result.block_day_long is True
    assert result.block_swing_long is True
    assert result.create_short_signal is False


def test_crash_guard_uses_asof_boundary_not_future_snapshot_bars():
    bs = list(bars(45, step=0))
    p = bs[-1]
    bs[-1] = OHLCVBar(p.timestamp, 97, 99, 89, 90, 4000)
    snap = snapshot(bs)
    asof = datetime.fromisoformat(bs[-2].timestamp) + timedelta(minutes=5)
    st = build_multi_timeframe_structure(snap, as_of=asof, requested_intervals=("5m",))
    result = evaluate_crash_guard(snap, st)
    assert result.state is CrashGuardState.NORMAL
    assert st.native_latest_timestamp == bs[-2].timestamp


def test_crash_guard_rejects_different_snapshot_hash():
    snap = snapshot(bars(40))
    st = structure_for(snap)
    other = replace(snap, frame_sha256="b" * 64)
    with pytest.raises(ValueError, match="same Phase-4"):
        evaluate_crash_guard(other, st)


def test_crash_config_is_provisional():
    cfg = CrashGuardConfig()
    assert cfg.learned is False
    with pytest.raises(ValueError, match="not learned"):
        CrashGuardConfig(learned=True)


@dataclass(frozen=True)
class Foundation:
    market_data_ready: bool = True
    intelligence_ready: bool = True
    market_structure_ready: bool = False
    historical_outcomes_ready: bool = False
    hard_rule_arbiter_ready: bool = False

    @property
    def decision_ready(self):
        return all(
            (
                self.market_data_ready,
                self.intelligence_ready,
                self.market_structure_ready,
                self.historical_outcomes_ready,
                self.hard_rule_arbiter_ready,
            )
        )

    @property
    def missing_layers(self):
        names = {
            "market_data": self.market_data_ready,
            "intelligence": self.intelligence_ready,
            "market_structure": self.market_structure_ready,
            "historical_outcomes": self.historical_outcomes_ready,
            "hard_rule_arbiter": self.hard_rule_arbiter_ready,
        }
        return tuple(k for k, v in names.items() if not v)


def test_phase5_context_advances_structure_only_and_still_not_decision_ready():
    snap = snapshot(bars(50, step=0.05))
    phase4 = BSEDataIntelligenceContext(
        Foundation(), snap, type("Intel", (), {"ready": True})()
    )
    ctx = build_bse_structure_risk_context(
        phase4,
        as_of=datetime.fromisoformat(snap.bars[-1].timestamp) + timedelta(minutes=5),
        requested_intervals=("5m", "15m"),
    )
    assert ctx.readiness.market_structure_ready is True
    assert ctx.readiness.historical_outcomes_ready is False
    assert ctx.readiness.hard_rule_arbiter_ready is False
    assert ctx.decision_ready is False
    assert ctx.missing_layers == ("historical_outcomes", "hard_rule_arbiter")


def test_phase5_context_does_not_mark_structure_ready_if_phase4_intelligence_not_ready():
    snap = snapshot(bars(50, step=0.05))
    phase4 = BSEDataIntelligenceContext(
        Foundation(), snap, type("Intel", (), {"ready": False})()
    )
    ctx = build_bse_structure_risk_context(
        phase4,
        as_of=datetime.fromisoformat(snap.bars[-1].timestamp) + timedelta(minutes=5),
    )
    assert ctx.readiness.market_structure_ready is False


def test_requested_timeframe_missing_keeps_structure_not_ready():
    snap = snapshot(bars(4))
    ctx = build_multi_timeframe_structure(
        snap,
        as_of=datetime(2026, 8, 21, 9, 35, tzinfo=IST),
        requested_intervals=("5m", "30m"),
    )
    assert ctx.ready is False


def test_weekly_derivation_deferred_without_exchange_calendar():
    snap = snapshot(bars(80))
    with pytest.raises(StructureValidationError, match="weekly/monthly"):
        derive_higher_timeframe_bars(
            snap,
            target_interval="7d",
            as_of=datetime(2026, 8, 22, 16, 0, tzinfo=IST),
        )
