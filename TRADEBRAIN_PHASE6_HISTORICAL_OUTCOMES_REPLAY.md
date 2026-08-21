# TradeBrain Phase 6 — BSE Historical Outcomes + Replay Foundation

## Purpose

Phase 6 gives the BSE profile deterministic memory of what happened **after an already-defined plan**. It does not create entries, targets, stops, broker orders, fills, or final BUY/SELL guidance.

Flow:

    Phase-5 point-in-time context
        -> immutable plan snapshot
        -> explicitly linked future replay bars
        -> TP-first / SL-first / neither / ambiguous / insufficient
        -> MAE / MFE / timing / gross-R observations
        -> provisional Crash Guard replay labels + false-positive accounting

The Phase-5 Windows workflow for commit `6eef17df4e309d4ab63161002b20c75ae0c6389a` completed successfully before this phase was started.

## Existing Vibe capability reused

Vibe already contains Trade Journal and Shadow Account tooling with useful patterns: frozen data contracts, FIFO trade pairing, deterministic arithmetic and reproducible backtest/attribution outputs. Phase 6 follows those patterns rather than inventing LLM-based outcome truth.

However, Trade Journal and Shadow Account are **not** used as the authority for BSE plan TP/SL outcomes. Journal fills describe actual user trades; Shadow Account studies behavior/counterfactuals. BSE plan outcome truth is a separate point-in-time research contract.

## New modules

- `agent/src/tradebrain/outcome_models.py`: frozen plan/replay/outcome contracts, hashing and shared validation.
- `agent/src/tradebrain/outcome_builders.py`: immutable BSE plan snapshots and replay-batch construction.
- `agent/src/tradebrain/outcome_evaluator.py`: deterministic no-lookahead TP/SL evaluation.
- `agent/src/tradebrain/historical_outcomes.py`: stable public facade.
- `agent/src/tradebrain/replay.py`: provisional Crash Guard replay/false-positive machinery.
- `agent/src/tradebrain/outcome_context.py`: Phase-6 readiness composition.

## Immutable decision-time plan snapshot

`BSEPlanSnapshot` freezes the exact plan and the evidence state that existed when the plan was defined. It includes:

- setup ID and schema version;
- decision timestamp, mode and direction;
- canonical BSE identity/listing and Vibe symbol;
- native interval;
- caller-supplied entry, target and stop;
- gross risk/reward geometry;
- explicit `net_rr=None` and `cost_model_version=None` until the MTF/cost engine exists;
- decision reference price;
- advisory/auto-execution policy state;
- policy SHA-256;
- Phase-4 market source + frame SHA-256;
- Phase-5 structure boundary/config versions + structure SHA-256;
- Phase-5 Crash Guard state/reasons/config + SHA-256;
- official-intelligence as-of/event count + SHA-256;
- known decision-time data gaps;
- final snapshot SHA-256.

The snapshot does **not** generate trade geometry. A caller must provide entry/TP/SL. Phase 6 validates the geometry and freezes it.

Plan snapshots are tamper-evident. Replay recomputes the plan payload hash; modifying a frozen field while retaining the original digest fails closed.

## BSE mode rules preserved

DAY:
- LONG or SHORT may be recorded when policy allows;
- intraday replay only;
- outcome horizon is capped by the current hard flat time, 15:15 Asia/Kolkata.

SWING/POSITION:
- remains LONG-only;
- SHORT plan snapshots are rejected;
- MTF remains a funding mechanism, not rescue averaging.

No retired L1/L2/L3/rescue-cycle logic returns.

## Replay lineage and no-lookahead

`ReplayBarBatch` carries exact identity, listing, interval, market-source lineage, the decision source-frame hash, its own deterministic bar hash, retrieval time, data-as-of and declared gaps.

Replay must match the plan's identity/source/interval lineage. OHLCV geometry, ordering, finite values and non-negative volume are revalidated. Hash mismatch fails closed.

Only complete bars after the decision boundary are eligible. With a 5-minute decision at 10:00, the already-completed 09:55–10:00 bar is not reused; a bar beginning at 10:00 may become future evidence only when it is complete.

