"""Composition rules for the attack grammar.

PDF S7.2 makes the validation layer mandatory: every chain the red-team strategist
returns is machine-validated before the simulator touches it. That validator is
:func:`validate_chain`, so it is worth more tests than anything else in Phase 1.
"""

from __future__ import annotations

import pytest

from adl.common.contracts import ChainError, is_valid_chain, valid_chain_space, validate_chain


def test_accepts_a_well_formed_chain() -> None:
    validate_chain(["phish_credential", "register_device", "drain_single"], "account_takeover")


def test_rejects_backwards_stages() -> None:
    with pytest.raises(ChainError, match="must not go backwards"):
        validate_chain(["drain_single", "phish_credential"], "account_takeover")


def test_rejects_unknown_primitive() -> None:
    with pytest.raises(ChainError, match="unknown primitive"):
        validate_chain(["phish_credential", "steal_everything"], "account_takeover")


def test_rejects_immediate_repeat() -> None:
    with pytest.raises(ChainError, match="repeated back to back"):
        validate_chain(["micro_test", "micro_test", "drain_single"], "account_takeover")


def test_rejects_too_short_and_too_long() -> None:
    with pytest.raises(ChainError, match="outside"):
        validate_chain(["drain_single"], "account_takeover")
    with pytest.raises(ChainError, match="outside"):
        validate_chain(["micro_test"] * 9, "account_takeover")


def test_requires_a_terminal_stage_unless_the_objective_is_exempt() -> None:
    probe_only = ["phish_credential", "balance_probe"]
    with pytest.raises(ChainError, match="must reach"):
        validate_chain(probe_only, "account_takeover")
    # credential_capture completes without moving money, so the same chain is valid
    validate_chain(probe_only, "credential_capture")


def test_two_primitives_at_the_same_stage_are_allowed() -> None:
    """Probing then sweeping is one realistic validate stage, not two chains."""
    assert is_valid_chain(
        ["micro_test", "card_test_sweep", "drain_single"], "account_takeover"
    )


def test_chain_space_is_large_enough_to_be_worth_searching() -> None:
    """PDF S4.2: 'roughly twenty primitives generate several hundred distinct chains'.

    N is the space the red-team strategist searches, so it has to be a real computed
    number rather than a rounded assertion. This test pins it: if the grammar changes,
    N changes and this test says so out loud.
    """
    n = valid_chain_space(require_terminal=True)
    assert n > 500, f"chain space of {n} is too small for the strategist to have room"
    print(f"\nvalid chain space (terminal required) = {n:,}")
    print(f"valid chain space (any composition)    = {valid_chain_space(False):,}")


def test_rejects_more_than_two_primitives_at_one_stage() -> None:
    with pytest.raises(ChainError, match="limit is 2"):
        validate_chain(
            ["micro_test", "card_test_sweep", "balance_probe", "drain_single"], "account_takeover"
        )


def test_coverage_is_reported_along_the_axes_not_as_a_fraction_of_the_chain_space() -> None:
    """The chain space is a capability statement, not a denominator.

    Implemented-over-valid would put the thin slice at roughly 1 in 10^5, which reads as
    a failure rather than as the deliberately small, axis-spread selection it is.
    """
    import json

    from adl.common.contracts import coverage_report
    from adl.common.paths import FIXTURES_DIR

    vectors = json.loads(
        (FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8")
    )["vectors"]
    report = coverage_report(vectors)

    print("\ncoverage of the thin slice:")
    for key, value in report.items():
        print(f"  {key:32s} {value}")

    assert report["primitives_total"] == 19
    assert report["grid_cells_total"] == 343
    assert len(report["channels_covered"]) >= 5
