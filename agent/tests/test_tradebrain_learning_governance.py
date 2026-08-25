from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from src.tradebrain.learning import (
    CandidateVersion,
    DataOrigin,
    SessionClass,
    build_learning_case,
    build_learning_cohort,
    evaluate_candidate,
    make_candidate_prediction,
)
from src.tradebrain.promotion import (
    PromotionPolicy,
    PromotionState,
    append_manual_promotion_record,
    append_promotion_assessment,
    approve_challenger,
    assess_promotion,
    compare_candidates,
)
from src.tradebrain.sdm_bridge import build_sdm_research_artifact


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def simple_case(i=0, *, cost=True, severe=False):
    setup_id = f"S{i}"
    setup_sha = f"{i+1:064x}"
    setup = Obj(
        setup_id=setup_id,
        snapshot_sha256=setup_sha,
        decision_at=f"2026-08-{10+i:02d}T10:00:00+05:30",
        direction="long",
        costs_known=cost,
    )
    outcome = Obj(
        setup_id=setup_id,
        setup_sha256=setup_sha,
        state="sl_first" if severe else "tp_first",
        replay_source_frame_sha256=f"{i+10:064x}",
        realized_gross_r=-1.0 if severe else 2.0,
        mae_r=-0.5,
        mfe_r=1.0,
        time_to_target_seconds=None if severe else 300.0,
        terminal_mark_r=None,
        cost_model_applied=cost,
    )
    crash = Obj(
        setup_id=setup_id,
        setup_sha256=setup_sha,
        label="stress" if severe else "no_stress",
        replay_source_frame_sha256=f"{i+20:064x}",
    )
    return build_learning_case(
        setup,
        outcome,
        crash,
        regime="bear" if severe else "bull",
        subperiod="P1" if i < 2 else "P2",
        session_class=SessionClass.SEVERE if severe else SessionClass.ORDINARY,
        data_origin=DataOrigin.REAL,
        no_lookahead_verified=True,
    )


def candidates():
    champion = CandidateVersion(
        version="A",
        family="crash_guard",
        role="champion",
        parameters={"threshold": -0.04},
    )
    challenger = CandidateVersion(
        version="B",
        family="crash_guard",
        role="challenger",
        parent_version="A",
        parameters={"threshold": -0.045},
        change_summary=("threshold changed",),
    )
    return champion, challenger


def eligible_assessment():
    cohort = build_learning_cohort(
        (
            simple_case(0, severe=False),
            simple_case(1, severe=True),
            simple_case(2, severe=False),
            simple_case(3, severe=True),
        )
    )
    champion, challenger = candidates()
    cp = tuple(
        make_candidate_prediction(champion, c, predicted_severe=(c.case_id in {"S0", "S1", "S3"}))
        for c in cohort.cases
    )
    xp = tuple(
        make_candidate_prediction(challenger, c, predicted_severe=(c.case_id in {"S1", "S3"}))
        for c in cohort.cases
    )
    ce = evaluate_candidate(champion, cohort, cp, split="out_of_sample")
    xe = evaluate_candidate(challenger, cohort, xp, split="out_of_sample")
    policy = PromotionPolicy(
        require_walk_forward=False,
        min_oos_cases=1,
        min_regimes=2,
        min_subperiods=2,
    )
    assessment = assess_promotion(
        compare_candidates(ce, xe),
        ce,
        xe,
        policy=policy,
        ordinary_case_count=cohort.ordinary_case_count,
        severe_case_count=cohort.severe_case_count,
    )
    assert assessment.state is PromotionState.ELIGIBLE_FOR_HUMAN_REVIEW
    return assessment


def test_promotion_assessment_uses_vibe_hash_chained_ledger(tmp_path):
    assessment = eligible_assessment()
    path = tmp_path / "promotion.jsonl"
    first = append_promotion_assessment(path, assessment)
    assert first["seq"] == 1
    assert first["event_type"] == "tradebrain_bse_promotion_assessment"
    assert first["promoted"] is False

    from src.governance.ledger import verify_chain

    verified = verify_chain(path)
    assert verified.ok
    assert verified.record_count == 1


def test_manual_promotion_is_second_auditable_record(tmp_path):
    assessment = eligible_assessment()
    path = tmp_path / "promotion.jsonl"
    append_promotion_assessment(path, assessment)
    record = approve_challenger(
        assessment,
        approved_by="Ram",
        approved_at=datetime(2026, 8, 21, 18, 30, tzinfo=timezone.utc),
        approval_note="Manual evidence review completed.",
    )
    second = append_manual_promotion_record(path, record)
    assert second["seq"] == 2
    assert second["event_type"] == "tradebrain_bse_manual_promotion"
    assert second["hard_rules_modified"] is False
    assert second["auto_execution_enabled"] is False

    from src.governance.ledger import verify_chain

    assert verify_chain(path).record_count == 2


def test_broken_governance_chain_refuses_extension(tmp_path):
    assessment = eligible_assessment()
    path = tmp_path / "promotion.jsonl"
    append_promotion_assessment(path, assessment)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("eligible_for_human_review", "tampered"), encoding="utf-8")

    from src.governance.ledger import LedgerCorruptionError

    with pytest.raises(LedgerCorruptionError):
        append_promotion_assessment(path, assessment)


def test_sdm_bridge_builds_benching_research_artifact_not_active_model():
    _, challenger = candidates()
    artifact = build_sdm_research_artifact(
        challenger,
        developer="dev",
        owner="owner",
        validator="validator",
    )
    assert artifact.status.value == "benching"
    assert artifact.validation_status.value == "in_validation"
    assert artifact.model_version == "B"
    assert artifact.universe == "BSE Ltd / NSE:BSE / INE118H01025"
    assert "Research-only" in artifact.limitations
    assert "Generic SDM thresholds do not prove BSE profitability" in artifact.limitations
    assert artifact.approver is None


def test_sdm_bridge_requires_governance_ownership_fields():
    _, challenger = candidates()
    with pytest.raises(ValueError, match="developer and owner"):
        build_sdm_research_artifact(challenger, developer="", owner="owner")


def test_sdm_bridge_serializes_nested_frozen_candidate_parameters():
    nested = CandidateVersion(
        version="B-nested",
        family="crash_guard",
        role="challenger",
        parent_version="A",
        parameters={
            "thresholds": {"severe": [-0.04, -0.07]},
            "windows": (3, 6),
        },
        change_summary=("nested thresholds changed",),
    )
    artifact = build_sdm_research_artifact(
        nested, developer="dev", owner="owner"
    )
    payload = json.loads(artifact.signal_definition)
    assert payload["parameters"]["thresholds"]["severe"] == [-0.04, -0.07]
    assert payload["parameters"]["windows"] == [3, 6]
