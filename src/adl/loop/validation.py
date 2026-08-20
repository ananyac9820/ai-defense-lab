"""The validation layer. Mandatory, per PDF S7.2.

"Language model output is unreliable at the margins: expect malformed chains, duplicates
of existing vectors, and compositions that violate ordering rules. Every returned chain
passes through grammar validation, deduplication against existing vector_ids, and a
plausibility check before the simulator touches it. Log rejections - the rejection rate
is itself an interesting number for the write-up."

It applies to deterministic proposals too. A mutation engine can produce a duplicate or
an unexecutable chain just as easily as a model can, and a validator that only runs on
model output is a validator that has not been tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adl.common.contracts import ChainError, validate, validate_chain


@dataclass
class Rejection:
    vector_id: str
    reason: str
    detail: str


@dataclass
class ValidationResult:
    accepted: list[dict[str, Any]]
    rejected: list[Rejection]

    @property
    def rejection_rate(self) -> float:
        total = len(self.accepted) + len(self.rejected)
        return len(self.rejected) / total if total else 0.0

    def summary(self) -> str:
        by_reason: dict[str, int] = {}
        for r in self.rejected:
            by_reason[r.reason] = by_reason.get(r.reason, 0) + 1
        detail = ", ".join(f"{k} {v}" for k, v in sorted(by_reason.items())) or "none"
        return (
            f"{len(self.accepted)} accepted, {len(self.rejected)} rejected "
            f"({self.rejection_rate:.0%}); reasons: {detail}"
        )


def _signature(vector: dict[str, Any]) -> tuple:
    """What makes two vectors the same attack, ignoring the id and the prose."""
    return (
        vector["channel"],
        vector["ai_capability"],
        vector["objective"],
        tuple(vector["chain"]),
        tuple(sorted(
            (k, tuple(v) if isinstance(v, list) else v)
            for k, v in vector.get("parameters", {}).items()
        )),
    )


def validate_proposals(
    proposals: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> ValidationResult:
    """Grammar validity, then duplication, then plausibility, then the schema."""
    from adl.generate.primitives import PRIMITIVES

    accepted: list[dict[str, Any]] = []
    rejected: list[Rejection] = []

    seen_ids = {v["vector_id"] for v in existing}
    seen_signatures = {_signature(v) for v in existing}

    for vector in proposals:
        vid = vector.get("vector_id", "?")

        try:
            validate_chain(vector["chain"], vector.get("objective"))
        except ChainError as err:
            rejected.append(Rejection(vid, "grammar_invalid", str(err)))
            continue
        except (KeyError, TypeError) as err:
            rejected.append(Rejection(vid, "malformed", str(err)))
            continue

        if vid in seen_ids:
            rejected.append(Rejection(vid, "duplicate_id", "vector_id already in use"))
            continue

        signature = _signature(vector)
        if signature in seen_signatures:
            rejected.append(
                Rejection(vid, "duplicate_attack", "identical chain and parameters exist")
            )
            continue

        # Plausibility: the simulator has to be able to run every primitive, or the
        # vector would be counted in the taxonomy while emitting nothing.
        missing = [p for p in vector["chain"] if p not in PRIMITIVES]
        if missing:
            rejected.append(Rejection(vid, "unimplemented_primitive", ", ".join(missing)))
            continue

        bad_ranges = [
            k for k, v in vector.get("parameters", {}).items()
            if isinstance(v, list) and len(v) == 2
            and all(isinstance(x, (int, float)) for x in v) and v[0] > v[1]
        ]
        if bad_ranges:
            rejected.append(Rejection(vid, "inverted_range", ", ".join(bad_ranges)))
            continue

        try:
            validate("attacks", {
                "contract_version": "0.1.0",
                "generated_at": "2026-08-20T00:00:00Z",
                "grammar_version": "0.1.0",
                "vectors": [vector],
            })
        except ValueError as err:
            rejected.append(Rejection(vid, "schema_invalid", str(err).split("\n")[0]))
            continue

        accepted.append(vector)
        seen_ids.add(vid)
        seen_signatures.add(signature)

    return ValidationResult(accepted=accepted, rejected=rejected)
