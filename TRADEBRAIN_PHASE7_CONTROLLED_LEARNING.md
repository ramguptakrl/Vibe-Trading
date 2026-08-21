# TradeBrain Phase 7 — Controlled Learning / Champion–Challenger Foundation

## Purpose

Phase 7 adds research governance around the deterministic Phase-6 historical-outcome and Crash replay records. It is deliberately a **controlled-learning foundation**, not a claim that BSE parameters are already learned or calibrated on production-quality history.

The invariant is:

    immutable Phase-6 truth
        -> fingerprinted research cohort
        -> Champion A / Challenger B definitions
        -> identical-data evaluation
        -> chronological walk-forward
        -> evidence-completeness promotion gate
        -> human review only
        -> tamper-evident audit record

No Phase-7 code changes a hard rule, live broker path, order path, final BSE verdict, or production parameter automatically.

## Existing Vibe machinery reused

Phase 7 keeps Vibe's Strategy Development Manager as research orchestration rather than recreating it. Vibe already provides artifact registration, lifecycle/status tracking, model-governance fields, and decay-monitoring infrastructure. TradeBrain adds the BSE-specific evidence contract around that machinery because generic IC/Sharpe thresholds are diagnostics, not proof that a BSE challenger deserves promotion.

Vibe's existing hash-chained governance ledger is reused for promotion assessments and explicit manual approval records. TradeBrain does not create a weaker parallel audit log.

## New modules

### `agent/src/tradebrain/learning.py`

Provides:

- recursively immutable `CandidateVersion` definitions;
- `CHAMPION` and `CHALLENGER` research roles;
- explicit parent version and change summary for challengers;
- a hard prohibition on `hard_rule_changes`;
- research-only / `learned=False` enforcement;
- immutable Phase-6-derived `LearningCase` records with SHA-256 integrity revalidation;
- real-vs-synthetic and ordinary-vs-severe provenance labels;
- order-stable cohort fingerprints;
- candidate predictions bound to both candidate SHA and case SHA;
- deterministic evaluation metrics;
- regime and subperiod slices;
- chronological non-overlapping walk-forward folds;
- walk-forward summaries.

The case hash commits to every Phase-6-derived field that Phase-7 scoring may consume, including outcome state, realized gross R, MAE/MFE, time-to-target, terminal mark, cost-model state, Crash replay label, source hashes, direction and decision timestamp. If an embedded record drifts after case creation, cohort/evaluation construction fails closed.

### `agent/src/tradebrain/promotion.py`

Provides:

- identical-dataset Champion/Challenger comparison;
- explicit benefit and tradeoff reporting;
- an evidence-completeness `PromotionPolicy`;
- default blockers for missing OOS evidence, walk-forward evidence, real history, no-lookahead verification, costs, ordinary/severe coverage, regime/subperiod coverage and sample size;
- a `no_measured_challenger_benefit` blocker;
- only two automatic states: `HOLD_CHAMPION` and `ELIGIBLE_FOR_HUMAN_REVIEW`;
- explicit manual approval records;
- append-only promotion audit helpers using Vibe's governance ledger.

Passing the evidence gate **does not promote the challenger**. It only makes the challenger eligible for deliberate human review. `approve_challenger(...)` creates an auditable approval record but does not mutate runtime configuration.

### `agent/src/tradebrain/sdm_bridge.py`

Builds a governed Vibe `Artifact` for TradeBrain candidates so the existing SDM/strategy store can coordinate research history. The bridge creates a `BENCHING` / `IN_VALIDATION` / Tier-2-significant research artifact with explicit intended use and limitations.

It does not:

- register or activate the artifact automatically;
- map BSE outcome metrics into unrelated IC/Sharpe fields;
- mark a candidate approved;
- grant execution authority.

## Metrics compared

Current Phase-7 evaluation exposes plan and risk-gate evidence including:

