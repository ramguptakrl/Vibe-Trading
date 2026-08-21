"""Read-only BSE Ltd market-data bridge for TradeBrain Phase 4.

The adapter deliberately reuses Vibe-Trading's existing ``india_equity`` loader
registry.  It does not register a new data vendor, alter fallback order, or touch
broker write paths.  Its job is to validate the returned OHLCV frame, bind it to
the already-verified BSE Ltd identity, attach deterministic provenance, and fail
closed when freshness is unknown or insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
import math
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from backtest.loaders.registry import resolve_loader
from src.goal.models import EvidenceInput
from src.tradebrain.bse_context import BSEIdentityContext, BSE_LTD_ISIN

__all__ = [
    "BSEMarketDataSnapshot",
    "FreshnessPolicy",
    "FreshnessStatus",
    "MarketDataValidationError",
    "OHLCVBar",
    "fetch_bse_market_data",
]

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


class MarketDataValidationError(ValueError):
    """Raised when a loader response cannot safely become BSE decision input."""


class FreshnessStatus(str, Enum):
    """Freshness state of a validated market-data snapshot."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


def _aware_datetime(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO-8601") from exc
    else:
        raise ValueError(f"{field_name} must be datetime or ISO-8601 string")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone/UTC offset")
    return parsed


@dataclass(frozen=True)
class FreshnessPolicy:
    """Explicit staleness limits chosen by the caller/decision profile.

    Phase 4 intentionally has no hidden interval-specific default. A caller that
    does not provide ``max_age`` gets ``UNKNOWN`` freshness and therefore cannot
    mark the market-data layer ready.
    """

    max_age: timedelta | None
    future_tolerance: timedelta = timedelta(minutes=5)
    naive_index_timezone: str = "UTC"

    def __post_init__(self) -> None:
        if self.max_age is not None and self.max_age.total_seconds() < 0:
            raise ValueError("max_age cannot be negative")
        if self.future_tolerance.total_seconds() < 0:
            raise ValueError("future_tolerance cannot be negative")
        try:
            ZoneInfo(self.naive_index_timezone)
        except Exception as exc:  # pragma: no cover - platform tz database failure
            raise ValueError(
                f"unknown naive_index_timezone {self.naive_index_timezone!r}"
            ) from exc


@dataclass(frozen=True)
class OHLCVBar:
    """Immutable normalized bar used by later TradeBrain structure/history layers."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BSEMarketDataSnapshot:
    """Validated read-only market data bound to canonical BSE Ltd identity."""

    isin: str
    qualified_symbol: str
    vibe_symbol: str
    market: str
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

    def to_frame(self) -> pd.DataFrame:
        """Materialize a defensive DataFrame copy for existing Vibe analytics."""
        frame = pd.DataFrame(
            [
                {
                    "trade_date": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in self.bars
            ]
        )
        if frame.empty:
            return frame
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], utc=True)
        frame = frame.set_index("trade_date")
        frame.index.name = "trade_date"
        return frame


def _normalize_timestamp(value: object, naive_tz: str) -> datetime:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise MarketDataValidationError("market-data index contains an invalid timestamp")
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(ZoneInfo(naive_tz))
    return stamp.to_pydatetime()


def _validate_frame(
    frame: pd.DataFrame,
    *,
    naive_tz: str,
) -> tuple[OHLCVBar, ...]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise MarketDataValidationError("market-data loader returned no BSE bars")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketDataValidationError("market-data frame must use a DatetimeIndex")
    if not frame.index.is_monotonic_increasing:
        raise MarketDataValidationError("market-data timestamps must be ascending")
    if not frame.index.is_unique:
        raise MarketDataValidationError("market-data timestamps must be unique")

    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise MarketDataValidationError(
            "market-data frame missing required OHLCV columns: " + ", ".join(missing)
        )

    bars: list[OHLCVBar] = []
    for timestamp, row in frame.loc[:, list(_REQUIRED_COLUMNS)].iterrows():
        values: dict[str, float] = {}
        for column in _REQUIRED_COLUMNS:
            try:
                value = float(row[column])
            except (TypeError, ValueError) as exc:
                raise MarketDataValidationError(
                    f"market-data {column} is not numeric at {timestamp!r}"
                ) from exc
            if not math.isfinite(value):
                raise MarketDataValidationError(
                    f"market-data {column} is not finite at {timestamp!r}"
                )
            values[column] = value

        if values["volume"] < 0:
            raise MarketDataValidationError(
                f"market-data volume cannot be negative at {timestamp!r}"
            )
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise MarketDataValidationError(
                f"market-data high is inconsistent at {timestamp!r}"
            )
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise MarketDataValidationError(
                f"market-data low is inconsistent at {timestamp!r}"
            )

        aware = _normalize_timestamp(timestamp, naive_tz)
        bars.append(
            OHLCVBar(
                timestamp=aware.isoformat(),
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                volume=values["volume"],
            )
        )
    return tuple(bars)


def _bars_hash(bars: Iterable[OHLCVBar]) -> str:
    canonical = "\n".join(
        "|".join(
            (
                bar.timestamp,
                format(bar.open, ".12g"),
                format(bar.high, ".12g"),
                format(bar.low, ".12g"),
                format(bar.close, ".12g"),
                format(bar.volume, ".12g"),
            )
        )
        for bar in bars
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def fetch_bse_market_data(
    identity: BSEIdentityContext,
    *,
    start_date: str,
    end_date: str,
    interval: str,
    retrieved_at: str | datetime,
    as_of: str | datetime,
    freshness_policy: FreshnessPolicy,
    loader_resolver: Callable[[str], object] = resolve_loader,
) -> BSEMarketDataSnapshot:
    """Fetch BSE Ltd OHLCV through Vibe's existing India fallback chain.

    ``loader_resolver`` is injectable for deterministic tests. Production callers
    use Vibe's ``resolve_loader('india_equity')`` unchanged, which currently
    prefers Yahoo/yfinance and can fall through to the configured India broker.
    """

    if identity.isin != BSE_LTD_ISIN or identity.qualified_symbol != "NSE:BSE":
        raise MarketDataValidationError(
            "market data can be attached only to the verified BSE Ltd NSE:BSE identity"
        )

    retrieved = _aware_datetime(retrieved_at, "retrieved_at")
    cutoff = _aware_datetime(as_of, "as_of")
    if retrieved > cutoff + freshness_policy.future_tolerance:
        raise MarketDataValidationError("retrieved_at is materially after as_of")

    loader = loader_resolver("india_equity")
    source_name = str(getattr(loader, "name", type(loader).__name__)).strip()
    if not source_name:
        raise MarketDataValidationError("resolved Vibe loader has no source name")
    if not hasattr(loader, "fetch"):
        raise MarketDataValidationError("resolved Vibe loader does not expose fetch()")

    payload = loader.fetch(
        [identity.vibe_symbol],
        start_date,
        end_date,
        interval=interval,
    )
    if not isinstance(payload, dict) or identity.vibe_symbol not in payload:
        raise MarketDataValidationError(
            f"{source_name} returned no exact {identity.vibe_symbol} series"
        )

    bars = _validate_frame(
        payload[identity.vibe_symbol],
        naive_tz=freshness_policy.naive_index_timezone,
    )
    latest = _aware_datetime(bars[-1].timestamp, "latest bar timestamp")
    if latest > cutoff + freshness_policy.future_tolerance:
        raise MarketDataValidationError("market-data series contains a future bar")

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
            f"BSE Ltd OHLCV observed through Vibe loader {source_name} for "
            f"{identity.vibe_symbol} ({interval})"
        ),
        evidence_type="market_data",
        source_provider=source_name,
        source_type="ohlcv",
        source_uri=f"vibe-loader:{source_name}",
        symbol_universe=[identity.vibe_symbol],
        timeframe=interval,
        method="tradebrain_bse_vibe_loader_bridge",
        assumptions={
            "market": "india_equity",
            "naive_index_timezone": freshness_policy.naive_index_timezone,
            "frame_sha256": digest,
            "freshness": freshness.value,
            "age_seconds": age_seconds,
        },
        data_as_of=latest.isoformat(),
        confidence="observed",
    )

    return BSEMarketDataSnapshot(
        isin=identity.isin,
        qualified_symbol=identity.qualified_symbol,
        vibe_symbol=identity.vibe_symbol,
        market="india_equity",
        interval=str(interval),
        source_name=source_name,
        requested_start=start_date,
        requested_end=end_date,
        retrieved_at=retrieved.isoformat(),
        data_as_of=latest.isoformat(),
        age_seconds=age_seconds,
        freshness=freshness,
        frame_sha256=digest,
        bars=bars,
        evidence=evidence,
    )
