"""The simulator. One generating process for every row in the ledger.

PDF S5, the only risk rated *Fatal*: if legitimate and fraudulent traffic come from
different generating processes, a gradient-boosted tree learns which program wrote each
row rather than which behaviour is fraudulent. The defence here is structural rather
than promised:

  * Every row - legitimate or fraudulent - is written by :class:`Emitter`. There is no
    second path. Amount rounding, identifier format, timestamp precision and null
    patterns are decided in one place and cannot diverge by class.
  * Identifiers are assigned after the whole run is sorted by time, so a transaction_id
    carries no information about when in the code a row was created.
  * Account traits that drive behaviour (activity rate, paste habit, amount scale) live
    outside the ledger. They are how the world works, not columns a detector may read.

Layers, per PDF S5.1: entity, behaviour, attack. The narrative layer is Phase 3.

    python -m adl.generate.simulator --transactions 200000 --out artifacts/ledger
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from adl.common.config import load_config
from adl.common.contracts import validate_chain
from adl.common.seeds import rng_for

GEOS = [
    "IN-MH-MUMBAI", "IN-MH-PUNE", "IN-KA-BENGALURU", "IN-DL-NEWDELHI",
    "IN-TN-CHENNAI", "IN-TS-HYDERABAD", "IN-WB-KOLKATA", "IN-GJ-AHMEDABAD",
    "IN-RJ-JAIPUR", "IN-KL-KOCHI",
]

# Joint structure lives here. Amount correlates with merchant category, which correlates
# with hour of day, which correlates with channel. Independent per-field sampling gives
# correct marginals and wrong structure - it passes a histogram check and fails a
# discriminator (PDF S5.1).
MCC_PROFILE: dict[str, dict[str, Any]] = {
    "5411": {"name": "grocery",      "scale": 780,   "sigma": 0.55, "peak_hour": 19, "spread": 3.4,
             "channels": {"cards_cnp": 0.25, "upi_instant": 0.65, "wallets_tokenisation": 0.10}},
    "5812": {"name": "restaurant",   "scale": 1250,  "sigma": 0.62, "peak_hour": 21, "spread": 2.6,
             "channels": {"cards_cnp": 0.35, "upi_instant": 0.55, "wallets_tokenisation": 0.10}},
    "5732": {"name": "electronics",  "scale": 16500, "sigma": 0.85, "peak_hour": 15, "spread": 4.5,
             "channels": {"cards_cnp": 0.72, "upi_instant": 0.20, "wallets_tokenisation": 0.08}},
    "4900": {"name": "utilities",    "scale": 2400,  "sigma": 0.50, "peak_hour": 11, "spread": 5.0,
             "channels": {"upi_instant": 0.70, "bank_transfer": 0.22, "cards_cnp": 0.08}},
    "6011": {"name": "cash",         "scale": 6500,  "sigma": 0.70, "peak_hour": 13, "spread": 4.0,
             "channels": {"bank_transfer": 0.60, "upi_instant": 0.40}},
    "5999": {"name": "retail",       "scale": 1900,  "sigma": 0.78, "peak_hour": 18, "spread": 4.2,
             "channels": {"cards_cnp": 0.45, "upi_instant": 0.45, "wallets_tokenisation": 0.10}},
    "7995": {"name": "gaming",       "scale": 4200,  "sigma": 0.95, "peak_hour": 23, "spread": 2.2,
             "channels": {"cards_cnp": 0.60, "wallets_tokenisation": 0.40}},
    "4814": {"name": "telecom",      "scale": 480,   "sigma": 0.45, "peak_hour": 10, "spread": 5.5,
             "channels": {"upi_instant": 0.80, "cards_cnp": 0.20}},
    "6012": {"name": "financial",    "scale": 24000, "sigma": 1.00, "peak_hour": 12, "spread": 3.8,
             "channels": {"bank_transfer": 0.85, "upi_instant": 0.15}},
}
MCCS = list(MCC_PROFILE)

SEGMENT_SCALE = {
    "retail_low": 0.45,
    "retail_mid": 1.0,
    "retail_high": 2.6,
    "sme": 4.2,
}


# ---------------------------------------------------------------------------
# Entity layer
# ---------------------------------------------------------------------------


@dataclass
class AccountTrait:
    """How one account behaves. Deliberately NOT part of the ledger.

    If ``paste_habit`` were a column, the detector would read the answer straight off
    the row. It is a property of the simulated person, and the only trace it leaves is
    the behaviour it produces.
    """

    account_id: str
    home_geo: str
    segment: str
    activity: float
    mcc_pref: list[str]
    mcc_weights: np.ndarray
    devices: list[str]
    paste_habit: float          # some people always paste a payee ID; many never do
    deliberation: float         # baseline hesitation multiplier before confirming
    sloppiness: float           # baseline correction rate


@dataclass
class Ledger:
    accounts: pd.DataFrame
    devices: pd.DataFrame
    merchants: pd.DataFrame
    transactions: pd.DataFrame
    sessions: pd.DataFrame
    session_events: pd.DataFrame
    graph_edges: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        n = len(self.transactions)
        f = int(self.transactions["is_fraud"].sum())
        return (
            f"{n:,} transactions · {f:,} fraudulent ({f / n:.3%}) · "
            f"{len(self.accounts):,} accounts · {len(self.sessions):,} sessions · "
            f"{len(self.graph_edges):,} edges"
        )

    def write_parquet(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "accounts", "devices", "merchants", "transactions",
            "sessions", "session_events", "graph_edges",
        ):
            getattr(self, name).to_parquet(out_dir / f"{name}.parquet", index=False)


class Emitter:
    """The single write path.

    Every row in the ledger is created here, whether it came from the behaviour layer or
    the attack layer. That is the whole mechanism behind the single-source rule: there is
    no second place where an amount could be rounded differently or a null could appear
    for a different reason.
    """

    def __init__(self) -> None:
        self._txns: list[dict[str, Any]] = []
        self._sessions: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._edges: list[dict[str, Any]] = []

    def transaction(
        self,
        *,
        ts: datetime,
        account_id: str,
        device_id: str,
        merchant_id: str | None,
        amount: float,
        channel: str,
        geography: str,
        mcc: str,
        auth_result: str,
        session_key: int | None = None,
        is_fraud: bool = False,
        vector_id: str | None = None,
        instance_id: str | None = None,
        chain_position: int | None = None,
        generation: int | None = None,
    ) -> int:
        self._txns.append({
            "_ts": ts,
            "_session_key": session_key,
            "account_id": account_id,
            "device_id": device_id,
            "merchant_id": merchant_id,
            # One rounding rule for every row. Threshold-avoidance amounts are round in
            # rupees but carry paise from the same distribution as everything else, so
            # decimal places can never become a class tell.
            "amount_inr": round(float(amount), 2),
            "channel": channel,
            "geography": geography,
            "mcc": mcc,
            "auth_result": auth_result,
            "is_fraud": is_fraud,
            "vector_id": vector_id,
            "instance_id": instance_id,
            "chain_position": chain_position,
            "generation": generation,
        })
        return len(self._txns) - 1

    def session(
        self,
        *,
        ts: datetime,
        account_id: str,
        device_id: str,
        channel: str,
        events: list[dict[str, Any]],
        outcome: str,
        is_fraud: bool = False,
        vector_id: str | None = None,
        instance_id: str | None = None,
        chain_position: int | None = None,
        generation: int | None = None,
    ) -> int:
        key = len(self._sessions)
        self._sessions.append({
            "_ts": ts,
            "_key": key,
            "account_id": account_id,
            "device_id": device_id,
            "channel": channel,
            "outcome": outcome,
            "is_fraud": is_fraud,
            "vector_id": vector_id,
            "instance_id": instance_id,
            "chain_position": chain_position,
            "generation": generation,
        })
        for order, event in enumerate(events):
            self._events.append({"_key": key, "event_order": order, **event})
        return key

    def edge(
        self,
        *,
        ts: datetime,
        source: str,
        target: str,
        amount: float,
        edge_type: str,
        txn_key: int | None = None,
    ) -> None:
        if source == target:
            return
        self._edges.append({
            "_ts": ts,
            "_txn_key": txn_key,
            "source_account": source,
            "target_account": target,
            "amount_inr": round(float(amount), 2),
            "edge_type": edge_type,
        })

    def finalise(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Sort by time, then assign identifiers.

        Identifiers are handed out in timestamp order rather than creation order. If they
        were sequential by creation, every attack instance would carry a contiguous block
        of transaction_ids and the provenance classifier would find it immediately.
        """
        txns = pd.DataFrame(self._txns).sort_values("_ts", kind="stable").reset_index(drop=True)
        sessions = (
            pd.DataFrame(self._sessions).sort_values("_ts", kind="stable").reset_index(drop=True)
        )
        events = pd.DataFrame(self._events)
        edges = pd.DataFrame(self._edges).sort_values("_ts", kind="stable").reset_index(drop=True)

        txns["transaction_id"] = [f"T{i:010d}" for i in range(len(txns))]
        sessions["session_id"] = [f"S{i:010d}" for i in range(len(sessions))]

        key_to_sid = dict(zip(sessions["_key"], sessions["session_id"]))
        txns["session_id"] = txns["_session_key"].map(key_to_sid).where(
            txns["_session_key"].notna(), None
        )
        events["session_id"] = events["_key"].map(key_to_sid)

        idx_to_tid = dict(enumerate(txns["transaction_id"]))
        # _txn_key indexes creation order, which sorting has just invalidated
        creation_to_sorted = {
            int(orig): i for i, orig in enumerate(txns.index[txns.index.argsort()])
        }
        del creation_to_sorted, idx_to_tid  # edges carry no transaction_id in Phase 2
        edges["transaction_id"] = None

        txns["timestamp"] = pd.to_datetime(txns.pop("_ts"), utc=True)
        sessions["started_at"] = pd.to_datetime(sessions.pop("_ts"), utc=True)
        edges["timestamp"] = pd.to_datetime(edges.pop("_ts"), utc=True)

        txns = txns.drop(columns=["_session_key"])
        sessions = sessions.drop(columns=["_key"])
        events = events.drop(columns=["_key"])
        edges = edges.drop(columns=["_txn_key"])
        return txns, sessions, events, edges


