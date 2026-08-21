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

---

# Full-scale run, 2M transactions (20 Aug 2026)

1,998,721 transactions, 40,000 accounts, 19,410 fraudulent (0.971%), 936,500 sessions,
384,175 graph edges. Test window prevalence 0.827%, 277 seen instances and 36 held-out
instances. These are the first numbers in the project built on real sample sizes.

| Variant | Precision | Recall | AUC-PR | Lift vs tuned baseline |
|---|---|---|---|---|
| BASELINE xgboost tuned, txn only | 0.372 | 0.830 | 0.801 | reference |
| floor: logistic regression | 0.054 | 0.803 | 0.160 | -80% |
| txn only | 0.761 | 0.774 | 0.829 | +4% |
| txn + session | 0.759 | 0.847 | 0.886 | +11% |
| **all three levels** | **0.997** | **0.806** | **0.977** | **+22%** |
| all levels minus graph | 0.759 | 0.847 | 0.886 | +11% |
| all levels minus coercion signal | 0.996 | 0.811 | 0.976 | +22% |
| all levels minus cadence signal | 0.994 | 0.806 | 0.973 | +22% |

Seen instance recall 88.1% over 277 instances. Per vector: V001 43/43, V002 126/157
(80.2%), V003 52/54, V005 23/23. Mule layering is the weakest, which is the expected
shape.

## D-026 — The graph level is the result

+0.091 AUC-PR over transaction and session evidence combined, and precision from 0.759 to
0.997 at a lower alert rate. `all_levels_minus_graph` reproduces `txn+session` to four
decimal places again, which is the check that keeps the claim falsifiable.

## D-027 — The held-out gap collapsed, and the earlier number was noise

At 250k the held-out family scored AUC-PR 0.111 against 0.994 seen, on **one instance**.
At 2M it scores **0.979 against 0.977 seen, on 36 instances** — the held-out family is
detected slightly *better* than the families the detector trained on.

The earlier gap was a sample-size artefact and should never have been treated as a
finding. Recording that plainly because it was briefly the headline.

**Why it generalises.** V004's chain is
`clone_voice_otp -> register_device -> provision_token -> drain_single`. Three of its four
primitives appear nowhere in training. The fourth, `drain_single`, is the extraction step
and it is shared with every trained family.

So the detector is not recognising attack families. It is recognising the **extraction
footprint** — a large transfer to a novel beneficiary with a particular graph signature —
and it does not care how the access was obtained. Holding out acquisition and
establishment stages withholds nothing that the model was using.

That is a genuine and defensible finding, and a more interesting one than a generalisation
gap: fraud that moves money the same way is caught the same way. It also says the current
held-out test is measuring the wrong thing.

**What a real unseen test needs.** Hold out an *extraction* primitive so the money
movement itself is novel, and hold out compositions as PDF S6.3 separately requires. Both
are now cheap because chains execute generically.

## D-028 — Separability at scale

    fraud_p05             0.2212        legit_p99      0.0033
    fraud_p50             1.0           legit_p99_9    0.1899
    fraud_above_legit_p99 0.988         separation_gap +0.0313

An overlap band exists now but is thin: under 5% of fraud scores below the 99.9th
percentile of legitimate traffic. Seen instance recall at 88.1% is inside the agreed
target band; `fraud_above_legit_p99` at 0.988 is above the 0.85-0.95 target.

`fraud_within_2x_threshold` was removed. With the net-value threshold at 0.985 it read
1.0 by construction and measured nothing. Replaced with `fraud_in_overlap_band` and
`separation_gap`, both independent of where the threshold happens to sit.

## D-029 — Coercion signal: negative finding confirmed at scale

Removing it moves AUC-PR from 0.977 to 0.976 and *improves* F1 from 0.891 to 0.894. With
1,420 fraudulent rows in the test window the signal now has real support, and it still
contributes nothing. The cadence signal contributes 0.004 AUC-PR, which is inside noise.

Reported as a negative result. No effect size has been touched at any point.

---

# D-030 — Holding out the extraction found the boundary (20 Aug 2026)

Preview at 300k, ahead of the full-scale confirmation. Three holdouts, each withholding
something different.

| Held out | What is novel | Instance detection |
|---|---|---|
| V004 SIM-swap takeover | acquisition and establishment; extraction is `drain_single`, seen | **100%** |
| V007 hijacked agent | `compromise_agent` + `agentic_purchase`, both unseen | **100%** |
| V006 merchant collusion | `merchant_collusion_payout`, unseen | **20%** (1 of 5) |
| V008 composition | nothing; four seen primitives in an unseen order | **100%** |

