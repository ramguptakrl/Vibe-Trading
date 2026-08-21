"""Deliberate champion/challenger promotion governance for TradeBrain Phase 7.

A challenger can at most become *eligible for human review*. This module never
mutates a production policy, never changes hard rules, and never marks a model
promoted without an explicit human approval record. Promotion/assessment records
can be appended to Vibe's existing hash-chained governance ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from src.tradebrain.learning import (
    CandidateEvaluation,
    CandidateRole,
    WalkForwardSummary,
)

__all__ = [
    "CandidateComparison",
    "ManualPromotionRecord",
    "PromotionAssessment",
    "PromotionPolicy",
    "PromotionState",
    "append_manual_promotion_record",
    "append_promotion_assessment",
    "approve_challenger",
    "assess_promotion",
    "compare_candidates",
]


class PromotionState(str, Enum):
    HOLD_CHAMPION = "hold_champion"
    ELIGIBLE_FOR_HUMAN_REVIEW = "eligible_for_human_review"


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _hash(value: object) -> str:
    body = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256(body.encode("utf-8")).hexdigest()


def _delta(challenger: float | None, champion: float | None) -> float | None:
    if challenger is None or champion is None:
        return None
    return challenger - champion


@dataclass(frozen=True)
class CandidateComparison:
    champion_version: str
    champion_sha256: str
    challenger_version: str
    challenger_sha256: str
    family: str
    split: str
    dataset_sha256: str
    case_ids: tuple[str, ...]
    champion_evaluation_sha256: str
    challenger_evaluation_sha256: str
    expectancy_delta_r: float | None
    hit_rate_delta: float | None
    profit_factor_delta: float | None
    max_drawdown_delta_r: float | None
    mean_mae_delta_r: float | None
    mean_mfe_delta_r: float | None
    median_time_to_target_delta_seconds: float | None
    trade_frequency_delta_per_day: float | None
    crash_precision_delta: float | None
    crash_recall_delta: float | None
    crash_false_positive_rate_delta: float | None
    blocked_winner_delta: int
    blocked_loser_delta: int
    admitted_case_delta: int
    benefits: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    comparison_sha256: str


def compare_candidates(
    champion: CandidateEvaluation,
    challenger: CandidateEvaluation,
) -> CandidateComparison:
    """Compare A/B on the exact same cases and split or fail closed."""

    if champion.candidate.role is not CandidateRole.CHAMPION:
        raise ValueError("champion evaluation must use CandidateRole.CHAMPION")
    if challenger.candidate.role is not CandidateRole.CHALLENGER:
        raise ValueError("challenger evaluation must use CandidateRole.CHALLENGER")
    if champion.candidate.family != challenger.candidate.family:
        raise ValueError("champion and challenger must belong to the same family")
    if challenger.candidate.parent_version != champion.candidate.version:
        raise ValueError("challenger parent_version must equal champion version")
    if champion.split != challenger.split:
        raise ValueError("A/B evaluations must use the same split")
    if champion.dataset_sha256 != challenger.dataset_sha256:
        raise ValueError("A/B evaluations must use the identical dataset fingerprint")
    if champion.case_ids != challenger.case_ids:
        raise ValueError("A/B evaluations must use the identical ordered case set")

    cm = champion.metrics
    xm = challenger.metrics
    expectancy = _delta(xm.expectancy_gross_r, cm.expectancy_gross_r)
    hit_rate = _delta(xm.hit_rate, cm.hit_rate)
    profit_factor = _delta(xm.profit_factor, cm.profit_factor)
    drawdown = _delta(xm.max_drawdown_r, cm.max_drawdown_r)
    mae = _delta(xm.mean_mae_r, cm.mean_mae_r)
    mfe = _delta(xm.mean_mfe_r, cm.mean_mfe_r)
    time_to_target = _delta(
        xm.median_time_to_target_seconds, cm.median_time_to_target_seconds
    )
    trade_frequency = _delta(
        xm.trade_frequency_per_day, cm.trade_frequency_per_day
    )
    precision = _delta(xm.crash_precision, cm.crash_precision)
    recall = _delta(xm.crash_recall, cm.crash_recall)
    fpr = _delta(xm.crash_false_positive_rate, cm.crash_false_positive_rate)
    blocked_winner_delta = xm.blocked_tp_first - cm.blocked_tp_first
    blocked_loser_delta = xm.blocked_sl_first - cm.blocked_sl_first
    admitted_delta = xm.admitted_cases - cm.admitted_cases

    benefits: list[str] = []
    tradeoffs: list[str] = []
    if expectancy is not None and expectancy != 0:
        (benefits if expectancy > 0 else tradeoffs).append(
            f"gross expectancy delta {expectancy:+.4f} R"
        )
    if hit_rate is not None and hit_rate != 0:
        (benefits if hit_rate > 0 else tradeoffs).append(
            f"hit-rate delta {hit_rate:+.4f}"
        )
    if profit_factor is not None and profit_factor != 0:
        (benefits if profit_factor > 0 else tradeoffs).append(
            f"profit-factor delta {profit_factor:+.4f}"
        )
    if drawdown is not None and drawdown != 0:
        (benefits if drawdown < 0 else tradeoffs).append(
            f"max-drawdown delta {drawdown:+.4f} R"
        )
    if mae is not None and mae != 0:
        (benefits if mae > 0 else tradeoffs).append(
            f"mean-MAE delta {mae:+.4f} R"
        )
    if mfe is not None and mfe != 0:
        (benefits if mfe > 0 else tradeoffs).append(
            f"mean-MFE delta {mfe:+.4f} R"
        )
    if time_to_target is not None and time_to_target != 0:
        (benefits if time_to_target < 0 else tradeoffs).append(
            f"median time-to-target delta {time_to_target:+.1f}s"
        )
    if fpr is not None and fpr != 0:
        (benefits if fpr < 0 else tradeoffs).append(
            f"Crash Guard false-positive-rate delta {fpr:+.4f}"
        )
    if recall is not None and recall != 0:
        (benefits if recall > 0 else tradeoffs).append(
            f"Crash Guard recall delta {recall:+.4f}"
        )
    if blocked_winner_delta > 0:
        tradeoffs.append(f"blocked {blocked_winner_delta} additional TP-first long plan(s)")
    elif blocked_winner_delta < 0:
        benefits.append(f"blocked {-blocked_winner_delta} fewer TP-first long plan(s)")
    if blocked_loser_delta > 0:
        benefits.append(f"blocked {blocked_loser_delta} additional SL-first long plan(s)")
    elif blocked_loser_delta < 0:
        tradeoffs.append(f"blocked {-blocked_loser_delta} fewer SL-first long plan(s)")
    if admitted_delta != 0:
        tradeoffs.append(f"admitted-case delta {admitted_delta:+d} case(s); review frequency impact")
    if trade_frequency is not None and trade_frequency != 0:
        tradeoffs.append(
            f"trade-frequency delta {trade_frequency:+.4f} admitted cases/day; directional preference is not assumed"
        )

    core = {
        "champion_version": champion.candidate.version,
        "champion_sha256": champion.candidate.sha256,
        "challenger_version": challenger.candidate.version,
        "challenger_sha256": challenger.candidate.sha256,
        "family": champion.candidate.family,
        "split": champion.split.value,
        "dataset_sha256": champion.dataset_sha256,
        "case_ids": champion.case_ids,
        "champion_evaluation_sha256": champion.evaluation_sha256,
        "challenger_evaluation_sha256": challenger.evaluation_sha256,
        "expectancy_delta_r": expectancy,
        "hit_rate_delta": hit_rate,
        "profit_factor_delta": profit_factor,
        "max_drawdown_delta_r": drawdown,
        "mean_mae_delta_r": mae,
        "mean_mfe_delta_r": mfe,
        "median_time_to_target_delta_seconds": time_to_target,
        "trade_frequency_delta_per_day": trade_frequency,
        "crash_precision_delta": precision,
        "crash_recall_delta": recall,
        "crash_false_positive_rate_delta": fpr,
        "blocked_winner_delta": blocked_winner_delta,
        "blocked_loser_delta": blocked_loser_delta,
        "admitted_case_delta": admitted_delta,
        "benefits": tuple(benefits),
        "tradeoffs": tuple(tradeoffs),
    }
    return CandidateComparison(**core, comparison_sha256=_hash(core))


@dataclass(frozen=True)
class PromotionPolicy:
    """Evidence-completeness gate, not a profitability threshold."""

    version: str = "phase7-governance-v1"
    require_out_of_sample: bool = True
    require_walk_forward: bool = True
    require_real_history: bool = True
    require_no_lookahead: bool = True
    require_cost_model: bool = True
    require_ordinary_and_severe_sessions: bool = True
    min_oos_cases: int = 30
    min_walk_forward_folds: int = 3
    min_regimes: int = 2
    min_subperiods: int = 2

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("promotion policy version is required")
        for name in (
            "min_oos_cases",
            "min_walk_forward_folds",
            "min_regimes",
            "min_subperiods",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass(frozen=True)
class PromotionAssessment:
    state: PromotionState
    policy_version: str
    comparison: CandidateComparison
    blockers: tuple[str, ...]
    review_notes: tuple[str, ...]
    human_approval_required: bool
    promoted: bool
    assessment_sha256: str


def assess_promotion(
    comparison: CandidateComparison,
    champion: CandidateEvaluation,
    challenger: CandidateEvaluation,
    *,
    policy: PromotionPolicy | None = None,
    champion_walk_forward: WalkForwardSummary | None = None,
    challenger_walk_forward: WalkForwardSummary | None = None,
    ordinary_case_count: int = 0,
    severe_case_count: int = 0,
) -> PromotionAssessment:
    """Gate a challenger. Passing means reviewable, never automatically promoted."""

    policy = PromotionPolicy() if policy is None else policy
    blockers: list[str] = []
    notes: list[str] = []

    if comparison.comparison_sha256 != compare_candidates(champion, challenger).comparison_sha256:
        raise ValueError("comparison does not match supplied evaluations")

    if not comparison.benefits:
        blockers.append("no_measured_challenger_benefit")

    if policy.require_out_of_sample and champion.split.value != "out_of_sample":
        blockers.append("comparison_not_out_of_sample")
    if champion.metrics.cases_total < policy.min_oos_cases:
        blockers.append("insufficient_oos_case_count")
    if policy.require_real_history and (
        not champion.all_real_history or not challenger.all_real_history
    ):
        blockers.append("synthetic_or_nonreal_history_present")
    if policy.require_no_lookahead and (
        not champion.no_lookahead_verified
        or not challenger.no_lookahead_verified
    ):
        blockers.append("no_lookahead_not_verified")
    if policy.require_cost_model and (
        not champion.costs_complete or not challenger.costs_complete
    ):
        blockers.append("cost_model_not_complete")
    if policy.require_ordinary_and_severe_sessions:
        if ordinary_case_count < 1:
            blockers.append("ordinary_sessions_missing")
        if severe_case_count < 1:
            blockers.append("severe_sessions_missing")

    if len(champion.by_regime) < policy.min_regimes or len(challenger.by_regime) < policy.min_regimes:
        blockers.append("insufficient_regime_coverage")
    if (
        len(champion.by_subperiod) < policy.min_subperiods
        or len(challenger.by_subperiod) < policy.min_subperiods
    ):
        blockers.append("insufficient_subperiod_coverage")

    if policy.require_walk_forward:
        if champion_walk_forward is None or challenger_walk_forward is None:
            blockers.append("walk_forward_missing")
        else:
            if champion_walk_forward.folds_sha256 != challenger_walk_forward.folds_sha256:
                blockers.append("walk_forward_folds_differ")
            if champion_walk_forward.fold_count < policy.min_walk_forward_folds:
                blockers.append("insufficient_walk_forward_folds")
            if (
                champion_walk_forward.candidate_version != champion.candidate.version
                or challenger_walk_forward.candidate_version != challenger.candidate.version
            ):
                blockers.append("walk_forward_candidate_mismatch")
            if policy.require_real_history and (
                not champion_walk_forward.all_real_history
                or not challenger_walk_forward.all_real_history
            ):
                blockers.append("walk_forward_not_all_real_history")
            if policy.require_no_lookahead and (
                not champion_walk_forward.no_lookahead_verified
                or not challenger_walk_forward.no_lookahead_verified
            ):
                blockers.append("walk_forward_no_lookahead_not_verified")
            if policy.require_cost_model and (
                not champion_walk_forward.costs_complete
                or not challenger_walk_forward.costs_complete
            ):
                blockers.append("walk_forward_costs_incomplete")

    if comparison.benefits:
        notes.extend(f"benefit: {item}" for item in comparison.benefits)
    if comparison.tradeoffs:
        notes.extend(f"tradeoff: {item}" for item in comparison.tradeoffs)
    if not comparison.benefits:
        notes.append("no measured benefit was established on the supplied comparison")
    if not comparison.tradeoffs:
        notes.append("no measured tradeoff was detected on the supplied comparison")

    state = (
        PromotionState.HOLD_CHAMPION
        if blockers
        else PromotionState.ELIGIBLE_FOR_HUMAN_REVIEW
    )
    payload = {
        "state": state,
        "policy_version": policy.version,
        "comparison_sha256": comparison.comparison_sha256,
        "blockers": tuple(dict.fromkeys(blockers)),
        "review_notes": tuple(notes),
        "human_approval_required": True,
        "promoted": False,
    }
    return PromotionAssessment(
        state=state,
        policy_version=policy.version,
        comparison=comparison,
        blockers=payload["blockers"],
        review_notes=payload["review_notes"],
        human_approval_required=True,
        promoted=False,
        assessment_sha256=_hash(payload),
    )


@dataclass(frozen=True)
class ManualPromotionRecord:
    prior_champion_version: str
    promoted_challenger_version: str
    challenger_sha256: str
    comparison_sha256: str
    assessment_sha256: str
    approved_by: str
    approved_at: str
    approval_note: str
    hard_rules_modified: bool
    auto_execution_enabled: bool
    record_sha256: str


def approve_challenger(
    assessment: PromotionAssessment,
    *,
    approved_by: str,
    approved_at: str | datetime,
    approval_note: str,
) -> ManualPromotionRecord:
    """Create an explicit human promotion record; does not mutate runtime config."""

    if assessment.state is not PromotionState.ELIGIBLE_FOR_HUMAN_REVIEW:
        raise ValueError("challenger is not eligible for human promotion review")
    if assessment.blockers:
        raise ValueError("cannot approve a challenger with promotion blockers")
    approver = str(approved_by or "").strip()
    note = str(approval_note or "").strip()
    if not approver:
        raise ValueError("approved_by is required")
    if not note:
        raise ValueError("approval_note is required")
    if isinstance(approved_at, datetime):
        stamp = approved_at
    else:
        stamp = datetime.fromisoformat(str(approved_at).strip().replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("approved_at must be timezone-aware")

    comp = assessment.comparison
    payload = {
        "prior_champion_version": comp.champion_version,
        "promoted_challenger_version": comp.challenger_version,
        "challenger_sha256": comp.challenger_sha256,
        "comparison_sha256": comp.comparison_sha256,
        "assessment_sha256": assessment.assessment_sha256,
        "approved_by": approver,
        "approved_at": stamp.isoformat(),
        "approval_note": note,
        "hard_rules_modified": False,
        "auto_execution_enabled": False,
    }
    return ManualPromotionRecord(**payload, record_sha256=_hash(payload))


def append_promotion_assessment(path: str | Path, assessment: PromotionAssessment) -> dict:
    """Append the assessment to Vibe's existing tamper-evident governance ledger."""

    from src.governance.ledger import append_record

    return append_record(
        Path(path),
        {
            "event_type": "tradebrain_bse_promotion_assessment",
            "policy_version": assessment.policy_version,
            "state": assessment.state.value,
            "comparison_sha256": assessment.comparison.comparison_sha256,
            "assessment_sha256": assessment.assessment_sha256,
            "blockers": list(assessment.blockers),
            "review_notes": list(assessment.review_notes),
            "promoted": False,
        },
    )


def append_manual_promotion_record(path: str | Path, record: ManualPromotionRecord) -> dict:
    """Append a deliberate approval record. It still does not mutate runtime policy."""

    from src.governance.ledger import append_record

    return append_record(
        Path(path),
        {
            "event_type": "tradebrain_bse_manual_promotion",
            "prior_champion_version": record.prior_champion_version,
            "promoted_challenger_version": record.promoted_challenger_version,
            "challenger_sha256": record.challenger_sha256,
            "comparison_sha256": record.comparison_sha256,
            "assessment_sha256": record.assessment_sha256,
            "approved_by": record.approved_by,
            "approved_at": record.approved_at,
            "approval_note": record.approval_note,
            "hard_rules_modified": record.hard_rules_modified,
            "auto_execution_enabled": record.auto_execution_enabled,
            "record_sha256": record.record_sha256,
        },
    )
