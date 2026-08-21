# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 10 — hard-rule arbiter + final advisory composition**
- Working branch: `tradebrain-phase10-final-guidance`
- Parent: `tradebrain-phase9-relative-market`
- Parent commit: `fe4687a227b95d7db92b3723c4d5ae292910a8cc`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- Target trader persona: **resident individual**
- NRI Zerodha/Kite credential, if used: **read-only market-data authentication only**
- TradeBrain broker/live execution behavior changed: **NO**
- Phase 7 targeted tests: **37 passed**
- Phase 7 Desktop Windows CI: **PASSED**, run `32517034012`
- Phase 8 targeted tests: **18 passed**
- Phase 8 Desktop Windows CI: **PASSED**, run `32524596840`
- Phase 9 targeted tests: **18 passed**
- Phase 9 Desktop Windows CI: **PASSED**, run `32525813721`
- Updated profile boundary tests: **10 passed**
- Phase 10 targeted tests: **29 passed**
- Phase 7 + updated profile + Phase 10 isolated validation: **76 passed**
- Phase 10 repository CI: **pending until committed PR workflow is observed**

## Completed through Phase 9

- [x] Additive advisory-only `tradebrain_bse` profile.
- [x] Company/issuer -> ISIN -> exchange-listing identity and exact BSE Ltd guard.
- [x] Provenance, identity hydration, market data and official-intelligence contracts.
- [x] No-lookahead multi-timeframe structure and provisional Crash Guard.
- [x] Deterministic TP/SL historical replay, MAE/MFE and Crash TP/FP/FN/TN accounting.
- [x] Controlled Champion/Challenger governance, OOS/walk-forward and human-only promotion.
- [x] Resident DAY/SWING source-dated transaction-cost economics and net R overlay.
- [x] Resident target persona separated from optional NRI read-only data credentials.
- [x] Point-in-time NIFTY 50 relative-market context with source/timestamp/prefix hashing.
- [x] Relative-market features remain research-only until deliberately promoted.

## Completed in Phase 10

- [x] Canonical Swing funding policy corrected to `CASH_DELIVERY_OR_OPTIONAL_MTF`; `mtf_required=False`.
- [x] DAY fresh-entry cutoff made explicit at **15:10 IST**; hard flat remains **15:15 IST**.
- [x] `target_trader_persona="resident_individual"` embedded in immutable profile.
- [x] Authoritative deterministic hard-rule arbiter added.
- [x] Hard-rule outcomes: ALLOW / BLOCKED / EXIT_REQUIRED / DATA_INSUFFICIENT.
- [x] Exact identity, advisory-only state, retired-logic state and geometry enforced.
- [x] DAY LONG/SHORT policy enforced independently from Crash Guard.
- [x] SWING SHORT is hard-blocked; SWING LONG remains permitted subject to other rules.
- [x] Severe Crash Guard blocks DAY/SWING LONG where configured but never creates a SHORT.
- [x] Structure-derived candidate geometry proposals added; proposal != verdict.
- [x] Candidate geometry is provisional (`learned=False`) and preserves separate DAY/SWING R:R gates.
- [x] Net-of-cost Phase-7 extension added for net expectancy/profit-factor/drawdown/coverage.
- [x] Net challenger comparison requires identical Phase-7 cohort/candidate lineage.
- [x] Net promotion remains human-review-only and requires complete resolved-trade cost coverage plus measured net benefit.
- [x] Final plan-specific advisory composer added.
- [x] Candidate verdict requires hard-rule ALLOW + bound resident costs + real/OOS/walk-forward/no-lookahead/cost-complete history with net expectancy.
- [x] WAIT / DATA_INSUFFICIENT / BLOCKED_BY_HARD_RULE / EXIT_REQUIRED fail-closed paths implemented.
- [x] Relative-market context is displayed as research context but cannot change Phase-10 verdict.
- [x] Confidence is categorical; no fake precision percentage.
- [x] Final guidance remains `advisory_only=True`, `auto_execution=False` and hash-addressed.
- [x] Phase 10 exact isolated validation: **29 passed** plus **10** updated profile tests and **37** Phase-7 regressions = **76 passed**.

## Explicitly deferred / do not claim

- [ ] Automatic selection/ranking of one proposal among multiple valid plan geometries.
- [ ] Real BSE cost-complete OOS/walk-forward calibration results proving any current provisional thresholds.
- [ ] Relative-market features as promoted decision authority.
- [ ] Production Kite historical/live adapter.
- [ ] API key/token storage in Git.
- [ ] BSE Command Center/API presentation layer.
- [ ] Broker/order writes or live execution.
- [ ] Generic Vibe order-registry structural blocking by the TradeBrain profile.
- [ ] `main` integration/merge.

## Hard boundaries

- `main` remains untouched by unreviewed TradeBrain work.
- Target trader is resident individual; NRI data credential class cannot alter resident economics/policy.
- DAY LONG/SHORT permitted only inside hard-rule boundaries; no fresh DAY entry at/after 15:10 IST; flat by 15:15 IST.
- SWING is LONG-only. MTF is optional, not required.
- Every candidate requires valid entry/TP/SL geometry.
- Crash Guard is a risk gate, never an automatic SHORT generator.
- AI, UI, history, relative-market features and research skills cannot override hard rules.
- Learning cannot silently modify hard rules or auto-promote a challenger.
- Final guidance cannot become a candidate verdict without resident cost economics and validated historical reliability.
- TradeBrain remains advisory-only and cannot place live orders.

## Next intended phase

**Phase 11 — read-only BSE Command Center / API presentation**

Expose the Phase-10 backend as a presentation contract and integrate a BSE-specific read-only view into Vibe's existing FastAPI/React application. The UI must render backend verdicts/lineage and must not invent signals, place orders, or bypass the hard-rule arbiter.

## Resume instruction

Inspect branch/commit/PR/CI first. Then read master spec, phase notes, status and actual diff. Continue from the latest green phase. Do not reintroduce MTF as a Swing prerequisite or allow NRI data credentials to alter resident advisory semantics.
