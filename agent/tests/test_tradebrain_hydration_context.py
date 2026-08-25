from dataclasses import FrozenInstanceError

import pytest

from src.tradebrain.bse_context import (
    BSE_LTD_CIN,
    BSE_LTD_ISIN,
    BSE_LTD_NSE_SYMBOL,
    bootstrap_verified_bse_ltd_identity,
    build_bse_ltd_decision_context,
)
from src.tradebrain.hydration import (
    IdentitySourceAuthority,
    SanitizedSecurityMasterRow,
    VerifiedIdentitySource,
    VerifiedSecurityMasterBatch,
    hydrate_verified_identity,
)
from src.tradebrain.identity import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityProvenance,
)


_RETRIEVED_AT = "2026-08-21T17:00:00+00:00"


def _source(
    uri: str = "https://www.nseindia.com/example",
    *,
    authority: IdentitySourceAuthority = IdentitySourceAuthority.NSE_OFFICIAL,
) -> VerifiedIdentitySource:
    return VerifiedIdentitySource(
        authority=authority,
        provenance=IdentityProvenance(
            source_provider="test provider",
            source_type="test_security_master",
            source_uri=uri,
            retrieved_at=_RETRIEVED_AT,
            confidence="verified",
        ),
    )


def _row(
    *,
    exchange: str = "NSE",
    symbol: str = "BSE",
    isin: str = BSE_LTD_ISIN,
    security_name: str = "BSE Limited",
    issuer_entity_id: str = BSE_LTD_CIN,
    issuer_legal_name: str = "BSE Limited",
    cin: str | None = BSE_LTD_CIN,
    exchange_security_id: str | None = None,
) -> SanitizedSecurityMasterRow:
    return SanitizedSecurityMasterRow(
        exchange=exchange,
        symbol=symbol,
        isin=isin,
        security_name=security_name,
        issuer_entity_id=issuer_entity_id,
        issuer_legal_name=issuer_legal_name,
        cin=cin,
        exchange_security_id=exchange_security_id,
    )


def test_official_nse_source_requires_official_https_domain():
    source = _source("https://nsearchives.nseindia.com/corporate/example")
    assert source.authority is IdentitySourceAuthority.NSE_OFFICIAL

    with pytest.raises(ValueError, match="official domain"):
        _source("https://nseindia.com.evil.example/corporate/example")

    with pytest.raises(ValueError, match="HTTPS"):
        _source("http://www.nseindia.com/corporate/example")


def test_official_bse_source_requires_bse_domain():
    source = _source(
        "https://www.bseindia.com/example",
        authority=IdentitySourceAuthority.BSE_OFFICIAL,
    )
    assert source.authority is IdentitySourceAuthority.BSE_OFFICIAL

    with pytest.raises(ValueError, match="official domain"):
        _source(
            "https://www.nseindia.com/example",
            authority=IdentitySourceAuthority.BSE_OFFICIAL,
        )


def test_verified_source_rejects_unverified_confidence():
    with pytest.raises(ValueError, match="confidence='verified'"):
        VerifiedIdentitySource(
            authority=IdentitySourceAuthority.NSE_OFFICIAL,
            provenance=IdentityProvenance(
                source_provider="NSE",
                source_type="test",
                source_uri="https://www.nseindia.com/example",
                retrieved_at=_RETRIEVED_AT,
                confidence="inferred",
            ),
        )


def test_sanitized_mapping_requires_explicit_canonical_fields():
    with pytest.raises(ValueError, match="missing required keys"):
        SanitizedSecurityMasterRow.from_mapping(
            {"exchange": "NSE", "symbol": "BSE", "isin": BSE_LTD_ISIN}
        )


def test_hydration_merges_nse_and_bse_listings_only_by_exact_isin():
    batch = VerifiedSecurityMasterBatch(
        source=_source(),
        rows=(
            _row(exchange="NSE", symbol="ABC", issuer_entity_id="issuer-1", cin=None),
            _row(exchange="BSE", symbol="123456", issuer_entity_id="issuer-1", cin=None),
        ),
    )

    hydrated = hydrate_verified_identity((batch,))
    bundle = hydrated.index.resolve_isin(BSE_LTD_ISIN).bundle

    assert {listing.qualified_symbol for listing in bundle.listings} == {
        "NSE:ABC",
        "BSE:123456",
    }


def test_hydration_rejects_conflicting_issuer_ids_for_same_isin():
    batch = VerifiedSecurityMasterBatch(
        source=_source(),
        rows=(
            _row(exchange="NSE", symbol="ABC", issuer_entity_id="issuer-1", cin=None),
            _row(exchange="BSE", symbol="123456", issuer_entity_id="issuer-2", cin=None),
        ),
    )

    with pytest.raises(IdentityConflictError, match="issuer_entity_id"):
        hydrate_verified_identity((batch,))