Seen instance recall 96.4%. Held-out family recall 75.0% overall, entirely because of
V006.

**The boundary is the rail, not the family and not the composition.** V004 changes how
access is obtained and is caught, because the extraction still looks like every other
extraction. V008 rearranges seen primitives and is caught, because recombination does not
change what any of them emit. V007 introduces two unseen primitives and is still caught,
because an agentic purchase is still a purchase: anomalous amount, unfamiliar merchant,
device with no history.

V006 evades because it extracts through a **merchant acquiring account**. Value never
touches a peer-to-peer transfer rail, so the graph signature the detector learned - a
large movement to a novel beneficiary, short residence, fan-in - simply is not there.

This sharpens the Defend claim rather than weakening it. The detector generalises across
attack families and across recombinations of known primitives, and it fails when the
extraction moves to a rail it has never seen. That is a specific, falsifiable statement
about where supervised detection stops, and it is the argument for the loop: the thing
that finds V006-shaped gaps is an adversary searching the grammar, not a bigger training
set.

## D-031 — The separability nudge worked

Extraction now routes through a category the victim already uses 55% of the time.

| | before | after |
|---|---|---|
| fraud_above_legit_p99 | 0.988 | **0.913** |
| fraud_in_overlap_band | <0.05 | **0.173** |
| separation_gap | +0.031 | **-0.011** |
| fraud_p50 | 1.0 | 0.722 |

Inside the agreed 0.85-0.95 band, with a genuine overlap corridor rather than an empty
one. Stopping here as agreed; this was one nudge, not a campaign.

## Two silent bugs, both found by running rather than reading

**The vector filter still tested the retired registry.** `vector_cycle` filtered on
membership of the hardcoded `ATTACKS` dict rather than on whether the chain's primitives
are implemented. All three new vectors were counted in the taxonomy, validated against
the contract, and emitted nothing whatsoever. Coverage would have been reported as 7/7
channels while two of those channels had no data behind them.

**The ledger cache key ignored the attack set.** Keyed on seed and size only, so the
first run after adding three vectors silently reused a ledger generated before they
existed. The evaluation ran to completion and reported on the wrong experiment. The key
now includes a digest of vector ids, chains, parameters and holdout flags.

Both belong in the walkthrough's methodology section. A cache that returns stale results
and a filter that drops vectors are exactly the failures that produce numbers for code
that never ran.

---

# Full-scale confirmation, 2M transactions (21 Aug 2026)

1,998,745 transactions, 40,000 accounts, 19,481 fraudulent (0.975%). Test window
prevalence 0.844%, with 241 seen instances, 83 held-out family instances and 23 held-out
composition instances. Eight vectors, three holdout regimes.

## The ablation

| Variant | Precision | Recall | AUC-PR | Lift vs tuned baseline |
|---|---|---|---|---|
| BASELINE xgboost tuned, txn only | 0.681 | 0.810 | 0.829 | reference |
| floor: logistic regression | 0.072 | 0.747 | 0.178 | -79% |
| txn only | 0.772 | 0.816 | 0.862 | +4% |
| txn + session | 0.746 | 0.886 | 0.912 | +10% |
| **all three levels** | 0.667 | **0.965** | **0.967** | **+17%** |
| all levels minus graph | 0.746 | 0.886 | 0.912 | +10% |
| all levels minus coercion signal | 0.639 | 0.974 | 0.976 | +18% |
| all levels minus cadence signal | 0.626 | 0.976 | 0.977 | +18% |

The graph level contributes **+0.055 AUC-PR and +7.9 points of recall**.
`all_levels_minus_graph` reproduces `txn+session` to four decimals for the third run
running, which is what keeps the claim falsifiable.

The tuned baseline is stronger at this scale (AUC-PR 0.829 against 0.801 at 250k), so the
headline lift falls from +22% to **+17%**. Reporting the smaller number.

## D-032 — V006 confirmed. The boundary is the extraction rail.

| Held out | What is novel | Instances | Detection |
|---|---|---|---|
| V004 SIM-swap takeover | acquisition and establishment | 27 | 100% |
| V007 hijacked agent | two unseen primitives, purchase rail | 35 | 100% |
| **V006 merchant collusion** | **unseen extraction rail** | **21** | **33.3%** |
| V008 composition | seen primitives, unseen order | 23 | 100% |

Seen instance recall 99.6% over 241 instances. Held-out family recall 83.1%, entirely
because of V006. Held-out composition recall 100%.

