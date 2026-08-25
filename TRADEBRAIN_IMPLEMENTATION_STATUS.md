# TradeBrain + BSE Integration — Implementation Status

Canonical status for the BSE TradeBrain profile. Read with `TRADEBRAIN_ARCHITECTURE.md`, `TRADEBRAIN_OPERATIONS.md`, PR #11 and the actual code/tests.

## Current state

- Working branch: `codex/complete-vibe-trading`
- Consolidated PR: **#11**, base `main`
- Upstream Vibe baseline: `HKUDS/Vibe-Trading@1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe version: `0.1.14`
- Target trader persona: **resident individual**
- Optional Zerodha/Kite credential: **read-only market-data authentication only**
- TradeBrain advisory-only state: **YES**
- Broker/order writes: **NO**
- Automatic challenger promotion: **NO**
- SWING SHORT: **prohibited**
- Core BSE backend, validation framework and Command Center: implemented on the working branch
- PR CI: must be fully green before merge

## Implemented core

- [x] Additive `tradebrain_bse` profile without replacing Vibe's core platform.
- [x] Reuse of Vibe market-data loaders, India-equity/backtest infrastructure, Strategy Store/SDM, governance ledger, FastAPI and React shell.
- [x] Company/issuer -> ISIN -> exchange-listing identity and exact BSE Ltd guard.
- [x] Provenance, identity hydration, market-data and official-intelligence contracts.
- [x] No-lookahead multi-timeframe structure and provisional Crash Guard.
- [x] DAY LONG/SHORT; fresh-entry cutoff 15:10 IST; hard-flat 15:15 IST.
- [x] SWING LONG-only with `CASH_DELIVERY_OR_OPTIONAL_MTF`; `mtf_required=False`.
- [x] Crash Guard is a LONG risk gate and cannot create a SHORT signal.
- [x] Resident DAY/SWING transaction-cost economics and net-R overlay.
- [x] Deterministic TP/SL replay, MAE/MFE and Crash TP/FP/FN/TN accounting.
- [x] Controlled Champion/Challenger evaluation with chronological OOS/walk-forward gates.
- [x] Human-only promotion backed by Vibe's governance ledger.
- [x] Relative-market context remains research-only until deliberately promoted.
- [x] Hard-rule arbiter with fail-closed ALLOW / BLOCKED / EXIT_REQUIRED / DATA_INSUFFICIENT states.
- [x] Structure-derived candidate geometry remains a proposal until evidence and hard-rule gates pass.
- [x] Final plan-specific advisory composer with categorical confidence and hash-addressed guidance.
- [x] BSE Command Center at `/tradebrain/bse`.
- [x] Manual and live-shadow evidence journals outside the repository.
- [x] MARKET_ACTIVE / DAY_EXIT_WINDOW / AFTER_MARKET / OFF_HOURS operating modes.
- [x] Fail-closed verified NSE exchange-calendar contract.
- [x] Validation-readiness contract for real history, OOS, walk-forward, no-lookahead, costs, live data and shadow evidence.
- [x] Optional Zerodha Kite read-only quote/history/WebSocket boundary with exact BSE Ltd identity guard.
- [x] Kite/profile raw environment access centralized in the Vibe config layer.

## Runtime/evidence gates

These require real external inputs and cannot be honestly completed by source code alone.

- [ ] Supply real `KITE_API_KEY` and current `KITE_ACCESS_TOKEN` outside Git and verify the read-only connection.
- [ ] Supply/refresh a source-audited current NSE trading-calendar snapshot.
- [ ] Perform real BSE Ltd historical backfill from the selected production source.
- [ ] Run the historical data-integrity audit on that real backfill.
- [ ] Produce cost-complete OOS/walk-forward/no-lookahead calibration evidence on untouched real history.
- [ ] Collect live read-only shadow observations across real market sessions.
- [ ] Review empirical Champion/Challenger evidence manually before any promotion.
- [ ] Merge PR #11 into `main` only after final audit and green CI.

## Not claimed or enabled

- Proven profitability.
- Learned/final BSE thresholds without real validation evidence.
- Automatic selection of one plan merely because it backtests best.
- Relative-market features as promoted decision authority.
- Broker/order writes or automated live execution.
- Automatic challenger promotion.
- API key/token storage in Git.
- AI/UI/history override of hard rules.

## Hard boundaries

- Target trader remains a resident individual; read-only broker credentials cannot alter resident economics or policy.
- DAY is LONG/SHORT within hard rules; no fresh DAY entry at/after 15:10 IST; flat by 15:15 IST.
- SWING is LONG-only. MTF is optional, not required.
- Every candidate requires valid entry/target/stop geometry.
- Crash Guard is a risk gate, never an automatic SHORT generator.
- AI, UI, history, relative-market features and research tooling cannot override hard rules.
- Learning cannot silently mutate hard rules or auto-promote a challenger.
- TradeBrain remains advisory-only and cannot place live orders.
- Missing or invalid exchange/data evidence fails closed instead of being guessed.

## Next verification

Fix any PR #11 CI regression, run the full repository suite, then move to real runtime evidence: BSE history/audit, OOS/walk-forward calibration, Kite read-only authentication and live shadow collection.
