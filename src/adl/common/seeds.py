"""Deterministic seeding.

PDF S10 rates a non-reproducible repository a Moderate risk and S12 requires every
reported number to be regenerable with one command. Nothing in this project may call
an unseeded RNG. Every component takes its generator from :func:`rng_for`, which
derives a stable sub-seed from the master seed and a component name, so adding a new
component never shifts the draws of an existing one.
"""

from __future__ import annotations

import hashlib

import numpy as np


def derive_seed(master_seed: int, component: str) -> int:
    """Stable 32-bit sub-seed for a named component.

    Uses BLAKE2b rather than :func:`hash`, which is salted per process on CPython and
    would silently break reproducibility across runs.
    """
    digest = hashlib.blake2b(
        component.encode("utf-8"), digest_size=8, key=str(master_seed).encode("utf-8")
    ).digest()
    return int.from_bytes(digest, "big") % (2**32)


def rng_for(master_seed: int, component: str) -> np.random.Generator:
    """The only sanctioned way to obtain a random generator in this codebase."""
    return np.random.default_rng(derive_seed(master_seed, component))
