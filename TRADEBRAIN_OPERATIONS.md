# TradeBrain BSE Operations

Operational reference for the BSE TradeBrain profile inside Vibe-Trading.

## Command Center

Frontend route: `/tradebrain/bse`.

The Command Center renders backend state only. It does not invent or post a trading verdict. It shows operating mode, authoritative guidance when supplied, Kite read-only readiness, manual/shadow journal state and external evidence gates.

## Operating modes

TradeBrain resolves Indian session time in `Asia/Kolkata` and requires a verified NSE calendar snapshot before treating a date as tradable.

- `MARKET_ACTIVE`: observe market, refresh context, compose advisory guidance and track manually accepted trades.
- `DAY_EXIT_WINDOW`: prioritize DAY exits and enforce the 15:15 IST hard-flat boundary.
- `AFTER_MARKET`: replay completed sessions, score advisories/manual outcomes, archive evidence and run research/challenger work.
- `OFF_HOURS`: maintenance, evidence archival and permitted research work only.

Broker order writes, automatic challenger promotion and hard-rule mutation are forbidden in every mode.

## Verified NSE calendar

Runtime file:

`$VIBE_TRADING_HOME/tradebrain/nse_calendar.json`

Default:

`~/.vibe-trading/tradebrain/nse_calendar.json`

Required fields include exchange `NSE`, timezone `Asia/Kolkata`, validity range, explicit trading dates, source identity/URL and a 64-hex source SHA-256. Missing, invalid or out-of-range evidence fails closed; weekdays are never treated as proof that the exchange is open.

## Journals

Runtime journal:

`$VIBE_TRADING_HOME/tradebrain/journal.json`

The journal lives outside the repository and is atomically replaced on write. Manual records bind the user's actual trade to the original advisory ID and 64-hex guidance SHA. Shadow records preserve unresolved/resolved advisory outcomes for live evidence collection.

Invalid geometry, malformed hashes and SWING SHORT records are rejected.

## Kite read-only setup

Kite is optional until real broker-data integration is being tested.

Environment values are read through the config layer:

- `KITE_API_KEY`
- `KITE_ACCESS_TOKEN`
- `KITE_ACCOUNT_CLASS` (default `nri_non_pis`)

The credential is a market-data credential only and does not change the resident-individual TradeBrain policy. The adapter supports login URL construction, access-token binding, instrument resolution, quotes, historical candles and a market WebSocket. It intentionally exposes no order, position-conversion or GTT mutation surface.

Exact BSE Ltd identity is guarded as `NSE:BSE` / `INE118H01025` when the provider supplies ISIN.

## API surface

Authenticated endpoints:

- `GET /tradebrain/bse/operating-mode`
- `GET /tradebrain/bse/command-center`
- `GET /tradebrain/bse/kite/status`
- `GET /tradebrain/bse/journal/manual`
- `POST /tradebrain/bse/journal/manual`
- `POST /tradebrain/bse/journal/manual/{trade_id}/close`
- `GET /tradebrain/bse/journal/shadow`
- `POST /tradebrain/bse/journal/shadow`
- `POST /tradebrain/bse/journal/shadow/{shadow_id}/resolve`

## Evidence gates

Source code alone cannot satisfy these gates:

- real Kite authentication and live/read-only data verification;
- source-audited current NSE calendar data;
- real BSE Ltd historical backfill and integrity audit;
- cost-complete no-lookahead OOS/walk-forward calibration;
- live shadow observations across real market sessions;
- explicit human Champion/Challenger review.

Until those inputs exist, the system must report the missing evidence rather than fabricate readiness, final thresholds or profitability.
