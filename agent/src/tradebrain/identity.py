"""Strict Indian security identity + provenance bridge for TradeBrain.

This module is additive: it does not alter Vibe-Trading loaders, databases, or
runtime registries.  It supplies the identity semantics Vibe's generic
``Entity``/``Security`` models intentionally do not enforce:

    issuer -> canonical security (ISIN) -> exchange listing(s)

No fuzzy company-name matching is performed here.  Resolution is by exact ISIN,
exact exchange+symbol, exact exchange security id, or an explicitly parseable
project symbol (``RELIANCE.NS``, ``500325.BO``, ``NSE:BSE``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Iterable, Mapping

from src.entities.models import Entity, EntityType, Security, SecurityType
from src.goal.models import EvidenceInput

__all__ = [
    "CanonicalSecurityIdentity",
    "ExchangeListingIdentity",
    "IdentityConflictError",
    "IdentityIndex",
    "IdentityNotFoundError",
    "IdentityProvenance",
    "IdentityResolution",
    "IndiaExchange",
    "IssuerIdentity",
    "ResolutionMethod",
    "SecurityIdentityBundle",
    "normalize_isin",
    "parse_project_symbol",
]

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class IdentityConflictError(ValueError):
    """Raised when two exact identifiers claim incompatible identities."""


class IdentityNotFoundError(LookupError):
    """Raised when an exact identity lookup has no known match."""


class IndiaExchange(str, Enum):
    """Indian cash-equity exchanges currently modeled by TradeBrain."""

    NSE = "NSE"
    BSE = "BSE"


class ResolutionMethod(str, Enum):
    """Deterministic methods allowed to resolve a security identity."""

    ISIN = "exact_isin"
    EXCHANGE_SYMBOL = "exact_exchange_symbol"
    EXCHANGE_SECURITY_ID = "exact_exchange_security_id"
    PROJECT_SYMBOL = "exact_project_symbol"


def _required_text(value: str, field_name: str) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError(f"{field_name} is required and cannot be empty")
    return cleaned


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _isin_luhn_valid(isin: str) -> bool:
    expanded = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in isin)
    total = 0
    for index, char in enumerate(reversed(expanded)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
        total += digit // 10 + digit % 10
    return total % 10 == 0


def normalize_isin(value: str) -> str:
    """Return an uppercase, checksum-validated ISIN.

    Placeholder values such as ``NA`` are rejected rather than turned into a
    synthetic identity.  A valid ISIN is 12 characters and passes the ISO 6166
    Luhn check digit.
    """

    cleaned = _required_text(value, "isin").upper()
    if not _ISIN_RE.fullmatch(cleaned):
        raise ValueError(
            f"invalid ISIN {value!r}; expected 12-character ISO 6166 form"
        )
    if not _isin_luhn_valid(cleaned):
        raise ValueError(f"invalid ISIN checksum for {cleaned!r}")
    return cleaned


def _normalize_exchange(value: IndiaExchange | str) -> IndiaExchange:
    if isinstance(value, IndiaExchange):
        return value
    try:
        return IndiaExchange(str(value).strip().upper())
    except ValueError as exc:
        raise ValueError("exchange must be exactly NSE or BSE") from exc


def _normalize_symbol(value: str) -> str:
    return _required_text(value, "symbol").upper()


def parse_project_symbol(code: str) -> tuple[IndiaExchange, str]:
    """Parse an explicitly exchange-qualified Vibe/broker symbol.

    Accepted forms:
    - ``RELIANCE.NS`` -> NSE / RELIANCE
    - ``500325.BO`` -> BSE / 500325
    - ``NSE:BSE`` -> NSE / BSE
    - ``BSE:500325`` -> BSE / 500325

    Bare symbols are intentionally rejected because choosing an exchange would
    be a guess.
    """

    cleaned = _required_text(code, "project symbol")
    upper = cleaned.upper()
    if upper.endswith(".NS"):
        return IndiaExchange.NSE, _normalize_symbol(cleaned[:-3])
    if upper.endswith(".BO"):
        return IndiaExchange.BSE, _normalize_symbol(cleaned[:-3])
    if ":" in cleaned:
        exchange_text, symbol = cleaned.split(":", 1)
        return _normalize_exchange(exchange_text), _normalize_symbol(symbol)
    raise ValueError(
        f"project symbol {code!r} is not exchange-qualified; use .NS, .BO, "
        "NSE:<symbol>, or BSE:<symbol>"
    )


@dataclass(frozen=True)
class IssuerIdentity:
    """Stable issuer identity above securities and listings."""

    entity_id: str
    legal_name: str
    cin: str | None = None
    lei: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_id", _required_text(self.entity_id, "entity_id"))
        object.__setattr__(self, "legal_name", _required_text(self.legal_name, "legal_name"))
        object.__setattr__(self, "cin", _normalize_optional(self.cin))
        object.__setattr__(self, "lei", _normalize_optional(self.lei))

    def to_vibe_entity(self) -> Entity:
        """Adapt this issuer to Vibe's existing generic entity model."""

        return Entity(
            entity_id=self.entity_id,
            name=self.legal_name,
            entity_type=EntityType.ISSUER,
            domicile="IN",
        )


