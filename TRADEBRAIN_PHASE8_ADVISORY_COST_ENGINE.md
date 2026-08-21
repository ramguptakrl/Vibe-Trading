# TradeBrain Phase 8 — DAY/SWING Advisory Cost Engine

## Goal

Phase 8 makes transaction-cost economics explicit for the two advisory modes the owner actually wants: **DAY/intraday** and **SWING**. It intentionally separates market advice from broker/account execution eligibility.

The rule is simple:

> A valid BSE DAY/SWING advisory setup is evaluated on market evidence first. Brokerage/account/product restrictions are a separate execution layer and must not erase the advisory result.

MTF is therefore **not required** for Phase 8 and is deferred as an optional funding overlay.

## Advisory modes

### DAY

- LONG or SHORT.
- Same-session/same-date cost classification.
- Owner hard rule still forces flat by 15:15 IST outside this accounting module.
- Intraday brokerage, sell-side STT, buy-side stamp duty, exchange transaction charge, SEBI fee and GST are modeled.
- Normal same-day square-off has no DP debit.
- Auto-square-off/call-and-trade cost is added only when explicitly requested.

### SWING

- LONG-only under current TradeBrain policy.
- If the position is actually held overnight, delivery economics apply.
- If a SWING idea is closed on its entry date, it is costed as intraday rather than delivery.
- Overnight delivery includes bilateral delivery STT, buy-side delivery stamp duty, exchange/SEBI/GST and DP debit when enabled.

## Brokerage profiles are not advice gates

`EquityBrokerageProfile` represents a fee schedule only. The module includes resident and NRI Non-PIS Zerodha fee profiles for estimating costs, but neither profile decides whether a DAY/SWING market setup exists.

This preserves the owner clarification that NRI/MTF restrictions are not the purpose of the brain; the brain should advise on Intraday and Swing trades.

## Source-dated charge schedules

The built-in Zerodha equity schedule is versioned and records a conservative `applicable_from` equal to its **first verified date**. This does not claim every rate changed on that date.

Historical replay before that boundary fails closed unless a separately verified historical schedule is supplied. This prevents today's brokerage/statutory fees from silently rewriting older backtests.

## Cost components

The engine supports:

- brokerage per executed order with rate/cap profiles;
- NSE/BSE equity cash transaction charges;
- SEBI turnover fee;
- GST on brokerage + exchange transaction + SEBI;
- intraday sell-side STT.
- delivery STT on both buy and sell;
- intraday/delivery buy-side stamp duty;
- DP debit for delivery exits when enabled;
- explicit auto-square-off/call-and-trade charge;
- explicit versioned entry/exit slippage assumptions.

Slippage changes execution prices and is not added again to `total_charges`.

## Break-even and net-target solvers

For LONG plans, Phase 8 finds the lowest tradable exit price that satisfies the requested net rupee target.

For DAY SHORT plans, it finds the highest cover price that still satisfies the requested net target.

The solver verifies the resulting paise/tick-grid value against the full charge calculation instead of returning only a mathematically approximate answer.

## Immutable Phase-6 overlay

`AdviceCostedPlanSnapshot` wraps, rather than mutates, a Phase-6 plan. It binds:

- original setup SHA-256;
- exact advisory position SHA-256;
- charge-schedule version and SHA-256;
- brokerage-profile version and SHA-256;
- slippage version and SHA-256.

`AdviceCostedPlanOutcome` applies realized costs only when Phase 6 mechanically resolved TP-first or SL-first. Ambiguous-same-bar, neither and data-insufficient paths remain uncosted rather than receiving fabricated exits.

The Crash label is not recomputed by the cost layer. It is rebound to the exact costed setup lineage for later controlled research.

## Current scope boundary

Phase 8 does **not**:

- require MTF for SWING;
- use NRI/MTF eligibility as an advice gate;
- place orders or mutate broker accounts;
- claim that an advisory setup is executable in every account;
- model income tax/TDS inside transaction-cost R;
- reconstruct partial fills/multiple real orders;
- backfill current charges into older history;
- generate final BUY/SELL guidance by itself.

## Validation

Revised scope validation:

- Phase 7 controlled-learning/governance tests: **37 passed**.
- Phase 8 DAY/SWING advisory-cost tests: **15 passed**.
- Combined isolated validation: **52 passed**.
- Phase 7 Desktop Windows CI: **PASSED**, run `32517034012`.
- Phase 8 repository CI must be observed after the clean commit/PR before claiming repository-level success.

## Next

Phase 9 should add point-in-time **relative-market context** (for example broad Indian-market stress/strength) only when source alignment is exact and controlled evaluation demonstrates incremental value.
