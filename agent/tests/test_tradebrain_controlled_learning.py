from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import math
import pytest

from src.tradebrain.learning import (
    CandidateRole,
    CandidateVersion,
    DataOrigin,
    EvaluationSplit,
    SessionClass,
    build_learning_case,
    build_learning_cohort,
    build_walk_forward_folds,
    evaluate_candidate,
    evaluate_walk_forward,
    make_candidate_prediction,
    summarize_walk_forward,
)
from src.tradebrain.promotion import (
    PromotionPolicy,
    PromotionState,
    approve_challenger,
    assess_promotion,
    compare_candidates,
)


@dataclass(frozen=True)
class Setup:
    setup_id: str
    snapshot_sha256: str
    decision_at: str
    direction: str = "long"
    costs_known: bool = False


@dataclass(frozen=True)
class Outcome:
    setup_id: str
    setup_sha256: str
    state: str
    replay_source_frame_sha256: str
    realized_gross_r: float | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    time_to_target_seconds: float | None = None
    terminal_mark_r: float | None = None
    cost_model_applied: bool = False


@dataclass(frozen=True)
class CrashCase:
    setup_id: str
    setup_sha256: str
    label: str
    replay_source_frame_sha256: str


def make_case(
    i,
    *,
    state="tp_first",
    label="no_stress",
    pred_origin=DataOrigin.REAL,
    session=SessionClass.ORDINARY,
    direction="long",
    regime=None,
    subperiod=None,
    cost=False,
    no_lookahead=True,
):
    dt = datetime(2025, 1, 1, 10, tzinfo=timezone.utc) + timedelta(days=i)
    setup_id = f"S{i}"
    setup_sha = f"{i:064x}"[-64:]
    setup = Setup(setup_id, setup_sha, dt.isoformat(), direction, cost)
    realized = 2.0 if state == "tp_first" else -1.0 if state == "sl_first" else None
    outcome = Outcome(
        setup_id,
        setup_sha,
        state,
        f"{i+100:064x}"[-64:],
        realized_gross_r=realized,
        mae_r=-0.4 if state != "data_insufficient" else None,
        mfe_r=1.2 if state != "data_insufficient" else None,
        time_to_target_seconds=600.0 if state == "tp_first" else None,
        terminal_mark_r=0.25 if state == "neither" else None,
        cost_model_applied=cost,
    )
    crash = CrashCase(
        setup_id,
        setup_sha,
        label,
        f"{i+200:064x}"[-64:],
    )
    return build_learning_case(
        setup,
        outcome,
        crash,
        regime=regime or ("up" if i % 2 == 0 else "down"),
        subperiod=subperiod or ("P1" if i < 4 else "P2"),
        session_class=session,
        data_origin=pred_origin,
        no_lookahead_verified=no_lookahead,
    )


def champion():
    return CandidateVersion(
        version="A1",
        family="crash_guard",
        role=CandidateRole.CHAMPION,
        parameters={"severe_one_bar_return": -0.04, "trigger_count": 2},
    )


def challenger():
    return CandidateVersion(
        version="B1",
        family="crash_guard",
        role=CandidateRole.CHALLENGER,
        parent_version="A1",
        parameters={"severe_one_bar_return": -0.045, "trigger_count": 2},
        change_summary=("one-bar severe threshold -4.0% -> -4.5%",),
    )


def predictions(candidate, cohort, severe_ids=()):
    severe = set(severe_ids)
    return tuple(
        make_candidate_prediction(
            candidate,
            case,
            predicted_severe=case.case_id in severe,
            rationale=("fixture",),
        )
        for case in cohort.cases
    )


def mixed_cohort(*, costs=False):
    cases = (
        make_case(0, state="tp_first", label="no_stress", cost=costs),
        make_case(1, state="sl_first", label="stress", session=SessionClass.SEVERE, cost=costs),
        make_case(2, state="sl_first", label="no_stress", cost=costs),
        make_case(3, state="tp_first", label="stress", session=SessionClass.SEVERE, cost=costs),
        make_case(4, state="neither", label="no_stress", cost=costs),
        make_case(5, state="ambiguous_same_bar", label="stress", session=SessionClass.SEVERE, cost=costs),
        make_case(6, state="data_insufficient", label="data_insufficient", cost=costs),
        make_case(7, state="tp_first", label="no_stress", direction="short", cost=costs),
    )
    return build_learning_cohort(cases)


