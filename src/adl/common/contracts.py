"""Contract loading, validation, and grammar rules.

The PDF's single strongest process instruction (S3, boxed) is to freeze the data
contracts before building the components. This module is the enforcement point: if a
producer emits something a consumer cannot read, a test fails here rather than in
Phase 5.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

from .paths import GRAMMAR_PATH, SCHEMA_BY_NAME


@lru_cache(maxsize=8)
def load_schema(name: str) -> dict[str, Any]:
    try:
        path = SCHEMA_BY_NAME[name]
    except KeyError:
        raise KeyError(f"unknown contract {name!r}; known: {sorted(SCHEMA_BY_NAME)}") from None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_grammar() -> dict[str, Any]:
    return json.loads(GRAMMAR_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), format_checker=FormatChecker())


def validation_errors(name: str, instance: Any) -> list[str]:
    """All schema violations, as readable strings. Empty list means valid."""
    errors = sorted(_validator(name).iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def validate(name: str, instance: Any) -> None:
    """Raise with every violation listed, not just the first."""
    errors = validation_errors(name, instance)
    if errors:
        joined = "\n  - ".join(errors)
        raise ValueError(f"{name} failed contract validation:\n  - {joined}")


def load_and_validate(name: str, path: str | Path) -> Any:
    instance = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(name, instance)
    return instance


# --------------------------------------------------------------------------------
# Grammar rules. The JSON Schema cannot express composition ordering, so chain
# validity lives here and every producer of attacks.json must pass through it.
# --------------------------------------------------------------------------------


class ChainError(ValueError):
    """A chain that violates the grammar's composition rules."""


def stage_of(primitive: str) -> str:
    grammar = load_grammar()
    try:
        return grammar["primitives"][primitive]["stage"]
    except KeyError:
        raise ChainError(f"unknown primitive {primitive!r}") from None


def validate_chain(chain: Iterable[str], objective: str | None = None) -> None:
    """Raise :class:`ChainError` unless the chain is a valid path through the grammar.

    Applied to hand-authored vectors and to every chain the red-team strategist
    returns (PDF S7.2 makes the validation layer mandatory).
    """
    grammar = load_grammar()
    rules = grammar["composition_rules"]
    order = grammar["stage_order"]
    chain = list(chain)

    if not (rules["min_length"] <= len(chain) <= rules["max_length"]):
        raise ChainError(
            f"chain length {len(chain)} outside [{rules['min_length']}, {rules['max_length']}]"
        )

    stages = [stage_of(p) for p in chain]
    indices = [order.index(s) for s in stages]

    if rules["stages_non_decreasing"] and any(b < a for a, b in zip(indices, indices[1:])):
        raise ChainError(f"stages must not go backwards: {list(zip(chain, stages))}")

    if rules["no_immediate_repeat"] and any(a == b for a, b in zip(chain, chain[1:])):
        raise ChainError(f"primitive repeated back to back in {chain}")

    if "max_per_stage" in rules:
        for stage in set(stages):
            used = stages.count(stage)
            if used > rules["max_per_stage"]:
                raise ChainError(
                    f"{used} primitives at stage {stage!r}, limit is {rules['max_per_stage']}; "
                    f"further repetition is parameter variation, not a distinct chain"
                )

    exempt = objective in set(rules["terminal_exempt_objectives"])
    if not exempt and not set(stages) & set(rules["terminal_stage_required"]):
        raise ChainError(
            f"chain must reach {rules['terminal_stage_required']} unless the objective is "
            f"one of {rules['terminal_exempt_objectives']}; got objective={objective!r}"
        )


def is_valid_chain(chain: Iterable[str], objective: str | None = None) -> bool:
    try:
        validate_chain(chain, objective)
    except ChainError:
        return False
    return True


@lru_cache(maxsize=4)
def valid_chain_space(require_terminal: bool = True) -> int:
    """Size of the grammar's valid chain space.

    PDF S4.2 frames the claim as "a grammar whose valid chain space is N, of which we
    implemented M, selected for coverage across all channel and capability axes" - N is
    the size of the space the red-team strategist can search, not a denominator to
    divide M by. See :func:`coverage_report` for the numbers that are actually
    reportable as coverage.

    Counted by dynamic programming over (last primitive, run length within the current
    stage, terminal reached) rather than by enumeration, because the space is large.
    """
    grammar = load_grammar()
    rules = grammar["composition_rules"]
    order: list[str] = grammar["stage_order"]
    prims: list[str] = list(grammar["primitives"])
    stage_idx = {p: order.index(grammar["primitives"][p]["stage"]) for p in prims}
    terminal = {order.index(s) for s in rules["terminal_stage_required"]}
    max_per_stage = rules.get("max_per_stage", rules["max_length"])

    # state: (last primitive, count used at the current stage, terminal reached) -> chains
    state: dict[tuple[int, int, bool], int] = {
        (i, 1, stage_idx[p] in terminal): 1 for i, p in enumerate(prims)
    }
    total = 0
    for length in range(1, rules["max_length"] + 1):
        if length >= rules["min_length"]:
            total += sum(
                c for (_, _, reached), c in state.items() if reached or not require_terminal
            )
        if length == rules["max_length"]:
            break
        nxt: dict[tuple[int, int, bool], int] = {}
        for (last, run, reached), count in state.items():
            for j, p in enumerate(prims):
                if rules["no_immediate_repeat"] and j == last:
                    continue
                if rules["stages_non_decreasing"] and stage_idx[p] < stage_idx[prims[last]]:
                    continue
                same_stage = stage_idx[p] == stage_idx[prims[last]]
                new_run = run + 1 if same_stage else 1
                if new_run > max_per_stage:
                    continue
                key = (j, new_run, reached or stage_idx[p] in terminal)
                nxt[key] = nxt.get(key, 0) + count
        state = nxt
    return total


def coverage_report(vectors: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Coverage of the attack surface, stated the three ways that mean something.

    A fraction of the chain space is not one of them: any grammar worth having admits
    orders of magnitude more chains than a team can implement, so M/N is a number that
    only ever looks bad. What is defensible is which primitives are exercised, which
    stage transitions are exercised, and which cells of the S4.1 taxonomy grid are
    populated - with reasoned explanations for the empty ones.
    """
    grammar = load_grammar()
    prims = set(grammar["primitives"])
    order = grammar["stage_order"]
    axes = grammar["axes"]
    vectors = list(vectors)

    used_prims = {p for v in vectors for p in v["chain"]}
    transitions = {
        (stage_of(a), stage_of(b)) for v in vectors for a, b in zip(v["chain"], v["chain"][1:])
    }
    possible_transitions = {
        (order[i], order[j]) for i in range(len(order)) for j in range(i, len(order))
    }
    cells = {(v["channel"], v["ai_capability"], v["objective"]) for v in vectors}
    grid_size = len(axes["channel"]) * len(axes["ai_capability"]) * len(axes["objective"])

    return {
        "n_vectors": len(vectors),
        "valid_chain_space": valid_chain_space(),
        "primitives_used": len(used_prims),
        "primitives_total": len(prims),
        "primitives_unused": sorted(prims - used_prims),
        "stage_transitions_used": len(transitions),
        "stage_transitions_possible": len(possible_transitions),
        "grid_cells_populated": len(cells),
        "grid_cells_total": grid_size,
        "channels_covered": sorted({v["channel"] for v in vectors}),
        "capabilities_covered": sorted({v["ai_capability"] for v in vectors}),
        "objectives_covered": sorted({v["objective"] for v in vectors}),
    }
