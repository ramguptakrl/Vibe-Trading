"""HTTP surface for the opt-in TradeBrain BSE operational layer."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import sys as _sys
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.tradebrain.command_center import build_command_center_snapshot
from src.tradebrain.journal import TradeBrainJournalStore
from src.tradebrain.kite_readonly import KiteReadOnlyAdapter
from src.tradebrain.session_modes import resolve_operating_state

__all__ = ["register_tradebrain_routes"]

_journal: TradeBrainJournalStore | None = None


def _get_journal() -> TradeBrainJournalStore:
    global _journal
    if _journal is None:
        _journal = TradeBrainJournalStore()
    return _journal


def _wire(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _wire(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _weekday_trading_day(now: datetime) -> bool:
    # Runtime fallback only. Command Center exposes the calendar source so a
    # weekday is never mistaken for an NSE-holiday-verified session.
    return now.astimezone(ZoneInfo("Asia/Kolkata")).weekday() < 5


class CreateManualTradeRequest(BaseModel):
    advisory_id: str = Field(..., min_length=1, max_length=256)
    guidance_sha256: str = Field(..., min_length=1, max_length=128)
    mode: str = Field(..., min_length=1, max_length=32)
    direction: str = Field(..., min_length=1, max_length=16)
    planned_entry: float = Field(..., gt=0)
    planned_target: float = Field(..., gt=0)
    planned_stop: float = Field(..., gt=0)
    actual_entry: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    opened_at: str | None = None
    note: str = Field("", max_length=2000)


class CloseManualTradeRequest(BaseModel):
    actual_exit: float = Field(..., gt=0)
    costs: float = Field(..., ge=0)
    exit_reason: str = Field(..., min_length=1, max_length=512)
    actual_outcome: str = Field(..., min_length=1, max_length=64)
    predicted_outcome: str | None = Field(None, max_length=64)
    closed_at: str | None = None


class CreateShadowAdvisoryRequest(BaseModel):
    advisory_id: str = Field(..., min_length=1, max_length=256)
    guidance_sha256: str = Field(..., min_length=1, max_length=128)
    mode: str = Field(..., min_length=1, max_length=32)
    direction: str = Field(..., min_length=1, max_length=16)
    entry: float = Field(..., gt=0)
    target: float = Field(..., gt=0)
    stop: float = Field(..., gt=0)
    advisory_at: str | None = None
    note: str = Field("", max_length=2000)


class ResolveShadowAdvisoryRequest(BaseModel):
    outcome: str = Field(..., min_length=1, max_length=64)
    gross_r: float | None = None
    resolved_at: str | None = None


AuthDep = Callable[..., Awaitable[Any] | Any]


def register_tradebrain_routes(app: FastAPI, require_auth: AuthDep | None = None) -> None:
    host = _sys.modules.get("api_server") or _sys.modules.get("agent.api_server")
    if host is None:
        raise RuntimeError("register_tradebrain_routes: api_server module not in sys.modules")
    if require_auth is None:
        require_auth = host.require_auth

    dependencies = [Depends(require_auth)]

    @app.get("/tradebrain/bse/operating-mode", dependencies=dependencies)
    async def tradebrain_operating_mode() -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        state = resolve_operating_state(now, is_trading_day=_weekday_trading_day(now))
        payload = _wire(state)
        payload["calendar_source"] = "weekday_fallback_not_nse_holiday_verified"
        return payload

    @app.get("/tradebrain/bse/command-center", dependencies=dependencies)
    async def tradebrain_command_center() -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        state = resolve_operating_state(now, is_trading_day=_weekday_trading_day(now))
        snapshot = build_command_center_snapshot(
            state,
            journal=_get_journal(),
            kite=KiteReadOnlyAdapter(),
        )
        payload = _wire(snapshot)
        payload["calendar_source"] = "weekday_fallback_not_nse_holiday_verified"
        payload["external_gates"] = list(payload["external_gates"]) + [
            "verified_nse_exchange_calendar_not_bound",
            "real_historical_backfill_not_verified_by_this_endpoint",
        ]
        return payload

    @app.get("/tradebrain/bse/kite/status", dependencies=dependencies)
    async def tradebrain_kite_status() -> dict[str, Any]:
        # Never returns keys or tokens.
        return _wire(KiteReadOnlyAdapter().readiness)

    @app.get("/tradebrain/bse/journal/manual", dependencies=dependencies)
    async def list_manual_trades() -> list[dict[str, Any]]:
        return [_wire(item) for item in _get_journal().list_manual_trades()]

    @app.post("/tradebrain/bse/journal/manual", dependencies=dependencies)
    async def create_manual_trade(request: CreateManualTradeRequest) -> dict[str, Any]:
        try:
            record = _get_journal().create_manual_trade(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _wire(record)

    @app.post("/tradebrain/bse/journal/manual/{trade_id}/close", dependencies=dependencies)
    async def close_manual_trade(trade_id: str, request: CloseManualTradeRequest) -> dict[str, Any]:
        try:
            record = _get_journal().close_manual_trade(trade_id, **request.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _wire(record)

    @app.get("/tradebrain/bse/journal/shadow", dependencies=dependencies)
    async def list_shadow_advisories() -> list[dict[str, Any]]:
        return [_wire(item) for item in _get_journal().list_shadow_advisories()]

    @app.post("/tradebrain/bse/journal/shadow", dependencies=dependencies)
    async def create_shadow_advisory(request: CreateShadowAdvisoryRequest) -> dict[str, Any]:
        try:
            record = _get_journal().create_shadow_advisory(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _wire(record)

    @app.post("/tradebrain/bse/journal/shadow/{shadow_id}/resolve", dependencies=dependencies)
    async def resolve_shadow_advisory(shadow_id: str, request: ResolveShadowAdvisoryRequest) -> dict[str, Any]:
        try:
            record = _get_journal().resolve_shadow_advisory(shadow_id, **request.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _wire(record)
