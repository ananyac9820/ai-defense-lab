"""Config loading and hashing.

The config hash goes into run_manifest.json so that two runs claiming the same
numbers can be shown to have used the same settings.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_PATH, REPO_ROOT

# The sources whose content determines what a run produces. Hashing these gives a
# clone-proof answer to "were these artefacts made by this code", which a modification
# time cannot: git does not preserve mtimes, so on a fresh clone every file carries the
# same timestamp and any ordering between them is an accident.
PRODUCING_SOURCES = (
    "src/adl/generate/simulator.py",
    "src/adl/generate/primitives.py",
    "src/adl/defend/features.py",
    "src/adl/defend/graph_features.py",
    "src/adl/defend/models.py",
    "src/adl/evaluate/metrics.py",
    "src/adl/evaluate/splits.py",
    "src/adl/evaluate/protocol.py",
    "src/adl/loop/strategist.py",
    "src/adl/loop/validation.py",
    "config.yaml",
)


@lru_cache(maxsize=4)
def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return cfg


def source_digest() -> str:
    """SHA-256 over the sources that determine a run's output.

    Recorded into every manifest so the audit can ask whether the artefacts were produced
    by the code currently in the repository, on any machine, including one that cloned
    five seconds ago.
    """
    h = hashlib.sha256()
    for name in PRODUCING_SOURCES:
        path = REPO_ROOT / name
        if path.exists():
            h.update(name.encode())
            h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def config_hash(path: Path | None = None) -> str:
    """SHA-256 of the raw config bytes, normalised for line endings.

    Normalisation matters on Windows: a checkout with CRLF would otherwise produce a
    different hash from the same file on CI.
    """
    path = path or CONFIG_PATH
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