- TP-first / SL-first / neither / ambiguous / insufficient counts;
- gross hit rate and gross expectancy R;
- profit factor;
- max drawdown in R;
- mean MAE/MFE;
- median time-to-target;
- terminal-mark R;
- admitted/blocked case counts and trade-frequency context;
- blocked TP-first and blocked SL-first long plans;
- Crash TP/FP/FN/TN/excluded counts;
- Crash precision, recall and false-positive rate;
- data coverage and cost coverage;
- regime slices;
- subperiod slices.

Gross outcome metrics are not represented as net profitability. The dedicated MTF/cost engine is still absent.

## Walk-forward rules

Walk-forward folds are built in chronological order. Train and test case IDs cannot overlap, and the test period must begin strictly after the train period ends. Only the future test set is evaluated as OOS for each fold.

Phase 7 does not tune a candidate inside these helpers. A future research runner may use the train portion to construct a challenger, but evaluation/promotion evidence must remain attached to the untouched future test portion.

## Default promotion gate

The default `phase7-governance-v1` gate requires at minimum:

- OOS comparison;
- real history only;
- no-lookahead verification;
- complete cost-model coverage;
- both ordinary and severe sessions;
- at least 30 OOS cases;
- at least 3 walk-forward folds;
- at least 2 regimes;
- at least 2 subperiods;
- at least one measured challenger benefit.

These are evidence-completeness requirements, not a promise of profitability. They intentionally make promotion impossible while Phase 8 cost economics are missing.

## Deliberate promotion / audit

A challenger that clears the evidence gate becomes only `ELIGIBLE_FOR_HUMAN_REVIEW`. A separate explicit approval record must supply:

- approver;
- timezone-aware approval time;
- review note;
- exact challenger SHA;
- exact comparison SHA;
- exact assessment SHA.

The record always states:

    hard_rules_modified = false
    auto_execution_enabled = false

Promotion assessment and approval records can be appended to Vibe's existing hash-chained governance ledger. A broken ledger refuses extension.

## SDM integration boundary

Vibe SDM remains useful for INGEST -> EXTRACT -> IMPLEMENT -> EVALUATE -> MONITOR orchestration and its model-governance store. For `tradebrain_bse`, however:

- generic SDM thresholds do not prove BSE profitability;
- Alpha Zoo/Shadow Account outputs remain hypotheses/diagnostics;
- BSE-specific Phase-6/7 evidence governs BSE parameter promotion;
- hard rules remain outside the learnable set;
- SDM decay scanning is not fed fabricated IC/Sharpe values from BSE outcome R.

A later adapter may persist BSE-specific evaluation history alongside SDM metadata after real replay data exists. This phase does not invent fake decay statistics.

## Validation

Phase-7 targeted isolated validation: **37 passed**.

The isolated harness tests the committed Phase-7 contracts with faithful stubs for the Vibe governance-ledger and strategy-store interfaces. Repository-level packaging/CI must be observed separately after the Phase-7 commit; it must not be conflated with the 37 behavioral tests.

## What Phase 7 does NOT claim

- No real BSE historical calibration dataset has been run yet.
- No real-world learned Crash Guard threshold exists yet.
- No support/resistance/timeframe parameter has been promoted.
- No cost-complete net profitability result exists.
- No candidate is automatically promoted.
- No hard owner rule can be changed by learning.
- No final BSE guidance is generated.
- No live order is placed.
- No Kite integration is added.

## Next phase

Phase 8 should implement exact MTF/broker economics before any challenger can satisfy the default promotion gate:

- Zerodha MTF funding/interest;
- brokerage/statutory/pledge/DP costs from verified current rules;
- exact holding days;
- gross-to-net R:R and break-even;
- explicit cost-model version/provenance;
- no timeless hard-coded charge assumptions.

After Phase 8, real BSE replay cohorts can be evaluated with net economics and become eligible for a meaningful champion–challenger review.
