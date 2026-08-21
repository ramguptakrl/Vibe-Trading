from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.goal.models import EvidenceInput
from src.tradebrain.market_data import (
    BSEMarketDataSnapshot,
    FreshnessPolicy,
    FreshnessStatus,
    OHLCVBar,
    _bars_hash,
)
from src.tradebrain.relative_market import (
    BenchmarkMarketDataSnapshot,
    RelativeMarketConfig,
    RelativeMarketStatus,
    RelativeMarketValidationError,
    build_relative_market_context,
    fetch_benchmark_market_data,
    nifty50_benchmark,
    relative_market_feature_payload,
)

ASOF = "2026-08-21T12:00:00+05:30"


def _bars(count=30, *, start=100.0, step=1.0, offset_minutes=0):
    base = datetime(2026, 8, 21, 9, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    out = []
    for i in range(count):
        close = start + step * i
        stamp = base + timedelta(minutes=5 * i + offset_minutes)
        out.append(OHLCVBar(stamp.isoformat(), close, close + 1, close - 1, close, 1000 + i))
    return tuple(out)


def _evidence(symbol, source, interval, stamp):
    return EvidenceInput(
        text="test market data",
        evidence_type="market_data",
        source_provider=source,
        source_type="ohlcv",
        source_uri=f"vibe-loader:{source}",
        symbol_universe=[symbol],
        timeframe=interval,
        method="test",
        assumptions={},
        data_as_of=stamp,
        confidence="observed",
    )


def _bse(*, bars=None, source="yahoo", freshness=FreshnessStatus.FRESH, interval="5m"):
    items = _bars() if bars is None else bars
    return BSEMarketDataSnapshot(
        isin="INE118H01025",
        qualified_symbol="NSE:BSE",
        vibe_symbol="BSE.NS",
        market="india_equity",
        interval=interval,
        source_name=source,
        requested_start="2026-08-21",
        requested_end="2026-08-21",
        retrieved_at=ASOF,
        data_as_of=items[-1].timestamp,
        age_seconds=0,
        freshness=freshness,
        frame_sha256=_bars_hash(items),
        bars=items,
        evidence=_evidence("BSE.NS", source, interval, items[-1].timestamp),
    )


def _benchmark(*, bars=None, source="yahoo", freshness=FreshnessStatus.FRESH, interval="5m"):
    items = _bars(start=200) if bars is None else bars
    definition = nifty50_benchmark()
    return BenchmarkMarketDataSnapshot(
        benchmark=definition,
        interval=interval,
        source_name=source,
        requested_start="2026-08-21",
        requested_end="2026-08-21",
        retrieved_at=ASOF,
        data_as_of=items[-1].timestamp,
        age_seconds=0,
        freshness=freshness,
        frame_sha256=_bars_hash(items),
        bars=items,
        evidence=_evidence(definition.loader_symbol, source, interval, items[-1].timestamp),
    )


def test_nifty50_descriptor_and_config_are_provisional():
    descriptor = nifty50_benchmark()
    assert descriptor.benchmark_id == "india:nifty50"
    assert descriptor.loader_symbol == "^NSEI"
    assert RelativeMarketConfig().learned is False
    with pytest.raises(RelativeMarketValidationError, match="controlled promotion"):
        RelativeMarketConfig(learned=True)


def test_aligned_fresh_context_is_observed_and_computes_raw_features():
    context = build_relative_market_context(
        _bse(bars=_bars(start=100, step=2)),
        _benchmark(bars=_bars(start=200, step=1)),
        as_of=ASOF,
    )
    assert context.status is RelativeMarketStatus.OBSERVED
    assert context.ready is True
    assert context.aligned_bar_count == 30
    assert context.relative_return_short == pytest.approx(
        context.bse_return_short - context.benchmark_return_short
    )
    assert context.relative_return_medium == pytest.approx(
        context.bse_return_medium - context.benchmark_return_medium
    )
    assert -1 <= context.correlation <= 1
    assert context.beta is not None
    assert len(context.context_sha256) == 64


@pytest.mark.parametrize("target", ["bse", "benchmark"])
@pytest.mark.parametrize("freshness", [FreshnessStatus.STALE, FreshnessStatus.UNKNOWN])
def test_stale_or_unknown_inputs_fail_closed(target, freshness):
    bse = _bse(freshness=freshness) if target == "bse" else _bse()
    benchmark = _benchmark(freshness=freshness) if target == "benchmark" else _benchmark()
    context = build_relative_market_context(bse, benchmark, as_of=ASOF)
    assert context.status is RelativeMarketStatus.DATA_INSUFFICIENT


@pytest.mark.parametrize(
    ("bse_kwargs", "benchmark_kwargs", "message"),
    [
        ({"interval": "5m"}, {"interval": "15m"}, "intervals"),
        ({"source": "yahoo"}, {"source": "india_broker"}, "same market-data source"),
    ],
)
def test_interval_or_default_source_mismatch_is_rejected(bse_kwargs, benchmark_kwargs, message):
    with pytest.raises(RelativeMarketValidationError, match=message):
        build_relative_market_context(_bse(**bse_kwargs), _benchmark(**benchmark_kwargs), as_of=ASOF)


def test_cross_source_comparison_requires_explicit_opt_out():
    context = build_relative_market_context(
        _bse(source="yahoo"),
        _benchmark(source="india_broker"),
        as_of=ASOF,
        config=RelativeMarketConfig(require_same_source=False),
    )
    assert context.ready is True
    assert context.bse_source_name != context.benchmark_source_name


def test_low_timestamp_alignment_fails_closed():
    context = build_relative_market_context(
        _bse(),
        _benchmark(bars=_bars(start=200, offset_minutes=1)),
        as_of=ASOF,
    )
    assert context.status is RelativeMarketStatus.DATA_INSUFFICIENT
    assert "alignment_ratio_below_minimum" in context.reasons


def test_equivalent_timezone_offsets_align_to_same_instant():
    shifted = []
    for bar in _bars(start=200):
        stamp = datetime.fromisoformat(bar.timestamp).astimezone(timezone.utc)
        shifted.append(OHLCVBar(stamp.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume))
    context = build_relative_market_context(_bse(), _benchmark(bars=tuple(shifted)), as_of=ASOF)
    assert context.ready is True
    assert context.aligned_bar_count == 30


def test_future_benchmark_shock_cannot_rewrite_earlier_context_or_prefix_hash():
    bse_bars = list(_bars())
    benchmark_bars = list(_bars(start=200))
    cutoff = bse_bars[20].timestamp
    config = RelativeMarketConfig(
        min_aligned_bars=10,
        medium_window_bars=10,
        correlation_window_bars=10,
    )
    before = build_relative_market_context(
        _bse(bars=tuple(bse_bars)),
        _benchmark(bars=tuple(benchmark_bars)),
        as_of=cutoff,
        config=config,
    )
    for i in range(21, len(benchmark_bars)):
        old = benchmark_bars[i]
        benchmark_bars[i] = OHLCVBar(old.timestamp, 1, 2, 0.5, 1, old.volume)
    after = build_relative_market_context(
        _bse(bars=tuple(bse_bars)),
        _benchmark(bars=tuple(benchmark_bars)),
        as_of=cutoff,
        config=config,
    )
    assert after.relative_return_medium == before.relative_return_medium
    assert after.benchmark_return_medium == before.benchmark_return_medium
    assert after.benchmark_prefix_sha256 == before.benchmark_prefix_sha256
    assert after.context_sha256 == before.context_sha256


def test_eligible_data_change_rewrites_point_in_time_context_hash():
    before = build_relative_market_context(_bse(), _benchmark(), as_of=ASOF)
    items = list(_bars(start=200))
    old = items[-1]
    items[-1] = OHLCVBar(old.timestamp, 150, 151, 149, 150, old.volume)
    after = build_relative_market_context(_bse(), _benchmark(bars=tuple(items)), as_of=ASOF)
    assert after.benchmark_prefix_sha256 != before.benchmark_prefix_sha256
    assert after.context_sha256 != before.context_sha256


def test_feature_payload_contains_lineage_but_no_trade_signal():
    context = build_relative_market_context(_bse(), _benchmark(), as_of=ASOF)
    payload = relative_market_feature_payload(context)
    assert payload["context_sha256"] == context.context_sha256
    assert payload["config_learned"] is False
    assert not {"direction", "verdict", "buy", "sell"} & set(payload)


def test_benchmark_drawdown_is_observed_not_a_hard_gate():
    items = list(_bars(start=200))
    old = items[-1]
    items[-1] = OHLCVBar(old.timestamp, 205, 206, 204, 205, old.volume)
    context = build_relative_market_context(_bse(), _benchmark(bars=tuple(items)), as_of=ASOF)
    assert context.benchmark_drawdown_from_medium_high < 0
    assert context.status is RelativeMarketStatus.OBSERVED


def test_context_hash_is_deterministic():
    first = build_relative_market_context(_bse(), _benchmark(), as_of=ASOF)
    second = build_relative_market_context(_bse(), _benchmark(), as_of=ASOF)
    assert first.context_sha256 == second.context_sha256


def test_fetch_requires_exact_benchmark_symbol():
    class Loader:
        name = "yahoo"

        def fetch(self, *args, **kwargs):
            return {"NOT_NIFTY": pd.DataFrame()}

    with pytest.raises(RelativeMarketValidationError, match="no exact"):
        fetch_benchmark_market_data(
            nifty50_benchmark(),
            start_date="2026-08-21",
            end_date="2026-08-21",
            interval="5m",
            retrieved_at=ASOF,
            as_of=ASOF,
            freshness_policy=FreshnessPolicy(timedelta(hours=3)),
            loader_resolver=lambda market: Loader(),
        )


def test_fetch_reuses_india_equity_loader_and_unknown_freshness_is_not_ready():
    index = pd.date_range("2026-08-21 09:15", periods=5, freq="5min", tz="Asia/Kolkata")
    frame = pd.DataFrame(
        {"open": [100] * 5, "high": [101] * 5, "low": [99] * 5, "close": [100] * 5, "volume": [0] * 5},
        index=index,
    )
    seen = {}

    class Loader:
        name = "yahoo"

        def fetch(self, symbols, start, end, interval):
            seen["symbols"] = symbols
            return {"^NSEI": frame}

    snapshot = fetch_benchmark_market_data(
        nifty50_benchmark(),
        start_date="2026-08-21",
        end_date="2026-08-21",
        interval="5m",
        retrieved_at=ASOF,
        as_of=ASOF,
        freshness_policy=FreshnessPolicy(None),
        loader_resolver=lambda market: (seen.__setitem__("market", market) or Loader()),
    )
    assert seen == {"market": "india_equity", "symbols": ["^NSEI"]}
    assert snapshot.freshness is FreshnessStatus.UNKNOWN
    assert snapshot.ready is False