@dataclass(frozen=True)
class CanonicalSecurityIdentity:
    """Cross-exchange security identity whose key is the ISIN."""

    isin: str
    issuer_id: str
    name: str
    security_type: SecurityType = SecurityType.EQUITY
    currency: str = "INR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "isin", normalize_isin(self.isin))
        object.__setattr__(self, "issuer_id", _required_text(self.issuer_id, "issuer_id"))
        object.__setattr__(self, "name", _required_text(self.name, "security name"))
        try:
            object.__setattr__(self, "security_type", SecurityType(self.security_type))
        except ValueError as exc:
            raise ValueError(f"unsupported security_type {self.security_type!r}") from exc
        currency = _required_text(self.currency, "currency").upper()
        if currency != "INR":
            raise ValueError("Indian cash-equity identity currency must be INR")
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True)
class ExchangeListingIdentity:
    """One exchange listing that points at a canonical ISIN security."""

    isin: str
    exchange: IndiaExchange | str
    symbol: str
    exchange_security_id: str | None = None
    active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "isin", normalize_isin(self.isin))
        object.__setattr__(self, "exchange", _normalize_exchange(self.exchange))
        object.__setattr__(self, "symbol", _normalize_symbol(self.symbol))
        object.__setattr__(
            self, "exchange_security_id", _normalize_optional(self.exchange_security_id)
        )

    @property
    def qualified_symbol(self) -> str:
        """Broker-style exact symbol, e.g. ``NSE:BSE``."""

        return f"{self.exchange.value}:{self.symbol}"

    @property
    def vibe_symbol(self) -> str:
        """Vibe/Yahoo-style market code used by the India loader chain."""

        suffix = ".NS" if self.exchange is IndiaExchange.NSE else ".BO"
        return f"{self.symbol}{suffix}"


