"""Verified Indian identity hydration for TradeBrain.

This module accepts only sanitized, explicit identity observations. Exchange-
specific network collectors/parsers are deliberately out of scope: they should
normalize their payloads into :class:`SanitizedSecurityMasterRow` and attach a
verified source receipt before calling this layer.

The merger key is ISIN. Company names are never used to join different
securities, and no missing row is interpreted as a delisting signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping
from urllib.parse import urlparse

from src.entities.models import SecurityType
from src.goal.models import EvidenceInput
from src.tradebrain.identity import (
    CanonicalSecurityIdentity,
    ExchangeListingIdentity,
    IdentityConflictError,
    IdentityIndex,
    IdentityProvenance,
    IndiaExchange,
    IssuerIdentity,
    SecurityIdentityBundle,
    normalize_isin,
)

__all__ = [
    "HydratedIdentitySet",
    "IdentitySourceAuthority",
    "SanitizedSecurityMasterRow",
    "VerifiedIdentitySource",
    "VerifiedSecurityMasterBatch",
    "hydrate_verified_identity",
]


class IdentitySourceAuthority(str, Enum):
    """Authority classification for verified identity batches."""

    NSE_OFFICIAL = "nse_official"
    BSE_OFFICIAL = "bse_official"
    LOCAL_VERIFIED = "local_verified"


_OFFICIAL_HOST_SUFFIXES: Mapping[IdentitySourceAuthority, tuple[str, ...]] = {
    IdentitySourceAuthority.NSE_OFFICIAL: ("nseindia.com",),
    IdentitySourceAuthority.BSE_OFFICIAL: ("bseindia.com",),
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


def _exact_text_key(value: str) -> str:
    """Normalize case + repeated whitespace only; this is not fuzzy matching."""
    return " ".join(_required(value, "identity text").split()).casefold()


def _exact_optional_key(value: str | None) -> str | None:
    cleaned = _optional(value)
    return cleaned.upper() if cleaned is not None else None


def _merge_optional_exact(values: Iterable[str | None], field_name: str) -> str | None:
    nonempty = [item for item in (_optional(value) for value in values) if item is not None]
    if not nonempty:
        return None
    keys = {_exact_optional_key(value) for value in nonempty}
    if len(keys) != 1:
        raise IdentityConflictError(
            f"conflicting {field_name} values for the same canonical ISIN: {nonempty!r}"
        )
    return nonempty[0]


@dataclass(frozen=True)
class VerifiedIdentitySource:
    """A provenance receipt plus an authority classification.

    Official NSE/BSE classifications fail closed unless the receipt points at an
    HTTPS host in the corresponding official domain. A future local TradeBrain
    store may use ``LOCAL_VERIFIED`` but must still carry an IdentityProvenance
    receipt.
    """

    authority: IdentitySourceAuthority | str
    provenance: IdentityProvenance

    def __post_init__(self) -> None:
        if isinstance(self.authority, IdentitySourceAuthority):
            authority = self.authority
        else:
            try:
                authority = IdentitySourceAuthority(
                    _required(str(self.authority), "authority").lower()
                )
            except ValueError as exc:
                raise ValueError(
                    f"unknown identity source authority {self.authority!r}"
                ) from exc
        object.__setattr__(self, "authority", authority)

        if self.provenance.confidence.strip().lower() != "verified":
            raise ValueError("verified identity sources require confidence='verified'")

        allowed = _OFFICIAL_HOST_SUFFIXES.get(authority)
        if allowed is None:
            return
        parsed = urlparse(self.provenance.source_uri)
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https":
            raise ValueError("official identity source URI must use HTTPS")
        if not any(host == suffix or host.endswith("." + suffix) for suffix in allowed):
            raise ValueError(
                f"{authority.value} source URI must resolve to an official domain, got {host!r}"
            )


@dataclass(frozen=True)
class SanitizedSecurityMasterRow:
    """Explicit identity observation emitted by a trusted source adapter.

    The row intentionally contains canonical field names. Phase 3 does not guess
    raw CSV column names because silently mapping the wrong column would create a
    durable identity error.
    """

    exchange: IndiaExchange | str
    symbol: str
    isin: str
    security_name: str
    issuer_entity_id: str
    issuer_legal_name: str
    exchange_security_id: str | None = None
    cin: str | None = None
    lei: str | None = None
    security_type: SecurityType = SecurityType.EQUITY
    currency: str = "INR"

    def __post_init__(self) -> None:
        exchange = self.exchange
        if not isinstance(exchange, IndiaExchange):
            try:
                exchange = IndiaExchange(_required(str(exchange), "exchange").upper())
            except ValueError as exc:
                raise ValueError("exchange must be exactly NSE or BSE") from exc
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "symbol", _required(self.symbol, "symbol").upper())
        object.__setattr__(self, "isin", normalize_isin(self.isin))
        object.__setattr__(self, "security_name", _required(self.security_name, "security_name"))
        object.__setattr__(
            self, "issuer_entity_id", _required(self.issuer_entity_id, "issuer_entity_id")
        )
        object.__setattr__(
            self, "issuer_legal_name", _required(self.issuer_legal_name, "issuer_legal_name")
        )
        object.__setattr__(self, "exchange_security_id", _optional(self.exchange_security_id))
        object.__setattr__(self, "cin", _optional(self.cin))
        object.__setattr__(self, "lei", _optional(self.lei))
        try:
            object.__setattr__(self, "security_type", SecurityType(self.security_type))
        except ValueError as exc:
            raise ValueError(f"unsupported security_type {self.security_type!r}") from exc
        currency = _required(self.currency, "currency").upper()
        if currency != "INR":
            raise ValueError("Indian security-master rows must use INR")
        object.__setattr__(self, "currency", currency)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "SanitizedSecurityMasterRow":
        """Build from canonical sanitized keys; no alias/fuzzy inference occurs."""
        required = (
            "exchange",
            "symbol",
            "isin",
            "security_name",
            "issuer_entity_id",
            "issuer_legal_name",
        )
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(
                "sanitized security-master row missing required keys: "
                + ", ".join(missing)
            )
        return cls(
            exchange=str(row["exchange"]),
            symbol=str(row["symbol"]),
            isin=str(row["isin"]),
            security_name=str(row["security_name"]),
            issuer_entity_id=str(row["issuer_entity_id"]),
            issuer_legal_name=str(row["issuer_legal_name"]),
            exchange_security_id=_optional(row.get("exchange_security_id")),  # type: ignore[arg-type]
            cin=_optional(row.get("cin")),  # type: ignore[arg-type]
            lei=_optional(row.get("lei")),  # type: ignore[arg-type]
            security_type=(
                row["security_type"]
                if isinstance(row.get("security_type"), SecurityType)
                else SecurityType(str(row.get("security_type", SecurityType.EQUITY.value)))
            ),
            currency=str(row.get("currency", "INR")),
        )


@dataclass(frozen=True)
class VerifiedSecurityMasterBatch:
    """One immutable source snapshot containing sanitized identity observations."""

    source: VerifiedIdentitySource
    rows: tuple[SanitizedSecurityMasterRow, ...]

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        if not rows:
            raise ValueError("verified security-master batch must contain at least one row")
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True)
class HydratedIdentitySet:
    """Result of merging verified identity observations by exact ISIN."""

    index: IdentityIndex
    bundles: tuple[SecurityIdentityBundle, ...]
    provenance_by_isin: Mapping[str, tuple[IdentityProvenance, ...]] = field(
        default_factory=dict
    )
    evidence_by_isin: Mapping[str, tuple[EvidenceInput, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provenance_by_isin",
            MappingProxyType(dict(self.provenance_by_isin)),
        )
        object.__setattr__(
            self,
            "evidence_by_isin",
            MappingProxyType(dict(self.evidence_by_isin)),
        )

    def provenance_for_isin(self, isin: str) -> tuple[IdentityProvenance, ...]:
        return self.provenance_by_isin.get(normalize_isin(isin), ())

    def evidence_for_isin(self, isin: str) -> tuple[EvidenceInput, ...]:
        return self.evidence_by_isin.get(normalize_isin(isin), ())


def _build_bundle(rows: list[SanitizedSecurityMasterRow]) -> SecurityIdentityBundle:
    isin = rows[0].isin
    if any(row.isin != isin for row in rows):
        raise AssertionError("_build_bundle received mixed ISINs")

    issuer_ids = {row.issuer_entity_id for row in rows}
    if len(issuer_ids) != 1:
        raise IdentityConflictError(
            f"ISIN {isin} has conflicting issuer_entity_id values: {sorted(issuer_ids)!r}"
        )

    legal_name_keys = {_exact_text_key(row.issuer_legal_name) for row in rows}
    if len(legal_name_keys) != 1:
        raise IdentityConflictError(
            f"ISIN {isin} has conflicting issuer legal names; no fuzzy merge is allowed"
        )

    security_name_keys = {_exact_text_key(row.security_name) for row in rows}
    if len(security_name_keys) != 1:
        raise IdentityConflictError(
            f"ISIN {isin} has conflicting security names; no fuzzy merge is allowed"
        )

    security_types = {row.security_type for row in rows}
    currencies = {row.currency for row in rows}
    if len(security_types) != 1 or len(currencies) != 1:
        raise IdentityConflictError(
            f"ISIN {isin} has conflicting security type/currency observations"
        )

    cin = _merge_optional_exact((row.cin for row in rows), "CIN")
    lei = _merge_optional_exact((row.lei for row in rows), "LEI")

    issuer = IssuerIdentity(
        entity_id=rows[0].issuer_entity_id,
        legal_name=rows[0].issuer_legal_name,
        cin=cin,
        lei=lei,
    )
    security = CanonicalSecurityIdentity(
        isin=isin,
        issuer_id=issuer.entity_id,
        name=rows[0].security_name,
        security_type=rows[0].security_type,
        currency=rows[0].currency,
    )

    grouped_listing_rows: dict[
        tuple[IndiaExchange, str], list[SanitizedSecurityMasterRow]
    ] = {}
    for row in rows:
        grouped_listing_rows.setdefault((row.exchange, row.symbol), []).append(row)

    listings: list[ExchangeListingIdentity] = []
    for (exchange, symbol), observations in grouped_listing_rows.items():
        exchange_security_id = _merge_optional_exact(
            (row.exchange_security_id for row in observations),
            f"{exchange.value}:{symbol} exchange_security_id",
        )
        listings.append(
            ExchangeListingIdentity(
                isin=isin,
                exchange=exchange,
                symbol=symbol,
                exchange_security_id=exchange_security_id,
            )
        )

    listings.sort(key=lambda item: (item.exchange.value, item.symbol))
    return SecurityIdentityBundle(issuer, security, tuple(listings))


def hydrate_verified_identity(
    batches: Iterable[VerifiedSecurityMasterBatch],
) -> HydratedIdentitySet:
    """Hydrate an exact identity index from verified sanitized observations.

    The function groups only by checksum-valid ISIN. It does not join on issuer
    names, symbols, or other fuzzy fields. Multiple batches may corroborate the
    same listing. Their provenance is retained independently.

    Absence is not state: if a later batch omits a prior listing, this function
    does not mark that listing inactive or delisted.
    """

    batches = tuple(batches)
    if not batches:
        raise ValueError("at least one verified identity batch is required")

    rows_by_isin: dict[str, list[SanitizedSecurityMasterRow]] = {}
    provenance_by_isin: dict[str, list[IdentityProvenance]] = {}
    evidence_by_isin: dict[str, list[EvidenceInput]] = {}

    for batch in batches:
        seen_in_batch: set[str] = set()
        for row in batch.rows:
            rows_by_isin.setdefault(row.isin, []).append(row)
            seen_in_batch.add(row.isin)
        for isin in sorted(seen_in_batch):
            receipt = batch.source.provenance
            provenance_by_isin.setdefault(isin, []).append(receipt)
            symbols = sorted(
                {row.symbol for row in batch.rows if row.isin == isin}
            )
            evidence_by_isin.setdefault(isin, []).append(
                receipt.to_evidence_input(
                    (
                        f"Verified identity observation for ISIN {isin} from "
                        f"{receipt.source_provider}"
                    ),
                    symbol_universe=symbols,
                    method="tradebrain_verified_identity_hydration",
                    assumptions={"authority": batch.source.authority.value},
                )
            )

    bundles = tuple(
        _build_bundle(rows_by_isin[isin]) for isin in sorted(rows_by_isin)
    )
    index = IdentityIndex(bundles)

    return HydratedIdentitySet(
        index=index,
        bundles=bundles,
        provenance_by_isin={
            isin: tuple(receipts) for isin, receipts in provenance_by_isin.items()
        },
        evidence_by_isin={
            isin: tuple(records) for isin, records in evidence_by_isin.items()
        },
    )
