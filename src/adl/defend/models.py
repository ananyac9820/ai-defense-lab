"""Detector models.

Two things live here: the committed baseline, and the levelled model that has to beat it.

The baseline is a logistic regression on plain transaction fields. It is deliberately a
reasonable model rather than a strawman - NOTES.md D-002 - because the lift number is
only as credible as what it is measured against, and a weak baseline is a self-inflicted
wound in front of judges who know the domain.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class Fitted:
    name: str
    columns: list[str]
    scores_train: np.ndarray
    scores_test: np.ndarray
    model: Any
    latency_p50_ms: float | None = None
    latency_p99_ms: float | None = None


def _matrix(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    return frame.reindex(columns=columns).to_numpy(dtype=np.float64, na_value=np.nan)


def fit_baseline(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]) -> Fitted:
    x_train = np.nan_to_num(_matrix(train, columns), nan=0.0)
    x_test = np.nan_to_num(_matrix(test, columns), nan=0.0)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0),
    )
    model.fit(x_train, train["is_fraud"].to_numpy())
    return Fitted(
        name="logistic_regression_transaction_only",
        columns=columns,
        scores_train=model.predict_proba(x_train)[:, 1],
        scores_test=model.predict_proba(x_test)[:, 1],
        model=model,
    )


def fit_gbm(
    train: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
    name: str,
    *,
    seed: int = 0,
    measure_latency: bool = False,
) -> Fitted:
    import lightgbm as lgb

    x_train, x_test = _matrix(train, columns), _matrix(test, columns)
    y_train = train["is_fraud"].to_numpy()

    # Class weighting during training, evaluation on the unmodified distribution
    # (PDF S5.2). No resampling of the test set, ever.
    positives = max(int(y_train.sum()), 1)
    model = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.06,
        num_leaves=48,
        min_child_samples=40,
        subsample=0.85,
        subsample_freq=1,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        scale_pos_weight=float(len(y_train) - positives) / positives,
        random_state=seed,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(x_train, y_train)

    p50 = p99 = None
    if measure_latency:
        # Payment authorisation budgets are measured in tens of milliseconds, so the
        # number that matters is single-transaction scoring, not batch throughput.
        sample = x_test[: min(300, len(x_test))]
        timings = []
        for row in sample:
            started = time.perf_counter()
            model.predict_proba(row.reshape(1, -1))
            timings.append((time.perf_counter() - started) * 1000)
        p50 = round(float(np.percentile(timings, 50)), 3)
        p99 = round(float(np.percentile(timings, 99)), 3)

    return Fitted(
        name=name,
        columns=columns,
        scores_train=model.predict_proba(x_train)[:, 1],
        scores_test=model.predict_proba(x_test)[:, 1],
        model=model,
        latency_p50_ms=p50,
        latency_p99_ms=p99,
    )


def top_contributions(
    fitted: Fitted, frame: pd.DataFrame, row_positions: np.ndarray, k: int = 6
) -> list[list[dict[str, Any]]]:
    """Signed feature contributions for selected rows.

    LightGBM's ``pred_contrib`` returns exact tree SHAP values, so this is the real thing
    rather than a proxy - and it is what the red-team strategist reads to work out which
    feature the detector is leaning on (PDF S7.3).
    """
    if not row_positions.size:
        return []
    matrix = _matrix(frame.iloc[row_positions], fitted.columns)
    contributions = fitted.model.predict(matrix, raw_score=False, pred_contrib=True)
    contributions = np.asarray(contributions)[:, :-1]  # last column is the expected value

    out: list[list[dict[str, Any]]] = []
    for row in contributions:
        order = np.argsort(np.abs(row))[::-1][:k]
        out.append([
            {"feature": fitted.columns[int(i)], "value": round(float(row[int(i)]), 4)}
            for i in order
        ])
    return out


TUNING_GRID = [
    {"max_depth": 4, "learning_rate": 0.10, "n_estimators": 300, "min_child_weight": 5},
    {"max_depth": 6, "learning_rate": 0.06, "n_estimators": 500, "min_child_weight": 3},
    {"max_depth": 6, "learning_rate": 0.10, "n_estimators": 300, "min_child_weight": 10},
    {"max_depth": 8, "learning_rate": 0.05, "n_estimators": 600, "min_child_weight": 5},
    {"max_depth": 8, "learning_rate": 0.10, "n_estimators": 400, "min_child_weight": 1},
    {"max_depth": 10, "learning_rate": 0.05, "n_estimators": 500, "min_child_weight": 3},
]


def fit_tuned_baseline(
    train: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
    *,
    seed: int = 0,
    validation_fraction: float = 0.2,
) -> tuple[Fitted, dict[str, Any]]:
    """A gradient-boosted baseline on transaction-level features, actually tuned.

    A logistic regression at 0.079 precision is a floor, not a baseline. Quoting lift
    against it produces a number in the high hundreds of percent that collapses the moment
    a judge asks what the baseline was. This is the honest comparator: the same model class
    as the full detector, tuned, given every transaction-level feature, and denied only the
    session and graph evidence that the architecture argument is about.

    Selection runs on a time-ordered tail of the TRAINING window. Tuning against test would
    be a quieter version of the leakage the split exists to prevent.
    """
    import xgboost as xgb

    ordered = train.sort_values("timestamp", kind="stable")
    cut = int(len(ordered) * (1 - validation_fraction))
    fit_part, validation = ordered.iloc[:cut], ordered.iloc[cut:]

    x_fit = _matrix(fit_part, columns)
    y_fit = fit_part["is_fraud"].to_numpy()
    x_val = _matrix(validation, columns)
    y_val = validation["is_fraud"].to_numpy()

    positives = max(int(y_fit.sum()), 1)
    weight = float(len(y_fit) - positives) / positives

    best_config: dict[str, Any] | None = None
    best_score = -np.inf
    trials: list[dict[str, Any]] = []

    for config in TUNING_GRID:
        model = xgb.XGBClassifier(
            **config,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.0,
            scale_pos_weight=weight,
            random_state=seed,
            n_jobs=-1,
            eval_metric="aucpr",
            tree_method="hist",
        )
        model.fit(x_fit, y_fit)
        score = (
            average_precision_score(y_val, model.predict_proba(x_val)[:, 1])
            if len(np.unique(y_val)) > 1
            else 0.0
        )
        trials.append({**config, "val_auc_pr": round(float(score), 4)})
        if score > best_score:
            best_score, best_config = float(score), config

    assert best_config is not None
    x_train, x_test = _matrix(train, columns), _matrix(test, columns)
    y_train = train["is_fraud"].to_numpy()
    final_positives = max(int(y_train.sum()), 1)
    final = xgb.XGBClassifier(
        **best_config,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        scale_pos_weight=float(len(y_train) - final_positives) / final_positives,
        random_state=seed,
        n_jobs=-1,
        eval_metric="aucpr",
        tree_method="hist",
    )
    final.fit(x_train, y_train)

    fitted = Fitted(
        name="xgboost_tuned_transaction_only",
        columns=columns,
        scores_train=final.predict_proba(x_train)[:, 1],
        scores_test=final.predict_proba(x_test)[:, 1],
        model=final,
    )
    return fitted, {
        "selected": best_config,
        "validation_auc_pr": round(best_score, 4),
        "trials": trials,
    }
