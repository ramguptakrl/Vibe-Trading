"""Environment accessors for the opt-in TradeBrain profile."""

from __future__ import annotations

import os
from typing import Mapping

TRADEBRAIN_PROFILE_ENV = "VIBE_TRADING_PROFILE"


def get_tradebrain_profile_value(environ: Mapping[str, str] | None = None) -> str:
    """Return the normalized TradeBrain profile selector.

    Raw process-environment access stays in the config layer. Tests and callers
    may inject a mapping to keep profile resolution deterministic.
    """

    source = os.environ if environ is None else environ
    return str(source.get(TRADEBRAIN_PROFILE_ENV, "")).strip().lower()
