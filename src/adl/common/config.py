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

from .paths import CONFIG_PATH


@lru_cache(maxsize=4)
def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return cfg


def config_hash(path: Path | None = None) -> str:
    """SHA-256 of the raw config bytes, normalised for line endings.

    Normalisation matters on Windows: a checkout with CRLF would otherwise produce a
    different hash from the same file on CI.
    """
    path = path or CONFIG_PATH
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