For DAY mode, a 15:10–15:15 bar may be considered; a bar starting at 15:15 is outside the allowed DAY horizon. A decision at or after the hard flat boundary is `DATA_INSUFFICIENT` for DAY replay.

## Outcome states

- `TP_FIRST`
- `SL_FIRST`
- `NEITHER`
- `AMBIGUOUS_SAME_BAR`
- `DATA_INSUFFICIENT`

If a single OHLC bar contains both TP and SL, Phase 6 does **not** guess intrabar order. The result stays `AMBIGUOUS_SAME_BAR` until finer evidence exists.

A known replay-price gap can hide a TP or SL. Therefore a later observed hit cannot override that uncertainty; categorical outcome becomes `DATA_INSUFFICIENT` while observed excursions remain available.

DAY intraday holes are mechanically detectable. SWING replay does not pretend overnight/weekend gaps are missing data until an exchange-calendar-aware layer exists; explicit declared gaps are honored.

Decision-context gaps are preserved separately from replay-price gaps. A known context limitation does not automatically change the mechanical TP/SL ordering if the future price path itself is complete.

## MAE / MFE / timing

The evaluator records:
- maximum adverse excursion in R;
- maximum favorable excursion in R;
- gross realized R for TP/SL;
- terminal mark R for unresolved `NEITHER` observations;
- time to target and stop.

With OHLC bars, exact intrabar hit seconds are unknowable. Timing therefore uses the **bar completion timestamp**, not fabricated precision.

Costs are intentionally not applied yet. Phase 6 must not claim net profitability, net R:R or MTF economics.

## Crash Guard replay

`replay.py` adds a provisional research label for testing Phase-5 Crash Guard instead of silently promoting its thresholds.

Default label contract:

    version = phase6-provisional-label-v1
    learned = false
    horizon = 6 native bars
    stress = future adverse low <= -5% from decision reference price

This is a declared research label, **not universal market truth and not a learned threshold**.

Each case records whether Phase-5 Crash Guard predicted `SEVERE`, whether the declared future stress label occurred, and one of:
- TRUE_POSITIVE
- FALSE_POSITIVE
- FALSE_NEGATIVE
- TRUE_NEGATIVE
- EXCLUDED_DATA_INSUFFICIENT

Crash Guard `DATA_INSUFFICIENT`, replay gaps and incomplete label horizons are excluded from confusion denominators instead of being counted as correct normal periods.

Summaries expose precision, recall and false-positive rate with explicit counts. Phase 6 never mutates Phase-5 Crash Guard configuration.

Synthetic fixtures validate the machinery only. **No real BSE false-positive rate or calibrated Crash Guard performance is claimed in Phase 6.**

## Readiness

Phase-6 composition may advance only `historical_outcomes_ready` when the Phase-5 context, exact plan snapshot and replay outcome are usable. `hard_rule_arbiter_ready` remains false, therefore `decision_ready` remains false.

## Validation

Isolated Phase-6 targeted validation: **44 passed** after the implementation was split into focused modules. The test suite covers hashing/tamper detection, identity/source binding, LONG/SHORT mechanics, SWING-long-only policy, DAY 15:15 horizon, same-bar ambiguity, MAE/MFE, bar-completion timing, data gaps, replay hashes, Crash Guard TP/FP/FN/TN accounting, incomplete-horizon exclusion, no mutation and readiness.

Phase-6 GitHub CI must still be observed on the committed PR before claiming repository-level Phase-6 integration success.

## Deliberately out of scope

No real historical BSE calibration dataset, no champion promotion, no walk-forward/OOS study, no relative-market index context, no exchange-calendar SWING completeness model, no MTF cost engine, no candidate generator, no authoritative hard-rule arbiter, no final guidance, no Kite integration, no broker/order changes, no UI/API changes and no persistence migration.

## Next phase

**Phase 7 — controlled BSE historical replay/calibration + champion-challenger foundation.**

It should run the Phase-6 machinery over real point-in-time BSE history, include severe and ordinary periods, measure false positives and data coverage, preserve champion A, create challenger B only with explicit versioned changes, compare on identical data, and forbid promotion without later OOS/walk-forward/cost/regime review.
