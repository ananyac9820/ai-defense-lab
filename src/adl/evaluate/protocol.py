"""One generation of the evaluation protocol, as a reusable unit.

The single-run pipeline and the closed loop need exactly the same thing: simulate, build
features, split leak-free, train, score seen and held-out separately, log misses. Writing
it twice would guarantee the loop and the headline numbers drift apart, and the first
symptom would be a detection curve that disagrees with the results table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from adl.defend.features import build_features, feature_columns
from adl.defend.models import fit_gbm, top_contributions
from adl.evaluate.metrics import (
    add_lift,
    choose_threshold,
    compute_metrics,
    instance_detection,
)
from adl.evaluate.splits import assert_leak_free, time_and_account_split


@dataclass
class GenerationResult:
    generation: int
    metrics_seen: dict[str, Any]
    metrics_unseen: dict[str, Any] | None
    metrics_composition: dict[str, Any] | None
    instance_recall: float
    unseen_recall: float | None
    per_vector: list[dict[str, Any]]
    misses: dict[str, Any]
    threshold: float
    n_transactions: int
    n_fraud: int
    n_vectors: int
    split_note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _score(model, frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    matrix = frame.reindex(columns=columns).to_numpy(dtype=np.float64, na_value=np.nan)
    return model.predict_proba(matrix)[:, 1]


def evaluate_generation(
    ledger,  # noqa: ANN001
    vectors: list[dict[str, Any]],
    cfg: dict[str, Any],
    *,
    generation: int,
    seed: int,
    baseline_metrics: dict[str, Any] | None = None,
) -> GenerationResult:
    """Train and score one generation against a leak-free split.

    Held-out families and held-out compositions are withheld from training and scored by
    the same fitted model. Refitting for the held-out sets would defeat the point of
    holding them out, which is easy to get wrong and impossible to see afterwards.
    """
    review_cost = float(cfg["cost_model"]["review_cost_inr"])
    held_family = {v["vector_id"] for v in vectors if v.get("holdout") == "family"}
    held_comp = {v["vector_id"] for v in vectors if v.get("holdout") == "composition"}
    withheld = held_family | held_comp
    seen_ids = {v["vector_id"] for v in vectors} - withheld

    features = build_features(ledger)
    split = time_and_account_split(
        features,
        train_fraction=cfg["split"]["train_fraction"],
        embargo_days=cfg["split"]["embargo_days"],
    )
    assert_leak_free(split)

    train_all, test_all = split.train, split.test
    train = train_all[(train_all["is_fraud"] == 0) | (~train_all["vector_id"].isin(withheld))]
    seen_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(seen_ids))]
    unseen_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(held_family))]
    comp_test = test_all[(test_all["is_fraud"] == 0) | (test_all["vector_id"].isin(held_comp))]

    columns = feature_columns({"transaction", "session", "graph"})
    fitted = fit_gbm(train, seen_test, columns, f"all_levels_g{generation}", seed=seed)

    y_train = train["is_fraud"].to_numpy()
    threshold, _ = choose_threshold(
        y_train, fitted.scores_train, train["amount_inr"].to_numpy(), review_cost
    )

    y_seen = seen_test["is_fraud"].to_numpy()
    metrics_seen = compute_metrics(
        y_seen, fitted.scores_test, threshold,
        review_cost_inr=review_cost, amounts=seen_test["amount_inr"].to_numpy(),
    )

    def _held(frame: pd.DataFrame) -> dict[str, Any] | None:
        if frame.empty or frame["is_fraud"].sum() == 0:
            return None
        scores = _score(fitted.model, frame, columns)
        metrics = compute_metrics(
            frame["is_fraud"].to_numpy(), scores, threshold,
            review_cost_inr=review_cost, amounts=frame["amount_inr"].to_numpy(),
        )
        if baseline_metrics:
            add_lift(metrics, baseline_metrics)
        return metrics

    metrics_unseen = _held(unseen_test)
    metrics_composition = _held(comp_test)
    if baseline_metrics:
        add_lift(metrics_seen, baseline_metrics)

    instance_recall, per_vector, missed_instances = instance_detection(
        y_seen, fitted.scores_test, seen_test["instance_id"].to_numpy(),
        seen_test["vector_id"].to_numpy(), threshold,
    )

    unseen_recall = None
    unseen_per_vector: list[dict[str, Any]] = []
    if not unseen_test.empty and unseen_test["is_fraud"].sum() > 0:
        unseen_scores = _score(fitted.model, unseen_test, columns)
        unseen_recall, unseen_per_vector, _ = instance_detection(
            unseen_test["is_fraud"].to_numpy(), unseen_scores,
            unseen_test["instance_id"].to_numpy(), unseen_test["vector_id"].to_numpy(),
            threshold,
        )
        for row in unseen_per_vector:
            row["holdout"] = "family"

    # Misses: one representative row per instance that never raised an alert, carrying the
    # SHAP contributions the strategist reads to decide what to attack next.
    missed_set = set(missed_instances)
    instances = seen_test["instance_id"].to_numpy()
    representative: dict[str, int] = {}
    for pos in np.flatnonzero(y_seen == 1):
        key = instances[pos]
        if key in missed_set:
            best = representative.get(key)
            if best is None or fitted.scores_test[pos] > fitted.scores_test[best]:
                representative[key] = int(pos)
    missed = np.array(sorted(representative.values()), dtype=int)
    shap_rows = top_contributions(fitted, seen_test, missed[:400])
    chain_by_vector = {v["vector_id"]: v["chain"] for v in vectors}

    misses = {
        "contract_version": "0.1.0",
        "run_id": f"{cfg['run']['run_id_prefix']}-g{generation}-{seed}",
        "generation": generation,
        "threshold": round(float(threshold), 6),
        "prevalence": round(float(y_seen.mean()), 6),
        "misses": [
            {
                "instance_id": str(seen_test.iloc[int(pos)]["instance_id"]),
                "vector_id": str(seen_test.iloc[int(pos)]["vector_id"]),
                "chain": chain_by_vector.get(str(seen_test.iloc[int(pos)]["vector_id"]), []),
                "primitives_present": chain_by_vector.get(
                    str(seen_test.iloc[int(pos)]["vector_id"]), []
                ),
                "score": round(float(fitted.scores_test[int(pos)]), 6),
                "level_scores": {"transaction": None, "session": None, "graph": None},
                "top_shap": shap,
                "evasion_hypothesis": None,
            }
            for pos, shap in zip(missed[:400], shap_rows)
        ],
        "per_vector": per_vector + unseen_per_vector,
    }

    return GenerationResult(
        generation=generation,
        metrics_seen=metrics_seen,
        metrics_unseen=metrics_unseen,
        metrics_composition=metrics_composition,
        instance_recall=instance_recall,
        unseen_recall=unseen_recall,
        per_vector=per_vector + unseen_per_vector,
        misses=misses,
        threshold=float(threshold),
        n_transactions=int(len(ledger.transactions)),
        n_fraud=int(ledger.transactions["is_fraud"].sum()),
        n_vectors=len(vectors),
        split_note=split.describe(),
    )
