"""Net-of-cost extension for Phase-7 controlled learning.

Phase 8 can attach ``realized_net_r`` to resolved outcomes.  This module reuses
Phase-7 cohort/prediction validation, then measures the admitted trades after
costs.  It does not replace the existing gross metrics; it adds a stricter net
gate before a challenger can be considered reviewable for BSE guidance.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from statistics import mean
from typing import Iterable, Mapping

from src.tradebrain.learning import (
    CandidateEvaluation,
    CandidatePrediction,
    CandidateRole,
    CandidateVersion,
    EvaluationSplit,
    LearningCohort,
    evaluate_candidate,
)

__all__ = [
    "NetCandidateComparison",
    "NetCandidateEvaluation",
    "NetEvaluationMetrics",
    "NetPromotionAssessment",
    "NetPromotionState",
    "assess_net_promotion",
    "compare_net_candidates",
    "evaluate_net_candidate",
]


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


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value)).lower()


@dataclass(frozen=True)
class NetEvaluationMetrics:
    admitted_cases: int
    resolved_trade_count: int
    costed_resolved_trade_count: int
    net_cost_coverage_ratio: float
    expectancy_net_r: float | None
    profit_factor_net: float | None
    max_drawdown_net_r: float | None
    total_net_r: float | None


@dataclass(frozen=True)
class NetCandidateEvaluation:
    core: CandidateEvaluation
    metrics: NetEvaluationMetrics
    evaluation_sha256: str

    @property
    def candidate(self) -> CandidateVersion:
        return self.core.candidate

    @property
    def split(self) -> EvaluationSplit:
        return self.core.split

    @property
    def dataset_sha256(self) -> str:
        return self.core.dataset_sha256

    @property
    def case_ids(self) -> tuple[str, ...]:
        return self.core.case_ids


def evaluate_net_candidate(
    candidate: CandidateVersion,
    cohort: LearningCohort,
    predictions: Iterable[CandidatePrediction],
    *,
    split: EvaluationSplit | str,
    walk_forward_fold_id: str | None = None,
) -> NetCandidateEvaluation:
    """Run normal Phase-7 validation, then calculate admitted net-R metrics."""

    pred_items = tuple(predictions)
    core = evaluate_candidate(
        candidate,
        cohort,
        pred_items,
        split=split,
        walk_forward_fold_id=walk_forward_fold_id,
    )
    pred_lookup = {item.case_id: item for item in pred_items}
    admitted = []
    for case in cohort.cases:
        pred = pred_lookup[case.case_id]
        direction = _enum_value(getattr(case.setup, "direction", ""))
        if direction == "long" and pred.predicted_severe:
            continue
        admitted.append(case)

    net_values: list[float] = []
    resolved_count = 0
    costed_count = 0
    for case in admitted:
        state = _enum_value(getattr(case.outcome, "state", ""))
        if state not in {"tp_first", "sl_first"}:
            continue
        resolved_count += 1
        net = getattr(case.outcome, "realized_net_r", None)
        applied = bool(getattr(case.outcome, "cost_model_applied", False))
        if applied and net is not None and math.isfinite(float(net)):
            costed_count += 1
            net_values.append(float(net))

    wins = [value for value in net_values if value > 0]
    losses = [value for value in net_values if value < 0]
    profit_factor = None
    if losses:
        profit_factor = sum(wins) / abs(sum(losses))
    drawdown = None
    if net_values:
        cumulative = 0.0
        peak = 0.0
        worst = 0.0
        for value in net_values:
            cumulative += value
            peak = max(peak, cumulative)
            worst = max(worst, peak - cumulative)
        drawdown = worst

    metrics = NetEvaluationMetrics(
        admitted_cases=len(admitted),
        resolved_trade_count=resolved_count,
        costed_resolved_trade_count=costed_count,
        net_cost_coverage_ratio=(costed_count / resolved_count if resolved_count else 0.0),
        expectancy_net_r=(mean(net_values) if net_values else None),
        profit_factor_net=profit_factor,
        max_drawdown_net_r=drawdown,
        total_net_r=(sum(net_values) if net_values else None),
    )
    digest = _hash(
        {
            "core_evaluation_sha256": core.evaluation_sha256,
            "metrics": metrics,
        }
    )
    return NetCandidateEvaluation(core=core, metrics=metrics, evaluation_sha256=digest)


@dataclass(frozen=True)
class NetCandidateComparison:
    champion_version: str
    challenger_version: str
    dataset_sha256: str
    case_ids: tuple[str, ...]
    expectancy_net_delta_r: float | None
    profit_factor_net_delta: float | None
    max_drawdown_net_delta_r: float | None
    total_net_delta_r: float | None
    benefits: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    comparison_sha256: str


def _delta(challenger: float | None, champion: float | None) -> float | None:
    if challenger is None or champion is None:
        return None
    return challenger - champion


def compare_net_candidates(
    champion: NetCandidateEvaluation,
    challenger: NetCandidateEvaluation,
) -> NetCandidateComparison:
    if champion.candidate.role is not CandidateRole.CHAMPION:
        raise ValueError("champion net evaluation must use CandidateRole.CHAMPION")
    if challenger.candidate.role is not CandidateRole.CHALLENGER:
        raise ValueError("challenger net evaluation must use CandidateRole.CHALLENGER")
    if challenger.candidate.parent_version != champion.candidate.version:
        raise ValueError("challenger parent_version must equal champion version")
    if champion.dataset_sha256 != challenger.dataset_sha256 or champion.case_ids != challenger.case_ids:
        raise ValueError("net A/B comparison requires the identical dataset/case ordering")
    if champion.split != challenger.split:
        raise ValueError("net A/B comparison requires the same split")

    cm = champion.metrics
    xm = challenger.metrics
    expectancy = _delta(xm.expectancy_net_r, cm.expectancy_net_r)
    pf = _delta(xm.profit_factor_net, cm.profit_factor_net)
    drawdown = _delta(xm.max_drawdown_net_r, cm.max_drawdown_net_r)
    total = _delta(xm.total_net_r, cm.total_net_r)

    benefits: list[str] = []
    tradeoffs: list[str] = []
    if expectancy is not None and expectancy != 0:
        (benefits if expectancy > 0 else tradeoffs).append(
            f"net expectancy delta {expectancy:+.4f} R"
        )
    if pf is not None and pf != 0:
        (benefits if pf > 0 else tradeoffs).append(
            f"net profit-factor delta {pf:+.4f}"
        )
    if drawdown is not None and drawdown != 0:
        (benefits if drawdown < 0 else tradeoffs).append(
            f"net max-drawdown delta {drawdown:+.4f} R"
        )
    if total is not None and total != 0:
        (benefits if total > 0 else tradeoffs).append(
            f"total net-R delta {total:+.4f} R"
        )

    core = {
        "champion_version": champion.candidate.version,
        "challenger_version": challenger.candidate.version,
        "dataset_sha256": champion.dataset_sha256,
        "case_ids": champion.case_ids,
        "expectancy_net_delta_r": expectancy,
        "profit_factor_net_delta": pf,
        "max_drawdown_net_delta_r": drawdown,
        "total_net_delta_r": total,
        "benefits": tuple(benefits),
        "tradeoffs": tuple(tradeoffs),
    }
    return NetCandidateComparison(**core, comparison_sha256=_hash(core))


class NetPromotionState(str, Enum):
    HOLD_CHAMPION = "hold_champion"
    ELIGIBLE_FOR_HUMAN_REVIEW = "eligible_for_human_review"


@dataclass(frozen=True)
class NetPromotionAssessment:
    state: NetPromotionState
    comparison: NetCandidateComparison
    blockers: tuple[str, ...]
    assessment_sha256: str


def assess_net_promotion(
    champion: NetCandidateEvaluation,
    challenger: NetCandidateEvaluation,
    *,
    base_promotion_state: object,
) -> NetPromotionAssessment:
    """Add a net-of-cost gate on top of the existing Phase-7 promotion result."""

    comparison = compare_net_candidates(champion, challenger)
    blockers: list[str] = []
    state_value = _enum_value(base_promotion_state)
    if state_value != "eligible_for_human_review":
        blockers.append("base_phase7_promotion_not_review_eligible")
    if champion.metrics.net_cost_coverage_ratio != 1.0:
        blockers.append("champion_resolved_cost_coverage_incomplete")
    if challenger.metrics.net_cost_coverage_ratio != 1.0:
        blockers.append("challenger_resolved_cost_coverage_incomplete")
    if not comparison.benefits:
        blockers.append("no_measured_net_challenger_benefit")

    state = (
        NetPromotionState.ELIGIBLE_FOR_HUMAN_REVIEW
        if not blockers
        else NetPromotionState.HOLD_CHAMPION
    )
    core = {
        "state": state,
        "comparison_sha256": comparison.comparison_sha256,
        "blockers": tuple(blockers),
    }
    return NetPromotionAssessment(
        state=state,
        comparison=comparison,
        blockers=tuple(blockers),
        assessment_sha256=_hash(core),
    )
