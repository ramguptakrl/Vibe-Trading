"""Read-only BSE Command Center view model.

The command center renders authoritative backend state. It never creates a
verdict; if no ``FinalGuidance`` is supplied the UI must show that guidance is
unavailable rather than infer one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.tradebrain.final_guidance import FinalGuidance
from src.tradebrain.journal import TradeBrainJournalStore
from src.tradebrain.kite_readonly import KiteReadOnlyAdapter
from src.tradebrain.profile import tradebrain_bse_policy
from src.tradebrain.session_modes import OperatingState

__all__ = ["CommandCenterSnapshot", "build_command_center_snapshot"]


@dataclass(frozen=True)
class CommandCenterSnapshot:
    profile: str
    company_name: str
    instrument: str
    advisory_only: bool
    auto_execution: bool
    operating: dict[str, Any]
    guidance: dict[str, Any] | None
    manual_trade_count: int
    open_manual_trade_count: int
    shadow_advisory_count: int
    pending_shadow_count: int
    kite: dict[str, Any]
    external_gates: tuple[str, ...]


def _serialize_guidance(guidance: FinalGuidance | None) -> dict[str, Any] | None:
    if guidance is None:
        return None
    payload = asdict(guidance)
    verdict = payload.get("verdict")
    if hasattr(verdict, "value"):
        payload["verdict"] = verdict.value
    return payload


def build_command_center_snapshot(
    operating: OperatingState,
    *,
    guidance: FinalGuidance | None = None,
    journal: TradeBrainJournalStore | None = None,
    kite: KiteReadOnlyAdapter | None = None,
) -> CommandCenterSnapshot:
    policy = tradebrain_bse_policy()
    store = journal or TradeBrainJournalStore()
    kite_adapter = kite or KiteReadOnlyAdapter()
    manual = store.list_manual_trades()
    shadow = store.list_shadow_advisories()
    gates: list[str] = []
    if guidance is None:
        gates.append("authoritative_guidance_not_supplied")
    if not kite_adapter.readiness.authenticated_read_ready:
        gates.append("kite_read_only_data_not_authenticated")
    if not shadow:
        gates.append("live_shadow_evidence_missing")

    return CommandCenterSnapshot(
        profile=policy.profile_name,
        company_name=policy.primary_security.company_name,
        instrument=policy.primary_security.instrument,
        advisory_only=policy.advisory_only,
        auto_execution=policy.auto_execution,
        operating=asdict(operating),
        guidance=_serialize_guidance(guidance),
        manual_trade_count=len(manual),
        open_manual_trade_count=sum(item.status.value == "open" for item in manual),
        shadow_advisory_count=len(shadow),
        pending_shadow_count=sum(item.status.value == "pending" for item in shadow),
        kite=asdict(kite_adapter.readiness),
        external_gates=tuple(gates),
    )
