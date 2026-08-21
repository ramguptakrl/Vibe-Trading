# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt` and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 0 — Baseline / integration freeze**
- Current working branch: `tradebrain-phase0-baseline`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**

## Completed

- [x] User fork established: `ramguptakrl/Vibe-Trading`.
- [x] Upstream fork confirmed synchronized at the frozen baseline before customization.
- [x] `tradebrain-bootstrap` created.
- [x] Canonical 2026-08-21 TradeBrain/Vibe reframing specification committed.
- [x] `tradebrain-phase0-baseline` created from `tradebrain-bootstrap`.
- [x] Baseline architecture/safety audit documented in `TRADEBRAIN_PHASE0_BASELINE.md`.
- [x] Existing Vibe India, research, backtest, governance and safety systems selected for reuse instead of wholesale replacement.

## Pending before/with Phase 1

- [ ] Obtain a real baseline test/CI run; do not label tests PASS until actually observed.
- [ ] Design the minimal `tradebrain_bse` profile contract.
- [ ] Add profile scaffolding without changing normal Vibe behavior.
- [ ] Add tests proving profile OFF preserves upstream/default behavior.
- [ ] Add tests proving BSE profile is advisory-only and cannot bypass designated hard rules.

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

## Next intended engineering phase

**Phase 1 — `tradebrain_bse` profile foundation**

Goal: introduce the smallest possible configuration/profile boundary that allows future BSE-specific logic to be added without globally rewriting Vibe-Trading.

Phase 1 should initially establish only policy/configuration boundaries and regression tests. Do not jump directly into Kite, indicators, Crash Guard porting, UI redesign, TradeBrain database migration, or live execution.

## Resume instruction

For a new chat/agent:

1. Inspect the current GitHub branch and latest commits.
2. Read `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`.
3. Read `TRADEBRAIN_PHASE0_BASELINE.md`.
4. Read this file.
5. Verify what is actually implemented in code before claiming a feature exists.
6. Continue from the unchecked items above, preserving hard boundaries.
