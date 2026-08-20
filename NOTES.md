# AI Defense Lab — Decision Log

Mastercard Innovation Challenge @ GFF 2026 · Team Code Ops
Deadline 31 Aug 2026 · target submission 29 Aug · 11 days remaining as of 20 Aug 2026.

This file is the running record of decisions and rationale. It becomes the source
material for the .docx walkthrough.

---

## 2026-08-20 — Source documents read

- `AI_Defense_Lab_Strategy.pdf` v3.0 (19 Aug 2026) — authoritative technical spec.
- `33_AI_Era_Frauds_Detailed.docx` — attack taxonomy source, 33 frauds in 6 categories.
- `AI_Defense_Lab_Research_Backed_Plan.docx` — judging insight, real cited cases.
- Mood reference image — depth/glass/bento only. Palette and layout NOT taken from it.

## D-001 — Two corrections to the PDF (from updated challenge page)

1. Solution walkthrough is a **Word document (.docx) only**. Where the PDF says
   "deck or document", it means .docx.
2. Code repository must be hosted on **GitHub** specifically.

## D-002 — Metric reporting: absolute AND lift

**Conflict.** PDF §6.4 requires precision/recall/F1/AUC-ROC/AUC-PR per vector.
The build brief says never report a bare F1, always lift over baseline.

**Resolution.** Absolute metrics live in the results tables (PDF satisfied). Every
*headline* figure in the UI, README and .docx is "X% over baseline".

**Baseline definition (committed, reproducible):** logistic regression on
transaction-level features only. Deliberately a *reasonable* baseline, not a
strawman — a weak baseline inflates lift and is a credibility risk with judges who
know the domain.

## D-003 — Ledger scale vs browser

Full ledger ~2M legitimate / ~20k fraudulent rows in Parquet, used for all metrics.
UI consumes a deterministic 25–50k-row demo slice plus precomputed aggregates.
The 1%-prevalence sparsity is preserved in the slice — it is the point of the
Ledger Stream view.

## D-004 — Non-obvious detection signals: A + B  [user decision, 20 Aug]

Chosen:

