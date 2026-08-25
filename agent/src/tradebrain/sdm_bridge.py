"""Thin bridge from TradeBrain candidates to Vibe SDM/strategy-store.

The bridge deliberately does not register or activate anything by itself. It
builds a governed research Artifact that callers may pass through Vibe's
existing strategy-store / SDM lifecycle. BSE-specific promotion remains subject
to TradeBrain's stricter OOS/walk-forward/cost/regime gates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from src.tradebrain.learning import CandidateVersion

__all__ = ["build_sdm_research_artifact"]


def _jsonable(value: object) -> object:
    """Recursively thaw frozen candidate parameters into JSON-safe values."""

    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"candidate parameter is not JSON-safe: {type(value).__name__}")


def build_sdm_research_artifact(
    candidate: CandidateVersion,
    *,
    developer: str,
    owner: str,
    validator: str | None = None,
    approver: str | None = None,
):
    """Return a Vibe strategy-store Artifact for research orchestration only."""

    from src.strategy_store.models import (
        Artifact,
        ArtifactStatus,
        ArtifactType,
        ModelTier,
        ValidationStatus,
        validate_model_registration,
    )

    developer = str(developer or "").strip()
    owner = str(owner or "").strip()
    if not developer or not owner:
        raise ValueError("developer and owner are required for SDM research registration")

    limitations = (
        "Research-only TradeBrain/BSE candidate. Not approved for live execution; "
        "tradebrain_bse remains advisory-only. Hard owner/exchange/broker rules are "
        "outside the learnable parameter set. Generic SDM thresholds do not prove "
        "BSE profitability or authorize promotion. Net economics must be validated "
        "through TradeBrain's resident advisory cost context; optional MTF funding, "
        "if introduced, requires separate verified economics and does not change policy."
    )
    intended_use = (
        "Coordinate BSE candidate research, replay, validation history and decay "
        "monitoring through Vibe SDM while TradeBrain retains final BSE governance."
    )
    signal_definition = json.dumps(
        {
            "tradebrain_family": candidate.family,
            "candidate_version": candidate.version,
            "candidate_sha256": candidate.sha256,
            "role": candidate.role.value,
            "parent_version": candidate.parent_version,
            "parameters": _jsonable(candidate.parameters),
            "change_summary": list(candidate.change_summary),
            "hard_rule_changes": [],
            "research_only": True,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    artifact = Artifact(
        id="",
        type=ArtifactType.STRATEGY,
        name=f"tradebrain_bse::{candidate.family}::{candidate.version}",
        universe="BSE Ltd / NSE:BSE / INE118H01025",
        signal_definition=signal_definition,
        status=ArtifactStatus.BENCHING,
        developer=developer,
        owner=owner,
        validator=(str(validator).strip() if validator else None),
        approver=(str(approver).strip() if approver else None),
        model_version=candidate.version,
        artifact_version="tradebrain-research",
        model_tier=ModelTier.TIER_2_SIGNIFICANT,
        intended_use=intended_use,
        limitations=limitations,
        validation_status=ValidationStatus.IN_VALIDATION,
    )
    validate_model_registration(artifact)
    return artifact
