"""Every grammar primitive, implemented as a function that mutates the world.

PDF S5.1: "Each primitive from the grammar is implemented as a function that mutates the
entity graph and emits the transactions, session events, and edges the primitive would
produce. An attack chain executes its primitives in order against a selected victim
entity."

This is the file that makes the closed loop possible. While the attack layer was five
hardcoded functions keyed by vector_id, the red-team strategist could propose new chains
but nothing could execute them, so every mutation would have been decoration. With
primitives as the unit, any grammar-valid chain runs.

Every primitive writes through the same Emitter as legitimate traffic. There is still
exactly one write path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np


@dataclass
class ChainContext:
    """Carried down the chain. Primitives read what earlier stages established."""

    world: Any
    trait: Any
    vector_id: str
    instance_id: str
    params: dict[str, Any]
    t: datetime
    device: str
    session_key: int | None = None
    beneficiary: str | None = None
    geography: str | None = None
    position: int = 0
    scale: float = 1.0
    emitted: list[str] = field(default_factory=list)

    @property
    def rng(self):
        return self.world.rng

    @property
    def em(self):
        return self.world.emitter

    def advance(self, minutes_lo: float, minutes_hi: float) -> None:
        self.t += timedelta(minutes=float(self.rng.uniform(minutes_lo, minutes_hi)))

    def amount(self, mcc: str, factor: tuple[float, float]) -> float:
        return self.world.amount(self.trait, mcc, factor) * self.scale

    def blend_mcc(self, default: str, p: float = 0.55) -> str:
        """Extract through a category the victim already uses, most of the time.

        Extraction was always routed through the same two or three merchant categories
        regardless of who the victim was, which made category a partial giveaway on its
        own. An attacker draining an account has every reason to move value through
        somewhere the account already transacts. This narrows the gap between fraudulent
        and legitimate rows without touching either behavioural signal.
        """
        if self.trait.mcc_pref and self.rng.random() < p:
            return str(self.rng.choice(self.trait.mcc_pref))
        return default

    def txn(self, **kwargs: Any) -> None:
        """Emit a transaction attributed to this chain instance."""
        defaults = {
            "ts": self.t,
            "account_id": self.trait.account_id,
            "device_id": self.device,
            "merchant_id": None,
            "geography": self.geography or self.trait.home_geo,
            "auth_result": "approved",
            "session_key": self.session_key,
            "is_fraud": True,
            "vector_id": self.vector_id,
            "instance_id": self.instance_id,
            "chain_position": self.position,
            "generation": self.world.generation,
        }
        self.em.transaction(**{**defaults, **kwargs})

    def session(self, *, channel: str, events: list[dict[str, Any]], outcome: str) -> None:
        self.session_key = self.em.session(
            ts=self.t,
            account_id=self.trait.account_id,
            device_id=self.device,
            channel=channel,
            events=events,
            outcome=outcome,
            is_fraud=True,
            vector_id=self.vector_id,
            instance_id=self.instance_id,
            chain_position=self.position,
            generation=self.world.generation,
        )

    def edge(self, target: str, amount: float, edge_type: str) -> None:
        self.em.edge(
            ts=self.t,
            source=self.trait.account_id,
            target=target,
            amount=amount,
            edge_type=edge_type,
        )


# ---------------------------------------------------------------------------
# Acquire
# ---------------------------------------------------------------------------


def phish_credential(ctx: ChainContext) -> None:
    from .simulator import legit_session_events, scripted_attack_events

    ctx.device = ctx.world.foreign_device()
    if ctx.world.slow:
        events, outcome = legit_session_events(ctx.rng, ctx.world.cfg, ctx.trait, 2000.0)
    else:
        events, outcome = scripted_attack_events(ctx.rng, ctx.world.cfg, 3, 0)
    ctx.session(channel="cards_cnp", events=events, outcome=outcome)
    ctx.advance(2, 90)


def clone_voice_otp(ctx: ChainContext) -> None:
    """Cloned voice walks the victim through reading back a one-time code."""
    dwell = ctx.params.get("otp_dwell_ms", [4000, 26000])
    events = [
        _event("app_open", 0, screen="home"),
        _event("login", int(ctx.rng.integers(700, 2600)), screen="auth"),
        _event(
            "otp_entry",
            int(ctx.rng.integers(4000, 30000)),
            screen="auth",
            field="otp",
            input_method="type",
            dwell_ms=int(ctx.rng.integers(*dwell)),
            corrections=int(ctx.rng.poisson(1.4)),
        ),
        _event("confirm", int(ctx.rng.integers(31000, 60000)), screen="confirm",
               dwell_ms=int(ctx.rng.integers(900, 9000))),
    ]
    ctx.session(channel="wallets_tokenisation", events=events, outcome="stepped_up")
    ctx.advance(1, 45)


def deepfake_kyc(ctx: ChainContext) -> None:
    """Synthetic face passes a liveness check faster than a person completes the flow."""
    seconds = float(ctx.rng.uniform(*ctx.params.get("kyc_session_seconds", [40, 150])))
    events = [
        _event("app_open", 0, screen="onboard"),
        _event("field_input", int(seconds * 250), screen="kyc", field="identity",
               input_method="paste", dwell_ms=int(ctx.rng.integers(200, 1400)), corrections=0),
        _event("confirm", int(seconds * 1000), screen="kyc",
               dwell_ms=int(ctx.rng.integers(300, 2000))),
    ]
    ctx.session(channel="kyc_onboarding", events=events, outcome="completed")
    ctx.advance(60, 60 * 24 * 30)


def synthesise_identity(ctx: ChainContext) -> None:
    """The actor becomes a thin-file account with no genuine history."""
    pool = ctx.world.synthetic_pool or ctx.world.mule_pool
    ctx.trait = ctx.world.traits[str(ctx.rng.choice(pool))]
    ctx.device = ctx.world.foreign_device()
    ctx.advance(60, 60 * 24 * 20)


def compromise_agent(ctx: ChainContext) -> None:
    """An AI agent's authorisation flow is hijacked. No human interaction events at all."""
    gap = int(ctx.rng.integers(400, 1600))
    events = [_event("app_open", 0, screen="agent")]
    t = 0
    for _ in range(int(ctx.rng.integers(3, 9))):
        t += max(60, int(ctx.rng.normal(gap, gap * 0.05)))
        events.append(_event("agent_action", t, screen="agent", input_method="none"))
    ctx.device = ctx.world.agent_device()
    ctx.session(channel="agentic_commerce", events=events, outcome="completed")
    ctx.advance(1, 30)


