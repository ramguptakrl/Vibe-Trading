"""TradeBrain integration namespace.

The package is intentionally additive. Importing it does not alter Vibe-Trading
runtime behavior. Custom behavior is activated only when a caller explicitly
resolves and uses a TradeBrain profile.
"""

from .profile import (
    TRADEBRAIN_BSE_PROFILE,
    TRADEBRAIN_PROFILE_ENV,
    TradeBrainBSEPolicy,
    active_profile_name,
    get_active_tradebrain_policy,
    tradebrain_bse_policy,
)

__all__ = [
    "TRADEBRAIN_BSE_PROFILE",
    "TRADEBRAIN_PROFILE_ENV",
    "TradeBrainBSEPolicy",
    "active_profile_name",
    "get_active_tradebrain_policy",
    "tradebrain_bse_policy",
]
