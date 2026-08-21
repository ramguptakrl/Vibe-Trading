# TradeBrain Phase 5 — BSE Market Structure + Crash Guard Foundation

## Purpose

Phase 5 adds adaptive market-structure and deterministic crash-risk context on top of the verified Phase-4 BSE market-data snapshot.

It does **not** create a trade candidate, BUY/SELL instruction, order, broker action, learned strategy, or final guidance.

The central invariant is:

    one validated Phase-4 BSE snapshot
        -> no-lookahead timeframe derivation
        -> adaptive structure
        -> deterministic Crash Guard
        -> risk context

No Phase-5 module fetches another price series.

## Inputs reused

Phase 5 consumes `BSEMarketDataSnapshot` from `agent/src/tradebrain/market_data.py`.

Therefore it inherits Phase-4 guarantees:

- canonical BSE Ltd identity;
- exact `NSE:BSE` / `BSE.NS` binding;
- validated OHLCV geometry;
- ascending/unique timestamps;
- deterministic source-frame SHA-256;
- explicit freshness status.

A stale or unknown-freshness Phase-4 snapshot cannot become Phase-5 structure-ready.

## New modules

### `agent/src/tradebrain/structure.py`

Provides:

- complete-bar boundary enforcement;
- no-lookahead higher-timeframe derivation;
- EMA 20/50/200 context by default;
- true-range / ATR-style volatility context;
- volume-ratio context;
- confirmed swing highs/lows;
- clustered support/resistance;
- observed-window high/low;
- optional all-time-high semantics only when lifetime coverage is explicitly certified;
- 52-week high/low only after at least 252 daily observations;
- trend classification;
- regime classification;
- flexible multi-timeframe composition.

The defaults are marked:

    version = phase5-provisional-v1
    learned = false

They are soft/adaptive parameters, not learned or promoted rules.

### `agent/src/tradebrain/crash_guard.py`

Provides a deterministic risk gate with states:

- `DATA_INSUFFICIENT`
- `NORMAL`
- `ELEVATED`
- `SEVERE`

Provisional inputs include combinations of:

- one-bar decline;
- multi-bar decline;
- gap-down;
- drawdown from observed high;
- true-range shock;
- bearish volume shock;
- confirmed support failure;
- multi-timeframe bearish alignment.

The thresholds are intentionally provisional and versioned. They require later replay/calibration across severe **and ordinary** sessions, including explicit false-positive measurement.

Current hard behavioral contract:

- `SEVERE` may block fresh DAY LONG;
- `SEVERE` may block fresh SWING/MTF LONG;
- Crash Guard never creates a SHORT;
- a SHORT must qualify independently in a later candidate layer;
- `DATA_INSUFFICIENT` is not treated as `NORMAL`.

### `agent/src/tradebrain/structure_context.py`

Composes Phase 4 + structure + Crash Guard.

It may advance only `market_structure_ready`.

It cannot mark:

- historical outcomes ready;
- hard-rule arbiter ready;
- final decision ready.

## No-lookahead rules

### Explicit `as_of`

Every Phase-5 analysis is bounded by an explicit timezone-aware `as_of`.

### Complete native bars

A native intraday bar is considered usable only when:

    bar_start + native_interval <= as_of

A bar that has merely started at `as_of` is not treated as a completed candle.

### Higher-timeframe buckets

Higher-timeframe bars:

- are derived only from Phase-4 bars;
- cannot be finer than the native interval;
- must be exact integer multiples of the native interval;
- require all expected constituent timestamps;
- exclude incomplete buckets.

Intraday buckets are anchored to the regular NSE cash-session open at 09:15 Asia/Kolkata.

### Daily derivation

When deriving a daily bar from intraday bars, Phase 5 requires a complete regular NSE 09:15–15:30 constituent sequence. Incomplete/special-session geometry is skipped rather than guessed.

Weekly/monthly derivation is deliberately deferred until an exchange-calendar-aware layer is connected.

### Crash Guard boundary

`MultiTimeframeStructure` records:

- exact native bar count used;
- exact latest complete native timestamp;
- Phase-4 source-frame SHA-256.

Crash Guard must match all three. It evaluates only that bounded prefix.

This prevents later bars still present in a larger snapshot from leaking backward into an earlier historical decision.

## Swing confirmation

A swing high/low is not confirmed merely because the current bar looks like a pivot.

With `swing_right = N`, the N right-hand confirmation bars must already exist within the `as_of` boundary.

This means a future bar cannot retroactively appear inside a past decision context.

## High / ATH semantics

Phase 5 distinguishes:

- `observed_window.high`
- `52_week_high`
- `all_time_high`

`all_time_high` remains `None` unless the caller explicitly certifies complete lifetime-history coverage for that interval.

This avoids calling a local maximum from a partial history window an ATH.

## Structure semantics

EMA, trend, volatility, level clustering, timeframe importance and thresholds remain adaptive/soft features.

They are not hard trading rules.

The market-structure layer describes the market; it does not decide whether to buy or sell.

## Crash Guard semantics

Crash Guard is intentionally asymmetric:

    risk state -> may block a fresh long

It does not imply:

    risk state -> open short

A severe crash state can therefore coexist with `NO_TRADE`, `WAIT`, or a separately qualified future DAY SHORT.

Market-wide stress and BSE-relative weakness are not yet included because Phase 5 has only the canonical BSE Ltd price series. Relative-market context belongs in a later phase.

## Readiness after Phase 5

With fresh Phase-4 market data, fresh official intelligence coverage, usable structure and usable Crash Guard:

    identity                  READY
    market data               READY
    official intelligence     READY
    market structure/risk     READY
    historical outcomes       NOT READY
    hard-rule arbiter         NOT READY
    final decision            NOT READY

This is deliberate.

## Validation

Targeted Phase-5 isolated validation covers:

- partial native-bar exclusion;
- complete higher-timeframe buckets;
- hole/missing-constituent rejection;
- no finer-timeframe derivation;
- right-side swing confirmation;
- observed-window vs certified ATH semantics;
- 52-week coverage requirements;
- insufficient EMA handling;
- up/down/sideways trend classification;
- deterministic support/resistance clustering;
- volume baseline behavior;
- multi-timeframe use of the same Phase-4 frame hash;
- stale Phase-4 snapshot rejection;
- provisional/frozen structure config;
- Crash Guard data-insufficient/normal/elevated/severe states;
- severe long blocking;
- no automatic short creation;
- future-shock no-lookahead protection;
- mismatched snapshot rejection;
- provisional Crash Guard config;
- Phase-5 readiness composition;
- missing requested-timeframe readiness blocking;
- weekly/monthly derivation deferral without an exchange calendar.

Targeted result before commit:

    28 passed

The validation uses the exact Phase-5 module contents with faithful stubs for existing Phase-4 contracts. It is not a claim that the entire upstream Vibe repository passes.

## Still not built

- no historical outcome memory;
- no TP-first / SL-first replay;
- no walk-forward calibration;
- no false-positive statistics yet;
- no learned Crash Guard thresholds;
- no relative-market/index context;
- no MTF economics/cost engine;
- no DAY/SWING candidate generator;
- no authoritative hard-rule arbiter;
- no final BSE guidance;
- no Kite integration;
- no broker write-path integration;
- no UI/API integration.

## Next intended phase

Phase 6 should build BSE plan-specific historical outcomes and replay on top of the exact identity/data/intelligence/structure versions.

It should record setup state at decision time, then measure what happened afterward without allowing future data into the original decision features.

Only after that evidence exists should structure/Crash Guard thresholds begin challenger-style calibration.
