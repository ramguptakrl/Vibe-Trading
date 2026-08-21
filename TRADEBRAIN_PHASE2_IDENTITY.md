# TradeBrain Phase 2 — India Identity / Provenance Bridge

## Purpose

Phase 2 adds the identity semantics that the owner's original TradeBrain treated as foundational while reusing Vibe-Trading's existing generic entity and evidence infrastructure.

This phase remains additive. It does not alter Vibe market-data loaders, broker connectors, databases, API routes, frontend behavior, backtest engines, or live execution.

## Vibe capabilities reused

Vibe already has:

- `src.entities.models.Entity` for legal/issuer entities.
- `src.entities.models.Security` for a listed security reference record.
- `Instrument.instrument_id`, which Vibe explicitly allows to be an ISIN.
- India market-data symbol conventions in `backtest/loaders/india_broker_loader.py`:
  - `RELIANCE.NS` -> NSE / RELIANCE
  - `500325.BO` -> BSE / 500325
- `src.goal.models.EvidenceInput` / `EvidenceRecord` carrying source provider, source type, source URI, artifact path/hash, data-as-of, confidence, and trace fields.

These remain the platform primitives. Phase 2 does not fork them.

## Gap Phase 2 fills

The TradeBrain identity rule is stricter than a ticker-centric model:

    Issuer / Company
        -> Canonical Security (ISIN)
            -> Exchange Listing(s)

A symbol is not the security identity. The same ISIN may have an NSE listing and a BSE listing.

Phase 2 adds:

- checksum-validated ISIN normalization;
- exact issuer identity;
- canonical security identity keyed by ISIN;
- NSE/BSE exchange-listing identity;
- explicit Vibe/Yahoo and broker-style symbol forms;
- deterministic exact identity resolution;
- conflict detection;
- adapters back into Vibe's existing `Entity` / `Security` models;
- immutable source-provenance receipts;
- adapter from provenance receipts into Vibe's existing evidence ledger model.

## Exact-resolution policy

Allowed:

- exact ISIN;
- exact `exchange + symbol`;
- exact exchange security ID;
- explicitly exchange-qualified project symbol:
  - `.NS`
  - `.BO`
  - `NSE:<symbol>`
  - `BSE:<symbol>`

Not allowed in this phase:

- fuzzy company-name matching;
- guessing the exchange for a bare symbol;
- merging two securities merely because names look similar;
- accepting placeholders such as `NA` as an identity;
- silently remapping an existing exchange listing to another ISIN.

## ISIN validation

`normalize_isin()`:

1. strips outer whitespace;
2. uppercases;
3. requires ISO-6166-style 12-character structure;
4. verifies the ISIN Luhn check digit.

This intentionally rejects malformed or placeholder IDs before they can become canonical keys.

## Cross-exchange representation

Example identity bundle:

    Issuer: Reliance Industries Limited
    ISIN:   INE002A01018

    Listings:
      NSE:RELIANCE  -> RELIANCE.NS
      BSE:500325    -> 500325.BO

Both Vibe `Security` adapter records use the same `instrument_id=INE002A01018`.

That preserves Vibe compatibility while keeping TradeBrain's cross-exchange identity invariant.

## Provenance bridge

`IdentityProvenance` records:

- source provider;
- source type;
- source URI;
- timezone-aware retrieval timestamp;
- optional data-as-of;
- optional raw artifact path + SHA-256;
- confidence.

Artifact path and SHA-256 are a pair: one cannot be present without the other.

`to_evidence_input()` maps directly supported fields into Vibe's existing `EvidenceInput` rather than creating a second research-evidence database.

Vibe's input model does not expose a caller-supplied `retrieved_at`; therefore the source retrieval timestamp is preserved in namespaced `tradebrain_provenance` metadata inside `assumptions` until a narrower persisted identity/evidence integration is designed.

## What is NOT built yet

- No DuckDB identity tables have been copied from the old TradeBrain.
- No NSE/BSE security-master collector has been connected to this index.
- No automatic hydration from the user's existing local TradeBrain database exists.
- No corporate-event entity linking is wired to this resolver yet.
- No API endpoint or frontend identity UI is added.
- No Kite integration is added.
- No broker write path is affected.
- No fuzzy alias engine is added.

## Validation

Targeted Phase 2 tests cover:

- ISIN normalization and checksum rejection;
- explicit symbol parsing;
- two exchange listings sharing one ISIN;
- mismatched-listing rejection;
- exact listing/project-symbol resolution;
- exact exchange-security-ID resolution;
- refusal to fuzzy-guess;
- conflicting mapping rejection;
- Vibe entity/security adaptation preserving ISIN;
- immutability;
- timezone/hash provenance validation;
- Vibe evidence-model adaptation.

Result in isolated validation using the exact Phase 2 module/test contents:

    12 passed

This is a targeted result only. Full upstream Vibe CI is not claimed PASS.

## Future integration rule

Persistence or collectors should hydrate `IdentityIndex` (or a future repository implementing the same exact-resolution contract) rather than changing the identity semantics.

The intended dependency direction is:

    official source / local TradeBrain store
              |
              v
       verified identity records
              |
              v
         IdentityIndex
              |
         +----+----+
         |         |
         v         v
      Vibe      TradeBrain
     models      BSE brain

Do not make market-data provider tickers the canonical identity key.

## Rollback

Phase 2 is additive under `agent/src/tradebrain/` plus tests/docs. It can be reverted without database migration or state repair.