@dataclass(frozen=True)
class SecurityIdentityBundle:
    """Issuer + canonical ISIN security + all verified exchange listings."""

    issuer: IssuerIdentity
    security: CanonicalSecurityIdentity
    listings: tuple[ExchangeListingIdentity, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        listings = tuple(self.listings)
        object.__setattr__(self, "listings", listings)
        if self.security.issuer_id != self.issuer.entity_id:
            raise IdentityConflictError(
                "canonical security issuer_id does not match issuer entity_id"
            )
        seen: set[tuple[IndiaExchange, str]] = set()
        for listing in listings:
            if listing.isin != self.security.isin:
                raise IdentityConflictError(
                    f"listing {listing.qualified_symbol} has ISIN {listing.isin}, "
                    f"expected {self.security.isin}"
                )
            key = (listing.exchange, listing.symbol)
            if key in seen:
                raise IdentityConflictError(
                    f"duplicate listing {listing.qualified_symbol} in identity bundle"
                )
            seen.add(key)

    def to_vibe_securities(self) -> tuple[Security, ...]:
        """Adapt listings to Vibe's existing ``Security`` records.

        The same canonical ISIN is deliberately used as ``instrument_id`` for
        every listing, preserving cross-exchange identity.
        """

        issuer = self.issuer.to_vibe_entity()
        return tuple(
            Security(
                instrument_id=self.security.isin,
                currency=self.security.currency,
                name=self.security.name,
                issuer=issuer,
                symbol=listing.symbol,
                exchange=listing.exchange.value,
                security_type=self.security.security_type,
            )
            for listing in self.listings
        )


@dataclass(frozen=True)
class IdentityResolution:
    """Auditable result of one deterministic identity lookup."""

    bundle: SecurityIdentityBundle
    method: ResolutionMethod
    query: str
    listing: ExchangeListingIdentity | None = None


class IdentityIndex:
    """In-memory exact resolver for verified identity bundles.

    It intentionally has no company-name fuzzy lookup.  Future persistence may
    hydrate this index from TradeBrain/DuckDB or another store without changing
    these resolution rules.
    """

    def __init__(self, bundles: Iterable[SecurityIdentityBundle] = ()) -> None:
        self._by_isin: dict[str, SecurityIdentityBundle] = {}
        self._by_listing: dict[tuple[IndiaExchange, str], SecurityIdentityBundle] = {}
        self._listing_records: dict[
            tuple[IndiaExchange, str], ExchangeListingIdentity
        ] = {}
        self._by_exchange_id: dict[
            tuple[IndiaExchange, str], tuple[SecurityIdentityBundle, ExchangeListingIdentity]
        ] = {}
        for bundle in bundles:
            self.add(bundle)

    def add(self, bundle: SecurityIdentityBundle) -> None:
        existing = self._by_isin.get(bundle.security.isin)
        if existing is not None and existing != bundle:
            raise IdentityConflictError(
                f"ISIN {bundle.security.isin} already maps to a different identity bundle"
            )
        self._by_isin[bundle.security.isin] = bundle

        for listing in bundle.listings:
            key = (listing.exchange, listing.symbol)
            prior = self._by_listing.get(key)
            if prior is not None and prior.security.isin != bundle.security.isin:
                raise IdentityConflictError(
                    f"listing {listing.qualified_symbol} already maps to "
                    f"{prior.security.isin}, cannot remap to {bundle.security.isin}"
                )
            self._by_listing[key] = bundle
            self._listing_records[key] = listing

            if listing.exchange_security_id:
                id_key = (listing.exchange, listing.exchange_security_id)
                prior_id = self._by_exchange_id.get(id_key)
                if prior_id is not None and prior_id[0].security.isin != bundle.security.isin:
                    raise IdentityConflictError(
                        f"exchange security id {listing.exchange.value}:"
                        f"{listing.exchange_security_id} already maps to "
                        f"{prior_id[0].security.isin}"
                    )
                self._by_exchange_id[id_key] = (bundle, listing)

    def resolve_isin(self, isin: str) -> IdentityResolution:
        normalized = normalize_isin(isin)
        bundle = self._by_isin.get(normalized)
        if bundle is None:
            raise IdentityNotFoundError(f"unknown ISIN {normalized}")
        return IdentityResolution(bundle, ResolutionMethod.ISIN, normalized)

    def resolve_listing(
        self, exchange: IndiaExchange | str, symbol: str
    ) -> IdentityResolution:
        ex = _normalize_exchange(exchange)
        sym = _normalize_symbol(symbol)
        key = (ex, sym)
        bundle = self._by_listing.get(key)
        if bundle is None:
            raise IdentityNotFoundError(f"unknown listing {ex.value}:{sym}")
        return IdentityResolution(
            bundle,
            ResolutionMethod.EXCHANGE_SYMBOL,
            f"{ex.value}:{sym}",
            self._listing_records[key],
        )

    def resolve_exchange_security_id(
        self, exchange: IndiaExchange | str, exchange_security_id: str
    ) -> IdentityResolution:
        ex = _normalize_exchange(exchange)
        security_id = _required_text(exchange_security_id, "exchange_security_id")
        hit = self._by_exchange_id.get((ex, security_id))
        if hit is None:
            raise IdentityNotFoundError(
                f"unknown exchange security id {ex.value}:{security_id}"
            )
        bundle, listing = hit
        return IdentityResolution(
            bundle,
            ResolutionMethod.EXCHANGE_SECURITY_ID,
            f"{ex.value}:{security_id}",
            listing,
        )

    def resolve_project_symbol(self, code: str) -> IdentityResolution:
        ex, symbol = parse_project_symbol(code)
        resolution = self.resolve_listing(ex, symbol)
        return IdentityResolution(
            resolution.bundle,
            ResolutionMethod.PROJECT_SYMBOL,
            _required_text(code, "project symbol"),
            resolution.listing,
        )


@dataclass(frozen=True)
class IdentityProvenance:
    """Immutable source receipt for an identity fact or mapping."""

    source_provider: str
    source_type: str
    source_uri: str
    retrieved_at: str
    data_as_of: str | None = None
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    confidence: str = "verified"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_provider", _required_text(self.source_provider, "source_provider")
        )
        object.__setattr__(self, "source_type", _required_text(self.source_type, "source_type"))
        object.__setattr__(self, "source_uri", _required_text(self.source_uri, "source_uri"))
        retrieved = _required_text(self.retrieved_at, "retrieved_at")
        try:
            parsed = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("retrieved_at must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone/UTC offset")
        object.__setattr__(self, "retrieved_at", retrieved)
        object.__setattr__(self, "data_as_of", _normalize_optional(self.data_as_of))
        object.__setattr__(self, "confidence", _required_text(self.confidence, "confidence"))

        path = _normalize_optional(self.artifact_path)
        digest = _normalize_optional(self.artifact_sha256)
        if (path is None) != (digest is None):
            raise ValueError(
                "artifact_path and artifact_sha256 must be provided together"
            )
        if digest is not None:
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError("artifact_sha256 must be a 64-character SHA-256 hex digest")
            digest = digest.lower()
        object.__setattr__(self, "artifact_path", path)
        object.__setattr__(self, "artifact_sha256", digest)

    def to_evidence_input(
        self,
        text: str,
        *,
        symbol_universe: Iterable[str] = (),
        method: str = "tradebrain_identity",
        assumptions: Mapping[str, object] | None = None,
    ) -> EvidenceInput:
        """Adapt this receipt into Vibe's existing evidence-ledger input.

        ``EvidenceInput`` has no caller-supplied ``retrieved_at`` field, so the
        source retrieval timestamp is retained in namespaced assumptions while
        all directly supported provenance fields map one-to-one.
        """

        metadata = dict(assumptions or {})
        metadata["tradebrain_provenance"] = {"retrieved_at": self.retrieved_at}
        return EvidenceInput(
            text=_required_text(text, "evidence text"),
            evidence_type="identity",
            source_provider=self.source_provider,
            source_type=self.source_type,
            source_uri=self.source_uri,
            symbol_universe=[str(item).strip() for item in symbol_universe if str(item).strip()],
            method=method,
            assumptions=metadata,
            artifact_path=self.artifact_path,
            artifact_hash=self.artifact_sha256,
            data_as_of=self.data_as_of,
            confidence=self.confidence,
        )