At 300k V006 detected at 20% on 5 instances; at 2M it is 33.3% on 21. The finding holds
and the number moved the way a small-sample number should.

## D-033 — AUC-PR is not comparable across the holdout slices

The held-out slices report AUC-PR 0.479 and 0.416 against 0.967 seen, and most of that
gap is an artefact. Each held-out slice contains one or two vectors' fraud against the
same legitimate traffic, so its prevalence is 0.104% and 0.098% against 0.844% for seen.
AUC-PR moves with prevalence by construction.

**Instance recall is the comparable figure** and it is what the write-up leads with:
99.6% seen, 83.1% held-out family, 100% held-out composition. The AUC-PR values are
reported with their prevalence attached and are not set against each other.

Catching this matters more than the numbers do: quoting 0.479 against 0.967 would have
been a real generalisation gap claim built mostly on a denominator.

## D-034 — Both behavioural signals are now slightly negative

Removing the coercion signal moves AUC-PR from 0.967 to 0.976. Removing the cadence
signal moves it to 0.977. At 1,445 fraudulent rows both have ample support and both are
very slightly harmful.

Reported as a negative finding, unchanged and untuned. The honest reading is that
transaction, velocity and graph evidence already carry everything these two contribute,
and the session-level behavioural columns add variance without adding information at this
prevalence.

## Separability at 2M

    fraud_p05  0.0664   legit_p99    0.0052   fraud_above_legit_p99  0.9785
    fraud_p50  1.0      legit_p99_9  0.2577   fraud_in_overlap_band  0.0734
                                              separation_gap        -0.1913

The overlap corridor is real: separation_gap is negative and 7.3% of fraud scores below
the 99.9th percentile of legitimate traffic. `fraud_above_legit_p99` reads 0.978 here
against 0.913 at 300k, so that particular statistic is scale-sensitive and the agreed
0.85-0.95 band only means something at a fixed scale. Not chasing it further.

---

# D-035 — The loop curve (21 Aug 2026)

Five generations at 400k transactions, 8 vectors growing to 32.

    G0   90.2%  #############################################
    G1   96.4%  ################################################
    G2   95.5%  ###############################################
    G3   91.3%  #############################################
    G4   94.1%  ###############################################

**This is not a converging curve and it should not be presented as one.** The script's
summary line reads "rising" because it compares the last value to the first, which is a
crude test that this shape defeats: the series goes up, down, down, up inside a 6-point
band. With 30 to 60 instances per generation that band is noise.

What the run does show, and what the walkthrough should say instead: **detection holds
between 90% and 96% while the attack set grows from 8 vectors to 32.** The detector is
not improving round on round; it is not degrading either, against an attack surface that
quadrupled.

## The measurement is not clean, and that is the more useful finding

Each generation adds vectors, so the population being measured changes every round. G0's
90.2% over 8 vectors and G4's 94.1% over 32 are not the same quantity, in the same way
the held-out AUC-PR slices were not comparable across prevalences. A curve built this way
cannot separate "the detector hardened" from "the mix got easier".

The fix, for whoever picks this up: hold a fixed evaluation set across generations, and
report detection on **newly added vectors only** as a separate series. That second series
is the one that answers the question the loop is actually asking, which is whether the
attacker can still get through after the detector has seen its last idea.

Not doing it now. Eight days left and the walkthrough is the larger risk.

## What did work

The strategist is directed, and demonstrably so. It read the miss log, found V006 at 11%
without being told V006 was interesting, and drifted `n_payouts` - the parameter feeding
the merchant-payout extraction. Later generations went after mule topology
(`n_mules`, `split_ratio_jitter`) and at G3 it substituted `merchant_collusion_payout`
with `agentic_purchase`, which is the extraction-rail dimension the boundary finding is
about. It found the same axis we did, from the data.

Validation accepted 24 of 24 proposals across four rounds. A 0% rejection rate is what
deterministic mutation should produce and is not evidence the validator works; the tests
that feed it malformed input are.

One vector, V031, evaded completely at generation 4 (0% detection).

---

# D-036 — Interface: contrast, bands, density, scale

## Contrast was a correctness bug, not a taste question

Audited by walking every text node's computed style and calculating true contrast against
the resolved background. **113 pieces of text under 12px failed 7:1. The worst was
2.54:1** - 10px grey-on-beige, which would have been invisible on a projector.