def test_candidate_rejects_hard_rule_changes():
    with pytest.raises(ValueError, match="hard"):
        CandidateVersion(
            version="B",
            family="x",
            role="challenger",
            parent_version="A",
            parameters={"x": 1},
            change_summary=("change soft x",),
            hard_rule_changes=("move DAY flat time",),
        )


def test_challenger_requires_parent_and_explicit_change():
    with pytest.raises(ValueError, match="parent"):
        CandidateVersion("B", "x", "challenger", {"x": 1}, ("x",))
    with pytest.raises(ValueError, match="change_summary"):
        CandidateVersion("B", "x", "challenger", {"x": 1}, (), "A")


def test_phase7_candidate_cannot_claim_learned_or_nonresearch():
    with pytest.raises(ValueError, match="learned=True"):
        CandidateVersion("A", "x", "champion", {"x": 1}, learned=True)
    with pytest.raises(ValueError, match="research_only"):
        CandidateVersion("A", "x", "champion", {"x": 1}, research_only=False)


def test_candidate_parameters_are_recursively_immutable():
    source = {"outer": {"thresholds": [-0.04, -0.07]}}
    candidate = CandidateVersion("A", "x", "champion", source)
    original_sha = candidate.sha256
    source["outer"]["thresholds"][0] = -0.99
    assert candidate.sha256 == original_sha
    with pytest.raises(TypeError):
        candidate.parameters["outer"]["new"] = 1


def test_challenger_version_cannot_equal_parent():
    with pytest.raises(ValueError, match="differ"):
        CandidateVersion(
            version="A", family="x", role="challenger", parameters={"x": 2},
            change_summary=("x changed",), parent_version="A",
        )


def test_learning_case_requires_matching_phase6_lineage():
    case = make_case(0)
    bad_outcome = replace(case.outcome, setup_sha256="bad")
    with pytest.raises(ValueError, match="outcome setup SHA"):
        build_learning_case(
            case.setup,
            bad_outcome,
            case.crash_case,
            regime="up",
            subperiod="P1",
            session_class="ordinary",
            data_origin="real",
            no_lookahead_verified=True,
        )


def test_cohort_rejects_case_whose_embedded_outcome_drifted_after_hashing():
    case = make_case(0)
    tampered = replace(case, outcome=replace(case.outcome, realized_gross_r=99.0))
    with pytest.raises(ValueError, match="learning case.*SHA-256"):
        build_learning_cohort((tampered,))


def test_cohort_fingerprint_is_order_independent_but_case_sensitive():
    a = make_case(0)
    b = make_case(1)
    c1 = build_learning_cohort((a, b))
    c2 = build_learning_cohort((b, a))
    assert c1.dataset_sha256 == c2.dataset_sha256
    changed = build_learning_case(
        b.setup, b.outcome, b.crash_case, regime="different-regime", subperiod=b.subperiod,
        session_class=b.session_class, data_origin=b.data_origin,
        no_lookahead_verified=b.no_lookahead_verified,
    )
    c3 = build_learning_cohort((a, changed))
    assert c1.dataset_sha256 != c3.dataset_sha256


def test_cohort_rejects_duplicate_case_ids():
    a = make_case(0)
    with pytest.raises(ValueError, match="unique"):
        build_learning_cohort((a, a))


def test_cohort_tracks_real_severe_and_ordinary_coverage():
    cohort = mixed_cohort()
    assert cohort.all_real
    assert cohort.synthetic_case_count == 0
    assert cohort.severe_case_count == 3
    assert cohort.ordinary_case_count == 5


def test_prediction_is_bound_to_candidate_and_case_sha():
    cohort = mixed_cohort()
    c = champion()
    pred = make_candidate_prediction(c, cohort.cases[0], predicted_severe=True)
    assert pred.candidate_sha256 == c.sha256
    assert pred.case_sha256 == cohort.cases[0].case_sha256
    assert len(pred.prediction_sha256) == 64


