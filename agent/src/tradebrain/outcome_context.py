"""Phase-6 composition: Phase-5 risk context -> immutable plan outcome memory."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from src.tradebrain.historical_outcomes import (
    BSEPlanSnapshot,
    PlanOutcome,
    ReplayBarBatch,
    OutcomeValidationError,
    build_bse_plan_snapshot,
    evaluate_plan_outcome,
)
from src.tradebrain.structure_context import BSEStructureRiskContext

__all__ = [
    "BSEHistoricalOutcomeContext",
    "build_bse_historical_outcome_context",
]


@dataclass(frozen=True)
class BSEHistoricalOutcomeContext:
    """Read-only Phase-6 context; still not a candidate generator or guidance."""

    phase5: BSEStructureRiskContext
    setup: BSEPlanSnapshot
    replay: ReplayBarBatch
    outcome: PlanOutcome

    @property
    def readiness(self):
        base = self.phase5.readiness
        ready = base.market_structure_ready and self.outcome.usable_for_history
        return replace(base, historical_outcomes_ready=ready)

    @property
    def decision_ready(self) -> bool:
        return self.readiness.decision_ready

    @property
    def missing_layers(self) -> tuple[str, ...]:
        return self.readiness.missing_layers


def build_bse_historical_outcome_context(
    phase5: BSEStructureRiskContext,
    setup: BSEPlanSnapshot,
    replay: ReplayBarBatch,
    *,
    evaluation_end: str | datetime | None = None,
) -> BSEHistoricalOutcomeContext:
    """Bind one exact Phase-5 setup to one deterministic replay outcome."""

    expected = build_bse_plan_snapshot(
        phase5,
        setup_id=setup.setup_id,
        mode=setup.mode,
        direction=setup.direction,
        entry=setup.entry,
        target=setup.target,
        stop=setup.stop,
        known_data_gaps=setup.known_data_gaps,
    )
    if expected.snapshot_sha256 != setup.snapshot_sha256:
        raise OutcomeValidationError("setup snapshot does not match the supplied Phase-5 context")
    outcome = evaluate_plan_outcome(setup, replay, evaluation_end=evaluation_end)
    return BSEHistoricalOutcomeContext(
        phase5=phase5,
        setup=setup,
        replay=replay,
        outcome=outcome,
    )
