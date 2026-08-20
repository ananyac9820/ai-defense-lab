"""The closed adversarial loop. PDF S7, and the novelty claim.

    python scripts/run_loop.py --generations 5 --transactions 400000

Each generation: simulate the current attack set, train, score, log what evaded, hand the
miss log to the red-team strategist, validate what comes back, append it, repeat.

The output is the detection-rate-per-generation curve, which the strategy document calls
the single most compelling artefact in the submission. It is also the one that can most
easily be faked, so three things are recorded alongside it and none of them flatter us:

  * the rejection rate of the validation layer, per generation;
  * which vectors survived longest, which is a finding rather than a metric;
  * whether the curve moved at all. S7.3 is explicit that a flat curve reported honestly
    beats a manufactured one, and this script will say so rather than tuning until it
    bends.

Scale note: the loop runs at a smaller ledger than the headline single-generation result,
because five generations at two million rows is three hours. The scale is stated in the
manifest and in every printout. Curves and headline metrics are never mixed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from adl.common.config import config_hash, load_config
from adl.common.contracts import validate
from adl.common.paths import ARTIFACTS_DIR, FIXTURES_DIR
from adl.common.seeds import rng_for
from adl.evaluate.protocol import evaluate_generation
from adl.generate.simulator import simulate
from adl.loop.strategist import propose
from adl.loop.validation import validate_proposals

PUBLISHED = ARTIFACTS_DIR / "published"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--transactions", type=int, default=400_000)
    parser.add_argument("--accounts", type=int, default=30_000)
    parser.add_argument("--proposals", type=int, default=6)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = load_config()
    seed = args.seed if args.seed is not None else cfg["run"]["seed"]

    attacks = json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))
    vectors: list[dict[str, Any]] = list(attacks["vectors"])

    generations: list[dict[str, Any]] = []
    curve: list[float] = []
    baseline_metrics: dict[str, Any] | None = None

    for g in range(args.generations):
        print("=" * 74)
        print(f"GENERATION {g}  ({len(vectors)} vectors, {args.transactions:,} transactions)")

        ledger = simulate(
            n_transactions=args.transactions,
            seed=seed + g,
            n_accounts=args.accounts,
            vectors=vectors,
        )
        print("  " + ledger.summary())

        result = evaluate_generation(
            ledger, vectors, cfg, generation=g, seed=seed, baseline_metrics=baseline_metrics
        )
        if baseline_metrics is None:
            # Generation 0 is the reference the curve is read against. Every later
            # generation is measured against the same fixed point, or the curve would be
            # comparing each round to itself and could not move.
            baseline_metrics = dict(result.metrics_seen)

        curve.append(result.instance_recall)
        print(f"  {result.split_note}")
        print(f"  seen instance recall {result.instance_recall:.1%}"
              f"   AUC-PR {result.metrics_seen['auc_pr']:.3f}"
              f"   at {result.metrics_seen['prevalence']:.3%} prevalence")
        if result.unseen_recall is not None:
            print(f"  held-out instance recall {result.unseen_recall:.1%}")

        survivors = sorted(result.per_vector, key=lambda r: r["detection_rate"])[:3]
        print("  weakest vectors: " + ", ".join(
            f"{r['vector_id']} {r['detection_rate']:.0%}" for r in survivors
        ) or "  none")

        (PUBLISHED / f"misses.g{g}.json").parent.mkdir(parents=True, exist_ok=True)
        validate("misses", result.misses)
        (PUBLISHED / f"misses.g{g}.json").write_text(
            json.dumps(result.misses, separators=(",", ":")) + "\n", encoding="utf-8"
        )

        proposed = rejected = 0
        if g < args.generations - 1:
            rng = rng_for(seed, f"strategist-g{g + 1}")
            proposals = propose(
                result.misses, vectors, rng=rng, generation=g + 1, n=args.proposals
            )
            outcome = validate_proposals([p.vector for p in proposals], vectors)
            proposed, rejected = len(proposals), len(outcome.rejected)
            print(f"  strategist: {outcome.summary()}")
            for p in proposals[:3]:
                print(f"    {p.vector['vector_id']} {p.mode}: {p.rationale}")
            vectors = vectors + outcome.accepted

        generations.append({
            "generation": g,
            "n_vectors": result.n_vectors,
            "n_transactions": result.n_transactions,
            "n_fraud": result.n_fraud,
            "metrics_seen": result.metrics_seen,
            "metrics_unseen": result.metrics_unseen or result.metrics_seen,
            **({"metrics_unseen_composition": result.metrics_composition}
               if result.metrics_composition else {}),
            "detection_rate": round(result.instance_recall, 4),
            "n_chains_proposed": proposed,
            "n_chains_rejected": rejected,
        })

    print("=" * 74)
    print("detection rate per generation")
    for g, rate in enumerate(curve):
        bar = "#" * int(rate * 50)
        print(f"  G{g}  {rate:6.1%}  {bar}")

    movement = max(curve) - min(curve)
    if movement < 0.02:
        print("\n  The curve is flat. Per S7.3 that is reported as a finding about detector")
        print("  robustness rather than escalated until it bends.")
    else:
        direction = "rising" if curve[-1] > curve[0] else "falling"
        print(f"\n  Curve moved {movement:.1%} across {len(curve)} generations, {direction}.")

    manifest = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-loop-{seed}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "config_hash": config_hash(),
        "code_version": None,
        "prevalence": generations[0]["metrics_seen"]["prevalence"],
        "is_fixture": False,
        "baseline": {
            "name": "generation_0_all_levels",
            "features": ["see run_manifest.json for the tuned transaction-only baseline"],
            "metrics": {**generations[0]["metrics_seen"], "lift_over_baseline": None},
        },
        "generations": generations,
        "fidelity": {
            "discriminator_auc": None,
            "comparable_columns": ["amount_inr", "hour_of_day", "mcc", "channel", "auth_result"],
            "excluded_columns": [],
            "reference_profiles": [],
            "ks_per_column": None,
            "psi_per_column": None,
            "correlation_delta_frobenius": None,
        },
        "cost_model": {"review_cost_inr": float(cfg["cost_model"]["review_cost_inr"]),
                       "currency": "INR"},
        "artefacts": {
            "attacks": "attacks_loop.json",
            "ledger_dir": "ledger/",
            "demo_slice": "demo_slice.json",
            "misses": [f"misses.g{g}.json" for g in range(args.generations)],
            "graph_snapshot": None,
        },
    }
    validate("run_manifest", manifest)
    (PUBLISHED / "run_manifest_loop.json").write_text(
        json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    (PUBLISHED / "attacks_loop.json").write_text(
        json.dumps(
            {"contract_version": "0.1.0",
             "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "grammar_version": "0.1.0",
             "vectors": vectors},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote run_manifest_loop.json and attacks_loop.json ({len(vectors)} vectors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
