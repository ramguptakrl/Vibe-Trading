from datetime import datetime
from zoneinfo import ZoneInfo

from src.tradebrain.operations_plan import OperationalTask, build_operations_plan
from src.tradebrain.session_modes import resolve_operating_state


IST = ZoneInfo("Asia/Kolkata")


def _state(hour: int, minute: int):
    return resolve_operating_state(
        datetime(2026, 8, 24, hour, minute, tzinfo=IST),
        is_trading_day=True,
    )


def test_market_mode_has_active_work_but_no_execution_capability():
    plan = build_operations_plan(_state(10, 0))
    assert OperationalTask.OBSERVE_MARKET in plan.required
    assert OperationalTask.COMPOSE_AUTHORITATIVE_GUIDANCE in plan.required
    assert "broker_order_write" in plan.forbidden
    assert "automatic_challenger_promotion" in plan.forbidden


def test_day_exit_window_prioritizes_exit_work():
    plan = build_operations_plan(_state(15, 12))
    assert OperationalTask.PRIORITIZE_DAY_EXIT in plan.required
    assert OperationalTask.COMPOSE_AUTHORITATIVE_GUIDANCE in plan.allowed


def test_after_market_runs_replay_scoring_and_research():
    plan = build_operations_plan(_state(17, 0))
    assert OperationalTask.REPLAY_COMPLETED_SESSION in plan.required
    assert OperationalTask.SCORE_ADVISORIES in plan.required
    assert OperationalTask.SCORE_MANUAL_TRADES in plan.required
    assert OperationalTask.RUN_CHALLENGER_RESEARCH in plan.allowed
