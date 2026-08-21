from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta

import pytest

from src.tradebrain.historical_outcomes import (
    OutcomeState, OutcomeValidationError, build_bse_plan_snapshot,
    build_replay_bar_batch, evaluate_plan_outcome,
)
from src.tradebrain.crash_guard import CrashGuardState
from src.tradebrain.market_data import OHLCVBar
from tradebrain_phase6_fixtures import IST, future_bars, make_bar, make_phase5, make_setup, replay_for

def test_plan_snapshot_is_frozen_and_costs_unknown():
    setup = make_setup()
    assert setup.net_rr is None
    assert setup.cost_model_version is None
    assert setup.costs_known is False
    assert setup.gross_rr == pytest.approx(2.0)
    with pytest.raises(FrozenInstanceError):
        setup.entry = 101


def test_plan_snapshot_binds_exact_phase5_context_hashes():
    phase5 = make_phase5()
    setup = make_setup(phase5=phase5)
    assert setup.market_data_frame_sha256 == phase5.phase4.market_data.frame_sha256
    assert setup.structure_sha256
    assert setup.crash_guard_sha256
    assert setup.intelligence_sha256
    assert setup.policy_sha256
    assert len(setup.snapshot_sha256) == 64


def test_snapshot_hash_changes_when_intelligence_changes():
    a = make_setup(phase5=make_phase5(event_title="A"))
    b = make_setup(phase5=make_phase5(event_title="B"))
    assert a.snapshot_sha256 != b.snapshot_sha256
    assert a.intelligence_sha256 != b.intelligence_sha256


def test_snapshot_hash_changes_when_crash_state_changes():
    a = make_setup(phase5=make_phase5(crash=CrashGuardState.NORMAL))
    b = make_setup(phase5=make_phase5(crash=CrashGuardState.SEVERE))
    assert a.snapshot_sha256 != b.snapshot_sha256


@pytest.mark.parametrize(
    "direction,entry,target,stop",
    [
        ("long", 100, 90, 95),
        ("long", 100, 110, 105),
        ("short", 100, 110, 105),
        ("short", 100, 90, 95),
    ],
)
def test_invalid_geometry_rejected(direction, entry, target, stop):
    with pytest.raises(OutcomeValidationError, match="geometry"):
        make_setup(direction=direction, entry=entry, target=target, stop=stop)


def test_swing_short_rejected():
    with pytest.raises(OutcomeValidationError, match="LONG-only"):
        make_setup(mode="swing", direction="short", target=90, stop=105)


def test_unready_phase5_rejected():
    with pytest.raises(OutcomeValidationError, match="not ready"):
        make_setup(phase5=make_phase5(ready=False))


def test_long_tp_first():
    setup = make_setup()
    rows = [
        (100, 106, 98, 104, 1000),
        (104, 111, 99, 110, 1000),
    ]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.TP_FIRST
    assert outcome.realized_gross_r == pytest.approx(2.0)
    assert outcome.mfe_r == pytest.approx(2.2)
    assert outcome.mae_r == pytest.approx(0.4)
    assert outcome.bars_examined == 2
    assert outcome.net_rr is None
    assert outcome.cost_model_applied is False



def test_time_to_target_is_bar_completion_not_fake_intrabar_time():
    setup = make_setup()
    rows = [(100, 111, 98, 110, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.TP_FIRST
    assert outcome.time_to_target_seconds == 300.0
    assert outcome.resolution_timestamp.endswith("10:05:00+05:30")


def test_long_sl_first():
    setup = make_setup()
    rows = [(100, 102, 94, 95, 1000), (95, 112, 94, 111, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.SL_FIRST
    assert outcome.realized_gross_r == -1.0
    assert outcome.bars_examined == 1


def test_short_tp_first():
    setup = make_setup(direction="short", entry=100, target=90, stop=105)
    rows = [(100, 102, 94, 95, 1000), (95, 101, 89, 90, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.TP_FIRST
    assert outcome.realized_gross_r == pytest.approx(2.0)
    assert outcome.mfe_r == pytest.approx(2.2)


def test_short_sl_first():
    setup = make_setup(direction="short", entry=100, target=90, stop=105)
    rows = [(100, 106, 98, 105, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.SL_FIRST
    assert outcome.realized_gross_r == -1.0


def test_same_bar_tp_and_sl_is_ambiguous_not_guessed():
    setup = make_setup()
    rows = [(100, 111, 94, 100, 1000)]
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.AMBIGUOUS_SAME_BAR
    assert outcome.realized_gross_r is None
    assert outcome.time_to_target_seconds == outcome.time_to_stop_seconds


def test_neither_is_censored_with_terminal_mark_separate():
    setup = make_setup()
    rows = [(100, 104, 98, 103, 1000)] * 3
    outcome = evaluate_plan_outcome(setup, replay_for(setup, future_bars(rows=rows)))
    assert outcome.state is OutcomeState.NEITHER
    assert outcome.realized_gross_r is None
    assert outcome.terminal_mark_r == pytest.approx(0.6)
    assert outcome.usable_for_history


