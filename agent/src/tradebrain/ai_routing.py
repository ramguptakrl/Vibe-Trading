"""BSE TradeBrain AI routing on top of Vibe's existing provider layer.

AI produces research, verification and candidate context only. Provider routing
can fail over, but no model result can bypass TradeBrain hard rules or authorize
execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from src.config.tradebrain import get_tradebrain_ai_environment
from src.providers.capabilities import get_provider_capabilities

__all__ = [
    "AIResearchRole",
    "AIProviderRoute",
    "TradeBrainAIRoutingPolicy",
    "build_ai_routing_policy",
]


class AIResearchRole(str, Enum):
    PRIMARY_REASONER = "primary_reasoner"
    INDEPENDENT_VERIFIER = "independent_verifier"
    FAILOVER_REASONER = "failover_reasoner"


@dataclass(frozen=True)
class AIProviderRoute:
    provider: str
    model: str
    role: AIResearchRole

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip().lower()
        model = str(self.model or "").strip()
        if not provider or not model:
            raise ValueError("AI provider and model are required")
        caps = get_provider_capabilities(provider, model)
        if caps.name != provider:
            raise ValueError(f"unsupported TradeBrain AI provider: {provider}")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)


@dataclass(frozen=True)
class TradeBrainAIRoutingPolicy:
    primary: AIProviderRoute
    verifier: AIProviderRoute
    failover_enabled: bool
    verify_material_findings: bool = True
    ai_final_authority: bool = False
    trade_authorization: bool = False
    order_execution_allowed: bool = False

    def ordered_attempts(self, selected_provider: str | None = None) -> tuple[AIProviderRoute, ...]:
        """Return deterministic reasoning/failover order without calling a model."""

        selected = str(selected_provider or self.primary.provider).strip().lower()
        if selected == "google":
            selected = "gemini"
        if selected == self.verifier.provider:
            first = AIProviderRoute(self.verifier.provider, self.verifier.model, AIResearchRole.PRIMARY_REASONER)
            if not self.failover_enabled:
                return (first,)
            return (
                first,
                AIProviderRoute(self.primary.provider, self.primary.model, AIResearchRole.FAILOVER_REASONER),
            )
        if selected != self.primary.provider:
            raise ValueError(f"unsupported selected TradeBrain AI provider: {selected}")
        if not self.failover_enabled:
            return (self.primary,)
        return (
            self.primary,
            AIProviderRoute(self.verifier.provider, self.verifier.model, AIResearchRole.FAILOVER_REASONER),
        )

    def verification_route(self, *, material: bool) -> AIProviderRoute | None:
        """Material primary findings receive an independent verifier when enabled."""

        if material and self.verify_material_findings:
            return self.verifier
        return None


def build_ai_routing_policy(
    environ: Mapping[str, str] | None = None,
) -> TradeBrainAIRoutingPolicy:
    configured = get_tradebrain_ai_environment(environ)
    primary = AIProviderRoute(
        configured.primary_provider,
        configured.primary_model,
        AIResearchRole.PRIMARY_REASONER,
    )
    verifier = AIProviderRoute(
        configured.verifier_provider,
        configured.verifier_model,
        AIResearchRole.INDEPENDENT_VERIFIER,
    )
    if primary.provider == verifier.provider:
        raise ValueError("TradeBrain verifier must use an independent provider")
    return TradeBrainAIRoutingPolicy(
        primary=primary,
        verifier=verifier,
        failover_enabled=configured.failover_enabled,
    )
