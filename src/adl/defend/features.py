"""Feature construction, level by level.

PDF S6.1: several of the strongest chains are invisible in a single transaction. Card
testing is a rhythm across a session. Mule layering is a topology. A row-level classifier
cannot represent either, so the levels are separate feature blocks and the lift each one
contributes is reported as an ablation.

Everything here is causal. Account statistics are expanding windows over that account's
own past, never full-sample aggregates - a mean computed over the whole dataset leaks the
future into the training rows and inflates every number downstream.

Levels:
  transaction  amount, hour, channel, MCC, device match, geography delta
  session      cadence, paste ratio, dwell, corrections, declines   <- signals A and B
  graph        degree ratios, pass-through, residence, cycles       <- adl.defend.graph_features
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRANSACTION_FEATURES = [
    "amount_inr",
    "log_amount",
    "hour_of_day",
    "day_of_week",
    "channel_code",
    "mcc_code",
    "auth_declined",
    "geography_matches_home",
    "account_age_days",
    "device_age_days",
]

SESSION_FEATURES = [
    "sess_n_events",
    "sess_duration_ms",
    "sess_cadence_cv",
    "sess_cadence_entropy",
    "sess_paste_ratio_payee",
    "sess_confirm_dwell_ms",
    "sess_correction_rate",
    "sess_n_declines",
    "sess_max_gap_ms",
]

VELOCITY_FEATURES = [
    "acct_txn_count_24h",
    "dev_txn_count_1h",
    "dev_decline_ratio_1h",
    "amount_z_account",
]

# Signal A is the coercion signature; signal B is cadence regularity. Named here so the
# ablation can drop exactly these and nothing else (NOTES.md D-004, mitigation 2).
COERCION_SIGNAL_FEATURES = [
    "sess_paste_ratio_payee",
    "sess_confirm_dwell_ms",
    "sess_correction_rate",
]
CADENCE_SIGNAL_FEATURES = [
    "sess_cadence_cv",
    "sess_cadence_entropy",
]


def _rolling_count(group_keys: np.ndarray, times_ns: np.ndarray, window_ns: int) -> np.ndarray:
    """Count of prior rows within `window` for each row, per group.

    Rows must already be in time order. Counts are strictly backward-looking; the row
    itself is excluded.
    """
    out = np.zeros(len(times_ns), dtype=np.float32)
    order = np.argsort(group_keys, kind="stable")
    grouped_keys = group_keys[order]
    boundaries = np.flatnonzero(np.diff(grouped_keys)) + 1
    for chunk in np.split(order, boundaries):
        t = times_ns[chunk]
        left = np.searchsorted(t, t - window_ns, side="left")
        out[chunk] = np.arange(len(chunk)) - left
    return out


def _rolling_declined_ratio(
    group_keys: np.ndarray, times_ns: np.ndarray, declined: np.ndarray, window_ns: int
) -> np.ndarray:
    out = np.zeros(len(times_ns), dtype=np.float32)
    order = np.argsort(group_keys, kind="stable")
    grouped_keys = group_keys[order]
    boundaries = np.flatnonzero(np.diff(grouped_keys)) + 1
    for chunk in np.split(order, boundaries):
        t = times_ns[chunk]
        d = declined[chunk].astype(np.float32)
        cum = np.concatenate([[0.0], np.cumsum(d)])
        left = np.searchsorted(t, t - window_ns, side="left")
        idx = np.arange(len(chunk))
        n = idx - left
        s = cum[idx] - cum[left]
        out[chunk] = np.where(n > 0, s / np.maximum(n, 1), 0.0)
    return out


def session_features(sessions: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Per-session aggregates, including both behavioural signals.

    Signal B (cadence regularity) is the coefficient of variation and the entropy of the
    inter-event interval series. Humans jitter; scripts and agents do not. Signal A (the
    coercion signature) is the paste ratio on payee fields, the dwell before confirming,
    and the correction rate.
    """
    ev = events.sort_values(["session_id", "event_order"], kind="stable")
    gaps = ev.groupby("session_id", sort=False)["t_offset_ms"].diff()

    # Everything below is one pass of C-level aggregation. A groupby.apply calling a
    # Python function per session took minutes on a few hundred thousand sessions and
    # would have been the wall at full scale.
    positive = gaps.where(gaps > 0)
    ev = ev.assign(
        _gap=gaps,
        _gap2=gaps.pow(2),
        _pos=positive,
        _plogp=positive * np.log(positive),
    )

    grouped = ev.groupby("session_id", sort=False)
    agg = grouped.agg(
        sess_n_events=("t_offset_ms", "size"),
        sess_duration_ms=("t_offset_ms", "max"),
        sess_max_gap_ms=("_gap", "max"),
        sess_correction_rate=("corrections", "mean"),
        _gap_sum=("_gap", "sum"),
        _gap_sq=("_gap2", "sum"),
        _gap_n=("_gap", "count"),
        _pos_sum=("_pos", "sum"),
        _plogp_sum=("_plogp", "sum"),
        _pos_n=("_pos", "count"),
    )

    # Signal B, part one: coefficient of variation of the inter-event intervals.
    n = agg["_gap_n"].to_numpy(dtype=float)
    total = agg["_gap_sum"].to_numpy(dtype=float)
    total_sq = agg["_gap_sq"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(n > 0, total / n, np.nan)
        variance = np.where(n > 1, (total_sq - n * mean**2) / (n - 1), np.nan)
        agg["sess_cadence_cv"] = np.where(
            (n > 1) & (mean > 0), np.sqrt(np.maximum(variance, 0)) / mean, np.nan
        )

        # Signal B, part two: normalised entropy of the interval series. Writing
        # p = g / S gives -sum(p log p) = log S - (sum g log g) / S, so the whole thing
        # comes out of two sums rather than a Python loop per session.
        s_sum = agg["_pos_sum"].to_numpy(dtype=float)
        q_sum = agg["_plogp_sum"].to_numpy(dtype=float)
        k = agg["_pos_n"].to_numpy(dtype=float)
        entropy = np.log(s_sum) - q_sum / s_sum
        agg["sess_cadence_entropy"] = np.where(
            (k > 1) & (s_sum > 0), entropy / np.log(k), np.nan
        )

    payee = ev[ev["field"] == "payee_id"]
    agg["sess_paste_ratio_payee"] = (
        payee.assign(_p=(payee["input_method"] == "paste").astype(float))
        .groupby("session_id", sort=False)["_p"].mean()
    )
    confirm = ev[ev["type"] == "confirm"]
    agg["sess_confirm_dwell_ms"] = confirm.groupby("session_id", sort=False)["dwell_ms"].max()
    declines = ev[ev["type"] == "decline_shown"]
    agg["sess_n_declines"] = declines.groupby("session_id", sort=False).size()

    agg = agg.reindex(columns=SESSION_FEATURES).fillna({"sess_n_declines": 0})
    return agg.reset_index().merge(
        sessions[["session_id", "account_id"]], on="session_id", how="left"
    )


def build_features(ledger) -> pd.DataFrame:  # noqa: ANN001 - Ledger, avoiding a cycle
    """Join every level into one frame, one row per transaction."""
    txns = ledger.transactions.sort_values("timestamp", kind="stable").reset_index(drop=True)
    accounts = ledger.accounts.set_index("account_id")
    devices = ledger.devices.set_index("device_id")

    ts = pd.to_datetime(txns["timestamp"], utc=True)
    out = pd.DataFrame(index=txns.index)
    out["transaction_id"] = txns["transaction_id"]
    out["account_id"] = txns["account_id"]
    out["timestamp"] = ts
    out["is_fraud"] = txns["is_fraud"].astype(int)
    out["vector_id"] = txns["vector_id"]
    # One execution of a chain. Carried through so detection can be scored per incident
    # and not only per row - see adl.evaluate.metrics.instance_detection.
    out["instance_id"] = txns["instance_id"]

    # --- transaction level -------------------------------------------------
    out["amount_inr"] = txns["amount_inr"].astype(np.float32)
    out["log_amount"] = np.log1p(txns["amount_inr"]).astype(np.float32)
    out["hour_of_day"] = ts.dt.hour.astype(np.float32) + ts.dt.minute.astype(np.float32) / 60
    out["day_of_week"] = ts.dt.dayofweek.astype(np.float32)
    out["channel_code"] = txns["channel"].astype("category").cat.codes.astype(np.float32)
    out["mcc_code"] = txns["mcc"].astype("category").cat.codes.astype(np.float32)
    out["auth_declined"] = (txns["auth_result"] == "declined").astype(np.float32)

    home = txns["account_id"].map(accounts["home_geo"])
    out["geography_matches_home"] = (txns["geography"] == home).astype(np.float32)

    opened = pd.to_datetime(txns["account_id"].map(accounts["opened_at"]), utc=True)
    first_seen = pd.to_datetime(txns["device_id"].map(devices["first_seen"]), utc=True)
    out["account_age_days"] = ((ts - opened).dt.total_seconds() / 86400).astype(np.float32)
    out["device_age_days"] = ((ts - first_seen).dt.total_seconds() / 86400).astype(np.float32)

    # --- velocity ----------------------------------------------------------
    times_ns = ts.astype("int64").to_numpy()
    acct = txns["account_id"].astype("category").cat.codes.to_numpy()
    dev = txns["device_id"].astype("category").cat.codes.to_numpy()
    declined = (txns["auth_result"] == "declined").to_numpy()

    out["acct_txn_count_24h"] = _rolling_count(acct, times_ns, 86_400 * 1_000_000_000)
    out["dev_txn_count_1h"] = _rolling_count(dev, times_ns, 3_600 * 1_000_000_000)
    out["dev_decline_ratio_1h"] = _rolling_declined_ratio(
        dev, times_ns, declined, 3_600 * 1_000_000_000
    )

    # Expanding, causal z-score of the amount against this account's own past. A
    # full-sample mean would leak the future into every training row.
    #
    # Computed from cumulative sums rather than groupby.transform with a lambda: the
    # lambda calls .expanding() once per account and was the second of two hot spots
    # that made a 300k-row run unfinishable.
    amounts = txns["amount_inr"].to_numpy(dtype=float)
    grouped_amounts = txns.groupby("account_id", sort=False)["amount_inr"]
    count_before = grouped_amounts.cumcount().to_numpy(dtype=float)
    sum_incl = grouped_amounts.cumsum().to_numpy(dtype=float)
    sumsq_incl = (
        txns.assign(_sq=amounts**2).groupby("account_id", sort=False)["_sq"].cumsum()
    ).to_numpy(dtype=float)

    sum_before = sum_incl - amounts
    sumsq_before = sumsq_incl - amounts**2
    with np.errstate(invalid="ignore", divide="ignore"):
        past_mean = np.where(count_before > 0, sum_before / count_before, np.nan)
        past_var = np.where(
            count_before > 1,
            (sumsq_before - count_before * past_mean**2) / (count_before - 1),
            np.nan,
        )
        past_std = np.sqrt(np.maximum(past_var, 0))
        z = (amounts - past_mean) / (past_std + 1.0)
    out["amount_z_account"] = np.nan_to_num(z, nan=0.0).astype(np.float32)

    # --- session level -----------------------------------------------------
    sess = session_features(ledger.sessions, ledger.session_events)
    out = out.join(
        txns[["session_id"]].join(sess.set_index("session_id"), on="session_id")[SESSION_FEATURES]
    )

    # --- graph level -------------------------------------------------------
    from .graph_features import build_graph_features

    out = out.join(build_graph_features(ledger, txns))
    return out


def feature_columns(levels: set[str], drop: list[str] | None = None) -> list[str]:
    from .graph_features import GRAPH_FEATURES

    cols: list[str] = []
    if "transaction" in levels:
        cols += TRANSACTION_FEATURES + VELOCITY_FEATURES
    if "session" in levels:
        cols += SESSION_FEATURES
    if "graph" in levels:
        cols += GRAPH_FEATURES
    for column in drop or []:
        if column in cols:
            cols.remove(column)
    return cols
