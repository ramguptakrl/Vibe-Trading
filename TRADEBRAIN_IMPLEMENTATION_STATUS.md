# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes, `TRADEBRAIN_PHASE11_OPERATIONS.md`, and the actual branch/PR before changing code.

## Current state

- Current phase: **Phase 11 — operational/presentation completion**
- Working branch: `codex/complete-vibe-trading`
- Consolidated PR: **#11**, base `main`
- Upstream Vibe baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- Target trader persona: **resident individual**
- Optional NRI Zerodha/Kite credential: **read-only market-data authentication only**
- TradeBrain broker/live execution behavior changed: **NO**
- TradeBrain advisory-only state: **YES**
- Automatic challenger promotion: **NO**
- SWING SHORT: **prohibited**
- Phase 0–10 backend: implemented
- Phase 11 operational/UI framework: implemented on the working branch
- Consolidated PR CI: must be green before integration is called complete

## Implemented backend/core

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
- [x] Canonical Swing funding policy `CASH_DELIVERY_OR_OPTIONAL_MTF`; `mtf_required=False`.
- [x] DAY fresh-entry cutoff **15:10 IST**; DAY hard-flat **15:15 IST**.
- [x] Deterministic hard-rule arbiter with ALLOW / BLOCKED / EXIT_REQUIRED / DATA_INSUFFICIENT.
- [x] DAY LONG/SHORT policy enforced independently from Crash Guard.
- [x] SWING SHORT hard-blocked.
- [x] Crash Guard acts as a risk gate and cannot create a SHORT signal.
- [x] Structure-derived candidate geometry proposals remain proposals, not verdicts.
- [x] Net-of-cost historical evidence and promotion comparison gates.
- [x] Final plan-specific advisory composer.
- [x] Final candidate verdict requires hard-rule ALLOW + resident costs + real/OOS/walk-forward/no-lookahead/cost-complete historical reliability.
- [x] WAIT / DATA_INSUFFICIENT / BLOCKED_BY_HARD_RULE / EXIT_REQUIRED fail-closed paths.
- [x] Confidence remains categorical; no fake precision percentage.
- [x] Final guidance remains hash-addressed, advisory-only and non-executing.

## Implemented Phase 11 operational layer

- [x] BSE Command Center React route at `/tradebrain/bse`.
- [x] Command Center renders backend state and does not invent a verdict.
- [x] Authenticated TradeBrain BSE FastAPI routes.
- [x] Manual `I took this trade` journal with original advisory id + guidance SHA-256 binding.
- [x] Manual trade close workflow with actual entry/exit, quantity, costs, outcome and realized P&L.
- [x] Live-shadow advisory journal and resolution workflow.
- [x] Runtime journal storage outside the Git repository.
- [x] Manual/shadow journal rejects malformed hashes, invalid geometry and SWING SHORT.
- [x] Deterministic MARKET_ACTIVE / DAY_EXIT_WINDOW / AFTER_MARKET / OFF_HOURS modes.
- [x] No fresh DAY entry at/after 15:10; DAY exit priority through the 15:15 hard-flat boundary.
- [x] After-market/off-hours permissions for replay and challenger research.
- [x] Broker writes, production mutation and automatic promotion disabled in every operating mode.
- [x] Fail-closed verified NSE exchange-calendar contract; weekdays alone are never treated as proof of an open session.
- [x] Validation-readiness contract for real history, OOS, walk-forward, no-lookahead, costs, live data and shadow evidence.
- [x] Optional Zerodha Kite **read-only** adapter boundary.
- [x] Kite exact `NSE:BSE` resolution with BSE Ltd ISIN guard where the provider supplies ISIN.
- [x] Kite read-only quote, historical-candle and market-WebSocket helpers.
- [x] Kite adapter exposes no order/position/GTT mutation methods.
- [x] Kite API key/token status is represented as booleans only; secrets are not returned by the Command Center API.
- [x] Phase 11 operator/setup documentation.
- [x] Phase 11 safety/persistence tests added.

## Runtime/evidence gates — cannot be honestly completed in source code alone

These are not missing architecture. They remain blocked until their real external inputs exist and pass validation.

- [ ] Install/use the optional Kite SDK in the production runtime.
- [ ] Supply real `KITE_API_KEY` and current `KITE_ACCESS_TOKEN` outside Git.
- [ ] Supply/refresh a source-audited current NSE trading-calendar snapshot.
- [ ] Perform real BSE Ltd historical backfill from the selected production source.
- [ ] Run the historical data-integrity audit on the real backfill.
- [ ] Produce real cost-complete OOS/walk-forward/no-lookahead calibration evidence.
- [ ] Collect live read-only shadow observations across real market sessions.
- [ ] Review empirical Champion/Challenger evidence manually before any promotion.
- [ ] Merge PR #11 into `main` only after review and green CI.

## Explicitly not claimed / not enabled

- [ ] Proven profitability.
- [ ] Learned/final BSE thresholds where evidence is still provisional.
- [ ] Automatic selection/ranking of one proposal among multiple valid plan geometries.
- [ ] Relative-market features as promoted decision authority.
- [ ] Broker/order writes or automated live execution.
- [ ] Automatic challenger promotion.
- [ ] API key/token storage in Git.
- [ ] AI/UI/history override of hard rules.

## Hard boundaries

- Target trader is resident individual; optional NRI data credentials cannot alter resident economics/policy.
- DAY LONG/SHORT permitted only inside hard-rule boundaries; no fresh DAY entry at/after 15:10 IST; flat by 15:15 IST.
- SWING is LONG-only. MTF is optional, not required.
- Every candidate requires valid entry/TP/SL geometry.
- Crash Guard is a risk gate, never an automatic SHORT generator.
- AI, UI, history, relative-market features and research skills cannot override hard rules.
- Learning cannot silently modify hard rules or auto-promote a challenger.
- Final guidance cannot become a candidate verdict without resident cost economics and validated historical reliability.
- TradeBrain remains advisory-only and cannot place live orders.
- Missing/invalid/out-of-range NSE calendar evidence fails closed instead of guessing a live session.

## Resume instruction

Inspect PR #11, its latest head and CI first. Fix all regressions before merge. After green integration, the next work is **runtime evidence acquisition** (Kite read-only authentication, real BSE history/audit, calibration and live shadow collection), not another speculative backend rewrite.
