# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 9 — point-in-time relative-market context**
- Working branch: `tradebrain-phase9-relative-market`
- Parent: `tradebrain-phase8-advisory-costs`
- Phase 8 parent commit: `55f7602b609d6424d81e1d032091be827582c651`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- TradeBrain trading/broker behavior changed: **NO**
- Target trader persona: **resident individual**
- NRI Zerodha/Kite credential, if used: **read-only market data only**; cannot select NRI fees/restrictions/advice rules
- Phase 7 targeted tests: **37 passed**
- Phase 7 Desktop Windows GitHub Actions: **PASSED**, run `32517034012`
- Phase 8 targeted tests: **18 passed**
- Phase 7 + Phase 8 combined isolated validation: **55 passed**
- Phase 8 Desktop Windows GitHub Actions: **PASSED**, run `32524596840`
- Phase 9 targeted isolated tests: **18 passed**
- Phase 9 repository CI: **pending until committed PR workflow is observed**

## Completed through Phase 8

- [x] Additive `tradebrain_bse` advisory-only profile.
- [x] Canonical Company/Issuer -> ISIN -> exchange-listing identity and strict resolution.
- [x] Verified provenance, point-in-time identity hydration, market-data and official intelligence contracts.
- [x] Single-snapshot no-lookahead market structure and provisional Crash Guard.
- [x] Deterministic TP/SL historical replay with MAE/MFE, ambiguity handling and DAY 15:15 boundary.
- [x] Controlled Champion/Challenger governance with OOS/walk-forward and no automatic promotion.
- [x] Resident DAY LONG/SHORT and SWING LONG-only transaction-cost economics.
- [x] Resident-persona boundary separated from optional NRI read-only data credentials.
- [x] Current fee snapshots are source-dated and cannot be silently backfilled into older history.
- [x] Cost overlays preserve immutable Phase-6 truth and exact lineage.

## Completed in Phase 9

- [x] Exact broad-market benchmark descriptor for NIFTY 50 (`^NSEI`) added.
- [x] Benchmark data reuses Vibe's existing `india_equity` loader resolver.
- [x] Exact benchmark-symbol requirement; no fuzzy/silent index substitution.
- [x] Same interval required between BSE and benchmark.
- [x] Same resolved market-data source required by default; cross-source comparison requires explicit opt-out.
- [x] Equivalent timezone offsets normalize to the same UTC instant before alignment.
- [x] BSE/benchmark bars are filtered to `timestamp <= as_of`.
- [x] Point-in-time prefix SHA-256 values prevent future appended bars from rewriting earlier context lineage.
- [x] Exact aligned-timestamp SHA-256 recorded.
- [x] Stale/unknown BSE or benchmark freshness fails closed.
- [x] Minimum aligned-bar and alignment-ratio requirements fail closed.
- [x] Relative measurements include 1-bar/short/medium returns, benchmark drawdown, correlation and beta.
- [x] Phase-9 config is explicitly provisional (`learned=False`).
- [x] Relative-market context cannot generate trade direction/verdict or override Crash Guard/hard rules.
- [x] Research feature payload carries context lineage for later Champion/Challenger experiments.
- [x] Future-shock regression proves bars after an earlier `as_of` cannot alter earlier relative measurements.
- [x] Phase 9 targeted isolated validation: **18 passed**.

## Explicitly deferred / do not claim

- [ ] Real BSE historical calibration proving relative-market features add value.
- [ ] Any learned/promoted relative-market threshold or weight.
- [ ] Automatic corporate-event network ingestion/persistence.
- [ ] Historical fee schedules before the verified Phase-8 boundary.
- [ ] Exchange-calendar-aware SWING completeness across special sessions/holidays.
- [ ] Authoritative final hard-rule arbiter.
- [ ] Final BSE guidance composition.
- [ ] BSE Command Center UI.
- [ ] Kite integration as a production data adapter.
- [ ] Broker/order write path or live execution.
- [ ] MTF as a requirement for SWING advice.

## Hard boundaries

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream Vibe capabilities; no big-bang rewrite.
- Never commit credentials/API keys/broker tokens/private local databases.
- Target trader is resident individual; NRI data-login metadata cannot alter resident brokerage/advice semantics.
- DAY may advise LONG or SHORT and remains hard-flat by 15:15 IST.
- SWING/POSITION remains LONG-only.
- Historical evaluation cannot see bars/events/features unavailable at its `as_of`.
- Relative-market context is soft/research context until controlled evaluation proves value.
- Crash Guard remains a risk gate and never auto-creates SHORT.
- Learning cannot modify hard rules or auto-promote a challenger.
- `tradebrain_bse` remains advisory-only.

## Next intended phase

**Phase 10 — BSE Command Center / final advisory presentation foundation**

Build the presentation/composition layer around already-verified identity, market data, intelligence, structure, Crash Guard, historical outcomes, costs and relative context. Keep final decision readiness fail-closed until the authoritative hard-rule arbiter is explicitly implemented.

## Resume instruction

Inspect current branch/commit/PR/CI first. Then read the master spec, phase notes, this status file, and actual TradeBrain diff. Do not let index context, NRI data credentials, AI, or UI bypass resident policy/hard-rule boundaries.
