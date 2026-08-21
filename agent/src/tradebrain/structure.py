"""No-lookahead BSE market-structure foundation for TradeBrain Phase 5.

The module consumes only the immutable :class:`BSEMarketDataSnapshot` produced
by Phase 4.  It never fetches another price series.  Its outputs are adaptive
market features, not trade signals and not learned parameters.

Important semantics:
- every analysis is bounded by an explicit ``as_of`` timestamp;
- confirmed swing points require their right-hand confirmation bars to already
  exist by ``as_of``;
- higher-timeframe bars are derived only from the supplied snapshot;
- incomplete higher-timeframe buckets are excluded;
- a window high is not called an all-time high unless the caller explicitly
  certifies that the supplied history has complete lifetime coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math
from statistics import median
from typing import Iterable
from zoneinfo import ZoneInfo

from src.tradebrain.market_data import BSEMarketDataSnapshot, OHLCVBar

__all__ = [
    "CoverageState",
    "MarketRegime",
    "MultiTimeframeStructure",
    "ObservedRange",
    "StructuralLevel",
    "StructureConfig",
    "StructureValidationError",
    "TimeframeStructure",
    "TrendState",
    "build_multi_timeframe_structure",
    "build_timeframe_structure",
    "derive_higher_timeframe_bars",
]


class StructureValidationError(ValueError):
    """Raised when supplied bars cannot safely become structure input."""


class TrendState(str, Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS_NORMAL = "sideways_normal"
    VOLATILE_UP = "volatile_up"
    VOLATILE_DOWN = "volatile_down"
    VOLATILE_SIDEWAYS = "volatile_sideways"
    UNKNOWN = "unknown"


class CoverageState(str, Enum):
    OBSERVED_WINDOW = "observed_window"
    COMPLETE_HISTORY = "complete_history"


def _aware(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise StructureValidationError(f"{field_name} must be ISO-8601") from exc
    else:
        raise StructureValidationError(f"{field_name} must be datetime or ISO-8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StructureValidationError(f"{field_name} must be timezone-aware")
    return parsed


def _parse_interval_minutes(interval: str) -> int:
    raw = str(interval or "").strip()
    if not raw:
        raise StructureValidationError("interval is required")
    lowered = raw.lower()
    if lowered.endswith("min"):
        number = lowered[:-3]
        unit = 1
    elif raw.endswith("m"):
        number = raw[:-1]
        unit = 1
    elif lowered.endswith("h"):
        number = lowered[:-1]
        unit = 60
    elif lowered.endswith("d"):
        number = lowered[:-1]
        unit = 1440
    else:
        raise StructureValidationError(
            f"unsupported interval {interval!r}; use minute/hour/day intervals"
        )
    try:
        value = int(number)
    except ValueError as exc:
        raise StructureValidationError(f"invalid interval {interval!r}") from exc
    if value <= 0:
        raise StructureValidationError("interval must be positive")
    return value * unit


def _bar_dt(bar: OHLCVBar) -> datetime:
    return _aware(bar.timestamp, "bar timestamp")


def _bounded_bars(
    bars: Iterable[OHLCVBar],
    *,
    as_of: str | datetime,
) -> tuple[OHLCVBar, ...]:
    cutoff = _aware(as_of, "as_of")
    bounded = tuple(bar for bar in bars if _bar_dt(bar) <= cutoff)
    if not bounded:
        raise StructureValidationError("no bars are knowable by as_of")
    if any(_bar_dt(a) >= _bar_dt(b) for a, b in zip(bounded, bounded[1:])):
        raise StructureValidationError("structure input timestamps must be strictly ascending")
    return bounded


def _ema(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    seed = sum(values[:period]) / period
    alpha = 2.0 / (period + 1.0)
    current = seed
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def _true_ranges(bars: tuple[OHLCVBar, ...]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        ranges.append(float(tr))
        previous_close = bar.close
    return ranges


def _confirmed_swings(
    bars: tuple[OHLCVBar, ...],
    *,
    left: int,
    right: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    if left < 1 or right < 1:
        raise StructureValidationError("swing left/right confirmation must be >= 1")
    for index in range(left, len(bars) - right):
        candidate = bars[index]
        left_bars = bars[index - left:index]
        right_bars = bars[index + 1:index + right + 1]
        if (
            all(candidate.high > item.high for item in left_bars)
            and all(candidate.high >= item.high for item in right_bars)
        ):
            highs.append((index, candidate.high))
        if (
            all(candidate.low < item.low for item in left_bars)
            and all(candidate.low <= item.low for item in right_bars)
        ):
            lows.append((index, candidate.low))
    return highs, lows


@dataclass(frozen=True)
class StructureConfig:
    """Provisional soft structure parameters; these are not learned values."""

    version: str = "phase5-provisional-v1"
    learned: bool = False
    ema_fast: int = 20
    ema_slow: int = 50
    ema_long: int = 200
    swing_left: int = 2
    swing_right: int = 2
    cluster_tolerance_pct: float = 0.005
    volume_window: int = 20
    volatility_window: int = 20
    volatile_tr_ratio: float = 1.8
    trend_separation_pct: float = 0.001

    def __post_init__(self) -> None:
        if self.learned:
            raise ValueError("Phase 5 structure defaults are provisional, not learned")
        if not self.version.strip():
            raise ValueError("structure config version is required")
        for name in ("ema_fast", "ema_slow", "ema_long", "volume_window", "volatility_window"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not (self.ema_fast < self.ema_slow < self.ema_long):
            raise ValueError("EMA periods must satisfy fast < slow < long")
        if self.swing_left < 1 or self.swing_right < 1:
            raise ValueError("swing confirmation widths must be >= 1")
        if self.cluster_tolerance_pct < 0:
            raise ValueError("cluster_tolerance_pct cannot be negative")
        if self.volatile_tr_ratio <= 0:
            raise ValueError("volatile_tr_ratio must be positive")


@dataclass(frozen=True)
class StructuralLevel:
    price: float
    kind: str
    touches: int
    first_timestamp: str
    last_timestamp: str


@dataclass(frozen=True)
class ObservedRange:
    low: float
    high: float
    low_timestamp: str
    high_timestamp: str
    coverage: CoverageState
    all_time_high: float | None
    fifty_two_week_low: float | None = None
    fifty_two_week_high: float | None = None


@dataclass(frozen=True)
class TimeframeStructure:
    interval: str
    as_of: str
    bar_count: int
    latest_timestamp: str
    latest_close: float
    ema_fast: float | None
    ema_slow: float | None
    ema_long: float | None
    atr: float | None
    true_range_ratio: float | None
    volume_ratio: float | None
    trend: TrendState
    regime: MarketRegime
    observed_range: ObservedRange
    levels: tuple[StructuralLevel, ...]
    confirmed_swing_highs: tuple[tuple[str, float], ...]
    confirmed_swing_lows: tuple[tuple[str, float], ...]
    config_version: str
    config_learned: bool = False


@dataclass(frozen=True)
class MultiTimeframeStructure:
    isin: str
    qualified_symbol: str
    source_frame_sha256: str
    native_interval: str
    as_of: str
    native_bar_count: int
    native_latest_timestamp: str
    timeframes: tuple[TimeframeStructure, ...]
    requested_intervals: tuple[str, ...]

    @property
    def ready(self) -> bool:
        available = {item.interval.lower() for item in self.timeframes if item.bar_count > 0}
        requested = {item.lower() for item in self.requested_intervals}
        return self.native_bar_count > 0 and bool(requested) and requested.issubset(available)

    def for_interval(self, interval: str) -> TimeframeStructure:
        normalized = str(interval).strip().lower()
        for item in self.timeframes:
            if item.interval.lower() == normalized:
                return item
        raise KeyError(interval)


def _cluster_levels(
    bars: tuple[OHLCVBar, ...],
    swing_highs: list[tuple[int, float]],
    swing_lows: list[tuple[int, float]],
    *,
    tolerance_pct: float,
) -> tuple[StructuralLevel, ...]:
    points: list[tuple[str, int, float]] = [
        ("resistance", index, price) for index, price in swing_highs
    ] + [
        ("support", index, price) for index, price in swing_lows
    ]
    points.sort(key=lambda item: item[2])
    clusters: list[list[tuple[str, int, float]]] = []
    for point in points:
        matched: list[tuple[str, int, float]] | None = None
        for cluster in clusters:
            center = sum(item[2] for item in cluster) / len(cluster)
            denom = max(abs(center), 1e-12)
            if abs(point[2] - center) / denom <= tolerance_pct:
                matched = cluster
                break
        if matched is None:
            clusters.append([point])
        else:
            matched.append(point)

    levels: list[StructuralLevel] = []
    for cluster in clusters:
        price = sum(item[2] for item in cluster) / len(cluster)
        support = sum(1 for item in cluster if item[0] == "support")
        resistance = len(cluster) - support
        kind = "support" if support > resistance else "resistance" if resistance > support else "mixed"
        indexes = sorted(item[1] for item in cluster)
        levels.append(
            StructuralLevel(
                price=price,
                kind=kind,
                touches=len(cluster),
                first_timestamp=bars[indexes[0]].timestamp,
                last_timestamp=bars[indexes[-1]].timestamp,
            )
        )
    levels.sort(key=lambda item: (item.price, item.kind))
    return tuple(levels)


def _trend_and_regime(
    latest_close: float,
    fast: float | None,
    slow: float | None,
    tr_ratio: float | None,
    config: StructureConfig,
) -> tuple[TrendState, MarketRegime]:
    if fast is None or slow is None:
        return TrendState.UNKNOWN, MarketRegime.UNKNOWN
    separation = abs(fast - slow) / max(abs(slow), 1e-12)
    if separation < config.trend_separation_pct:
        trend = TrendState.SIDEWAYS
    elif latest_close > fast > slow:
        trend = TrendState.UP
    elif latest_close < fast < slow:
        trend = TrendState.DOWN
    else:
        trend = TrendState.SIDEWAYS

    volatile = tr_ratio is not None and tr_ratio >= config.volatile_tr_ratio
    if trend is TrendState.UP:
        regime = MarketRegime.VOLATILE_UP if volatile else MarketRegime.TRENDING_UP
    elif trend is TrendState.DOWN:
        regime = MarketRegime.VOLATILE_DOWN if volatile else MarketRegime.TRENDING_DOWN
    elif trend is TrendState.SIDEWAYS:
        regime = MarketRegime.VOLATILE_SIDEWAYS if volatile else MarketRegime.SIDEWAYS_NORMAL
    else:
        regime = MarketRegime.UNKNOWN
    return trend, regime


def build_timeframe_structure(
    bars: Iterable[OHLCVBar],
    *,
    interval: str,
    as_of: str | datetime,
    config: StructureConfig | None = None,
    history_complete: bool = False,
) -> TimeframeStructure:
    """Build deterministic structure from bars knowable at ``as_of`` only."""

    config = StructureConfig() if config is None else config
    bounded = _bounded_bars(bars, as_of=as_of)
    cutoff = _aware(as_of, "as_of")
    closes = [bar.close for bar in bounded]
    volumes = [bar.volume for bar in bounded]
    ranges = _true_ranges(bounded)

    fast = _ema(closes, config.ema_fast)
    slow = _ema(closes, config.ema_slow)
    long = _ema(closes, config.ema_long)

    atr = None
    tr_ratio = None
    if len(ranges) >= config.volatility_window:
        recent = ranges[-config.volatility_window:]
        atr = sum(recent) / len(recent)
        baseline_pool = ranges[:-1][-config.volatility_window:]
        if baseline_pool:
            baseline = median(baseline_pool)
            if baseline > 0:
                tr_ratio = ranges[-1] / baseline

    volume_ratio = None
    if len(volumes) >= config.volume_window + 1:
        baseline = median(volumes[-config.volume_window - 1:-1])
        if baseline > 0:
            volume_ratio = volumes[-1] / baseline

    swing_highs, swing_lows = _confirmed_swings(
        bounded,
        left=config.swing_left,
        right=config.swing_right,
    )
    levels = _cluster_levels(
        bounded,
        swing_highs,
        swing_lows,
        tolerance_pct=config.cluster_tolerance_pct,
    )

    highest_index = max(range(len(bounded)), key=lambda i: bounded[i].high)
    lowest_index = min(range(len(bounded)), key=lambda i: bounded[i].low)
    all_time_high = bounded[highest_index].high if history_complete else None

    # 52-week semantics are exposed only for daily bars and only after at least
    # 252 knowable daily observations; otherwise pretending a shorter period is
    # "52-week" would manufacture coverage.
    fifty_two_week_high = None
    fifty_two_week_low = None
    try:
        interval_minutes = _parse_interval_minutes(interval)
    except StructureValidationError:
        interval_minutes = 0
    if interval_minutes >= 1440 and len(bounded) >= 252:
        trailing = bounded[-252:]
        fifty_two_week_high = max(bar.high for bar in trailing)
        fifty_two_week_low = min(bar.low for bar in trailing)

    observed = ObservedRange(
        low=bounded[lowest_index].low,
        high=bounded[highest_index].high,
        low_timestamp=bounded[lowest_index].timestamp,
        high_timestamp=bounded[highest_index].timestamp,
        coverage=(
            CoverageState.COMPLETE_HISTORY
            if history_complete
            else CoverageState.OBSERVED_WINDOW
        ),
        all_time_high=all_time_high,
        fifty_two_week_low=fifty_two_week_low,
        fifty_two_week_high=fifty_two_week_high,
    )

    trend, regime = _trend_and_regime(
        bounded[-1].close,
        fast,
        slow,
        tr_ratio,
        config,
    )
    return TimeframeStructure(
        interval=str(interval),
        as_of=cutoff.isoformat(),
        bar_count=len(bounded),
        latest_timestamp=bounded[-1].timestamp,
        latest_close=bounded[-1].close,
        ema_fast=fast,
        ema_slow=slow,
        ema_long=long,
        atr=atr,
        true_range_ratio=tr_ratio,
        volume_ratio=volume_ratio,
        trend=trend,
        regime=regime,
        observed_range=observed,
        levels=levels,
        confirmed_swing_highs=tuple(
            (bounded[index].timestamp, price) for index, price in swing_highs
        ),
        confirmed_swing_lows=tuple(
            (bounded[index].timestamp, price) for index, price in swing_lows
        ),
        config_version=config.version,
        config_learned=config.learned,
    )


def derive_higher_timeframe_bars(
    snapshot: BSEMarketDataSnapshot,
    *,
    target_interval: str,
    as_of: str | datetime,
    session_timezone: str = "Asia/Kolkata",
    session_open_hour: int = 9,
    session_open_minute: int = 15,
) -> tuple[OHLCVBar, ...]:
    """Derive complete higher-timeframe bars from the Phase-4 snapshot only.

    The function never downsamples to a finer interval. Intraday buckets are
    anchored to 09:15 Asia/Kolkata. A bucket is emitted only after its entire
    target duration is knowable at ``as_of``; this prevents an incomplete
    higher-timeframe candle from leaking future information.
    """

    if not snapshot.bars:
        raise StructureValidationError("cannot derive timeframes from an empty snapshot")
    base_minutes = _parse_interval_minutes(snapshot.interval)
    target_minutes = _parse_interval_minutes(target_interval)
    if target_minutes < base_minutes:
        raise StructureValidationError(
            f"cannot derive finer {target_interval} bars from {snapshot.interval}"
        )
    if target_minutes % base_minutes != 0:
        raise StructureValidationError(
            "target interval must be an integer multiple of the snapshot interval"
        )
    cutoff = _aware(as_of, "as_of")
    bounded = _bounded_bars(snapshot.bars, as_of=cutoff)
    tz = ZoneInfo(session_timezone)
    if target_minutes == base_minutes:
        local_cutoff = cutoff.astimezone(tz)
        if base_minutes >= 1440:
            session_close = local_cutoff.replace(
                hour=15, minute=30, second=0, microsecond=0
            )
            return tuple(
                bar for bar in bounded
                if (
                    _bar_dt(bar).astimezone(tz).date() < local_cutoff.date()
                    or (
                        _bar_dt(bar).astimezone(tz).date() == local_cutoff.date()
                        and local_cutoff >= session_close
                    )
                )
            )
        return tuple(
            bar for bar in bounded
            if _bar_dt(bar).astimezone(tz) + timedelta(minutes=base_minutes)
            <= local_cutoff
        )

    if target_minutes >= 1440:
        if target_minutes != 1440:
            raise StructureValidationError(
                "Phase 5 derives only daily bars above intraday; weekly/monthly require "
                "a later exchange-calendar-aware layer"
            )
        if base_minutes >= 1440:
            return bounded
        session_minutes = 375  # regular NSE cash session: 09:15-15:30 IST
        if session_minutes % base_minutes != 0:
            raise StructureValidationError(
                "native interval does not evenly partition the regular NSE session"
            )
        required_count = session_minutes // base_minutes
        grouped: dict[object, list[OHLCVBar]] = {}
        for bar in bounded:
            local = _bar_dt(bar).astimezone(tz)
            grouped.setdefault(local.date(), []).append(bar)
        result: list[OHLCVBar] = []
        local_cutoff = cutoff.astimezone(tz)
        for day in sorted(grouped):
            if day > local_cutoff.date():
                continue
            if day == local_cutoff.date():
                session_close = local_cutoff.replace(
                    hour=15, minute=30, second=0, microsecond=0
                )
                if local_cutoff < session_close:
                    continue
            items = sorted(grouped[day], key=_bar_dt)
            if len(items) != required_count:
                continue
            anchor = datetime(
                day.year, day.month, day.day,
                session_open_hour, session_open_minute,
                tzinfo=tz,
            )
            expected = [
                anchor + timedelta(minutes=base_minutes * offset)
                for offset in range(required_count)
            ]
            actual = [_bar_dt(item).astimezone(tz) for item in items]
            if actual != expected:
                continue
            result.append(_aggregate(items, anchor.isoformat()))
        return tuple(result)

    buckets: dict[datetime, list[OHLCVBar]] = {}
    for bar in bounded:
        local = _bar_dt(bar).astimezone(tz)
        anchor = local.replace(
            hour=session_open_hour,
            minute=session_open_minute,
            second=0,
            microsecond=0,
        )
        if local < anchor:
            continue
        elapsed_minutes = int((local - anchor).total_seconds() // 60)
        bucket_index = elapsed_minutes // target_minutes
        start = anchor + timedelta(minutes=bucket_index * target_minutes)
        buckets.setdefault(start, []).append(bar)

    result: list[OHLCVBar] = []
    local_cutoff = cutoff.astimezone(tz)
    required_count = target_minutes // base_minutes
    for start in sorted(buckets):
        items = buckets[start]
        end = start + timedelta(minutes=target_minutes)
        if end > local_cutoff:
            continue
        if len(items) != required_count:
            # Missing or extra constituent bars make the derived candle ambiguous.
            continue
        item_times = [_bar_dt(item).astimezone(tz) for item in sorted(items, key=_bar_dt)]
        expected = [
            start + timedelta(minutes=base_minutes * offset)
            for offset in range(required_count)
        ]
        if item_times != expected:
            # Do not paper over holes or irregular timestamps.
            continue
        result.append(_aggregate(items, start.isoformat()))
    return tuple(result)


def _aggregate(items: list[OHLCVBar], timestamp: str) -> OHLCVBar:
    ordered = sorted(items, key=_bar_dt)
    return OHLCVBar(
        timestamp=timestamp,
        open=ordered[0].open,
        high=max(bar.high for bar in ordered),
        low=min(bar.low for bar in ordered),
        close=ordered[-1].close,
        volume=sum(bar.volume for bar in ordered),
    )


def build_multi_timeframe_structure(
    snapshot: BSEMarketDataSnapshot,
    *,
    as_of: str | datetime,
    requested_intervals: Iterable[str] = (),
    config: StructureConfig | None = None,
    complete_history_intervals: Iterable[str] = (),
) -> MultiTimeframeStructure:
    """Build flexible multi-timeframe context without a second market-data fetch."""

    if not snapshot.ready:
        raise StructureValidationError(
            "Phase-5 structure requires a fresh Phase-4 market-data snapshot"
        )
    cutoff = _aware(as_of, "as_of")
    config = StructureConfig() if config is None else config
    requested = tuple(str(item).strip() for item in requested_intervals if str(item).strip())
    if not requested:
        requested = (snapshot.interval,)
    complete = {item.lower() for item in complete_history_intervals}

    native_minutes = _parse_interval_minutes(snapshot.interval)
    native_bars = derive_higher_timeframe_bars(
        snapshot,
        target_interval=snapshot.interval,
        as_of=cutoff,
    )
    if not native_bars:
        raise StructureValidationError(
            "no complete native bars are knowable by as_of"
        )
    structures: list[TimeframeStructure] = []
    seen: set[str] = set()
    for interval in requested:
        key = interval.lower()
        if key in seen:
            continue
        seen.add(key)
        target_minutes = _parse_interval_minutes(interval)
        if target_minutes < native_minutes:
            raise StructureValidationError(
                f"requested {interval} is finer than native {snapshot.interval}"
            )
        bars = derive_higher_timeframe_bars(
            snapshot,
            target_interval=interval,
            as_of=cutoff,
        )
        if not bars:
            continue
        structures.append(
            build_timeframe_structure(
                bars,
                interval=interval,
                as_of=cutoff,
                config=config,
                history_complete=key in complete,
            )
        )

    return MultiTimeframeStructure(
        isin=snapshot.isin,
        qualified_symbol=snapshot.qualified_symbol,
        source_frame_sha256=snapshot.frame_sha256,
        native_interval=snapshot.interval,
        as_of=cutoff.isoformat(),
        native_bar_count=len(native_bars),
        native_latest_timestamp=native_bars[-1].timestamp,
        timeframes=tuple(structures),
        requested_intervals=requested,
    )
