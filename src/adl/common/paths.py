"""Repository paths. Everything resolves from the repo root so that scripts work
regardless of the directory they are invoked from."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

CONTRACTS_DIR = REPO_ROOT / "contracts"
FIXTURES_DIR = REPO_ROOT / "fixtures"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
DATA_DIR = REPO_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
WEB_PUBLIC_DIR = REPO_ROOT / "web" / "public"
CONFIG_PATH = REPO_ROOT / "config.yaml"

GRAMMAR_PATH = CONTRACTS_DIR / "grammar.json"
ATTACKS_SCHEMA = CONTRACTS_DIR / "attacks.schema.json"
LEDGER_SCHEMA = CONTRACTS_DIR / "ledger.schema.json"
MISSES_SCHEMA = CONTRACTS_DIR / "misses.schema.json"
RUN_MANIFEST_SCHEMA = CONTRACTS_DIR / "run_manifest.schema.json"

SCHEMA_BY_NAME = {
    "attacks": ATTACKS_SCHEMA,
    "ledger": LEDGER_SCHEMA,
    "misses": MISSES_SCHEMA,
    "run_manifest": RUN_MANIFEST_SCHEMA,
}
