# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, `TRADEBRAIN_PHASE0_BASELINE.md`, the latest phase note, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 5 — BSE market structure + Crash Guard foundation**
- Current working branch: `tradebrain-phase5-structure-crashguard`
- Parent phase branch: `tradebrain-phase4-data-intelligence`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO — TradeBrain remains outside existing Vibe runtime decision/order paths**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**
- Phase 1 targeted tests: **10 PASSED**
- Phase 2 targeted tests: **12 PASSED**
- Phase 3 targeted tests: **15 PASSED**
- Phase 4 targeted tests: **18 PASSED**
- Phase 5 targeted tests: **28 PASSED in isolated validation**
- Full upstream Vibe CI: **NOT CLAIMED PASS unless a completed workflow is explicitly recorded**

## Completed

- [x] Fork/bootstrap/master specification established.
- [x] Phase 0 baseline / architecture / safety checkpoint established.
- [x] Phase 1 opt-in `tradebrain_bse` policy foundation implemented.
- [x] Phase 2 issuer -> canonical ISIN security -> NSE/BSE listing identity model implemented.
- [x] Phase 2 exact resolver and Vibe evidence/provenance bridge implemented.
- [x] Phase 3 verified identity hydration contract implemented.
- [x] BSE Ltd canonical guard established: `INE118H01025` / CIN `L67120MH2005PLC155188` / `NSE:BSE` / `BSE.NS`.
- [x] Phase 3 decision-context envelope created with identity ready and downstream layers explicitly not ready.
- [x] Phase 4 read-only Vibe `india_equity` market-data bridge implemented.
- [x] Phase 4 official NSE/BSE intelligence contract and point-in-time filtering implemented.
- [x] Phase 4 can advance only market-data and intelligence readiness.
- [x] Phase 5 branch created from the exact Phase 4 checkpoint.
- [x] Phase 5 consumes only the immutable Phase-4 market snapshot; it creates no second price fetch path.
- [x] Complete native-bar boundary enforced at explicit timezone-aware `as_of`.
- [x] Higher-timeframe derivation is no-lookahead, exact-multiple only and excludes incomplete/holey buckets.
- [x] Flexible multi-timeframe structure implemented without imposing one rigid timeframe recipe.
- [x] EMA 20/50/200 context implemented with insufficient-history handling.
- [x] True-range/ATR-style volatility and volume-ratio context implemented.
- [x] Confirmed swing highs/lows require right-side bars to exist by `as_of`.
- [x] Deterministic clustered structural support/resistance implemented.
- [x] Observed-window high/low is separated from true ATH semantics.
- [x] `all_time_high` is exposed only when complete history is explicitly certified.
- [x] 52-week high/low requires at least 252 daily observations.
- [x] Adaptive trend/regime classification implemented.
- [x] Provisional/frozen `StructureConfig` is explicitly `learned=False`.
- [x] Deterministic Crash Guard implemented with DATA_INSUFFICIENT/NORMAL/ELEVATED/SEVERE states.
- [x] Crash Guard uses decline, drawdown, gap, true-range, volume, structural support and multi-timeframe context.
- [x] Crash Guard thresholds are versioned provisional soft parameters, not learned values.
- [x] Severe Crash Guard can block fresh DAY LONG and SWING/MTF LONG.
- [x] Crash Guard never auto-creates a SHORT.
- [x] Crash Guard is forced to the exact native complete-bar boundary recorded by structure.
- [x] Future-shock regression test proves later snapshot bars cannot leak into an earlier Crash Guard evaluation.
- [x] Phase-5 composition can advance only market-structure readiness.
- [x] Historical-outcomes and hard-rule-arbiter readiness remain false.
- [x] `decision_ready` remains false after Phase 5 by design.
- [x] Phase 5 targeted validation executed: **28 passed**.
- [x] `TRADEBRAIN_PHASE5_STRUCTURE_CRASH_GUARD.md` records architecture, semantics, limitations and next step.

## Validation / integration still pending