def test_hydration_rejects_fuzzy_legal_name_merge():
    batch = VerifiedSecurityMasterBatch(
        source=_source(),
        rows=(
            _row(
                exchange="NSE",
                symbol="ABC",
                issuer_entity_id="issuer-1",
                issuer_legal_name="Example Limited",
                cin=None,
            ),
            _row(
                exchange="BSE",
                symbol="123456",
                issuer_entity_id="issuer-1",
                issuer_legal_name="Example Industries Limited",
                cin=None,
            ),
        ),
    )

    with pytest.raises(IdentityConflictError, match="no fuzzy merge"):
        hydrate_verified_identity((batch,))


def test_duplicate_listing_can_be_corroborated_by_multiple_sources():
    first = VerifiedSecurityMasterBatch(source=_source(), rows=(_row(),))
    second = VerifiedSecurityMasterBatch(
        source=_source("https://nsearchives.nseindia.com/corporate/second"),
        rows=(_row(),),
    )

    hydrated = hydrate_verified_identity((first, second))
    bundle = hydrated.index.resolve_listing("NSE", "BSE").bundle

    assert len(bundle.listings) == 1
    assert len(hydrated.provenance_for_isin(BSE_LTD_ISIN)) == 2
    assert len(hydrated.evidence_for_isin(BSE_LTD_ISIN)) == 2


def test_hydration_does_not_infer_delisting_from_absence():
    hydrated = hydrate_verified_identity(
        (VerifiedSecurityMasterBatch(source=_source(), rows=(_row(),)),)
    )
    bundle = hydrated.index.resolve_isin(BSE_LTD_ISIN).bundle

    assert [listing.qualified_symbol for listing in bundle.listings] == ["NSE:BSE"]
    with pytest.raises(IdentityNotFoundError):
        hydrated.index.resolve_listing("BSE", "BSE")


def test_bse_bootstrap_resolves_canonical_security_from_official_sources():
    hydrated = bootstrap_verified_bse_ltd_identity(retrieved_at=_RETRIEVED_AT)
    resolution = hydrated.index.resolve_listing("NSE", BSE_LTD_NSE_SYMBOL)

    assert resolution.bundle.security.isin == BSE_LTD_ISIN
    assert resolution.bundle.issuer.cin == BSE_LTD_CIN
    assert resolution.listing is not None
    assert resolution.listing.vibe_symbol == "BSE.NS"


def test_bse_bootstrap_does_not_invent_bse_exchange_listing():
    hydrated = bootstrap_verified_bse_ltd_identity(retrieved_at=_RETRIEVED_AT)

    with pytest.raises(IdentityNotFoundError):
        hydrated.index.resolve_listing("BSE", "BSE")


def test_bse_context_inherits_advisory_only_policy_and_is_not_decision_ready():
    context = build_bse_ltd_decision_context(
        bootstrap_verified_bse_ltd_identity(retrieved_at=_RETRIEVED_AT)
    )

    assert context.profile_name == "tradebrain_bse"
    assert context.advisory_only is True
    assert context.auto_execution is False
    assert context.identity.qualified_symbol == "NSE:BSE"
    assert context.identity.vibe_symbol == "BSE.NS"
    assert context.identity.known_vibe_symbols == ("BSE.NS",)
    assert context.identity_verified is True
    assert context.decision_ready is False
    assert context.missing_layers == (
        "market_data",
        "intelligence",
        "market_structure",
        "historical_outcomes",
        "hard_rule_arbiter",
    )


def test_bse_context_keeps_official_identity_evidence_attached():
    context = build_bse_ltd_decision_context(
        bootstrap_verified_bse_ltd_identity(retrieved_at=_RETRIEVED_AT)
    )

    assert len(context.identity.provenance) == 2
    assert len(context.identity.evidence) == 2
    assert all(item.confidence == "verified" for item in context.identity.evidence)
    assert all(
        item.method == "tradebrain_verified_identity_hydration"
        for item in context.identity.evidence
    )
    assert all(
        item.source_uri and "nseindia.com" in item.source_uri
        for item in context.identity.evidence
    )


def test_bse_context_fails_closed_if_profile_target_maps_to_wrong_isin():
    wrong_isin = "INE002A01018"
    batch = VerifiedSecurityMasterBatch(
        source=_source(),
        rows=(
            _row(
                isin=wrong_isin,
                issuer_entity_id="wrong-issuer",
                cin=None,
            ),
        ),
    )
    hydrated = hydrate_verified_identity((batch,))

    with pytest.raises(IdentityConflictError, match="expected"):
        build_bse_ltd_decision_context(hydrated)


def test_phase3_records_are_immutable():
    context = build_bse_ltd_decision_context(
        bootstrap_verified_bse_ltd_identity(retrieved_at=_RETRIEVED_AT)
    )

    with pytest.raises(FrozenInstanceError):
        context.identity.isin = "INE002A01018"
