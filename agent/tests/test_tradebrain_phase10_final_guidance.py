from dataclasses import dataclass, replace
from datetime import time
from types import SimpleNamespace

import pytest

from src.tradebrain.candidate_geometry import (
    CandidateGeometryConfig,
    propose_structure_candidates,
)
from src.tradebrain.final_guidance import (
    GuidanceVerdict,
    HistoricalReliabilitySummary,
    compose_final_guidance,
)
from src.tradebrain.hard_rules import (
    AdvisoryPlanRequest,
    HardRuleCode,
    HardRuleState,
    RuleIntent,
    evaluate_bse_hard_rules,
)
from src.tradebrain.learning import (
    CandidateRole,
    CandidateVersion,
    DataOrigin,
    EvaluationSplit,
    SessionClass,
    build_learning_case,
    build_learning_cohort,
    make_candidate_prediction,
)
from src.tradebrain.net_learning import (
    NetPromotionState,
    assess_net_promotion,
    compare_net_candidates,
    evaluate_net_candidate,
)
from src.tradebrain.outcome_models import Direction, PlanMode
from src.tradebrain.profile import tradebrain_bse_policy

ASOF = "2026-08-21T14:00:00+05:30"


def _readiness(ready=True):
    return SimpleNamespace(
        identity_verified=ready,
        market_data_ready=ready,
        intelligence_ready=ready,
        market_structure_ready=ready,
    )


def _level(price, kind, touches=2):
    return SimpleNamespace(price=price, kind=kind, touches=touches)


def _phase5(*, ready=True, day_block=False, swing_block=False, identity=True, levels=True):
    policy = tradebrain_bse_policy()
    ident = SimpleNamespace(
        isin="INE118H01025" if identity else "BAD",
        qualified_symbol="NSE:BSE" if identity else "NSE:OTHER",
    )
    foundation = SimpleNamespace(
        profile_name=policy.profile_name,
        advisory_only=True,
        auto_execution=False,
        identity=ident,
    )
    intelligence = SimpleNamespace(events=())
    phase4 = SimpleNamespace(foundation=foundation, intelligence=intelligence)
    structural_levels = (
        (_level(95.0, "support"), _level(120.0, "resistance"))
        if levels
        else ()
    )
    tf = SimpleNamespace(
        interval="5m",
        latest_close=100.0,
        trend=SimpleNamespace(value="up"),
        regime=SimpleNamespace(value="trending_up"),
        levels=structural_levels,
    )
    structure = SimpleNamespace(as_of=ASOF, timeframes=(tf,))
    crash = SimpleNamespace(
        block_day_long=day_block,
        block_swing_long=swing_block,
        state=SimpleNamespace(value="severe" if day_block or swing_block else "normal"),
        reasons=("stress",) if day_block or swing_block else (),
    )
    return SimpleNamespace(
        readiness=_readiness(ready),
        phase4=phase4,
        structure=structure,
        crash_guard=crash,
    )


def _request(mode="day", direction="long", entry=100, target=110, stop=95, intent="new_entry"):
    return AdvisoryPlanRequest(mode, direction, entry, target, stop, intent)


def _history(ready=True):
    return HistoricalReliabilitySummary(
        sample_count=80 if ready else 0,
        out_of_sample=ready,
        walk_forward=ready,
        real_history=ready,
        no_lookahead_verified=ready,
        costs_complete=ready,
        expectancy_net_r=0.35 if ready else None,
        hit_rate=0.58 if ready else None,
        max_drawdown_net_r=4.2 if ready else None,
        source_sha256="h" * 64,
    )


def _economics(request, *, net_pnl=200.0):
    position = SimpleNamespace(
        mode=request.mode,
        direction=request.direction,
        entry_reference_price=request.entry,
        quantity=100,
    )
    return SimpleNamespace(position=position, net_pnl=net_pnl)


def test_profile_reflects_resident_day_swing_scope_and_optional_mtf():
    policy = tradebrain_bse_policy()
    assert policy.target_trader_persona == "resident_individual"
    assert policy.day.fresh_entry_cutoff == time(15, 10)
    assert policy.day.flat_by == time(15, 15)
    assert policy.swing.long_allowed is True
    assert policy.swing.short_allowed is False
    assert policy.swing.mtf_required is False
    assert policy.swing.funding_mechanism == "CASH_DELIVERY_OR_OPTIONAL_MTF"


def test_valid_day_long_before_cutoff_is_allowed():
    assessment = evaluate_bse_hard_rules(_phase5(), _request(), as_of=ASOF)
    assert assessment.state is HardRuleState.ALLOW
    assert assessment.auto_execution_allowed is False
    assert assessment.hard_rules_clear is True


