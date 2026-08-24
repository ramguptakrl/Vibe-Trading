"""Centralized environment access for the optional TradeBrain Kite adapter."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

__all__ = ["KiteEnvironment", "get_kite_environment"]


@dataclass(frozen=True)
class KiteEnvironment:
    api_key: str | None
    access_token: str | None
    account_class: str


def get_kite_environment(environ: Mapping[str, str] | None = None) -> KiteEnvironment:
    """Read optional Kite data credentials through the repository config layer."""
    source = os.environ if environ is None else environ
    return KiteEnvironment(
        api_key=(source.get("KITE_API_KEY") or "").strip() or None,
        access_token=(source.get("KITE_ACCESS_TOKEN") or "").strip() or None,
        account_class=(source.get("KITE_ACCOUNT_CLASS") or "nri_non_pis").strip().lower(),
    )
