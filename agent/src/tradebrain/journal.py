"""Persistent manual-trade and shadow-advisory journal for TradeBrain BSE.

Runtime data lives under ``VIBE_TRADING_HOME/tradebrain`` and never in the repo.
The journal records what the advisory said and what actually happened; it does
not place, modify, or cancel broker orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any
from uuid import uuid4

from src.config.paths import get_runtime_root

__all__ = [
    "ManualTradeRecord",
    "ManualTradeStatus",
    "ShadowAdvisoryRecord",
    "ShadowStatus",
    "TradeBrainJournalStore",
]


class ManualTradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ShadowStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(body.encode("utf-8")).hexdigest()


def _finite_positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        op = ">= 0" if allow_zero else "> 0"
        raise ValueError(f"{name} must be finite and {op}")
    return number


@dataclass(frozen=True)
class ManualTradeRecord:
    trade_id: str
    advisory_id: str
    guidance_sha256: str
    mode: str
    direction: str
    planned_entry: float
    planned_target: float
    planned_stop: float
    actual_entry: float
    quantity: float
    opened_at: str
    status: ManualTradeStatus
    actual_exit: float | None
    closed_at: str | None
    costs: float | None
    realized_pnl: float | None
    exit_reason: str | None
    predicted_outcome: str | None
    actual_outcome: str | None
    note: str
    record_sha256: str


@dataclass(frozen=True)
class ShadowAdvisoryRecord:
    shadow_id: str
    advisory_id: str
    guidance_sha256: str
    mode: str
    direction: str
    entry: float
    target: float
    stop: float
    advisory_at: str
    status: ShadowStatus
    resolved_at: str | None
    outcome: str | None
    gross_r: float | None
    note: str
    record_sha256: str


class TradeBrainJournalStore:
    """Small atomic JSON store suitable for the single-user desktop runtime."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (get_runtime_root() / "tradebrain" / "journal.json")
        self._lock = RLock()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"manual_trades": [], "shadow_advisories": []}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "manual_trades": list(raw.get("manual_trades", [])),
            "shadow_advisories": list(raw.get("shadow_advisories", [])),
        }

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".journal.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @staticmethod
    def _manual_from_dict(row: dict[str, Any]) -> ManualTradeRecord:
        data = dict(row)
        data["status"] = ManualTradeStatus(data["status"])
        return ManualTradeRecord(**data)

    @staticmethod
    def _shadow_from_dict(row: dict[str, Any]) -> ShadowAdvisoryRecord:
        data = dict(row)
        data["status"] = ShadowStatus(data["status"])
        return ShadowAdvisoryRecord(**data)

    def list_manual_trades(self) -> tuple[ManualTradeRecord, ...]:
        with self._lock:
            rows = self._load()["manual_trades"]
        return tuple(self._manual_from_dict(row) for row in reversed(rows))

    def list_shadow_advisories(self) -> tuple[ShadowAdvisoryRecord, ...]:
        with self._lock:
            rows = self._load()["shadow_advisories"]
        return tuple(self._shadow_from_dict(row) for row in reversed(rows))

    def create_manual_trade(
        self,
        *,
        advisory_id: str,
        guidance_sha256: str,
        mode: str,
        direction: str,
        planned_entry: float,
        planned_target: float,
        planned_stop: float,
        actual_entry: float,
        quantity: float,
        opened_at: str | None = None,
        note: str = "",
    ) -> ManualTradeRecord:
        for name, value in {
            "advisory_id": advisory_id,
            "guidance_sha256": guidance_sha256,
            "mode": mode,
            "direction": direction,
        }.items():
            if not str(value).strip():
                raise ValueError(f"{name} is required")
        core: dict[str, Any] = {
            "trade_id": str(uuid4()),
            "advisory_id": advisory_id.strip(),
            "guidance_sha256": guidance_sha256.strip(),
            "mode": mode.strip().lower(),
            "direction": direction.strip().lower(),
            "planned_entry": _finite_positive(planned_entry, "planned_entry"),
            "planned_target": _finite_positive(planned_target, "planned_target"),
            "planned_stop": _finite_positive(planned_stop, "planned_stop"),
            "actual_entry": _finite_positive(actual_entry, "actual_entry"),
            "quantity": _finite_positive(quantity, "quantity"),
            "opened_at": opened_at or _now(),
            "status": ManualTradeStatus.OPEN.value,
            "actual_exit": None,
            "closed_at": None,
            "costs": None,
            "realized_pnl": None,
            "exit_reason": None,
            "predicted_outcome": None,
            "actual_outcome": None,
            "note": str(note or "").strip(),
        }
        record = dict(core, record_sha256=_hash(core))
        with self._lock:
            payload = self._load()
            payload["manual_trades"].append(record)
            self._save(payload)
        return self._manual_from_dict(record)

    def close_manual_trade(
        self,
        trade_id: str,
        *,
        actual_exit: float,
        costs: float,
        exit_reason: str,
        actual_outcome: str,
        predicted_outcome: str | None = None,
        closed_at: str | None = None,
    ) -> ManualTradeRecord:
        with self._lock:
            payload = self._load()
            for index, row in enumerate(payload["manual_trades"]):
                if row["trade_id"] != trade_id:
                    continue
                if row["status"] == ManualTradeStatus.CLOSED.value:
                    raise ValueError("manual trade is already closed")
                exit_px = _finite_positive(actual_exit, "actual_exit")
                fee = _finite_positive(costs, "costs", allow_zero=True)
                gross = (
                    (exit_px - float(row["actual_entry"])) * float(row["quantity"])
                    if row["direction"] == "long"
                    else (float(row["actual_entry"]) - exit_px) * float(row["quantity"])
                )
                updated = dict(row)
                updated.update(
                    actual_exit=exit_px,
                    closed_at=closed_at or _now(),
                    costs=fee,
                    realized_pnl=gross - fee,
                    exit_reason=str(exit_reason or "").strip(),
                    predicted_outcome=(str(predicted_outcome).strip() if predicted_outcome is not None else None),
                    actual_outcome=str(actual_outcome or "").strip(),
                    status=ManualTradeStatus.CLOSED.value,
                )
                updated.pop("record_sha256", None)
                updated["record_sha256"] = _hash(updated)
                payload["manual_trades"][index] = updated
                self._save(payload)
                return self._manual_from_dict(updated)
        raise KeyError(f"manual trade not found: {trade_id}")

    def create_shadow_advisory(
        self,
        *,
        advisory_id: str,
        guidance_sha256: str,
        mode: str,
        direction: str,
        entry: float,
        target: float,
        stop: float,
        advisory_at: str | None = None,
        note: str = "",
    ) -> ShadowAdvisoryRecord:
        for name, value in {
            "advisory_id": advisory_id,
            "guidance_sha256": guidance_sha256,
            "mode": mode,
            "direction": direction,
        }.items():
            if not str(value).strip():
                raise ValueError(f"{name} is required")
        core: dict[str, Any] = {
            "shadow_id": str(uuid4()),
            "advisory_id": advisory_id.strip(),
            "guidance_sha256": guidance_sha256.strip(),
            "mode": mode.strip().lower(),
            "direction": direction.strip().lower(),
            "entry": _finite_positive(entry, "entry"),
            "target": _finite_positive(target, "target"),
            "stop": _finite_positive(stop, "stop"),
            "advisory_at": advisory_at or _now(),
            "status": ShadowStatus.PENDING.value,
            "resolved_at": None,
            "outcome": None,
            "gross_r": None,
            "note": str(note or "").strip(),
        }
        record = dict(core, record_sha256=_hash(core))
        with self._lock:
            payload = self._load()
            payload["shadow_advisories"].append(record)
            self._save(payload)
        return self._shadow_from_dict(record)

    def resolve_shadow_advisory(
        self,
        shadow_id: str,
        *,
        outcome: str,
        gross_r: float | None,
        resolved_at: str | None = None,
    ) -> ShadowAdvisoryRecord:
        if not str(outcome or "").strip():
            raise ValueError("outcome is required")
        if gross_r is not None and not math.isfinite(float(gross_r)):
            raise ValueError("gross_r must be finite when supplied")
        with self._lock:
            payload = self._load()
            for index, row in enumerate(payload["shadow_advisories"]):
                if row["shadow_id"] != shadow_id:
                    continue
                if row["status"] == ShadowStatus.RESOLVED.value:
                    raise ValueError("shadow advisory is already resolved")
                updated = dict(row)
                updated.update(
                    status=ShadowStatus.RESOLVED.value,
                    resolved_at=resolved_at or _now(),
                    outcome=str(outcome).strip(),
                    gross_r=None if gross_r is None else float(gross_r),
                )
                updated.pop("record_sha256", None)
                updated["record_sha256"] = _hash(updated)
                payload["shadow_advisories"][index] = updated
                self._save(payload)
                return self._shadow_from_dict(updated)
        raise KeyError(f"shadow advisory not found: {shadow_id}")
