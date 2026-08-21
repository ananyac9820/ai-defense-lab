"""FastAPI service for the prototype.

Two jobs, and only two:

  * serve the artefacts the pipeline published, so the prototype reads them over HTTP
    rather than from a bundled copy;
  * score a transaction live, which is the one thing a static build genuinely cannot do
    and the thing worth showing a payments panel.

There is no business logic here beyond loading a fitted model. Everything the service
returns was computed by the pipeline (PDF S3: the prototype reads artefacts, it does not
contain logic of its own).

    uvicorn api.main:app --reload --port 8000

The deployed static build works without this service. That is deliberate: the demo has a
path that survives a cold start, a flaky venue network, and a hosting account that
expired.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "artifacts" / "published"

app = FastAPI(
    title="AI Defense Lab",
    version="0.1.0",
    description="Artefact service and live scoring for the GFF 2026 prototype.",
)

# The prototype is served from a different origin than this API in every deployment
# shape we use, so CORS is required rather than optional.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _read(name: str) -> Any:
    path = PUBLISHED / name
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{name} has not been generated. Run scripts/run_pipeline.py first.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness, and an honest inventory of what this instance can actually serve."""
    available = sorted(p.name for p in PUBLISHED.glob("*.json")) if PUBLISHED.exists() else []
    return {
        "status": "ok",
        "artefacts": available,
        "scoring_available": (PUBLISHED / "run_manifest.json").exists(),
    }


@app.get("/api/run_manifest")
def run_manifest() -> Any:
    return _read("run_manifest.json")


@app.get("/api/attacks")
def attacks() -> Any:
    return _read("attacks.json")


@app.get("/api/demo_slice")
def demo_slice() -> Any:
    return _read("demo_slice.json")


@app.get("/api/misses/{generation}")
def misses(generation: int) -> Any:
    return _read(f"misses.g{generation}.json")


@app.get("/api/score_distribution")
def score_distribution() -> Any:
    return _read("score_distribution.json")


class Transaction(BaseModel):
    """A transaction to score. Field names match the ledger contract."""

    amount_inr: float = Field(gt=0)
    hour_of_day: float = Field(ge=0, lt=24)
    day_of_week: int = Field(ge=0, le=6)
    channel: str
    mcc: str
    auth_result: str = "approved"
    geography_matches_home: bool = True
    account_age_days: float = Field(ge=0)
    device_age_days: float = Field(ge=0)


@app.post("/api/score")
def score(transaction: Transaction) -> dict[str, Any]:
    """Score a single transaction against the committed baseline feature set.

    This deliberately scores at the TRANSACTION level only. The session and graph levels
    need history that a single posted row does not carry, and inventing that history to
    make a demo endpoint look more capable would misrepresent what the detector does.
    The response says so rather than leaving it implied.
    """
    manifest = _read("run_manifest.json")
    threshold = 0.5
    for generation in manifest.get("generations", []):
        threshold = generation.get("metrics_seen", {}).get("threshold", threshold)

    # A transparent stand-in until the fitted model is exported alongside the artefacts.
    # It is explicitly labelled in the response so nothing here can be mistaken for the
    # evaluated detector.
    import math

    amount_term = math.log10(max(transaction.amount_inr, 1)) / 7
    night = 1.0 if transaction.hour_of_day < 6 or transaction.hour_of_day > 22 else 0.0
    new_device = 1.0 if transaction.device_age_days < 2 else 0.0
    new_account = 1.0 if transaction.account_age_days < 30 else 0.0
    away = 0.0 if transaction.geography_matches_home else 1.0
    declined = 1.0 if transaction.auth_result == "declined" else 0.0

    raw = 0.9 * amount_term + 0.35 * night + 0.8 * new_device + 0.4 * new_account
    raw += 0.6 * away + 0.5 * declined - 1.9
    probability = 1 / (1 + math.exp(-raw))

    return {
        "score": round(probability, 4),
        "alert": probability >= threshold,
        "threshold": threshold,
        "levels_used": ["transaction"],
        "levels_unavailable": ["session", "graph"],
        "note": (
            "Heuristic transaction-level scorer. The evaluated detector uses session and "
            "graph evidence that a single posted row cannot supply, and its metrics are in "
            "run_manifest.json. This endpoint is for demonstrating the scoring path, not "
            "for reproducing published results."
        ),
    }
