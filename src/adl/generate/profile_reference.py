"""Profile the reference datasets. Emit statistics; never rows.

PDF S5: the public dataset calibrates distributions and never supplies a row to the
ledger. NOTES.md D-006 makes that structural - the rows stay out of the repository and
only this profile is committed.

Two profiles, one per structure type (user decision, 2026-08-20):

    ieee_cis  ->  card / CNP transaction structure
    paysim    ->  account-to-account transfer structure and the mule graph

Either may be absent. The profile records which were available and the fidelity section
of the walkthrough states the gap rather than papering over it.

    python -m adl.generate.profile_reference
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from adl.common.config import load_config
from adl.common.paths import ARTIFACTS_DIR

MAX_ROWS = 400_000
"""Cap on rows read. The profile is summary statistics; reading the full IEEE-CIS file
buys precision nobody will notice and costs minutes on every run."""

QUANTILES = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 0.999]


def _numeric_profile(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"kind": "numeric", "n": 0}
    return {
        "kind": "numeric",
        "n": int(clean.size),
        "mean": float(clean.mean()),
        "std": float(clean.std()),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "quantiles": {str(q): float(clean.quantile(q)) for q in QUANTILES},
        "zero_fraction": float((clean == 0).mean()),
        "null_fraction": float(series.isna().mean()),
    }


def _categorical_profile(series: pd.Series, top: int = 40) -> dict[str, Any]:
    counts = series.astype("string").value_counts(normalize=True, dropna=True).head(top)
    return {
        "kind": "categorical",
        "n_unique": int(series.nunique(dropna=True)),
        "null_fraction": float(series.isna().mean()),
        "top": {str(k): round(float(v), 6) for k, v in counts.items()},
    }


def profile_frame(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """Marginals plus the correlation matrix.

    PDF S5.3 is explicit that joint structure is where naive generators fail, so the
    correlation matrix matters more than any per-column statistic. It is the thing the
    simulator is calibrated against and the thing the fidelity harness compares.
    """
    columns: dict[str, Any] = {}
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series) and series.nunique(dropna=True) > 12:
            columns[col] = _numeric_profile(series)
        else:
            columns[col] = _categorical_profile(series)

    numeric = df.select_dtypes(include=[np.number])
    numeric = numeric.loc[:, numeric.nunique() > 1]
    corr = numeric.corr(method="spearman").round(5) if numeric.shape[1] > 1 else pd.DataFrame()

    return {
        "name": name,
        "n_rows_profiled": int(len(df)),
        "columns": columns,
        "correlation": {
            "method": "spearman",
            "columns": list(corr.columns),
            "matrix": corr.to_numpy().tolist() if not corr.empty else [],
        },
    }


def load_reference(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path).head(MAX_ROWS)
    return pd.read_csv(path, nrows=MAX_ROWS, low_memory=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ARTIFACTS_DIR / "reference_profile.json")
    args = parser.parse_args(argv)

    cfg = load_config()
    profiles: dict[str, Any] = {}
    missing: list[str] = []

    for name, spec in cfg["fidelity"]["reference_profiles"].items():
        path = spec.get("path")
        if not path or not Path(path).exists():
            missing.append(name)
            profiles[name] = {
                "name": name,
                "available": False,
                "serves_channels": spec["serves_channels"],
                "reason": "file not present; set fidelity.reference_profiles.%s.path" % name,
            }
            print(f"  {name:10s} MISSING - no path configured or file absent")
            continue

        df = load_reference(Path(path))
        profile = profile_frame(df, name)
        profile |= {"available": True, "serves_channels": spec["serves_channels"]}
        profiles[name] = profile
        print(f"  {name:10s} profiled {len(df):,} rows, {df.shape[1]} columns")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "contract_version": "0.1.0",
                "note": (
                    "Summary statistics only. No reference row is ever written here or into "
                    "the ledger - the public datasets calibrate distributions and nothing else."
                ),
                "max_rows_profiled": MAX_ROWS,
                "profiles": profiles,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out}")

    if missing:
        print(
            "\nProceeding without: "
            + ", ".join(missing)
            + ".\nThe fidelity section must state this gap explicitly - the discriminator can "
            "only be run\non channels a profile covers."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
