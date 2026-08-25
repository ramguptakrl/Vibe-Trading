from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from src.tradebrain.historical_outcomes import (
    OutcomeState, OutcomeValidationError, build_replay_bar_batch, evaluate_plan_outcome,
)
from .tradebrain_phase6_fixtures import IST, future_bars, make_bar, make_phase5, make_setup, replay_for

def test_decision_time_completed_bar_is_not_reused_as_future_result():
    setup = make_setup()
    decision = datetime.fromisoformat(setup.decision_at)
    bars = (
        make_bar(decision - timedelta(minutes=5), h=120, l=80),
        make_bar(decision, h=104, l=98, c=102),
        make_bar(decision + timedelta(minutes=5), h=105, l=99, c=103),
    )
    outcome = evaluate_plan_outcome(setup, replay_for(setup, bars))
    assert outcome.state is OutcomeState.NEITHER
    assert outcome.first_future_timestamp == decision.isoformat()
    assert outcome.bars_examined == 2


def test_partial_bar_past_evaluation_end_is_excluded():
    setup = make_setup()
    decision = datetime.fromisoformat(setup.decision_at)
    bars = (
        make_bar(decision, h=104, l=98),
        make_bar(decision + timedelta(minutes=5), h=111, l=99),
    )
    outcome = evaluate_plan_outcome(
        setup,
        replay_for(setup, bars),
        evaluation_end=decision + timedelta(minutes=9),
    )
    assert outcome.state is OutcomeState.NEITHER
    assert outcome.bars_examined == 1


def test_day_horizon_stops_at_1515_and_does_not_see_1515_bar():
    decision = datetime(2026, 8, 21, 15, 0, tzinfo=IST)
    setup = make_setup(phase5=make_phase5(decision=decision))
    rows = [
        (100, 102, 98, 100, 1000),
        (100, 103, 98, 101, 1000),
        (101, 104, 99, 102, 1000),
        (102, 120, 90, 110, 1000),
    ]
    bars = future_bars(decision=decision, rows=rows)
    outcome = evaluate_plan_outcome(setup, replay_for(setup, bars))
    assert outcome.state is OutcomeState.NEITHER
    assert outcome.bars_examined == 3
    assert outcome.last_future_timestamp.endswith("15:10:00+05:30")
    assert outcome.horizon_capped_by_day_flat is True


def test_decision_at_or_after_day_flat_is_data_insufficient():
    decision = datetime(2026, 8, 21, 15, 15, tzinfo=IST)
    setup = make_setup(phase5=make_phase5(decision=decision))
    bars = future_bars(decision=decision)
    outcome = evaluate_plan_outcome(setup, replay_for(setup, bars))
    assert outcome.state is OutcomeState.DATA_INSUFFICIENT
    assert "decision_at_or_after_day_flat" in outcome.replay_data_gaps


def test_intraday_missing_bar_fails_closed_even_if_later_tp_seen():
    setup = make_setup()
    decision = datetime.fromisoformat(setup.decision_at)
    bars = (
        make_bar(decision, h=104, l=98),
        make_bar(decision + timedelta(minutes=10), h=111, l=99),
    )
    outcome = evaluate_plan_outcome(setup, replay_for(setup, bars))
    assert outcome.state is OutcomeState.DATA_INSUFFICIENT
    assert any(gap.startswith("intraday_gap:") for gap in outcome.replay_data_gaps)
    assert outcome.realized_gross_r is None


def test_declared_replay_gap_fails_closed_for_swing():
    setup = make_setup(mode="swing")
    decision = datetime.fromisoformat(setup.decision_at)
    bars = future_bars(decision=decision)
    outcome = evaluate_plan_outcome(
        setup, replay_for(setup, bars, gaps=("exchange_archive_gap",))
    )
    assert outcome.state is OutcomeState.DATA_INSUFFICIENT
    assert "exchange_archive_gap" in outcome.replay_data_gaps


def test_decision_context_gap_is_preserved_but_does_not_poison_price_outcome():
    setup = make_setup(gaps=("relative_market_not_available",))
    rows = [(100, 111, 98, 110, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.TP_FIRST
    assert outcome.decision_context_gaps == ("relative_market_not_available",)
    assert outcome.replay_data_gaps == ()


def test_no_future_bars_is_data_insufficient():
    setup = make_setup()
    replay = build_replay_bar_batch(
        setup,
        bars=(),
        source_name="test_loader",
        retrieved_at=datetime.fromisoformat(setup.decision_at) + timedelta(hours=1),
    )
    outcome = evaluate_plan_outcome(setup, replay)
    assert outcome.state is OutcomeState.DATA_INSUFFICIENT
    assert "no_complete_future_bars" in outcome.replay_data_gaps



def test_tampered_plan_snapshot_hash_fails_closed():
    setup = make_setup()
    tampered = replace(setup, entry=101.0)
    with pytest.raises(OutcomeValidationError, match="plan snapshot SHA-256"):
        build_replay_bar_batch(
            tampered,
            bars=future_bars(),
            source_name="test_loader",
            retrieved_at=datetime.fromisoformat(setup.decision_at) + timedelta(hours=1),
        )


def test_replay_source_mismatch_fails_closed():
    setup = make_setup()
    batch = replay_for(setup, future_bars())
    with pytest.raises(OutcomeValidationError, match="identity/source/interval"):
        evaluate_plan_outcome(setup, replace(batch, source_name="other_loader"))


def test_replay_identity_mismatch_fails_closed():
    setup = make_setup()
    batch = replay_for(setup, future_bars())
    with pytest.raises(OutcomeValidationError, match="identity/source/interval"):
        evaluate_plan_outcome(setup, replace(batch, qualified_symbol="BSE:FAKE"))


def test_replay_tamper_hash_fails_closed():
    setup = make_setup()
    batch = replay_for(setup, future_bars())
    with pytest.raises(OutcomeValidationError, match="SHA-256"):
        evaluate_plan_outcome(setup, replace(batch, frame_sha256="0" * 64))


def test_replay_bar_geometry_is_validated():
    setup = make_setup()
    decision = datetime.fromisoformat(setup.decision_at)
    bad = (make_bar(decision, o=100, h=99, l=98, c=100),)
    with pytest.raises(OutcomeValidationError, match="high"):
        build_replay_bar_batch(
            setup,
            bars=bad,
            source_name="test_loader",
            retrieved_at=decision + timedelta(hours=1),
        )
