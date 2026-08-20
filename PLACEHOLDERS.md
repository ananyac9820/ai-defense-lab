# Placeholders that must die before submission

Synthesised shapes are exactly what survives to demo day unnoticed. Everything on this
list is something the interface currently *shows* that is not a measured result. Each one
gets a visible badge in the UI until it is real, and this file is the checklist that gets
walked before the repository is submitted.

**Rule: nothing ships with a badge still on it. If it cannot be made real, it comes out
of the demo.**

| # | Placeholder | Where | Badged? | Dies when | Status |
|---|---|---|---|---|---|
| P-01 | Threshold sweep curve — precision, recall and alert rate are extrapolated from a single operating point by a monotone family, not measured at each threshold | `web/src/environments/DetectionSurface.tsx` | yes, on the chart | the evaluation emits a real sweep: metrics recomputed at 40 thresholds and written into the run manifest | **open** |
| P-02 | All fixture metric values — recall, AUC-PR, discriminator AUC, net value | `fixtures/run_manifest.fixture.json` | yes, page-level FIXTURE DATA badge | the prototype reads `artifacts/published/` instead of `fixtures/` (Phase 5) | **open** |
| P-03 | Generation curve G1–G4 — invented progression; only G0 exists | `fixtures/run_manifest.fixture.json` | yes, page-level | the loop runs for real (Phase 4) | **open** |
| P-04 | `metrics_unseen` currently carries the *seen* numbers, because no families are held out yet | `scripts/run_pipeline.py` | not yet — needs one | held-out families and unseen compositions are defined and evaluated separately (Phase 3) | **open** |
| P-05 | Discriminator AUC is `null` — no reference profile on disk to discriminate against | run manifest, Fidelity Mirror | yes, shown as "pending" | IEEE-CIS and PaySim profiles exist and the fidelity harness runs | **open** |
| P-06 | Graph-level features are listed in the Account Nebula but not yet computed by the detector | `web/src/environments/AccountNebula.tsx` | not yet — needs one | the graph level lands in the detector (Phase 3) | **open** |
| P-07 | `level_scores` in `misses.json` are all `null` — the detector is a single model, not three combined | `scripts/run_pipeline.py` | n/a, not surfaced yet | three-level detector with per-level scores (Phase 3) | **open** |
| P-08 | Narrative text on attack vectors is `null`; the narrative layer is not built | `fixtures/attacks.fixture.json` | n/a, not surfaced | Gemini narrative layer (Phase 3) | **open** |

## How a placeholder gets closed

1. The thing it stands in for produces a real number.
2. The badge comes out of the component.
3. The row is marked **closed** here with the commit that did it.
4. `PLACEHOLDERS.md` is read aloud against the running demo the day before submission.