- [ ] Obtain/record a completed full upstream test or CI run before claiming the whole Vibe repository passes.
- [ ] Confirm Phase 5 imports in a complete clean checkout/package install, not only isolated contract validation.
- [ ] Do not claim the Phase 1 profile structurally blocks broker writes; it is still not wired into Vibe's live/order registry.
- [ ] Do not claim automatic NSE/BSE identity/security-master network ingestion; hydration still consumes sanitized verified snapshots.
- [ ] Do not claim automatic NSE announcement/corporate-action network ingestion; Phase 4 defines the verified source/event contract only.
- [ ] Do not claim identity/event persistence; no DuckDB migration has occurred.
- [ ] Do not claim Phase-5 thresholds are learned, calibrated or promoted.
- [ ] Do not claim false-positive performance has been measured yet.
- [ ] Do not claim relative-market/index stress is included in Crash Guard yet.
- [ ] Do not claim historical outcomes, MTF cost engine, candidate generation, hard-rule arbiter or final guidance are implemented yet.
- [ ] Do not claim Kite is integrated yet.

## Hard boundaries — do not silently change

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream Vibe capabilities unless the master specification explicitly justifies an override.
- No big-bang rewrite.
- No credentials, API keys, broker tokens or private local databases in Git.
- Exchange symbol != canonical security identity.
- ISIN remains the cross-exchange security identity for the Indian-security layer.
- Never merge different ISINs because names look similar.
- Never infer an exchange from an unqualified bare symbol inside the strict resolver.
- Missing from a source snapshot does not prove delisting.
- Official facts must remain traceable to provenance.
- Fresh source check with zero events is different from no source check.
- Market-data freshness thresholds must be explicit; unknown freshness cannot become decision-ready.
- Phase-5 structure must consume the Phase-4 snapshot; do not fetch a parallel BSE price series.
- Historical decisions cannot see bars/events that were not knowable at their `as_of`.
- Do not label an observed-window high as ATH without complete-history certification.
- Structure/level/timeframe/volume/Crash thresholds are soft/adaptive until validated.
- Crash Guard is a risk gate, not a trade signal.
- Severe Crash Guard can block fresh longs; it does not automatically qualify a short.
- `DATA_INSUFFICIENT` must never be treated as `NORMAL`.
- Correct identity + fresh prices + intelligence + structure still do not constitute a trading decision.
- BSE final guidance remains evidence-driven, not `indicator -> BUY/SELL`.
- AI is context/reasoning, not deterministic market data or hard-rule authority.
- DAY flat-by-15:15 IST remains immutable.
- SWING/POSITION remains long-only and MTF-funded under the current policy.
- Retired L1/L2/L3 rescue averaging must not return.
- Hard rules are never silently optimized away.
- Normal Vibe-Trading behavior remains available outside the custom profile.

## Next intended engineering phase

**Phase 6 — BSE plan-specific historical outcomes + replay foundation**

Preferred sequence:

1. define an immutable decision/setup snapshot keyed to identity + source hashes + policy/config versions;
2. evaluate TP-first / SL-first / neither using only bars after the decision timestamp;
3. record MAE, MFE, time-to-target, outcome R and data gaps;
4. separate DAY and SWING/POSITION outcome semantics;
5. preserve Crash Guard/structure/intelligence state as it was known at decision time;
6. create replay fixtures for severe and ordinary sessions;
7. measure false positives before any Crash Guard threshold can become a challenger;
8. keep all learned/promotion changes behind later champion-challenger governance.

MTF economics, relative-market context, hard-rule arbitration and final guidance should be layered only after outcome evidence is trustworthy.

## Resume instruction

For a new chat/agent:

1. inspect the current GitHub branch and latest commits;
2. read the master specification;
3. read `TRADEBRAIN_PHASE0_BASELINE.md`;
4. read `TRADEBRAIN_PHASE2_IDENTITY.md`;
5. read `TRADEBRAIN_PHASE3_HYDRATION_CONTEXT.md`;
6. read `TRADEBRAIN_PHASE4_DATA_INTELLIGENCE.md`;
7. read `TRADEBRAIN_PHASE5_STRUCTURE_CRASH_GUARD.md`;
8. read this file;
9. inspect `agent/src/tradebrain/profile.py`;
10. inspect `identity.py`, `hydration.py`, and `bse_context.py`;
11. inspect `market_data.py`, `intelligence.py`, and `data_intelligence.py`;
12. inspect `structure.py`, `crash_guard.py`, and `structure_context.py`;
13. inspect Phase 1-5 targeted tests and draft PRs/check results;
14. verify implemented vs pending features before making claims;
15. continue with Phase 6 without bypassing identity, provenance, freshness, point-in-time or readiness boundaries.
