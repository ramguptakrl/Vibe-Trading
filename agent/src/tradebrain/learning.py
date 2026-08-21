"""Controlled BSE learning / calibration foundation for TradeBrain Phase 7.

This module consumes immutable Phase-6 plan/outcome/replay records. It does not
generate entries, mutate hard rules, or auto-promote a challenger. Candidate
predictions are evaluated on an identical, fingerprinted cohort so benefits and
trade-offs can be inspected before any deliberate promotion decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import math
from statistics import mean, median
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

__all__ = [
    "CandidateEvaluation",
    "CandidatePrediction",
    "CandidateRole",
    "CandidateVersion",
    "DataOrigin",
    "EvaluationMetrics",
    "EvaluationSplit",
    "LearningCase",
    "LearningCohort",
    "MetricSlice",
    "SessionClass",
    "WalkForwardFold",
    "WalkForwardSummary",
    "build_learning_case",
    "build_learning_cohort",
    "build_walk_forward_folds",
    "evaluate_candidate",
    "evaluate_walk_forward",
    "make_candidate_prediction",
    "summarize_walk_forward",
    "validate_learning_case_integrity",
]


class CandidateRole(str, Enum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"


class EvaluationSplit(str, Enum):
    IN_SAMPLE = "in_sample"
    VALIDATION = "validation"
    OUT_OF_SAMPLE = "out_of_sample"


class DataOrigin(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class SessionClass(str, Enum):
    ORDINARY = "ordinary"
    SEVERE = "severe"
    OTHER = "other"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _aware(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _hash(payload: object) -> str:
    body = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256(body.encode("utf-8")).hexdigest()


def _required_text(value: str, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def _freeze_parameter(value: object) -> object:
    """Recursively freeze candidate parameters so a version cannot drift after hashing."""

    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze_parameter(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        })
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_parameter(item) for item in value)
    if isinstance(value, set):
        frozen = tuple(_freeze_parameter(item) for item in value)
        return tuple(sorted(frozen, key=lambda item: json.dumps(_canonical(item), sort_keys=True, default=str)))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"unsupported mutable/opaque candidate parameter type: {type(value).__name__}")


@dataclass(frozen=True)
class CandidateVersion:
    """Versioned soft-parameter candidate. Hard-rule changes are forbidden."""

    version: str
    family: str
    role: CandidateRole | str
    parameters: Mapping[str, object]
    change_summary: tuple[str, ...] = ()
    parent_version: str | None = None
    hard_rule_changes: tuple[str, ...] = ()
    research_only: bool = True
    learned: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _required_text(self.version, "version"))
        object.__setattr__(self, "family", _required_text(self.family, "family"))
        role = self.role if isinstance(self.role, CandidateRole) else CandidateRole(str(self.role))
        object.__setattr__(self, "role", role)
        params = dict(self.parameters)
        if not params:
            raise ValueError("candidate parameters cannot be empty")
        frozen_params = {
            str(key): _freeze_parameter(item)
            for key, item in sorted(params.items(), key=lambda item: str(item[0]))
        }
        object.__setattr__(self, "parameters", MappingProxyType(frozen_params))
        changes = tuple(_required_text(item, "change_summary item") for item in self.change_summary)
        object.__setattr__(self, "change_summary", changes)
        hard = tuple(_required_text(item, "hard_rule_changes item") for item in self.hard_rule_changes)
        object.__setattr__(self, "hard_rule_changes", hard)
        if hard:
            raise ValueError("Phase 7 learning cannot modify hard owner/exchange/broker rules")
        if role is CandidateRole.CHALLENGER:
            if not self.parent_version or not str(self.parent_version).strip():
                raise ValueError("challenger requires parent_version")
            if str(self.parent_version).strip() == self.version:
                raise ValueError("challenger version must differ from parent_version")
            if not changes:
                raise ValueError("challenger requires an explicit change_summary")
        if self.learned:
            raise ValueError(
                "Phase 7 candidate definitions are research candidates; learned=True requires a later deliberate promotion record"
            )
        if not self.research_only:
            raise ValueError("Phase 7 candidates must remain research_only")

    @property
    def sha256(self) -> str:
        return _hash(
            {
                "version": self.version,
                "family": self.family,
                "role": self.role,
                "parameters": dict(self.parameters),
                "change_summary": self.change_summary,
                "parent_version": self.parent_version,
                "hard_rule_changes": self.hard_rule_changes,
                "research_only": self.research_only,
                "learned": self.learned,
            }
        )


@dataclass(frozen=True)
class LearningCase:
    """One immutable historical observation linked to Phase-6 truth."""

    case_id: str
    setup: object
    outcome: object
    crash_case: object
    regime: str
    subperiod: str
    session_class: SessionClass | str
    data_origin: DataOrigin | str
    no_lookahead_verified: bool
    case_sha256: str
    notes: tuple[str, ...] = ()

    @property
    def decision_at(self) -> str:
        return str(getattr(self.setup, "decision_at"))

    @property
    def costs_known(self) -> bool:
        return bool(
            getattr(self.setup, "costs_known", False)
            and getattr(self.outcome, "cost_model_applied", False)
        )


def _learning_case_payload(
    *,
    case_id: str,
    setup: object,
    outcome: object,
    crash_case: object,
    regime: str,
    subperiod: str,
    session_class: SessionClass,
    data_origin: DataOrigin,
    no_lookahead_verified: bool,
    notes: tuple[str, ...],
) -> dict[str, object]:
    """Hash every field Phase-7 metrics/governance can consume from a case."""

    return {
        "case_id": case_id,
        "setup": {
            "setup_id": str(getattr(setup, "setup_id", "")),
            "snapshot_sha256": str(getattr(setup, "snapshot_sha256", "")),
            "decision_at": str(getattr(setup, "decision_at", "")),
            "direction": _enum_value(getattr(setup, "direction", "")),
            "costs_known": bool(getattr(setup, "costs_known", False)),
        },
        "outcome": {
            "setup_id": str(getattr(outcome, "setup_id", "")),
            "setup_sha256": str(getattr(outcome, "setup_sha256", "")),
            "state": _enum_value(getattr(outcome, "state", "")),
            "replay_source_frame_sha256": str(getattr(outcome, "replay_source_frame_sha256", "")),
            "realized_gross_r": getattr(outcome, "realized_gross_r", None),
            "mae_r": getattr(outcome, "mae_r", None),
            "mfe_r": getattr(outcome, "mfe_r", None),
            "time_to_target_seconds": getattr(outcome, "time_to_target_seconds", None),
            "terminal_mark_r": getattr(outcome, "terminal_mark_r", None),
            "cost_model_applied": bool(getattr(outcome, "cost_model_applied", False)),
        },
        "crash_case": {
            "setup_id": str(getattr(crash_case, "setup_id", "")),
            "setup_sha256": str(getattr(crash_case, "setup_sha256", "")),
            "label": _enum_value(getattr(crash_case, "label", "")),
            "replay_source_frame_sha256": str(getattr(crash_case, "replay_source_frame_sha256", "")),
        },
        "regime": regime,
        "subperiod": subperiod,
        "session_class": session_class,
        "data_origin": data_origin,
        "no_lookahead_verified": bool(no_lookahead_verified),
        "notes": notes,
    }


def validate_learning_case_integrity(case: LearningCase) -> None:
    """Fail closed if any Phase-6-derived field used by learning drifted after hashing."""

    payload = _learning_case_payload(
        case_id=case.case_id,
        setup=case.setup,
        outcome=case.outcome,
        crash_case=case.crash_case,
        regime=case.regime,
        subperiod=case.subperiod,
        session_class=(case.session_class if isinstance(case.session_class, SessionClass) else SessionClass(str(case.session_class))),
        data_origin=(case.data_origin if isinstance(case.data_origin, DataOrigin) else DataOrigin(str(case.data_origin))),
        no_lookahead_verified=case.no_lookahead_verified,
        notes=case.notes,
    )
    if _hash(payload) != case.case_sha256:
        raise ValueError(f"learning case {case.case_id!r} SHA-256 does not match its fields")


def build_learning_case(
    setup: object,
    outcome: object,
    crash_case: object,
    *,
    case_id: str | None = None,
    regime: str,
    subperiod: str,
    session_class: SessionClass | str,
    data_origin: DataOrigin | str,
    no_lookahead_verified: bool,
    notes: Iterable[str] = (),
) -> LearningCase:
    """Bind Phase-6 records into a tamper-evident Phase-7 research case."""

    setup_id = _required_text(str(getattr(setup, "setup_id", "")), "setup.setup_id")
    setup_sha = _required_text(
        str(getattr(setup, "snapshot_sha256", "")), "setup.snapshot_sha256"
    )
    if str(getattr(outcome, "setup_id", "")) != setup_id:
        raise ValueError("outcome setup_id does not match setup")
    if str(getattr(crash_case, "setup_id", "")) != setup_id:
        raise ValueError("Crash replay setup_id does not match setup")
    if str(getattr(outcome, "setup_sha256", "")) != setup_sha:
        raise ValueError("outcome setup SHA-256 does not match setup")
    if str(getattr(crash_case, "setup_sha256", "")) != setup_sha:
        raise ValueError("Crash replay setup SHA-256 does not match setup")
    _aware(str(getattr(setup, "decision_at", "")), "setup.decision_at")
    regime = _required_text(regime, "regime")
    subperiod = _required_text(subperiod, "subperiod")
    session = (
        session_class
        if isinstance(session_class, SessionClass)
        else SessionClass(str(session_class))
    )
    origin = data_origin if isinstance(data_origin, DataOrigin) else DataOrigin(str(data_origin))
    cid = _required_text(case_id or setup_id, "case_id")
    note_tuple = tuple(str(item).strip() for item in notes if str(item).strip())
    payload = _learning_case_payload(
        case_id=cid,
        setup=setup,
        outcome=outcome,
        crash_case=crash_case,
        regime=regime,
        subperiod=subperiod,
        session_class=session,
        data_origin=origin,
        no_lookahead_verified=bool(no_lookahead_verified),
        notes=note_tuple,
    )
    return LearningCase(
        case_id=cid,
        setup=setup,
        outcome=outcome,
        crash_case=crash_case,
        regime=regime,
        subperiod=subperiod,
        session_class=session,
        data_origin=origin,
        no_lookahead_verified=bool(no_lookahead_verified),
        case_sha256=_hash(payload),
        notes=note_tuple,
    )


@dataclass(frozen=True)
class LearningCohort:
    cases: tuple[LearningCase, ...]
    dataset_sha256: str
    case_ids: tuple[str, ...]
    real_case_count: int
    synthetic_case_count: int
    ordinary_case_count: int
    severe_case_count: int

    @property
    def all_real(self) -> bool:
        return self.synthetic_case_count == 0

    @property
    def no_lookahead_verified(self) -> bool:
        return all(case.no_lookahead_verified for case in self.cases)


def build_learning_cohort(cases: Iterable[LearningCase]) -> LearningCohort:
    """Create an order-stable fingerprint so A/B comparisons use identical data."""

    items = tuple(sorted(cases, key=lambda c: (_aware(c.decision_at, "decision_at"), c.case_id)))
    if not items:
        raise ValueError("learning cohort cannot be empty")
    for case in items:
        validate_learning_case_integrity(case)
    ids = tuple(case.case_id for case in items)
    if len(set(ids)) != len(ids):
        raise ValueError("learning cohort case_id values must be unique")
    fingerprint = _hash(
        [
            {
                "case_id": case.case_id,
                "case_sha256": case.case_sha256,
                "decision_at": case.decision_at,
            }
            for case in items
        ]
    )
    return LearningCohort(
        cases=items,
        dataset_sha256=fingerprint,
        case_ids=ids,
        real_case_count=sum(case.data_origin is DataOrigin.REAL for case in items),
        synthetic_case_count=sum(case.data_origin is DataOrigin.SYNTHETIC for case in items),
        ordinary_case_count=sum(
            case.session_class is SessionClass.ORDINARY for case in items
        ),
        severe_case_count=sum(case.session_class is SessionClass.SEVERE for case in items),
    )


@dataclass(frozen=True)
class CandidatePrediction:
    case_id: str
    case_sha256: str
    candidate_version: str
    candidate_sha256: str
    predicted_severe: bool
    rationale: tuple[str, ...] = ()
    prediction_sha256: str = ""


def make_candidate_prediction(
    candidate: CandidateVersion,
    case: LearningCase,
    *,
    predicted_severe: bool,
    rationale: Iterable[str] = (),
) -> CandidatePrediction:
    reasons = tuple(str(item).strip() for item in rationale if str(item).strip())
    payload = {
        "case_id": case.case_id,
        "case_sha256": case.case_sha256,
        "candidate_version": candidate.version,
        "candidate_sha256": candidate.sha256,
        "predicted_severe": bool(predicted_severe),
        "rationale": reasons,
    }
    return CandidatePrediction(
        case_id=case.case_id,
        case_sha256=case.case_sha256,
        candidate_version=candidate.version,
        candidate_sha256=candidate.sha256,
        predicted_severe=bool(predicted_severe),
        rationale=reasons,
        prediction_sha256=_hash(payload),
    )


@dataclass(frozen=True)
class EvaluationMetrics:
    cases_total: int
    usable_outcomes: int
    admitted_cases: int
    blocked_long_cases: int
    tp_first: int
    sl_first: int
    neither: int
    ambiguous_same_bar: int
    data_insufficient: int
    resolved_trade_count: int
    hit_rate: float | None
    expectancy_gross_r: float | None
    profit_factor: float | None
    max_drawdown_r: float | None
    mean_mae_r: float | None
    mean_mfe_r: float | None
    median_time_to_target_seconds: float | None
    mean_terminal_mark_r: float | None
    trade_frequency_per_day: float | None
    blocked_tp_first: int
    blocked_sl_first: int
    crash_true_positive: int
    crash_false_positive: int
    crash_false_negative: int
    crash_true_negative: int
    crash_excluded: int
    crash_precision: float | None
    crash_recall: float | None
    crash_false_positive_rate: float | None
    data_coverage_ratio: float
    cost_coverage_ratio: float


@dataclass(frozen=True)
class MetricSlice:
    label: str
    metrics: EvaluationMetrics


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate: CandidateVersion
    split: EvaluationSplit
    dataset_sha256: str
    case_ids: tuple[str, ...]
    metrics: EvaluationMetrics
    by_regime: tuple[MetricSlice, ...]
    by_subperiod: tuple[MetricSlice, ...]
    all_real_history: bool
    no_lookahead_verified: bool
    costs_complete: bool
    walk_forward_fold_id: str | None = None

    @property
    def evaluation_sha256(self) -> str:
        return _hash(
            {
                "candidate_sha256": self.candidate.sha256,
                "split": self.split,
                "dataset_sha256": self.dataset_sha256,
                "case_ids": self.case_ids,
                "metrics": self.metrics,
                "by_regime": self.by_regime,
                "by_subperiod": self.by_subperiod,
                "all_real_history": self.all_real_history,
                "no_lookahead_verified": self.no_lookahead_verified,
                "costs_complete": self.costs_complete,
                "walk_forward_fold_id": self.walk_forward_fold_id,
            }
        )


def _outcome_value(case: LearningCase) -> str:
    return _enum_value(getattr(case.outcome, "state", "")).lower()


def _direction_value(case: LearningCase) -> str:
    return _enum_value(getattr(case.setup, "direction", "")).lower()


def _label_value(case: LearningCase) -> str:
    return _enum_value(getattr(case.crash_case, "label", "")).lower()


def _is_data_insufficient(case: LearningCase) -> bool:
    return _outcome_value(case) == "data_insufficient"


def _compute_metrics(
    cases: Sequence[LearningCase],
    predictions: Mapping[str, CandidatePrediction],
) -> EvaluationMetrics:
    total = len(cases)
    admitted: list[LearningCase] = []
    blocked: list[LearningCase] = []
    for case in cases:
        pred = predictions[case.case_id]
        block_long = _direction_value(case) == "long" and pred.predicted_severe
        (blocked if block_long else admitted).append(case)

    states = [_outcome_value(case) for case in admitted]
    tp = states.count("tp_first")
    sl = states.count("sl_first")
    neither = states.count("neither")
    ambiguous = states.count("ambiguous_same_bar")
    insufficient = states.count("data_insufficient")
    usable = total - sum(_is_data_insufficient(case) for case in cases)

    realized: list[float] = []
    maes: list[float] = []
    mfes: list[float] = []
    target_times: list[float] = []
    terminal: list[float] = []
    for case in admitted:
        if _is_data_insufficient(case):
            continue
        r = getattr(case.outcome, "realized_gross_r", None)
        if r is not None and math.isfinite(float(r)):
            realized.append(float(r))
        mae = getattr(case.outcome, "mae_r", None)
        if mae is not None and math.isfinite(float(mae)):
            maes.append(float(mae))
        mfe = getattr(case.outcome, "mfe_r", None)
        if mfe is not None and math.isfinite(float(mfe)):
            mfes.append(float(mfe))
        tt = getattr(case.outcome, "time_to_target_seconds", None)
        if tt is not None and math.isfinite(float(tt)):
            target_times.append(float(tt))
        mark = getattr(case.outcome, "terminal_mark_r", None)
        if mark is not None and math.isfinite(float(mark)):
            terminal.append(float(mark))

    wins = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    profit_factor = None
    if losses:
        profit_factor = sum(wins) / abs(sum(losses))
    elif wins:
        profit_factor = None

    drawdown = None
    if realized:
        cumulative = 0.0
        peak = 0.0
        worst = 0.0
        for value in realized:
            cumulative += value
            peak = max(peak, cumulative)
            worst = max(worst, peak - cumulative)
        drawdown = worst

    crash_tp = crash_fp = crash_fn = crash_tn = crash_ex = 0
    for case in cases:
        label = _label_value(case)
        pred = predictions[case.case_id].predicted_severe
        if label == "data_insufficient":
            crash_ex += 1
        elif label == "stress":
            if pred:
                crash_tp += 1
            else:
                crash_fn += 1
        elif label == "no_stress":
            if pred:
                crash_fp += 1
            else:
                crash_tn += 1
        else:
            crash_ex += 1

    precision_den = crash_tp + crash_fp
    recall_den = crash_tp + crash_fn
    fpr_den = crash_fp + crash_tn

    decision_days = {
        _aware(case.decision_at, "decision_at").date()
        for case in admitted
    }
    blocked_tp = sum(_outcome_value(case) == "tp_first" for case in blocked)
    blocked_sl = sum(_outcome_value(case) == "sl_first" for case in blocked)
    cost_known = sum(case.costs_known for case in cases)

    return EvaluationMetrics(
        cases_total=total,
        usable_outcomes=usable,
        admitted_cases=len(admitted),
        blocked_long_cases=len(blocked),
        tp_first=tp,
        sl_first=sl,
        neither=neither,
        ambiguous_same_bar=ambiguous,
        data_insufficient=insufficient,
        resolved_trade_count=len(realized),
        hit_rate=tp / (tp + sl) if tp + sl else None,
        expectancy_gross_r=mean(realized) if realized else None,
        profit_factor=profit_factor,
        max_drawdown_r=drawdown,
        mean_mae_r=mean(maes) if maes else None,
        mean_mfe_r=mean(mfes) if mfes else None,
        median_time_to_target_seconds=median(target_times) if target_times else None,
        mean_terminal_mark_r=mean(terminal) if terminal else None,
        trade_frequency_per_day=(
            len(admitted) / len(decision_days) if decision_days else None
        ),
        blocked_tp_first=blocked_tp,
        blocked_sl_first=blocked_sl,
        crash_true_positive=crash_tp,
        crash_false_positive=crash_fp,
        crash_false_negative=crash_fn,
        crash_true_negative=crash_tn,
        crash_excluded=crash_ex,
        crash_precision=crash_tp / precision_den if precision_den else None,
        crash_recall=crash_tp / recall_den if recall_den else None,
        crash_false_positive_rate=crash_fp / fpr_den if fpr_den else None,
        data_coverage_ratio=usable / total if total else 0.0,
        cost_coverage_ratio=cost_known / total if total else 0.0,
    )


def _slice(
    cases: Sequence[LearningCase],
    predictions: Mapping[str, CandidatePrediction],
    attr: str,
) -> tuple[MetricSlice, ...]:
    groups: dict[str, list[LearningCase]] = {}
    for case in cases:
        groups.setdefault(str(getattr(case, attr)), []).append(case)
    return tuple(
        MetricSlice(label=label, metrics=_compute_metrics(tuple(group), predictions))
        for label, group in sorted(groups.items())
    )


def evaluate_candidate(
    candidate: CandidateVersion,
    cohort: LearningCohort,
    predictions: Iterable[CandidatePrediction],
    *,
    split: EvaluationSplit | str,
    walk_forward_fold_id: str | None = None,
) -> CandidateEvaluation:
    """Evaluate one candidate on a fingerprinted cohort.

    Predictions must cover every case exactly once and must themselves be
    bound to the candidate SHA and case SHA. That prevents accidental A/B
    comparisons on different data or stale candidate output.
    """

    split_value = split if isinstance(split, EvaluationSplit) else EvaluationSplit(str(split))
    for case in cohort.cases:
        validate_learning_case_integrity(case)
    pred_items = tuple(predictions)
    by_id = {item.case_id: item for item in pred_items}
    if len(by_id) != len(pred_items):
        raise ValueError("candidate predictions contain duplicate case_id values")
    if set(by_id) != set(cohort.case_ids):
        raise ValueError("candidate predictions must cover the exact cohort case set")
    case_lookup = {case.case_id: case for case in cohort.cases}
    for case_id, pred in by_id.items():
        case = case_lookup[case_id]
        if pred.case_sha256 != case.case_sha256:
            raise ValueError(f"prediction {case_id!r} is bound to a different case SHA")
        if pred.candidate_version != candidate.version:
            raise ValueError(f"prediction {case_id!r} uses a different candidate version")
        if pred.candidate_sha256 != candidate.sha256:
            raise ValueError(f"prediction {case_id!r} uses a different candidate SHA")
        expected = _hash(
            {
                "case_id": pred.case_id,
                "case_sha256": pred.case_sha256,
                "candidate_version": pred.candidate_version,
                "candidate_sha256": pred.candidate_sha256,
                "predicted_severe": pred.predicted_severe,
                "rationale": pred.rationale,
            }
        )
        if pred.prediction_sha256 != expected:
            raise ValueError(f"prediction {case_id!r} SHA-256 does not match its fields")

    metrics = _compute_metrics(cohort.cases, by_id)
    return CandidateEvaluation(
        candidate=candidate,
        split=split_value,
        dataset_sha256=cohort.dataset_sha256,
        case_ids=cohort.case_ids,
        metrics=metrics,
        by_regime=_slice(cohort.cases, by_id, "regime"),
        by_subperiod=_slice(cohort.cases, by_id, "subperiod"),
        all_real_history=cohort.all_real,
        no_lookahead_verified=cohort.no_lookahead_verified,
        costs_complete=(metrics.cost_coverage_ratio == 1.0),
        walk_forward_fold_id=walk_forward_fold_id,
    )


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: str
    train_case_ids: tuple[str, ...]
    test_case_ids: tuple[str, ...]
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    def __post_init__(self) -> None:
        if not self.train_case_ids or not self.test_case_ids:
            raise ValueError("walk-forward fold requires non-empty train and test sets")
        if set(self.train_case_ids) & set(self.test_case_ids):
            raise ValueError("walk-forward train/test case sets must not overlap")
        if _aware(self.train_end, "train_end") >= _aware(self.test_start, "test_start"):
            raise ValueError("walk-forward test period must start after train period ends")


def build_walk_forward_folds(
    cohort: LearningCohort,
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    expanding: bool = True,
) -> tuple[WalkForwardFold, ...]:
    """Create chronological case-count folds without look-ahead."""

    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be positive")
    step = test_size if step_size is None else step_size
    if step < 1:
        raise ValueError("step_size must be positive")
    cases = cohort.cases
    folds: list[WalkForwardFold] = []
    test_start_idx = train_size
    fold_no = 1
    while test_start_idx + test_size <= len(cases):
        train_start_idx = 0 if expanding else max(0, test_start_idx - train_size)
        train = cases[train_start_idx:test_start_idx]
        test = cases[test_start_idx:test_start_idx + test_size]
        if train and test:
            train_end_dt = _aware(train[-1].decision_at, "train_end")
            test_start_dt = _aware(test[0].decision_at, "test_start")
            if train_end_dt >= test_start_dt:
                raise ValueError("cohort timestamps do not permit chronological walk-forward")
            folds.append(
                WalkForwardFold(
                    fold_id=f"WF{fold_no}",
                    train_case_ids=tuple(case.case_id for case in train),
                    test_case_ids=tuple(case.case_id for case in test),
                    train_start=train[0].decision_at,
                    train_end=train[-1].decision_at,
                    test_start=test[0].decision_at,
                    test_end=test[-1].decision_at,
                )
            )
            fold_no += 1
        test_start_idx += step
    if not folds:
        raise ValueError("cohort is too small for the requested walk-forward geometry")
    return tuple(folds)


def _subset_cohort(cohort: LearningCohort, case_ids: Sequence[str]) -> LearningCohort:
    allowed = set(case_ids)
    return build_learning_cohort(case for case in cohort.cases if case.case_id in allowed)


def evaluate_walk_forward(
    candidate: CandidateVersion,
    cohort: LearningCohort,
    predictions: Iterable[CandidatePrediction],
    folds: Iterable[WalkForwardFold],
) -> tuple[CandidateEvaluation, ...]:
    """Evaluate only each fold's chronologically future test set."""

    pred_lookup = {item.case_id: item for item in predictions}
    results: list[CandidateEvaluation] = []
    for fold in folds:
        sub = _subset_cohort(cohort, fold.test_case_ids)
        sub_preds = tuple(pred_lookup[case_id] for case_id in sub.case_ids)
        results.append(
            evaluate_candidate(
                candidate,
                sub,
                sub_preds,
                split=EvaluationSplit.OUT_OF_SAMPLE,
                walk_forward_fold_id=fold.fold_id,
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class WalkForwardSummary:
    candidate_version: str
    candidate_sha256: str
    folds_sha256: str
    fold_count: int
    total_oos_cases: int
    all_real_history: bool
    no_lookahead_verified: bool
    costs_complete: bool
    mean_expectancy_gross_r: float | None
    worst_expectancy_gross_r: float | None
    mean_hit_rate: float | None
    mean_crash_false_positive_rate: float | None
    worst_crash_false_positive_rate: float | None
    evaluation_sha256s: tuple[str, ...]


def summarize_walk_forward(
    evaluations: Iterable[CandidateEvaluation],
    folds: Iterable[WalkForwardFold],
) -> WalkForwardSummary:
    items = tuple(evaluations)
    fold_items = tuple(folds)
    if not items or len(items) != len(fold_items):
        raise ValueError("walk-forward evaluations must align one-for-one with folds")
    versions = {item.candidate.version for item in items}
    shas = {item.candidate.sha256 for item in items}
    if len(versions) != 1 or len(shas) != 1:
        raise ValueError("walk-forward evaluations must use one candidate")
    expected_fold_ids = [fold.fold_id for fold in fold_items]
    actual_fold_ids = [item.walk_forward_fold_id for item in items]
    if actual_fold_ids != expected_fold_ids:
        raise ValueError("walk-forward evaluation fold IDs do not match fold definitions")
    for item in items:
        if item.split is not EvaluationSplit.OUT_OF_SAMPLE:
            raise ValueError("walk-forward test evaluations must be OUT_OF_SAMPLE")

    expectancies = [
        item.metrics.expectancy_gross_r
        for item in items
        if item.metrics.expectancy_gross_r is not None
    ]
    hit_rates = [item.metrics.hit_rate for item in items if item.metrics.hit_rate is not None]
    fprs = [
        item.metrics.crash_false_positive_rate
        for item in items
        if item.metrics.crash_false_positive_rate is not None
    ]
    folds_sha = _hash(
        [
            {
                "fold_id": fold.fold_id,
                "train_case_ids": fold.train_case_ids,
                "test_case_ids": fold.test_case_ids,
                "train_start": fold.train_start,
                "train_end": fold.train_end,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
            }
            for fold in fold_items
        ]
    )
    first = items[0]
    return WalkForwardSummary(
        candidate_version=first.candidate.version,
        candidate_sha256=first.candidate.sha256,
        folds_sha256=folds_sha,
        fold_count=len(items),
        total_oos_cases=sum(item.metrics.cases_total for item in items),
        all_real_history=all(item.all_real_history for item in items),
        no_lookahead_verified=all(item.no_lookahead_verified for item in items),
        costs_complete=all(item.costs_complete for item in items),
        mean_expectancy_gross_r=mean(expectancies) if expectancies else None,
        worst_expectancy_gross_r=min(expectancies) if expectancies else None,
        mean_hit_rate=mean(hit_rates) if hit_rates else None,
        mean_crash_false_positive_rate=mean(fprs) if fprs else None,
        worst_crash_false_positive_rate=max(fprs) if fprs else None,
        evaluation_sha256s=tuple(item.evaluation_sha256 for item in items),
    )
