"""Point-in-time relative-market context for TradeBrain Phase 9.

This module adds broad Indian-market context around the verified BSE Ltd market
snapshot.  It is deliberately research/advisory context only: it cannot create
LONG/SHORT signals, cannot override Crash Guard/hard rules, and is not treated as
"learned" until the existing Phase-7 champion/challenger process proves value.

The benchmark path reuses Vibe's existing ``india_equity`` loader resolver.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Callable, Iterable, Mapping

from backtest.loaders.registry import resolve_loader
from src.goal.models import EvidenceInput
from src.tradebrain.market_data import (
    BSEMarketDataSnapshot,
    FreshnessPolicy,
    FreshnessStatus,
    OHLCVBar,
    _aware_datetime,
    _bars_hash,
    _validate_frame,
)

__all__ = [
    "BenchmarkDefinition",
    "BenchmarkMarketDataSnapshot",
    "RelativeMarketConfig",
    "RelativeMarketContext",
    "RelativeMarketStatus",
    "RelativeMarketValidationError",
    "build_relative_market_context",
    "fetch_benchmark_market_data",
    "nifty50_benchmark",
    "relative_market_feature_payload",
]


class RelativeMarketValidationError(ValueError):
    """Raised when benchmark/relative-market inputs cannot be aligned safely."""


class RelativeMarketStatus(str, Enum):
    DATA_INSUFFICIENT = "data_insufficient"
    OBSERVED = "observed"


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(k): _canonical(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if is_dataclass(value):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return float(f"{value:.15g}")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _hash(value: object) -> str:
    body = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BenchmarkDefinition:
    """Exact benchmark identity; no fuzzy symbol substitution is permitted."""

    benchmark_id: str
    display_name: str
    loader_symbol: str
    market: str = "india_equity"
    role: str = "broad_market"

    def __post_init__(self) -> None:
        for name in ("benchmark_id", "display_name", "loader_symbol", "market", "role"):
            value = str(getattr(self, name) or "").strip()
            if not value:
                raise RelativeMarketValidationError(f"{name} is required")
            object.__setattr__(self, name, value)


def nifty50_benchmark() -> BenchmarkDefinition:
    """Yahoo-compatible NIFTY 50 benchmark descriptor.

    ``^NSEI`` is an exact loader symbol, not a canonical security identity.
    If the resolved provider cannot return that exact symbol, the fetch fails
    closed instead of silently substituting another index.
    """

    return BenchmarkDefinition(
        benchmark_id="india:nifty50",
        display_name="NIFTY 50",
        loader_symbol="^NSEI",
        market="india_equity",
        role="broad_market",
    )


@dataclass(frozen=True)
class BenchmarkMarketDataSnapshot:
    benchmark: BenchmarkDefinition
    interval: str
    source_name: str
    requested_start: str
    requested_end: str
    retrieved_at: str
    data_as_of: str
    age_seconds: float
    freshness: FreshnessStatus
    frame_sha256: str
    bars: tuple[OHLCVBar, ...]
    evidence: EvidenceInput

    @property
    def ready(self) -> bool:
        return bool(self.bars) and self.freshness is FreshnessStatus.FRESH


def fetch_benchmark_market_data(
    benchmark: BenchmarkDefinition,
    *,
    start_date: str,
    end_date: str,
    interval: str,
    retrieved_at: str | datetime,
    as_of: str | datetime,
    freshness_policy: FreshnessPolicy,
    loader_resolver: Callable[[str], object] = resolve_loader,
) -> BenchmarkMarketDataSnapshot:
    """Fetch one exact benchmark through Vibe's existing India loader chain."""

    retrieved = _aware_datetime(retrieved_at, "retrieved_at")
    cutoff = _aware_datetime(as_of, "as_of")
    if retrieved > cutoff + freshness_policy.future_tolerance:
        raise RelativeMarketValidationError("retrieved_at is materially after as_of")

    loader = loader_resolver(benchmark.market)
    source_name = str(getattr(loader, "name", type(loader).__name__)).strip()
    if not source_name:
        raise RelativeMarketValidationError("resolved benchmark loader has no source name")
    if not hasattr(loader, "fetch"):
        raise RelativeMarketValidationError("resolved benchmark loader does not expose fetch()")

    payload = loader.fetch(
        [benchmark.loader_symbol],
        start_date,
        end_date,
        interval=interval,
    )
    if not isinstance(payload, dict) or benchmark.loader_symbol not in payload:
        raise RelativeMarketValidationError(
            f"{source_name} returned no exact {benchmark.loader_symbol} benchmark series"
        )

    try:
        bars = _validate_frame(
            payload[benchmark.loader_symbol],
            naive_tz=freshness_policy.naive_index_timezone,
        )
    except Exception as exc:
        raise RelativeMarketValidationError(str(exc)) from exc

    latest = _aware_datetime(bars[-1].timestamp, "latest benchmark timestamp")
    if latest > cutoff + freshness_policy.future_tolerance:
        raise RelativeMarketValidationError("benchmark series contains a future bar")

    age_seconds = max(0.0, (cutoff - latest).total_seconds())
    if freshness_policy.max_age is None:
        freshness = FreshnessStatus.UNKNOWN
    elif age_seconds <= freshness_policy.max_age.total_seconds():
        freshness = FreshnessStatus.FRESH
    else:
        freshness = FreshnessStatus.STALE

    digest = _bars_hash(bars)
    evidence = EvidenceInput(
        text=(
            f"{benchmark.display_name} OHLCV observed through Vibe loader "
            f"{source_name} ({benchmark.loader_symbol}, {interval})"
        ),
        evidence_type="market_data",
        source_provider=source_name,
        source_type="benchmark_ohlcv",
        source_uri=f"vibe-loader:{source_name}",
        symbol_universe=[benchmark.loader_symbol],
        timeframe=str(interval),
        method="tradebrain_relative_market_vibe_loader_bridge",
        assumptions={
            "benchmark_id": benchmark.benchmark_id,
            "benchmark_role": benchmark.role,
            "market": benchmark.market,
            "frame_sha256": digest,
            "freshness": freshness.value,
            "age_seconds": age_seconds,
        },
        data_as_of=latest.isoformat(),
        confidence="observed",
    )
    return BenchmarkMarketDataSnapshot(
        benchmark=benchmark,
        interval=str(interval),
        source_name=source_name,
        requested_start=str(start_date),
        requested_end=str(end_date),
        retrieved_at=retrieved.isoformat(),
        data_as_of=latest.isoformat(),
        age_seconds=age_seconds,
        freshness=freshness,
        frame_sha256=digest,
        bars=bars,
        evidence=evidence,
    )


