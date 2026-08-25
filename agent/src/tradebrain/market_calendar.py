"""Fail-closed verified exchange-calendar contract for TradeBrain BSE.

TradeBrain must not infer a live NSE session from weekdays alone.  A caller may
provide a source-audited JSON snapshot under the runtime directory.  If that
snapshot is absent, malformed, outside its validity window, or does not contain
the queried date, the calendar is *not verified* and market-active operation is
blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from src.config.paths import get_runtime_root

__all__ = [
    "ExchangeCalendarSnapshot",
    "TradingDayResolution",
    "load_exchange_calendar",
    "resolve_trading_day",
]

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class ExchangeCalendarSnapshot:
    exchange: str
    timezone: str
    valid_from: date
    valid_to: date
    trading_dates: frozenset[date]
    source_name: str
    source_url: str
    source_sha256: str
    snapshot_sha256: str


@dataclass(frozen=True)
class TradingDayResolution:
    local_date: str
    is_trading_day: bool
    verified: bool
    source_name: str | None
    source_url: str | None
    snapshot_sha256: str | None
    blocker: str | None


def _default_path() -> Path:
    return get_runtime_root() / "tradebrain" / "nse_calendar.json"


def _snapshot_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def load_exchange_calendar(path: Path | None = None) -> ExchangeCalendarSnapshot:
    target = path or _default_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    if str(raw.get("exchange", "")).strip().upper() != "NSE":
        raise ValueError("calendar exchange must be NSE")
    if str(raw.get("timezone", "")).strip() != "Asia/Kolkata":
        raise ValueError("calendar timezone must be Asia/Kolkata")
    source_name = str(raw.get("source_name", "")).strip()
    source_url = str(raw.get("source_url", "")).strip()
    source_sha = str(raw.get("source_sha256", "")).strip().lower()
    if not source_name or not source_url:
        raise ValueError("calendar source_name and source_url are required")
    if not _SHA256_RE.fullmatch(source_sha):
        raise ValueError("calendar source_sha256 must be a 64-character hexadecimal SHA-256")

    valid_from = date.fromisoformat(str(raw["valid_from"]))
    valid_to = date.fromisoformat(str(raw["valid_to"]))
    if valid_to < valid_from:
        raise ValueError("calendar valid_to cannot precede valid_from")

    trading_dates = frozenset(date.fromisoformat(str(item)) for item in raw.get("trading_dates", []))
    if not trading_dates:
        raise ValueError("calendar trading_dates cannot be empty")
    if any(item < valid_from or item > valid_to for item in trading_dates):
        raise ValueError("calendar trading_dates must fall inside the validity window")

    fingerprint_payload = {
        "exchange": "NSE",
        "timezone": "Asia/Kolkata",
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
        "trading_dates": sorted(item.isoformat() for item in trading_dates),
        "source_name": source_name,
        "source_url": source_url,
        "source_sha256": source_sha,
    }
    return ExchangeCalendarSnapshot(
        exchange="NSE",
        timezone="Asia/Kolkata",
        valid_from=valid_from,
        valid_to=valid_to,
        trading_dates=trading_dates,
        source_name=source_name,
        source_url=source_url,
        source_sha256=source_sha,
        snapshot_sha256=_snapshot_hash(fingerprint_payload),
    )


def resolve_trading_day(at: datetime, path: Path | None = None) -> TradingDayResolution:
    local_date = at.astimezone(_IST).date() if at.tzinfo is not None else at.replace(tzinfo=_IST).date()
    target = path or _default_path()
    if not target.exists():
        return TradingDayResolution(
            local_date=local_date.isoformat(),
            is_trading_day=False,
            verified=False,
            source_name=None,
            source_url=None,
            snapshot_sha256=None,
            blocker="verified_nse_exchange_calendar_missing",
        )
    try:
        snapshot = load_exchange_calendar(target)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return TradingDayResolution(
            local_date=local_date.isoformat(),
            is_trading_day=False,
            verified=False,
            source_name=None,
            source_url=None,
            snapshot_sha256=None,
            blocker="verified_nse_exchange_calendar_invalid",
        )
    if local_date < snapshot.valid_from or local_date > snapshot.valid_to:
        return TradingDayResolution(
            local_date=local_date.isoformat(),
            is_trading_day=False,
            verified=False,
            source_name=snapshot.source_name,
            source_url=snapshot.source_url,
            snapshot_sha256=snapshot.snapshot_sha256,
            blocker="verified_nse_exchange_calendar_out_of_range",
        )
    return TradingDayResolution(
        local_date=local_date.isoformat(),
        is_trading_day=local_date in snapshot.trading_dates,
        verified=True,
        source_name=snapshot.source_name,
        source_url=snapshot.source_url,
        snapshot_sha256=snapshot.snapshot_sha256,
        blocker=None,
    )
