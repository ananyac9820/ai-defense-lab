"""The committed fixtures must be contract-valid and byte-reproducible.

If the fixtures drift from the contracts, the frontend is being built against a shape
the pipeline will never emit - which is the late-integration failure PDF S10 rates
Severe, arriving on schedule.
"""

from __future__ import annotations

import json

import pytest

from adl.common.contracts import validate, validate_chain, validation_errors
from adl.common.paths import FIXTURES_DIR

FIXTURE_CONTRACTS = [
    ("attacks.fixture.json", "attacks"),
    ("ledger.fixture.json", "ledger"),
    ("run_manifest.fixture.json", "run_manifest"),
    *[(f"misses.g{g}.fixture.json", "misses") for g in range(5)],
]


def _load(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("filename", "contract"), FIXTURE_CONTRACTS)
def test_fixture_matches_its_contract(filename: str, contract: str) -> None:
    errors = validation_errors(contract, _load(filename))
    assert not errors, f"{filename}:\n  - " + "\n  - ".join(errors[:12])


def test_every_fixture_vector_is_a_valid_chain() -> None:
    for v in _load("attacks.fixture.json")["vectors"]:
        validate_chain(v["chain"], v["objective"])


def test_every_vector_is_grounded_in_a_real_case() -> None:
    """Build brief requirement 4: no vector ships without a cited incident."""
    for v in _load("attacks.fixture.json")["vectors"]:
        src = v["source"]
        assert src["citation_url"].startswith("http"), v["vector_id"]
        assert len(src["case"]) > 40, f"{v['vector_id']} source is too thin to render"
        assert src["doc_ref"], f"{v['vector_id']} must say where in the source docs it came from"


def test_thin_slice_covers_all_three_detection_levels() -> None:
    """NOTES.md D-012: the five were chosen so each proves a different level."""
    levels = {lvl for v in _load("attacks.fixture.json")["vectors"] for lvl in v["expected_levels"]}
    assert levels == {"transaction", "session", "graph"}


def test_thin_slice_spans_at_least_five_channels() -> None:
    channels = {v["channel"] for v in _load("attacks.fixture.json")["vectors"]}
    assert len(channels) >= 5, f"only {len(channels)} channels covered: {sorted(channels)}"


def test_ledger_fixture_holds_realistic_prevalence() -> None:
    """PDF S5.2. A fixture at 50% fraud would teach the UI the wrong visual density."""
    txns = _load("ledger.fixture.json")["tables"]["transactions"]
    prevalence = sum(t["is_fraud"] for t in txns) / len(txns)
    assert 0.005 <= prevalence <= 0.02, f"fixture prevalence {prevalence:.4f} is not near 1%"


def test_ledger_referential_integrity() -> None:
    tables = _load("ledger.fixture.json")["tables"]
    accounts = {a["account_id"] for a in tables["accounts"]}
    devices = {d["device_id"] for d in tables["devices"]}
    merchants = {m["merchant_id"] for m in tables["merchants"]}

    for t in tables["transactions"]:
        assert t["account_id"] in accounts
        assert t["device_id"] in devices
        assert t["merchant_id"] is None or t["merchant_id"] in merchants
    for s in tables["sessions"]:
        assert s["account_id"] in accounts
    for e in tables["graph_edges"]:
        assert e["source_account"] in accounts and e["target_account"] in accounts
        assert e["source_account"] != e["target_account"], "self-loop in the account graph"


def test_behavioural_signal_overlaps_between_classes() -> None:
    """NOTES.md D-004, mitigation 1.

    A signal that separates cleanly is a simulator bug, not a result. Legitimate
    sessions must also contain pasted payee IDs, or the detector is being handed the
    answer.
    """
    sessions = _load("ledger.fixture.json")["tables"]["sessions"]

    def paste_rate(fraud: bool) -> float:
        rows = [
            e for s in sessions if s["is_fraud"] is fraud
            for e in s["events"] if e.get("field") == "payee_id"
        ]
        assert rows, f"no payee_id events for is_fraud={fraud}"
        return sum(e["input_method"] == "paste" for e in rows) / len(rows)

    legit, fraud = paste_rate(False), paste_rate(True)
    assert 0.05 < legit < 0.5, f"legitimate paste rate {legit:.2f} is implausible"
    assert fraud > legit, "the coercion signal should lean the right way"
    assert fraud < 0.95, f"fraud paste rate {fraud:.2f} is a giveaway, not a signal"


def test_fixtures_are_flagged_as_fixtures() -> None:
    """No screenshot of invented numbers may be mistaken for a result."""
    assert _load("run_manifest.fixture.json")["is_fixture"] is True


def test_fixtures_are_byte_reproducible(tmp_path, monkeypatch) -> None:
    """Same seed, same bytes. PDF S12: every number regenerable with one command."""
    import scripts.make_fixtures as mf

    monkeypatch.setattr(mf, "FIXTURES_DIR", tmp_path)
    mf.main()

    for filename, contract in FIXTURE_CONTRACTS:
        regenerated = (tmp_path / filename).read_bytes()
        committed = (FIXTURES_DIR / filename).read_bytes()
        assert regenerated == committed, (
            f"{filename} is not reproducible from seed - regenerate and commit, or find "
            f"the unseeded RNG call"
        )
        validate(contract, json.loads(regenerated))
