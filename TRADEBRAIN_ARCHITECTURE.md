# TradeBrain BSE Architecture

This is the canonical architecture for the BSE-focused TradeBrain profile inside Vibe-Trading. It replaces the temporary phase-by-phase design notes.

## Design rule

TradeBrain is an additive BSE decision layer, not a fork of Vibe's strongest infrastructure. Keep the upstream Vibe component when it is already stronger; add TradeBrain only where Indian identity, BSE policy, provenance, fail-closed safety, or advisory governance needs stricter behavior.

## Reused Vibe core

TradeBrain deliberately reuses these original Vibe capabilities instead of rebuilding weaker copies:

- FastAPI backend assembly, authentication, middleware and route infrastructure.
- React frontend/router and the existing application shell.
- Vibe market-data loader registry and source ecosystem through the TradeBrain loader adapter.
- `IndiaEquityEngine` and generic backtest infrastructure for Indian equity mechanics, fees and research compatibility.
- Strategy Store / SDM model lifecycle for research candidate registration and validation history.
- Governance ledger for tamper-evident approval/promotion records.
- Existing research, replay, scheduling, swarm and analysis infrastructure where it does not conflict with BSE hard rules.

## TradeBrain additions

TradeBrain owns the BSE-specific decision contract:

- canonical company -> ISIN -> exchange-listing identity and exact BSE Ltd instrument guard;
- source provenance, timestamps, evidence fingerprints and fail-closed data quality;
- no-lookahead multi-timeframe market structure;
- provisional Crash Guard as a LONG risk gate, never a SHORT generator;
- DAY and SWING hard-policy arbitration;
- structure-derived entry/target/stop candidate geometry;
- resident-individual transaction-cost economics;
- deterministic historical outcome/replay accounting;
- controlled Champion/Challenger evaluation with OOS and walk-forward gates;
- final plan-specific advisory composition;
- operating modes, manual/shadow journals and the BSE Command Center;
- optional Zerodha Kite read-only market-data adapter.

## Final policy

Primary security: BSE Ltd, canonical listing `NSE:BSE`, ISIN `INE118H01025`.

- DAY: LONG and SHORT are allowed subject to hard rules. Fresh DAY entry stops at 15:10 IST and DAY exposure must be flat by 15:15 IST.
- SWING: LONG only. Funding is cash/delivery or optional MTF; MTF is not required.
- Crash Guard: may block fresh LONG exposure when severe; it does not create SHORT signals and does not independently force an existing position out.
- Target trader persona: resident individual. Optional NRI-class broker credentials used for read-only data cannot alter the target policy or economics.
- Execution: advisory-only. TradeBrain exposes no broker order-writing authority and automatic challenger promotion is prohibited.

## Decision precedence

1. Immutable owner and verified exchange/broker rules.
2. Data integrity, provenance, no-lookahead and fail-closed requirements.
3. BSE policy.
4. TradeBrain Indian identity and historical memory.
5. Validated learned parameters.
6. Generic Vibe defaults.
7. LLM/research opinion.

A lower layer can never override a higher layer.

## Validation contract

A candidate cannot become authoritative merely because it backtests well. Production review requires real history, chronological OOS evidence, walk-forward evaluation, verified no-lookahead behavior, complete costs, sufficient sample coverage and explicit human review. Synthetic fixtures may test software behavior but cannot establish profitability or promote parameters.

## Integration boundary

Vibe remains the platform body; TradeBrain is the stricter BSE brain. The correct implementation extends and adapts original Vibe components rather than copying their internals into parallel modules. Any future feature should follow the same rule: reuse upstream infrastructure where safe, and keep BSE decision authority inside the TradeBrain hard-rule and evidence boundary.
