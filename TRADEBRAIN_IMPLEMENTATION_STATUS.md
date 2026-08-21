# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 6 — BSE plan-specific historical outcomes + replay foundation**
- Working branch: `tradebrain-phase6-outcomes-replay`
- Parent: `tradebrain-phase5-structure-crashguard`
- Integration branch: `tradebrain-bootstrap`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- TradeBrain trading/broker/frontend behavior changed: **NO**
- Phase 1 tests: **10 passed**
- Phase 2 tests: **12 passed**
- Phase 3 tests: **15 passed**
- Phase 4 tests: **18 passed**
- Phase 5 tests: **28 passed**
- Phase 5 GitHub Actions: **Desktop Windows PASSED**, run `32510807307`
- Phase 6 tests: **44 passed in isolated validation**
- Phase 6 GitHub CI: **pending until the committed PR workflow is observed**

## Completed through Phase 5

- [x] Additive `tradebrain_bse` profile; normal Vibe remains available outside it.
- [x] Advisory-only / auto-execution-off policy contract.
- [x] Company/issuer -> canonical ISIN -> exchange-listing identity model.
- [x] BSE Ltd canonical guard: `INE118H01025`, `NSE:BSE`, `BSE.NS`.
- [x] Verified provenance/identity hydration contracts.
- [x] Read-only Phase-4 bridge reusing Vibe `india_equity` data loaders.
- [x] Explicit market-data freshness, OHLCV validation and frame SHA-256.
- [x] Official NSE/BSE issuer-intelligence point-in-time contract.
- [x] Single-snapshot no-lookahead multi-timeframe structure.
- [x] EMA/volatility/volume/swing/S-R/range/trend/regime context.
- [x] Observed-window high separated from true ATH semantics.
- [x] Deterministic provisional Crash Guard; `DATA_INSUFFICIENT/NORMAL/ELEVATED/SEVERE`.
- [x] Severe Crash Guard may block fresh longs but never creates a SHORT.
- [x] Exact native-bar prefix/hash prevents future-bar leakage into historical Crash Guard evaluation.
- [x] Phase-5 Windows packaging workflow completed successfully.

## Completed in Phase 6

- [x] Branch created from exact Phase-5 commit `6eef17df4e309d4ab63161002b20c75ae0c6389a`.
- [x] Frozen `BSEPlanSnapshot` binds plan geometry to exact identity, policy, Phase-4 market hash, Phase-5 structure/Crash Guard and official-intelligence context.
- [x] Plan snapshot SHA-256 is recomputed before replay; altered history fails closed.
- [x] Phase 6 validates caller-supplied entry/TP/SL but does not generate them.
- [x] DAY LONG/SHORT and SWING LONG-only semantics preserved.
- [x] Costs remain explicitly unknown: `net_rr=None`, no net-profitability claim.
- [x] `ReplayBarBatch` binds future bars to exact identity/source/interval lineage and deterministic frame hash.
- [x] Replay revalidates ascending/unique timestamps and OHLCV geometry.
- [x] Deterministic outcomes: TP-first, SL-first, neither, ambiguous-same-bar, data-insufficient.
- [x] Same-bar TP+SL never receives a guessed intrabar order.
- [x] MAE/MFE, gross R, terminal-mark R and time-to-TP/SL recorded.
- [x] Hit time uses bar completion, not fabricated intrabar seconds.
- [x] DAY replay is capped by hard 15:15 Asia/Kolkata flat time.
- [x] Known replay-price gaps fail closed; decision-context gaps are kept separately.
- [x] SWING overnight completeness is not guessed without exchange-calendar support.
- [x] Provisional Crash Guard replay label + TP/FP/FN/TN/excluded machinery added.
- [x] Crash replay reports precision/recall/false-positive rate with explicit denominators.
- [x] Crash Guard DATA_INSUFFICIENT, incomplete horizons and gapped replay are excluded rather than counted as normal.
- [x] Phase-5 Crash Guard thresholds are never mutated/promoted by Phase 6.
- [x] Phase-6 composition can advance only `historical_outcomes_ready`.
- [x] `hard_rule_arbiter_ready` remains false and `decision_ready` remains false.
- [x] Phase-6 targeted validation: **44 passed**.

## Not yet implemented / do not claim

- [ ] Automatic NSE/BSE identity or corporate-event network ingestion.
- [ ] Identity/event/outcome persistence or DuckDB migration.
- [ ] Real BSE historical replay/calibration statistics.
- [ ] A measured real-world Crash Guard false-positive rate.
- [ ] Phase-5 or Phase-6 provisional thresholds as learned/promoted values.
- [ ] Exchange-calendar-aware SWING completeness across holidays/special sessions.
- [ ] Relative-market/index stress context.
- [ ] MTF funding/interest/broker-cost engine or net R:R.
- [ ] Candidate generation.
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
- Missing from a source snapshot does not prove delisting.
- Official facts must remain traceable to provenance.
- Unknown/stale market data cannot become decision-ready.
- Historical evaluation cannot see bars/events unavailable at its decision `as_of`.
- Phase-5 structure and Phase-6 replay must preserve exact source hashes/lineage.
- A partial observed window must not be called ATH.
- Soft structure/Crash/replay thresholds remain provisional until controlled validation.
- Crash Guard is a risk gate, not a SHORT generator.
- `DATA_INSUFFICIENT` is never equivalent to `NORMAL`.
- DAY hard flat remains 15:15 IST.
- SWING/POSITION remains LONG-only and MTF-funded.
- Retired L1/L2/L3/rescue averaging must not return.
- Costs/net profitability cannot be claimed before the cost engine exists.
- AI remains context/reasoning and cannot override hard rules.
- The `tradebrain_bse` profile remains advisory-only.

## Next intended phase

**Phase 7 — controlled BSE historical replay/calibration + champion-challenger foundation**

Preferred sequence:
1. obtain/construct point-in-time BSE replay windows from the existing verified data path;
2. cover severe **and ordinary** sessions, not one famous crash day;
3. run Phase-6 plan/outcome and Crash replay machinery without look-ahead;
4. report data coverage, excluded cases and false positives explicitly;
5. freeze current parameters as champion A;
6. create versioned challenger B only when a concrete hypothesis exists;
7. replay A/B on identical data and compare expectancy, hit rate, drawdown, MAE/MFE, timing, false positives and regime stability;
8. keep promotion disabled until later OOS/walk-forward/cost/slippage governance is satisfied.

MTF economics, relative-market context, hard-rule arbitration and final guidance remain later layers.

## Resume instruction

Inspect the current branch/commit/PR and CI first. Then read the master spec and Phase 0/2/3/4/5/6 notes, this status file, and the actual `agent/src/tradebrain/` diff. Verify implemented vs pending claims before starting Phase 7. Continue without bypassing identity, provenance, freshness, point-in-time, plan/replay hashing or advisory-only boundaries.