# ---------------------------------------------------------------------------
# Establish
# ---------------------------------------------------------------------------


def provision_token(ctx: ChainContext) -> None:
    target = ctx.beneficiary or str(ctx.rng.choice(ctx.world.mule_pool))
    ctx.edge(target, 0.0, "token_provision")
    ctx.txn(
        amount=ctx.amount("4814", (0.001, 0.01)),
        channel="wallets_tokenisation",
        mcc="4814",
        merchant_id=ctx.world.merchant("4814")["merchant_id"],
    )
    ctx.advance(1, 120)


def register_device(ctx: ChainContext) -> None:
    """New device bound to the account, from somewhere the account has never been."""
    ctx.device = ctx.world.foreign_device()
    away = [g for g in ctx.world.geos if g != ctx.trait.home_geo]
    ctx.geography = str(ctx.rng.choice(away))
    ctx.edge(str(ctx.rng.choice(ctx.world.mule_pool)), 0.0, "shared_device")
    ctx.advance(1, 180)


def open_mule_account(ctx: ChainContext) -> None:
    ctx.beneficiary = str(ctx.rng.choice(ctx.world.mule_pool))
    ctx.edge(ctx.beneficiary, 0.0, "shared_beneficiary")
    ctx.advance(5, 60 * 24)


def add_beneficiary(ctx: ChainContext) -> None:
    """Novel payee added minutes before extraction, entered under instruction."""
    from .simulator import coerced_session_events

    ctx.beneficiary = str(ctx.rng.choice(ctx.world.mule_pool))
    events, outcome = coerced_session_events(
        ctx.rng, ctx.world.cfg, ctx.trait, ctx.amount("6011", (3.0, 30.0))
    )
    ctx.session(channel="upi_instant", events=events, outcome=outcome)
    ctx.edge(ctx.beneficiary, 0.0, "shared_beneficiary")
    ctx.advance(1, 40)


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def micro_test(ctx: ChainContext) -> None:
    ctx.txn(
        amount=max(1.0, ctx.amount("6011", (0.001, 0.03))),
        channel="upi_instant",
        mcc="6011",
    )
    ctx.advance(1, 30)


