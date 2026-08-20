"""Metrics, in the form the contract requires.

Two rules, both from PDF S6.4 and NOTES.md D-002:

  * Prevalence is stated next to every metric. It is a required field, so a metrics
    object cannot be constructed without it.
  * Nothing is reported bare. Absolute values go in the tables; the headline is
    percentage lift over the committed baseline.

AUC-PR is the honest headline at low prevalence. AUC-ROC flatters imbalanced problems and
is reported alongside rather than instead.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    precision_recall_fscore_support,
    roc_auc_score,
)


def compute_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    *,
    review_cost_inr: float,
    amounts: np.ndarray | None = None,
    latency_p50_ms: float | None = None,
    latency_p99_ms: float | None = None,
) -> dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    predicted = (scores >= threshold).astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, predicted, average="binary", zero_division=0
    )
    auc_roc = roc_auc_score(y_true, scores) if len(np.unique(y_true)) > 1 else float("nan")
    auc_pr = average_precision_score(y_true, scores) if len(np.unique(y_true)) > 1 else float("nan")

    net_value = None
    if amounts is not None:
        amounts = np.asarray(amounts, dtype=float)
        caught = float(amounts[(y_true == 1) & (predicted == 1)].sum())
        false_positives = int(((y_true == 0) & (predicted == 1)).sum())
        net_value = caught - false_positives * review_cost_inr

    return {
        "prevalence": float(y_true.mean()),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "auc_roc": round(float(auc_roc), 4),
        "auc_pr": round(float(auc_pr), 4),
        "alert_rate": round(float(predicted.mean()), 5),
        "net_value_protected_inr": None if net_value is None else round(net_value, 2),
        "scoring_latency_p50_ms": latency_p50_ms,
        "scoring_latency_p99_ms": latency_p99_ms,
        "lift_over_baseline": None,
    }


def add_lift(metrics: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Attach percentage lift over the baseline for the metrics a headline can use."""
    lift: dict[str, float] = {}
    for key in ("auc_pr", "recall", "precision", "f1", "net_value_protected_inr"):
        ours, base = metrics.get(key), baseline.get(key)
        if ours is None or base in (None, 0):
            continue
        lift[key] = round((ours - base) / abs(base) * 100, 1)
    metrics["lift_over_baseline"] = lift
    return metrics


def choose_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    amounts: np.ndarray,
    review_cost_inr: float,
) -> tuple[float, float]:
    """Pick the threshold that maximises net value protected.

    PDF S6.4: this converts threshold selection from an arbitrary choice into an economic
    optimisation. Fitted on the TRAINING split only - choosing it on test would be a
    quieter form of the same leakage the split is designed to prevent.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    amounts = np.asarray(amounts, dtype=float)

    candidates = np.unique(np.quantile(scores, np.linspace(0.50, 0.9999, 220)))
    best_threshold, best_value = 0.5, -np.inf
    for threshold in candidates:
        predicted = scores >= threshold
        value = (
            amounts[(y_true == 1) & predicted].sum()
            - int(((y_true == 0) & predicted).sum()) * review_cost_inr
        )
        if value > best_value:
            best_threshold, best_value = float(threshold), float(value)
    return best_threshold, best_value


def per_vector_row_detection(
    y_true: np.ndarray, scores: np.ndarray, vector_ids: np.ndarray, threshold: float
) -> list[dict[str, Any]]:
    """Row-weighted detection per vector. Reported alongside the instance figure, never
    instead of it."""
    y_true = np.asarray(y_true).astype(int)
    detected = np.asarray(scores, dtype=float) >= threshold
    rows: list[dict[str, Any]] = []
    for vector in sorted({v for v, y in zip(vector_ids, y_true) if y == 1 and v is not None}):
        mask = (vector_ids == vector) & (y_true == 1)
        n = int(mask.sum())
        hit = int(detected[mask].sum())
        rows.append({
            "vector_id": str(vector),
            "n_instances": n,
            "n_detected": hit,
            "detection_rate": round(hit / n, 4) if n else 0.0,
            "holdout": "none",
        })
    return rows


def instance_detection(
    y_true: np.ndarray,
    scores: np.ndarray,
    instance_ids: np.ndarray,
    vector_ids: np.ndarray,
    threshold: float,
) -> tuple[float, list[dict[str, Any]], list[str]]:
    """Detection scored per attack instance rather than per row.

    Row-weighted recall is the wrong unit for this problem and flatters it badly. A card
    testing sweep emits twenty rows and counts twenty times; an authorised push payment
    emits one and counts once. The row metric therefore reports mostly how well the
    detector finds the noisiest vector, and a fraud team catching nineteen of twenty
    probes after the money has gone has caught nothing.

    An instance counts as detected when ANY of its rows scores at or above the operating
    threshold, which is what an alert queue actually does.

    Returns the overall instance recall, per-vector rows, and the ids of missed
    instances.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    flagged = scores >= threshold

    best: dict[str, float] = {}
    vector_of: dict[str, str] = {}
    for i in np.flatnonzero(y_true == 1):
        instance = instance_ids[i]
        if instance is None or (isinstance(instance, float) and np.isnan(instance)):
            continue
        instance = str(instance)
        best[instance] = max(best.get(instance, 0.0), float(scores[i]))
        vector_of.setdefault(instance, str(vector_ids[i]))

    if not best:
        return 0.0, [], []

    detected = {i: v >= threshold for i, v in best.items()}
    missed = sorted(i for i, hit in detected.items() if not hit)

    rows: list[dict[str, Any]] = []
    for vector in sorted(set(vector_of.values())):
        members = [i for i, v in vector_of.items() if v == vector]
        hit = sum(detected[i] for i in members)
        rows.append({
            "vector_id": vector,
            "n_instances": len(members),
            "n_detected": int(hit),
            "detection_rate": round(hit / len(members), 4),
            "holdout": "none",
        })

    overall = sum(detected.values()) / len(detected)
    del flagged
    return float(overall), rows, missed


def format_table(name: str, metrics: dict[str, Any]) -> str:
    lift = metrics.get("lift_over_baseline") or {}
    lift_text = (
        "  ".join(f"{k}+{v:.0f}%" if v >= 0 else f"{k}{v:.0f}%" for k, v in lift.items())
        or "baseline"
    )
    return (
        f"{name:<34s} P {metrics['precision']:.3f}  R {metrics['recall']:.3f}  "
        f"F1 {metrics['f1']:.3f}  AUC-PR {metrics['auc_pr']:.3f}  "
        f"alert {metrics['alert_rate']:.4%}  @prev {metrics['prevalence']:.3%}\n"
        f"{'':34s} {lift_text}"
    )
