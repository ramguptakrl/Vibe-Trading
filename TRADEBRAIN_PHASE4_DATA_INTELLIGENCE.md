# TradeBrain Phase 4 — BSE Market Data + Official Intelligence

## Purpose

Phase 4 attaches read-only market observations and official issuer-intelligence coverage to the canonical BSE Ltd identity established in Phase 3.

The phase remains additive. It does not replace Vibe-Trading's data loaders, change the India fallback chain, create orders, alter broker connectors, redesign the frontend, or generate a BUY/SELL/WAIT verdict.

## Vibe capabilities reused

Vibe already has a market-data registry with an `india_equity` fallback chain. At the frozen upstream baseline the chain is:

    yahoo -> yfinance -> india_broker -> local

The India broker bridge already adapts configured Shoonya/Dhan read-only history into the same OHLCV shape, while the Yahoo loader already understands `.NS` / `.BO` symbols and intraday/daily intervals.

Phase 4 therefore calls Vibe's existing `resolve_loader("india_equity")`; it does not register another market-data vendor.

Vibe also has an RSSHub event provider with point-in-time safeguards. Phase 4 does not use RSSHub as an official source, but it preserves the same architectural principle: an event is not visible before its publication time. Official NSE/BSE facts are kept factual and are not assigned a sentiment score in this phase.

## Market-data bridge

`agent/src/tradebrain/market_data.py` adds a strict adapter around Vibe's existing loader output.

For the BSE profile it requires the already-verified identity:

    ISIN              INE118H01025
    Exact listing     NSE:BSE
    Vibe symbol       BSE.NS
    Market            india_equity

The adapter:

1. resolves the existing Vibe India loader chain;
2. requests the exact `BSE.NS` series;
3. requires a non-empty `DatetimeIndex`;
4. requires ascending, unique timestamps;
5. requires numeric finite `open/high/low/close/volume`;
6. rejects negative volume;
7. validates OHLC geometry;
8. rejects materially future bars;
9. converts bars into immutable `OHLCVBar` records;
10. computes a deterministic SHA-256 over the normalized bars;
11. creates a Vibe `EvidenceInput` describing loader, symbol, timeframe, hash and freshness.

### Explicit freshness policy

Phase 4 intentionally does **not** hide a guessed interval-specific freshness limit in the adapter.

The caller supplies `FreshnessPolicy(max_age=...)`.

If `max_age=None`, freshness is `UNKNOWN` and the market-data layer is **not ready**. If the latest bar exceeds the supplied age limit it is `STALE` and also not ready.

This keeps future DAY/SWING logic from silently inheriting arbitrary staleness assumptions from a generic loader.

### Naive timestamps

Vibe loaders can return timezone-naive indices. Phase 4 requires an explicit `naive_index_timezone` assumption in `FreshnessPolicy`; the current default is `UTC`, matching the existing Yahoo loader's UTC-naive conversion. The assumption is written into evidence rather than hidden.

## Official issuer-intelligence bridge

`agent/src/tradebrain/intelligence.py` adds a sanitized official-event contract for NSE/BSE announcements and corporate actions.

It is **not a network scraper**. Future exchange adapters must normalize raw responses into `SanitizedIssuerEvent` / `OfficialIssuerEventBatch` and attach provenance.

Official source authorities are:

- `nse_official`
- `bse_official`

The source URI must use HTTPS and resolve to the matching official domain (`nseindia.com` or `bseindia.com`). Event-specific URIs, when present, must match the same authority.

### Identity binding

An event must carry at least one exact identity key:

- ISIN; and/or
- exchange + symbol.

For BSE Ltd:

    ISIN          INE118H01025
    Listing       NSE:BSE

Company-name similarity is never used for attachment.

If an event supplies both ISIN and listing and they disagree, the system fails closed with an identity conflict.

### Point-in-time visibility

Only events with `published_at <= as_of` enter the Phase-4 snapshot. Future-published events are excluded.

No Phase-4 LLM/sentiment score is created from official facts. Later reasoning may interpret the event, but the source layer remains factual.

### Empty official scans are meaningful

An official source scan may contain zero matching BSE events and still prove that the source was checked.

That distinction is important:

    no fresh source check        !=      fresh source check, zero events

The second case can satisfy intelligence coverage; the first cannot.

For BSE Ltd the default required authority is NSE because the verified equity listing is `NSE:BSE`. BSE-official coverage may be added where relevant but is not invented as a listing requirement.

## Phase-4 composition

`agent/src/tradebrain/data_intelligence.py` combines:

- Phase-3 canonical identity foundation;
- validated market-data snapshot;
- official intelligence snapshot.

It advances only the readiness flags it can actually prove:

    identity_verified          READY (from Phase 3)
    market_data_ready          based on Phase-4 freshness/validation
    intelligence_ready         based on official fresh coverage
    market_structure_ready     NOT READY
    historical_outcomes_ready  NOT READY
    hard_rule_arbiter_ready    NOT READY

Therefore even with fresh prices and a completed NSE announcement check:

    decision_ready = False

No recommendation is generated in Phase 4.

## What Phase 4 does NOT build

- No new market-data provider.
- No modification of Vibe's `india_equity` fallback order.
- No live Kite integration.
- No automatic NSE/BSE announcement scraper yet.
- No sentiment/LLM classification of official events.
- No market structure, support/resistance, ATH logic or Crash Guard.
- No historical analogue/outcome engine.
- No MTF cost engine.
- No DAY/SWING candidate generator.
- No hard-rule arbiter implementation.
- No broker/order wiring.
- No frontend/API changes.

## Validation

Targeted Phase-4 contract validation was executed in an isolated environment using the exact Phase-4 module/test contents and compatible stubs for the already-existing upstream/Phase-3 contracts.

Result:

    18 passed

Coverage includes:

- exact `BSE.NS` request through the `india_equity` resolver;
- deterministic bar hashing;
- immutable bar snapshots;
- unknown/stale freshness preventing readiness;
- duplicate timestamp and invalid-OHLC rejection;
- future-bar rejection;
- evidence metadata;
- official NSE/BSE domain enforcement;
- exact event identity requirements;
- fresh empty official-scan coverage;
- point-in-time event filtering;
- no fuzzy attachment by company-looking title;
- ISIN/listing conflict rejection;
- stale/future intelligence source guards;
- event-URI authority enforcement;
- Phase-4 readiness advancing only market-data and intelligence;
- canonical mismatch rejection during composition.

Full upstream Vibe CI is still recorded separately and must not be described as passing unless an actual workflow completes successfully.

## Next engineering phase

Phase 5 should build **market structure + Crash Guard inputs** on top of the immutable Phase-4 bar snapshot rather than fetching prices independently.

Preferred order:

1. multi-timeframe bar normalization/derivation with no look-ahead;
2. market regime/trend context;
3. structural supports/resistances;
4. comparable ATH / major structure state;
5. Crash Guard as a deterministic risk gate;
6. tests proving no future data enters a historical decision timestamp.

Historical outcome learning and final DAY/SWING candidate generation should remain later phases.
