# TradeBrain + BSE Integration — Implementation Status

This file is the short, persistent resume point for humans and coding agents. Read it together with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, `TRADEBRAIN_PHASE0_BASELINE.md`, the latest phase note, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 3 — verified India identity hydration + BSE decision-context foundation**
- Current working branch: `tradebrain-phase3-hydration-context`
- Parent phase branch: `tradebrain-phase2-identity`
- Parent integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe package version: `0.1.14`
- Trading behavior changed by TradeBrain so far: **NO — TradeBrain remains outside existing Vibe runtime decision/order paths**
- Broker/execution behavior changed by TradeBrain so far: **NO**
- Frontend behavior changed by TradeBrain so far: **NO**
- Phase 1 targeted tests: **10 PASSED**
- Phase 2 targeted tests: **12 PASSED**
- Phase 3 targeted tests: **15 PASSED in isolated validation**
- Full upstream Vibe CI: **PENDING / NOT CLAIMED PASS**

## Completed

- [x] Fork/bootstrap/master specification established.
- [x] Phase 0 baseline / architecture / safety checkpoint established.
- [x] Phase 1 opt-in `tradebrain_bse` policy foundation implemented.
- [x] Phase 2 issuer -> canonical ISIN security -> NSE/BSE listing identity model implemented.
- [x] Phase 2 exact resolver and Vibe evidence/provenance bridge implemented.
- [x] Phase 3 branch created from the exact Phase 2 commit.
- [x] Verified source authority boundary implemented for NSE/BSE official domains plus future local verified storage.
- [x] Canonical sanitized security-master row contract implemented; raw column guessing is intentionally excluded.
- [x] Hydrator merges observations only by checksum-valid ISIN.
- [x] Conflicting issuer/security/listing identity facts fail closed.
- [x] Multiple official observations can corroborate one exact listing while preserving separate provenance.
- [x] Missing from a source snapshot is not treated as a delisting fact.
- [x] BSE Ltd verified bootstrap identity established from official NSE-hosted sources.
- [x] BSE Ltd canonical guard: `INE118H01025` / CIN `L67120MH2005PLC155188` / `NSE:BSE`.
- [x] BSE Ltd Vibe market-data code resolves to `BSE.NS`.
- [x] Phase 3 does not invent a `BSE:BSE` listing.
- [x] BSE decision-context foundation created with identity ready and all downstream decision layers explicitly not ready.
- [x] `decision_ready` remains false until market data, intelligence, structure, historical outcomes and hard-rule arbiter are supplied.
- [x] Phase 3 targeted validation executed: **15 passed**.
- [x] `TRADEBRAIN_PHASE3_HYDRATION_CONTEXT.md` records architecture, official bootstrap evidence, limitations and next step.

## Validation / integration still pending

- [ ] Obtain a real full upstream test/CI run; do not label upstream tests PASS until actually observed.
- [ ] Confirm Phase 3 imports against a complete clean checkout/package install, not only isolated contract validation.
- [ ] Do not claim the Phase 1 profile structurally blocks broker writes; it is still not wired into Vibe's live/order registry.
- [ ] Do not claim automatic NSE/BSE network security-master ingestion; Phase 3 accepts sanitized verified rows/snapshots.
- [ ] Do not claim identity persistence; no DuckDB migration has occurred.
- [ ] Do not claim corporate announcements/events are identity-resolved yet.
- [ ] Do not claim BSE market data, structure, Crash Guard, historical outcomes or final guidance are implemented yet.

## Hard boundaries — do not silently change

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream Vibe capabilities unless the master specification explicitly justifies an override.
- No big-bang rewrite.
- No credentials, API keys, broker tokens or private local databases in Git.
- Exchange symbol != canonical security identity.
- ISIN is the cross-exchange security identity for the Indian-security layer.
- Never merge different ISINs because names look similar.
- Never infer an exchange from an unqualified bare symbol inside the strict resolver.
- Missing from a source snapshot does not prove delisting.
- Official identity authority must remain traceable to provenance.
- Correct identity alone is not a trading decision.
- BSE final guidance remains evidence-driven, not `indicator -> BUY/SELL`.
- AI is context/reasoning, not deterministic market data or hard-rule authority.
- DAY flat-by-15:15 IST remains immutable.
- SWING/POSITION remains long-only and MTF-funded under the current policy.
- Retired L1/L2/L3 rescue averaging must not return.
- Crash Guard blocks/risk-gates; it does not itself create a short setup.
- Hard rules are never silently optimized away.
- Normal Vibe-Trading behavior remains available outside the custom profile.

## Next intended engineering phase

**Phase 4 — read-only BSE market-data + company-event context**

Preferred sequence:

1. attach historical/live read-only market observations to canonical `NSE:BSE` / `INE118H01025`;
2. reuse Vibe's India/Yahoo/broker data interfaces rather than replace them;
3. enforce source timestamp/freshness and symbol/ISIN binding;
4. add official NSE company-announcement/corporate-action evidence behind the same identity;
5. assemble a richer BSE context envelope;
6. still do not generate live orders.

Market structure, Crash Guard and historical outcome learning should follow only after the data/event envelope is reliable.

## Resume instruction

For a new chat/agent:

1. inspect the current GitHub branch and latest commits;
2. read the master specification;
3. read `TRADEBRAIN_PHASE0_BASELINE.md`;
4. read `TRADEBRAIN_PHASE2_IDENTITY.md`;
5. read `TRADEBRAIN_PHASE3_HYDRATION_CONTEXT.md`;
6. read this file;
7. inspect `agent/src/tradebrain/profile.py`;
8. inspect `agent/src/tradebrain/identity.py`;
9. inspect `agent/src/tradebrain/hydration.py`;
10. inspect `agent/src/tradebrain/bse_context.py`;
11. inspect Phase 1/2/3 tests and draft PRs;
12. verify implemented vs pending features before making claims;
13. continue with Phase 4 without bypassing the identity/provenance boundary.
