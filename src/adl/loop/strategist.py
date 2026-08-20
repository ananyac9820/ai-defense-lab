"""The red-team strategist.

PDF S7.1: the strategist receives the miss log plus the grammar vocabulary and returns
new chains, in two mutation modes.

  recomposition    reorder or substitute primitives within a chain
  parameter drift  same chain, altered velocity, amounts, or device spread

Deterministic by default, and that is a design decision rather than a limitation. S10
rates "red-team agent produces invalid output" a Moderate risk with the remedy
"substitute parameter-drift mutation, which is deterministic and needs no model". Both
modes here run without a language model at all; the model is an optional layer that
proposes and never executes, and every chain it returns passes the same validation as a
deterministic one.

The interesting part is that mutation is *directed*. The miss log carries SHAP
contributions, so the strategist can see which feature the detector leaned on to catch a
family and move the parameters that feed that feature. That is S7.3's escalation step,
available from the first generation rather than only when the curve flattens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from adl.common.contracts import is_valid_chain, load_grammar, stage_of

# Which simulator parameters feed which detector features. Mutating blind wastes
# generations; this is the map that makes drift purposeful.
FEATURE_TO_PARAMS: dict[str, list[str]] = {
    "sess_cadence_cv": ["inter_arrival_ms"],
    "sess_cadence_entropy": ["inter_arrival_ms"],
    "sess_paste_ratio_payee": ["paste_rate_payee"],
    "sess_confirm_dwell_ms": ["confirm_dwell_ms", "otp_dwell_ms"],
    "sess_n_declines": ["decline_ratio"],
    "dev_decline_ratio_1h": ["decline_ratio"],
    "dev_txn_count_1h": ["cards_per_sweep", "inter_arrival_ms"],
    "acct_txn_count_24h": ["n_withdrawals", "cards_per_sweep"],
    "amount_inr": ["drain_amount_inr", "probe_amount_inr", "micro_test_amount_inr"],
    "log_amount": ["drain_amount_inr", "under_threshold_margin_inr"],
    "amount_z_account": ["drain_amount_inr"],
    "g_residence_seconds": ["residence_seconds", "hop_delay_minutes"],
    "g_passthrough_score": ["split_ratio_jitter", "n_mules"],
    "g_degree_ratio": ["n_mules"],
    "g_fanout_24h": ["n_mules"],
    "g_beneficiary_novelty": ["payee_age_minutes"],
    "account_age_days": ["days_dormant_after_open"],
    "geography_matches_home": ["geo_jump_km"],
}


@dataclass
class Proposal:
    vector: dict[str, Any]
    mode: str
    rationale: str


def _next_vector_id(existing: list[dict[str, Any]]) -> str:
    used = {int(v["vector_id"][1:]) for v in existing if v["vector_id"][1:].isdigit()}
    return f"V{max(used) + 1:03d}" if used else "V001"


def _pressure_points(miss_records: list[dict[str, Any]]) -> list[str]:
    """Features that most often pushed instances towards being caught.

    A positive SHAP contribution moved the instance towards the fraud class, so the
    features with the largest positive mass across the miss log are the ones the detector
    is leaning on. Those are what the next generation should attack.
    """
    weight: dict[str, float] = {}
    for record in miss_records:
        for entry in record.get("top_shap", []):
            if entry["value"] > 0:
                weight[entry["feature"]] = weight.get(entry["feature"], 0.0) + entry["value"]
    return [f for f, _ in sorted(weight.items(), key=lambda kv: -kv[1])]


def recompose(
    parent: dict[str, Any], rng: np.random.Generator, attempts: int = 40
) -> tuple[list[str], str] | None:
    """Reorder or substitute primitives, keeping the chain grammar-valid.

    Held-out compositions are cheap to build this way: same primitives the detector saw
    during training, arranged in an order it never did (PDF S6.3).
    """
    grammar = load_grammar()
    by_stage: dict[str, list[str]] = {}
    for name, spec in grammar["primitives"].items():
        by_stage.setdefault(spec["stage"], []).append(name)

    for _ in range(attempts):
        chain = list(parent["chain"])
        if rng.random() < 0.55 and len(chain) > 1:
            # substitute one primitive for a sibling at the same stage
            index = int(rng.integers(0, len(chain)))
            siblings = [p for p in by_stage[stage_of(chain[index])] if p != chain[index]]
            if not siblings:
                continue
            replacement = str(rng.choice(siblings))
            chain[index] = replacement
            note = f"substituted {parent['chain'][index]} with {replacement}"
        else:
            # insert a primitive from a stage the chain does not yet use
            unused = [s for s in grammar["stage_order"]
                      if s not in {stage_of(p) for p in chain}]
            if not unused:
                continue
            stage = str(rng.choice(unused))
            addition = str(rng.choice(by_stage[stage]))
            order = grammar["stage_order"]
            chain.append(addition)
            chain.sort(key=lambda p: order.index(stage_of(p)))
            note = f"inserted {addition} at stage {stage}"

        if chain != parent["chain"] and is_valid_chain(chain, parent["objective"]):
            return chain, note
    return None


def drift(
    parent: dict[str, Any], targets: list[str], rng: np.random.Generator
) -> tuple[dict[str, Any], str]:
    """Same chain, parameters moved against whatever the detector is leaning on.

    Ranges widen and shift rather than being replaced, so a drifted vector stays a
    plausible execution of the same attack rather than becoming a different one.
    """
    params = {k: list(v) if isinstance(v, list) else v for k, v in parent["parameters"].items()}
    wanted: list[str] = []
    for feature in targets:
        wanted.extend(FEATURE_TO_PARAMS.get(feature, []))

    touched: list[str] = []
    for name in wanted:
        value = params.get(name)
        if not isinstance(value, list) or len(value) != 2:
            continue
        if not all(isinstance(x, (int, float)) for x in value):
            continue
        lo, hi = float(value[0]), float(value[1])
        span = max(hi - lo, abs(hi) * 0.1, 1e-6)
        # Push towards the ordinary end and widen: slower, smaller, less distinctive.
        new_lo = max(0.0, lo - span * float(rng.uniform(0.1, 0.6)))
        new_hi = hi + span * float(rng.uniform(0.2, 1.2))
        params[name] = [round(new_lo, 4), round(new_hi, 4)]
        touched.append(name)
        if len(touched) >= 3:
            break

    if not touched:
        # Nothing mapped: widen one numeric range at random so a generation is never wasted
        numeric = [k for k, v in params.items()
                   if isinstance(v, list) and len(v) == 2
                   and all(isinstance(x, (int, float)) for x in v)]
        if numeric:
            name = str(rng.choice(numeric))
            lo, hi = float(params[name][0]), float(params[name][1])
            params[name] = [round(lo * 0.6, 4), round(hi * 1.6, 4)]
            touched.append(name)

    return params, "widened " + ", ".join(touched) if touched else "no parameter moved"


def propose(
    misses: dict[str, Any],
    vectors: list[dict[str, Any]],
    *,
    rng: np.random.Generator,
    generation: int,
    n: int = 8,
) -> list[Proposal]:
    """Generate candidate vectors for the next generation.

    Families that survived longest get mutated first: the miss log's per-vector detection
    rates say where the detector is weakest, and that is where another push is most likely
    to pay.
    """
    by_id = {v["vector_id"]: v for v in vectors}
    survival = sorted(misses.get("per_vector", []), key=lambda r: r["detection_rate"])
    targets = _pressure_points(misses.get("misses", []))

    proposals: list[Proposal] = []
    working = list(vectors)

    for row in survival:
        parent = by_id.get(row["vector_id"])
        if parent is None:
            continue
        for mode in ("parameter_drift", "recomposition"):
            if len(proposals) >= n:
                break
            child = {**parent}
            child["vector_id"] = _next_vector_id(working)
            child["generation"] = generation
            child["parent_vector_id"] = parent["vector_id"]
            child["mutation_mode"] = mode
            child["holdout"] = "none"

            if mode == "parameter_drift":
                child["parameters"], note = drift(parent, targets, rng)
                child["chain"] = list(parent["chain"])
                child["name"] = f"{parent['name']} (drift g{generation})"
            else:
                result = recompose(parent, rng)
                if result is None:
                    continue
                child["chain"], note = result
                child["parameters"] = {
                    k: list(v) if isinstance(v, list) else v
                    for k, v in parent["parameters"].items()
                }
                child["name"] = f"{parent['name']} (recomposed g{generation})"

            child["data_signature"] = (
                f"Generation {generation} mutation of {parent['vector_id']}: {note}. "
                f"Directed at {', '.join(targets[:3]) or 'no measured pressure point'}."
            )
            child["expected_levels"] = list(parent["expected_levels"])
            child["source"] = {**parent["source"]}
            child["narrative"] = None
            proposals.append(Proposal(vector=child, mode=mode, rationale=note))
            working.append(child)

    return proposals[:n]
