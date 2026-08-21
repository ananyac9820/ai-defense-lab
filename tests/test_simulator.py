"""Guards on the simulator's output.

The tests that matter here are not "does it run" but "is what it produces defensible":
realistic prevalence, overlapping behavioural distributions, instance identifiers that
make instance-level scoring possible, and joint structure rather than independent fields.
"""

from __future__ import annotations

import numpy as np
import pytest

from adl.common.contracts import load_schema, validation_errors
from adl.generate.simulator import simulate


@pytest.fixture(scope="module")
def ledger():
    return simulate(n_transactions=30_000, seed=11, n_accounts=4_000)


def test_prevalence_is_near_the_configured_base_rate(ledger) -> None:
    actual = ledger.transactions["is_fraud"].mean()
    assert 0.006 <= actual <= 0.016, f"prevalence {actual:.4%} is not near 1%"


def test_every_fraud_row_belongs_to_an_identified_instance(ledger) -> None:
    """misses.json references instance_id; the ledger has to be able to name it."""
    fraud = ledger.transactions[ledger.transactions["is_fraud"]]
    assert fraud["instance_id"].notna().all()
    assert fraud["instance_id"].str.match(r"^I\d{6}$").all()
    assert ledger.transactions.loc[~ledger.transactions["is_fraud"], "instance_id"].isna().all()


def test_no_single_vector_dominates_the_fraud_rows(ledger) -> None:
    """A vector supplying most of the fraudulent rows makes row-weighted recall a report
    on that one vector. Instance-level scoring is the real fix, but the row mix should
    still not be pathological."""
    share = ledger.transactions[ledger.transactions["is_fraud"]]["vector_id"].value_counts(
        normalize=True
    )
    assert share.iloc[0] < 0.62, f"top vector holds {share.iloc[0]:.0%} of fraud rows:\n{share}"


def test_every_authored_vector_produces_instances(ledger) -> None:
    """Every vector in attacks.json must actually emit, and the count is not hardcoded.

    This previously asserted a literal five and went stale the moment three vectors were
    added, which is how it stayed red on CI for three commits. The literal was also
    checking nothing useful. The bug it should have caught was the retired registry
    filter, which let three authored vectors be counted in the taxonomy, validated
    against the contract, and emit nothing whatsoever. Comparing against the authored set
    catches exactly that, and cannot go stale.
    """
    import json

    from adl.common.paths import FIXTURES_DIR

    authored = {
        v["vector_id"]
        for v in json.loads(
            (FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8")
        )["vectors"]
    }
    fraud = ledger.transactions[ledger.transactions["is_fraud"]]
    per_vector = fraud.groupby("vector_id")["instance_id"].nunique()

    silent = authored - set(per_vector.index)
    assert not silent, (
        f"authored but emitted nothing: {sorted(silent)}. A vector counted in the coverage "
        f"claim that produces no data inflates every number depending on it."
    )
    assert per_vector.min() >= 3, f"too few instances of some vectors:\n{per_vector}"


def test_behavioural_signal_overlaps_between_classes(ledger) -> None:
    """NOTES.md D-004, mitigation 1, and the explicit instruction to honour it in the
    simulator rather than retrofit it.

    A meaningful fraction of legitimate users paste a payee ID and hesitate before
    confirming a large transfer. If the legitimate distribution were clean and only fraud
    carried the telemetry, the ablation number would be spectacular and meaningless.
    """
    events = ledger.session_events.merge(
        ledger.sessions[["session_id", "is_fraud"]], on="session_id", how="left"
    )
    payee = events[events["field"] == "payee_id"]

    # Support is genuinely thin on the fraud side: only the APP-fraud vector produces
    # payee-entry events, and authorised push payment is one transfer per instance. That
    # scarcity is realistic and is itself a finding - the coercion signal has little to
    # learn from at this scale.
    def paste_rate(is_fraud: bool) -> float:
        rows = payee[payee["is_fraud"] == is_fraud]
        assert len(rows) >= 5, f"only {len(rows)} payee events for is_fraud={is_fraud}"
        return float((rows["input_method"] == "paste").mean())

    legit, fraud = paste_rate(False), paste_rate(True)
    assert 0.10 < legit < 0.45, f"legitimate paste rate {legit:.2f} is not realistic"
    assert fraud > legit, "the coercion signal should lean the right way"
    assert fraud < 0.95, f"fraud paste rate {fraud:.2f} is a giveaway, not a signal"


def test_confirm_dwell_overlaps_between_classes(ledger) -> None:
    events = ledger.session_events.merge(
        ledger.sessions[["session_id", "is_fraud"]], on="session_id", how="left"
    )
    confirm = events[(events["type"] == "confirm") & events["dwell_ms"].notna()]
    legit = confirm[~confirm["is_fraud"]]["dwell_ms"].to_numpy(dtype=float)
    fraud = confirm[confirm["is_fraud"]]["dwell_ms"].to_numpy(dtype=float)
    assert len(legit) > 50 and len(fraud) > 5

    # Ordinary hesitation before a large transfer must reach into the coerced range.
    overlap = float((legit > np.percentile(fraud, 25)).mean())
    assert overlap > 0.05, (
        f"only {overlap:.1%} of legitimate confirms reach the coerced lower quartile; "
        f"the distributions barely touch"
    )


def test_amounts_are_jointly_structured_not_independent(ledger) -> None:
    """PDF S5.1: amount correlates with merchant category, which correlates with hour.

    Independent per-field sampling gives correct marginals and wrong structure - it passes
    a histogram check and fails a discriminator.
    """
    txns = ledger.transactions[~ledger.transactions["is_fraud"]]
    by_mcc = txns.groupby("mcc")["amount_inr"].median()
    assert by_mcc.max() / by_mcc.min() > 4, "amount does not vary with merchant category"

    hours = txns.assign(hour=txns["timestamp"].dt.hour).groupby("mcc")["hour"].mean()
    assert hours.max() - hours.min() > 3, "hour of day does not vary with merchant category"


def test_a_sample_of_every_table_satisfies_the_ledger_contract(ledger) -> None:
    """The Parquet ledger is validated by sampling rows back into the contract's shape.

    Without this the JSON Schema only ever sees the fixtures, and the real generator can
    drift away from the contract unnoticed.
    """
    import json

    def records(frame, n=25):
        sample = frame.head(n).copy()
        for column in sample.columns:
            if str(sample[column].dtype).startswith("datetime"):
                sample[column] = sample[column].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return json.loads(sample.to_json(orient="records"))

    sessions = records(ledger.sessions)
    events_by_session = {
        sid: records(group.drop(columns=["session_id"]), 40)
        for sid, group in ledger.session_events.groupby("session_id")
    }
    for session in sessions:
        session["events"] = [
            {k: v for k, v in event.items() if k != "event_order"}
            for event in events_by_session.get(session["session_id"], [])
        ] or [{"type": "app_open", "t_offset_ms": 0}]

    payload = {
        "contract_version": "0.1.0",
        "label_columns": load_schema("ledger")["properties"]["label_columns"]["const"],
        "provenance_forbidden_columns": ["row_source", "generator_version"],
        "tables": {
            "accounts": records(ledger.accounts),
            "devices": records(ledger.devices),
            "merchants": records(ledger.merchants),
            "transactions": records(ledger.transactions),
            "sessions": sessions,
            "graph_edges": records(ledger.graph_edges),
        },
    }
    errors = validation_errors("ledger", payload)
    assert not errors, "generated ledger violates its contract:\n  - " + "\n  - ".join(errors[:10])
