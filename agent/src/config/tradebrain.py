"""Environment accessors for the opt-in TradeBrain profile."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

TRADEBRAIN_PROFILE_ENV = "VIBE_TRADING_PROFILE"
TRADEBRAIN_PRIMARY_AI_PROVIDER_ENV = "TRADEBRAIN_PRIMARY_AI_PROVIDER"
TRADEBRAIN_PRIMARY_AI_MODEL_ENV = "TRADEBRAIN_PRIMARY_AI_MODEL"
TRADEBRAIN_VERIFIER_AI_PROVIDER_ENV = "TRADEBRAIN_VERIFIER_AI_PROVIDER"
TRADEBRAIN_VERIFIER_AI_MODEL_ENV = "TRADEBRAIN_VERIFIER_AI_MODEL"
TRADEBRAIN_AI_FAILOVER_ENV = "TRADEBRAIN_AI_FAILOVER"

DEFAULT_PRIMARY_AI_PROVIDER = "groq"
DEFAULT_PRIMARY_AI_MODEL = "openai/gpt-oss-20b"
DEFAULT_VERIFIER_AI_PROVIDER = "gemini"
DEFAULT_VERIFIER_AI_MODEL = "gemini-3.7-flash"


@dataclass(frozen=True)
class TradeBrainAIEnvironment:
    primary_provider: str
    primary_model: str
    verifier_provider: str
    verifier_model: str
    failover_enabled: bool


def _bool(value: object, *, default: bool) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def get_tradebrain_profile_value(environ: Mapping[str, str] | None = None) -> str:
    """Return the normalized TradeBrain profile selector.

    Raw process-environment access stays in the config layer. Tests and callers
    may inject a mapping to keep profile resolution deterministic.
    """

    source = os.environ if environ is None else environ
    return str(source.get(TRADEBRAIN_PROFILE_ENV, "")).strip().lower()


def get_tradebrain_ai_environment(
    environ: Mapping[str, str] | None = None,
) -> TradeBrainAIEnvironment:
    """Resolve BSE TradeBrain AI roles without exposing provider credentials."""

    source = os.environ if environ is None else environ
    return TradeBrainAIEnvironment(
        primary_provider=str(
            source.get(TRADEBRAIN_PRIMARY_AI_PROVIDER_ENV, DEFAULT_PRIMARY_AI_PROVIDER)
        ).strip().lower() or DEFAULT_PRIMARY_AI_PROVIDER,
        primary_model=str(
            source.get(TRADEBRAIN_PRIMARY_AI_MODEL_ENV, DEFAULT_PRIMARY_AI_MODEL)
        ).strip() or DEFAULT_PRIMARY_AI_MODEL,
        verifier_provider=str(
            source.get(TRADEBRAIN_VERIFIER_AI_PROVIDER_ENV, DEFAULT_VERIFIER_AI_PROVIDER)
        ).strip().lower() or DEFAULT_VERIFIER_AI_PROVIDER,
        verifier_model=str(
            source.get(TRADEBRAIN_VERIFIER_AI_MODEL_ENV, DEFAULT_VERIFIER_AI_MODEL)
        ).strip() or DEFAULT_VERIFIER_AI_MODEL,
        failover_enabled=_bool(source.get(TRADEBRAIN_AI_FAILOVER_ENV), default=True),
    )
