# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 7 — controlled learning / champion–challenger foundation**
- Working branch: `tradebrain-phase7-controlled-learning`
- Parent: `tradebrain-phase6-outcomes-replay`
- Integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- TradeBrain trading/broker/frontend behavior changed: **NO**
- Phase 1 tests: **10 passed**
- Phase 2 tests: **12 passed**
- Phase 3 tests: **15 passed**
- Phase 4 tests: **18 passed**
- Phase 5 tests: **28 passed**
- Phase 5 Desktop Windows GitHub Actions: **PASSED**, run `32510807307`
- Phase 6 tests: **44 passed**
- Phase 6 Desktop Windows GitHub Actions: **PASSED**, run `32514348171`
- Phase 7 tests: **37 passed in isolated validation**
- Phase 7 repository CI: **pending until the committed PR workflow is observed**

## Completed through Phase 6

- [x] Additive opt-in `tradebrain_bse` profile; normal Vibe remains available outside it.
- [x] Advisory-only / auto-execution-off policy contract.
- [x] Company/issuer -> canonical ISIN -> NSE/BSE listing identity model and strict resolver.
- [x] BSE Ltd canonical guard: `INE118H01025`, `NSE:BSE`, `BSE.NS`.
- [x] Verified provenance/identity hydration contracts and Vibe EvidenceInput bridge.
- [x] Read-only Phase-4 bridge reusing Vibe `india_equity` market-data loaders.
- [x] Explicit market-data freshness, OHLCV validation and frame SHA-256.
- [x] Official NSE/BSE issuer-intelligence point-in-time contract.
- [x] Single-snapshot no-lookahead multi-timeframe structure.
- [x] EMA/volatility/volume/swing/S-R/range/trend/regime context.
- [x] Observed-window high separated from true ATH semantics.
- [x] Deterministic provisional Crash Guard with `DATA_INSUFFICIENT/NORMAL/ELEVATED/SEVERE`.
- [x] Severe Crash Guard may block fresh longs but never creates a SHORT.
- [x] Immutable Phase-6 BSE plan snapshots with decision-time identity/policy/data/structure/intelligence/Crash lineage.
- [x] Deterministic TP-first / SL-first / neither / ambiguous / insufficient outcome replay.
- [x] MAE/MFE, gross R, terminal R, time-to-TP/SL and DAY 15:15 horizon enforcement.
- [x] Provisional Crash replay TP/FP/FN/TN/excluded machinery with explicit false-positive rate.
- [x] Historical-outcome readiness can advance; hard-rule arbiter/final decision remain false.
- [x] Phase-6 Windows packaging workflow completed successfully.

## Completed in Phase 7

- [x] Branch created from exact Phase-6 commit `58163b463c61b8c63fd5e0b3465b8738f8883f1c`.
- [x] Versioned Champion/Challenger research definitions added.
- [x] Candidate parameters recursively frozen; candidate SHA cannot drift through nested mutation.
- [x] Challengers require explicit parent version and explicit change summary.
- [x] `hard_rule_changes` are rejected at candidate construction.
- [x] Phase-7 candidates remain `research_only=True` and `learned=False`.
- [x] Phase-6-derived learning cases commit all scoring-relevant setup/outcome/Crash fields to SHA-256.
- [x] Learning-case integrity is revalidated before cohort construction/evaluation.
- [x] Cohorts are deterministic/fingerprinted and classify real/synthetic + ordinary/severe evidence.
- [x] Candidate predictions bind exact candidate SHA to exact case SHA and are revalidated before scoring.
- [x] Identical-dataset A/B comparison enforced; different case set/split/fingerprint fails closed.
- [x] Metrics include gross expectancy/hit rate/profit factor/drawdown/MAE/MFE/timing/frequency and Crash false positives/recall/precision.
- [x] Regime and subperiod slices exposed.
- [x] Chronological, non-overlapping walk-forward folds and OOS test-only evaluation added.
- [x] Default promotion gate requires OOS, walk-forward, real history, no-lookahead, cost completeness, ordinary+severe coverage, sample/regime/subperiod coverage and a measured challenger benefit.
- [x] Passing the gate yields only `ELIGIBLE_FOR_HUMAN_REVIEW`; no automatic promotion exists.
- [x] Manual approval creates an audit record but does not mutate runtime policy.
- [x] Manual record permanently states `hard_rules_modified=false` and `auto_execution_enabled=false`.
- [x] Promotion assessment/manual records reuse Vibe's hash-chained governance ledger.
- [x] Vibe SDM bridge creates a governed BENCHING/IN_VALIDATION research artifact only.
- [x] Nested recursively frozen candidate parameters are thawed safely into JSON for the Vibe SDM artifact bridge.
- [x] Generic SDM IC/Sharpe thresholds are not misrepresented as BSE promotion proof.
- [x] Phase-7 targeted isolated validation: **37 passed**.

