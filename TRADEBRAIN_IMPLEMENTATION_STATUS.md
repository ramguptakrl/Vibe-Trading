# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, `TRADEBRAIN_PHASE0_BASELINE.md`, the latest phase note, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 2 — India identity / provenance bridge**
- Current working branch: `tradebrain-phase2-identity`
- Parent phase branch: `tradebrain-phase1-profile`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO — custom profile/identity code is not wired into existing Vibe runtime decision paths yet**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**
- Phase 1 targeted tests: **10 PASSED**
- Phase 2 targeted tests: **12 PASSED in isolated validation using the exact Phase 2 module/test contents**
- Full upstream Vibe CI: **PENDING / NOT CLAIMED PASS**

## Completed

- [x] User fork established: `ramguptakrl/Vibe-Trading`.
- [x] Upstream fork frozen at the recorded baseline before customization.
- [x] `tradebrain-bootstrap` created with the canonical reframing specification.
- [x] Phase 0 baseline / architecture / safety checkpoint created.
- [x] Phase 1 additive `tradebrain_bse` profile foundation created.
- [x] `tradebrain_bse` remains opt-in and normal Vibe behavior remains available.
- [x] Phase 1 hard policy contract encodes advisory-only, auto-execution OFF, DAY 15:15 IST cutoff, DAY long/short, SWING long-only + MTF, AI no-hard-rule override, and retired L1/L2/L3/rescue averaging disabled.
- [x] Draft PR #1 records Phase 1 against the Phase 0 checkpoint.
- [x] Phase 2 branch created from the validated Phase 1 branch.
- [x] Vibe generic `Entity` / `Security` models reviewed and selected for reuse.
- [x] Vibe India broker/Yahoo symbol conventions reviewed and selected for reuse.
- [x] Vibe `EvidenceInput` provenance fields reviewed and selected for reuse.
- [x] Strict TradeBrain India identity layer implemented under `agent/src/tradebrain/identity.py`.
- [x] ISIN normalization validates structure + checksum and rejects placeholders/malformed IDs.
- [x] Issuer -> canonical ISIN security -> NSE/BSE listing hierarchy implemented.
- [x] Exact resolver supports ISIN, exchange+symbol, exchange security ID, and explicitly qualified project symbols.
- [x] Resolver deliberately refuses fuzzy company/symbol guessing.
- [x] Conflict detection prevents one exact listing from silently remapping to another ISIN.
- [x] Adapters preserve canonical ISIN as Vibe `Security.instrument_id` across multiple exchange listings.
- [x] Immutable identity provenance receipt implemented with timezone-aware retrieval time and optional raw artifact SHA-256.
- [x] Provenance adapter reuses Vibe's existing `EvidenceInput` rather than creating another evidence ledger.
- [x] `TRADEBRAIN_PHASE2_IDENTITY.md` documents the architecture, reuse decisions and unbuilt gaps.
- [x] Targeted Phase 2 validation executed: **12 passed**.

## Validation / integration still pending

- [ ] Obtain a real baseline/full upstream test or CI run; do not label upstream tests PASS until actually observed.
- [ ] Confirm Phase 2 imports in a clean checkout of the complete repository, not only isolated contract validation.
- [ ] Do not claim the profile structurally blocks broker writes yet; the Phase 1 policy is not wired into Vibe's live/order registry.
- [ ] Do not claim Phase 2 identity is persisted yet; no old TradeBrain DuckDB tables were copied or migrated.
- [ ] Do not claim official NSE/BSE security masters are feeding the new index yet.
- [ ] Do not claim corporate events use the new resolver yet.

## Hard boundaries — do not silently change

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream capabilities unless the master spec explicitly justifies an override.
- No big-bang rewrite.
- No credentials, API keys, broker tokens or private local databases in Git.
- Exchange symbol != canonical security identity.
- ISIN is the cross-exchange security identity for this Indian-security layer.
- Never merge different ISINs because company names look similar.
- Never infer an exchange from an unqualified bare symbol inside the strict identity resolver.
- Missing from the latest source does not by itself prove delisting.
- BSE final guidance remains evidence-driven, not `indicator -> BUY/SELL`.
- AI is context/reasoning, not the deterministic market-data source or hard-rule authority.
- DAY flat-by-15:15 IST is immutable under the current policy.
- SWING/POSITION is currently long-only and MTF-funded.
- Retired L1/L2/L3 rescue averaging must not return to active logic.
- Crash Guard blocks/risk-gates where designated; it does not automatically create a short setup.
- Hard rules are never silently optimized away by backtesting/learning.
- Normal Vibe-Trading behavior must remain available outside the custom profile.

## Next intended engineering phase

**Phase 3 — verified India identity hydration + BSE decision-context foundation**

Goal: connect the strict Phase 2 identity contract to narrow, verified inputs without importing the old TradeBrain application wholesale, then begin the BSE-specific context layer on top of canonical identity.

Preferred sequence:

1. define a repository/loader interface that can hydrate verified identity bundles;
2. add a safe adapter for sanitized/official NSE/BSE security-master rows or future local TradeBrain storage;
3. keep raw-source provenance attached;
4. prove BSE Ltd resolves canonically before using it in BSE-specific decision logic;
5. only then begin market-structure / historical-context integration.

Do not jump directly into automatic execution, broad UI redesign, or a destructive database migration.

## Resume instruction

For a new chat/agent:

1. Inspect the current GitHub branch and latest commits.
2. Read `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`.
3. Read `TRADEBRAIN_PHASE0_BASELINE.md`.
4. Read `TRADEBRAIN_PHASE2_IDENTITY.md`.
5. Read this file.
6. Inspect `agent/src/tradebrain/profile.py`.
7. Inspect `agent/src/tradebrain/identity.py`.
8. Inspect `agent/tests/test_tradebrain_bse_profile.py` and `agent/tests/test_tradebrain_identity.py`.
9. Inspect draft PRs/check results without assuming mergeability means correctness.
10. Verify what is actually implemented and what has actually passed tests before claiming a feature exists.
