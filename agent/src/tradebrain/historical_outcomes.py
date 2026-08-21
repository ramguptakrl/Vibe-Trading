"""Public Phase-6 BSE historical-outcome API.

Implementation is split into focused model, builder and evaluator modules while
this facade keeps a stable import surface for later TradeBrain phases.
"""

from src.tradebrain.outcome_models import (
    BSEPlanSnapshot, Direction, OutcomeState, OutcomeValidationError, PlanMode,
    PlanOutcome, ReplayBarBatch, validate_plan_snapshot_integrity,
)
from src.tradebrain.outcome_builders import build_bse_plan_snapshot, build_replay_bar_batch
from src.tradebrain.outcome_evaluator import evaluate_plan_outcome

__all__ = [
    "BSEPlanSnapshot", "Direction", "OutcomeState", "OutcomeValidationError",
    "PlanMode", "PlanOutcome", "ReplayBarBatch", "build_bse_plan_snapshot",
    "build_replay_bar_batch", "evaluate_plan_outcome",
    "validate_plan_snapshot_integrity",
]
