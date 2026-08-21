# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, `TRADEBRAIN_PHASE0_BASELINE.md`, the latest phase note, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 4 — read-only BSE market data + official issuer intelligence**
- Current working branch: `tradebrain-phase4-data-intelligence`
- Parent phase branch: `tradebrain-phase3-hydration-context`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO — TradeBrain remains outside existing Vibe runtime decision/order paths**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**
- Phase 1 targeted tests: **10 PASSED**
- Phase 2 targeted tests: **12 PASSED**
- Phase 3 targeted tests: **15 PASSED**
- Phase 4 targeted tests: **18 PASSED in isolated validation**
- Full upstream Vibe CI: **NOT CLAIMED PASS unless a completed workflow is explicitly recorded below**

## Completed

- [x] Fork/bootstrap/master specification established.
- [x] Phase 0 baseline / architecture / safety checkpoint established.
- [x] Phase 1 opt-in `tradebrain_bse` policy foundation implemented.
- [x] Phase 2 issuer -> canonical ISIN security -> NSE/BSE listing identity model implemented.
- [x] Phase 2 exact resolver and Vibe evidence/provenance bridge implemented.
- [x] Phase 3 verified identity hydration contract implemented.
- [x] BSE Ltd canonical guard established: `INE118H01025` / CIN `L67120MH2005PLC155188` / `NSE:BSE` / `BSE.NS`.
- [x] Phase 3 decision-context envelope created with identity ready and downstream layers explicitly not ready.
- [x] Phase 4 branch created from the exact Phase 3 checkpoint.
- [x] Existing Vibe `india_equity` loader registry/fallback chain reviewed and reused rather than replaced.
- [x] Read-only BSE market-data bridge implemented around Vibe `resolve_loader("india_equity")`.
- [x] Exact BSE identity/symbol binding enforced before market data can enter TradeBrain.
- [x] OHLCV timestamps/columns/numeric geometry validated; duplicate/future/invalid bars fail closed.
- [x] Normalized immutable bars receive deterministic SHA-256 provenance.
- [x] Market-data freshness is explicit; `UNKNOWN` or `STALE` cannot mark the layer ready.
- [x] Market-data observations map into Vibe `EvidenceInput` without creating a second evidence ledger.
- [x] Official NSE/BSE issuer-intelligence source contract implemented with HTTPS/domain authority checks.
- [x] Sanitized issuer events require exact ISIN and/or exact exchange+symbol identity.
- [x] Conflicting ISIN/listing facts fail closed; company-name-looking text is never used as identity.
- [x] Point-in-time event filtering excludes events published after `as_of`.
- [x] Fresh official scans with zero matching events are preserved as valid coverage evidence.
- [x] Phase-4 composition advances only `market_data_ready` and `intelligence_ready`; structure/history/hard-rule layers stay false.
- [x] `decision_ready` remains false after Phase 4 by design.
- [x] Phase 4 targeted validation executed: **18 passed**.
- [x] `TRADEBRAIN_PHASE4_DATA_INTELLIGENCE.md` records architecture, reuse decisions, limitations and next step.

## Validation / integration still pending

- [ ] Obtain/record a completed full upstream test or CI run before claiming the whole Vibe repository passes.
- [ ] Confirm Phase 4 imports in a complete clean checkout/package install, not only isolated contract validation.
- [ ] Do not claim the Phase 1 profile structurally blocks broker writes; it is still not wired into Vibe's live/order registry.
- [ ] Do not claim automatic NSE/BSE identity/security-master network ingestion; hydration still consumes sanitized verified snapshots.
- [ ] Do not claim automatic NSE announcement/corporate-action network ingestion; Phase 4 defines the verified source/event contract only.
- [ ] Do not claim identity/event persistence; no DuckDB migration has occurred.
- [ ] Do not claim market structure, Crash Guard, historical outcomes, MTF cost engine or final guidance are implemented yet.
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
- Correct identity + fresh prices + official-event coverage still do not constitute a trading decision.
- BSE final guidance remains evidence-driven, not `indicator -> BUY/SELL`.
- AI is context/reasoning, not deterministic market data or hard-rule authority.
- DAY flat-by-15:15 IST remains immutable.
- SWING/POSITION remains long-only and MTF-funded under the current policy.
- Retired L1/L2/L3 rescue averaging must not return.
- Crash Guard blocks/risk-gates; it does not itself create a short setup.
- Hard rules are never silently optimized away.
- Normal Vibe-Trading behavior remains available outside the custom profile.

## Next intended engineering phase

**Phase 5 — BSE market structure + Crash Guard foundation**

Preferred sequence:

1. consume Phase-4 immutable BSE bars instead of fetching a second price series;
2. derive/validate required timeframes without look-ahead;
3. model trend/regime and major structural support/resistance;
4. add comparable-ATH state;
5. implement Crash Guard as a deterministic risk gate, not a trade signal;
6. prove historical decisions cannot see future bars/events.

Historical outcome learning, MTF economics and final DAY/SWING guidance should follow only after structure/risk inputs are reliable.

## Resume instruction

For a new chat/agent:

1. inspect the current GitHub branch and latest commits;
2. read the master specification;
3. read `TRADEBRAIN_PHASE0_BASELINE.md`;
4. read `TRADEBRAIN_PHASE2_IDENTITY.md`;
5. read `TRADEBRAIN_PHASE3_HYDRATION_CONTEXT.md`;
6. read `TRADEBRAIN_PHASE4_DATA_INTELLIGENCE.md`;
7. read this file;
8. inspect `agent/src/tradebrain/profile.py`;
9. inspect `agent/src/tradebrain/identity.py` and `hydration.py`;
10. inspect `agent/src/tradebrain/bse_context.py`;
11. inspect `agent/src/tradebrain/market_data.py`;
12. inspect `agent/src/tradebrain/intelligence.py`;
13. inspect `agent/src/tradebrain/data_intelligence.py`;
14. inspect Phase 1-4 tests and draft PRs/check results;
15. verify implemented vs pending features before making claims;
16. continue with Phase 5 without bypassing identity, provenance, freshness or point-in-time boundaries.
