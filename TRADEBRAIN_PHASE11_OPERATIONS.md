# TradeBrain Phase 11 — Operational Completion Layer

This checkpoint completes the remaining **code/framework** around the Phase-10 BSE advisory core without enabling broker execution.

## Added in this phase

- BSE Command Center route: `/tradebrain/bse`
- deterministic India-session operating modes
- DAY exit window enforcement around the resident policy cutoffs
- after-market/off-hours research permissions
- fail-closed verified NSE calendar contract
- persistent manual trade journal (`I took this trade` workflow)
- persistent live-shadow advisory journal
- validation-readiness gates for real/OOS/walk-forward/no-lookahead/cost-complete evidence
- optional Zerodha Kite **read-only** market-data adapter
- exact `NSE:BSE` / BSE Ltd instrument identity check
- quote, historical-candle and WebSocket market-stream helpers
- authenticated API endpoints for the operational surface
- tests for safety boundaries and persistence

## Safety boundary

The BSE profile remains advisory-only.

- no broker order placement
- no broker order modification
- no broker order cancellation
- no position conversion
- no GTT writes
- no automatic challenger promotion
- no UI-generated verdict
- no AI override of hard rules

Kite credentials are data credentials only and do not change the target resident-individual advisory/cost persona.

## API routes

- `GET /tradebrain/bse/operating-mode`
- `GET /tradebrain/bse/command-center`
- `GET /tradebrain/bse/kite/status`
- `GET /tradebrain/bse/journal/manual`
- `POST /tradebrain/bse/journal/manual`
- `POST /tradebrain/bse/journal/manual/{trade_id}/close`
- `GET /tradebrain/bse/journal/shadow`
- `POST /tradebrain/bse/journal/shadow`
- `POST /tradebrain/bse/journal/shadow/{shadow_id}/resolve`

All routes use the existing Vibe-Trading API authentication dependency.

## Operating modes

The controller resolves four modes in `Asia/Kolkata`:

1. `market_active`
2. `day_exit_window`
3. `after_market`
4. `off_hours`

The resident policy remains authoritative:

- market observation starts at 09:15 IST
- no fresh DAY entry at/after 15:10 IST
- DAY must be flat by 15:15 IST
- market observation may continue through 15:30 IST
- after-market research mode runs after the cash session

Broker writes and automatic promotion remain false in every mode.

## Verified NSE calendar contract

TradeBrain does **not** assume Monday-Friday means the market is open.

A source-audited calendar snapshot can be placed at:

`$VIBE_TRADING_HOME/tradebrain/nse_calendar.json`

or, with the default runtime root:

`~/.vibe-trading/tradebrain/nse_calendar.json`

Schema:

```json
{
  "exchange": "NSE",
  "timezone": "Asia/Kolkata",
  "valid_from": "2026-01-01",
  "valid_to": "2026-12-31",
  "trading_dates": ["2026-01-02", "2026-01-05"],
  "source_name": "NSE official trading calendar",
  "source_url": "https://www.nseindia.com/...",
  "source_sha256": "<64 hex characters>"
}
```

If the file is missing, invalid, or outside its validity window, TradeBrain fails closed and does not enter a market-active state.

## Manual and shadow evidence

Runtime evidence is stored outside the repository at:

`$VIBE_TRADING_HOME/tradebrain/journal.json`

Manual records bind the actual trade to the original advisory id and `guidance_sha256`, preserve planned geometry, record actual entry/exit/quantity/costs, and calculate realized P&L.

Shadow records bind the observed outcome to the original advisory without a broker order.

The journal rejects:

- malformed guidance hashes
- unsupported modes/directions
- SWING SHORT
- invalid LONG/SHORT target/entry/stop geometry

## Kite read-only setup

The adapter lazy-loads the official `kiteconnect` Python SDK so the base Vibe-Trading install remains unchanged.

Install when the framework is ready for real Zerodha data:

```bash
pip install "kiteconnect>=5.2.1,<6"
```

Environment values:

```text
KITE_API_KEY=...
KITE_ACCESS_TOKEN=...
KITE_ACCOUNT_CLASS=nri_non_pis
```

The Command Center status endpoint returns only booleans such as `api_key_configured` and `access_token_configured`; it never returns the key or token.

## Evidence gates that cannot be fabricated in code

The following are intentionally **not marked complete until real inputs exist**:

- source-audited current NSE session calendar snapshot
- real BSE Ltd historical backfill from the selected production data source
- data-integrity audit of that history
- real out-of-sample/walk-forward/no-lookahead/calibration results
- authenticated Kite read-only session
- live market shadow observations
- empirical production-review evidence

These are runtime/evidence gates, not missing architecture. The validation layer keeps candidate guidance and production-review readiness blocked until the required evidence is actually present.