@dataclass(frozen=True)
class RelativeMarketConfig:
    """Versioned measurement geometry; Phase 9 defaults are not learned rules."""

    version: str = "phase9-relative-v1"
    short_window_bars: int = 5
    medium_window_bars: int = 20
    correlation_window_bars: int = 20
    min_aligned_bars: int = 21
    min_alignment_ratio: float = 0.90
    require_same_source: bool = True
    learned: bool = False

    def __post_init__(self) -> None:
        if not str(self.version).strip():
            raise RelativeMarketValidationError("relative-market config version is required")
        for name in (
            "short_window_bars",
            "medium_window_bars",
            "correlation_window_bars",
            "min_aligned_bars",
        ):
            if int(getattr(self, name)) < 1:
                raise RelativeMarketValidationError(f"{name} must be >= 1")
        if not 0 < float(self.min_alignment_ratio) <= 1:
            raise RelativeMarketValidationError("min_alignment_ratio must be in (0, 1]")
        if self.learned:
            raise RelativeMarketValidationError(
                "Phase 9 relative-market config is provisional; learned=True requires controlled promotion"
            )


@dataclass(frozen=True)
class RelativeMarketContext:
    status: RelativeMarketStatus
    as_of: str
    benchmark_id: str
    benchmark_symbol: str
    interval: str
    bse_source_name: str
    benchmark_source_name: str
    bse_prefix_sha256: str
    benchmark_prefix_sha256: str
    aligned_timestamps_sha256: str
    aligned_bar_count: int
    bse_eligible_bar_count: int
    benchmark_eligible_bar_count: int
    alignment_ratio: float
    latest_aligned_timestamp: str | None
    bse_return_1bar: float | None
    benchmark_return_1bar: float | None
    relative_return_1bar: float | None
    bse_return_short: float | None
    benchmark_return_short: float | None
    relative_return_short: float | None
    bse_return_medium: float | None
    benchmark_return_medium: float | None
    relative_return_medium: float | None
    benchmark_drawdown_from_medium_high: float | None
    correlation: float | None
    beta: float | None
    config_version: str
    config_learned: bool
    reasons: tuple[str, ...]
    context_sha256: str

    @property
    def ready(self) -> bool:
        return self.status is RelativeMarketStatus.OBSERVED


