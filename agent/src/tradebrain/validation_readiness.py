"""Operational evidence/readiness gates for TradeBrain BSE."""

from __future__ import annotations

from dataclasses import dataclass

from src.tradebrain.final_guidance import HistoricalReliabilitySummary

__all__ = ["ValidationReadiness", "assess_validation_readiness"]


@dataclass(frozen=True)
class ValidationReadiness:
    ready_for_candidate_guidance: bool
    ready_for_live_shadow: bool
    ready_for_production_review: bool
    blockers: tuple[str, ...]
    sample_count: int
    real_history: bool
    out_of_sample: bool
    walk_forward: bool
    no_lookahead_verified: bool
    costs_complete: bool
    live_market_data_connected: bool
    shadow_sample_count: int


def assess_validation_readiness(
    historical: HistoricalReliabilitySummary | None,
    *,
    live_market_data_connected: bool,
    shadow_sample_count: int,
    min_shadow_samples: int = 20,
) -> ValidationReadiness:
    if shadow_sample_count < 0:
        raise ValueError("shadow_sample_count cannot be negative")
    if min_shadow_samples < 1:
        raise ValueError("min_shadow_samples must be >= 1")

    blockers: list[str] = []
    if historical is None:
        blockers.append("historical_reliability_missing")
        sample_count = 0
        real_history = out_of_sample = walk_forward = no_lookahead = costs = False
        candidate = False
    else:
        sample_count = historical.sample_count
        real_history = historical.real_history
        out_of_sample = historical.out_of_sample
        walk_forward = historical.walk_forward
        no_lookahead = historical.no_lookahead_verified
        costs = historical.costs_complete
        candidate = historical.ready
        if not real_history:
            blockers.append("real_history_missing")
        if not out_of_sample:
            blockers.append("out_of_sample_missing")
        if not walk_forward:
            blockers.append("walk_forward_missing")
        if not no_lookahead:
            blockers.append("no_lookahead_not_verified")
        if not costs:
            blockers.append("cost_model_incomplete")
        if historical.sample_count <= 0:
            blockers.append("historical_sample_count_zero")
        if historical.expectancy_net_r is None:
            blockers.append("net_expectancy_missing")

    live_shadow = candidate and live_market_data_connected
    if not live_market_data_connected:
        blockers.append("live_market_data_not_connected")
    production = live_shadow and shadow_sample_count >= min_shadow_samples
    if shadow_sample_count < min_shadow_samples:
        blockers.append("insufficient_live_shadow_samples")

    return ValidationReadiness(
        ready_for_candidate_guidance=candidate,
        ready_for_live_shadow=live_shadow,
        ready_for_production_review=production,
        blockers=tuple(dict.fromkeys(blockers)),
        sample_count=sample_count,
        real_history=real_history,
        out_of_sample=out_of_sample,
        walk_forward=walk_forward,
        no_lookahead_verified=no_lookahead,
        costs_complete=costs,
        live_market_data_connected=live_market_data_connected,
        shadow_sample_count=shadow_sample_count,
    )
