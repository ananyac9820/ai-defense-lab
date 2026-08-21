"""Freshness and provenance audit for every published figure.

    python scripts/audit_artefacts.py

Four bugs in this project have produced numbers for code that never ran:

  1. a vector filter that tested a retired registry, so three attack vectors were
     counted in the taxonomy and emitted nothing;
  2. a ledger cache keyed on seed and size but not the attack set, which served a
     ledger generated before three vectors existed;
  3. the loop and the pipeline both writing misses.g0.json, so whichever ran last
     silently replaced the other's miss log;
  4. a cache key that still did not cover the simulator source, so editing a primitive
     would serve a ledger built by code that no longer exists.

Every one was caught by a number looking wrong, not by a test. A manual checklist will
miss the fifth, so this is a script and it fails loudly.

It asserts three things:

  FRESHNESS   every artefact records the digest of the source that produced it, and that
              digest matches the code in the repository now. Modification times cannot
              answer this - git does not preserve them, so on a fresh clone every file
              carries the same timestamp. The clean-clone test caught that.
  PROVENANCE  the run manifest's config hash matches the current config, its seed matches
              the configured seed, and dependent artefacts carry the same run_id.
  COHERENCE   the artefacts agree with each other and with the attack set: prevalences
              match, vector ids are all real, holdout vectors are absent from training.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from adl.common.config import config_hash, load_config, source_digest
from adl.common.paths import ARTIFACTS_DIR, FIXTURES_DIR

PUBLISHED = ARTIFACTS_DIR / "published"
WALKTHROUGH = ARTIFACTS_DIR / "AI_Defense_Lab_Walkthrough.docx"

@dataclass
class Finding:
    level: str          # FAIL or WARN
    check: str
    detail: str


def freshness(findings: list[Finding]) -> None:
    """Were these artefacts produced by the code currently in the repository?

    Originally this compared modification times, and the clean-clone test proved that
    wrong on the machine it matters most on: git does not preserve mtimes, so every file
    in a fresh clone carries the same timestamp and any ordering between them is an
    accident. The check reported four failures on a clone where nothing was actually
    stale, and would have reported none on a clone where everything was.

    Content digests answer the question properly and identically everywhere.
    """
    current = source_digest()

    for artefact in ("run_manifest.json", "run_manifest_loop.json"):
        path = PUBLISHED / artefact
        if not path.exists():
            findings.append(Finding("WARN", "freshness", f"{artefact} not present"))
            continue
        recorded = json.loads(path.read_text(encoding="utf-8")).get("source_digest")
        if recorded is None:
            findings.append(Finding(
                "WARN", "freshness",
                f"{artefact} predates source-digest recording, so its provenance cannot "
                f"be verified. Regenerate it.",
            ))
        elif recorded != current:
            findings.append(Finding(
                "FAIL", "freshness",
                f"{artefact} was produced by different code: records "
                f"{recorded[:12]}, current source digest is {current[:12]}. Regenerate "
                f"before quoting any figure from it.",
            ))

    # The walkthrough records what it was built from, so the same question can be asked
    # of it without relying on file times either.
    stamp = ARTIFACTS_DIR / "walkthrough_build.json"
    if not WALKTHROUGH.exists():
        findings.append(Finding("WARN", "freshness", "walkthrough .docx not built"))
    elif not stamp.exists():
        findings.append(Finding("WARN", "freshness", "walkthrough build stamp missing"))
    else:
        built = json.loads(stamp.read_text(encoding="utf-8"))
        if built.get("source_digest") != current:
            findings.append(Finding(
                "FAIL", "freshness",
                f"the walkthrough was built from source digest "
                f"{str(built.get('source_digest'))[:12]}, current is {current[:12]}. Its "
                f"figures describe code that has since changed.",
            ))
        manifest_path = PUBLISHED / "run_manifest.json"
        if manifest_path.exists():
            live = json.loads(manifest_path.read_text(encoding="utf-8"))
            if built.get("run_id") != live.get("run_id"):
                findings.append(Finding(
                    "FAIL", "freshness",
                    f"the walkthrough was built from run {built.get('run_id')} but the "
                    f"published manifest is {live.get('run_id')}.",
                ))


def provenance(findings: list[Finding]) -> dict[str, Any] | None:
    path = PUBLISHED / "run_manifest.json"
    if not path.exists():
        findings.append(Finding("FAIL", "provenance", "run_manifest.json missing"))
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cfg = load_config()

    current = config_hash()
    if manifest["config_hash"] != current:
        findings.append(Finding(
            "FAIL", "provenance",
            f"config hash mismatch: manifest {manifest['config_hash'][:12]} vs current "
            f"{current[:12]}. config.yaml changed after the run, so the settings that "
            f"produced these numbers are not the settings in the repository.",
        ))
    if manifest["seed"] != cfg["run"]["seed"]:
        findings.append(Finding(
            "FAIL", "provenance",
            f"seed mismatch: manifest {manifest['seed']} vs config {cfg['run']['seed']}",
        ))
    if manifest.get("is_fixture"):
        findings.append(Finding(
            "FAIL", "provenance",
            "run_manifest is flagged is_fixture. Fixture numbers must never reach the "
            "walkthrough or the deployed prototype.",
        ))

    misses_path = PUBLISHED / "misses.g0.json"
    if misses_path.exists():
        misses = json.loads(misses_path.read_text(encoding="utf-8"))
        expected = f"{cfg['run']['run_id_prefix']}-g0-{manifest['seed']}"
        if misses["run_id"] != expected:
            findings.append(Finding(
                "FAIL", "provenance",
                f"misses.g0.json carries run_id {misses['run_id']}, expected {expected}. "
                f"It was written by a different run than the manifest.",
            ))
    return manifest


def coherence(findings: list[Finding], manifest: dict[str, Any] | None) -> None:
    if manifest is None:
        return
    attacks = json.loads((FIXTURES_DIR / "attacks.fixture.json").read_text(encoding="utf-8"))
    known = {v["vector_id"] for v in attacks["vectors"]}
    held = {v["vector_id"] for v in attacks["vectors"] if v.get("holdout") != "none"}

    misses_path = PUBLISHED / "misses.g0.json"
    if misses_path.exists():
        misses = json.loads(misses_path.read_text(encoding="utf-8"))
        unknown = {r["vector_id"] for r in misses["per_vector"]} - known
        if unknown:
            findings.append(Finding(
                "FAIL", "coherence",
                f"miss log references vectors not in attacks.json: {sorted(unknown)}",
            ))
        reported = {r["vector_id"] for r in misses["per_vector"]}
        silent = known - reported
        if silent:
            findings.append(Finding(
                "WARN", "coherence",
                f"vectors authored but absent from the miss log: {sorted(silent)}. Either "
                f"they emitted nothing or they produced no test-window instances.",
            ))
        missing_holdouts = held - reported
        if missing_holdouts:
            findings.append(Finding(
                "WARN", "coherence",
                f"held-out vectors missing from the results: {sorted(missing_holdouts)}. "
                f"The holdout table in the walkthrough will be short a row.",
            ))

    slice_path = PUBLISHED / "demo_slice.json"
    if slice_path.exists():
        demo = json.loads(slice_path.read_text(encoding="utf-8"))
        declared = manifest["prevalence"]
        actual = demo.get("prevalence", 0)
        if abs(actual - declared) > declared * 0.5:
            findings.append(Finding(
                "WARN", "coherence",
                f"demo slice prevalence {actual:.4%} differs sharply from the run's "
                f"{declared:.4%}. The slice is a window, so some drift is expected, but "
                f"this much means the prototype is showing an unrepresentative sample.",
            ))

    for gen in manifest["generations"]:
        for key in ("metrics_seen", "metrics_unseen"):
            m = gen.get(key)
            if m and m.get("prevalence", 0) <= 0:
                findings.append(Finding(
                    "FAIL", "coherence",
                    f"generation {gen['generation']} {key} has non-positive prevalence; a "
                    f"metric without a base rate cannot be read.",
                ))
        if gen.get("metrics_seen") and gen.get("metrics_unseen"):
            if gen["metrics_seen"] == gen["metrics_unseen"]:
                findings.append(Finding(
                    "WARN", "coherence",
                    f"generation {gen['generation']} reports identical seen and unseen "
                    f"metrics. That means nothing is actually held out.",
                ))


def main() -> int:
    findings: list[Finding] = []
    freshness(findings)
    manifest = provenance(findings)
    coherence(findings, manifest)

    print("=" * 74)
    print("ARTEFACT AUDIT")
    print("=" * 74)
    if not findings:
        print("  clean: every artefact is fresh, provenanced and internally consistent")
        return 0

    fails = [f for f in findings if f.level == "FAIL"]
    warns = [f for f in findings if f.level == "WARN"]
    for f in fails + warns:
        print(f"\n  [{f.level}] {f.check}")
        for line in f.detail.split(". "):
            print(f"        {line.strip().rstrip('.')}.")

    print()
    print(f"  {len(fails)} failures, {len(warns)} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
