"""Phase-4 composition of BSE identity, market data and official intelligence."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.tradebrain.bse_context import BSEDecisionContextFoundation
from src.tradebrain.intelligence import BSEIntelligenceSnapshot
from src.tradebrain.market_data import BSEMarketDataSnapshot

__all__ = ["BSEDataIntelligenceContext", "build_bse_data_intelligence_context"]


@dataclass(frozen=True)
class BSEDataIntelligenceContext:
    """Read-only Phase-4 context; still not a trading recommendation."""

    foundation: BSEDecisionContextFoundation
    market_data: BSEMarketDataSnapshot
    intelligence: BSEIntelligenceSnapshot

    @property
    def readiness(self) -> BSEDecisionContextFoundation:
        """Advance only the layers that Phase 4 can actually prove ready."""
        return replace(
            self.foundation,
            market_data_ready=self.market_data.ready,
            intelligence_ready=self.intelligence.ready,
        )

    @property
    def decision_ready(self) -> bool:
        return self.readiness.decision_ready

    @property
    def missing_layers(self) -> tuple[str, ...]:
        return self.readiness.missing_layers


def build_bse_data_intelligence_context(
    foundation: BSEDecisionContextFoundation,
    market_data: BSEMarketDataSnapshot,
    intelligence: BSEIntelligenceSnapshot,
) -> BSEDataIntelligenceContext:
    """Bind validated Phase-4 inputs to the same canonical BSE Ltd security."""

    isin = foundation.identity.isin
    qualified = foundation.identity.qualified_symbol
    if market_data.isin != isin or intelligence.isin != isin:
        raise ValueError("Phase-4 inputs do not share the foundation's canonical ISIN")
    if (
        market_data.qualified_symbol != qualified
        or intelligence.qualified_symbol != qualified
    ):
        raise ValueError("Phase-4 inputs do not share the foundation's exact listing")
    return BSEDataIntelligenceContext(foundation, market_data, intelligence)
