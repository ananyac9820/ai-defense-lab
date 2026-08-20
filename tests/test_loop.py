"""The strategist and its validation layer.

PDF S7.2 makes validation mandatory. A validator that has only ever seen well-formed
input is not a validator, so most of these tests feed it things that should be refused.
"""

from __future__ import annotations

import json

import pytest

from adl.common.paths import FIXTURES_DIR
from adl.common.seeds import rng_for
from adl.loop.strategist import drift, propose, recompose
from adl.loop.validation import validate_proposals


@pytest.fixture(scope="module")
def vectors():
    return json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))[
        "vectors"
    ]


@pytest.fixture(scope="module")
def empty_misses(vectors):
    return {
        "contract_version": "0.1.0",
        "run_id": "test",
        "generation": 0,
        "threshold": 0.5,
        "prevalence": 0.01,
        "misses": [],
        "per_vector": [
            {"vector_id": v["vector_id"], "n_instances": 10, "n_detected": 9,
             "detection_rate": 0.9}
            for v in vectors
        ],
    }


def test_proposals_are_grammar_valid_and_executable(vectors, empty_misses) -> None:
    proposals = propose(empty_misses, vectors, rng=rng_for(1, "t"), generation=1, n=8)
    assert proposals
    result = validate_proposals([p.vector for p in proposals], vectors)
    assert not result.rejected, [(r.vector_id, r.reason, r.detail) for r in result.rejected]


def test_every_proposal_records_its_parent_and_mode(vectors, empty_misses) -> None:
    """A mutation with no lineage cannot be explained in the write-up."""
    for proposal in propose(empty_misses, vectors, rng=rng_for(2, "t"), generation=3, n=6):
        assert proposal.vector["parent_vector_id"] in {v["vector_id"] for v in vectors}
        assert proposal.vector["mutation_mode"] in {"recomposition", "parameter_drift"}
        assert proposal.vector["generation"] == 3


def test_drift_moves_parameters_without_inverting_them(vectors) -> None:
    parent = next(v for v in vectors if "residence_seconds" in v["parameters"])
    params, note = drift(parent, ["g_residence_seconds"], rng_for(3, "t"))
    assert params != parent["parameters"]
    assert "residence_seconds" in note
    for value in params.values():
        if isinstance(value, list) and len(value) == 2 and all(
            isinstance(x, (int, float)) for x in value
        ):
            assert value[0] <= value[1]


def test_recomposition_keeps_the_chain_valid(vectors) -> None:
    parent = vectors[0]
    result = recompose(parent, rng_for(4, "t"))
    assert result is not None
    chain, _ = result
    assert chain != parent["chain"]


def test_validator_refuses_a_backwards_chain(vectors) -> None:
    bad = {**vectors[0], "vector_id": "V900", "chain": ["drain_single", "phish_credential"]}
    result = validate_proposals([bad], vectors)
    assert result.rejected and result.rejected[0].reason == "grammar_invalid"


def test_validator_refuses_a_duplicate_attack(vectors) -> None:
    clone = {**vectors[0], "vector_id": "V901"}
    result = validate_proposals([clone], vectors)
    assert result.rejected and result.rejected[0].reason == "duplicate_attack"


def test_validator_refuses_a_reused_id(vectors) -> None:
    collision = {**vectors[0], "chain": ["phish_credential", "micro_test", "drain_single"]}
    result = validate_proposals([collision], vectors)
    assert result.rejected and result.rejected[0].reason == "duplicate_id"


def test_validator_refuses_an_unimplemented_primitive(vectors) -> None:
    """A vector counted in the taxonomy that emits nothing would inflate coverage."""
    bad = {
        **vectors[0],
        "vector_id": "V902",
        "chain": ["phish_credential", "teleport_funds"],
    }
    result = validate_proposals([bad], vectors)
    assert result.rejected
    assert result.rejected[0].reason in {"grammar_invalid", "unimplemented_primitive"}


def test_validator_refuses_an_inverted_range(vectors) -> None:
    bad = {
        **vectors[0],
        "vector_id": "V903",
        "chain": ["phish_credential", "balance_probe", "drain_single"],
        "parameters": {"drain_amount_inr": [900, 100]},
    }
    result = validate_proposals([bad], vectors)
    assert result.rejected and result.rejected[0].reason == "inverted_range"


def test_rejection_rate_is_reported(vectors, empty_misses) -> None:
    """S7.2: the rejection rate is itself a number for the write-up."""
    good = propose(empty_misses, vectors, rng=rng_for(5, "t"), generation=1, n=2)
    bad = [{**vectors[0], "vector_id": "V904", "chain": ["drain_single", "micro_test"]}]
    result = validate_proposals([p.vector for p in good] + bad, vectors)
    assert 0.0 < result.rejection_rate < 1.0
    assert "rejected" in result.summary()
