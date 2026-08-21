"""Final advisory composition foundation for TradeBrain Phase 10.

The composer is plan-specific and fail-closed. It does not generate a plan and
it does not place orders.  A LONG/SHORT candidate verdict is possible only when
hard rules allow the supplied plan and validated cost-complete historical
reliability is explicitly supplied.  Relative-market context is surfaced as
research context only and cannot change the verdict by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Mapping

from src.tradebrain.advisory_costs import EquityTradeEconomics
from src.tradebrain.hard_rules import (
    AdvisoryPlanRequest,
    HardRuleAssessment,
    HardRuleState,
)
from src.tradebrain.relative_market import RelativeMarketContext
from src.tradebrain.structure_context import BSEStructureRiskContext

__all__ = [
    "ConfidenceBreakdown",
    "FinalGuidance",
    "GuidanceVerdict",
    "HistoricalReliabilitySummary",
    "compose_final_guidance",
]


class GuidanceVerdict(str, Enum):
    LONG_CANDIDATE = "long_candidate"
    SHORT_CANDIDATE = "short_candidate"
    WAIT = "wait"
    NO_TRADE = "no_trade"
    EXIT_REQUIRED = "exit_required"
    DATA_INSUFFICIENT = "data_insufficient"
    BLOCKED_BY_HARD_RULE = "blocked_by_hard_rule"


def _canon(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: _canon(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canon(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return float(f"{value:.15g}")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _hash(value: object) -> str:
    body = json.dumps(_canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HistoricalReliabilitySummary:
    """Evidence gate for final guidance; not a learned parameter itself."""

    sample_count: int
    out_of_sample: bool
    walk_forward: bool
    real_history: bool
    no_lookahead_verified: bool
    costs_complete: bool
    expectancy_net_r: float | None
    hit_rate: float | None
    max_drawdown_net_r: float | None
    source_sha256: str

    def __post_init__(self) -> None:
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if not str(self.source_sha256).strip():
            raise ValueError("historical reliability source_sha256 is required")
        for name in ("expectancy_net_r", "hit_rate", "max_drawdown_net_r"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when supplied")

    @property
    def ready(self) -> bool:
        return (
            self.sample_count > 0
            and self.out_of_sample
            and self.walk_forward
            and self.real_history
            and self.no_lookahead_verified
            and self.costs_complete
            and self.expectancy_net_r is not None
        )


@dataclass(frozen=True)
class ConfidenceBreakdown:
    """Categorical confidence dimensions; no fake precision percentage."""

    data_quality: str
    hard_rules: str
    historical_reliability: str
    cost_economics: str
    relative_market: str
    model_uncertainty: str = "not_quantified"


@dataclass(frozen=True)
class FinalGuidance:
    isin: str
    qualified_symbol: str
    mode: str
    direction: str
    verdict: GuidanceVerdict
    as_of: str
    entry: float
    target: float
    stop: float
    gross_rr: float | None
    projected_net_rr: float | None
    projected_net_pnl: float | None
    hard_rule_state: str
    hard_rule_codes: tuple[str, ...]
    crash_guard_state: str
    crash_guard_reasons: tuple[str, ...]
    timeframe_summary: tuple[tuple[str, str, str, float], ...]
    intelligence_event_count: int
    historical_sample_count: int
    historical_expectancy_net_r: float | None
    historical_hit_rate: float | None
    relative_market_context_sha256: str | None
    relative_market_ready: bool | None
    confidence: ConfidenceBreakdown
    why: tuple[str, ...]
    what_changes_verdict: tuple[str, ...]
    data_gaps: tuple[str, ...]
    advisory_only: bool
    auto_execution: bool
    guidance_sha256: str


def _validate_cost_binding(
    request: AdvisoryPlanRequest,
    economics: EquityTradeEconomics,
) -> float:
    position = economics.position
    if str(getattr(position.mode, "value", position.mode)) != request.mode.value:
        raise ValueError("projected cost economics mode does not match plan request")
    if str(getattr(position.direction, "value", position.direction)) != request.direction.value:
        raise ValueError("projected cost economics direction does not match plan request")
    if abs(float(position.entry_reference_price) - request.entry) > 1e-9:
        raise ValueError("projected cost economics entry does not match plan request")
    risk_total = request.risk_per_share * position.quantity
    if risk_total <= 0:
        raise ValueError("valid plan risk is required for projected net R")
    return float(economics.net_pnl) / risk_total


def compose_final_guidance(
    phase5: BSEStructureRiskContext,
    request: AdvisoryPlanRequest,
    hard_rules: HardRuleAssessment,
    *,
    historical: HistoricalReliabilitySummary | None,
    projected_costs: EquityTradeEconomics | None,
    relative_market: RelativeMarketContext | None = None,
) -> FinalGuidance:
    """Compose one plan-specific advisory result without generating the plan."""

    if hard_rules.request_sha256 != request.request_sha256:
        raise ValueError("hard-rule assessment does not belong to the supplied plan request")

    foundation = phase5.phase4.foundation
    projected_net_rr = None
    projected_net_pnl = None
    if projected_costs is not None:
        projected_net_rr = _validate_cost_binding(request, projected_costs)
        projected_net_pnl = float(projected_costs.net_pnl)

    data_gaps: list[str] = []
    why: list[str] = []
    changes: list[str] = []

    if hard_rules.state is HardRuleState.DATA_INSUFFICIENT:
        verdict = GuidanceVerdict.DATA_INSUFFICIENT
        why.extend(hard_rules.reasons)
        changes.append("restore all required identity/market/intelligence/structure inputs")
    elif hard_rules.state is HardRuleState.EXIT_REQUIRED:
        verdict = GuidanceVerdict.EXIT_REQUIRED
        why.extend(hard_rules.reasons)
        changes.append("DAY position must be flat; a new setup can be considered in a later valid session")
    elif hard_rules.state is HardRuleState.BLOCKED:
        verdict = GuidanceVerdict.BLOCKED_BY_HARD_RULE
        why.extend(hard_rules.reasons)
        changes.append("hard-rule blocker must clear; AI/history/relative-market context cannot override it")
    else:
        if projected_costs is None:
            data_gaps.append("projected_transaction_costs_missing")
        if historical is None:
            data_gaps.append("historical_reliability_missing")
        elif not historical.ready:
            data_gaps.append("historical_reliability_not_fully_validated")

        if data_gaps:
            verdict = GuidanceVerdict.WAIT
            why.append("hard rules allow the plan, but evidence needed for a candidate verdict is incomplete")
            if projected_costs is None:
                changes.append("attach source-dated resident transaction-cost economics for the proposed exit")
            if historical is None or not historical.ready:
                changes.append("supply real, OOS, walk-forward, no-lookahead, cost-complete historical reliability")
        else:
            verdict = (
                GuidanceVerdict.LONG_CANDIDATE
                if request.direction.value == "long"
                else GuidanceVerdict.SHORT_CANDIDATE
            )
            why.append("hard rules are clear and required cost-complete historical evidence is validated")
            changes.append("invalidate the plan if entry/target/stop, hard-rule state, or evidence lineage changes")

    relative_ready = None
    relative_sha = None
    if relative_market is not None:
        relative_ready = relative_market.ready
        relative_sha = relative_market.context_sha256
        if not relative_market.ready:
            data_gaps.append("relative_market_context_not_ready")
        # Relative context is intentionally not added to verdict logic in Phase 10.

    readiness = phase5.readiness
    data_quality = (
        "ready"
        if (
            readiness.identity_verified
            and readiness.market_data_ready
            and readiness.intelligence_ready
            and readiness.market_structure_ready
        )
        else "insufficient"
    )
    confidence = ConfidenceBreakdown(
        data_quality=data_quality,
        hard_rules=("clear" if hard_rules.state is HardRuleState.ALLOW else hard_rules.state.value),
        historical_reliability=("validated" if historical is not None and historical.ready else "missing_or_unvalidated"),
        cost_economics=("projected" if projected_costs is not None else "missing"),
        relative_market=(
            "not_supplied"
            if relative_market is None
            else "observed_research_only"
            if relative_market.ready
            else "insufficient_research_only"
        ),
    )

    tf_summary = tuple(
        (
            item.interval,
            str(getattr(item.trend, "value", item.trend)),
            str(getattr(item.regime, "value", item.regime)),
            float(item.latest_close),
        )
        for item in phase5.structure.timeframes
    )

    history_count = historical.sample_count if historical is not None else 0
    history_exp = historical.expectancy_net_r if historical is not None else None
    history_hit = historical.hit_rate if historical is not None else None

    core = {
        "isin": foundation.identity.isin,
        "qualified_symbol": foundation.identity.qualified_symbol,
        "mode": request.mode.value,
        "direction": request.direction.value,
        "verdict": verdict,
        "as_of": hard_rules.as_of,
        "entry": request.entry,
        "target": request.target,
        "stop": request.stop,
        "gross_rr": request.gross_rr,
        "projected_net_rr": projected_net_rr,
        "projected_net_pnl": projected_net_pnl,
        "hard_rule_state": hard_rules.state.value,
        "hard_rule_codes": tuple(code.value for code in hard_rules.codes),
        "crash_guard_state": str(getattr(phase5.crash_guard.state, "value", phase5.crash_guard.state)),
        "crash_guard_reasons": tuple(phase5.crash_guard.reasons),
        "timeframe_summary": tf_summary,
        "intelligence_event_count": len(phase5.phase4.intelligence.events),
        "historical_sample_count": history_count,
        "historical_expectancy_net_r": history_exp,
        "historical_hit_rate": history_hit,
        "relative_market_context_sha256": relative_sha,
        "relative_market_ready": relative_ready,
        "confidence": confidence,
        "why": tuple(why),
        "what_changes_verdict": tuple(changes),
        "data_gaps": tuple(dict.fromkeys(data_gaps)),
        "advisory_only": True,
        "auto_execution": False,
    }
    return FinalGuidance(**core, guidance_sha256=_hash(core))
