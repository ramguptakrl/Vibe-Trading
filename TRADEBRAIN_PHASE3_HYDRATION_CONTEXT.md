# TradeBrain Phase 3 — Verified India Identity Hydration + BSE Context Foundation

## Scope

Phase 3 connects the strict Phase 2 identity model to verified source observations and creates the first canonical BSE Ltd decision-context envelope.

This phase remains additive. It does **not** wire TradeBrain into Vibe's existing broker/order path, does not fetch live prices, does not calculate market structure, and does not issue trading decisions.

## Reuse decisions

Vibe already provides:

- generic issuer/security models;
- India market-data loaders and NSE/BSE symbol conventions;
- evidence records with source URI, data-as-of, confidence and artifact hash fields.

TradeBrain therefore adds only the missing layer between verified Indian source observations and the canonical Phase 2 identity index.

## New modules

### `agent/src/tradebrain/hydration.py`

Adds a fail-closed verified identity hydration boundary.

Input is a `VerifiedSecurityMasterBatch` containing:

1. a `VerifiedIdentitySource` receipt; and
2. one or more `SanitizedSecurityMasterRow` observations.

Rows must use explicit canonical fields. Phase 3 intentionally does not infer raw CSV column aliases.

Hydration rules:

- checksum-valid ISIN is the merge key;
- issuer/symbol/name similarity is never a merge key;
- exact duplicate listings may be corroborated by multiple sources;
- conflicting issuer IDs, legal names, security names, CINs, LEIs or exchange security IDs fail closed;
- missing from one source snapshot does **not** create a delisted/inactive fact;
- NSE/BSE official source classifications require HTTPS URLs in the corresponding official domain;
- verified source receipts must carry `confidence="verified"`;
- provenance and Vibe `EvidenceInput` records remain attached by ISIN.

### `agent/src/tradebrain/bse_context.py`

Adds the canonical BSE Ltd target guard.

The Phase 3 verified reference is:

- Legal name: `BSE Limited`
- CIN: `L67120MH2005PLC155188`
- ISIN: `INE118H01025`
- Primary listing used by the TradeBrain profile: `NSE:BSE`
- Vibe/Yahoo-style symbol: `BSE.NS`

Official bootstrap evidence:

1. NSE integrated filing, data-as-of 2026-05-07:
   `https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_156058_07052026182427_iXBRL_WEB.html`
2. BSE Limited FY2024-25 annual report hosted by NSE:
   `https://archives.nseindia.com/annual_reports/AR_27090_BSE_2024_2025_A_24072025103555.pdf`

The first source carries the NSE symbol, company name and ISIN. The annual report carries BSE Limited's CIN and identifies NSE as the exchange where its shares were listed for that report.

These references are a verified bootstrap snapshot, **not** a live-fetch implementation. Future source collectors should refresh the same contract and, when raw bytes are archived, attach SHA-256 hashes.

## Decision-context readiness

Phase 3 introduces `BSEDecisionContextFoundation`.

It deliberately reports only identity as ready:

- identity: ready;
- market data: not ready;
- intelligence/events: not ready;
- market structure: not ready;
- historical outcomes: not ready;
- hard-rule arbiter: not ready.

Therefore `decision_ready` is false in Phase 3.

This prevents later code from treating correct symbol resolution as sufficient evidence for a BUY/SELL/WAIT decision.

## BSE Ltd fail-closed checks

The context builder resolves the profile's exact primary listing and then verifies:

- listing is `NSE:BSE`;
- canonical ISIN is `INE118H01025`;
- issuer CIN is `L67120MH2005PLC155188`.

If `NSE:BSE` is ever mapped to another ISIN/CIN, context construction fails instead of silently analysing the wrong company.

Phase 3 does not invent a `BSE:BSE` self-listing. If a future verified source establishes a new listing, it may be hydrated as another listing of the same ISIN.

## Validation

Targeted Phase 3 contract suite:

`agent/tests/test_tradebrain_hydration_context.py`

Isolated validation result before commit:

**15 passed**

Coverage includes:

- official-domain validation;
- verified-confidence enforcement;
- explicit sanitized-row schema;
- exact ISIN cross-exchange merge;
- issuer/name conflict rejection;
- duplicate-source corroboration;
- absence-is-not-delisting behavior;
- canonical BSE Ltd ISIN/CIN/NSE symbol;
- no invented BSE-exchange listing;
- advisory-only policy propagation;
- incomplete decision-readiness envelope;
- attached provenance/evidence;
- wrong-ISIN fail-closed behavior;
- immutable Phase 3 context records.

Full upstream Vibe CI is still not claimed PASS because the phase PRs intentionally target the previous TradeBrain phase branch rather than `main`.

## Still not built

- automatic NSE/BSE network security-master collectors;
- raw source archival/download hashing;
- persistence into DuckDB or another TradeBrain store;
- corporate announcement/event resolution through the identity index;
- live/historical BSE price context;
- market breadth/regime context;
- multi-timeframe structure;
- Crash Guard;
- historical analogue/outcome engine;
- hard-rule arbiter integration;
- DAY/SWING candidate generation;
- broker execution gating or Kite;
- frontend/API exposure.

## Next phase

Phase 4 should connect **read-only BSE market data and company-event evidence** to this canonical subject, preserving provenance and freshness. It should not yet generate autonomous orders.
