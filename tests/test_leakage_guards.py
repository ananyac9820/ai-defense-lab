"""Guards against the two ways this project could produce a number it cannot defend.

Both are cheap to check and expensive to discover late, which is the whole argument
for writing them in Phase 1.
"""

from __future__ import annotations

import json

from adl.common.config import load_config
from adl.common.contracts import load_schema
from adl.common.paths import FIXTURES_DIR
from adl.common.seeds import derive_seed, rng_for


def test_baseline_uses_no_label_columns() -> None:
    """NOTES.md D-002. A baseline that can see a label is not a baseline."""
    labels = set(load_schema("ledger")["properties"]["label_columns"]["const"])
    features = set(load_config()["baseline"]["features"])
    assert not features & labels, f"baseline features touch labels: {sorted(features & labels)}"


def test_baseline_is_transaction_level_only() -> None:
    """The whole point of the ablation is that the baseline cannot see session or
    graph evidence. If it could, the per-level lift in PDF S6.1 would be meaningless."""
    forbidden = ("session_", "graph_", "cadence", "paste", "dwell", "fanout", "cycle")
    for feature in load_config()["baseline"]["features"]:
        assert not feature.startswith(forbidden), f"{feature} is not transaction-level"


def test_behavioural_fields_exist_only_on_session_events() -> None:
    """NOTES.md D-004. Signals A and B must be invisible to the transaction baseline.

    If a paste ratio or a dwell time ever appears as a transaction column, the baseline
    silently gains the differentiator and the reported lift collapses to noise.
    """
    ledger = load_schema("ledger")
    txn_columns = set(ledger["$defs"]["transaction"]["properties"])
    behavioural = {"input_method", "dwell_ms", "corrections", "t_offset_ms"}
    assert not txn_columns & behavioural
    assert behavioural <= set(ledger["$defs"]["session_event"]["properties"])


def test_split_is_configured_for_both_time_and_account() -> None:
    """PDF S6.2 requires both conditions, not either."""
    split = load_config()["split"]
    assert split["mode"] == "time_and_account"
    assert split["embargo_days"] >= 1, "an embargo gap kills boundary leakage between windows"


def test_prevalence_is_realistic() -> None:
    """PDF S5.2: real payment fraud runs 0.1% to 2%."""
    prevalence = load_config()["simulation"]["fraud_prevalence"]
    assert 0.001 <= prevalence <= 0.02


def test_metrics_contract_forces_prevalence_alongside_every_metric() -> None:
    metrics = load_schema("run_manifest")["$defs"]["metrics"]
    assert "prevalence" in metrics["required"]
    assert "auc_pr" in metrics["required"], "AUC-PR is the honest headline at low prevalence"


def test_seeds_are_stable_across_processes() -> None:
    """Not hash(); CPython salts that per process and it would break reproducibility."""
    assert derive_seed(20260831, "simulator") == derive_seed(20260831, "simulator")
    assert derive_seed(20260831, "simulator") != derive_seed(20260831, "detector")
    assert rng_for(1, "x").integers(0, 10**9) == rng_for(1, "x").integers(0, 10**9)


def test_no_reference_rows_are_committed() -> None:
    """NOTES.md D-006. Reference data calibrates distributions; it never supplies rows."""
    from adl.common.paths import REFERENCE_DIR

    strays = [p.name for p in REFERENCE_DIR.glob("*") if p.suffix in {".csv", ".parquet", ".zip"}]
    assert not strays, f"reference rows must not be committed: {strays}"


def test_fixture_manifest_reports_lift_not_bare_scores() -> None:
    """Build brief requirement 2: every headline is lift over a defined baseline."""
    manifest = json.loads((FIXTURES_DIR / "run_manifest.fixture.json").read_text(encoding="utf-8"))
    assert manifest["baseline"]["metrics"]["lift_over_baseline"] is None, "baseline has no lift"
    for gen in manifest["generations"]:
        for key in ("metrics_seen", "metrics_unseen"):
            lift = gen[key]["lift_over_baseline"]
            assert lift and "auc_pr" in lift, f"generation {gen['generation']} {key} has no lift"
