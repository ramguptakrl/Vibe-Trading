"""BSE Ltd canonical subject + decision-context foundation.

Phase 3 verifies the identity of the BSE Ltd security before any market
structure, history, news, or strategy logic is allowed to claim it is operating
on the BSE profile's target instrument.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.goal.models import EvidenceInput
from src.tradebrain.hydration import (
    HydratedIdentitySet,
    IdentitySourceAuthority,
    SanitizedSecurityMasterRow,
    VerifiedIdentitySource,
    VerifiedSecurityMasterBatch,
    hydrate_verified_identity,
)
from src.tradebrain.identity import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityProvenance,
    IndiaExchange,
)
from src.tradebrain.profile import TradeBrainBSEPolicy, tradebrain_bse_policy

__all__ = [
    "BSE_LTD_CIN",
    "BSE_LTD_ISIN",
    "BSE_LTD_NSE_SYMBOL",
    "BSEDecisionContextFoundation",
    "BSEIdentityContext",
    "bootstrap_verified_bse_ltd_identity",
    "build_bse_ltd_decision_context",
]


BSE_LTD_ISIN = "INE118H01025"
BSE_LTD_CIN = "L67120MH2005PLC155188"
BSE_LTD_NSE_SYMBOL = "BSE"
BSE_LTD_LEGAL_NAME = "BSE Limited"

# Official-source bootstrap references. These are not live fetchers. Future
# collectors should rehydrate the same identity contract from current source
# snapshots and keep raw-artifact hashes when bytes are archived.
_NSE_INTEGRATED_FILING_URI = (
    "https://nsearchives.nseindia.com/corporate/ixbrl/"
    "INTEGRATED_FILING_INDAS_156058_07052026182427_iXBRL_WEB.html"
)
_NSE_ANNUAL_REPORT_URI = (
    "https://archives.nseindia.com/annual_reports/"
    "AR_27090_BSE_2024_2025_A_24072025103555.pdf"
)


def _row() -> SanitizedSecurityMasterRow:
    return SanitizedSecurityMasterRow(
        exchange=IndiaExchange.NSE,
        symbol=BSE_LTD_NSE_SYMBOL,
        isin=BSE_LTD_ISIN,
        security_name=BSE_LTD_LEGAL_NAME,
        issuer_entity_id=BSE_LTD_CIN,
        issuer_legal_name=BSE_LTD_LEGAL_NAME,
        cin=BSE_LTD_CIN,
    )


def bootstrap_verified_bse_ltd_identity(*, retrieved_at: str) -> HydratedIdentitySet:
    """Build the Phase-3 BSE Ltd identity snapshot from official NSE evidence.

    Evidence #1 is a 2026 NSE integrated filing carrying symbol ``BSE``, company
    name ``BSE Limited`` and ISIN ``INE118H01025``. Evidence #2 is BSE Limited's
    FY2024-25 annual report hosted by NSE, which carries the CIN and identifies
    NSE as the exchange where the shares are listed.

    The function intentionally creates no BSE-exchange listing for BSE Limited.
    """

    filing = VerifiedSecurityMasterBatch(
        source=VerifiedIdentitySource(
            authority=IdentitySourceAuthority.NSE_OFFICIAL,
            provenance=IdentityProvenance(
                source_provider="National Stock Exchange of India Limited",
                source_type="integrated_filing_indas",
                source_uri=_NSE_INTEGRATED_FILING_URI,
                retrieved_at=retrieved_at,
                data_as_of="2026-05-07",
                confidence="verified",
            ),
        ),
        rows=(_row(),),
    )
    annual_report = VerifiedSecurityMasterBatch(
        source=VerifiedIdentitySource(
            authority=IdentitySourceAuthority.NSE_OFFICIAL,
            provenance=IdentityProvenance(
                source_provider="National Stock Exchange of India Limited",
                source_type="issuer_annual_report",
                source_uri=_NSE_ANNUAL_REPORT_URI,
                retrieved_at=retrieved_at,
                data_as_of="2025-03-31",
                confidence="verified",
            ),
        ),
        rows=(_row(),),
    )
    return hydrate_verified_identity((filing, annual_report))


@dataclass(frozen=True)
class BSEIdentityContext:
    """Verified canonical target consumed by later BSE decision layers."""

    issuer_entity_id: str
    legal_name: str
    isin: str
    cin: str
    primary_exchange: str
    primary_symbol: str
    qualified_symbol: str
    vibe_symbol: str
    known_vibe_symbols: tuple[str, ...]
    provenance: tuple[IdentityProvenance, ...]
    evidence: tuple[EvidenceInput, ...]


@dataclass(frozen=True)
class BSEDecisionContextFoundation:
    """Explicit readiness envelope for the future BSE Master Brain.

    Phase 3 fills identity only. The false flags are intentional guardrails: a
    caller cannot mistake a verified symbol for a complete trading decision.
    """

    profile_name: str
    advisory_only: bool
    auto_execution: bool
    identity: BSEIdentityContext
    identity_verified: bool = True
    market_data_ready: bool = False
    intelligence_ready: bool = False
    market_structure_ready: bool = False
    historical_outcomes_ready: bool = False
    hard_rule_arbiter_ready: bool = False

    @property
    def decision_ready(self) -> bool:
        return all(
            (
                self.identity_verified,
                self.market_data_ready,
                self.intelligence_ready,
                self.market_structure_ready,
                self.historical_outcomes_ready,
                self.hard_rule_arbiter_ready,
            )
        )

    @property
    def missing_layers(self) -> tuple[str, ...]:
        flags: Mapping[str, bool] = {
            "market_data": self.market_data_ready,
            "intelligence": self.intelligence_ready,
            "market_structure": self.market_structure_ready,
            "historical_outcomes": self.historical_outcomes_ready,
            "hard_rule_arbiter": self.hard_rule_arbiter_ready,
        }
        return tuple(name for name, ready in flags.items() if not ready)


def build_bse_ltd_decision_context(
    hydrated: HydratedIdentitySet,
    *,
    policy: TradeBrainBSEPolicy | None = None,
) -> BSEDecisionContextFoundation:
    """Resolve the profile target and enforce BSE Ltd's canonical identity."""

    policy = tradebrain_bse_policy() if policy is None else policy
    target = policy.primary_security
    if target.exchange.upper() != "NSE" or target.symbol.upper() != BSE_LTD_NSE_SYMBOL:
        raise IdentityConflictError(
            "tradebrain_bse primary security must remain the exact NSE:BSE target"
        )

    resolution = hydrated.index.resolve_listing(target.exchange, target.symbol)
    bundle = resolution.bundle
    listing = resolution.listing
    if listing is None:
        raise IdentityNotFoundError("BSE profile target resolved without a listing record")

    if bundle.security.isin != BSE_LTD_ISIN:
        raise IdentityConflictError(
            f"NSE:BSE resolved to {bundle.security.isin}, expected {BSE_LTD_ISIN}"
        )
    if (bundle.issuer.cin or "").upper() != BSE_LTD_CIN:
        raise IdentityConflictError(
            f"BSE Ltd issuer CIN {bundle.issuer.cin!r} does not match {BSE_LTD_CIN}"
        )

    vibe_symbols = tuple(item.vibe_symbol for item in bundle.listings)
    identity = BSEIdentityContext(
        issuer_entity_id=bundle.issuer.entity_id,
        legal_name=bundle.issuer.legal_name,
        isin=bundle.security.isin,
        cin=bundle.issuer.cin or "",
        primary_exchange=listing.exchange.value,
        primary_symbol=listing.symbol,
        qualified_symbol=listing.qualified_symbol,
        vibe_symbol=listing.vibe_symbol,
        known_vibe_symbols=vibe_symbols,
        provenance=hydrated.provenance_for_isin(bundle.security.isin),
        evidence=hydrated.evidence_for_isin(bundle.security.isin),
    )
    return BSEDecisionContextFoundation(
        profile_name=policy.profile_name,
        advisory_only=policy.advisory_only,
        auto_execution=policy.auto_execution,
        identity=identity,
    )
