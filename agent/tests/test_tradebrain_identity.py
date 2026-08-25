from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.entities.models import EntityType, SecurityType
from src.tradebrain.identity import (
    CanonicalSecurityIdentity,
    ExchangeListingIdentity,
    IdentityConflictError,
    IdentityIndex,
    IdentityNotFoundError,
    IdentityProvenance,
    IndiaExchange,
    IssuerIdentity,
    ResolutionMethod,
    SecurityIdentityBundle,
    normalize_isin,
    parse_project_symbol,
)

RELIANCE_ISIN = "INE002A01018"


def _reliance_bundle() -> SecurityIdentityBundle:
    issuer = IssuerIdentity(
        entity_id="issuer-reliance",
        legal_name="Reliance Industries Limited",
    )
    security = CanonicalSecurityIdentity(
        isin=RELIANCE_ISIN,
        issuer_id=issuer.entity_id,
        name="Reliance Industries Limited",
    )
    return SecurityIdentityBundle(
        issuer=issuer,
        security=security,
        listings=(
            ExchangeListingIdentity(
                isin=RELIANCE_ISIN,
                exchange="NSE",
                symbol="RELIANCE",
                exchange_security_id="NSE-RELIANCE",
            ),
            ExchangeListingIdentity(
                isin=RELIANCE_ISIN,
                exchange="BSE",
                symbol="500325",
                exchange_security_id="500325",
            ),
        ),
    )


def test_isin_normalizes_and_validates_checksum() -> None:
    assert normalize_isin(" ine002a01018 ") == RELIANCE_ISIN
    with pytest.raises(ValueError):
        normalize_isin("NA")
    with pytest.raises(ValueError, match="checksum"):
        normalize_isin("INE002A01019")


def test_project_symbol_parser_requires_explicit_exchange() -> None:
    assert parse_project_symbol("RELIANCE.NS") == (IndiaExchange.NSE, "RELIANCE")
    assert parse_project_symbol("500325.BO") == (IndiaExchange.BSE, "500325")
    assert parse_project_symbol("NSE:BSE") == (IndiaExchange.NSE, "BSE")
    with pytest.raises(ValueError, match="exchange-qualified"):
        parse_project_symbol("RELIANCE")


def test_bundle_allows_multiple_listings_for_one_isin() -> None:
    bundle = _reliance_bundle()
    assert bundle.security.isin == RELIANCE_ISIN
    assert {item.qualified_symbol for item in bundle.listings} == {
        "NSE:RELIANCE",
        "BSE:500325",
    }
    assert {item.vibe_symbol for item in bundle.listings} == {
        "RELIANCE.NS",
        "500325.BO",
    }


def test_bundle_rejects_listing_for_different_isin() -> None:
    bundle = _reliance_bundle()
    bad = ExchangeListingIdentity(
        isin="INE009A01021",
        exchange="NSE",
        symbol="INFY",
    )
    with pytest.raises(IdentityConflictError):
        SecurityIdentityBundle(
            issuer=bundle.issuer,
            security=bundle.security,
            listings=(bad,),
        )


def test_index_resolves_exact_listing_and_project_symbol() -> None:
    index = IdentityIndex([_reliance_bundle()])
    by_nse = index.resolve_listing("nse", "reliance")
    by_bse = index.resolve_project_symbol("500325.BO")
    assert by_nse.bundle.security.isin == RELIANCE_ISIN
    assert by_bse.bundle.security.isin == RELIANCE_ISIN
    assert by_nse.method is ResolutionMethod.EXCHANGE_SYMBOL
    assert by_bse.method is ResolutionMethod.PROJECT_SYMBOL


def test_index_resolves_exchange_security_id() -> None:
    index = IdentityIndex([_reliance_bundle()])
    resolved = index.resolve_exchange_security_id("BSE", "500325")
    assert resolved.bundle.security.isin == RELIANCE_ISIN
    assert resolved.listing is not None
    assert resolved.method is ResolutionMethod.EXCHANGE_SECURITY_ID


def test_index_does_not_fuzzy_guess_symbols() -> None:
    index = IdentityIndex([_reliance_bundle()])
    with pytest.raises(IdentityNotFoundError):
        index.resolve_listing("NSE", "RELIANC")
    with pytest.raises(ValueError, match="exchange-qualified"):
        index.resolve_project_symbol("RELIANCE")


def test_conflicting_listing_mapping_is_rejected() -> None:
    first = _reliance_bundle()
    issuer = IssuerIdentity(entity_id="issuer-infosys", legal_name="Infosys Limited")
    other = SecurityIdentityBundle(
        issuer=issuer,
        security=CanonicalSecurityIdentity(
            isin="INE009A01021",
            issuer_id=issuer.entity_id,
            name="Infosys Limited",
        ),
        listings=(
            ExchangeListingIdentity(
                isin="INE009A01021",
                exchange="NSE",
                symbol="RELIANCE",
            ),
        ),
    )
    index = IdentityIndex([first])
    with pytest.raises(IdentityConflictError, match="already maps"):
        index.add(other)


def test_vibe_adapter_preserves_isin_as_instrument_id() -> None:
    securities = _reliance_bundle().to_vibe_securities()
    assert len(securities) == 2
    assert all(item.instrument_id == RELIANCE_ISIN for item in securities)
    assert all(item.currency == "INR" for item in securities)
    assert all(item.issuer is not None for item in securities)
    assert all(item.issuer.entity_type is EntityType.ISSUER for item in securities)
    assert all(item.security_type is SecurityType.EQUITY for item in securities)


def test_identity_models_are_immutable() -> None:
    bundle = _reliance_bundle()
    with pytest.raises(FrozenInstanceError):
        bundle.security.name = "Changed"  # type: ignore[misc]


def test_provenance_requires_timezone_and_complete_hash_pair() -> None:
    with pytest.raises(ValueError, match="timezone"):
        IdentityProvenance(
            source_provider="NSE",
            source_type="security_master",
            source_uri="https://example.test/nse.csv",
            retrieved_at="2026-08-21T10:00:00",
        )
    with pytest.raises(ValueError, match="provided together"):
        IdentityProvenance(
            source_provider="NSE",
            source_type="security_master",
            source_uri="https://example.test/nse.csv",
            retrieved_at="2026-08-21T10:00:00+05:30",
            artifact_path="raw/nse.csv",
        )


def test_provenance_maps_into_existing_vibe_evidence_model() -> None:
    digest = "A" * 64
    receipt = IdentityProvenance(
        source_provider="NSE",
        source_type="security_master",
        source_uri="https://example.test/nse.csv",
        retrieved_at="2026-08-21T10:00:00+05:30",
        data_as_of="2026-08-21",
        artifact_path="raw/security_master/nse.csv",
        artifact_sha256=digest,
        confidence="verified",
    )
    evidence = receipt.to_evidence_input(
        "Exact NSE symbol and ISIN mapping",
        symbol_universe=["NSE:RELIANCE"],
    )
    assert evidence.evidence_type == "identity"
    assert evidence.source_provider == "NSE"
    assert evidence.artifact_hash == digest.lower()
    assert evidence.data_as_of == "2026-08-21"
    assert evidence.symbol_universe == ["NSE:RELIANCE"]
    assert evidence.assumptions["tradebrain_provenance"]["retrieved_at"] == (
        "2026-08-21T10:00:00+05:30"
    )