def test_day_short_is_not_created_or_blocked_merely_by_severe_crash():
    p5 = _phase5(day_block=True, swing_block=True)
    assessment = evaluate_bse_hard_rules(
        p5, _request(direction="short", target=90, stop=105), as_of=ASOF
    )
    assert assessment.state is HardRuleState.ALLOW
    assert HardRuleCode.CRASH_GUARD_BLOCKS_DAY_LONG not in assessment.codes


@pytest.mark.parametrize(
    ("stamp", "code"),
    [
        ("2026-08-21T15:10:00+05:30", HardRuleCode.DAY_NO_FRESH_ENTRY_WINDOW),
        ("2026-08-21T15:15:00+05:30", HardRuleCode.DAY_FLAT_BY_REACHED),
    ],
)
def test_no_fresh_day_entry_in_exit_window(stamp, code):
    assessment = evaluate_bse_hard_rules(_phase5(), _request(), as_of=stamp)
    assert assessment.state is HardRuleState.BLOCKED
    assert code in assessment.codes


def test_existing_day_position_at_flat_boundary_requires_exit():
    assessment = evaluate_bse_hard_rules(
        _phase5(),
        _request(intent=RuleIntent.EXISTING_POSITION),
        as_of="2026-08-21T15:15:00+05:30",
    )
    assert assessment.state is HardRuleState.EXIT_REQUIRED
    assert HardRuleCode.DAY_FLAT_BY_REACHED in assessment.codes


def test_swing_short_is_hard_blocked():
    assessment = evaluate_bse_hard_rules(
        _phase5(),
        _request(mode="swing", direction="short", target=90, stop=105),
        as_of=ASOF,
    )
    assert assessment.state is HardRuleState.BLOCKED
    assert HardRuleCode.SWING_SHORT_FORBIDDEN in assessment.codes


def test_severe_crash_blocks_day_and_swing_long():
    day = evaluate_bse_hard_rules(_phase5(day_block=True), _request(), as_of=ASOF)
    swing = evaluate_bse_hard_rules(
        _phase5(swing_block=True),
        _request(mode="swing", target=120, stop=95),
        as_of=ASOF,
    )
    assert HardRuleCode.CRASH_GUARD_BLOCKS_DAY_LONG in day.codes
    assert HardRuleCode.CRASH_GUARD_BLOCKS_SWING_LONG in swing.codes


def test_invalid_geometry_is_hard_blocked():
    assessment = evaluate_bse_hard_rules(
        _phase5(), _request(target=90, stop=95), as_of=ASOF
    )
    assert assessment.state is HardRuleState.BLOCKED
    assert HardRuleCode.INVALID_GEOMETRY in assessment.codes


def test_core_context_not_ready_is_data_insufficient():
    assessment = evaluate_bse_hard_rules(_phase5(ready=False), _request(), as_of=ASOF)
    assert assessment.state is HardRuleState.DATA_INSUFFICIENT


def test_identity_mismatch_is_blocked():
    assessment = evaluate_bse_hard_rules(_phase5(identity=False), _request(), as_of=ASOF)
    assert HardRuleCode.IDENTITY_MISMATCH in assessment.codes
    assert assessment.state is HardRuleState.BLOCKED


def test_hard_rule_hash_is_deterministic():
    a = evaluate_bse_hard_rules(_phase5(), _request(), as_of=ASOF)
    b = evaluate_bse_hard_rules(_phase5(), _request(), as_of=ASOF)
    assert a.assessment_sha256 == b.assessment_sha256


def test_candidate_geometry_only_surfaces_directions_that_meet_current_rr_geometry():
    proposals = propose_structure_candidates(_phase5())
    modes = {(item.request.mode.value, item.request.direction.value) for item in proposals.proposals}
    assert ("day", "long") in modes
    assert ("swing", "long") in modes
    assert ("day", "short") not in modes
    assert ("swing", "short") not in modes
    assert all(item.config_learned is False for item in proposals.proposals)


def test_candidate_geometry_can_surface_day_short_when_its_rr_threshold_is_met():
    proposals = propose_structure_candidates(
        _phase5(), config=CandidateGeometryConfig(day_min_gross_rr=0.2)
    )
    modes = {(item.request.mode.value, item.request.direction.value) for item in proposals.proposals}
    assert ("day", "short") in modes
    assert ("swing", "short") not in modes


def test_candidate_geometry_requires_two_sided_confirmed_levels():
    proposals = propose_structure_candidates(_phase5(levels=False))
    assert not proposals.proposals
    assert "two_sided_structural_levels_unavailable" in proposals.rejected