def card_test_sweep(ctx: ChainContext) -> None:
    """Rapid authorisations across many cards. The rhythm is the tell, not any one row."""
    n = int(np.clip(ctx.rng.integers(*ctx.params.get("cards_per_sweep", [40, 260])) // 8, 6, 26))
    gap_ms = int(ctx.rng.integers(*ctx.params.get("inter_arrival_ms", [900, 2600])))
    decline_ratio = float(ctx.rng.uniform(*ctx.params.get("decline_ratio", [0.55, 0.9])))

    from .simulator import legit_session_events, scripted_attack_events

    if ctx.world.slow:
        n = max(3, n // 3)
        gap_ms = int(gap_ms * ctx.rng.uniform(6, 40))
        events, outcome = legit_session_events(ctx.rng, ctx.world.cfg, ctx.trait, 2000.0)
    else:
        events, outcome = scripted_attack_events(ctx.rng, ctx.world.cfg, n, int(n * decline_ratio))
    ctx.session(channel="cards_cnp", events=events, outcome=outcome)

    declines = int(n * decline_ratio)
    base = ctx.t
    for i in range(n):
        merchant = ctx.world.merchant()
        ctx.t = base + timedelta(milliseconds=i * gap_ms)
        ctx.txn(
            amount=max(1.0, ctx.amount(merchant["mcc"], (0.002, 0.02))),
            channel="cards_cnp",
            mcc=merchant["mcc"],
            merchant_id=merchant["merchant_id"],
            auth_result="declined" if i < declines else "approved",
        )
    ctx.t = base + timedelta(milliseconds=n * gap_ms)
    ctx.advance(0.5, 20)


def balance_probe(ctx: ChainContext) -> None:
    events = [
        _event("app_open", 0, screen="home"),
        _event("view_balance", int(ctx.rng.integers(600, 5000)), screen="balance"),
    ]
    ctx.session(channel="upi_instant", events=events, outcome="abandoned")
    ctx.advance(1, 60)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def drain_single(ctx: ChainContext) -> None:
    target = ctx.beneficiary or str(ctx.rng.choice(ctx.world.mule_pool))
    mcc = ctx.blend_mcc("6011")
    amount = ctx.amount(mcc, (2.0, 26.0))
    ctx.txn(
        amount=amount,
        channel="upi_instant" if ctx.rng.random() < 0.6 else "bank_transfer",
        mcc=mcc,
        auth_result="declined" if ctx.world.declined else "approved",
    )
    if not ctx.world.declined:
        ctx.edge(target, amount, "transfer")
    ctx.advance(1, 90)


def structured_withdrawal(ctx: ChainContext) -> None:
    """Amounts clustered just under a round threshold, spread over hours."""
    threshold = float(ctx.params.get("threshold_inr", 50000))
    margin = ctx.params.get("under_threshold_margin_inr", [500, 4800])
    n = int(ctx.rng.integers(*ctx.params.get("n_withdrawals", [4, 18])))
    target = ctx.beneficiary or str(ctx.rng.choice(ctx.world.mule_pool))

    for i in range(n):
        if i > 0 and ctx.world.aborted(ctx.position + i // 4):
            return
        ctx.advance(30, 9 * 60)
        amount = (threshold - float(ctx.rng.uniform(*margin))) * ctx.scale
        ctx.txn(amount=max(1.0, amount), channel="bank_transfer", mcc=ctx.blend_mcc("6011"))
        ctx.edge(target, max(1.0, amount), "transfer")


def merchant_collusion_payout(ctx: ChainContext) -> None:
    """Value extracted through a controlled merchant acquiring account."""
    merchant = ctx.world.young_merchant()
    for _ in range(int(ctx.rng.integers(2, 7))):
        ctx.advance(5, 240)
        ctx.txn(
            amount=ctx.amount(merchant["mcc"], (1.5, 12.0)),
            channel="merchant_payouts",
            mcc=merchant["mcc"],
            merchant_id=merchant["merchant_id"],
        )


def agentic_purchase(ctx: ChainContext) -> None:
    """A manipulated agent buys on the victim's behalf. No human interaction event."""
    merchant = ctx.world.merchant("5732")
    ctx.txn(
        amount=ctx.amount(merchant["mcc"], (1.2, 8.0)),
        channel="agentic_commerce",
        mcc=merchant["mcc"],
        merchant_id=merchant["merchant_id"],
    )
    ctx.advance(1, 60)


# ---------------------------------------------------------------------------
# Obfuscate
# ---------------------------------------------------------------------------


def layer_through_mules(ctx: ChainContext) -> None:
    """Fan out, rest briefly, collect. The topology is the whole signature."""
    n_mules = int(ctx.rng.integers(*ctx.params.get("n_mules", [4, 14])))
    pool = ctx.world.mule_pool
    mules = [str(m) for m in ctx.rng.choice(pool, size=min(n_mules, len(pool)), replace=False)]
    if len(mules) < 3:
        return
    hub, sink = mules[0], mules[-1]
    dormant = ctx.rng.random() < float(
        ctx.world.cfg["simulation"].get("realism", {}).get("p_dormant_hop", 0.0)
    )
    amount = ctx.amount("6012", (2.0, 18.0))

    for hop, mule in enumerate(mules[1:-1]):
        if ctx.world.aborted(ctx.position + hop // 3):
            return
        share = amount / max(len(mules) - 2, 1) * float(ctx.rng.uniform(0.85, 1.15))
        ctx.advance(*ctx.params.get("hop_delay_minutes", [3, 55]))
        ctx.em.transaction(
            ts=ctx.t, account_id=hub, device_id=ctx.device, merchant_id=None,
            amount=max(1.0, share), channel="bank_transfer",
            geography=ctx.trait.home_geo, mcc="6012", auth_result="approved",
            is_fraud=True, vector_id=ctx.vector_id, instance_id=ctx.instance_id,
            chain_position=ctx.position, generation=ctx.world.generation,
        )
        ctx.em.edge(ts=ctx.t, source=hub, target=mule, amount=max(1.0, share),
                    edge_type="transfer")

        residence = float(ctx.rng.uniform(*ctx.params.get("residence_seconds", [60, 5400])))
        if dormant:
            residence *= float(ctx.rng.uniform(20, 400))
        ctx.t += timedelta(seconds=residence)
        onward = share * float(ctx.rng.uniform(0.9, 0.99))
        ctx.em.transaction(
            ts=ctx.t, account_id=mule, device_id=ctx.device, merchant_id=None,
            amount=max(1.0, onward), channel="upi_instant",
            geography=ctx.trait.home_geo, mcc="6011", auth_result="approved",
            is_fraud=True, vector_id=ctx.vector_id, instance_id=ctx.instance_id,
            chain_position=ctx.position, generation=ctx.world.generation,
        )
        ctx.em.edge(ts=ctx.t, source=mule, target=sink, amount=max(1.0, onward),
                    edge_type="transfer")
        ctx.em.edge(ts=ctx.t, source=mule, target=hub, amount=0.0, edge_type="shared_device")


def cross_channel_hop(ctx: ChainContext) -> None:
    """The same value crossing rails within a short window, to defeat single-rail rules."""
    amount = ctx.amount("6011", (1.5, 9.0))
    for channel, mcc in (("wallets_tokenisation", "4814"), ("upi_instant", "6011")):
        ctx.advance(2, 90)
        ctx.txn(amount=max(1.0, amount * float(ctx.rng.uniform(0.9, 1.0))),
                channel=channel, mcc=mcc)


def dispute_after_extraction(ctx: ChainContext) -> None:
    """Chargeback raised after the value is gone, recovering the funds a second time."""
    events = [
        _event("app_open", 0, screen="home"),
        _event("nav", int(ctx.rng.integers(2000, 30000)), screen="disputes"),
        _event("dispute_open", int(ctx.rng.integers(31000, 90000)), screen="disputes",
               field="note", input_method="paste",
               dwell_ms=int(ctx.rng.integers(4000, 40000)), corrections=int(ctx.rng.poisson(2))),
    ]
    ctx.advance(60 * 24, 60 * 24 * 20)
    ctx.session(channel="cards_cnp", events=events, outcome="completed")


def _event(kind: str, t_offset_ms: int, **extra: Any) -> dict[str, Any]:
    return {
        "type": kind,
        "t_offset_ms": t_offset_ms,
        "screen": None,
        "field": None,
        "input_method": None,
        "dwell_ms": None,
        "corrections": None,
        **extra,
    }


PRIMITIVES: dict[str, Callable[[ChainContext], None]] = {
    "phish_credential": phish_credential,
    "clone_voice_otp": clone_voice_otp,
    "deepfake_kyc": deepfake_kyc,
    "synthesise_identity": synthesise_identity,
    "compromise_agent": compromise_agent,
    "provision_token": provision_token,
    "register_device": register_device,
    "open_mule_account": open_mule_account,
    "add_beneficiary": add_beneficiary,
    "micro_test": micro_test,
    "card_test_sweep": card_test_sweep,
    "balance_probe": balance_probe,
    "drain_single": drain_single,
    "structured_withdrawal": structured_withdrawal,
    "merchant_collusion_payout": merchant_collusion_payout,
    "agentic_purchase": agentic_purchase,
    "layer_through_mules": layer_through_mules,
    "cross_channel_hop": cross_channel_hop,
    "dispute_after_extraction": dispute_after_extraction,
}


def execute_chain(world: Any, vector: dict[str, Any]) -> int:
    """Run one instance of a chain. Returns the number of primitives that executed.

    The abort profile drawn in ``World.new_instance`` decides how far it gets, so the
    fraud population contains partial executions rather than only the attacker's best
    case.
    """
    instance_id = world.new_instance()
    ctx = ChainContext(
        world=world,
        trait=world.victim(),
        vector_id=vector["vector_id"],
        instance_id=instance_id,
        params=vector.get("parameters", {}),
        t=world.when(),
        device=world.foreign_device(),
        scale=world.restraint,
    )

    executed = 0
    for position, name in enumerate(vector["chain"], start=1):
        if world.aborted(position):
            break
        fn = PRIMITIVES.get(name)
        if fn is None:
            continue
        ctx.position = position
        fn(ctx)
        ctx.emitted.append(name)
        executed += 1
    return executed
