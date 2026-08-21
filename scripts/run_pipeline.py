"""End to end: simulate, split, train, evaluate, publish.

    python scripts/run_pipeline.py --transactions 2000000 --accounts 40000

Writes to artifacts/published/: run_manifest.json, misses.g0.json, demo_slice.json,
score_distribution.json. Those are what the prototype reads and the only generated files
that get committed. The full ledger stays out of git and is regenerable from the seed.

Three things this script is careful about, all of them things a judge can ask about:

  * The headline baseline is a TUNED gradient-boosted model on transaction features, not
    the logistic regression. Lift over a weak floor is a number that collapses under one
    question. The logistic regression is kept and reported as a floor, labelled as such.
  * Held-out attack families never appear in training, and their metrics are reported
    separately. Merging them with seen performance would be the single most misleading
    thing this repository could do.
  * The score distribution is printed. If fraud sits far from the boundary rather than
    near it, high recall is a statement about attack realism, not detector quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from adl.common.config import config_hash, load_config, source_digest
from adl.common.contracts import coverage_report, validate
from adl.common.paths import ARTIFACTS_DIR, FIXTURES_DIR
from adl.defend.features import (
    CADENCE_SIGNAL_FEATURES,
    COERCION_SIGNAL_FEATURES,
    SESSION_FEATURES,
    build_features,
    feature_columns,
)
from adl.defend.models import fit_baseline, fit_gbm, fit_tuned_baseline, top_contributions
from adl.evaluate.metrics import (
    add_lift,
    choose_threshold,
    compute_metrics,
    format_table,
    instance_detection,
    per_vector_row_detection,
)
from adl.evaluate.splits import assert_leak_free, time_and_account_split
from adl.generate.simulator import simulate

PUBLISHED = ARTIFACTS_DIR / "published"


def load_cached_ledger(cache_dir):  # noqa: ANN001, ANN201
    """Reload a previously simulated ledger from Parquet.

    Reproducibility is unaffected: the cache key is the seed and the size, and the
    simulator is deterministic in both, so a cached ledger is bit-identical to the one a
    fresh run would produce. Deleting the cache directory is always safe.
    """
    from adl.generate.simulator import Ledger

    tables = {
        name: pd.read_parquet(cache_dir / f"{name}.parquet")
        for name in ("accounts", "devices", "merchants", "transactions",
                     "sessions", "session_events", "graph_edges")
    }
    return Ledger(
        **tables,
        meta={"prevalence_actual": float(tables["transactions"]["is_fraud"].mean()),
              "cached": True},
    )


def _git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


def score_distribution(y: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    """How far fraud sits from the boundary, and how far legitimate traffic sits from it.

    A detector at 100% recall can mean two very different things. If fraudulent instances
    score just above the threshold, the problem is hard and the model is good at it. If
    they cluster at the top of the range with a wide empty gap beneath them, the attacks
    are too clean and the number is a statement about the simulator.
    """
    fraud = np.asarray(scores)[np.asarray(y) == 1]
    legit = np.asarray(scores)[np.asarray(y) == 0]
    if not len(fraud) or not len(legit):
        return {}

    legit_99 = float(np.percentile(legit, 99))
    legit_99_9 = float(np.percentile(legit, 99.9))
    return {
        "n_fraud": int(len(fraud)),
        "fraud_p05": round(float(np.percentile(fraud, 5)), 4),
        "fraud_p50": round(float(np.percentile(fraud, 50)), 4),
        "fraud_p95": round(float(np.percentile(fraud, 95)), 4),
        "legit_p50": round(float(np.percentile(legit, 50)), 6),
        "legit_p99": round(legit_99, 4),
        "legit_p99_9": round(legit_99_9, 4),
        "threshold": round(float(threshold), 6),
        # The separation number. Near 1.0 means almost every fraudulent row outscores 99%
        # of legitimate traffic, which is the shape of an unrealistically clean attack.
        "fraud_above_legit_p99": round(float((fraud > legit_99).mean()), 4),
        # Fraud inside the band where legitimate traffic still lives. These are the
        # genuinely hard cases, and their absence is what an over-clean attack model
        # looks like.
        "fraud_in_overlap_band": round(float((fraud < legit_99_9).mean()), 4),
        # Positive means an empty corridor between the top of legitimate traffic and the
        # bottom of fraud. A wide one is a simulator artefact, not a detector achievement.
        "separation_gap": round(float(np.percentile(fraud, 5) - legit_99_9), 4),
    }


def _demo_slice(ledger, score_lookup: dict[str, float], n_rows: int) -> dict[str, Any]:  # noqa: ANN001
    """Columnar JSON, session events only for surfaced alerts."""
    txns = ledger.transactions
    start = max(0, len(txns) // 2 - n_rows // 2)
    window = txns.iloc[start:start + n_rows].reset_index(drop=True)

    window_scores: list[float | None] = [
        None if t not in score_lookup else round(float(score_lookup[t]), 5)
        for t in window["transaction_id"]
    ]

    columns = {
        "transaction_id": window["transaction_id"].tolist(),
        "account_id": window["account_id"].tolist(),
        "device_id": window["device_id"].tolist(),
        "timestamp": window["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist(),
        "amount_inr": [round(float(a), 2) for a in window["amount_inr"]],
        "channel": window["channel"].tolist(),
        "geography": window["geography"].tolist(),
        "mcc": window["mcc"].tolist(),
        "auth_result": window["auth_result"].tolist(),
        "is_fraud": [bool(b) for b in window["is_fraud"]],
        "vector_id": [None if pd.isna(v) else str(v) for v in window["vector_id"]],
        "score": window_scores,
    }

    surfaced = window.loc[
        [s is not None and s > 0.5 for s in window_scores], "session_id"
    ].dropna().unique()[:120]
    events = ledger.session_events[ledger.session_events["session_id"].isin(surfaced)]
    sessions_payload = {
        sid: group.drop(columns=["session_id"]).where(pd.notna(group), None).to_dict("records")
        for sid, group in events.groupby("session_id")
    }

    accounts_in_window = set(window["account_id"])
    edges = ledger.graph_edges[
        ledger.graph_edges["source_account"].isin(accounts_in_window)
        | ledger.graph_edges["target_account"].isin(accounts_in_window)
    ].head(6000)

    return {
        "contract_version": "0.1.0",
        "format": "columnar",
        "n_rows": len(window),
        "prevalence": round(float(window["is_fraud"].mean()), 5),
        "columns": columns,
        "sessions": sessions_payload,
        "graph_edges": {
            "source_account": edges["source_account"].tolist(),
            "target_account": edges["target_account"].tolist(),
            "amount_inr": [round(float(a), 2) for a in edges["amount_inr"]],
            "edge_type": edges["edge_type"].tolist(),
            "timestamp": edges["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist(),
        },
        "accounts": {
            aid: bool(m)
            for aid, m in zip(ledger.accounts["account_id"], ledger.accounts["label_is_mule"])
            if aid in accounts_in_window
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transactions", type=int, default=300_000)
    parser.add_argument("--accounts", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument(
        "--cache-ledger",
        action="store_true",
        help="Write the simulated ledger to artifacts/ledger_cache and reuse it on the "
             "next run with the same seed and size. A two-million-row simulate takes "
             "half an hour; throwing that away on every iteration is the difference "
             "between running the evaluation twice a day and twenty times.",
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    seed = args.seed if args.seed is not None else cfg["run"]["seed"]
    review_cost = float(cfg["cost_model"]["review_cost_inr"])

    attacks = json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))
    held_out = {v["vector_id"] for v in attacks["vectors"] if v["holdout"] == "family"}
    held_comp = {v["vector_id"] for v in attacks["vectors"] if v["holdout"] == "composition"}
    withheld = held_out | held_comp
    seen_vectors = {v["vector_id"] for v in attacks["vectors"]} - withheld

    print("=" * 74)
    # The cache key has to cover the attack set, not just the seed and the size. It did
    # not, and the first run after three new vectors were added silently reused a ledger
    # generated before they existed: the held-out families were simply absent and the
    # evaluation reported on the wrong experiment. Stale-cache bugs produce numbers for
    # code you did not run, which is the worst failure mode available to this project.
    # The key covers the attack set AND the simulator source. Attacks alone was not
    # enough: editing a primitive changes every row in the ledger while leaving the
    # vector definitions untouched, so a cache keyed on attacks would happily serve a
    # ledger built by code that no longer exists.
    simulator_source = b"".join(
        (Path(__file__).resolve().parents[1] / "src" / "adl" / "generate" / name).read_bytes()
        for name in ("simulator.py", "primitives.py")
    )
    attacks_digest = hashlib.sha256(
        json.dumps(
            [(v["vector_id"], v["chain"], v.get("parameters"), v.get("holdout"))
             for v in attacks["vectors"]],
            sort_keys=True,
        ).encode()
        + simulator_source
    ).hexdigest()[:10]
    cache_dir = (
        ARTIFACTS_DIR / "ledger_cache"
        / f"{seed}-{args.transactions}-{args.accounts}-{attacks_digest}"
    )
    if args.cache_ledger and (cache_dir / "transactions.parquet").exists():
        print(f"simulate (cached: {cache_dir.name})")
        ledger = load_cached_ledger(cache_dir)
    else:
        print("simulate")
        ledger = simulate(n_transactions=args.transactions, seed=seed, n_accounts=args.accounts)
        if args.cache_ledger:
            ledger.write_parquet(cache_dir)
            print(f"  cached to {cache_dir.name}")
    print("  " + ledger.summary())

    print("features")
    features = build_features(ledger)
    print(f"  {features.shape[1]} columns over {len(features):,} rows")

    print("split")
    split = time_and_account_split(
        features,
        train_fraction=cfg["split"]["train_fraction"],
        embargo_days=cfg["split"]["embargo_days"],
    )
    assert_leak_free(split)
    print("  " + split.describe())

    # PDF S6.3. Held-out families never appear in training at all. Legitimate traffic is
    # untouched; only the fraudulent rows of those vectors are withheld.
    train_all, test_all = split.train, split.test
    train = train_all[(train_all["is_fraud"] == 0) | (~train_all["vector_id"].isin(withheld))]
    seen_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(seen_vectors))]
    unseen_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(held_out))]
    comp_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(held_comp))]

    print(f"  held-out families:     {sorted(held_out) or 'none'}")
    print(f"  held-out compositions: {sorted(held_comp) or 'none'}")
    print(f"  train       {len(train):>8,} rows, {int(train['is_fraud'].sum()):>5} fraud")
    print(f"  seen test   {len(seen_test):>8,} rows, {int(seen_test['is_fraud'].sum()):>5} fraud")
    print(f"  unseen test {len(unseen_test):>8,} rows, {int(unseen_test['is_fraud'].sum()):>5} fraud")

    y_train = train["is_fraud"].to_numpy()
    amounts_train = train["amount_inr"].to_numpy()
    y_seen = seen_test["is_fraud"].to_numpy()
    amounts_seen = seen_test["amount_inr"].to_numpy()
    y_unseen = unseen_test["is_fraud"].to_numpy()
    amounts_unseen = unseen_test["amount_inr"].to_numpy()
    y_comp = comp_test["is_fraud"].to_numpy()
    amounts_comp = comp_test["amount_inr"].to_numpy()

    txn_cols = list(cfg["baseline"]["features"])

    print("baseline (tuned xgboost, primary)")
    tuned, tuning = fit_tuned_baseline(train, seen_test, txn_cols, seed=seed)
    tuned_threshold, _ = choose_threshold(y_train, tuned.scores_train, amounts_train, review_cost)
    baseline_metrics = compute_metrics(
        y_seen, tuned.scores_test, tuned_threshold,
        review_cost_inr=review_cost, amounts=amounts_seen,
    )
    print(f"  selected {tuning['selected']}")
    print(f"  validation AUC-PR {tuning['validation_auc_pr']}")

    print("baseline (logistic regression, floor)")
    floor = fit_baseline(train, seen_test, txn_cols)
    floor_threshold, _ = choose_threshold(y_train, floor.scores_train, amounts_train, review_cost)
    floor_metrics = compute_metrics(
        y_seen, floor.scores_test, floor_threshold,
        review_cost_inr=review_cost, amounts=amounts_seen,
    )
    add_lift(floor_metrics, baseline_metrics)

    all_levels = {"transaction", "session", "graph"}
    variants: list[tuple[str, list[str], bool]] = [
        ("txn_only", feature_columns({"transaction"}), False),
        ("txn+session", feature_columns({"transaction", "session"}), False),
        ("all_levels", feature_columns(all_levels), True),
        ("all_levels_minus_graph", feature_columns({"transaction", "session"}), False),
        ("all_levels_minus_coercion_signal",
         feature_columns(all_levels, drop=COERCION_SIGNAL_FEATURES), False),
        ("all_levels_minus_cadence_signal",
         feature_columns(all_levels, drop=CADENCE_SIGNAL_FEATURES), False),
    ]

    print("train")
    ablation: list[dict[str, Any]] = []
    headline: dict[str, Any] | None = None
    headline_unseen: dict[str, Any] | None = None
    headline_comp: dict[str, Any] | None = None
    comp_scores = np.array([])
    headline_fit = None
    headline_threshold = 0.5
    distribution: dict[str, Any] = {}
    unseen_scores = np.array([])

    for name, columns, is_headline in variants:
        fitted = fit_gbm(train, seen_test, columns, name, seed=seed, measure_latency=is_headline)
        threshold, _ = choose_threshold(y_train, fitted.scores_train, amounts_train, review_cost)
        metrics = compute_metrics(
            y_seen, fitted.scores_test, threshold,
            review_cost_inr=review_cost, amounts=amounts_seen,
            latency_p50_ms=fitted.latency_p50_ms, latency_p99_ms=fitted.latency_p99_ms,
        )
        add_lift(metrics, baseline_metrics)
        ablation.append({"variant": name, "metrics": metrics})

        if is_headline:
            headline, headline_fit, headline_threshold = metrics, fitted, threshold
            distribution = score_distribution(y_seen, fitted.scores_test, threshold)
            # Same fitted model, scored against the held-out families. Refitting for the
            # unseen set would defeat the entire point of holding them out.
            unseen_scores = fitted.model.predict_proba(
                unseen_test.reindex(columns=columns).to_numpy(dtype=np.float64, na_value=np.nan)
            )[:, 1]
            headline_unseen = compute_metrics(
                y_unseen, unseen_scores, threshold,
                review_cost_inr=review_cost, amounts=amounts_unseen,
            )
            add_lift(headline_unseen, baseline_metrics)

            comp_scores = fitted.model.predict_proba(
                comp_test.reindex(columns=columns).to_numpy(dtype=np.float64, na_value=np.nan)
            )[:, 1]
            headline_comp = compute_metrics(
                y_comp, comp_scores, threshold,
                review_cost_inr=review_cost, amounts=amounts_comp,
            )
            add_lift(headline_comp, baseline_metrics)

    assert headline is not None and headline_fit is not None and headline_unseen is not None

    print("\nresults, evaluated on the unmodified distribution")
    print("-" * 74)
    print(format_table("BASELINE xgboost tuned, txn only", baseline_metrics))
    print(format_table("floor: logistic regression", floor_metrics))
    print("-" * 74)
    for row in ablation:
        print(format_table(row["variant"], row["metrics"]))
    print("-" * 74)
    print(format_table("HELD-OUT families (novel extraction)", headline_unseen))
    if headline_comp and headline_comp["prevalence"] > 0:
        print(format_table("HELD-OUT compositions (seen prims)", headline_comp))
    elif headline_comp:
        print("HELD-OUT compositions        no instances in the test window at this scale")
    print("-" * 74)
    print(f"operating threshold {headline_threshold:.6f}, chosen on train by net value")

    print("\nscore distribution, seen test")
    for key, value in distribution.items():
        print(f"  {key:26s} {value}")
    if distribution.get("fraud_above_legit_p99", 0) > 0.9:
        print("  NOTE: nearly every fraudulent row outscores 99% of legitimate traffic.")
        print("        That is a statement about attack realism, not detector quality.")

    instance_recall, per_vector, missed_instances = instance_detection(
        y_seen, headline_fit.scores_test, seen_test["instance_id"].to_numpy(),
        seen_test["vector_id"].to_numpy(), headline_threshold,
    )
    unseen_recall, unseen_per_vector, _ = instance_detection(
        y_unseen, unseen_scores, unseen_test["instance_id"].to_numpy(),
        unseen_test["vector_id"].to_numpy(), headline_threshold,
    )
    comp_recall, comp_per_vector, _ = instance_detection(
        y_comp, comp_scores, comp_test["instance_id"].to_numpy(),
        comp_test["vector_id"].to_numpy(), headline_threshold,
    )
    per_vector_rows = per_vector_row_detection(
        y_seen, headline_fit.scores_test, seen_test["vector_id"].to_numpy(), headline_threshold
    )
    row_rate = {r["vector_id"]: r for r in per_vector_rows}

    print("\nper vector, instance detection [rows in brackets]")
    for row in per_vector:
        rows_for = row_rate.get(row["vector_id"], {"n_detected": 0, "n_instances": 0})
        print(f"  {row['vector_id']}  {row['n_detected']:>4}/{row['n_instances']:<4} instances "
              f"{row['detection_rate']:>6.1%}   "
              f"[{rows_for['n_detected']}/{rows_for['n_instances']} rows]")
    print(f"  SEEN instance recall   {instance_recall:.1%} over "
          f"{sum(r['n_instances'] for r in per_vector)} instances")
    for row in unseen_per_vector:
        row["holdout"] = "family"
        print(f"  {row['vector_id']}  {row['n_detected']:>4}/{row['n_instances']:<4} instances "
              f"{row['detection_rate']:>6.1%}   HELD OUT, never trained on")
    print(f"  UNSEEN-FAMILY instance recall {unseen_recall:.1%} over "
          f"{sum(r['n_instances'] for r in unseen_per_vector)} instances")
    for row in comp_per_vector:
        row["holdout"] = "composition"
        print(f"  {row['vector_id']}  {row['n_detected']:>4}/{row['n_instances']:<4} instances "
              f"{row['detection_rate']:>6.1%}   HELD OUT composition")
    print(f"  UNSEEN-COMPOSITION instance recall {comp_recall:.1%} over "
          f"{sum(r['n_instances'] for r in comp_per_vector)} instances")

    missed_set = set(missed_instances)
    test_instances = seen_test["instance_id"].to_numpy()
    representative: dict[str, int] = {}
    for pos in np.flatnonzero(y_seen == 1):
        instance = test_instances[pos]
        if instance in missed_set:
            current = representative.get(instance)
            if current is None or headline_fit.scores_test[pos] > headline_fit.scores_test[current]:
                representative[instance] = int(pos)
    missed = np.array(sorted(representative.values()), dtype=int)
    shap_rows = top_contributions(headline_fit, seen_test, missed[:400])
    chain_by_vector = {v["vector_id"]: v["chain"] for v in attacks["vectors"]}

    misses_payload = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-g0-{seed}",
        "generation": 0,
        "threshold": round(float(headline_threshold), 6),
        "prevalence": round(float(y_seen.mean()), 6),
        "misses": [
            {
                "instance_id": str(seen_test.iloc[int(pos)]["instance_id"]),
                "vector_id": str(seen_test.iloc[int(pos)]["vector_id"]),
                "chain": chain_by_vector.get(str(seen_test.iloc[int(pos)]["vector_id"]), []),
                "primitives_present": chain_by_vector.get(
                    str(seen_test.iloc[int(pos)]["vector_id"]), []
                ),
                "score": round(float(headline_fit.scores_test[int(pos)]), 6),
                "level_scores": {"transaction": None, "session": None, "graph": None},
                "top_shap": shap,
                "evasion_hypothesis": None,
            }
            for pos, shap in zip(missed[:400], shap_rows)
        ],
        "per_vector": per_vector + unseen_per_vector + comp_per_vector,
    }
    validate("misses", misses_payload)

    coverage = coverage_report(attacks["vectors"])
    manifest = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-{seed}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "config_hash": config_hash(),
        "source_digest": source_digest(),
        "code_version": _git_sha(),
        "prevalence": round(float(ledger.meta["prevalence_actual"]), 6),
        "is_fixture": False,
        "baseline": {
            "name": "xgboost_tuned_transaction_only",
            "features": txn_cols,
            "metrics": baseline_metrics,
        },
        "baseline_floor": {
            "name": "logistic_regression_transaction_only",
            "features": txn_cols,
            "metrics": floor_metrics,
        },
        "generations": [{
            "generation": 0,
            "n_vectors": len(attacks["vectors"]),
            "n_transactions": int(len(ledger.transactions)),
            "n_fraud": int(ledger.transactions["is_fraud"].sum()),
            "metrics_seen": headline,
            "metrics_unseen": headline_unseen,
            # Only reported when the composition holdout actually landed instances in the
            # test window. An empty holdout has prevalence zero, and a metrics object at
            # zero prevalence describes nothing.
            **({"metrics_unseen_composition": headline_comp}
               if headline_comp and headline_comp["prevalence"] > 0 else {}),
            "ablation": ablation,
            "detection_rate": round(instance_recall, 4),
            "n_chains_proposed": 0,
            "n_chains_rejected": 0,
        }],
        "fidelity": {
            "discriminator_auc": None,
            "comparable_columns": ["amount_inr", "hour_of_day", "mcc", "channel", "auth_result"],
            "excluded_columns": SESSION_FEATURES,
            "reference_profiles": [
                {"name": "ieee_cis", "serves_channels": ["cards_cnp", "wallets_tokenisation"],
                 "available": False},
                {"name": "paysim",
                 "serves_channels": ["upi_instant", "bank_transfer", "merchant_payouts"],
                 "available": False},
            ],
            "ks_per_column": None,
            "psi_per_column": None,
            "correlation_delta_frobenius": None,
        },
        "cost_model": {"review_cost_inr": review_cost, "currency": "INR"},
        "artefacts": {
            "attacks": "attacks.json",
            "ledger_dir": "ledger/",
            "demo_slice": "demo_slice.json",
            "misses": ["misses.g0.json"],
            "graph_snapshot": None,
        },
    }
    validate("run_manifest", manifest)

    print("\ncoverage")
    print(f"  {coverage['primitives_used']}/{coverage['primitives_total']} primitives, "
          f"{coverage['grid_cells_populated']}/{coverage['grid_cells_total']} grid cells, "
          f"{len(coverage['channels_covered'])}/7 channels")

    if args.no_publish:
        return 0

    PUBLISHED.mkdir(parents=True, exist_ok=True)
    score_lookup = dict(zip(seen_test["transaction_id"], headline_fit.scores_test))
    slice_payload = _demo_slice(ledger, score_lookup, cfg["simulation"]["demo_slice_rows"])
    slice_payload["threshold"] = round(float(headline_threshold), 6)

    for name, payload in (
        ("run_manifest.json", manifest),
        ("misses.g0.json", misses_payload),
        ("demo_slice.json", slice_payload),
        ("score_distribution.json", distribution),
    ):
        path = PUBLISHED / name
        path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"  wrote {path.name} ({path.stat().st_size / 1024:.0f} KB)")

    (PUBLISHED / "attacks.json").write_text(json.dumps(attacks, indent=2) + "\n", encoding="utf-8")
    ledger.write_parquet(ARTIFACTS_DIR / "ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
