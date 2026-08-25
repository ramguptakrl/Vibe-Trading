"""Deterministic work plan for each TradeBrain BSE operating mode.

This module turns the session-mode safety state into an explicit work queue.
It is intentionally side-effect free: an executor may run these tasks, but the
plan itself cannot fetch data, mutate production policy, or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.tradebrain.session_modes import OperatingMode, OperatingState

__all__ = ["OperationalTask", "OperationsPlan", "build_operations_plan"]


class OperationalTask(str, Enum):
    OBSERVE_MARKET = "observe_market"
    REFRESH_MARKET_CONTEXT = "refresh_market_context"
    COMPOSE_AUTHORITATIVE_GUIDANCE = "compose_authoritative_guidance"
    TRACK_MANUAL_TRADES = "track_manual_trades"
    PRIORITIZE_DAY_EXIT = "prioritize_day_exit"
    REPLAY_COMPLETED_SESSION = "replay_completed_session"
    SCORE_ADVISORIES = "score_advisories"
    SCORE_MANUAL_TRADES = "score_manual_trades"
    RUN_CHALLENGER_RESEARCH = "run_challenger_research"
    ARCHIVE_EVIDENCE = "archive_evidence"
    MAINTAIN_DATASETS = "maintain_datasets"


@dataclass(frozen=True)
class OperationsPlan:
    mode: OperatingMode
    required: tuple[OperationalTask, ...]
    allowed: tuple[OperationalTask, ...]
    forbidden: tuple[str, ...]


def build_operations_plan(state: OperatingState) -> OperationsPlan:
    """Build a deterministic, non-executing work plan for ``state``."""

    if state.mode is OperatingMode.MARKET_ACTIVE:
        required = (
            OperationalTask.OBSERVE_MARKET,
            OperationalTask.REFRESH_MARKET_CONTEXT,
            OperationalTask.COMPOSE_AUTHORITATIVE_GUIDANCE,
            OperationalTask.TRACK_MANUAL_TRADES,
        )
        if state.permissions.day_exit_priority:
            required += (OperationalTask.PRIORITIZE_DAY_EXIT,)
        allowed = required
    elif state.mode is OperatingMode.DAY_EXIT_WINDOW:
        required = (
            OperationalTask.OBSERVE_MARKET,
            OperationalTask.REFRESH_MARKET_CONTEXT,
            OperationalTask.TRACK_MANUAL_TRADES,
            OperationalTask.PRIORITIZE_DAY_EXIT,
        )
        allowed = required + (OperationalTask.COMPOSE_AUTHORITATIVE_GUIDANCE,)
    elif state.mode is OperatingMode.AFTER_MARKET:
        required = (
            OperationalTask.REPLAY_COMPLETED_SESSION,
            OperationalTask.SCORE_ADVISORIES,
            OperationalTask.SCORE_MANUAL_TRADES,
            OperationalTask.ARCHIVE_EVIDENCE,
        )
        allowed = required + (
            OperationalTask.RUN_CHALLENGER_RESEARCH,
            OperationalTask.MAINTAIN_DATASETS,
        )
    else:
        required = (
            OperationalTask.ARCHIVE_EVIDENCE,
            OperationalTask.MAINTAIN_DATASETS,
        )
        allowed = required + (
            OperationalTask.REPLAY_COMPLETED_SESSION,
            OperationalTask.SCORE_ADVISORIES,
            OperationalTask.SCORE_MANUAL_TRADES,
            OperationalTask.RUN_CHALLENGER_RESEARCH,
        )

    return OperationsPlan(
        mode=state.mode,
        required=required,
        allowed=allowed,
        forbidden=(
            "broker_order_write",
            "automatic_challenger_promotion",
            "hard_rule_mutation",
            "ui_generated_verdict",
        ),
    )
