# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, `TRADEBRAIN_PHASE0_BASELINE.md`, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 1 — `tradebrain_bse` profile foundation**
- Current working branch: `tradebrain-phase1-profile`
- Parent phase branch: `tradebrain-phase0-baseline`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO — profile is not wired into existing Vibe runtime paths yet**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**
- Phase 1 targeted tests: **10 PASSED in an isolated Python validation using the exact committed Phase 1 module/test contents**
- Full upstream Vibe CI: **PENDING / NOT CLAIMED PASS**

## Completed

- [x] User fork established: `ramguptakrl/Vibe-Trading`.
- [x] Upstream fork confirmed synchronized at the frozen baseline before customization.
- [x] `tradebrain-bootstrap` created.
- [x] Canonical 2026-08-21 TradeBrain/Vibe reframing specification committed.
- [x] `tradebrain-phase0-baseline` created from `tradebrain-bootstrap`.
- [x] Baseline architecture/safety audit documented in `TRADEBRAIN_PHASE0_BASELINE.md`.
- [x] Existing Vibe India, research, backtest, governance and safety systems selected for reuse instead of wholesale replacement.
- [x] `tradebrain-phase1-profile` created from the Phase 0 checkpoint.
- [x] Additive `agent/src/tradebrain/` namespace designed so imports do not mutate upstream runtime state.
- [x] Minimal `tradebrain_bse` policy contract implemented.
- [x] Explicit opt-in resolver uses `VIBE_TRADING_PROFILE=tradebrain_bse`; absent/unknown values keep the custom profile OFF.
- [x] Policy contract encodes advisory-only, auto-execution OFF, BSE Ltd / `NSE:BSE`, DAY 15:15 IST cutoff, DAY long/short allowed, SWING long-only + MTF funding, AI no-hard-rule override, and retired L1/L2/L3/rescue averaging disabled.
- [x] Phase 1 regression tests authored for default-OFF behavior, exact opt-in, immutable policy values and hard boundaries.
- [x] Targeted Phase 1 contract tests executed in an isolated Python environment: **10 passed**.
- [x] Draft PR #1 opened from `tradebrain-phase1-profile` to `tradebrain-phase0-baseline` for review/check visibility; it must not be merged automatically.

## Validation still pending

- [ ] Obtain a real baseline/full upstream test or CI run; do not label upstream tests PASS until actually observed.
- [ ] Confirm the full repository package/import context through upstream CI or a clean checkout of the complete repository.
- [ ] The upstream `CI` workflow targets pull requests to `main`, so the Phase 1 -> Phase 0 safety PR does not trigger that full workflow by design.
- [ ] Do not claim the profile structurally blocks broker writes yet: Phase 1 defines the policy boundary but deliberately does not wire it into Vibe's existing live/order registry.

## Hard boundaries — do not silently change

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream capabilities unless the master spec explicitly justifies an override.
- No big-bang rewrite.
- No credentials or private local databases in Git.
- BSE final guidance remains evidence-driven, not `indicator -> BUY/SELL`.
- AI is context/reasoning, not the deterministic market-data source or hard-rule authority.
- DAY flat-by-15:15 IST is immutable under the current policy.
- SWING/POSITION is currently long-only and MTF-funded.
- Retired L1/L2/L3 rescue averaging must not return to active logic.
- Crash Guard blocks/risk-gates where designated; it does not automatically create a short setup.
- Hard rules are never silently optimized away by backtesting/learning.
- Normal Vibe-Trading behavior must remain available outside the custom profile.
- Phase 1 profile code must remain additive until narrow integration points are explicitly designed and tested.

## Next intended engineering phase

**Phase 2 — India identity / provenance bridge design**

Goal: reuse Vibe's platform while adding TradeBrain's stronger Indian security/entity identity concepts (company -> canonical security/ISIN -> exchange listings) and provenance boundaries without copying the old application wholesale.

Before Phase 2 changes production paths, choose narrow interfaces for identity lookup and evidence provenance. Do not jump directly into Kite, indicators, Crash Guard porting, UI redesign, TradeBrain database migration, or live execution.

## Resume instruction

For a new chat/agent:

1. Inspect the current GitHub branch and latest commits.
2. Read `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`.
3. Read `TRADEBRAIN_PHASE0_BASELINE.md`.
4. Read this file.
5. Inspect `agent/src/tradebrain/profile.py` and `agent/tests/test_tradebrain_bse_profile.py`.
6. Inspect draft PR #1 and any check results without assuming mergeability means correctness.
7. Verify what is actually implemented and what has actually passed tests before claiming a feature exists.
8. Continue from the unchecked validation items and the next phase, preserving hard boundaries.
