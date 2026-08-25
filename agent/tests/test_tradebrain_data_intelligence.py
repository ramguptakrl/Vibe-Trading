from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pandas as pd
import pytest

from src.tradebrain.bse_context import BSEDecisionContextFoundation, BSEIdentityContext
from src.tradebrain.data_intelligence import build_bse_data_intelligence_context
from src.tradebrain.identity import IdentityConflictError, IdentityProvenance
from src.tradebrain.intelligence import (
    IntelligenceValidationError,
    OfficialEventAuthority,
    OfficialIssuerEventBatch,
    SanitizedIssuerEvent,
    VerifiedIntelligenceSource,
    build_bse_intelligence_snapshot,
)
from src.tradebrain.market_data import (
    FreshnessPolicy,
    FreshnessStatus,
    MarketDataValidationError,
    fetch_bse_market_data,
)

IDENTITY = BSEIdentityContext(
    issuer_entity_id="L67120MH2005PLC155188",
    legal_name="BSE Limited",
    isin="INE118H01025",
    cin="L67120MH2005PLC155188",
    primary_exchange="NSE",
    primary_symbol="BSE",
    qualified_symbol="NSE:BSE",
    vibe_symbol="BSE.NS",
    known_vibe_symbols=("BSE.NS",),
    provenance=(),
    evidence=(),
)
AS_OF = "2026-08-21T14:30:00+00:00"
RETRIEVED = "2026-08-21T14:29:00+00:00"


class FakeLoader:
    name = "yahoo"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls: list[tuple] = []

    def fetch(self, codes, start, end, *, interval="1D"):
        self.calls.append((codes, start, end, interval))
        return {codes[0]: self.frame}


def _frame(last: str = "2026-08-21T14:00:00") -> pd.DataFrame:
    index = pd.DatetimeIndex(["2026-08-21T13:55:00", last])
    return pd.DataFrame(
        {
            "open": [2300, 2310],
            "high": [2320, 2330],
            "low": [2290, 2300],
            "close": [2310, 2325],
            "volume": [1000, 1200],
        },
        index=index,
    )


def _market_snapshot(
    frame: pd.DataFrame | None = None,
    max_age: timedelta | None = timedelta(hours=1),
):
    loader = FakeLoader(_frame() if frame is None else frame)
    snapshot = fetch_bse_market_data(
        IDENTITY,
        start_date="2026-08-21",
        end_date="2026-08-21",
        interval="5m",
        retrieved_at=RETRIEVED,
        as_of=AS_OF,
        freshness_policy=FreshnessPolicy(max_age=max_age),
        loader_resolver=lambda market: loader,
    )
    return snapshot, loader


def _source(
    uri: str = "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    *,
    retrieved_at: str = RETRIEVED,
    authority: OfficialEventAuthority = OfficialEventAuthority.NSE_OFFICIAL,
) -> VerifiedIntelligenceSource:
    return VerifiedIntelligenceSource(
        authority=authority,
        provenance=IdentityProvenance(
            source_provider="NSE",
            source_type="corporate_announcements",
            source_uri=uri,
            retrieved_at=retrieved_at,
            data_as_of="2026-08-21",
            confidence="verified",
        ),
    )


def _event(**overrides) -> SanitizedIssuerEvent:
    values = {
        "source_event_id": "evt-1",
        "event_type": "announcement",
        "title": "BSE Limited announcement",
        "published_at": "2026-08-21T13:00:00+00:00",
        "isin": "INE118H01025",
        "event_uri": "https://nsearchives.nseindia.com/corporate/example",
    }
    values.update(overrides)
    return SanitizedIssuerEvent(**values)


def _intelligence_snapshot(
    rows=(),
    *,
    retrieved_at: str = RETRIEVED,
    max_age: timedelta = timedelta(hours=1),
):
    return build_bse_intelligence_snapshot(
        IDENTITY,
        (
            OfficialIssuerEventBatch(
                source=_source(retrieved_at=retrieved_at),
                rows=tuple(rows),
            ),
        ),
        as_of=AS_OF,
        max_source_age=max_age,
    )


def test_market_bridge_uses_exact_bse_symbol_and_vibe_market():
    snapshot, loader = _market_snapshot()

    assert loader.calls == [(["BSE.NS"], "2026-08-21", "2026-08-21", "5m")]
    assert snapshot.isin == "INE118H01025"
    assert snapshot.qualified_symbol == "NSE:BSE"
    assert snapshot.source_name == "yahoo"
    assert snapshot.ready is True


def test_market_snapshot_is_immutable_and_hash_is_deterministic():
    first, _ = _market_snapshot()
    second, _ = _market_snapshot()

    assert first.frame_sha256 == second.frame_sha256
    assert len(first.frame_sha256) == 64
    assert isinstance(first.bars, tuple)
    with pytest.raises(FrozenInstanceError):
        first.source_name = "x"


def test_market_snapshot_unknown_freshness_is_not_ready():
    snapshot, _ = _market_snapshot(max_age=None)

    assert snapshot.freshness is FreshnessStatus.UNKNOWN
    assert snapshot.ready is False


def test_market_snapshot_stale_is_not_ready():
    stale = _frame("2026-08-21T10:00:00")
    stale.index = pd.DatetimeIndex(
        ["2026-08-21T09:55:00", "2026-08-21T10:00:00"]
    )
    snapshot, _ = _market_snapshot(stale, timedelta(hours=1))

    assert snapshot.freshness is FreshnessStatus.STALE
    assert snapshot.ready is False


