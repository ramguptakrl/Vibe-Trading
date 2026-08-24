"""Read-only Zerodha Kite adapter boundary for TradeBrain BSE.

The adapter intentionally exposes only authentication helpers, exact identity,
quote, historical-candle and market-stream construction. There are no
order/position mutation methods.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping, Sequence

from src.tradebrain.resident_advisory import DataCredentialUse, ReadOnlyMarketDataCredential

__all__ = [
    "KiteConfiguration",
    "KiteReadOnlyAdapter",
    "KiteReadiness",
    "KiteSDKUnavailable",
]

_BSE_ISIN = "INE118H01025"


class KiteSDKUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class KiteConfiguration:
    api_key: str | None
    access_token: str | None
    account_class: str = "nri_non_pis"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "KiteConfiguration":
        source = os.environ if environ is None else environ
        return cls(
            api_key=(source.get("KITE_API_KEY") or "").strip() or None,
            access_token=(source.get("KITE_ACCESS_TOKEN") or "").strip() or None,
            account_class=(source.get("KITE_ACCOUNT_CLASS") or "nri_non_pis").strip().lower(),
        )


@dataclass(frozen=True)
class KiteReadiness:
    sdk_available: bool
    api_key_configured: bool
    access_token_configured: bool
    authenticated_read_ready: bool
    read_only: bool = True
    broker_order_write_allowed: bool = False


class KiteReadOnlyAdapter:
    def __init__(self, config: KiteConfiguration | None = None) -> None:
        self.config = config or KiteConfiguration.from_env()
        self.credential = ReadOnlyMarketDataCredential(
            provider="zerodha_kite",
            account_class=self.config.account_class,
            uses=(DataCredentialUse.BACKTEST, DataCredentialUse.HISTORICAL, DataCredentialUse.LIVE),
            read_only=True,
            affects_target_persona=False,
        )
        try:
            from kiteconnect import KiteConnect, KiteTicker  # type: ignore
        except ImportError:
            self._kite_cls = None
            self._ticker_cls = None
        else:
            self._kite_cls = KiteConnect
            self._ticker_cls = KiteTicker
        self._client: Any | None = None
        self._bound_access_token: str | None = None

    @property
    def readiness(self) -> KiteReadiness:
        sdk = self._kite_cls is not None and self._ticker_cls is not None
        key = bool(self.config.api_key)
        token = bool(self._effective_access_token())
        return KiteReadiness(
            sdk_available=sdk,
            api_key_configured=key,
            access_token_configured=token,
            authenticated_read_ready=sdk and key and token,
        )

    def _effective_access_token(self) -> str | None:
        return self._bound_access_token or self.config.access_token

    def login_url(self) -> str:
        if self._kite_cls is None:
            raise KiteSDKUnavailable("Install the optional Kite SDK: pip install 'kiteconnect>=5.2.1,<6'")
        if not self.config.api_key:
            raise RuntimeError("KITE_API_KEY is not configured")
        return self._kite_cls(api_key=self.config.api_key).login_url()

    def bind_access_token(self, access_token: str) -> None:
        if self._kite_cls is None:
            raise KiteSDKUnavailable("Install the optional Kite SDK: pip install 'kiteconnect>=5.2.1,<6'")
        if not self.config.api_key:
            raise RuntimeError("KITE_API_KEY is not configured")
        token = str(access_token or "").strip()
        if not token:
            raise ValueError("access_token is required")
        self._bound_access_token = token
        self._client = self._kite_cls(api_key=self.config.api_key)
        self._client.set_access_token(token)

    def _read_client(self):
        if self._client is not None:
            return self._client
        if self._kite_cls is None:
            raise KiteSDKUnavailable("Install the optional Kite SDK: pip install 'kiteconnect>=5.2.1,<6'")
        token = self._effective_access_token()
        if not self.config.api_key or not token:
            raise RuntimeError("Kite read-only data access is not authenticated")
        self._client = self._kite_cls(api_key=self.config.api_key)
        self._client.set_access_token(token)
        return self._client

    def build_market_stream(self):
        """Build a KiteTicker WebSocket client for read-only market ticks."""
        if self._ticker_cls is None:
            raise KiteSDKUnavailable("Install the optional Kite SDK: pip install 'kiteconnect>=5.2.1,<6'")
        token = self._effective_access_token()
        if not self.config.api_key or not token:
            raise RuntimeError("Kite read-only market stream is not authenticated")
        return self._ticker_cls(self.config.api_key, token)

    def resolve_bse_ltd_instrument(self) -> dict[str, Any]:
        """Resolve exact BSE Ltd equity by NSE symbol and ISIN where present."""
        instruments = self._read_client().instruments("NSE")
        matches = [
            row for row in instruments
            if str(row.get("tradingsymbol", "")).upper() == "BSE"
            and str(row.get("exchange", "NSE")).upper() == "NSE"
            and str(row.get("instrument_type", "")).upper() in {"EQ", ""}
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one NSE:BSE equity instrument; found {len(matches)}")
        row = dict(matches[0])
        isin = str(row.get("isin", "")).upper().strip()
        if isin and isin != _BSE_ISIN:
            raise RuntimeError(f"NSE:BSE ISIN mismatch: expected {_BSE_ISIN}, got {isin}")
        return row

    def quote(self, instrument: str = "NSE:BSE") -> dict[str, Any]:
        result = self._read_client().quote([instrument])
        return dict(result[instrument])

    def historical_candles(
        self,
        instrument_token: int,
        from_date: Any,
        to_date: Any,
        interval: str,
        *,
        continuous: bool = False,
        oi: bool = False,
    ) -> Sequence[dict[str, Any]]:
        return self._read_client().historical_data(
            instrument_token,
            from_date,
            to_date,
            interval,
            continuous=continuous,
            oi=oi,
        )

    @staticmethod
    def forbidden_write_methods() -> tuple[str, ...]:
        return (
            "place_order",
            "modify_order",
            "cancel_order",
            "convert_position",
            "place_gtt",
            "modify_gtt",
            "delete_gtt",
        )
