# TradeBrain Phase 0 — Frozen Vibe-Trading Baseline

## Purpose

This document freezes the exact upstream Vibe-Trading baseline from which the TradeBrain + BSE integration begins. Phase 0 is intentionally documentation/scaffolding only: it must not change trading behavior, broker behavior, strategy behavior, frontend behavior, or execution permissions.

The canonical integration philosophy remains defined in `TRADEBRAIN_VIBE_REFRAME_MASTER_SPEC_2026-08-21.txt`.

## Frozen baseline

- Repository: `ramguptakrl/Vibe-Trading`
- Upstream: `HKUDS/Vibe-Trading`
- Upstream/default branch: `main`
- Frozen upstream commit: `1907e47d31d72f34bc2c87e0e5c4f750c83da59d`
- Vibe-Trading package version: `0.1.14`
- Python requirement: `>=3.11`
- Phase 0 working branch: `tradebrain-phase0-baseline`
- Integration parent branch: `tradebrain-bootstrap`
- `tradebrain-bootstrap` was verified as exactly one commit ahead and zero behind `main` before Phase 0; that one commit added only the master TradeBrain reframing specification.

## Existing repository shape to preserve

- Backend/package code: `agent/`
- Frontend: `frontend/`
- Wiki: `wiki/`
- CLI entry point: `agent/cli/`
- MCP entry point: `agent/mcp_server.py`
- FastAPI/server surfaces already exist upstream.
- DuckDB is already an upstream dependency and may be reused where appropriate rather than introducing a second database library without reason.

## Existing upstream capabilities relevant to TradeBrain

The following upstream capabilities should be reused where they are stronger than the legacy projects:

### India market support

- Existing `IndiaEquityEngine` under `agent/backtest/engines/india_equity.py`.
- Existing India broker history bridge under `agent/backtest/loaders/india_broker_loader.py`.
- Existing Dhan and Shoonya connector infrastructure.
- India engine already models configurable India cash-equity rules/costs and is therefore the preferred base for generic India backtesting rather than replacing it wholesale.

### Research and controlled strategy development

- Existing research-goal lifecycle and evidence audit tooling.
- Existing hypothesis / strategy-development infrastructure.
- Existing Strategy Development Manager flow for ingest → extract → implement → evaluate → monitor.
- Existing factor, Alpha Zoo, backtest, research, and scheduled-research infrastructure should remain available.

### Governance and safety

- Existing mandate/order enforcement surfaces.
- Existing kill-switch / order-safety architecture.
- Existing append-only/hash-chained governance ledger primitives.
- Existing contributor guidance explicitly treats broker connector, mandate, order gate, halt, and audit-ledger logic as safety-critical.
- TradeBrain work must not weaken, bypass, or globally replace these protections.

## TradeBrain/BSE boundaries frozen at Phase 0

The following are architectural requirements for later phases, not Phase 0 code changes:

1. TradeBrain must be an additive profile/overlay, not a destructive rewrite of Vibe-Trading.
2. Normal Vibe behavior must remain available when the TradeBrain profile is disabled.
3. The first custom profile will be named `tradebrain_bse` unless a later deliberate decision changes the name.
4. The BSE profile remains advisory-only unless the owner explicitly changes that product boundary in a future reviewed phase.
5. LLMs, swarms, generic factors, indicators, or strategy-discovery outputs may contribute evidence/context but may not bypass hard BSE rules.
6. DAY trading and SWING/POSITION semantics from the master spec remain the controlling BSE-specific policy.
7. DAY must be flat by 15:15 IST; this is a hard rule and is not learnable away.
8. SWING/POSITION remains long-only in the current BSE policy; MTF is a funding mechanism, not the retired L1/L2/L3 rescue system.
9. Legacy L1/L2/L3 rescue averaging remains retired from active decision logic.
10. Crash Guard remains a risk/exposure gate, not an automatic short generator.
11. Hard-rule behavior and learned/adaptive behavior must remain explicitly separated.
12. TradeBrain India identity/provenance concepts (issuer → ISIN/canonical security → exchange listings, source timestamps/hashes/raw archives) should be integrated selectively rather than replacing upstream generic market plumbing.
13. Zerodha/Kite is a later additive adapter/data source; it must not require removal of existing Vibe sources/connectors.
14. No secrets, broker credentials, `.env` contents, local TradeBrain database, or private exports belong in Git.

## Phase 0 verification policy

Before Phase 1 changes are considered safe, the implementation should preserve the repository's own validation expectations. Relevant upstream checks include:

```bash
git status --short --branch
git diff --check
python -m compileall -q agent/cli
python -m py_compile agent/api_server.py agent/mcp_server.py
pytest --ignore=agent/tests/e2e_backtest --ignore=agent/tests/test_e2e_harness_v2.py --tb=short -q
pytest agent/tests/test_sdk_order_gate.py agent/tests/test_mandate_enforcement.py -q
cd frontend && npm ci && npm run build
```

For future changes touching live/order safety, the narrower upstream safety suite should also be used:

```bash
pytest agent/tests/test_sdk_order_gate.py \
  agent/tests/test_mandate_enforcement.py \
  agent/tests/test_killswitch_blocks_orders.py \
  agent/tests/test_readonly_default.py -q
```

Phase 0 itself does not claim these commands were executed merely because they are documented here. A test result may only be marked VERIFIED after a real run/CI result is observed.

## Phase 0 completion criteria

- [x] Exact upstream SHA frozen.
- [x] Exact package version frozen.
- [x] Master TradeBrain integration specification present in Git.
- [x] Separate Phase 0 branch created from the integration branch.
- [x] Existing India/research/governance capabilities identified for reuse.
- [x] Safety-critical upstream surfaces explicitly protected from casual modification.
- [x] Persistent implementation-status file added.
- [ ] Baseline test suite executed in a real compatible environment or GitHub CI and results recorded.

The unchecked test item is intentionally not fabricated. Phase 0 documentation can complete while baseline execution verification remains `PENDING` until an actual runner is used.
