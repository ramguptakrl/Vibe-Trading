# TradeBrain Phase 9 — Point-in-Time Relative-Market Context

## Goal

Phase 9 adds broad Indian-market context around the verified BSE Ltd market snapshot without turning an index into a trade signal.

The initial benchmark descriptor is **NIFTY 50** using the exact Vibe/Yahoo-compatible symbol `^NSEI`. The descriptor is an index-data identity, not a canonical security/ISIN identity.

## Core rules

- Reuse Vibe's existing `india_equity` loader resolver.
- Require the exact benchmark symbol returned by the selected provider; never fuzzy-substitute another index.
- Use the same interval as BSE Ltd.
- By default require the same resolved market-data source for BSE and benchmark.
- Normalize equivalent timezone offsets before timestamp alignment.
- Only bars at or before the requested `as_of` may contribute to relative metrics.
- Context hashing uses the point-in-time eligible prefixes, not later/future bars in a larger source frame.
- Stale or unknown BSE/benchmark freshness cannot become relative-market ready.
- Missing alignment fails closed.
- Relative-market features are provisional research context (`learned=False`), not owner/exchange/broker hard rules.
- Relative context never creates LONG/SHORT, never bypasses Crash Guard, and never changes DAY/SWING policy.

## Measurements

Phase 9 records:

- exact aligned bar count and alignment ratio;
- BSE and benchmark one-bar returns;
- short-window BSE/benchmark/relative returns;
- medium-window BSE/benchmark/relative returns;
- benchmark drawdown from the medium-window high;
- aligned return correlation;
- aligned beta;
- exact BSE/benchmark point-in-time prefix SHA-256 values;
- aligned-timestamp SHA-256;
- config version and learned flag.

The default windows are measurement geometry only. They are not claimed to be optimized or learned.

## Data path

`fetch_benchmark_market_data()` reuses `resolve_loader("india_equity")`.

The initial exact benchmark descriptor is:

- benchmark id: `india:nifty50`
- display name: `NIFTY 50`
- loader symbol: `^NSEI`
- role: `broad_market`

If the selected provider cannot return that exact symbol, Phase 9 fails closed. Future broker/Kite adapters may supply another exact provider-specific descriptor without changing the resident-trader advisory persona.

## Point-in-time protection

`build_relative_market_context()` filters both BSE and benchmark series to `timestamp <= as_of`, converts timestamps to UTC for exact-instant matching, then computes metrics only from the aligned prefix.

A regression test mutates all benchmark bars after an earlier `as_of` into a severe crash and verifies the earlier relative-market measurements remain unchanged.

The context SHA is based on the eligible point-in-time prefixes. Appending future bars to a larger source snapshot therefore does not rewrite an earlier context hash.

## Controlled-learning boundary

`relative_market_feature_payload()` exposes deterministic research features plus the context SHA.

It deliberately contains no `direction`, `verdict`, `BUY`, or `SELL` field.

Before relative-market features influence final BSE guidance, they must be compared through the existing Phase-7 Champion/Challenger process on identical OOS/walk-forward data. Phase 9 itself performs no promotion.

## Validation

- Phase 9 targeted isolated suite: **18 passed**.
- Phase 8 targeted resident DAY/SWING suite: **18 passed**.
- Phase 7 + Phase 8 isolated validation previously recorded: **55 passed**.
- Phase 8 Desktop Windows GitHub Actions: **PASSED**, run `32524596840`.
- Phase 9 repository CI must be observed after the committed draft PR before claiming repository-level success.

## Not implemented here

- No final trade decision.
- No new Crash Guard hard gate.
- No automatic strategy-weight change.
- No learned relative-market threshold.
- No live order/broker write.
- No API key/token storage.
- No NRI-account restriction leaking into the resident target trader.
- No sector/index basket optimization yet.

## Next

After Phase 9 is validated, the next planned engineering phase is the BSE Command Center/final advisory presentation layer, while the authoritative hard-rule arbiter and final-guidance composition must remain fail-closed until their required inputs are explicitly implemented.
