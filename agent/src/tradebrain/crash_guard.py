"""Deterministic Crash Guard risk gate for TradeBrain Phase 5.

Crash Guard consumes already-validated Phase-4 bars and Phase-5 structure.  It
is not an entry signal, and even a SEVERE state never creates a SHORT. Thresholds
in this phase are explicitly provisional soft parameters that must later be
replayed on severe and ordinary sessions and measured for false positives.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median

from src.tradebrain.market_data import BSEMarketDataSnapshot
from src.tradebrain.structure import MultiTimeframeStructure, TrendState

__all__ = [
    "CrashGuardConfig",
    "CrashGuardMetrics",
    "CrashGuardResult",
    "CrashGuardState",
    "evaluate_crash_guard",
]


class CrashGuardState(str, Enum):
    DATA_INSUFFICIENT = "data_insufficient"
    NORMAL = "normal"
    ELEVATED = "elevated"
    SEVERE = "severe"


@dataclass(frozen=True)
class CrashGuardConfig:
    """Provisional soft thresholds; not promoted/learned parameters."""

    version: str = "phase5-provisional-v1"
    learned: bool = False
    lookback_bars: int = 20
    return_window_bars: int = 3
    severe_one_bar_return: float = -0.04
    severe_window_return: float = -0.07
    severe_gap_return: float = -0.03
    severe_drawdown_from_observed_high: float = -0.10
    severe_true_range_ratio: float = 2.5
    severe_volume_ratio: float = 2.0
    severe_support_break_pct: float = -0.015
    elevated_one_bar_return: float = -0.02
    elevated_window_return: float = -0.04
    elevated_gap_return: float = -0.015
    elevated_drawdown_from_observed_high: float = -0.06
    elevated_true_range_ratio: float = 1.8
    elevated_volume_ratio: float = 1.5
    elevated_support_break_pct: float = -0.005
    bearish_alignment_timeframes: int = 2
    severe_trigger_count: int = 2

    def __post_init__(self) -> None:
        if self.learned:
            raise ValueError("Phase 5 Crash Guard thresholds are provisional, not learned")
        if not self.version.strip():
            raise ValueError("Crash Guard config version is required")
        if self.lookback_bars < 3:
            raise ValueError("lookback_bars must be >= 3")
        if self.return_window_bars < 2:
            raise ValueError("return_window_bars must be >= 2")
        if self.severe_trigger_count < 1:
            raise ValueError("severe_trigger_count must be >= 1")
        if self.bearish_alignment_timeframes < 1:
            raise ValueError("bearish_alignment_timeframes must be >= 1")


@dataclass(frozen=True)
class CrashGuardMetrics:
    one_bar_return: float
    window_return: float
    gap_return: float
    drawdown_from_observed_high: float
    true_range_ratio: float | None
    volume_ratio: float | None
    consecutive_down_bars: int
    bearish_timeframe_count: int
    support_break_pct: float | None


@dataclass(frozen=True)
class CrashGuardResult:
    state: CrashGuardState
    reasons: tuple[str, ...]
    metrics: CrashGuardMetrics | None
    config_version: str
    config_learned: bool
    block_day_long: bool
    block_swing_long: bool
    create_short_signal: bool = False

    @property
    def usable(self) -> bool:
        return self.state is not CrashGuardState.DATA_INSUFFICIENT


def _true_range(current, previous_close: float) -> float:
    return max(
        current.high - current.low,
        abs(current.high - previous_close),
        abs(current.low - previous_close),
    )


def _nearest_broken_support(
    structure: MultiTimeframeStructure,
    *,
    latest_close: float,
) -> float | None:
    candidates: list[float] = []
    for timeframe in structure.timeframes:
        for level in timeframe.levels:
            if level.kind in {"support", "mixed"} and level.touches >= 2:
                if latest_close < level.price:
                    candidates.append(level.price)
    return min(candidates, key=lambda price: abs(price - latest_close)) if candidates else None


def evaluate_crash_guard(
    snapshot: BSEMarketDataSnapshot,
    structure: MultiTimeframeStructure,
    *,
    config: CrashGuardConfig | None = None,
) -> CrashGuardResult:
    """Evaluate BSE-specific stress without generating a trade direction."""

    config = CrashGuardConfig() if config is None else config
    if (
        snapshot.isin != structure.isin
        or snapshot.qualified_symbol != structure.qualified_symbol
        or snapshot.frame_sha256 != structure.source_frame_sha256
    ):
        raise ValueError("Crash Guard inputs do not share the same Phase-4 market snapshot")
    if not snapshot.ready or not structure.ready:
        return CrashGuardResult(
            state=CrashGuardState.DATA_INSUFFICIENT,
            reasons=("market_or_structure_not_ready",),
            metrics=None,
            config_version=config.version,
            config_learned=config.learned,
            block_day_long=False,
            block_swing_long=False,
        )

    if structure.native_bar_count > len(snapshot.bars):
        raise ValueError("structure native_bar_count exceeds Phase-4 snapshot")
    bars = snapshot.bars[:structure.native_bar_count]
    if not bars or bars[-1].timestamp != structure.native_latest_timestamp:
        raise ValueError("Crash Guard structure boundary does not match Phase-4 bars")
    minimum = max(config.lookback_bars + 1, config.return_window_bars + 1)
    if len(bars) < minimum:
        return CrashGuardResult(
            state=CrashGuardState.DATA_INSUFFICIENT,
            reasons=("insufficient_lookback",),
            metrics=None,
            config_version=config.version,
            config_learned=config.learned,
            block_day_long=False,
            block_swing_long=False,
        )

    latest = bars[-1]
    previous = bars[-2]
    one_bar_return = latest.close / previous.close - 1.0
    window_anchor = bars[-1 - config.return_window_bars].close
    window_return = latest.close / window_anchor - 1.0
    gap_return = latest.open / previous.close - 1.0
    observed_high = max(bar.high for bar in bars[-config.lookback_bars:])
    drawdown = latest.close / observed_high - 1.0

    true_ranges = [
        _true_range(bars[index], bars[index - 1].close)
        for index in range(1, len(bars))
    ]
    recent_baseline_tr = true_ranges[-config.lookback_bars:-1]
    tr_ratio = None
    if recent_baseline_tr:
        baseline = median(recent_baseline_tr)
        if baseline > 0:
            tr_ratio = true_ranges[-1] / baseline

    baseline_volumes = [bar.volume for bar in bars[-config.lookback_bars - 1:-1]]
    volume_ratio = None
    if baseline_volumes:
        baseline = median(baseline_volumes)
        if baseline > 0:
            volume_ratio = latest.volume / baseline

    consecutive_down = 0
    for bar in reversed(bars):
        if bar.close < bar.open:
            consecutive_down += 1
        else:
            break

    bearish_count = sum(
        1 for item in structure.timeframes if item.trend is TrendState.DOWN
    )
    broken_support = _nearest_broken_support(structure, latest_close=latest.close)
    support_break_pct = (
        latest.close / broken_support - 1.0 if broken_support is not None else None
    )

    metrics = CrashGuardMetrics(
        one_bar_return=one_bar_return,
        window_return=window_return,
        gap_return=gap_return,
        drawdown_from_observed_high=drawdown,
        true_range_ratio=tr_ratio,
        volume_ratio=volume_ratio,
        consecutive_down_bars=consecutive_down,
        bearish_timeframe_count=bearish_count,
        support_break_pct=support_break_pct,
    )

    severe: list[str] = []
    elevated: list[str] = []
    if one_bar_return <= config.severe_one_bar_return:
        severe.append("one_bar_decline")
    elif one_bar_return <= config.elevated_one_bar_return:
        elevated.append("one_bar_decline")

    if window_return <= config.severe_window_return:
        severe.append("multi_bar_decline")
    elif window_return <= config.elevated_window_return:
        elevated.append("multi_bar_decline")

    if gap_return <= config.severe_gap_return:
        severe.append("gap_down")
    elif gap_return <= config.elevated_gap_return:
        elevated.append("gap_down")

    if drawdown <= config.severe_drawdown_from_observed_high:
        severe.append("drawdown_from_observed_high")
    elif drawdown <= config.elevated_drawdown_from_observed_high:
        elevated.append("drawdown_from_observed_high")

    if tr_ratio is not None:
        if tr_ratio >= config.severe_true_range_ratio:
            severe.append("true_range_shock")
        elif tr_ratio >= config.elevated_true_range_ratio:
            elevated.append("true_range_shock")

    if volume_ratio is not None and latest.close < latest.open:
        if volume_ratio >= config.severe_volume_ratio:
            severe.append("bearish_volume_shock")
        elif volume_ratio >= config.elevated_volume_ratio:
            elevated.append("bearish_volume_shock")

    if support_break_pct is not None:
        if support_break_pct <= config.severe_support_break_pct:
            severe.append("major_support_failure")
        elif support_break_pct <= config.elevated_support_break_pct:
            elevated.append("support_failure")

    if bearish_count >= config.bearish_alignment_timeframes:
        elevated.append("multi_timeframe_bearish_alignment")

    # A lone soft metric is not enough for a severe classification under the
    # provisional Phase-5 policy. A very large one-bar collapse, however, is
    # independently severe because waiting for a second confirmation would
    # undermine the gate's purpose.
    catastrophic_one_bar = one_bar_return <= config.severe_one_bar_return * 1.5
    if len(severe) >= config.severe_trigger_count or catastrophic_one_bar:
        state = CrashGuardState.SEVERE
        reasons = tuple(severe + elevated)
    elif severe or elevated:
        state = CrashGuardState.ELEVATED
        reasons = tuple(severe + elevated)
    else:
        state = CrashGuardState.NORMAL
        reasons = ()

    block = state is CrashGuardState.SEVERE
    return CrashGuardResult(
        state=state,
        reasons=reasons,
        metrics=metrics,
        config_version=config.version,
        config_learned=config.learned,
        block_day_long=block,
        block_swing_long=block,
        create_short_signal=False,
    )