The muted tokens were solved for rather than sampled: on paper `--fg-2` is #3a3a34
(10.2:1) and `--fg-3` is #4e4e46 (7.5:1); on ink they are #cfcdc4 (11.9:1) and #b3b1a7
(8.8:1). 11px is now the floor everywhere, tracking on uppercase mono is 0.12em, and
chart axis labels moved from 9px muted to 11px at --fg-2.

Re-audited after: **0 failures, smallest text 11px.**

The warning colour needed its own pair. Vermilion measures 4.65:1 on paper, fine for a
55px figure and not fine for an 11px badge, so the badge uses #94290c on paper and
#ff9a72 on ink.

## Bands

Colour is band-scoped. Every component reads --fg, --fg-2, --fg-3, --rule, --ground and
--spot, so a section inverts without touching a single component. Sections 02, 04, 06 and
the colophon are ink; the rest are paper. Each band carries its own hairline grid at the
same pitch, so the field continues across the inversion instead of stopping at it.

The spot colour has two variants for the same reason as the warning colour: viridian
reads on paper and disappears on ink, so bands pick #0f5c4a or #4bbf95 in defender view
and #c43d18 or #ff7a4d in attacker view. The inversion is still one state change.

## Density and scale

Section padding and gaps cut by roughly a third. One hero number per section at
clamp(3.4rem, 9vw, 7rem) in the spot colour, which is also the single colour event on each
band: 444,573 chains, the prevalence, pass-through accounts flagged, net value protected,
instance recall, discriminator AUC. Figures went from 26px to 34px.

Both 3D scenes are full-bleed within their sections rather than figures in a column.

---

# D-037 — The ledger cache is not committed (21 Aug 2026)

119MB across seven Parquet files, the largest 54MB. Under GitHub's hard limit but over
its warning threshold, and committing it would contradict the rule stated in the README
and in D-006: the ledger stays out of git because it regenerates exactly from one seed,
and a repository that ships its own outputs cannot demonstrate that they reproduce.

Taking the conservative option. Instead:

- The simulator prints progress every 5% of the behaviour layer with a running estimate,
  because a reproduction step that prints nothing for thirty minutes reads as hung and a
  judge who kills it at minute ten concludes the repository is broken.
- The README carries a table of stage runtimes with the 35-minute simulate called out.
- `--cache-ledger` makes the second run of the same seed and size skip the simulate.

---

# D-038 — The audit's freshness check was wrong, and the clean-clone test caught it

The first clean-clone run reported four freshness failures on a repository where nothing
was actually stale. The check compared modification times, and **git does not preserve
mtimes**: every file in a fresh clone carries the clone timestamp, so any ordering
between them is an accident. It would equally have reported zero failures on a clone
where everything was stale.

The control built to catch bugs of this class had the bug of this class. It only showed
up because the clean-clone test was started early rather than on the last day, which is
the argument for starting it early.

Replaced with content digests. `source_digest()` hashes the eleven files whose content
determines a run's output, every manifest records it, and the walkthrough writes a
`walkthrough_build.json` stamp carrying the digest and the run_id it was built from. The
question "were these artefacts produced by this code" is now answered identically on any
machine.

The ledger cache key already used the same idea, which is where the approach came from.

# D-039 — The loop's final curve, and how to read it

    gen   fixed set   new vectors   current set
    G0       94.7%       n/a           94.7%
    G1       92.1%      100.0%        100.0%
    G2       94.7%      100.0%        100.0%
    G3       97.4%      100.0%         96.6%
    G4       97.4%      100.0%         98.6%

Fixed set moved 94.7% to 97.4% across five generations, a 2.6-point rise inside a
5.3-point band. On its own that is noise and is not claimed as hardening.

**The new-vector series is the result.** Every generation that introduced vectors caught
all of them, while the fixed set never exceeded 97.4%. The worst generation for fresh
mutations beat the best generation for the original set.

Reported as: directed mutation inside a fixed grammar produces variants, not novelty. It
moves parameters and recombines primitives the grammar already contains, and it never
invents a new extraction rail - which is exactly where V006 showed the boundary to be.
Adversarial search of this kind hardens a defender against variation and not against
novelty, and the practical instruction is to point a red team at new rails rather than at
parameter space.

The average gap (+3.6 points) understates this because the new-vector series is pinned at
its ceiling, so both the console summary and the walkthrough compare the worst fresh
generation against the best fixed generation instead. Two of my own outputs initially
disagreed on this, one calling it "no measurable difference" while the other wrote the
strong version; they now share the test.

Caveat carried into the document: G0's new-vector figure is definitionally the whole set,
since every vector is new at generation 0. The code now records None there; this run
predates that fix by minutes and shows 94.7%.