# ---------------------------------------------------------------------------
# Behaviour layer, including the two behavioural signals
# ---------------------------------------------------------------------------


def _amount_for(rng: np.random.Generator, mcc: str, trait: AccountTrait) -> float:
    p = MCC_PROFILE[mcc]
    return float(p["scale"] * SEGMENT_SCALE[trait.segment] * rng.lognormal(0, p["sigma"]))


def _hour_for(rng: np.random.Generator, mcc: str) -> float:
    p = MCC_PROFILE[mcc]
    return float(np.clip(rng.normal(p["peak_hour"], p["spread"]), 0, 23.999))


def _channel_for(rng: np.random.Generator, mcc: str) -> str:
    options = MCC_PROFILE[mcc]["channels"]
    keys = list(options)
    return str(rng.choice(keys, p=np.array([options[k] for k in keys])))


def legit_session_events(
    rng: np.random.Generator,
    cfg: dict[str, Any],
    trait: AccountTrait,
    amount: float,
    *,
    scripted: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """A legitimate session, with realistic telemetry rather than a clean baseline.

    NOTES.md D-004 and the build brief: if only fraudulent sessions carry paste events
    and hesitation, the ablation number will look spectacular and mean nothing. So:

      * paste habit is a per-account trait, not a coin flip - some people always paste a
        payee ID, and they do it on every legitimate transfer they ever make;
      * dwell before confirm scales with amount, because ordinary people hesitate before
        sending a large sum to anyone;
      * corrections scale with an account's own sloppiness.

    The coerced profile in :func:`coerced_session_events` is a shift on top of the same
    distributions, not a different kind of object.
    """
    b = cfg["simulation"]["behavioural"]
    events: list[dict[str, Any]] = []
    t = 0

    def add(kind: str, gap: tuple[int, int], **extra: Any) -> None:
        nonlocal t
        t += int(rng.integers(*gap))
        events.append({"type": kind, "t_offset_ms": t, "screen": None, "field": None,
                       "input_method": None, "dwell_ms": None, "corrections": None, **extra})

    events.append({"type": "app_open", "t_offset_ms": 0, "screen": "home", "field": None,
                   "input_method": None, "dwell_ms": None, "corrections": None})

    if scripted:
        # Legitimate automation exists: standing instructions, merchant batch jobs. Their
        # cadence is machine-regular too, which is what stops signal B being a free win.
        gap = int(rng.integers(700, 2400))
        cv = float(rng.uniform(*b["scripted_cadence_cv"]))
        # Same event-count range as an attack sweep. If legitimate automation were always
        # short, session duration alone would separate the classes and the cadence signal
        # would never have to do any work.
        for _ in range(int(rng.integers(4, 30))):
            t += max(80, int(rng.normal(gap, gap * cv)))
            events.append({"type": "submit", "t_offset_ms": t, "screen": "api", "field": None,
                           "input_method": None, "dwell_ms": None, "corrections": None})
        return events, "completed"

    add("login", (600, 3200), screen="auth")
    for _ in range(int(rng.integers(0, 4))):
        add("nav", (400, 9000), screen="browse")
    if rng.random() < 0.45:
        add("view_balance", (500, 6000), screen="balance")

    # Amount-scaled hesitation. A ₹2,000 transfer and a ₹200,000 transfer do not get the
    # same amount of thought from the same person.
    magnitude = math.log10(max(amount, 100)) - 2
    dwell_lo, dwell_hi = b["legit_confirm_dwell_ms"]
    deliberation = trait.deliberation * (1 + 0.55 * max(magnitude, 0))

    add(
        "add_payee", (500, 5000), screen="transfer", field="payee_id",
        input_method="paste" if rng.random() < trait.paste_habit else "type",
        dwell_ms=int(rng.integers(600, 9000) * trait.deliberation),
        corrections=int(rng.poisson(1.6 * trait.sloppiness)),
    )
    add(
        "field_input", (400, 5200), screen="transfer", field="amount",
        input_method="paste" if rng.random() < trait.paste_habit * 0.35 else "type",
        dwell_ms=int(rng.integers(500, 7000) * trait.deliberation),
        corrections=int(rng.poisson(1.3 * trait.sloppiness)),
    )
    confirm_dwell = int(rng.integers(dwell_lo, dwell_hi) * deliberation)
    add("confirm", (300, 2200), screen="confirm", dwell_ms=confirm_dwell)
    if rng.random() < 0.06:
        return events, "abandoned"
    add("submit", (200, 1400), screen="confirm")
    return events, "completed"


def coerced_session_events(
    rng: np.random.Generator,
    cfg: dict[str, Any],
    trait: AccountTrait,
    amount: float,
) -> tuple[list[dict[str, Any]], str]:
    """Signal A: the victim is authorising this themselves, while being talked through it.

    Own device, own credentials, own location, own account history. What differs is the
    interaction: the payee ID arrives from somewhere else and gets pasted, hesitation
    before confirm runs long, corrections rise, and the input arrives in the read-to-me
    rhythm of a long pause followed by a burst.

    A ``noise_floor`` fraction of coerced sessions are given the ordinary profile
    instead. Real coercion does not always leave a mark, and a signal with no false
    negatives in the simulator is a signal that will not survive contact with anything.
    """
    b = cfg["simulation"]["behavioural"]
    if rng.random() < b["noise_floor"]:
        return legit_session_events(rng, cfg, trait, amount)

    events, t = [{"type": "app_open", "t_offset_ms": 0, "screen": "home", "field": None,
                  "input_method": None, "dwell_ms": None, "corrections": None}], 0

    def add(kind: str, gap: tuple[int, int], **extra: Any) -> None:
        nonlocal t
        t += int(rng.integers(*gap))
        events.append({"type": kind, "t_offset_ms": t, "screen": None, "field": None,
                       "input_method": None, "dwell_ms": None, "corrections": None, **extra})

    add("login", (700, 3600), screen="auth")
    # the pause-then-burst rhythm: listening, then acting
    add("nav", (9000, 48000), screen="transfer")

    paste = max(trait.paste_habit, b["coerced_paste_rate_payee"])
    corr_lo, corr_hi = b["coerced_correction_rate"]
    add(
        "add_payee", (300, 2600), screen="transfer", field="payee_id",
        input_method="paste" if rng.random() < paste else "type",
        dwell_ms=int(rng.integers(400, 5200)),
        corrections=int(rng.poisson(3.2 * float(rng.uniform(corr_lo, corr_hi)) * 2)),
    )
    add(
        "field_input", (200, 1800), screen="transfer", field="amount",
        input_method="type",
        dwell_ms=int(rng.integers(300, 4200)),
        corrections=int(rng.poisson(2.4 * float(rng.uniform(corr_lo, corr_hi)) * 2)),
    )
    dwell_lo, dwell_hi = b["coerced_confirm_dwell_ms"]
    add("confirm", (400, 3000), screen="confirm",
        dwell_ms=int(rng.integers(dwell_lo, dwell_hi) * trait.deliberation))
    add("submit", (200, 1600), screen="confirm")
    return events, "completed"


def scripted_attack_events(
    rng: np.random.Generator, cfg: dict[str, Any], n_attempts: int, declines: int
) -> tuple[list[dict[str, Any]], str]:
    """Signal B at its most visible: a checkout bot's cadence."""
    b = cfg["simulation"]["behavioural"]
    events = [{"type": "app_open", "t_offset_ms": 0, "screen": "checkout", "field": None,
               "input_method": None, "dwell_ms": None, "corrections": None}]
    gap = int(rng.integers(600, 2400))
    cv = float(rng.uniform(*b["scripted_cadence_cv"]))
    t = 0
    for i in range(n_attempts):
        t += max(60, int(rng.normal(gap, gap * cv)))
        events.append({"type": "submit", "t_offset_ms": t, "screen": "checkout", "field": None,
                       "input_method": "paste", "dwell_ms": None, "corrections": 0})
        if i < declines:
            t += int(rng.integers(40, 260))
            events.append({"type": "decline_shown", "t_offset_ms": t, "screen": "checkout",
                           "field": None, "input_method": None, "dwell_ms": None,
                           "corrections": None})
    return events, "blocked" if declines > n_attempts * 0.5 else "completed"


# ---------------------------------------------------------------------------
# Attack layer - the five generation-0 chains
# ---------------------------------------------------------------------------


@dataclass
class World:
    cfg: dict[str, Any]
    rng: np.random.Generator
    emitter: Emitter
    traits: dict[str, AccountTrait]
    account_ids: list[str]
    devices: list[str]
    merchants: pd.DataFrame
    mule_pool: list[str]
    start: datetime
    days: int
    _merchant_index: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    _all_merchants: list[dict[str, str]] = field(default_factory=list)
    instance_seq: int = 0
    instance_id: str = "I000000"
    abort_after: int = 99
    slow: bool = False
    restraint: float = 1.0
    declined: bool = False

    def new_instance(self) -> str:
        """Start an instance and draw the execution profile it will be run with.

        Not every attack is executed well. Drawing an abort point, a pace and a restraint
        factor per instance is what stops the fraud population being uniformly the
        attacker's best case, which is the state the first score distribution revealed:
        99.3% of fraudulent rows above the 99th percentile of legitimate traffic, with an
        empty band beneath them.
        """
        self.instance_seq += 1
        self.instance_id = f"I{self.instance_seq:06d}"

        r = self.cfg["simulation"].get("realism", {})
        if not r.get("enabled", False):
            self.abort_after = 99
            self.slow = False
            self.restraint = 1.0
            self.declined = False
            return self.instance_id

        # Geometric abort: each remaining stage is another chance to stop.
        p = float(r["p_abort_per_stage"])
        stage = 1
        while stage < 6 and self.rng.random() > p:
            stage += 1
        self.abort_after = stage
        self.slow = bool(self.rng.random() < float(r["p_slow_actor"]))
        self.declined = bool(self.rng.random() < float(r["p_declined_extraction"]))
        self.restraint = float(self.rng.uniform(*r["amount_restraint"]))
        return self.instance_id

    def aborted(self, stage: int) -> bool:
        """True when this instance stopped before reaching ``stage``."""
        return stage > self.abort_after

    def amount(self, trait: AccountTrait, mcc: str, factor: tuple[float, float]) -> float:
        """An attack amount expressed relative to what this account normally does.

        Drawing fraud amounts from an absolute uniform range while legitimate amounts come
        from a per-account lognormal makes the two separable on amount alone - which is a
        property of the generator, not of fraud. Anomalous-for-this-account is the real
        signal, so that is what gets simulated.
        """
        base = _amount_for(self.rng, mcc, trait)
        return float(base * self.rng.uniform(*factor) * self.restraint)

    def when(self) -> datetime:
        """Start time for an attack instance, uniform across the observation window.

        An earlier attempt reserved a horizon at the end so that long chains would finish
        inside the window. That fixed one bias and created a worse one: with no attacks
        starting in the final fifty days, the time-ordered split had almost no fraud in its
        test half. Right-censoring at the boundary is the correct treatment and it is
        applied to both classes by a single filter in :func:`simulate`.
        """
        day = float(self.rng.uniform(0, self.days))
        return self.start + timedelta(days=day)

    def victim(self) -> AccountTrait:
        return self.traits[str(self.rng.choice(self.account_ids))]

    def merchant(self, mcc: str | None = None) -> dict[str, str]:
        """Pick a merchant, optionally of a given category.

        Backed by a prebuilt index rather than a DataFrame filter. Filtering the merchant
        frame per call was 82% of simulator runtime and put a full-scale run out of reach:
        2.9ms per transaction is 1.6 hours for two million rows.
        """
        pool = self._merchant_index.get(mcc) if mcc else self._all_merchants
        if not pool:
            pool = self._all_merchants
        return pool[int(self.rng.integers(0, len(pool)))]

    def foreign_device(self) -> str:
        return str(self.rng.choice(self.devices))


def _attack_v001(world: World, params: dict[str, Any]) -> None:
    """BIN sweep via AI-scripted checkout bot. Session rhythm is the tell."""
    rng, em = world.rng, world.emitter
    iid = world.new_instance()
    trait = world.victim()
    device = world.foreign_device()
    t0 = world.when()
    # A sweep is bursty but not unbounded. Capping it stops one vector supplying most of
    # the fraudulent ROWS in the ledger and drowning out every other vector in any
    # row-weighted metric.
    n = int(np.clip(rng.integers(*params["cards_per_sweep"]) // 8, 6, 26))
    if world.slow:
        # A careless operator runs the sweep by hand: fewer attempts, human pacing, and
        # a cadence that no longer separates from ordinary checkout behaviour.
        n = max(3, n // 3)
    decline_ratio = float(rng.uniform(*params["decline_ratio"]))
    declines = int(n * decline_ratio)
    gap_ms = int(rng.integers(*params["inter_arrival_ms"]))
    if world.slow:
        gap_ms = int(gap_ms * rng.uniform(6, 40))

    if world.slow:
        events, outcome = legit_session_events(rng, world.cfg, trait, 2000.0)
    else:
        events, outcome = scripted_attack_events(rng, world.cfg, n, declines)
    key = em.session(ts=t0, account_id=trait.account_id, device_id=device, channel="cards_cnp",
                     events=events, outcome=outcome, is_fraud=True, vector_id="V001",
                     instance_id=iid, chain_position=1, generation=0)

    for i in range(n):
        merchant = world.merchant()
        em.transaction(
            ts=t0 + timedelta(milliseconds=i * gap_ms),
            account_id=trait.account_id, device_id=device, merchant_id=merchant["merchant_id"],
            amount=world.amount(trait, merchant["mcc"], (0.002, 0.02)),
            channel="cards_cnp", geography=trait.home_geo, mcc=merchant["mcc"],
            auth_result="declined" if i < declines else "approved",
            session_key=key, is_fraud=True, vector_id="V001", instance_id=iid,
            chain_position=1, generation=0,
        )

    if world.aborted(2):
        return
    merchant = world.merchant("5732")
    em.transaction(
        ts=t0 + timedelta(milliseconds=n * gap_ms + 30_000),
        account_id=trait.account_id, device_id=device, merchant_id=merchant["merchant_id"],
        amount=world.amount(trait, merchant["mcc"], (1.8, 9.0)),
        channel="cards_cnp", geography=trait.home_geo, mcc=merchant["mcc"],
        auth_result="declined" if world.declined else "approved",
        session_key=key, is_fraud=True, vector_id="V001",
        instance_id=iid, chain_position=2, generation=0,
    )


def _attack_v002(world: World, params: dict[str, Any]) -> None:
    """Mule layering. Graph topology is the tell; no single row looks wrong."""
    rng, em = world.rng, world.emitter
    iid = world.new_instance()
    trait = world.victim()
    t0 = world.when()
    n_mules = int(rng.integers(*params["n_mules"]))
    mules = [str(m) for m in rng.choice(world.mule_pool, size=min(n_mules, len(world.mule_pool)),
                                        replace=False)]
    amount = world.amount(trait, "6012", (2.5, 22.0))

    device = world.foreign_device()
    em.transaction(
        ts=t0, account_id=trait.account_id, device_id=device, merchant_id=None,
        amount=amount, channel="bank_transfer", geography=trait.home_geo, mcc="6012",
        auth_result="approved", is_fraud=True, vector_id="V002", instance_id=iid,
        chain_position=1, generation=0,
    )
    em.edge(ts=t0, source=trait.account_id, target=mules[0], amount=amount, edge_type="transfer")

    # fan out, then collect: short residence at every hop
    hub, sink = mules[0], mules[-1]
    remaining = amount
    if world.aborted(2):
        return
    dormant = world.rng.random() < float(
        world.cfg["simulation"].get("realism", {}).get("p_dormant_hop", 0.0)
    )
    for hop, mule in enumerate(mules[1:-1] or mules[1:]):
        if world.aborted(2 + hop // 3):
            return
        share = remaining / max(len(mules) - 2, 1) * float(
            1 + rng.uniform(*params["split_ratio_jitter"]) - 0.15
        )
        share = max(1000.0, min(share, remaining))
        t1 = t0 + timedelta(minutes=float(rng.uniform(*params["hop_delay_minutes"])))
        em.transaction(
            ts=t1, account_id=hub, device_id=device, merchant_id=None, amount=share,
            channel="bank_transfer", geography=GEOS[int(rng.integers(0, len(GEOS)))], mcc="6012",
            auth_result="approved", is_fraud=True, vector_id="V002", instance_id=iid,
            chain_position=2, generation=0,
        )
        em.edge(ts=t1, source=hub, target=mule, amount=share, edge_type="transfer")

        residence = float(rng.uniform(*params["residence_seconds"]))
        if dormant:
            # Money that rests looks like money that belongs there. This is the single
            # most discriminative graph feature, so it must not be free.
            residence *= float(rng.uniform(20, 400))
        t2 = t1 + timedelta(seconds=residence)
        onward = share * float(rng.uniform(0.9, 0.99))
        em.transaction(
            ts=t2, account_id=mule, device_id=device, merchant_id=None, amount=onward,
            channel="upi_instant", geography=GEOS[int(rng.integers(0, len(GEOS)))], mcc="6011",
            auth_result="approved", is_fraud=True, vector_id="V002", instance_id=iid,
            chain_position=3, generation=0,
        )
        em.edge(ts=t2, source=mule, target=sink, amount=onward, edge_type="transfer")
        em.edge(ts=t2, source=mule, target=hub, amount=0.0, edge_type="shared_device")


def _attack_v003(world: World, params: dict[str, Any]) -> None:
    """Deepfake investment scam driving an APP transfer. Signal A carries this one."""
    rng, em = world.rng, world.emitter
    iid = world.new_instance()
    trait = world.victim()
    device = trait.devices[0]                     # the victim own device, own credentials
    t0 = world.when()
    amount = world.amount(trait, "6011", (3.0, 30.0))

    events, outcome = coerced_session_events(rng, world.cfg, trait, amount)
    key = em.session(ts=t0, account_id=trait.account_id, device_id=device,
                     channel="upi_instant", events=events, outcome=outcome, is_fraud=True,
                     vector_id="V003", instance_id=iid, chain_position=1, generation=0)

    beneficiary = str(rng.choice(world.mule_pool))
    em.edge(ts=t0, source=trait.account_id, target=beneficiary, amount=0.0,
            edge_type="shared_beneficiary")

    if world.aborted(2):
        return                      # the victim stopped: session only, no money moved
    t1 = t0 + timedelta(minutes=float(rng.uniform(1, 8)))
    em.transaction(
        ts=t1, account_id=trait.account_id, device_id=device, merchant_id=None,
        amount=world.amount(trait, "6011", (0.001, 0.03)),
        channel="upi_instant", geography=trait.home_geo, mcc="6011", auth_result="approved",
        session_key=key, is_fraud=True, vector_id="V003", instance_id=iid,
        chain_position=2, generation=0,
    )
    if world.aborted(3):
        return                      # the micro test went through and nothing followed
    t2 = t1 + timedelta(minutes=float(rng.uniform(1, 25)))
    em.transaction(
        ts=t2, account_id=trait.account_id, device_id=device, merchant_id=None, amount=amount,
        channel="upi_instant", geography=trait.home_geo, mcc="6011", auth_result="approved",
        session_key=key, is_fraud=True, vector_id="V003", instance_id=iid,
        chain_position=3, generation=0,
    )
    em.edge(ts=t2, source=trait.account_id, target=beneficiary, amount=amount,
            edge_type="transfer")


def _attack_v004(world: World, params: dict[str, Any]) -> None:
    """SIM swap to ATO with cloned-voice OTP. Device and geography discontinuity."""
    rng, em = world.rng, world.emitter
    iid = world.new_instance()
    trait = world.victim()
    device = world.foreign_device()
    t0 = world.when()
    away = [g for g in GEOS if g != trait.home_geo]
    geo = str(rng.choice(away))

    events = [
        {"type": "app_open", "t_offset_ms": 0, "screen": "home", "field": None,
         "input_method": None, "dwell_ms": None, "corrections": None},
        {"type": "login", "t_offset_ms": int(rng.integers(700, 2600)), "screen": "auth",
         "field": None, "input_method": None, "dwell_ms": None, "corrections": None},
        {"type": "otp_entry", "t_offset_ms": int(rng.integers(4000, 30000)), "screen": "auth",
         "field": "otp", "input_method": "type",
         "dwell_ms": int(rng.integers(*params["otp_dwell_ms"])), "corrections": 0},
        {"type": "confirm", "t_offset_ms": int(rng.integers(31000, 60000)), "screen": "confirm",
         "field": None, "input_method": None, "dwell_ms": int(rng.integers(900, 6000)),
         "corrections": None},
    ]
    key = em.session(ts=t0, account_id=trait.account_id, device_id=device,
                     channel="wallets_tokenisation", events=events, outcome="stepped_up",
                     is_fraud=True, vector_id="V004", instance_id=iid, chain_position=1,
                     generation=0)
    em.edge(ts=t0, source=trait.account_id, target=str(rng.choice(world.mule_pool)),
            amount=0.0, edge_type="token_provision")

    if world.aborted(2):
        return                      # step-up held; the session is all that exists
    t1 = t0 + timedelta(minutes=float(rng.uniform(*params["minutes_device_to_drain"])))
    merchant = world.merchant("5732")
    em.transaction(
        ts=t1, account_id=trait.account_id, device_id=device,
        merchant_id=merchant["merchant_id"],
        amount=world.amount(trait, merchant["mcc"], (2.0, 14.0)),
        channel="wallets_tokenisation", geography=geo, mcc=merchant["mcc"],
        auth_result="declined" if world.declined else "approved",
        session_key=key, is_fraud=True, vector_id="V004",
        instance_id=iid, chain_position=3, generation=0,
    )


def _attack_v005(world: World, params: dict[str, Any]) -> None:
    """Synthetic identity through deepfake KYC, then structuring under a threshold."""
    rng, em = world.rng, world.emitter
    iid = world.new_instance()
    mule = str(rng.choice(world.mule_pool))
    trait = world.traits[mule]
    device = world.foreign_device()
    t0 = world.when()

    kyc_seconds = float(rng.uniform(*params["kyc_session_seconds"]))
    events = [
        {"type": "app_open", "t_offset_ms": 0, "screen": "onboard", "field": None,
         "input_method": None, "dwell_ms": None, "corrections": None},
        {"type": "field_input", "t_offset_ms": int(kyc_seconds * 250), "screen": "kyc",
         "field": "identity", "input_method": "paste", "dwell_ms": int(rng.integers(200, 1400)),
         "corrections": 0},
        {"type": "confirm", "t_offset_ms": int(kyc_seconds * 1000), "screen": "kyc",
         "field": None, "input_method": None, "dwell_ms": int(rng.integers(300, 2000)),
         "corrections": None},
    ]
    key = em.session(ts=t0, account_id=mule, device_id=device, channel="kyc_onboarding",
                     events=events, outcome="completed", is_fraud=True, vector_id="V005",
                     instance_id=iid, chain_position=1, generation=0)

    dormant = float(rng.uniform(*params["days_dormant_after_open"]))
    threshold = float(params["threshold_inr"])
    n = int(rng.integers(*params["n_withdrawals"]))
    t = t0 + timedelta(days=dormant)
    sink = str(rng.choice(world.mule_pool))
    if world.aborted(2):
        return                      # account opened and never used
    for i in range(n):
        if i > 0 and world.aborted(2 + i // 4):
            return
        t = t + timedelta(hours=float(rng.uniform(0.5, 9)))
        amount = threshold - float(rng.uniform(*params["under_threshold_margin_inr"]))
        em.transaction(
            ts=t, account_id=mule, device_id=device, merchant_id=None, amount=amount,
            channel="bank_transfer", geography=trait.home_geo, mcc="6011",
            auth_result="approved", session_key=key if i == 0 else None,
            is_fraud=True, vector_id="V005", instance_id=iid,
            chain_position=3 + (i > 0), generation=0,
        )
        em.edge(ts=t, source=mule, target=sink, amount=amount, edge_type="transfer")


ATTACKS = {
    "V001": _attack_v001,
    "V002": _attack_v002,
    "V003": _attack_v003,
    "V004": _attack_v004,
    "V005": _attack_v005,
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _load_vectors() -> list[dict[str, Any]]:
    """Generation-0 vectors. They live in the fixture today and move to the taxonomy
    module when the grammar is completed in Phase 3."""
    import json

    from adl.common.paths import FIXTURES_DIR

    data = json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))
    for v in data["vectors"]:
        validate_chain(v["chain"], v["objective"])
    return data["vectors"]


def _sample_param(rng: np.random.Generator, value: Any) -> Any:
    if isinstance(value, list) and len(value) == 2 and all(
        isinstance(x, (int, float)) for x in value
    ):
        return value
    return value


def simulate(
    n_transactions: int | None = None,
    seed: int | None = None,
    prevalence: float | None = None,
    n_accounts: int | None = None,
    vectors: Iterable[dict[str, Any]] | None = None,
) -> Ledger:
    cfg = load_config()
    sim = cfg["simulation"]
    seed = seed if seed is not None else cfg["run"]["seed"]
    n_transactions = n_transactions or sim["n_transactions_target"]
    prevalence = prevalence if prevalence is not None else sim["fraud_prevalence"]
    n_accounts = n_accounts or sim["n_accounts"]
    vectors = list(vectors) if vectors is not None else _load_vectors()

    rng = rng_for(seed, "simulator")
    start = datetime.fromisoformat(sim["window_start"].replace("Z", "+00:00"))
    days = int(sim["window_days"])

    # --- entity layer ------------------------------------------------------
    n_devices = int(n_accounts * 1.3)
    n_merchants = max(200, int(n_accounts * 0.075))

    device_ids = [f"D{i:08d}" for i in range(n_devices)]
    devices = pd.DataFrame({
        "device_id": device_ids,
        "first_seen": [start - timedelta(days=float(d)) for d in rng.uniform(1, 1400, n_devices)],
        "os_family": rng.choice(["android", "ios", "web", "agent"], size=n_devices,
                                p=[0.63, 0.22, 0.13, 0.02]),
        "is_emulator": rng.random(n_devices) < 0.025,
    })

    merchants = pd.DataFrame({
        "merchant_id": [f"M{i:06d}" for i in range(n_merchants)],
        "onboarded_at": [start - timedelta(days=float(d))
                         for d in rng.uniform(5, 2200, n_merchants)],
        "mcc": rng.choice(MCCS, size=n_merchants),
        "geo": rng.choice(GEOS, size=n_merchants),
        "risk_tier": rng.choice(["low", "medium", "high"], size=n_merchants, p=[0.7, 0.24, 0.06]),
    })

    account_ids = [f"A{i:08d}" for i in range(n_accounts)]
    n_mules = max(40, int(n_accounts * 0.012))
    # Mules are scattered through the identifier space, not taken from the end of it.
    # Slicing the tail made account_id itself predict the label - the provenance test
    # caught it at AUC 0.72 on the raw identifier alone. An id that encodes ground truth
    # is a leak no amount of feature selection downstream can undo.
    mule_index = rng.choice(n_accounts, size=n_mules, replace=False)
    mule_pool = [account_ids[int(i)] for i in mule_index]
    mule_set = set(mule_pool)
    n_synth = max(12, n_mules // 3)
    synth_set = set(mule_pool[:n_synth])

    segments = rng.choice(list(SEGMENT_SCALE), size=n_accounts, p=[0.34, 0.42, 0.17, 0.07])
    home = rng.choice(GEOS, size=n_accounts)
    # activity is heavy-tailed: a few accounts transact constantly, most rarely
    activity = rng.lognormal(0, 0.9, n_accounts)
    # Paste habit is bimodal by person, not a per-event coin flip. Roughly a fifth of
    # people paste payee IDs habitually; the rest almost never do.
    habitual = rng.random(n_accounts) < 0.21
    paste_habit = np.where(habitual, rng.uniform(0.55, 0.95, n_accounts),
                           rng.uniform(0.01, 0.14, n_accounts))
    deliberation = rng.lognormal(0, 0.35, n_accounts)
    sloppiness = rng.lognormal(0, 0.5, n_accounts)

    traits: dict[str, AccountTrait] = {}
    for i, aid in enumerate(account_ids):
        k = int(rng.integers(2, 5))
        pref = list(rng.choice(MCCS, size=k, replace=False))
        weights = rng.dirichlet(np.ones(k) * 1.7)
        n_dev = 1 + int(rng.random() < 0.28)
        traits[aid] = AccountTrait(
            account_id=aid, home_geo=str(home[i]), segment=str(segments[i]),
            activity=float(activity[i]), mcc_pref=[str(m) for m in pref], mcc_weights=weights,
            devices=[str(d) for d in rng.choice(device_ids, size=n_dev, replace=False)],
            paste_habit=float(paste_habit[i]), deliberation=float(deliberation[i]),
            sloppiness=float(sloppiness[i]),
        )

    accounts = pd.DataFrame({
        "account_id": account_ids,
        "opened_at": [
            start - timedelta(days=float(d))
            for d in np.where(
                np.array([a in mule_set for a in account_ids]),
                rng.uniform(2, 90, n_accounts),
                rng.uniform(30, 2600, n_accounts),
            )
        ],
        "home_geo": home,
        "segment": segments,
        "kyc_level": rng.choice(["full", "min", "video"], size=n_accounts, p=[0.62, 0.3, 0.08]),
        "label_is_mule": np.array([a in mule_set for a in account_ids]),
        "label_is_synthetic_identity": np.array([a in synth_set for a in account_ids]),
    })

    em = Emitter()
    world = World(cfg=cfg, rng=rng, emitter=em, traits=traits, account_ids=account_ids,
                  devices=device_ids, merchants=merchants, mule_pool=mule_pool,
                  start=start, days=days)
    world._all_merchants = [
        {"merchant_id": m, "mcc": c}
        for m, c in zip(merchants["merchant_id"], merchants["mcc"])
    ]
    for record in world._all_merchants:
        world._merchant_index.setdefault(record["mcc"], []).append(record)

    # --- attack layer, run first so the fraud lands across the whole window ------
    # Volume is set from the target prevalence. Each instance emits a variable number of
    # rows, so the loop measures rather than assumes.
    target_fraud = int(n_transactions * prevalence)
    vector_cycle = [v for v in vectors if v["vector_id"] in ATTACKS]
    if not vector_cycle:
        raise ValueError("no implemented vectors among the supplied attacks.json")

    instances = 0
    while len(em._txns) < target_fraud:
        vector = vector_cycle[instances % len(vector_cycle)]
        params = {k: _sample_param(rng, v) for k, v in vector["parameters"].items()}
        ATTACKS[vector["vector_id"]](world, params)
        instances += 1
    n_fraud_rows = len(em._txns)

    # --- behaviour layer ---------------------------------------------------
    n_legit = max(0, n_transactions - n_fraud_rows)
    weights = np.array([traits[a].activity for a in account_ids])
    weights = weights / weights.sum()
    chosen = rng.choice(n_accounts, size=n_legit, p=weights)
    day_offsets = rng.uniform(0, days, n_legit)
    session_draw = rng.random(n_legit)
    scripted_draw = rng.random(n_legit)
    geo_draw = rng.random(n_legit)
    decline_draw = rng.random(n_legit)

    for i in range(n_legit):
        trait = traits[account_ids[int(chosen[i])]]
        mcc = str(rng.choice(trait.mcc_pref, p=trait.mcc_weights))
        hour = _hour_for(rng, mcc)
        ts = start + timedelta(days=float(day_offsets[i]) // 1) + timedelta(hours=hour)
        ts += timedelta(seconds=float(rng.uniform(0, 60)))
        amount = _amount_for(rng, mcc, trait)
        channel = _channel_for(rng, mcc)
        device = trait.devices[int(rng.integers(0, len(trait.devices)))]
        merchant = world.merchant(mcc)
        geography = trait.home_geo if geo_draw[i] > 0.11 else str(rng.choice(GEOS))

        key = None
        # Interactive rails produce a session most of the time; card rails rarely do.
        p_session = 0.65 if channel in {"upi_instant", "bank_transfer"} else 0.18
        if session_draw[i] < p_session:
            scripted = scripted_draw[i] < 0.035
            events, outcome = legit_session_events(rng, cfg, trait, amount, scripted=scripted)
            key = em.session(ts=ts - timedelta(seconds=float(rng.uniform(20, 400))),
                             account_id=trait.account_id, device_id=device, channel=channel,
                             events=events, outcome=outcome)

        em.transaction(
            ts=ts, account_id=trait.account_id, device_id=device,
            merchant_id=None if channel == "bank_transfer" else merchant["merchant_id"],
            amount=amount, channel=channel, geography=geography, mcc=mcc,
            auth_result="declined" if decline_draw[i] < 0.037 else "approved",
            session_key=key,
        )
        if channel == "bank_transfer":
            em.edge(ts=ts, source=trait.account_id,
                    target=account_ids[int(rng.integers(0, n_accounts))],
                    amount=amount, edge_type="transfer")

    txns, sessions, events_df, edges = em.finalise()
    txns["is_fraud"] = txns["is_fraud"].astype(bool)

    # Right-censoring at the observation boundary. A real dataset is a window: chains still
    # in flight when the window closes are partially observed, and that is a property of
    # the observation rather than of the fraud. One filter, applied to both classes by the
    # same rule, so it cannot become a provenance asymmetry.
    window_end = start + timedelta(days=days)
    keep = txns["timestamp"] <= window_end
    censored = int((~keep).sum())
    txns = txns[keep].reset_index(drop=True)
    live_sessions = sessions["started_at"] <= window_end
    sessions = sessions[live_sessions].reset_index(drop=True)
    events_df = events_df[events_df["session_id"].isin(set(sessions["session_id"]))]
    txns.loc[~txns["session_id"].isin(set(sessions["session_id"])), "session_id"] = None
    edges = edges[edges["timestamp"] <= window_end].reset_index(drop=True)

    return Ledger(
        accounts=accounts, devices=devices, merchants=merchants,
        transactions=txns, sessions=sessions, session_events=events_df, graph_edges=edges,
        meta={
            "seed": seed,
            "prevalence_target": prevalence,
            "prevalence_actual": float(txns["is_fraud"].mean()),
            "attack_instances": instances,
            "rows_censored_at_window_end": censored,
            "window_start": start.isoformat(),
            "window_days": days,
            "vectors": [v["vector_id"] for v in vector_cycle],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transactions", type=int, default=200_000)
    parser.add_argument("--accounts", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    ledger = simulate(
        n_transactions=args.transactions, seed=args.seed, n_accounts=args.accounts
    )
    print(ledger.summary())
    print(f"  target prevalence {ledger.meta['prevalence_target']:.3%} · "
          f"actual {ledger.meta['prevalence_actual']:.3%} · "
          f"{ledger.meta['attack_instances']} attack instances")
    if args.out:
        ledger.write_parquet(args.out)
        print(f"  wrote parquet to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
