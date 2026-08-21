# TradeBrain + BSE Integration — Implementation Status

Persistent resume point. Read with `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`, phase notes, and the actual branch diff before changing code.

## Current state

- Current phase: **Phase 8 — DAY/SWING advisory transaction-cost economics**
- Working branch: `tradebrain-phase8-advisory-costs`
- Parent: `tradebrain-phase7-controlled-learning`
- Upstream baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- TradeBrain trading/broker/frontend behavior changed: **NO**
- Phase 7 targeted tests: **37 passed**
- Phase 7 Desktop Windows GitHub Actions: **PASSED**, run `32517034012`
- Revised Phase 8 DAY/SWING targeted tests: **15 passed**
- Resident-persona/data-credential separation tests: **3 passed**
- Phase 8 total targeted tests: **18 passed**
- Combined Phase 7 + Phase 8 targeted validation: **55 passed**
- Phase 8 repository CI: **pending until the committed PR workflow is observed**

## Completed through Phase 7

- [x] Additive `tradebrain_bse` advisory-only profile.
- [x] Canonical Company/Issuer -> ISIN -> exchange-listing identity and strict resolution.
- [x] Verified provenance, point-in-time identity hydration, market-data and official intelligence contracts.
- [x] Single-snapshot no-lookahead market structure and provisional Crash Guard.
- [x] Deterministic plan/outcome replay with TP/SL ambiguity handling, MAE/MFE and DAY 15:15 boundary.
- [x] Controlled Champion/Challenger research governance with OOS/walk-forward gates and no automatic promotion.

## Completed in revised Phase 8

- [x] DAY advisory cost path supports LONG and SHORT.
- [x] SWING advisory cost path remains LONG-only.
- [x] DAY and same-day SWING exits use intraday charge semantics.
- [x] Overnight SWING uses delivery charge semantics and DP debit when enabled.
- [x] Target trader persona is explicitly **resident individual** through canonical `resident_advisory.py`; non-resident fee profiles cannot replace it in the BSE target path.
- [x] Intraday STT sell-side and stamp-duty buy-side placement modeled for LONG and SHORT.
- [x] Delivery bilateral STT, buy stamp duty, exchange/SEBI/GST and DP modeled.
- [x] Slippage is explicit/versioned and reflected in execution prices rather than double-counted as a fee.
- [x] LONG and DAY SHORT break-even / requested-net-target solvers verify the paise/tick result.
- [x] Auto-square-off/call-and-trade charge is explicit and only applied when requested.
- [x] Current built-in Zerodha charge snapshot is source-dated and refuses historical backfill before its first verified date.
- [x] Immutable `AdviceCostedPlanSnapshot` binds Phase-6 setup SHA to exact position, charge schedule, brokerage profile, and slippage lineage.
- [x] Only resolved TP-first/SL-first outcomes receive realized net R; ambiguous/neither/data-insufficient paths remain uncosted.
- [x] Costed Crash cases rebind unchanged Crash labels to the exact costed setup lineage.
- [x] NRI Zerodha/Kite credentials may be used only as read-only backtest/historical/live market-data authentication; the contract stores no secret and credential account type cannot alter resident brokerage/advice semantics.
- [x] Revised Phase 8 deliberately does **not** require MTF or account eligibility to produce DAY/SWING advice.

## Explicitly deferred / do not claim

- [ ] MTF funding economics as an active Phase-8 requirement. User scope is DAY/SWING advice first; MTF can be added later as an optional overlay if needed.
- [ ] Account/product eligibility as a market-advice gate.
- [ ] Real BSE historical cost-complete replay/calibration statistics.
- [ ] Historical broker/statutory charge schedules before the current verified snapshot boundary.
- [ ] Fill-level multi-order reconstruction.
- [ ] Income-tax/TDS modeling inside transaction-cost R.
- [ ] Candidate generation.
- [ ] Relative-market/index stress context.
- [ ] Authoritative hard-rule arbiter.
- [ ] Final BSE guidance layer.
- [ ] Kite integration or broker-write path.
- [ ] TradeBrain live execution.

## Hard boundaries

- `main` is not the development target for unreviewed TradeBrain work.
- Preserve upstream Vibe capabilities; no big-bang rewrite.
- Never commit credentials/API keys/broker tokens/private local databases.
- Historical evaluation cannot see bars/events or fee schedules unavailable at its decision `as_of`.
- Current fee snapshots must not be silently backfilled into older history.
- DAY hard flat remains 15:15 IST.
- DAY may advise LONG or SHORT; SWING/POSITION remains LONG-only.
- Data API credential account type is separate from target trader persona: an NRI read-only data login must never select NRI fees or restrictions for the resident trader.
- MTF/account restrictions, if modeled later, apply to execution/funding overlays and must not erase otherwise-valid DAY/SWING market advice.
- Crash Guard is a risk gate, never an automatic SHORT generator.
- Hard rules cannot be modified by learning.
- `tradebrain_bse` remains advisory-only and cannot place live orders.

## Next intended phase

**Phase 9 — BSE relative-market context**

Add point-in-time broad-market/index context only where it measurably improves BSE decisions, preserve exact source/timestamp/hash alignment, and route any candidate features through the existing controlled-learning evaluation path.

## Resume instruction

Inspect current branch/commit/PR/CI first. Then read the master spec, phase notes, this status file, and the actual `agent/src/tradebrain/` diff. Do not reintroduce MTF as a prerequisite for DAY/SWING advice unless the owner explicitly changes scope.
