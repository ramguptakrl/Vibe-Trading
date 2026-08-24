from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.tradebrain.crash_guard import CrashGuardState
from src.tradebrain.historical_outcomes import (
    OutcomeState, OutcomeValidationError, build_replay_bar_batch,
)
from src.tradebrain.outcome_context import build_bse_historical_outcome_context
from src.tradebrain.replay import (
    CrashReplayConfusion, CrashReplayLabel, CrashReplayLabelConfig,
    evaluate_crash_replay_case, summarize_crash_replay,
)
from .tradebrain_phase6_fixtures import (
    IST, future_bars, make_bar, make_phase5, make_setup, replay_for, stress_rows,
)

def test_crash_replay_true_positive():
    phase5 = make_phase5(crash=CrashGuardState.SEVERE)
    setup = make_setup(phase5=phase5)
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(True)))
    )
    assert case.label is CrashReplayLabel.STRESS
    assert case.confusion is CrashReplayConfusion.TRUE_POSITIVE


def test_crash_replay_false_positive_is_explicit_under_declared_label():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.SEVERE))
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(False)))
    )
    assert case.label is CrashReplayLabel.NO_STRESS
    assert case.confusion is CrashReplayConfusion.FALSE_POSITIVE


def test_crash_replay_false_negative():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.NORMAL))
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(True)))
    )
    assert case.confusion is CrashReplayConfusion.FALSE_NEGATIVE


def test_crash_replay_true_negative():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.NORMAL))
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(False)))
    )
    assert case.confusion is CrashReplayConfusion.TRUE_NEGATIVE


def test_crash_guard_data_insufficient_is_excluded_from_confusion_metrics():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.DATA_INSUFFICIENT))
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(True)))
    )
    assert case.confusion is CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT
    assert "crash_guard_data_insufficient" in case.limitations


def test_incomplete_crash_replay_horizon_is_excluded():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.SEVERE))
    bars = future_bars(rows=stress_rows(False)[:3])
    case = evaluate_crash_replay_case(setup, replay_for(setup, bars))
    assert case.label is CrashReplayLabel.DATA_INSUFFICIENT
    assert case.confusion is CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT


def test_gap_in_crash_replay_is_excluded():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.SEVERE))
    decision = datetime.fromisoformat(setup.decision_at)
    bars = tuple(
        make_bar(decision + timedelta(minutes=5*i), l=99)
        for i in (0, 1, 3, 4, 5, 6)
    )
    case = evaluate_crash_replay_case(setup, replay_for(setup, bars))
    assert case.confusion is CrashReplayConfusion.EXCLUDED_DATA_INSUFFICIENT
    assert any("intraday_gap" in item for item in case.limitations)


def test_replay_label_config_is_frozen_and_not_learned():
    cfg = CrashReplayLabelConfig()
    assert cfg.learned is False
    with pytest.raises(ValueError, match="not learned"):
        CrashReplayLabelConfig(learned=True)
    with pytest.raises(FrozenInstanceError):
        cfg.horizon_bars = 10


def test_crash_replay_does_not_mutate_phase5_crash_guard():
    phase5 = make_phase5(crash=CrashGuardState.SEVERE)
    before = phase5.crash_guard
    setup = make_setup(phase5=phase5)
    evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(False)))
    )
    assert phase5.crash_guard == before
    assert phase5.crash_guard.config_version == "phase5-provisional-v1"


def test_crash_replay_summary_metrics():
    cases = []
    for state, stress in (
        (CrashGuardState.SEVERE, True),
        (CrashGuardState.SEVERE, False),
        (CrashGuardState.NORMAL, True),
        (CrashGuardState.NORMAL, False),
    ):
        setup = make_setup(phase5=make_phase5(crash=state))
        cases.append(evaluate_crash_replay_case(
            setup, replay_for(setup, future_bars(rows=stress_rows(stress)))
        ))
    summary = summarize_crash_replay(cases)
    assert (summary.true_positive, summary.false_positive, summary.false_negative, summary.true_negative) == (1, 1, 1, 1)
    assert summary.precision == pytest.approx(0.5)
    assert summary.recall == pytest.approx(0.5)
    assert summary.false_positive_rate == pytest.approx(0.5)


def test_crash_replay_summary_uses_none_when_denominator_absent():
    setup = make_setup(phase5=make_phase5(crash=CrashGuardState.NORMAL))
    case = evaluate_crash_replay_case(
        setup, replay_for(setup, future_bars(rows=stress_rows(False)))
    )
    summary = summarize_crash_replay((case,))
    assert summary.precision is None
    assert summary.false_positive_rate == 0.0


def test_outcome_context_advances_only_historical_outcomes():
    phase5 = make_phase5()
    setup = make_setup(phase5=phase5)
    outcome_ctx = build_bse_historical_outcome_context(
        phase5,
        setup,
        replay_for(setup, future_bars(rows=[(100, 111, 98, 110, 1000)])),
    )
    assert outcome_ctx.readiness.historical_outcomes_ready is True
    assert outcome_ctx.readiness.hard_rule_arbiter_ready is False
    assert outcome_ctx.decision_ready is False
    assert outcome_ctx.missing_layers == ("hard_rule_arbiter",)


def test_outcome_context_does_not_advance_on_data_insufficient():
    phase5 = make_phase5()
    setup = make_setup(phase5=phase5)
    decision = datetime.fromisoformat(setup.decision_at)
    empty = build_replay_bar_batch(
        setup,
        bars=(),
        source_name="test_loader",
        retrieved_at=decision + timedelta(hours=1),
    )
    ctx = build_bse_historical_outcome_context(phase5, setup, empty)
    assert ctx.readiness.historical_outcomes_ready is False


def test_outcome_context_rejects_setup_from_different_phase5_snapshot():
    phase5_a = make_phase5(event_title="A")
    phase5_b = make_phase5(event_title="B")
    setup = make_setup(phase5=phase5_a)
    batch = replay_for(setup, future_bars())
    with pytest.raises(OutcomeValidationError, match="does not match"):
        build_bse_historical_outcome_context(phase5_b, setup, batch)
