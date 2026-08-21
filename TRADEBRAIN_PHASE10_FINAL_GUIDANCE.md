# TradeBrain Phase 10 — Hard-Rule Arbiter + Final Advisory Composition

## Goal

Phase 10 closes the deterministic backend decision boundary before any Command Center UI is allowed to render a BSE verdict.

The order is intentional:

`verified evidence -> structure/Crash Guard -> candidate geometry -> hard-rule arbiter -> resident cost economics -> validated historical reliability -> final advisory composition`

No UI, LLM, relative-market feature, research skill, or broker credential may bypass that sequence.

## Canonical resident policy correction

The BSE target trader remains a **resident individual**.

DAY:
- LONG or SHORT;
- no fresh DAY entry at/after 15:10 IST;
- hard flat by 15:15 IST.

SWING/POSITION:
- LONG-only;
- cash/delivery is valid;
- MTF is optional rather than required.

The canonical policy string is `CASH_DELIVERY_OR_OPTIONAL_MTF` and `mtf_required=False`.

An NRI Zerodha/Kite login may still be used only as a read-only market-data credential; it does not alter this policy or resident economics.

## Hard-rule arbiter

`hard_rules.py` is deterministic and fail-closed. It binds one immutable plan request to:

- canonical BSE Ltd identity (`INE118H01025`, `NSE:BSE`);
- profile advisory-only / auto-execution-off state;
- retired rescue architecture remaining disabled;
- valid entry/target/stop geometry;
- DAY long/short permissions;
- DAY 15:10 fresh-entry cutoff and 15:15 hard flat;
- SWING LONG-only policy;
- Crash Guard long blocks.

States:

- `ALLOW`
- `BLOCKED`
- `EXIT_REQUIRED`
- `DATA_INSUFFICIENT`

Severe Crash Guard may block DAY LONG or SWING LONG. It does **not** create or automatically qualify a DAY SHORT.

## Candidate geometry

`candidate_geometry.py` proposes deterministic structure-derived entry/target/stop shapes from confirmed support/resistance. It does not choose a verdict.

The geometry defaults are provisional (`learned=False`). DAY and SWING proposals have separate starting minimum gross R:R requirements. A direction that is permitted by policy is not necessarily proposed on every snapshot; it must also satisfy its current structure/R:R geometry.

No SWING SHORT proposal is ever generated.

## Net-of-cost learning gate

Phase 8 introduced realized `net R`. Phase 7 originally retained gross metrics for research traceability. `net_learning.py` adds the stricter BSE promotion layer:

- reuses all Phase-7 cohort, case SHA, candidate SHA, prediction, OOS and walk-forward integrity checks;
- computes admitted resolved-trade net expectancy, net profit factor, net drawdown and total net R;
- requires complete cost coverage on resolved outcomes;
- compares Champion A vs Challenger B on identical cases;
- requires at least one measured **net** benefit before the challenger can remain review-eligible;
- never auto-promotes a challenger.

Gross metrics remain available for traceability; cost-complete net metrics become the stricter BSE decision/promotion evidence.

## Final guidance composer

`final_guidance.py` consumes a supplied plan. It does not fabricate one.

A `LONG_CANDIDATE` or `SHORT_CANDIDATE` is possible only when:

1. hard rules return `ALLOW`;
2. projected resident transaction costs are attached to the same plan geometry;
3. historical reliability is real-history, OOS, walk-forward, no-lookahead, cost-complete and includes net expectancy.

Otherwise the composer returns one of:

- `WAIT`
- `DATA_INSUFFICIENT`
- `BLOCKED_BY_HARD_RULE`
- `EXIT_REQUIRED`

`NO_TRADE` remains a schema verdict for later explicit use; Phase 10 does not invent a discretionary NO_TRADE rule simply to fill the field.

Relative-market context from Phase 9 is surfaced as research-only evidence and may create a data-gap note if unavailable, but it cannot flip the verdict until controlled learning deliberately promotes a relative-market feature.

## Confidence

Phase 10 intentionally avoids fake precision percentages. Confidence is separated into categorical dimensions:

- data quality;
- hard-rule status;
- historical reliability;
- cost economics;
- relative-market context;
- model uncertainty (`not_quantified`).

## Output lineage

Final guidance records:

- identity/mode/direction;
- entry/target/stop;
- gross and projected net R:R;
- projected net P&L;
- hard-rule state/codes;
- Crash Guard state/reasons;
- multi-timeframe trend/regime summary;
- official-intelligence event count;
- historical sample/net expectancy/hit rate;
- optional relative-market context SHA;
- why / what-changes-verdict / data gaps;
- `advisory_only=True`;
- `auto_execution=False`;
- deterministic guidance SHA-256.

## Validation

Exact isolated validation after the policy correction:

- updated BSE profile boundary: **10 passed**;
- Phase-10 hard-rule/candidate/net-learning/final-guidance tests: **29 passed**;
- existing Phase-7 controlled-learning/governance regressions: **37 passed**;
- combined Phase-7 + updated-profile + Phase-10 validation: **76 passed**.

Phase 9 Desktop Windows GitHub Actions: **PASSED**, run `32525813721`.

Phase 10 repository CI must be observed after the committed draft PR before repository-level success is claimed.

## Still not implemented here

- No broker/order writes or live execution.
- No production Kite adapter or API-key storage.
- No automatic plan selection from multiple proposals.
- No silent learned threshold promotion.
- No Command Center UI yet.
- No generic Vibe runtime takeover.

## Next

Phase 11 should expose this backend through a read-only BSE Command Center/API presentation layer. The UI must render the backend verdict and lineage; it must never synthesize or override one.
