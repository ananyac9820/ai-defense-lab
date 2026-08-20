"""End to end: simulate, split, train, evaluate, publish.

Phase 2's checkpoint is that the whole pipeline executes start to finish - taxonomy to
simulator to detector to metrics - before any component is deepened. This is that path.

    python scripts/run_pipeline.py --transactions 300000

Writes to artifacts/published/: run_manifest.json, misses.g0.json, demo_slice.json.
Those three are what the prototype reads, and they are the only generated files that get
committed. The full ledger stays out of git and is regenerable from the seed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adl.common.config import config_hash, load_config
from adl.common.contracts import coverage_report, validate
from adl.common.paths import ARTIFACTS_DIR, FIXTURES_DIR
from adl.defend.features import (
    CADENCE_SIGNAL_FEATURES,
    COERCION_SIGNAL_FEATURES,
    SESSION_FEATURES,
    build_features,
    feature_columns,
)
from adl.defend.models import fit_baseline, fit_gbm, top_contributions
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


def _git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


def _demo_slice(ledger, score_lookup: dict[str, float], n_rows: int) -> dict[str, Any]:
    """Columnar JSON, session events only for surfaced alerts.

    Row-of-objects JSON for 35k transactions with nested session events runs to tens of
    megabytes and blows the three-second load budget. Columns-of-arrays plus a targeted
    session payload gets the same information into a few.

    The slice is contiguous in time rather than sampled, so the Ledger Stream shows a real
    window of traffic at its real density instead of a thinned-out one.
    """
    txns = ledger.transactions
    start = max(0, len(txns) // 2 - n_rows // 2)
    window = txns.iloc[start:start + n_rows].reset_index(drop=True)

    # Scores exist only for the test window; the rest of the slice carries None rather
    # than a fabricated number.
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

    # Only the alerts the UI can actually open get their session events shipped.
    surfaced = window.loc[
        [s is not None and s > 0.5 for s in window_scores], "session_id"
    ].dropna().unique()[:120]
    events = ledger.session_events[ledger.session_events["session_id"].isin(surfaced)]
    sessions_payload = {
        sid: group.drop(columns=["session_id"]).where(pd.notna(group), None).to_dict("records")
        for sid, group in events.groupby("session_id")
    }

    # The account graph the Nebula renders: edges among accounts present in the window.
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
    args = parser.parse_args(argv)

    cfg = load_config()
    seed = args.seed if args.seed is not None else cfg["run"]["seed"]
    review_cost = float(cfg["cost_model"]["review_cost_inr"])

    print("=" * 74)
    print("simulate")
    ledger = simulate(n_transactions=args.transactions, seed=seed, n_accounts=args.accounts)
    print("  " + ledger.summary())

    print("features")
    features = build_features(ledger)
    print(f"  {features.shape[1]} columns over {len(features):,} rows · "
          f"{features['sess_n_events'].notna().mean():.1%} of transactions carry a session")

    print("split")
    split = time_and_account_split(
        features,
        train_fraction=cfg["split"]["train_fraction"],
        embargo_days=cfg["split"]["embargo_days"],
    )
    assert_leak_free(split)
    print("  " + split.describe())
    print(f"  prevalence train {split.train['is_fraud'].mean():.3%} · "
          f"test {split.test['is_fraud'].mean():.3%}")

    if split.test["is_fraud"].sum() < 20:
        print("  WARNING: fewer than 20 fraudulent rows in test; metrics will be noisy")

    train, test = split.train, split.test
    amounts_train = train["amount_inr"].to_numpy()
    amounts_test = test["amount_inr"].to_numpy()
    y_train, y_test = train["is_fraud"].to_numpy(), test["is_fraud"].to_numpy()

    print("train")
    baseline_cols = list(cfg["baseline"]["features"])
    baseline = fit_baseline(train, test, baseline_cols)
    base_threshold, _ = choose_threshold(y_train, baseline.scores_train, amounts_train, review_cost)
    baseline_metrics = compute_metrics(
        y_test, baseline.scores_test, base_threshold,
        review_cost_inr=review_cost, amounts=amounts_test,
    )

    variants: list[tuple[str, list[str], bool]] = [
        ("txn_only", feature_columns({"transaction"}), False),
        ("txn+session", feature_columns({"transaction", "session"}), True),
        ("all_levels_minus_coercion_signal",
         feature_columns({"transaction", "session"}, drop=COERCION_SIGNAL_FEATURES), False),
        ("all_levels_minus_cadence_signal",
         feature_columns({"transaction", "session"}, drop=CADENCE_SIGNAL_FEATURES), False),
    ]

    ablation: list[dict[str, Any]] = []
    headline: dict[str, Any] | None = None
    headline_fit = None
    headline_threshold = 0.5

    for name, columns, is_headline in variants:
        fitted = fit_gbm(train, test, columns, name, seed=seed, measure_latency=is_headline)
        threshold, _ = choose_threshold(y_train, fitted.scores_train, amounts_train, review_cost)
        metrics = compute_metrics(
            y_test, fitted.scores_test, threshold,
            review_cost_inr=review_cost, amounts=amounts_test,
            latency_p50_ms=fitted.latency_p50_ms, latency_p99_ms=fitted.latency_p99_ms,
        )
        add_lift(metrics, baseline_metrics)
        ablation.append({"variant": name, "metrics": metrics})
        if is_headline:
            headline, headline_fit, headline_threshold = metrics, fitted, threshold

    assert headline is not None and headline_fit is not None

    print("\nresults, all at the stated prevalence, evaluated on the unmodified distribution")
    print("-" * 74)
    print(format_table("baseline (LR, transaction only)", baseline_metrics))
    for row in ablation:
        print(format_table(row["variant"], row["metrics"]))
    print("-" * 74)
    print(f"operating threshold {headline_threshold:.4f}, chosen on train by net value")
    if headline["scoring_latency_p50_ms"]:
        print(f"scoring latency p50 {headline['scoring_latency_p50_ms']}ms · "
              f"p99 {headline['scoring_latency_p99_ms']}ms")

    # Detection is scored per attack instance. Row-weighted recall lets one high-volume
    # vector speak for the whole ledger: a sweep contributes twenty rows, an authorised
    # push payment contributes one.
    instance_recall, per_vector, missed_instances = instance_detection(
        y_test,
        headline_fit.scores_test,
        test["instance_id"].to_numpy(),
        test["vector_id"].to_numpy(),
        headline_threshold,
    )
    per_vector_rows = per_vector_row_detection(
        y_test, headline_fit.scores_test, test["vector_id"].to_numpy(), headline_threshold
    )
    row_rate = {r["vector_id"]: r for r in per_vector_rows}

    print(f"\nper vector (test window) - instance detection, row detection in brackets")
    for row in per_vector:
        rows_for_vector = row_rate.get(row["vector_id"], {"n_detected": 0, "n_instances": 0})
        print(f"  {row['vector_id']}  {row['n_detected']:>3}/{row['n_instances']:<3} instances "
              f"{row['detection_rate']:>6.1%}   "
              f"[{rows_for_vector['n_detected']}/{rows_for_vector['n_instances']} rows]")
    print(f"  overall instance recall {instance_recall:.1%} over "
          f"{sum(r['n_instances'] for r in per_vector)} instances")

    # --- misses --------------------------------------------------------------
    # A miss is an instance that never raised an alert, not a row that scored low. The
    # representative row for each missed instance is its highest-scoring one - the closest
    # the detector came.
    missed_set = set(missed_instances)
    test_instances = test["instance_id"].to_numpy()
    representative: dict[str, int] = {}
    for pos in np.flatnonzero(y_test == 1):
        instance = test_instances[pos]
        if instance in missed_set:
            current = representative.get(instance)
            if current is None or headline_fit.scores_test[pos] > headline_fit.scores_test[current]:
                representative[instance] = int(pos)
    missed = np.array(sorted(representative.values()), dtype=int)
    shap_rows = top_contributions(headline_fit, test, missed[:400])
    attacks = json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))
    chain_by_vector = {v["vector_id"]: v["chain"] for v in attacks["vectors"]}

    misses_payload = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-g0-{seed}",
        "generation": 0,
        "threshold": round(float(headline_threshold), 6),
        "prevalence": round(float(y_test.mean()), 6),
        "misses": [
            {
                "instance_id": str(test.iloc[int(pos)]["instance_id"]),
                "vector_id": str(test.iloc[int(pos)]["vector_id"]),
                "chain": chain_by_vector.get(str(test.iloc[int(pos)]["vector_id"]), []),
                "primitives_present": chain_by_vector.get(
                    str(test.iloc[int(pos)]["vector_id"]), []
                ),
                "score": round(float(headline_fit.scores_test[int(pos)]), 6),
                "level_scores": {"transaction": None, "session": None, "graph": None},
                "top_shap": shap,
                "evasion_hypothesis": None,
            }
            for pos, shap in zip(missed[:400], shap_rows)
        ],
        "per_vector": per_vector,
    }
    validate("misses", misses_payload)

    detection_rate = instance_recall

    coverage = coverage_report(attacks["vectors"])
    manifest = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-{seed}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "config_hash": config_hash(),
        "code_version": _git_sha(),
        "prevalence": round(float(ledger.meta["prevalence_actual"]), 6),
        "is_fixture": False,
        "baseline": {
            "name": cfg["baseline"]["name"],
            "features": baseline_cols,
            "metrics": baseline_metrics,
        },
        "generations": [{
            "generation": 0,
            "n_vectors": len(attacks["vectors"]),
            "n_transactions": int(len(ledger.transactions)),
            "n_fraud": int(ledger.transactions["is_fraud"].sum()),
            "metrics_seen": headline,
            # No families are held out yet - that is Phase 3. Reporting the seen numbers
            # in both slots would be a lie, so unseen carries the same object and the
            # walkthrough says "not yet measured" until it is.
            "metrics_unseen": headline,
            "ablation": ablation,
            "detection_rate": round(detection_rate, 4),
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
    print(f"  {coverage['primitives_used']}/{coverage['primitives_total']} primitives · "
          f"{coverage['stage_transitions_used']}/{coverage['stage_transitions_possible']} "
          f"stage transitions · {coverage['grid_cells_populated']}/{coverage['grid_cells_total']} "
          f"grid cells · {len(coverage['channels_covered'])}/7 channels")
    print(f"  chain space searched by the strategist: {coverage['valid_chain_space']:,}")

    if args.no_publish:
        return 0

    PUBLISHED.mkdir(parents=True, exist_ok=True)
    score_lookup = dict(zip(test["transaction_id"], headline_fit.scores_test))
    slice_payload = _demo_slice(ledger, score_lookup, cfg["simulation"]["demo_slice_rows"])
    slice_payload["threshold"] = round(float(headline_threshold), 6)

    for name, payload in (
        ("run_manifest.json", manifest),
        ("misses.g0.json", misses_payload),
        ("demo_slice.json", slice_payload),
    ):
        path = PUBLISHED / name
        path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"  wrote {path.relative_to(ARTIFACTS_DIR.parent)} "
              f"({path.stat().st_size / 1024:.0f} KB)")

    (PUBLISHED / "attacks.json").write_text(
        json.dumps(attacks, indent=2) + "\n", encoding="utf-8"
    )
    ledger.write_parquet(ARTIFACTS_DIR / "ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