def test_market_rejects_duplicate_or_bad_ohlc():
    duplicate = _frame()
    duplicate.index = pd.DatetimeIndex(
        ["2026-08-21T14:00:00", "2026-08-21T14:00:00"]
    )
    with pytest.raises(MarketDataValidationError, match="unique"):
        _market_snapshot(duplicate)

    bad = _frame()
    bad.loc[bad.index[-1], "high"] = 2200
    with pytest.raises(MarketDataValidationError, match="high"):
        _market_snapshot(bad)


def test_market_rejects_wrong_identity_and_future_bar():
    wrong = replace(IDENTITY, isin="INE002A01018")
    with pytest.raises(MarketDataValidationError, match="verified BSE"):
        fetch_bse_market_data(
            wrong,
            start_date="2026-08-21",
            end_date="2026-08-21",
            interval="5m",
            retrieved_at=RETRIEVED,
            as_of=AS_OF,
            freshness_policy=FreshnessPolicy(max_age=timedelta(hours=1)),
            loader_resolver=lambda market: FakeLoader(_frame()),
        )

    with pytest.raises(MarketDataValidationError, match="future bar"):
        _market_snapshot(_frame("2026-08-21T15:00:00"))


def test_market_evidence_records_loader_hash_and_freshness():
    snapshot, _ = _market_snapshot()

    assert snapshot.evidence.method == "tradebrain_bse_vibe_loader_bridge"
    assert snapshot.evidence.source_provider == "yahoo"
    assert snapshot.evidence.assumptions["frame_sha256"] == snapshot.frame_sha256
    assert snapshot.evidence.assumptions["freshness"] == "fresh"


def test_official_intelligence_source_requires_correct_https_domain():
    assert _source().authority is OfficialEventAuthority.NSE_OFFICIAL

    with pytest.raises(ValueError, match="official domain"):
        _source("https://nseindia.com.evil.example/x")
    with pytest.raises(ValueError, match="HTTPS"):
        _source("http://www.nseindia.com/x")


def test_event_requires_exact_identity_key_and_pairing():
    with pytest.raises(ValueError, match="requires exact"):
        SanitizedIssuerEvent(
            source_event_id="x",
            event_type="announcement",
            title="x",
            published_at="2026-08-21T10:00:00+00:00",
        )

    with pytest.raises(ValueError, match="provided together"):
        SanitizedIssuerEvent(
            source_event_id="x",
            event_type="announcement",
            title="x",
            published_at="2026-08-21T10:00:00+00:00",
            exchange="NSE",
        )


def test_fresh_empty_official_scan_is_valid_intelligence_coverage():
    snapshot = _intelligence_snapshot()

    assert snapshot.events == ()
    assert snapshot.coverage_complete is True
    assert snapshot.ready is True
    assert snapshot.fresh_authorities == (OfficialEventAuthority.NSE_OFFICIAL,)


def test_event_visible_only_when_published_by_as_of():
    snapshot = _intelligence_snapshot(
        (
            _event(),
            _event(
                source_event_id="future",
                published_at="2026-08-21T15:00:00+00:00",
            ),
        )
    )

    assert [event.source_event_id for event in snapshot.events] == ["evt-1"]


def test_unrelated_exact_event_is_filtered_not_fuzzy_matched():
    snapshot = _intelligence_snapshot(
        (
            _event(
                source_event_id="other",
                isin="INE002A01018",
                title="BSE-looking name",
            ),
        )
    )

    assert snapshot.events == ()


def test_conflicting_isin_and_listing_fails_closed():
    conflicting = _event(
        isin="INE118H01025",
        exchange="NSE",
        symbol="NOTBSE",
    )
    with pytest.raises(IdentityConflictError, match="conflicting ISIN"):
        _intelligence_snapshot((conflicting,))


def test_stale_intelligence_source_is_not_ready():
    snapshot = _intelligence_snapshot(
        retrieved_at="2026-08-20T10:00:00+00:00",
        max_age=timedelta(hours=1),
    )

    assert snapshot.ready is False
    assert snapshot.stale_authorities == (OfficialEventAuthority.NSE_OFFICIAL,)


def test_future_retrieval_snapshot_is_rejected():
    with pytest.raises(IntelligenceValidationError, match="retrieved after"):
        _intelligence_snapshot(retrieved_at="2026-08-21T16:00:00+00:00")


def test_event_uri_must_match_source_authority():
    with pytest.raises(ValueError, match="official domain"):
        OfficialIssuerEventBatch(
            source=_source(),
            rows=(_event(event_uri="https://www.bseindia.com/x"),),
        )


def test_phase4_context_advances_only_market_data_and_intelligence():
    market_data, _ = _market_snapshot()
    intelligence = _intelligence_snapshot()
    context = build_bse_data_intelligence_context(
        BSEDecisionContextFoundation(
            profile_name="tradebrain_bse",
            advisory_only=True,
            auto_execution=False,
            identity=IDENTITY,
        ),
        market_data,
        intelligence,
    )

    assert context.readiness.market_data_ready is True
    assert context.readiness.intelligence_ready is True
    assert context.decision_ready is False
    assert context.missing_layers == (
        "market_structure",
        "historical_outcomes",
        "hard_rule_arbiter",
    )


def test_phase4_context_rejects_mismatched_canonical_inputs():
    market_data, _ = _market_snapshot()
    intelligence = _intelligence_snapshot()
    bad_market_data = replace(market_data, isin="INE002A01018")
    foundation = BSEDecisionContextFoundation(
        profile_name="tradebrain_bse",
        advisory_only=True,
        auto_execution=False,
        identity=IDENTITY,
    )

    with pytest.raises(ValueError, match="canonical ISIN"):
        build_bse_data_intelligence_context(
            foundation,
            bad_market_data,
            intelligence,
        )