def _return(closes: tuple[float, ...], bars: int) -> float | None:
    if bars < 1 or len(closes) <= bars:
        return None
    start = closes[-(bars + 1)]
    end = closes[-1]
    if start == 0:
        return None
    return end / start - 1.0


def _period_returns(closes: tuple[float, ...], window: int) -> tuple[float, ...]:
    if len(closes) < 2:
        return ()
    usable = closes[-(window + 1):] if len(closes) > window else closes
    out: list[float] = []
    for previous, current in zip(usable, usable[1:]):
        if previous == 0:
            continue
        out.append(current / previous - 1.0)
    return tuple(out)


def _corr_beta(
    bse_closes: tuple[float, ...],
    benchmark_closes: tuple[float, ...],
    window: int,
) -> tuple[float | None, float | None]:
    x = _period_returns(benchmark_closes, window)
    y = _period_returns(bse_closes, window)
    n = min(len(x), len(y))
    if n < 2:
        return None, None
    x = x[-n:]
    y = y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y)) / n
    vx = sum((a - mx) ** 2 for a in x) / n
    vy = sum((b - my) ** 2 for b in y) / n
    beta = cov / vx if vx > 0 else None
    corr = cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else None
    if corr is not None:
        corr = max(-1.0, min(1.0, corr))
    return corr, beta


def _medium_drawdown(closes: tuple[float, ...], bars: int) -> float | None:
    if not closes:
        return None
    window = closes[-(bars + 1):] if len(closes) > bars else closes
    high = max(window)
    if high <= 0:
        return None
    return closes[-1] / high - 1.0


def _context_core(**kwargs: object) -> dict[str, object]:
    return dict(kwargs)