def test_evaluation_requires_exact_prediction_coverage():
    cohort = mixed_cohort()
    c = champion()
    with pytest.raises(ValueError, match="exact cohort"):
        evaluate_candidate(c, cohort, predictions(c, cohort)[:-1], split="validation")


def test_evaluation_rejects_tampered_prediction():
    cohort = mixed_cohort()
    c = champion()
    preds = list(predictions(c, cohort))
    preds[0] = replace(preds[0], predicted_severe=not preds[0].predicted_severe)
    with pytest.raises(ValueError, match="SHA-256"):
        evaluate_candidate(c, cohort, preds, split="validation")


def test_candidate_metrics_track_plan_outcomes_and_crash_confusion():
    cohort = mixed_cohort()
    c = champion()
    ev = evaluate_candidate(
        c,
        cohort,
        predictions(c, cohort, severe_ids=("S1", "S2")),
        split=EvaluationSplit.OUT_OF_SAMPLE,
    )
    # S1 is a true-positive severe call, S2 is false positive.
    assert ev.metrics.crash_true_positive == 1
    assert ev.metrics.crash_false_positive == 1
    assert ev.metrics.crash_false_negative == 2
    assert ev.metrics.crash_true_negative == 3
    assert ev.metrics.crash_excluded == 1
    assert math.isclose(ev.metrics.crash_precision, 0.5)
    assert math.isclose(ev.metrics.crash_false_positive_rate, 1 / 4)
    # S1 and S2 are LONG, so both are blocked from admitted-plan metrics.
    assert ev.metrics.blocked_long_cases == 2
    assert ev.metrics.blocked_sl_first == 2
    assert ev.metrics.blocked_tp_first == 0
    assert ev.metrics.admitted_cases == 6
    assert ev.metrics.cost_coverage_ratio == 0.0


def test_short_plan_is_not_auto_blocked_by_severe_crash_prediction():
    case = make_case(0, direction="short", label="stress")
    cohort = build_learning_cohort((case,))
    c = champion()
    ev = evaluate_candidate(
        c, cohort, predictions(c, cohort, severe_ids=(case.case_id,)), split="validation"
    )
    assert ev.metrics.blocked_long_cases == 0
    assert ev.metrics.admitted_cases == 1


def test_resolved_expectancy_profit_factor_and_drawdown_are_auditable():
    cases = (
        make_case(0, state="tp_first"),
        make_case(1, state="sl_first"),
        make_case(2, state="tp_first"),
    )
    cohort = build_learning_cohort(cases)
    c = champion()
    ev = evaluate_candidate(c, cohort, predictions(c, cohort), split="validation")
    assert ev.metrics.resolved_trade_count == 3
    assert math.isclose(ev.metrics.expectancy_gross_r, 1.0)
    assert math.isclose(ev.metrics.profit_factor, 4.0)
    assert math.isclose(ev.metrics.max_drawdown_r, 1.0)


def test_regime_and_subperiod_slices_are_exposed():
    cohort = mixed_cohort()
    c = champion()
    ev = evaluate_candidate(c, cohort, predictions(c, cohort), split="validation")
    assert {s.label for s in ev.by_regime} == {"down", "up"}
    assert {s.label for s in ev.by_subperiod} == {"P1", "P2"}


def test_cost_complete_requires_every_phase6_case_to_have_cost_model():
    no_cost = mixed_cohort(costs=False)
    costed = mixed_cohort(costs=True)
    c = champion()
    assert not evaluate_candidate(c, no_cost, predictions(c, no_cost), split="validation").costs_complete
    assert evaluate_candidate(c, costed, predictions(c, costed), split="validation").costs_complete


def test_walk_forward_folds_are_chronological_and_nonoverlapping():
    cohort = mixed_cohort()
    folds = build_walk_forward_folds(cohort, train_size=4, test_size=2)
    assert len(folds) == 2
    assert folds[0].train_case_ids == ("S0", "S1", "S2", "S3")
    assert folds[0].test_case_ids == ("S4", "S5")
    assert not (set(folds[0].train_case_ids) & set(folds[0].test_case_ids))


def test_walk_forward_refuses_too_small_cohort():
    cohort = build_learning_cohort((make_case(0), make_case(1)))
    with pytest.raises(ValueError, match="too small"):
        build_walk_forward_folds(cohort, train_size=2, test_size=1)


