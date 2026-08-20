"""Graph level of the detector.

PDF S6.1 and the build brief's first requirement: Mastercard's AI Garage doubled
compromised-card detection by combining generative AI with graph technology over
relationships between accounts, devices and cards. Mule layering is a topology, not a
row. Fan-out, short cycles, and accounts defined by what they never do, which is hold a
balance. No amount of tuning lets a row-level classifier represent that.

Everything here is causal and windowed. A feature computed over the whole graph would
let a transaction on day three see money that moved on day ninety, which is the graph
version of the leak the time split exists to prevent. Each transaction sees only the
subgraph that existed before it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GRAPH_FEATURES = [
    "g_fanin_24h",
    "g_fanout_24h",
    "g_degree_ratio",
    "g_passthrough_score",
    "g_residence_seconds",
    "g_in_short_cycle",
    "g_shared_device_degree",
    "g_counterparty_age_days",
    "g_beneficiary_novelty",
]


def _windowed_degree(
    keys: np.ndarray, times_ns: np.ndarray, window_ns: int
) -> np.ndarray:
    """Count of prior edges per account within a trailing window.

    Rows must be time-sorted. Strictly backward-looking: an edge never counts itself.
    """
    out = np.zeros(len(times_ns), dtype=np.float32)
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    if len(sorted_keys) == 0:
        return out
    boundaries = np.flatnonzero(np.diff(sorted_keys)) + 1
    for chunk in np.split(order, boundaries):
        t = times_ns[chunk]
        left = np.searchsorted(t, t - window_ns, side="left")
        out[chunk] = np.arange(len(chunk)) - left
    return out


def _windowed_sum(
    keys: np.ndarray, times_ns: np.ndarray, values: np.ndarray, window_ns: int
) -> np.ndarray:
    out = np.zeros(len(times_ns), dtype=np.float64)
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    if len(sorted_keys) == 0:
        return out
    boundaries = np.flatnonzero(np.diff(sorted_keys)) + 1
    for chunk in np.split(order, boundaries):
        t = times_ns[chunk]
        v = values[chunk].astype(np.float64)
        cum = np.concatenate([[0.0], np.cumsum(v)])
        left = np.searchsorted(t, t - window_ns, side="left")
        idx = np.arange(len(chunk))
        out[chunk] = cum[idx] - cum[left]
    return out


def account_graph_state(edges: pd.DataFrame, window_hours: int = 24) -> pd.DataFrame:
    """Per-edge, causal view of each account's local topology.

    Returned frame is indexed like ``edges`` and carries, for the SOURCE account of each
    edge, what the graph looked like immediately before that edge existed.
    """
    e = edges.sort_values("timestamp", kind="stable").reset_index(drop=True)
    window_ns = window_hours * 3_600 * 1_000_000_000
    times = pd.to_datetime(e["timestamp"], utc=True).astype("int64").to_numpy()

    src = e["source_account"].astype("category")
    tgt = e["target_account"].astype("category")
    amounts = e["amount_inr"].to_numpy(dtype=float)
    is_transfer = (e["edge_type"] == "transfer").to_numpy()

    # Money in and money out, per account, in the trailing window. A mule is the account
    # where these two are near-equal and neither is zero.
    out_codes = src.cat.codes.to_numpy()
    in_codes = tgt.cat.codes.to_numpy()

    fanout = _windowed_degree(out_codes, times, window_ns)
    money_out = _windowed_sum(out_codes, times, amounts * is_transfer, window_ns)

    # Inbound needs the same treatment keyed on the target, then read back onto the row
    # whose source is that account. Build a lookup of (account, time) -> inbound state.
    inbound_frame = pd.DataFrame({
        "account": tgt.astype(str).to_numpy(),
        "t": times,
        "amount": amounts * is_transfer,
    }).sort_values("t", kind="stable")
    in_codes_sorted = inbound_frame["account"].astype("category").cat.codes.to_numpy()
    in_times = inbound_frame["t"].to_numpy()
    fanin_sorted = _windowed_degree(in_codes_sorted, in_times, window_ns)
    money_in_sorted = _windowed_sum(
        in_codes_sorted, in_times, inbound_frame["amount"].to_numpy(), window_ns
    )
    inbound_frame = inbound_frame.assign(fanin=fanin_sorted, money_in=money_in_sorted)

    # For each edge, the source account's inbound state as of just before this edge.
    # merge_asof is exactly "last value at or before, per key", which is what a causal
    # graph feature is. The per-row Python loop this replaces was the reason a full-scale
    # run took forty minutes.
    inbound_state = (
        inbound_frame.rename(columns={"account": "_acct"})
        .sort_values("t", kind="stable")
        .reset_index(drop=True)
    )
    probe = pd.DataFrame({"_acct": src.astype(str).to_numpy(), "t": times}).reset_index()
    probe = probe.sort_values("t", kind="stable")

    # merge_asof consumes the right frame's key, so the matched edge's own timestamp has
    # to be carried across as a separate column or residence time silently becomes zero.
    inbound_state = inbound_state.assign(t_in=inbound_state["t"])
    joined = pd.merge_asof(
        probe,
        inbound_state[["_acct", "t", "t_in", "fanin", "money_in", "amount"]],
        on="t",
        by="_acct",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("index")

    fanin = np.nan_to_num(joined["fanin"].to_numpy(dtype=float), nan=-1.0) + 1.0
    fanin = np.where(fanin < 0.5, 0.0, fanin).astype(np.float32)
    money_in = np.nan_to_num(
        joined["money_in"].to_numpy(dtype=float) + joined["amount"].to_numpy(dtype=float), nan=0.0
    )
    last_in_time = joined["t_in"].to_numpy(dtype=float)

    total = money_in + money_out
    with np.errstate(invalid="ignore", divide="ignore"):
        passthrough = np.where(
            (total > 0) & (money_in > 0) & (money_out > 0),
            1 - np.abs(money_in - money_out) / total,
            0.0,
        )
        degree_ratio = np.where(fanout > 0, fanin / fanout, 0.0)

    # Residence time: how long the money sat before moving on. Near zero is the mule
    # signature - the account never holds a balance.
    residence = np.where(
        np.isnan(last_in_time), np.nan, (times - last_in_time) / 1e9
    )

    shared_device = (
        e.assign(_sd=(e["edge_type"] == "shared_device").astype(float))
        .groupby("source_account", sort=False)["_sd"]
        .cumsum()
        .to_numpy()
    )

    return pd.DataFrame({
        "source_account": e["source_account"].to_numpy(),
        "target_account": e["target_account"].to_numpy(),
        "timestamp": pd.to_datetime(e["timestamp"], utc=True),
        "g_fanin_24h": fanin,
        "g_fanout_24h": fanout,
        "g_degree_ratio": degree_ratio.astype(np.float32),
        "g_passthrough_score": passthrough.astype(np.float32),
        "g_residence_seconds": residence.astype(np.float32),
        "g_shared_device_degree": shared_device.astype(np.float32),
    })


def short_cycle_membership(
    edges: pd.DataFrame, max_length: int = 4, max_nnz: int = 40_000_000
) -> set[str]:
    """Accounts sitting on a short closed loop in the transfer graph.

    Layering closes a loop: value leaves an account, moves through a handful of others,
    and comes back. That is the topological signature worth a feature.

    Computed from powers of the sparse adjacency matrix rather than by enumerating
    cycles. ``networkx.simple_cycles`` took 9 seconds on twelve thousand edges and did not
    finish at all on the 384k edges a two-million-row ledger produces, because cycle
    enumeration is exponential in the worst case and the transfer graph is exactly the
    dense-in-places shape that triggers it. The diagonal of A^k counts closed walks of
    length k through each node, and three sparse multiplies give the same membership
    answer in well under a second.

    The difference between a closed walk and a simple cycle is that a walk may revisit a
    node. At lengths two to four on a sparse financial graph that distinction almost never
    bites, and where it does the account is on a tight loop either way, which is what the
    feature is for. Stated here rather than left as a silent approximation.
    """
    from scipy import sparse

    transfers = edges[edges["edge_type"] == "transfer"]
    if transfers.empty:
        return set()

    nodes = pd.Index(
        pd.unique(pd.concat([transfers["source_account"], transfers["target_account"]]))
    )
    rows = nodes.get_indexer(transfers["source_account"])
    cols = nodes.get_indexer(transfers["target_account"])
    n = len(nodes)

    adjacency = sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n)
    )
    adjacency.data[:] = 1

    on_cycle_mask = np.zeros(n, dtype=bool)
    power = adjacency
    for length in range(2, max_length + 1):
        power = power @ adjacency
        if power.nnz > max_nnz:
            # Refuse to densify. A shorter bound still identifies tight loops, and a
            # feature that occasionally exhausts memory is worse than a slightly
            # coarser one.
            break
        on_cycle_mask |= power.diagonal() > 0
        power.data[:] = np.minimum(power.data, 1)

    return set(nodes[on_cycle_mask])


def build_graph_features(ledger, transactions: pd.DataFrame) -> pd.DataFrame:  # noqa: ANN001
    """Graph features joined onto transactions, one row per transaction.

    Each transaction picks up the state of its account's local topology as of the last
    edge before it. Transactions on accounts with no graph history get zeros rather than
    nulls for the count features, because "no edges yet" is genuinely zero rather than
    unknown, and NaN for residence, because "never received" is not a duration.
    """
    edges = ledger.graph_edges
    if edges.empty:
        return pd.DataFrame(
            {c: np.zeros(len(transactions), dtype=np.float32) for c in GRAPH_FEATURES},
            index=transactions.index,
        )

    state = account_graph_state(edges)
    on_cycle = short_cycle_membership(edges)

    accounts = ledger.accounts.set_index("account_id")
    txn_times = pd.to_datetime(transactions["timestamp"], utc=True).astype("int64").to_numpy()
    txn_accounts = transactions["account_id"].to_numpy()

    out = pd.DataFrame(index=transactions.index)
    for column in GRAPH_FEATURES:
        out[column] = np.float32(0.0)
    out["g_residence_seconds"] = np.nan

    carried = [
        "g_fanin_24h",
        "g_fanout_24h",
        "g_degree_ratio",
        "g_passthrough_score",
        "g_residence_seconds",
        "g_shared_device_degree",
    ]

    # Same join, same reason: the last graph state for this account strictly before this
    # transaction. Nothing here may see an edge that had not happened yet.
    left = pd.DataFrame({
        "_acct": txn_accounts,
        "t": txn_times,
        "_row": np.arange(len(transactions)),
    }).sort_values("t", kind="stable")

    right = (
        state.assign(_acct=state["source_account"], t=state["timestamp"].astype("int64"))
        .sort_values("t", kind="stable")[["_acct", "t", *carried]]
        .reset_index(drop=True)
    )

    joined = pd.merge_asof(
        left, right, on="t", by="_acct", direction="backward", allow_exact_matches=True
    ).sort_values("_row")

    for column in carried:
        values = joined[column].to_numpy(dtype=float)
        out[column] = (
            values if column == "g_residence_seconds" else np.nan_to_num(values, nan=0.0)
        ).astype(np.float32)

    out["g_in_short_cycle"] = np.isin(txn_accounts, list(on_cycle)).astype(np.float32)

    opened = pd.to_datetime(transactions["account_id"].map(accounts["opened_at"]), utc=True)
    out["g_counterparty_age_days"] = (
        (pd.to_datetime(transactions["timestamp"], utc=True) - opened).dt.total_seconds() / 86400
    ).astype(np.float32)

    # Beneficiary novelty: has this account sent to anyone at all before now? A first
    # outbound transfer to a brand new payee is the shape of authorised push payment.
    first_out = state.groupby("source_account")["timestamp"].min()
    first_out_ns = transactions["account_id"].map(first_out)
    out["g_beneficiary_novelty"] = (
        pd.to_datetime(first_out_ns, utc=True).astype("int64").to_numpy() >= txn_times
    ).astype(np.float32)

    return out