## Not yet implemented / do not claim

- [ ] Automatic NSE/BSE identity or corporate-event network ingestion.
- [ ] Identity/event/outcome/learning persistence or DuckDB migration.
- [ ] Real BSE historical replay/calibration statistics.
- [ ] A measured real-world Crash Guard false-positive rate.
- [ ] Any Phase-5/6/7 provisional parameter as learned/promoted production truth.
- [ ] BSE-specific decay thresholds based on real evaluation history.
- [ ] Exchange-calendar-aware SWING completeness across holidays/special sessions.
- [ ] Relative-market/index stress context.
- [ ] MTF funding/interest/broker-cost engine or cost-complete net R:R.
- [ ] Candidate generation from live/current BSE context.
- [ ] Authoritative hard-rule arbiter.
- [ ] Final BSE guidance.
- [ ] Kite integration.
- [ ] Structural broker-write blocking in generic Vibe registries.
- [ ] TradeBrain live execution.

## Hard boundaries

- Never develop unreviewed TradeBrain work directly on `main`.
- Preserve upstream Vibe capabilities; no big-bang rewrite.
- Never commit credentials/API keys/broker tokens/private local databases.
- Exchange symbol != canonical security identity; ISIN remains the Indian cross-exchange security key where applicable.
- Never fuzzy-merge different ISINs or infer an exchange from an unqualified symbol.
- Official facts must remain traceable to provenance.
- Unknown/stale market data cannot become decision-ready.
- Historical evaluation cannot see bars/events unavailable at decision `as_of`.
- Phase-5/6/7 records must preserve and revalidate exact hashes/lineage.
- Soft structure/Crash/replay/learning parameters remain provisional until deliberate controlled promotion.
- Learning can never modify DAY 15:15, SWING-long-only, advisory-only, broker/exchange or other hard owner rules.
- Crash Guard is a risk gate, never an automatic SHORT generator.
- `DATA_INSUFFICIENT` is never equivalent to `NORMAL`.
- Retired L1/L2/L3/rescue averaging must not return.
- Costs/net profitability cannot be claimed before the verified cost engine exists.
- Passing a promotion evidence gate is not promotion; human review/approval is mandatory.
- AI remains context/reasoning and cannot override hard rules.
- `tradebrain_bse` remains advisory-only and cannot place live orders.

## Next intended phase

**Phase 8 — exact MTF position + broker cost engine**

Preferred sequence:
1. define a versioned cost-source/provenance contract;
2. model Zerodha MTF funded amount from actual applicable margin rather than assuming leverage;
3. model brokerage, exchange/statutory taxes, pledge/unpledge, DP and MTF interest using verified effective-date rules;
4. calculate exact calendar holding days and MTF interest;
5. compute gross -> net break-even and net R:R for DAY/SWING contexts where applicable;
6. fail closed when a charge/margin rule is missing or stale;
7. attach cost-model version/hash to Phase-6 plan/outcome records;
8. rerun controlled Phase-7 comparison only after cost completeness is real.

Relative-market context, hard-rule arbitration, final guidance, UI and broader TradeBrain expansion remain later layers.

## Resume instruction

Inspect current branch/commit/PR/CI first. Then read the master spec, Phase 0/2/3/4/5/6/7 notes, this file, and the actual `agent/src/tradebrain/` diff. Verify implemented vs pending claims before continuing. Do not bypass identity, provenance, freshness, no-lookahead, immutable replay lineage, champion/challenger governance, cost-completeness or advisory-only boundaries.