def test_candidate_geometry_is_provisional_not_learned():
    with pytest.raises(ValueError, match="provisional"):
        CandidateGeometryConfig(learned=True)


def test_final_guidance_waits_without_history_and_costs():
    request = _request()
    hard = evaluate_bse_hard_rules(_phase5(), request, as_of=ASOF)
    guidance = compose_final_guidance(
        _phase5(), request, hard, historical=None, projected_costs=None
    )
    assert guidance.verdict is GuidanceVerdict.WAIT
    assert "historical_reliability_missing" in guidance.data_gaps
    assert "projected_transaction_costs_missing" in guidance.data_gaps


def test_final_guidance_surfaces_hard_block_without_history_override():
    p5 = _phase5(day_block=True)
    request = _request()
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    guidance = compose_final_guidance(
        p5, request, hard, historical=_history(), projected_costs=_economics(request)
    )
    assert guidance.verdict is GuidanceVerdict.BLOCKED_BY_HARD_RULE


def test_final_guidance_surfaces_exit_required():
    p5 = _phase5()
    request = _request(intent="existing_position")
    hard = evaluate_bse_hard_rules(
        p5, request, as_of="2026-08-21T15:15:00+05:30"
    )
    guidance = compose_final_guidance(
        p5, request, hard, historical=_history(), projected_costs=_economics(request)
    )
    assert guidance.verdict is GuidanceVerdict.EXIT_REQUIRED


def test_final_guidance_is_data_insufficient_when_core_context_is_not_ready():
    p5 = _phase5(ready=False)
    request = _request()
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    guidance = compose_final_guidance(
        p5, request, hard, historical=_history(), projected_costs=_economics(request)
    )
    assert guidance.verdict is GuidanceVerdict.DATA_INSUFFICIENT


@pytest.mark.parametrize(
    ("direction", "target", "stop", "verdict"),
    [
        ("long", 110, 95, GuidanceVerdict.LONG_CANDIDATE),
        ("short", 90, 105, GuidanceVerdict.SHORT_CANDIDATE),
    ],
)
def test_final_guidance_requires_rules_history_and_costs_for_candidate(
    direction, target, stop, verdict
):
    p5 = _phase5()
    request = _request(direction=direction, target=target, stop=stop)
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    guidance = compose_final_guidance(
        p5,
        request,
        hard,
        historical=_history(),
        projected_costs=_economics(request, net_pnl=250),
    )
    assert guidance.verdict is verdict
    assert guidance.projected_net_rr is not None
    assert guidance.advisory_only is True
    assert guidance.auto_execution is False
    assert guidance.confidence.model_uncertainty == "not_quantified"


def test_unvalidated_history_keeps_final_guidance_waiting():
    p5 = _phase5()
    request = _request()
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    guidance = compose_final_guidance(
        p5, request, hard, historical=_history(False), projected_costs=_economics(request)
    )
    assert guidance.verdict is GuidanceVerdict.WAIT


def test_relative_market_is_research_only_and_does_not_flip_candidate_verdict():
    p5 = _phase5()
    request = _request()
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    relative = SimpleNamespace(ready=False, context_sha256="r" * 64)
    guidance = compose_final_guidance(
        p5,
        request,
        hard,
        historical=_history(),
        projected_costs=_economics(request),
        relative_market=relative,
    )
    assert guidance.verdict is GuidanceVerdict.LONG_CANDIDATE
    assert "relative_market_context_not_ready" in guidance.data_gaps


def test_cost_projection_must_match_plan_identity_geometry():
    p5 = _phase5()
    request = _request()
    hard = evaluate_bse_hard_rules(p5, request, as_of=ASOF)
    bad = _economics(request)
    bad.position.entry_reference_price = 999
    with pytest.raises(ValueError, match="entry"):
        compose_final_guidance(
            p5, request, hard, historical=_history(), projected_costs=bad
        )


@dataclass(frozen=True)
class Setup:
    setup_id: str
    snapshot_sha256: str
    decision_at: str
    direction: str
    costs_known: bool = True


@dataclass(frozen=True)
class Outcome:
    setup_id: str
    setup_sha256: str
    state: str
    replay_source_frame_sha256: str
    realized_gross_r: float | None
    realized_net_r: float | None
    mae_r: float | None = 0.5
    mfe_r: float | None = 1.5
    time_to_target_seconds: float | None = 600
    terminal_mark_r: float | None = None
    cost_model_applied: bool = True


@dataclass(frozen=True)
class Crash:
    setup_id: str
    setup_sha256: str
    label: str = "no_stress"
    replay_source_frame_sha256: str = "f" * 64


