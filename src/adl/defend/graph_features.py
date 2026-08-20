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
    inbound_lookup = inbound_frame.sort_values(["account", "t"], kind="stable")
    src_names = src.astype(str).to_numpy()
    fanin = np.zeros(len(e), dtype=np.float32)
    money_in = np.zeros(len(e), dtype=np.float64)
    last_in_time = np.full(len(e), np.nan)

    grouped = {name: group for name, group in inbound_lookup.groupby("account", sort=False)}
    for i in range(len(e)):
        group = grouped.get(src_names[i])
        if group is None:
            continue
        pos = np.searchsorted(group["t"].to_numpy(), times[i], side="left") - 1
        if pos >= 0:
            fanin[i] = group["fanin"].to_numpy()[pos] + 1
            money_in[i] = group["money_in"].to_numpy()[pos] + group["amount"].to_numpy()[pos]
            last_in_time[i] = group["t"].to_numpy()[pos]

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


def short_cycle_membership(edges: pd.DataFrame, max_length: int = 4) -> set[str]:
    """Accounts sitting on a cycle of at most ``max_length`` transfer hops.

    Layering closes a loop: value leaves an account, travels through a handful of others,
    and comes back. Short cycles are the cheapest topological expression of that, and
    unlike a full community detection pass they are computable in one sweep.
    """
    import networkx as nx

    transfers = edges[edges["edge_type"] == "transfer"]
    graph = nx.DiGraph()
    graph.add_edges_from(zip(transfers["source_account"], transfers["target_account"]))

    on_cycle: set[str] = set()
    try:
        for cycle in nx.simple_cycles(graph, length_bound=max_length):
            on_cycle.update(cycle)
    except TypeError:
        # networkx below 3.1 has no length_bound; fall back to bounded search
        for cycle in nx.simple_cycles(graph):
            if len(cycle) <= max_length:
                on_cycle.update(cycle)
    return on_cycle


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

    by_account = {name: group for name, group in state.groupby("source_account", sort=False)}
    state_times = {
        name: group["timestamp"].astype("int64").to_numpy() for name, group in by_account.items()
    }

    carried = ["g_fanin_24h", "g_fanout_24h", "g_degree_ratio", "g_passthrough_score",
               "g_residence_seconds", "g_shared_device_degree"]
    values = {c: np.zeros(len(transactions), dtype=np.float32) for c in carried}
    values["g_residence_seconds"][:] = np.nan

    for i in range(len(transactions)):
        group = by_account.get(txn_accounts[i])
        if group is None:
            continue
        pos = np.searchsorted(state_times[txn_accounts[i]], txn_times[i], side="right") - 1
        if pos < 0:
            continue
        row = group.iloc[pos]
        for c in carried:
            values[c][i] = row[c]

    for c in carried:
        out[c] = values[c]

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
