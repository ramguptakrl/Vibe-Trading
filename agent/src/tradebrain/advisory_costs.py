"""Phase-8 advisory equity cost engine for BSE DAY and SWING plans.

This module is deliberately separate from broker execution eligibility.  It can
cost a hypothetical/advisory DAY or SWING plan even when a particular account
cannot execute the product.  MTF, when used, remains an optional funding overlay
implemented in :mod:`src.tradebrain.mtf_costs`.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, getcontext
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

getcontext().prec = 34
D = Decimal
PAISE = D("0.01")
RUPEE = D("1")

__all__ = [
    "AdviceCostValidationError",
    "AdviceTradeMode",
    "AdviceDirection",
    "AdviceSettlementClass",
    "EquityBrokerageProfile",
    "EquityAdvicePosition",
    "EquityChargeBreakdown",
    "EquityTradeEconomics",
    "ZerodhaEquityChargeSchedule",
    "build_equity_advice_position",
    "calculate_equity_trade_economics",
    "required_exit_price_for_net_target",
    "zerodha_equity_schedule_2026_08_21",
    "zerodha_resident_brokerage_2026_08_21",
    "zerodha_nri_nonpis_brokerage_2026_08_21",
]


class AdviceCostValidationError(ValueError):
    pass


class AdviceTradeMode(str, Enum):
    DAY = "day"
    SWING = "swing"


class AdviceDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class AdviceSettlementClass(str, Enum):
    INTRADAY = "intraday"
    DELIVERY = "delivery"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


def _dec(value: object, name: str, *, positive=False, nonnegative=False) -> Decimal:
    try:
        out = D(str(value))
    except Exception as exc:  # noqa: BLE001
        raise AdviceCostValidationError(f"{name} must be numeric") from exc
    if not out.is_finite():
        raise AdviceCostValidationError(f"{name} must be finite")
    if positive and out <= 0:
        raise AdviceCostValidationError(f"{name} must be > 0")
    if nonnegative and out < 0:
        raise AdviceCostValidationError(f"{name} must be >= 0")
    return out


def _money(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def _stt_rupee(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP)


def _aware(value: str | datetime, name: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise AdviceCostValidationError(f"{name} must be ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise AdviceCostValidationError(f"{name} must be timezone-aware")
    return dt


def _canon(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canon(item) for item in value]
    if is_dataclass(value):
        return {f.name: _canon(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _hash(value: object) -> str:
    body = json.dumps(_canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(body.encode("utf-8")).hexdigest()


def _official_zerodha_https(url: str) -> bool:
    parsed = urlparse(str(url))
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "zerodha.com" or host.endswith(".zerodha.com"))


@dataclass(frozen=True)
class ZerodhaEquityChargeSchedule:
    """Statutory/exchange/equity charges verified from official Zerodha sources."""

    version: str
    applicable_from: str
    verified_at: str
    applicability_basis: str
    source_urls: tuple[str, ...]
    gst_rate: Decimal
    stt_delivery_rate: Decimal
    stt_intraday_sell_rate: Decimal
    nse_equity_transaction_rate: Decimal
    bse_equity_transaction_rate: Decimal
    sebi_turnover_rate: Decimal
    stamp_delivery_buy_rate: Decimal
    stamp_intraday_buy_rate: Decimal
    dp_male_base_rupees: Decimal
    dp_female_base_rupees: Decimal
    auto_squareoff_base_rupees: Decimal
    timezone: str = "Asia/Kolkata"

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise AdviceCostValidationError("charge schedule version is required")
        _aware(self.verified_at, "verified_at")
        try:
            datetime.fromisoformat(self.applicable_from)
        except ValueError as exc:
            raise AdviceCostValidationError("applicable_from must be ISO date") from exc
        if not self.source_urls or any(not _official_zerodha_https(u) for u in self.source_urls):
            raise AdviceCostValidationError("official Zerodha HTTPS source_urls are required")
        for name in (
            "gst_rate", "stt_delivery_rate", "stt_intraday_sell_rate",
            "nse_equity_transaction_rate", "bse_equity_transaction_rate",
            "sebi_turnover_rate", "stamp_delivery_buy_rate", "stamp_intraday_buy_rate",
            "dp_male_base_rupees", "dp_female_base_rupees", "auto_squareoff_base_rupees",
        ):
            object.__setattr__(self, name, _dec(getattr(self, name), name, nonnegative=True))

    @property
    def sha256(self) -> str:
        return _hash(self)

    def exchange_transaction_rate(self, exchange: Exchange) -> Decimal:
        return self.nse_equity_transaction_rate if exchange is Exchange.NSE else self.bse_equity_transaction_rate


@dataclass(frozen=True)
class EquityBrokerageProfile:
    """Fee profile only; never an account/product eligibility decision."""

    version: str
    applicable_from: str
    verified_at: str
    source_urls: tuple[str, ...]
    intraday_rate: Decimal
    intraday_cap_rupees: Decimal
    delivery_rate: Decimal
    delivery_cap_rupees: Decimal
    eligibility_neutral: bool = True

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise AdviceCostValidationError("brokerage profile version is required")
        _aware(self.verified_at, "verified_at")
        try:
            datetime.fromisoformat(self.applicable_from)
        except ValueError as exc:
            raise AdviceCostValidationError("applicable_from must be ISO date") from exc
        if not self.source_urls or any(not _official_zerodha_https(u) for u in self.source_urls):
            raise AdviceCostValidationError("official Zerodha HTTPS source_urls are required")
        for name in ("intraday_rate", "intraday_cap_rupees", "delivery_rate", "delivery_cap_rupees"):
            object.__setattr__(self, name, _dec(getattr(self, name), name, nonnegative=True))

    @property
    def sha256(self) -> str:
        return _hash(self)

    def brokerage(self, notional: Decimal, settlement: AdviceSettlementClass) -> Decimal:
        if settlement is AdviceSettlementClass.INTRADAY:
            rate, cap = self.intraday_rate, self.intraday_cap_rupees
        else:
            rate, cap = self.delivery_rate, self.delivery_cap_rupees
        raw = notional * rate
        if cap > 0:
            raw = min(raw, cap)
        return _money(raw)


@dataclass(frozen=True)
class SlippageAssumption:
    version: str
    entry_bps: Decimal
    exit_bps: Decimal
    basis: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.basis.strip():
            raise AdviceCostValidationError("slippage version and basis are required")
        object.__setattr__(self, "entry_bps", _dec(self.entry_bps, "entry_bps", nonnegative=True))
        object.__setattr__(self, "exit_bps", _dec(self.exit_bps, "exit_bps", nonnegative=True))

    @property
    def sha256(self) -> str:
        return _hash(self)


@dataclass(frozen=True)
class EquityAdvicePosition:
    qualified_symbol: str
    exchange: Exchange
    mode: AdviceTradeMode
    direction: AdviceDirection
    quantity: int
    entry_reference_price: Decimal
    entry_execution_price: Decimal
    slippage_sha256: str

    @property
    def position_sha256(self) -> str:
        return _hash(self)


@dataclass(frozen=True)
class EquityChargeBreakdown:
    entry_brokerage: Decimal
    exit_brokerage: Decimal
    entry_transaction_charge: Decimal
    exit_transaction_charge: Decimal
    entry_sebi_fee: Decimal
    exit_sebi_fee: Decimal
    entry_gst: Decimal
    exit_gst: Decimal
    entry_stt: Decimal
    exit_stt: Decimal
    buy_stamp_duty: Decimal
    dp_charge: Decimal
    auto_squareoff_charge: Decimal
    slippage_cost: Decimal
    total_charges: Decimal


@dataclass(frozen=True)
class EquityTradeEconomics:
    position: EquityAdvicePosition
    settlement_class: AdviceSettlementClass
    charge_schedule_version: str
    charge_schedule_sha256: str
    brokerage_profile_version: str
    brokerage_profile_sha256: str
    entry_at: str
    exit_at: str
    exit_reference_price: Decimal
    exit_execution_price: Decimal
    gross_pnl: Decimal
    charges: EquityChargeBreakdown
    net_pnl: Decimal
    net_return_on_entry_notional: Decimal
    break_even_exit_price: Decimal | None
    target_exit_price: Decimal | None
    target_net_profit: Decimal | None
    cost_model_version: str
    costs_complete: bool

    @property
    def economics_sha256(self) -> str:
        return _hash(self)


def zerodha_equity_schedule_2026_08_21() -> ZerodhaEquityChargeSchedule:
    return ZerodhaEquityChargeSchedule(
        version="zerodha-equity-2026-08-21-v1",
        applicable_from="2026-08-21",
        verified_at="2026-08-21T19:28:00+00:00",
        applicability_basis="first_verified_date; not a claim that every rate changed on this date",
        source_urls=(
            "https://zerodha.com/charges/",
            "https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/how-is-the-securities-transaction-tax-stt-calculated",
            "https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/exchange-transaction-charges",
            "https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/auto-square-off",
        ),
        gst_rate=D("0.18"),
        stt_delivery_rate=D("0.001"),
        stt_intraday_sell_rate=D("0.00025"),
        nse_equity_transaction_rate=D("0.0000307"),
        bse_equity_transaction_rate=D("0.0000375"),
        sebi_turnover_rate=D("0.000001"),
        stamp_delivery_buy_rate=D("0.00015"),
        stamp_intraday_buy_rate=D("0.00003"),
        dp_male_base_rupees=D("13"),
        dp_female_base_rupees=D("12.75"),
        auto_squareoff_base_rupees=D("50"),
    )


def zerodha_resident_brokerage_2026_08_21() -> EquityBrokerageProfile:
    return EquityBrokerageProfile(
        version="zerodha-resident-equity-2026-08-21-v1",
        applicable_from="2026-08-21",
        verified_at="2026-08-21T19:28:00+00:00",
        source_urls=(
            "https://zerodha.com/charges/",
            "https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/what-is-the-brokerage-at-zerodha-for-equity",
        ),
        intraday_rate=D("0.0003"), intraday_cap_rupees=D("20"),
        delivery_rate=D("0"), delivery_cap_rupees=D("0"),
    )


def zerodha_nri_nonpis_brokerage_2026_08_21() -> EquityBrokerageProfile:
    """Fee-only NRI Non-PIS profile; it does not decide whether a trade is allowed."""

    return EquityBrokerageProfile(
        version="zerodha-nri-nonpis-equity-2026-08-21-v1",
        applicable_from="2026-08-21",
        verified_at="2026-08-21T19:28:00+00:00",
        source_urls=("https://zerodha.com/charges/",),
        intraday_rate=D("0.005"), intraday_cap_rupees=D("50"),
        delivery_rate=D("0.005"), delivery_cap_rupees=D("50"),
    )


def _validate_applicability(applicable_from: str, when: datetime, timezone_name: str) -> None:
    date = when.astimezone(ZoneInfo(timezone_name)).date()
    if date < datetime.fromisoformat(applicable_from).date():
        raise AdviceCostValidationError(
            f"current verified cost snapshot cannot be backfilled before {applicable_from}; supply a historical source-dated schedule/profile"
        )


def build_equity_advice_position(
    *,
    qualified_symbol: str,
    exchange: Exchange | str,
    mode: AdviceTradeMode | str,
    direction: AdviceDirection | str,
    quantity: int,
    entry_reference_price: Decimal | float | str,
    slippage: SlippageAssumption,
) -> EquityAdvicePosition:
    if quantity < 1:
        raise AdviceCostValidationError("quantity must be >= 1")
    ex = exchange if isinstance(exchange, Exchange) else Exchange(str(exchange).upper())
    prefix = str(qualified_symbol).split(":", 1)[0].upper() if ":" in str(qualified_symbol) else ""
    if prefix != ex.value:
        raise AdviceCostValidationError("qualified_symbol exchange prefix does not match exchange")
    m = mode if isinstance(mode, AdviceTradeMode) else AdviceTradeMode(str(mode).lower())
    d = direction if isinstance(direction, AdviceDirection) else AdviceDirection(str(direction).lower())
    if m is AdviceTradeMode.SWING and d is AdviceDirection.SHORT:
        raise AdviceCostValidationError("SWING/POSITION equity advice remains LONG-only")
    ref = _dec(entry_reference_price, "entry_reference_price", positive=True)
    sign = D("1") if d is AdviceDirection.LONG else D("-1")
    execution = _money(ref * (D("1") + sign * slippage.entry_bps / D("10000")))
    if execution <= 0:
        raise AdviceCostValidationError("entry execution price must be positive after slippage")
    return EquityAdvicePosition(
        qualified_symbol=str(qualified_symbol), exchange=ex, mode=m, direction=d,
        quantity=int(quantity), entry_reference_price=_money(ref), entry_execution_price=execution,
        slippage_sha256=slippage.sha256,
    )


def _settlement(position: EquityAdvicePosition, entry_at: datetime, exit_at: datetime, timezone_name: str) -> AdviceSettlementClass:
    tz = ZoneInfo(timezone_name)
    same_day = entry_at.astimezone(tz).date() == exit_at.astimezone(tz).date()
    if position.mode is AdviceTradeMode.DAY:
        if not same_day:
            raise AdviceCostValidationError("DAY advice costs require same-session/same-date exit")
        return AdviceSettlementClass.INTRADAY
    # A SWING idea closed the same day is charged as intraday by Zerodha; otherwise delivery.
    return AdviceSettlementClass.INTRADAY if same_day else AdviceSettlementClass.DELIVERY


def _side_base(
    notional: Decimal,
    *,
    settlement: AdviceSettlementClass,
    exchange: Exchange,
    brokerage: EquityBrokerageProfile,
    schedule: ZerodhaEquityChargeSchedule,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    b = brokerage.brokerage(notional, settlement)
    txn = _money(notional * schedule.exchange_transaction_rate(exchange))
    sebi = _money(notional * schedule.sebi_turnover_rate)
    gst = _money((b + txn + sebi) * schedule.gst_rate)
    return b, txn, sebi, gst


def _calc_once(
    position: EquityAdvicePosition,
    *,
    entry_at: datetime,
    exit_at: datetime,
    exit_reference_price: Decimal,
    schedule: ZerodhaEquityChargeSchedule,
    brokerage: EquityBrokerageProfile,
    slippage: SlippageAssumption,
    include_dp_charge: bool,
    female_primary_holder: bool,
    auto_squareoff_order_count: int,
) -> tuple[Decimal, AdviceSettlementClass, EquityChargeBreakdown, Decimal, Decimal]:
    if exit_at < entry_at:
        raise AdviceCostValidationError("exit_at cannot be earlier than entry_at")
    if position.slippage_sha256 != slippage.sha256:
        raise AdviceCostValidationError("slippage assumption does not match frozen position")
    if auto_squareoff_order_count < 0:
        raise AdviceCostValidationError("auto_squareoff_order_count cannot be negative")
    _validate_applicability(schedule.applicable_from, entry_at, schedule.timezone)
    _validate_applicability(brokerage.applicable_from, entry_at, schedule.timezone)
    settlement = _settlement(position, entry_at, exit_at, schedule.timezone)

    exit_sign = D("-1") if position.direction is AdviceDirection.LONG else D("1")
    exit_exec = _money(exit_reference_price * (D("1") + exit_sign * slippage.exit_bps / D("10000")))
    if exit_exec <= 0:
        raise AdviceCostValidationError("exit execution price must be positive after slippage")

    entry_value = _money(position.entry_execution_price * position.quantity)
    exit_value = _money(exit_exec * position.quantity)
    eb, etxn, esebi, egst = _side_base(entry_value, settlement=settlement, exchange=position.exchange, brokerage=brokerage, schedule=schedule)
    xb, xtxn, xsebi, xgst = _side_base(exit_value, settlement=settlement, exchange=position.exchange, brokerage=brokerage, schedule=schedule)

    entry_stt = exit_stt = D("0.00")
    stamp = D("0.00")
    if settlement is AdviceSettlementClass.DELIVERY:
        entry_stt = _stt_rupee(entry_value * schedule.stt_delivery_rate)
        exit_stt = _stt_rupee(exit_value * schedule.stt_delivery_rate)
        stamp = _money(entry_value * schedule.stamp_delivery_buy_rate)
    else:
        # STT is on the sell side only; stamp duty is on the buy side only.
        if position.direction is AdviceDirection.LONG:
            exit_stt = _stt_rupee(exit_value * schedule.stt_intraday_sell_rate)
            stamp = _money(entry_value * schedule.stamp_intraday_buy_rate)
        else:
            entry_stt = _stt_rupee(entry_value * schedule.stt_intraday_sell_rate)
            stamp = _money(exit_value * schedule.stamp_intraday_buy_rate)

    dp = D("0.00")
    if settlement is AdviceSettlementClass.DELIVERY and include_dp_charge:
        base = schedule.dp_female_base_rupees if female_primary_holder else schedule.dp_male_base_rupees
        dp = _money(base * (D("1") + schedule.gst_rate))
    auto_sq = _money(schedule.auto_squareoff_base_rupees * auto_squareoff_order_count * (D("1") + schedule.gst_rate))

    if position.direction is AdviceDirection.LONG:
        gross = _money(exit_value - entry_value)
        entry_slip = max(D("0"), position.entry_execution_price - position.entry_reference_price) * position.quantity
        exit_slip = max(D("0"), exit_reference_price - exit_exec) * position.quantity
    else:
        gross = _money(entry_value - exit_value)
        entry_slip = max(D("0"), position.entry_reference_price - position.entry_execution_price) * position.quantity
        exit_slip = max(D("0"), exit_exec - exit_reference_price) * position.quantity
    slippage_cost = _money(entry_slip + exit_slip)
    total = _money(eb + xb + etxn + xtxn + esebi + xsebi + egst + xgst + entry_stt + exit_stt + stamp + dp + auto_sq)
    net = _money(gross - total)
    charges = EquityChargeBreakdown(
        entry_brokerage=eb, exit_brokerage=xb,
        entry_transaction_charge=etxn, exit_transaction_charge=xtxn,
        entry_sebi_fee=esebi, exit_sebi_fee=xsebi,
        entry_gst=egst, exit_gst=xgst,
        entry_stt=entry_stt, exit_stt=exit_stt,
        buy_stamp_duty=stamp, dp_charge=dp, auto_squareoff_charge=auto_sq,
        slippage_cost=slippage_cost, total_charges=total,
    )
    return exit_exec, settlement, charges, gross, net


def required_exit_price_for_net_target(
    position: EquityAdvicePosition,
    *,
    entry_at: str | datetime,
    exit_at: str | datetime,
    schedule: ZerodhaEquityChargeSchedule,
    brokerage: EquityBrokerageProfile,
    slippage: SlippageAssumption,
    net_target_rupees: Decimal | float | str = 0,
    include_dp_charge: bool = True,
    female_primary_holder: bool = False,
    auto_squareoff_order_count: int = 0,
    tick_size: Decimal | float | str | None = None,
) -> Decimal:
    target = _dec(net_target_rupees, "net_target_rupees")
    entry_dt, exit_dt = _aware(entry_at, "entry_at"), _aware(exit_at, "exit_at")

    def pnl(ref: Decimal) -> Decimal:
        return _calc_once(
            position, entry_at=entry_dt, exit_at=exit_dt, exit_reference_price=ref,
            schedule=schedule, brokerage=brokerage, slippage=slippage,
            include_dp_charge=include_dp_charge, female_primary_holder=female_primary_holder,
            auto_squareoff_order_count=auto_squareoff_order_count,
        )[4]

    if position.direction is AdviceDirection.LONG:
        low, high = D("0.01"), max(position.entry_execution_price * D("2"), position.entry_execution_price + D("100"))
        guard = 0
        while pnl(high) < target:
            high *= D("2")
            guard += 1
            if guard > 30:
                raise AdviceCostValidationError("unable to bracket long target exit price")
        for _ in range(120):
            mid = (low + high) / D("2")
            if pnl(mid) >= target:
                high = mid
            else:
                low = mid
        raw = _money(high)
        step = _dec(tick_size, "tick_size", positive=True) if tick_size is not None else PAISE
        units = (raw / step).quantize(RUPEE, rounding=ROUND_CEILING)
        candidate = _money(units * step)
        for _ in range(20):
            if pnl(candidate) >= target:
                return candidate
            candidate = _money(candidate + step)
    else:
        # For a short, lower cover price improves P&L. Find the highest price that still meets target.
        low, high = PAISE, position.entry_reference_price * D("2")
        if pnl(low) < target:
            raise AdviceCostValidationError("requested short net target is not attainable above zero price")
        for _ in range(120):
            mid = (low + high) / D("2")
            if pnl(mid) >= target:
                low = mid
            else:
                high = mid
        step = _dec(tick_size, "tick_size", positive=True) if tick_size is not None else PAISE
        # Floor to a tradable grid because lower price helps a short.
        units = (low / step).to_integral_value(rounding="ROUND_FLOOR")
        candidate = _money(units * step)
        for _ in range(20):
            if candidate > 0 and pnl(candidate) >= target:
                return candidate
            candidate = _money(candidate - step)
    raise AdviceCostValidationError("unable to satisfy net target on supplied price grid")


def calculate_equity_trade_economics(
    position: EquityAdvicePosition,
    *,
    entry_at: str | datetime,
    exit_at: str | datetime,
    exit_reference_price: Decimal | float | str,
    schedule: ZerodhaEquityChargeSchedule,
    brokerage: EquityBrokerageProfile,
    slippage: SlippageAssumption,
    include_dp_charge: bool = True,
    female_primary_holder: bool = False,
    auto_squareoff_order_count: int = 0,
    tick_size: Decimal | float | str | None = None,
    net_target_rupees: Decimal | float | str | None = None,
) -> EquityTradeEconomics:
    entry_dt, exit_dt = _aware(entry_at, "entry_at"), _aware(exit_at, "exit_at")
    exit_ref = _dec(exit_reference_price, "exit_reference_price", positive=True)
    exit_exec, settlement, charges, gross, net = _calc_once(
        position, entry_at=entry_dt, exit_at=exit_dt, exit_reference_price=exit_ref,
        schedule=schedule, brokerage=brokerage, slippage=slippage,
        include_dp_charge=include_dp_charge, female_primary_holder=female_primary_holder,
        auto_squareoff_order_count=auto_squareoff_order_count,
    )
    breakeven = required_exit_price_for_net_target(
        position, entry_at=entry_dt, exit_at=exit_dt, schedule=schedule,
        brokerage=brokerage, slippage=slippage, net_target_rupees=0,
        include_dp_charge=include_dp_charge, female_primary_holder=female_primary_holder,
        auto_squareoff_order_count=auto_squareoff_order_count, tick_size=tick_size,
    )
    target_price = target_net = None
    if net_target_rupees is not None:
        target_net = _money(_dec(net_target_rupees, "net_target_rupees"))
        target_price = required_exit_price_for_net_target(
            position, entry_at=entry_dt, exit_at=exit_dt, schedule=schedule,
            brokerage=brokerage, slippage=slippage, net_target_rupees=target_net,
            include_dp_charge=include_dp_charge, female_primary_holder=female_primary_holder,
            auto_squareoff_order_count=auto_squareoff_order_count, tick_size=tick_size,
        )
    entry_notional = _money(position.entry_execution_price * position.quantity)
    return EquityTradeEconomics(
        position=position, settlement_class=settlement,
        charge_schedule_version=schedule.version, charge_schedule_sha256=schedule.sha256,
        brokerage_profile_version=brokerage.version, brokerage_profile_sha256=brokerage.sha256,
        entry_at=entry_dt.isoformat(), exit_at=exit_dt.isoformat(),
        exit_reference_price=_money(exit_ref), exit_execution_price=exit_exec,
        gross_pnl=gross, charges=charges, net_pnl=net,
        net_return_on_entry_notional=(net / entry_notional if entry_notional else D("0")),
        break_even_exit_price=breakeven, target_exit_price=target_price,
        target_net_profit=target_net,
        cost_model_version=f"phase8-advice:{schedule.version}:{brokerage.version}:{slippage.version}",
        costs_complete=True,
    )
