"""Phase-5 composition: Phase-4 evidence -> structure -> Crash Guard."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable

from src.tradebrain.crash_guard import (
    CrashGuardConfig,
    CrashGuardResult,
    evaluate_crash_guard,
)
from src.tradebrain.data_intelligence import BSEDataIntelligenceContext
from src.tradebrain.structure import (
    MultiTimeframeStructure,
    StructureConfig,
    build_multi_timeframe_structure,
)

__all__ = [
    "BSEStructureRiskContext",
    "build_bse_structure_risk_context",
]


@dataclass(frozen=True)
class BSEStructureRiskContext:
    """Read-only Phase-5 context; still not a trade candidate or recommendation."""

    phase4: BSEDataIntelligenceContext
    structure: MultiTimeframeStructure
    crash_guard: CrashGuardResult

    @property
    def readiness(self):
        """Advance only market_structure when structure and Crash Guard are usable."""
        base = self.phase4.readiness
        ready = (
            base.market_data_ready
            and base.intelligence_ready
            and self.structure.ready
            and self.crash_guard.usable
        )
        return replace(base, market_structure_ready=ready)

    @property
    def decision_ready(self) -> bool:
        return self.readiness.decision_ready

    @property
    def missing_layers(self) -> tuple[str, ...]:
        return self.readiness.missing_layers


def build_bse_structure_risk_context(
    phase4: BSEDataIntelligenceContext,
    *,
    as_of: str | datetime,
    requested_intervals: Iterable[str] = (),
    structure_config: StructureConfig | None = None,
    crash_guard_config: CrashGuardConfig | None = None,
    complete_history_intervals: Iterable[str] = (),
) -> BSEStructureRiskContext:
    """Build Phase-5 context from the exact Phase-4 market snapshot."""

    structure = build_multi_timeframe_structure(
        phase4.market_data,
        as_of=as_of,
        requested_intervals=requested_intervals,
        config=structure_config,
        complete_history_intervals=complete_history_intervals,
    )
    crash_guard = evaluate_crash_guard(
        phase4.market_data,
        structure,
        config=crash_guard_config,
    )
    return BSEStructureRiskContext(
        phase4=phase4,
        structure=structure,
        crash_guard=crash_guard,
    )
