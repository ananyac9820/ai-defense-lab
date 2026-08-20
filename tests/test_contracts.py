"""The contracts must be well-formed before anything is built against them.

PDF S3 (boxed): "Define the JSON schemas ... on day one, commit them, and treat
changes to them as a decision requiring agreement." These tests are what make that
enforceable rather than aspirational.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from adl.common.contracts import load_grammar, load_schema
from adl.common.paths import CONTRACTS_DIR, SCHEMA_BY_NAME

CONTRACT_NAMES = sorted(SCHEMA_BY_NAME)


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_schema_is_itself_valid(name: str) -> None:
    Draft202012Validator.check_schema(load_schema(name))


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_schema_is_versioned_and_frozen(name: str) -> None:
    schema = load_schema(name)
    assert "FROZEN CONTRACT v0" in schema["description"], (
        f"{name} lost its freeze marker; a contract without one invites silent edits"
    )
    props = schema["properties"]
    assert props["contract_version"]["const"] == "0.1.0"


def test_all_four_contracts_present() -> None:
    on_disk = {p.name for p in CONTRACTS_DIR.glob("*.schema.json")}
    assert on_disk == {f"{n}.schema.json" for n in CONTRACT_NAMES}
    assert len(on_disk) == 4, "three from the PDF plus run_manifest, added 2026-08-20"


def test_grammar_primitives_are_internally_consistent() -> None:
    grammar = load_grammar()
    stages = set(grammar["stage_order"])
    assert len(grammar["primitives"]) == 19, "PDF S4.2 vocabulary; changing the count is a decision"
    for name, prim in grammar["primitives"].items():
        assert prim["stage"] in stages, f"{name} has stage {prim['stage']!r} outside stage_order"
        assert prim["description"].strip()
        assert prim["data_footprint"].strip(), f"{name} must state what the simulator emits"
        assert set(prim["detection_level_hint"]) <= {"transaction", "session", "graph"}


def test_grammar_axes_match_the_schemas() -> None:
    """A vector's channel must be expressible in both the grammar and the ledger."""
    grammar = load_grammar()
    attacks = load_schema("attacks")["$defs"]["vector"]["properties"]
    ledger = load_schema("ledger")["$defs"]["transaction"]["properties"]

    assert grammar["axes"]["channel"] == attacks["channel"]["enum"]
    assert grammar["axes"]["channel"] == ledger["channel"]["enum"]
    assert grammar["axes"]["ai_capability"] == attacks["ai_capability"]["enum"]
    assert grammar["axes"]["objective"] == attacks["objective"]["enum"]


def test_grammar_axes_are_seven_by_seven_by_seven() -> None:
    """The taxonomy grid from PDF S4.1. Seven rows, three populated axes."""
    axes = load_grammar()["axes"]
    assert [len(v) for v in axes.values()] == [7, 7, 7]
    assert "agentic_commerce" in axes["channel"], "PDF S4.1: do not omit agentic commerce"
    assert "agent_impersonation" in axes["ai_capability"]


def test_contracts_are_utf8_json_without_bom() -> None:
    for path in CONTRACTS_DIR.glob("*.json"):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name} has a BOM"
        json.loads(raw.decode("utf-8"))
