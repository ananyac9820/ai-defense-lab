"""One command, every number.

PDF S12: "Repository clones clean, installs from a lockfile, and reproduces every
reported number with one command." This is that command. It grows a stage per phase;
each stage prints what it produced so a clean-clone run is legible rather than silent.

    python scripts/reproduce.py

Phase 1 runs the two stages that exist. Missing stages are listed, not skipped
silently - an honest "not built yet" beats a green run that checked nothing.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

STAGES: list[tuple[str, list[str] | None]] = [
    ("profile reference datasets", [sys.executable, "-m", "adl.generate.profile_reference"]),
    ("generate fixtures", [sys.executable, "scripts/make_fixtures.py"]),
    ("contract and leakage tests", [sys.executable, "-m", "pytest", "-q"]),
    ("simulate ledger", None),           # Phase 2
    ("train detector and evaluate", None),  # Phase 3
    ("run the adversarial loop", None),  # Phase 4
    ("publish artefacts for the prototype", None),  # Phase 5
    ("build the walkthrough document", [sys.executable, "scripts/build_walkthrough.py"]),
]


def main() -> int:
    env_path = str(REPO)
    failures: list[str] = []
    pending: list[str] = []

    for name, cmd in STAGES:
        if cmd is None:
            pending.append(name)
            continue
        print(f"\n=== {name} " + "=" * max(0, 60 - len(name)))
        started = time.time()
        result = subprocess.run(cmd, cwd=REPO, env={**__import__("os").environ,
                                                    "PYTHONPATH": env_path})
        elapsed = time.time() - started
        status = "ok" if result.returncode == 0 else f"FAILED ({result.returncode})"
        print(f"--- {name}: {status} in {elapsed:.1f}s")
        if result.returncode != 0:
            failures.append(name)

    print("\n" + "=" * 70)
    if pending:
        print("not built yet: " + ", ".join(pending))
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("all implemented stages reproduced cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
