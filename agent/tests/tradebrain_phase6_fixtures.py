from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.tradebrain.crash_guard import CrashGuardState
from src.tradebrain.historical_outcomes import build_bse_plan_snapshot, build_replay_bar_batch
from src.tradebrain.market_data import OHLCVBar

IST = ZoneInfo("Asia/Kolkata")
ISIN = "INE118H01025"


@dataclass(frozen=True)
class Identity:
    isin: str = ISIN
    qualified_symbol: str = "NSE:BSE"
    vibe_symbol: str = "BSE.NS"


@dataclass(frozen=True)
class Readiness:
    identity_verified: bool = True
    market_data_ready: bool = True
    intelligence_ready: bool = True
    market_structure_ready: bool = True
    historical_outcomes_ready: bool = False
    hard_rule_arbiter_ready: bool = False

    @property
    def decision_ready(self):
        return all((
            self.identity_verified,
            self.market_data_ready,
            self.intelligence_ready,
            self.market_structure_ready,
            self.historical_outcomes_ready,
            self.hard_rule_arbiter_ready,
        ))

    @property
    def missing_layers(self):
        flags = {
            "market_data": self.market_data_ready,
            "intelligence": self.intelligence_ready,
            "market_structure": self.market_structure_ready,
            "historical_outcomes": self.historical_outcomes_ready,
            "hard_rule_arbiter": self.hard_rule_arbiter_ready,
        }
        return tuple(k for k, v in flags.items() if not v)


@dataclass(frozen=True)
class TF:
    interval: str = "5m"
    config_version: str = "phase5-provisional-v1"


@dataclass(frozen=True)
class Structure:
    isin: str
    qualified_symbol: str
    source_frame_sha256: str
    native_interval: str
    as_of: str
    native_bar_count: int
    native_latest_timestamp: str
    timeframes: tuple[TF, ...]
    requested_intervals: tuple[str, ...] = ("5m",)


@dataclass(frozen=True)
class Crash:
    state: CrashGuardState
    reasons: tuple[str, ...]
    config_version: str = "phase5-provisional-v1"
    config_learned: bool = False
    block_day_long: bool = False
    block_swing_long: bool = False
    create_short_signal: bool = False

    @property
    def usable(self):
        return self.state is not CrashGuardState.DATA_INSUFFICIENT


@dataclass(frozen=True)
class Event:
    source_event_id: str
    title: str
    published_at: str


@dataclass(frozen=True)
class Intelligence:
    as_of: str
    events: tuple[Event, ...] = ()


@dataclass(frozen=True)
class Foundation:
    profile_name: str
    advisory_only: bool
    auto_execution: bool
    identity: Identity


@dataclass(frozen=True)
class Market:
    source_name: str
    frame_sha256: str
    bars: tuple[OHLCVBar, ...]


@dataclass(frozen=True)
class Phase4:
    foundation: Foundation
    market_data: Market
    intelligence: Intelligence


@dataclass(frozen=True)
class Phase5:
    phase4: Phase4
    structure: Structure
    crash_guard: Crash
    readiness: Readiness


def make_bar(ts, o=100, h=102, l=98, c=100, v=1000):
    return OHLCVBar(ts.isoformat(), float(o), float(h), float(l), float(c), float(v))


def make_phase5(*, decision=None, crash=CrashGuardState.NORMAL, event_title="none", ready=True):
    if decision is None:
        decision = datetime(2026, 8, 21, 10, 0, tzinfo=IST)
    start = decision - timedelta(minutes=45)
    bars = tuple(
        make_bar(start + timedelta(minutes=5*i), c=100 + 0.1*i)
        for i in range(9)
    )
    frame_hash = "a" * 64
    latest = bars[-1].timestamp
    foundation = Foundation("tradebrain_bse", True, False, Identity())
    market = Market("test_loader", frame_hash, bars)
    intel = Intelligence(
        as_of=(decision - timedelta(minutes=1)).isoformat(),
        events=() if event_title == "none" else (
            Event("E1", event_title, (decision - timedelta(minutes=2)).isoformat()),
        ),
    )
    structure = Structure(
        ISIN,
        "NSE:BSE",
        frame_hash,
        "5m",
        decision.isoformat(),
        len(bars),
        latest,
        (TF(),),
    )
    crash_obj = Crash(
        state=crash,
        reasons=("synthetic",) if crash is not CrashGuardState.NORMAL else (),
        block_day_long=crash is CrashGuardState.SEVERE,
        block_swing_long=crash is CrashGuardState.SEVERE,
    )
    return Phase5(
        Phase4(foundation, market, intel),
        structure,
        crash_obj,
        Readiness(market_structure_ready=ready),
    )


def make_setup(*, phase5=None, mode="day", direction="long", gaps=(), entry=100, target=110, stop=95):
    phase5 = phase5 or make_phase5()
    return build_bse_plan_snapshot(
        phase5,
        setup_id="S1",
        mode=mode,
        direction=direction,
        entry=entry,
        target=target,
        stop=stop,
        known_data_gaps=gaps,
    )


def future_bars(decision=None, rows=None):
    decision = decision or datetime(2026, 8, 21, 10, 0, tzinfo=IST)
    rows = rows or [
        (100, 102, 98, 101, 1000),
        (101, 103, 99, 102, 1000),
        (102, 104, 100, 103, 1000),
        (103, 105, 101, 104, 1000),
        (104, 106, 102, 105, 1000),
        (105, 107, 103, 106, 1000),
    ]
    return tuple(
        make_bar(
            decision + timedelta(minutes=5*i),
            o=row[0], h=row[1], l=row[2], c=row[3], v=row[4],
        )
        for i, row in enumerate(rows)
    )


def replay_for(setup, bars, *, gaps=(), source="test_loader"):
    last = datetime.fromisoformat(bars[-1].timestamp) if bars else datetime.fromisoformat(setup.decision_at)
    return build_replay_bar_batch(
        setup,
        bars=bars,
        source_name=source,
        retrieved_at=last + timedelta(hours=1),
        declared_gaps=gaps,
    )




def stress_rows(stress=True):
    return [
        (100, 101, 99, 100, 1000),
        (100, 101, 98, 99, 1000),
        (99, 100, 97, 98, 1000),
        (98, 99, 96, 97, 1000),
        (97, 98, 96, 97, 1000),
        (97, 98, 94 if stress else 96, 97, 1000),
    ]