def test_walk_forward_evaluates_only_future_test_sets():
    cohort = mixed_cohort()
    c = champion()
    preds = predictions(c, cohort)
    folds = build_walk_forward_folds(cohort, train_size=4, test_size=2)
    evals = evaluate_walk_forward(c, cohort, preds, folds)
    assert [ev.case_ids for ev in evals] == [("S4", "S5"), ("S6", "S7")]
    assert all(ev.split is EvaluationSplit.OUT_OF_SAMPLE for ev in evals)


def test_walk_forward_summary_is_versioned_and_stability_visible():
    cohort = mixed_cohort()
    c = champion()
    folds = build_walk_forward_folds(cohort, train_size=4, test_size=2)
    evals = evaluate_walk_forward(c, cohort, predictions(c, cohort), folds)
    summary = summarize_walk_forward(evals, folds)
    assert summary.candidate_version == "A1"
    assert summary.fold_count == 2
    assert summary.total_oos_cases == 4
    assert len(summary.folds_sha256) == 64


def test_compare_candidates_fails_on_different_dataset():
    cohort = mixed_cohort()
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    other = build_learning_cohort(cohort.cases[:-1])
    xe = evaluate_candidate(x, other, predictions(x, other), split="out_of_sample")
    with pytest.raises(ValueError, match="identical dataset"):
        compare_candidates(ce, xe)


def test_compare_candidates_reports_benefits_and_tradeoffs():
    cohort = mixed_cohort()
    c = champion()
    x = challenger()
    # Champion calls S2 severe (false positive / blocks a loser); challenger removes it.
    ce = evaluate_candidate(
        c, cohort, predictions(c, cohort, severe_ids=("S1", "S2")), split="out_of_sample"
    )
    xe = evaluate_candidate(
        x, cohort, predictions(x, cohort, severe_ids=("S1",)), split="out_of_sample"
    )
    comp = compare_candidates(ce, xe)
    assert comp.challenger_version == "B1"
    assert comp.crash_false_positive_rate_delta < 0
    assert comp.blocked_loser_delta == -1
    assert comp.benefits
    assert comp.tradeoffs


