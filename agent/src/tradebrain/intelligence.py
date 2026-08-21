"""Verified official issuer-intelligence bridge for BSE Ltd (Phase 4).

This module consumes sanitized NSE/BSE announcement/corporate-action snapshots.
It does not scrape exchange sites itself. Source adapters must attach official
provenance and exact identifiers; this layer binds facts to the Phase-3 BSE Ltd
identity, enforces point-in-time visibility, and records coverage even when an
official scan returns zero matching events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping
from urllib.parse import urlparse

from src.goal.models import EvidenceInput
from src.tradebrain.bse_context import BSEIdentityContext, BSE_LTD_ISIN
from src.tradebrain.identity import IdentityConflictError, IdentityProvenance, normalize_isin

__all__ = [
    "BSEIntelligenceSnapshot",
    "IntelligenceValidationError",
    "IssuerEventType",
    "OfficialEventAuthority",
    "OfficialIssuerEventBatch",
    "SanitizedIssuerEvent",
    "VerifiedIntelligenceSource",
    "build_bse_intelligence_snapshot",
]


class IntelligenceValidationError(ValueError):
    """Raised when official intelligence cannot be safely attached to BSE Ltd."""


class OfficialEventAuthority(str, Enum):
    NSE_OFFICIAL = "nse_official"
    BSE_OFFICIAL = "bse_official"


class IssuerEventType(str, Enum):
    ANNOUNCEMENT = "announcement"
    CORPORATE_ACTION = "corporate_action"
    FINANCIAL_RESULT = "financial_result"
    BOARD_MEETING = "board_meeting"
    REGULATORY = "regulatory"
    SHAREHOLDER = "shareholder"
    OTHER = "other"


_HOSTS: Mapping[OfficialEventAuthority, tuple[str, ...]] = {
    OfficialEventAuthority.NSE_OFFICIAL: ("nseindia.com",),
    OfficialEventAuthority.BSE_OFFICIAL: ("bseindia.com",),
}


def _required(value: str, field_name: str) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError(f"{field_name} is required and cannot be empty")
    return cleaned


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _aware(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_required(value, field_name).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone/UTC offset")
    return parsed


def _validate_official_uri(uri: str, authority: OfficialEventAuthority) -> None:
    parsed = urlparse(_required(uri, "source URI"))
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise ValueError("official intelligence URI must use HTTPS")
    allowed = _HOSTS[authority]
    if not any(host == suffix or host.endswith("." + suffix) for suffix in allowed):
        raise ValueError(
            f"{authority.value} intelligence URI must resolve to an official domain, got {host!r}"
        )


@dataclass(frozen=True)
class VerifiedIntelligenceSource:
    """Official NSE/BSE source receipt for one sanitized event snapshot."""

    authority: OfficialEventAuthority | str
    provenance: IdentityProvenance

    def __post_init__(self) -> None:
        if isinstance(self.authority, OfficialEventAuthority):
            authority = self.authority
        else:
            try:
                authority = OfficialEventAuthority(
                    _required(str(self.authority), "authority").lower()
                )
            except ValueError as exc:
                raise ValueError(
                    f"unknown official event authority {self.authority!r}"
                ) from exc
        object.__setattr__(self, "authority", authority)
        if self.provenance.confidence.strip().lower() != "verified":
            raise ValueError("official intelligence sources require confidence='verified'")
        _validate_official_uri(self.provenance.source_uri, authority)


@dataclass(frozen=True)
class SanitizedIssuerEvent:
    """Explicit announcement/corporate-action fact with exact identity keys."""

    source_event_id: str
    event_type: IssuerEventType | str
    title: str
    published_at: str
    isin: str | None = None
    exchange: str | None = None
    symbol: str | None = None
    effective_date: date | str | None = None
    event_uri: str | None = None
    summary: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_event_id", _required(self.source_event_id, "source_event_id")
        )
        try:
            event_type = (
                self.event_type
                if isinstance(self.event_type, IssuerEventType)
                else IssuerEventType(
                    _required(str(self.event_type), "event_type").lower()
                )
            )
        except ValueError as exc:
            raise ValueError(f"unknown issuer event_type {self.event_type!r}") from exc
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "title", _required(self.title, "title"))
        published = _aware(self.published_at, "published_at")
        object.__setattr__(self, "published_at", published.isoformat())

        isin = _optional(self.isin)
        if isin is not None:
            isin = normalize_isin(isin)
        object.__setattr__(self, "isin", isin)

        exchange = _optional(self.exchange)
        symbol = _optional(self.symbol)
        if (exchange is None) != (symbol is None):
            raise ValueError("exchange and symbol must be provided together")
        if exchange is not None:
            exchange = exchange.upper()
            if exchange not in {"NSE", "BSE"}:
                raise ValueError("event exchange must be NSE or BSE")
            symbol = symbol.upper() if symbol is not None else None
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "symbol", symbol)
        if isin is None and exchange is None:
            raise ValueError(
                "issuer event requires exact ISIN and/or exchange+symbol identity"
            )

        if self.effective_date is not None:
            try:
                effective = (
                    self.effective_date
                    if isinstance(self.effective_date, date)
                    else date.fromisoformat(str(self.effective_date).strip())
                )
            except ValueError as exc:
                raise ValueError("effective_date must be ISO YYYY-MM-DD") from exc
            object.__setattr__(self, "effective_date", effective)

        object.__setattr__(self, "event_uri", _optional(self.event_uri))
        object.__setattr__(self, "summary", str(self.summary or "").strip())
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class OfficialIssuerEventBatch:
    """One official source scan; rows may be empty and still prove coverage."""

    source: VerifiedIntelligenceSource
    rows: tuple[SanitizedIssuerEvent, ...] = ()

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        for row in rows:
            if row.event_uri is not None:
                _validate_official_uri(row.event_uri, self.source.authority)
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True)
class BSEIntelligenceSnapshot:
    """Point-in-time official intelligence attached to canonical BSE Ltd."""

    isin: str
    qualified_symbol: str
    as_of: str
    required_authorities: tuple[OfficialEventAuthority, ...]
    fresh_authorities: tuple[OfficialEventAuthority, ...]
    stale_authorities: tuple[OfficialEventAuthority, ...]
    events: tuple[SanitizedIssuerEvent, ...]
    evidence: tuple[EvidenceInput, ...]

    @property
    def coverage_complete(self) -> bool:
        return all(
            authority in self.fresh_authorities for authority in self.required_authorities
        )

    @property
    def ready(self) -> bool:
        return self.coverage_complete


def _event_matches_identity(
    event: SanitizedIssuerEvent, identity: BSEIdentityContext
) -> bool:
    isin_match: bool | None = None
    listing_match: bool | None = None

    if event.isin is not None:
        isin_match = event.isin == identity.isin
    if event.exchange is not None and event.symbol is not None:
        listing_match = (
            event.exchange == identity.primary_exchange.upper()
            and event.symbol == identity.primary_symbol.upper()
        )

    if isin_match is not None and listing_match is not None and isin_match != listing_match:
        raise IdentityConflictError(
            f"official event {event.source_event_id!r} has conflicting ISIN and listing identity"
        )
    return bool(isin_match or listing_match)


def build_bse_intelligence_snapshot(
    identity: BSEIdentityContext,
    batches: Iterable[OfficialIssuerEventBatch],
    *,
    as_of: str | datetime,
    max_source_age: timedelta,
    required_authorities: Iterable[OfficialEventAuthority] = (
        OfficialEventAuthority.NSE_OFFICIAL,
    ),
    future_tolerance: timedelta = timedelta(minutes=5),
) -> BSEIntelligenceSnapshot:
    """Build official BSE Ltd event context with point-in-time/freshness guards."""

    if identity.isin != BSE_LTD_ISIN or identity.qualified_symbol != "NSE:BSE":
        raise IntelligenceValidationError(
            "official intelligence can be attached only to verified BSE Ltd identity"
        )
    if max_source_age.total_seconds() < 0 or future_tolerance.total_seconds() < 0:
        raise ValueError("freshness durations cannot be negative")

    cutoff = _aware(as_of, "as_of")
    required = tuple(dict.fromkeys(required_authorities))
    if not required:
        raise ValueError("at least one required official authority is needed")

    fresh: set[OfficialEventAuthority] = set()
    stale: set[OfficialEventAuthority] = set()
    evidence: list[EvidenceInput] = []
    seen_events: dict[
        tuple[OfficialEventAuthority, str], SanitizedIssuerEvent
    ] = {}

    for batch in tuple(batches):
        retrieved = _aware(batch.source.provenance.retrieved_at, "source retrieved_at")
        if retrieved > cutoff + future_tolerance:
            raise IntelligenceValidationError(
                f"{batch.source.authority.value} intelligence snapshot was retrieved after as_of"
            )
        age = max(0.0, (cutoff - retrieved).total_seconds())
        if age <= max_source_age.total_seconds():
            fresh.add(batch.source.authority)
        else:
            stale.add(batch.source.authority)

        matched_count = 0
        for event in batch.rows:
            published = _aware(event.published_at, "event published_at")
            if published > cutoff:
                continue
            if not _event_matches_identity(event, identity):
                continue
            matched_count += 1
            key = (batch.source.authority, event.source_event_id)
            prior = seen_events.get(key)
            if prior is not None and prior != event:
                raise IdentityConflictError(
                    f"official event id {key!r} was reused for conflicting facts"
                )
            seen_events[key] = event

        receipt = batch.source.provenance
        evidence.append(
            EvidenceInput(
                text=(
                    f"Official {batch.source.authority.value} intelligence snapshot checked "
                    f"for BSE Ltd; {matched_count} matching event(s) visible as of "
                    f"{cutoff.isoformat()}"
                ),
                evidence_type="issuer_intelligence",
                source_provider=receipt.source_provider,
                source_type=receipt.source_type,
                source_uri=receipt.source_uri,
                symbol_universe=[identity.vibe_symbol],
                method="tradebrain_bse_official_intelligence_bridge",
                assumptions={
                    "authority": batch.source.authority.value,
                    "retrieved_at": receipt.retrieved_at,
                    "source_age_seconds": age,
                    "matching_event_count": matched_count,
                },
                artifact_path=receipt.artifact_path,
                artifact_hash=receipt.artifact_sha256,
                data_as_of=receipt.data_as_of,
                confidence="verified",
            )
        )

    events = tuple(
        sorted(
            seen_events.values(),
            key=lambda item: (
                _aware(item.published_at, "published_at"),
                item.source_event_id,
            ),
            reverse=True,
        )
    )
    return BSEIntelligenceSnapshot(
        isin=identity.isin,
        qualified_symbol=identity.qualified_symbol,
        as_of=cutoff.isoformat(),
        required_authorities=required,
        fresh_authorities=tuple(sorted(fresh, key=lambda item: item.value)),
        stale_authorities=tuple(sorted(stale - fresh, key=lambda item: item.value)),
        events=events,
        evidence=tuple(evidence),
    )