def _learning_case(i, gross, net, state):
    sid = f"S{i}"
    sha = f"{i:064x}"[-64:]
    setup = Setup(sid, sha, f"2026-08-{10+i:02d}T10:00:00+05:30", "long")
    outcome = Outcome(sid, sha, state, "e" * 64, gross, net)
    crash = Crash(sid, sha)
    return build_learning_case(
        setup,
        outcome,
        crash,
        regime="trend",
        subperiod="p1" if i < 3 else "p2",
        session_class=SessionClass.ORDINARY,
        data_origin=DataOrigin.REAL,
        no_lookahead_verified=True,
    )


def _net_fixture():
    cases = (
        _learning_case(1, 2.0, 1.8, "tp_first"),
        _learning_case(2, -1.0, -1.2, "sl_first"),
        _learning_case(3, 2.0, 1.7, "tp_first"),
        _learning_case(4, -1.0, -1.1, "sl_first"),
    )
    cohort = build_learning_cohort(cases)
    champion = CandidateVersion(
        version="A",
        family="crash",
        role=CandidateRole.CHAMPION,
        parameters={"x": 1},
    )
    challenger = CandidateVersion(
        version="B",
        family="crash",
        role=CandidateRole.CHALLENGER,
        parameters={"x": 2},
        parent_version="A",
        change_summary=("test",),
    )
    cp = [make_candidate_prediction(champion, c, predicted_severe=False) for c in cases]
    xp = [
        make_candidate_prediction(challenger, c, predicted_severe=(c.case_id == "S2"))
        for c in cases
    ]
    return cases, cohort, champion, challenger, cp, xp


def test_net_learning_measures_costed_resolved_expectancy():
    _, cohort, champion, _, cp, _ = _net_fixture()
    result = evaluate_net_candidate(
        champion, cohort, cp, split=EvaluationSplit.OUT_OF_SAMPLE
    )
    assert result.metrics.net_cost_coverage_ratio == 1.0
    assert result.metrics.expectancy_net_r == pytest.approx(0.3)


def test_net_challenger_can_show_benefit_by_blocking_costed_loser():
    _, cohort, champion, challenger, cp, xp = _net_fixture()
    a = evaluate_net_candidate(champion, cohort, cp, split=EvaluationSplit.OUT_OF_SAMPLE)
    b = evaluate_net_candidate(challenger, cohort, xp, split=EvaluationSplit.OUT_OF_SAMPLE)
    comparison = compare_net_candidates(a, b)
    assert comparison.expectancy_net_delta_r > 0
    assert comparison.benefits


def test_net_promotion_requires_base_gate_and_complete_cost_coverage():
    _, cohort, champion, challenger, cp, xp = _net_fixture()
    a = evaluate_net_candidate(champion, cohort, cp, split=EvaluationSplit.OUT_OF_SAMPLE)
    b = evaluate_net_candidate(challenger, cohort, xp, split=EvaluationSplit.OUT_OF_SAMPLE)
    allowed = assess_net_promotion(
        a, b, base_promotion_state="eligible_for_human_review"
    )
    held = assess_net_promotion(a, b, base_promotion_state="hold_champion")
    assert allowed.state is NetPromotionState.ELIGIBLE_FOR_HUMAN_REVIEW
    assert held.state is NetPromotionState.HOLD_CHAMPION


def test_missing_net_cost_on_resolved_trade_blocks_net_promotion():
    cases, cohort, champion, challenger, cp, xp = _net_fixture()
    broken_outcome = replace(cases[0].outcome, realized_net_r=None)
    broken_case = build_learning_case(
        cases[0].setup,
        broken_outcome,
        cases[0].crash_case,
        regime=cases[0].regime,
        subperiod=cases[0].subperiod,
        session_class=cases[0].session_class,
        data_origin=cases[0].data_origin,
        no_lookahead_verified=True,
    )
    broken_cohort = build_learning_cohort((broken_case,) + cases[1:])
    cp2 = [make_candidate_prediction(champion, c, predicted_severe=False) for c in broken_cohort.cases]
    xp2 = [
        make_candidate_prediction(challenger, c, predicted_severe=(c.case_id == "S2"))
        for c in broken_cohort.cases
    ]
    a = evaluate_net_candidate(champion, broken_cohort, cp2, split=EvaluationSplit.OUT_OF_SAMPLE)
    b = evaluate_net_candidate(challenger, broken_cohort, xp2, split=EvaluationSplit.OUT_OF_SAMPLE)
    assessment = assess_net_promotion(
        a, b, base_promotion_state="eligible_for_human_review"
    )
    assert assessment.state is NetPromotionState.HOLD_CHAMPION
    assert any("cost_coverage" in blocker for blocker in assessment.blockers)
