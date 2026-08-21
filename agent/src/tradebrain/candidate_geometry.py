"""Deterministic structure-derived plan geometry proposals for Phase 10.

Candidate geometry is not a verdict.  The module proposes bounded entry/target/
stop shapes from already-confirmed structural levels, then the hard-rule arbiter,
cost layer, history and final-guidance composer decide whether the proposal may
be surfaced as a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math

from src.tradebrain.hard_rules import AdvisoryPlanRequest
from src.tradebrain.outcome_models import Direction, PlanMode
from src.tradebrain.structure_context import BSEStructureRiskContext

__all__ = [
    "CandidateGeometryConfig",
    "CandidateProposal",
    "CandidateProposalSet",
    "propose_structure_candidates",
]


@dataclass(frozen=True)
class CandidateGeometryConfig:
    version: str = "phase10-geometry-v1"
    learned: bool = False
    day_min_gross_rr: float = 1.0
    swing_min_gross_rr: float = 3.0
    stop_buffer_pct: float = 0.001
    min_level_touches: int = 1

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("candidate geometry config version is required")
        if self.learned:
            raise ValueError("Phase 10 geometry defaults are provisional, not learned")
        if self.day_min_gross_rr <= 0 or self.swing_min_gross_rr <= 0:
            raise ValueError("minimum R:R values must be positive")
        if self.stop_buffer_pct < 0:
            raise ValueError("stop_buffer_pct cannot be negative")
        if self.min_level_touches < 1:
            raise ValueError("min_level_touches must be >= 1")


@dataclass(frozen=True)
class CandidateProposal:
    proposal_id: str
    request: AdvisoryPlanRequest
    source_intervals: tuple[str, ...]
    support: float
    resistance: float
    config_version: str
    config_learned: bool
    proposal_sha256: str


@dataclass(frozen=True)
class CandidateProposalSet:
    as_of: str
    proposals: tuple[CandidateProposal, ...]
    rejected: tuple[str, ...]
    config_version: str
    set_sha256: str


def _hash(payload: object) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(body.encode("utf-8")).hexdigest()


def _levels(phase5: BSEStructureRiskContext, config: CandidateGeometryConfig):
    supports: list[tuple[float, str]] = []
    resistances: list[tuple[float, str]] = []
    for timeframe in phase5.structure.timeframes:
        for level in timeframe.levels:
            if level.touches < config.min_level_touches:
                continue
            if level.kind in {"support", "mixed"}:
                supports.append((float(level.price), timeframe.interval))
            if level.kind in {"resistance", "mixed"}:
                resistances.append((float(level.price), timeframe.interval))
    return supports, resistances


def _make(
    *,
    mode: PlanMode,
    direction: Direction,
    entry: float,
    support: float,
    resistance: float,
    source_intervals: tuple[str, ...],
    config: CandidateGeometryConfig,
) -> CandidateProposal | None:
    buffer = config.stop_buffer_pct
    if direction is Direction.LONG:
        stop = support * (1.0 - buffer)
        target = resistance
    else:
        stop = resistance * (1.0 + buffer)
        target = support
    request = AdvisoryPlanRequest(
        mode=mode,
        direction=direction,
        entry=entry,
        target=target,
        stop=stop,
    )
    rr = request.gross_rr
    minimum = config.day_min_gross_rr if mode is PlanMode.DAY else config.swing_min_gross_rr
    if rr is None or rr < minimum:
        return None
    core = {
        "mode": mode.value,
        "direction": direction.value,
        "entry": entry,
        "target": target,
        "stop": stop,
        "support": support,
        "resistance": resistance,
        "source_intervals": source_intervals,
        "config_version": config.version,
        "config_learned": config.learned,
    }
    digest = _hash(core)
    return CandidateProposal(
        proposal_id=f"{mode.value}:{direction.value}:{digest[:12]}",
        request=request,
        source_intervals=source_intervals,
        support=support,
        resistance=resistance,
        config_version=config.version,
        config_learned=config.learned,
        proposal_sha256=digest,
    )


def propose_structure_candidates(
    phase5: BSEStructureRiskContext,
    *,
    config: CandidateGeometryConfig | None = None,
) -> CandidateProposalSet:
    """Propose DAY long/short and SWING long geometry from confirmed levels only."""

    cfg = CandidateGeometryConfig() if config is None else config
    if not phase5.readiness.market_structure_ready:
        return CandidateProposalSet(
            as_of=phase5.structure.as_of,
            proposals=(),
            rejected=("market_structure_not_ready",),
            config_version=cfg.version,
            set_sha256=_hash({"as_of": phase5.structure.as_of, "rejected": ["market_structure_not_ready"], "config": cfg.version}),
        )
    if not phase5.structure.timeframes:
        return CandidateProposalSet(
            as_of=phase5.structure.as_of,
            proposals=(),
            rejected=("no_timeframe_structure",),
            config_version=cfg.version,
            set_sha256=_hash({"as_of": phase5.structure.as_of, "rejected": ["no_timeframe_structure"], "config": cfg.version}),
        )

    entry = float(phase5.structure.timeframes[0].latest_close)
    supports, resistances = _levels(phase5, cfg)
    below = [(price, interval) for price, interval in supports if price < entry]
    above = [(price, interval) for price, interval in resistances if price > entry]
    rejected: list[str] = []
    proposals: list[CandidateProposal] = []
    if not below or not above:
        rejected.append("two_sided_structural_levels_unavailable")
    else:
        support_price = max(price for price, _ in below)
        resistance_price = min(price for price, _ in above)
        intervals = tuple(sorted({
            interval for price, interval in below if price == support_price
        } | {
            interval for price, interval in above if price == resistance_price
        }))
        for mode, direction in (
            (PlanMode.DAY, Direction.LONG),
            (PlanMode.DAY, Direction.SHORT),
            (PlanMode.SWING, Direction.LONG),
        ):
            proposal = _make(
                mode=mode,
                direction=direction,
                entry=entry,
                support=support_price,
                resistance=resistance_price,
                source_intervals=intervals,
                config=cfg,
            )
            if proposal is None:
                rejected.append(f"{mode.value}_{direction.value}_below_min_rr")
            else:
                proposals.append(proposal)

    core = {
        "as_of": phase5.structure.as_of,
        "proposal_sha256s": tuple(item.proposal_sha256 for item in proposals),
        "rejected": tuple(rejected),
        "config_version": cfg.version,
    }
    return CandidateProposalSet(
        as_of=phase5.structure.as_of,
        proposals=tuple(proposals),
        rejected=tuple(rejected),
        config_version=cfg.version,
        set_sha256=_hash(core),
    )