def build_relative_market_context(
    bse: BSEMarketDataSnapshot,
    benchmark: BenchmarkMarketDataSnapshot,
    *,
    as_of: str | datetime,
    config: RelativeMarketConfig | None = None,
) -> RelativeMarketContext:
    """Align BSE and benchmark bars exactly at ``as_of`` and compute raw features.

    The output is context only.  It does not block/allow a trade, does not create
    direction, and does not alter Crash Guard or hard-rule state.
    """

    cfg = RelativeMarketConfig() if config is None else config
    cutoff = _aware_datetime(as_of, "as_of")

    if str(bse.interval).lower() != str(benchmark.interval).lower():
        raise RelativeMarketValidationError("BSE and benchmark intervals must match exactly")
    if cfg.require_same_source and bse.source_name != benchmark.source_name:
        raise RelativeMarketValidationError(
            "relative-market comparison requires the same market-data source by default"
        )

    bse_eligible = tuple(
        bar for bar in bse.bars
        if _aware_datetime(bar.timestamp, "BSE bar timestamp") <= cutoff
    )
    benchmark_eligible = tuple(
        bar for bar in benchmark.bars
        if _aware_datetime(bar.timestamp, "benchmark bar timestamp") <= cutoff
    )

    def stamp_key(bar: OHLCVBar, label: str) -> str:
        return _aware_datetime(bar.timestamp, label).astimezone(timezone.utc).isoformat()

    bse_map = {stamp_key(bar, "BSE bar timestamp"): bar for bar in bse_eligible}
    benchmark_map = {
        stamp_key(bar, "benchmark bar timestamp"): bar for bar in benchmark_eligible
    }
    stamps = tuple(sorted(set(bse_map) & set(benchmark_map)))
    denominator = min(len(bse_eligible), len(benchmark_eligible))
    ratio = len(stamps) / denominator if denominator else 0.0

    reasons: list[str] = []
    if bse.freshness is not FreshnessStatus.FRESH:
        reasons.append(f"bse_freshness_{bse.freshness.value}")
    if benchmark.freshness is not FreshnessStatus.FRESH:
        reasons.append(f"benchmark_freshness_{benchmark.freshness.value}")
    if len(stamps) < cfg.min_aligned_bars:
        reasons.append("insufficient_aligned_bars")
    if ratio < cfg.min_alignment_ratio:
        reasons.append("alignment_ratio_below_minimum")

    bse_closes = tuple(float(bse_map[stamp].close) for stamp in stamps)
    benchmark_closes = tuple(float(benchmark_map[stamp].close) for stamp in stamps)

    bse1 = _return(bse_closes, 1)
    bm1 = _return(benchmark_closes, 1)
    bses = _return(bse_closes, cfg.short_window_bars)
    bms = _return(benchmark_closes, cfg.short_window_bars)
    bsem = _return(bse_closes, cfg.medium_window_bars)
    bmm = _return(benchmark_closes, cfg.medium_window_bars)
    corr, beta = _corr_beta(
        bse_closes,
        benchmark_closes,
        cfg.correlation_window_bars,
    )

    def relative(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None

    status = (
        RelativeMarketStatus.DATA_INSUFFICIENT
        if reasons
        else RelativeMarketStatus.OBSERVED
    )
    core = _context_core(
        status=status,
        as_of=cutoff.isoformat(),
        benchmark_id=benchmark.benchmark.benchmark_id,
        benchmark_symbol=benchmark.benchmark.loader_symbol,
        interval=str(bse.interval),
        bse_source_name=bse.source_name,
        benchmark_source_name=benchmark.source_name,
        bse_prefix_sha256=_bars_hash(bse_eligible),
        benchmark_prefix_sha256=_bars_hash(benchmark_eligible),
        aligned_timestamps_sha256=_hash(stamps),
        aligned_bar_count=len(stamps),
        bse_eligible_bar_count=len(bse_eligible),
        benchmark_eligible_bar_count=len(benchmark_eligible),
        alignment_ratio=ratio,
        latest_aligned_timestamp=stamps[-1] if stamps else None,
        bse_return_1bar=bse1,
        benchmark_return_1bar=bm1,
        relative_return_1bar=relative(bse1, bm1),
        bse_return_short=bses,
        benchmark_return_short=bms,
        relative_return_short=relative(bses, bms),
        bse_return_medium=bsem,
        benchmark_return_medium=bmm,
        relative_return_medium=relative(bsem, bmm),
        benchmark_drawdown_from_medium_high=_medium_drawdown(
            benchmark_closes, cfg.medium_window_bars
        ),
        correlation=corr,
        beta=beta,
        config_version=cfg.version,
        config_learned=cfg.learned,
        reasons=tuple(reasons),
    )
    return RelativeMarketContext(
        **core,
        context_sha256=_hash(core),
    )


def relative_market_feature_payload(context: RelativeMarketContext) -> dict[str, object]:
    """Return a deterministic research-feature payload for Phase-7 candidates.

    This is not a trading signal.  Downstream research should bind the returned
    ``context_sha256`` to its experiment artifacts and compare Champion A versus
    Challenger B before any relative-market feature is promoted.
    """

    return {
        "context_sha256": context.context_sha256,
        "status": context.status.value,
        "benchmark_id": context.benchmark_id,
        "benchmark_symbol": context.benchmark_symbol,
        "interval": context.interval,
        "relative_return_1bar": context.relative_return_1bar,
        "relative_return_short": context.relative_return_short,
        "relative_return_medium": context.relative_return_medium,
        "benchmark_return_short": context.benchmark_return_short,
        "benchmark_return_medium": context.benchmark_return_medium,
        "benchmark_drawdown_from_medium_high": context.benchmark_drawdown_from_medium_high,
        "correlation": context.correlation,
        "beta": context.beta,
        "config_version": context.config_version,
        "config_learned": context.config_learned,
    }