- **A — Coercion signature** (headline). Form-interaction telemetry: paste-vs-type
  ratio on payee/amount fields, dwell before confirm, correction/backspace rate,
  "long pause then burst" cadence of a user being read instructions by phone.
  Targets APP fraud (#24), UPI collect scams (#25), deepfake investment scams (#21)
  — the blind spot where user, device, credentials, location and history are all
  genuine.
- **B — Session cadence regularity**. Coefficient of variation and entropy of
  inter-event intervals. Humans jitter, scripts do not. Targets card testing (#9),
  credential stuffing (#5), agentic commerce fraud (#33).

Rejected for now: C — per-account navigation surprisal (Markov model over screen
transitions). Good signal, highest compute cost, kept as a stretch item.

**Circularity caveat — must appear in the walkthrough.** Any signal we invent in our
own simulator is detectable by construction. Three mitigations, all mandatory:

1. Inject at modest effect size with heavily overlapping legit/fraud distributions
   (plenty of legitimate users paste a payee ID).
2. Report the ablation lift with the signal removed, so its contribution is a stated
   number and not a hidden crutch.
3. Calibrate effect sizes against published behavioural-biometrics literature, not
   against values that flatter the result.

If the signal contributes an implausibly large recall gain, that is a red flag to
investigate, not a win to report.

## D-005 — Fidelity harness scope

IEEE-CIS / PaySim / ULB contain no session-timing or interaction telemetry, so the
§5.3 discriminator can only run on the reference-comparable column subset.
Behavioural columns are calibrated against published effect sizes, not against a
dataset. State this explicitly rather than let a headline AUC imply coverage it does
not have.

## D-006 — Reference datasets are never redistributed

IEEE-CIS is competition-licensed. We commit `reference_profile.json` (marginals,
correlation matrix, quantiles) and never the rows. This aligns with the §5 single-
source rule and means clean-clone reproduction needs no Kaggle account.

## D-007 — 3D scope: 4 environments in 3D, 2 in 2D  [user decision, 20 Aug]

**3D (WebGL):** Loop Helix, Account Nebula, Threat Constellation, Detection Surface.
**High-craft 2D:** Ledger Stream, Fidelity Mirror.

Build order within 3D: Loop Helix and Account Nebula first — they carry the novelty
claim and the Mastercard-graph requirement respectively.

The world-inversion mechanic (attacker view / defender view, 800ms morph) applies to
all six. Each has a genuine dual reading, including Fidelity Mirror
("how convincing is my forgery" vs "how faithful is my data") — the inversion is not
decorative anywhere.

Every environment also ships the 2D chart view of the same data, built in Phase 1
against fixtures. It is the reduced-motion path and the venue-machine fallback.

## D-008 — Prototype hosting: live FastAPI  [user decision, 20 Aug]

Primary: FastAPI deployed live, enabling real-time re-scoring in the demo.

**Open risk.** A judge clicking a link needs the server up; free-tier hosts cold-start
in 30–60s. Recommended mitigation (pending confirmation): also produce a static
artefact export as venue fallback. It is nearly free — the artefact bundle is
generated anyway — and protects against cold starts and venue wifi.
Hosting provider still to be chosen (needed by Phase 5).

## D-009 — LLM reproducibility

Red-team strategist and narrative layer cache all outputs to the repo. Clean-clone
reproduction runs from cache; `--regenerate` flag for live runs. Provider/key still
to be confirmed.

## D-010 — Net value protected: cost constants

Defaults pending confirmation: ₹250 per manual review; average fraud value taken
from the simulator's own distribution. Both configurable, both stated beside the
metric.

## D-011 — Palette (from build brief, adopted)

Base #070B0F · Surface rgba(18,26,33,0.55) · Defender #17E88F / #3FD8E8 ·
Attacker #FFAA2B / #FF3D71 · Text #E8EDF0 · Muted #6B7C8A. Dark only, no light mode.
Accents cross over on inversion so colour always encodes which side you are viewing.

## D-012 — Fraud implementation priority

**Phase 2 thin slice (5), one per detection level, five of seven channel axes:**

| # | Fraud | Level it proves |
|---|---|---|
| 9 | Card testing / BIN attack | Session |
| 27 | Mule networks | Graph |
| 24 | APP fraud (UPI) | Behavioural |
| 2+4 | ATO via SIM swap / OTP intercept | Transaction |
| 1+3 | Synthetic identity → deepfake video-KYC | Cross-table |

**Phase 3 adds:** #16 deepfake video-call CEO fraud (Arup $25.6M), #21 deepfake
celebrity investment scam (Pune ₹43 lakh), #28 structuring, #13 friendly fraud
(45% Mastercard stat, uses the narrative layer as a real feature), #33 agentic
commerce fraud (PDF §4.1: do not omit), #32 adversarial probing of the detector.

**#32 note.** "Fraudster probes the model for blind spots" *is* our closed loop seen
from the other side. Implementing it makes the red-team strategist a modelled
attacker in the taxonomy rather than only a build artefact.

**Deliberately excluded, with reasons** (§4.1 requires reasoned empty cells):
#10 skimming, #11 Magecart, #22 fake UPI apps, #29 check fraud, #6 forged documents.
Their footprint is physical, in-page JS, in-app, or an image — not a
transaction/session/graph signature. Simulating them would mean inventing a data
footprint we cannot defend.

## D-013 — Scope and safety boundary (PDF §9, restated)

Synthetic DATA only: transaction records, session events, graph edges. No voice
cloning, no phishing generators, no deepfake code, nothing that can reach a live
endpoint. Attack primitives are simulated as their data footprint only. Stated in
the README and in the walkthrough.

## Environment facts (verified 20 Aug 2026)

node v24.14.0 · npm 11.9.0 · git 2.53.0 · Python 3.14.3 (also 3.13, 3.10 present).
xgboost 3.4.1, lightgbm 4.7.0, shap 0.52.0 all resolve on 3.14.
`gh` CLI NOT installed — repo creation needs `gh` installed or the GitHub web UI.

---

# Phase 1 — Foundations (20 Aug 2026)

## D-014 — Working location and remote

Repository lives at `C:\Users\anany\dev\ai-defense-lab`, moved out of Downloads.
Remote `origin` set to https://github.com/ananyac9820/ai-defense-lab. Commits are made
locally; pushes happen through the browser. `gh` is not installed and is not needed.

Repo topics to set when the remote is populated: `fraud-detection`, `adversarial-ml`,
`synthetic-data`, `payment-security`.

## D-015 — Four contracts, not three

`run_manifest.json` was added alongside the PDF's three. The prototype needs one artefact
that describes a run — seeds, config hash, prevalence, per-generation metrics, fidelity,
artefact paths — and inventing it under pressure in Phase 5 is exactly the late
integration failure S10 rates Severe. It is the only file the frontend must understand in
order to render every view.

Ledger went from three tables to six. S5.1's entity layer has to be materialised —
`accounts`, `devices`, `merchants` — or no history-dependent feature is computable at all.

## D-016 — Coverage is stated along the axes, never as a fraction of the chain space

**Found during Phase 1, and it would have become an embarrassing slide.**

The first grammar admitted 7,566,765 valid chains. PDF S4.2 says "roughly twenty
primitives generate several hundred distinct, valid attack chains", and the intuitive
reading of the coverage claim is implemented-over-valid. At 5 implemented that fraction is
1 in 1.5 million, which reads as failure rather than as a deliberately small,
axis-spread selection. Any grammar worth having has this property: M/N is a number that
can only ever look bad.

Two changes:

1. Added `max_per_stage: 2` to the composition rules. Repeating a stage more than twice is
   parameter variation, not a distinct chain. This brings the space to **444,573** valid
   chains — still large enough for the strategist to have room to search, and no longer
   inflated by degenerate repetition.
2. Coverage is reported four ways that mean something, via `coverage_report()`:
   primitives used of 19, stage transitions used of 15 possible, grid cells populated of
   343 (7 channels × 7 capabilities × 7 objectives), and channels covered of 7. The chain
   space is quoted as a **capability statement** — the size of the space the red-team
   strategist searches — which is how S4.2 actually phrases it.

Thin slice at generation 0: 14/19 primitives, 9/15 transitions, 5/343 grid cells,
5/7 channels, 5/7 capabilities, 5/7 objectives.

## D-017 — AnimatePresence removed from the environment switcher

`AnimatePresence mode="wait"` holds the exiting child until its exit animation resolves.
Under React 19 StrictMode with a Suspense boundary inside, it never resolved: the rail
highlight moved but the view did not change. Replaced with a keyed remount and a fade-in.
The real cross-dissolve between environments arrives with the 3D camera in Phase 5.

Caught by driving the built page rather than by reading the code — worth remembering as
the check for the rest of the interface work.

## Phase 1 results

- 49 tests passing, 1 xfail. The xfail is the provenance test, marked
  `raises=ModuleNotFoundError, strict=True` so it can only pass silently for the right
  reason and pytest will fail the day the simulator lands and the marker is still there.
- Fixtures byte-reproducible from seed 20260831; the reproduction test regenerates and
  compares against the committed bytes.
- Six 2D environments rendering against fixtures. Perspective inversion verified live:
  accent crosses `#17e88f` → `#ffaa2b`, copy inverts ("the topology" → "the route").
- Production build 3.5s, ~220 KB gzipped, three.js already split into its own chunk so
  the 2D path never downloads the 3D runtime.
- Reference profiles both pending — awaiting the IEEE-CIS and PaySim files on disk. The
  profiler runs and records them as unavailable rather than failing.

## Bug found and fixed in Phase 1

Mule-ring fixture generator emitted a self-loop when the ring's sink account was also
treated as a hop. Caught by the referential-integrity test, not by eye.

---

# Phase 2 — Thin vertical slice (20 Aug 2026)

Pipeline executes start to finish: taxonomy → simulator → features → leak-free split →
baseline → levelled detector → metrics → misses.json → run manifest → published artefacts.

## D-018 — Detection is scored per attack instance, not per row

**Contract change, made after the first end-to-end run. Flagging rather than burying.**

`instance_id` added to `transactions` and `sessions` in the ledger contract, and to the
label-column list.

Two reasons, and the first is a straight contract bug: `misses.json` already required an
`instance_id`, and the ledger had no way to name one. Phase 2 was filling it with a
transaction id, which misrepresents what a miss is.

The second is that row-weighted recall is the wrong unit and flatters the result badly. A
card-testing sweep emits twenty rows and counts twenty times; an authorised push payment
emits one and counts once. So a row metric mostly reports how well the detector finds the
noisiest vector — and a fraud team that catches nineteen of twenty probes after the money
has gone has caught nothing. An instance now counts as detected when any of its rows
scores above the operating threshold, which is what an alert queue actually does. Row
figures are still printed alongside, never instead.

## D-019 — Three leaks found by running it, not by reading it

**1. Mules occupied a contiguous block of the account id space.** `mule_pool` was
`account_ids[-n_mules:]`, so the raw identifier predicted the label at AUC 0.72 on its
own. An id that encodes ground truth is a leak nothing downstream can undo. Mules are now
a uniform random choice across the id space, with a regression test.

**2. Attack chains ran off the end of the window.** `World.when()` sampled uniformly
across the whole simulation period, so the later stages of long chains landed past the end
of legitimate traffic. The tail of the ledger was disproportionately fraudulent and
transaction-id ordering alone predicted the label at AUC 0.60. Attack start times now
reserve a 50-day horizon.

**3. One vector supplied 80% of the fraudulent rows.** The card-testing sweep emitted up
to 60 rows per instance while the APP-fraud vector emitted two, so the first run reported
AUC-PR 0.999 and it was almost entirely V001. Sweep size is now capped at 6–26 probes, and
instance-level scoring is the real fix.

## D-020 — The provenance test runs under the leak-free split

Under a random split the test measured burst memorisation rather than provenance: every
individual formatting feature sat at chance while the combination reached 0.69, because
fraudulent rows arrive in bursts that share a timestamp and occupy adjacent ids, and a
random split puts half a burst in train and half in test.

It now uses `time_and_account_split`, the same protocol as the real detector. Two things
are also excluded from its feature set, both after a failing run:

- **Null patterns.** A bank transfer genuinely has no merchant, and fraud favours transfer
  rails, so nullity is signal about the transaction rather than about the writer.
- **Raw entity identifiers.** Handed the full account id, a tree memorises which accounts
  are mules — identity memorisation, which the account-disjoint split exists to prevent,
  not a formatting artefact.

What remains is what the test is actually for: sub-second precision, amount rounding,
rupee digit, and transaction-id ordinal. All at chance, individually and combined.

## D-021 — Performance, and where it went

The first 300k run did not finish in ten minutes. Three hot spots, all found by profiling
rather than guessing:

| Hot spot | Cost | Fix |
|---|---|---|
| `World.merchant()` filtering the merchant DataFrame per call | 82% of simulator runtime | prebuilt index by MCC |
| session aggregates via `groupby.apply` with a Python function per session | minutes on 140k sessions | one pass of vectorised `groupby.agg`; entropy rewritten as `log S − (Σ g log g)/S` so it comes out of two sums |
| expanding per-account mean/std via `transform(lambda)` | seconds per run, worse at scale | cumulative sums |

Feature building went from unfinishable to 5.9s on 300k rows. The simulator is now ~1ms
per transaction — 300k in ~4.5 minutes, so a full 2M run is roughly half an hour. That is
tolerable as a one-off but not for iteration; if Phase 3 needs repeated full-scale runs it
gets vectorised.

## D-022 — Right-censoring at the observation boundary

The horizon added in D-019 fixed one bias and created a worse one. With no attacks
starting in the final fifty days, the time-ordered split had almost no fraud in its test
half: test prevalence fell to 0.079% with two instances, and the detector reported
AUC-PR 1.000 and a lift of +16,293%. A number that absurd is a gift - it is obvious
enough to investigate rather than believe.

Attack start times are uniform across the window again. Chains still in flight when the
window closes are truncated by a single filter applied to both classes, which is what a
real observation window does. Partially observed chains near the edge are realistic
right-censoring, not a defect.

## Phase 2 results

300k transactions, 25k accounts, seed 20260831, prevalence 0.924% in the test window.
Baseline is logistic regression on transaction fields only.

| Variant | Precision | Recall | F1 | AUC-PR | Alert rate | Lift (AUC-PR) |
|---|---|---|---|---|---|---|
| baseline | 0.079 | 0.885 | 0.145 | 0.152 | 10.37% | — |
| transaction only | 0.754 | 0.876 | 0.810 | 0.912 | 1.07% | +501% |
| **transaction + session** | **0.822** | **0.949** | **0.881** | **0.964** | **1.07%** | **+534%** |
| minus coercion signal | 0.825 | 0.949 | 0.883 | 0.961 | 1.06% | +533% |
| minus cadence signal | 0.805 | 0.936 | 0.866 | 0.964 | 1.07% | +535% |

Instance recall 94.9% over 39 instances. Scoring latency p50 3.2ms, p99 5.9ms - inside a
payment authorisation budget. Operating threshold 0.0029, chosen on train by net value.

Per vector, instance detection: V001 5/5, V002 15/15, V003 7/9, V004 6/6, V005 4/4. The
only vector the detector misses is the coercion one, which is the expected shape.

## What these numbers are NOT yet worth

- **38 attack instances in the test window.** Every per-vector figure is built on single
  digits. Nothing here is publishable until the full-scale run.
- **The coercion signal contributes nothing measurable**, because only the APP-fraud
  vector produces payee-entry events and it supplies about five instances per run. Seven
  fraudulent payee events against thirteen thousand legitimate ones is realistic scarcity,
  and it is also too little to learn from. Phase 3 needs either far more volume or an
  instance mix weighted towards the behavioural vectors.
- **`metrics_unseen` currently carries the seen numbers** because no families are held
  out yet. Tracked as P-04.
- **The split discards 42% of rows** to satisfy both conditions at once. Structurally
  correct, but worth stating in the walkthrough rather than letting someone discover it.

---

# D-023 — Interface rebuilt as a technical dossier (20 Aug 2026)

**This reverses D-011 and the "dark only" line in the original design spec.** The new
reference is a paper-light annotated blueprint, and the thirty-item list of AI-slop tells
rules out most of what the first interface was made of. Both instructions are newer than
the spec, so both win. Flagged rather than silently applied: if the ink ground is wanted
back, the whole palette is four tokens.

## What the interface is now

Warm paper (#F3F2EE, not pure white), ink (#14140F), one continuous fixed hairline grid
with registration marks behind every section. Type is Archivo for display and IBM Plex
Mono for the annotation voice. Content is one scrolling document: masthead, six numbered
sections, colophon. Sections overlap into each other and the ground never restarts, so
there is no seam to see. Terms and privacy are the only separate routes.

The inversion survives intact and is now cleaner: one spot colour, viridian #0F5C4A for
the defence and vermilion #C43D18 for the attack. Everything else is paper and ink, so
the swap is the only colour event on the page and cannot read as decoration.

## Audited against the list, in the browser rather than by eye

Zero violations for drop shadows, radial gradients, backdrop blur, border radius above
4px, and CSS transitions. Zero emoji. Zero em dashes. Zero "it is not X, it is Y"
constructions. Background is not pure white. Fonts are not Inter, Geist or Space Grotesk.

Specific replacements: bento grids became an annotated two-column layout on a drawing
grid; glass panels became bordered spec plates with title bars; the icon set became
drawn marks, leader lines and hatching; hover became an instant state change with no
transition; skeleton loaders are now real and shown while artefacts load; terms and
privacy notices exist and say what is actually true of this artefact.

Bundle dropped from 220KB to 73KB gzipped, because the chart library went with the
redesign. Every figure is now hand-drawn SVG, which suits hairlines better than a
charting default ever would.

## D-024 — The frontend reads live artefacts

The columnar demo slice arrived before the frontend knew how to read it, so the first
load after the redesign failed on a shape mismatch. One adapter in lib/data.ts now
normalises both the row-form fixture and the columnar slice, and the views are unchanged.
The prototype is currently rendering real pipeline output, not fixtures, and the fixture
badge correctly does not appear.

---

# Phase 3 (in progress) — the graph level

## D-025 — Graph features, causal and windowed

Nine features in `adl/defend/graph_features.py`: fan-in and fan-out over 24 hours, degree
ratio, pass-through score, residence time, short-cycle membership, shared-device degree,
counterparty age, beneficiary novelty.

Every one is strictly backward looking. Each transaction sees only the subgraph that
existed before it, because a statistic computed over the whole graph lets a transaction
on day three see money that moved on day ninety. That is the graph version of exactly the
leak the time split exists to prevent, and it would be invisible in the split assertions.

Single-feature AUC on a 40k smoke run: residence time 0.870 where defined, degree ratio
0.625, pass-through 0.624, cycle membership 0.557.

## Result: what the graph level contributes

250k transactions, 20k accounts, test prevalence 1.132%.

| Variant | Precision | Recall | AUC-PR | Lift over baseline |
|---|---|---|---|---|
| baseline (LR, transaction only) | 0.079 | 0.847 | 0.113 | — |
| transaction only | 0.759 | 0.897 | 0.915 | +709% |
| transaction + session | 0.866 | 0.909 | 0.956 | +745% |
| **all three levels** | **0.826** | **1.000** | **0.994** | **+778%** |
| all levels minus graph | 0.866 | 0.909 | 0.956 | +745% |
| all levels minus coercion signal | 0.801 | 1.000 | 0.993 | +778% |
| all levels minus cadence signal | 0.766 | 1.000 | 0.995 | +780% |

**The graph level contributes +0.038 AUC-PR and +9 points of recall** over transaction and
session evidence combined. That is the number that answers the brief's first requirement,
and it is isolated rather than asserted: `all_levels_minus_graph` reproduces the
`txn+session` row exactly, which is the check that the ablation is doing what it says.

Precision falls slightly when the graph level is added, because it catches more at a
lower threshold. Net value protected rises 16%, which is the trade the operator actually
cares about.

## Still not publishable

Instance recall is now 100% over 37 instances. Perfect detection on thirty-seven
incidents is not a result, it is a sample size. Nothing changes until the full-scale run
and held-out families, which are the next two items.

The coercion signal still contributes nothing measurable. Removing it costs 0.001 AUC-PR.
The cadence signal is the same. Both are starved of support at this scale.