def test_default_promotion_policy_holds_without_costs_walkforward_and_sample_size():
    cohort = mixed_cohort()
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    xe = evaluate_candidate(x, cohort, predictions(x, cohort), split="out_of_sample")
    comp = compare_candidates(ce, xe)
    assessment = assess_promotion(
        comp,
        ce,
        xe,
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    assert assessment.state is PromotionState.HOLD_CHAMPION
    assert not assessment.promoted
    assert "cost_model_not_complete" in assessment.blockers
    assert "walk_forward_missing" in assessment.blockers
    assert "insufficient_oos_case_count" in assessment.blockers


def test_complete_evidence_without_measured_benefit_still_holds_champion():
    cohort = mixed_cohort(costs=True)
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    xe = evaluate_candidate(x, cohort, predictions(x, cohort), split="out_of_sample")
    assessment = assess_promotion(
        compare_candidates(ce, xe), ce, xe,
        policy=PromotionPolicy(
            require_walk_forward=False, min_oos_cases=1, min_regimes=2, min_subperiods=2
        ),
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    assert assessment.state is PromotionState.HOLD_CHAMPION
    assert "no_measured_challenger_benefit" in assessment.blockers


def test_permissive_complete_evidence_only_becomes_human_review_eligible():
    cohort = mixed_cohort(costs=True)
    c = champion()
    x = challenger()
    cp = predictions(c, cohort, severe_ids=("S0", "S1", "S3"))
    xp = predictions(x, cohort, severe_ids=("S1", "S3"))
    ce = evaluate_candidate(c, cohort, cp, split="out_of_sample")
    xe = evaluate_candidate(x, cohort, xp, split="out_of_sample")
    folds = build_walk_forward_folds(cohort, train_size=4, test_size=2)
    cws = summarize_walk_forward(evaluate_walk_forward(c, cohort, cp, folds), folds)
    xws = summarize_walk_forward(evaluate_walk_forward(x, cohort, xp, folds), folds)
    comp = compare_candidates(ce, xe)
    policy = PromotionPolicy(
        require_cost_model=True,
        min_oos_cases=1,
        min_walk_forward_folds=2,
        min_regimes=2,
        min_subperiods=2,
    )
    assessment = assess_promotion(
        comp,
        ce,
        xe,
        policy=policy,
        champion_walk_forward=cws,
        challenger_walk_forward=xws,
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    assert assessment.state is PromotionState.ELIGIBLE_FOR_HUMAN_REVIEW
    assert assessment.human_approval_required
    assert not assessment.promoted
    assert assessment.blockers == ()


def test_synthetic_history_blocks_promotion():
    cases = list(mixed_cohort(costs=True).cases)
    synthetic = make_case(
        8,
        state="tp_first",
        label="no_stress",
        pred_origin=DataOrigin.SYNTHETIC,
        cost=True,
        subperiod="P2",
    )
    cohort = build_learning_cohort((*cases, synthetic))
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    xe = evaluate_candidate(x, cohort, predictions(x, cohort), split="out_of_sample")
    comp = compare_candidates(ce, xe)
    policy = PromotionPolicy(
        require_walk_forward=False,
        min_oos_cases=1,
        min_regimes=1,
        min_subperiods=1,
    )
    assessment = assess_promotion(
        comp, ce, xe, policy=policy, ordinary_case_count=1, severe_case_count=1
    )
    assert "synthetic_or_nonreal_history_present" in assessment.blockers


def test_unverified_no_lookahead_blocks_promotion():
    cohort = build_learning_cohort(
        (
            make_case(0, cost=True, no_lookahead=False),
            make_case(1, cost=True, session=SessionClass.SEVERE),
        )
    )
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    xe = evaluate_candidate(x, cohort, predictions(x, cohort), split="out_of_sample")
    assessment = assess_promotion(
        compare_candidates(ce, xe),
        ce,
        xe,
        policy=PromotionPolicy(
            require_walk_forward=False,
            min_oos_cases=1,
            min_regimes=1,
            min_subperiods=1,
        ),
        ordinary_case_count=1,
        severe_case_count=1,
    )
    assert "no_lookahead_not_verified" in assessment.blockers


def test_manual_approval_rejected_when_assessment_is_hold():
    cohort = mixed_cohort()
    c = champion()
    x = challenger()
    ce = evaluate_candidate(c, cohort, predictions(c, cohort), split="out_of_sample")
    xe = evaluate_candidate(x, cohort, predictions(x, cohort), split="out_of_sample")
    assessment = assess_promotion(
        compare_candidates(ce, xe),
        ce,
        xe,
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    with pytest.raises(ValueError, match="not eligible"):
        approve_challenger(
            assessment,
            approved_by="owner",
            approved_at=datetime.now(timezone.utc),
            approval_note="approve",
        )


def test_manual_approval_record_never_claims_hard_rule_or_execution_change():
    cohort = mixed_cohort(costs=True)
    c = champion()
    x = challenger()
    cp = predictions(c, cohort, severe_ids=("S0", "S1", "S3"))
    xp = predictions(x, cohort, severe_ids=("S1", "S3"))
    ce = evaluate_candidate(c, cohort, cp, split="out_of_sample")
    xe = evaluate_candidate(x, cohort, xp, split="out_of_sample")
    folds = build_walk_forward_folds(cohort, train_size=4, test_size=2)
    assessment = assess_promotion(
        compare_candidates(ce, xe),
        ce,
        xe,
        policy=PromotionPolicy(
            min_oos_cases=1,
            min_walk_forward_folds=2,
            min_regimes=2,
            min_subperiods=2,
        ),
        champion_walk_forward=summarize_walk_forward(evaluate_walk_forward(c, cohort, cp, folds), folds),
        challenger_walk_forward=summarize_walk_forward(evaluate_walk_forward(x, cohort, xp, folds), folds),
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    record = approve_challenger(
        assessment,
        approved_by="owner",
        approved_at="2026-08-21T18:00:00+00:00",
        approval_note="reviewed evidence and tradeoffs",
    )
    assert record.promoted_challenger_version == "B1"
    assert not record.hard_rules_modified
    assert not record.auto_execution_enabled
    assert len(record.record_sha256) == 64
