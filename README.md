# AI Defense Lab for Payment Security

**Mastercard Innovation Challenge · GFF 2026 · Team Code Ops**

Generative AI made payment fraud cheap to produce and fast to mutate. This project owns
both sides of that fight: it composes attacks from a grammar, simulates their data
footprint, detects them across three levels of evidence, and then feeds the detector's
own failures back to the attacker to do it again.

The closed loop is the point. The detection-rate-per-generation curve it produces is the
result we are actually claiming.

---

## Scope and safety boundary

**This repository generates synthetic data. It does not generate attack tooling.**

Synthetic transaction records, session event sequences and account-graph edges — yes, in
full detail. Working voice-cloning pipelines, phishing generators, deepfake code, or
anything capable of reaching a live endpoint — no, under any framing.

Attack mechanisms are described in the taxonomy at the level of detail required to model
their observable data signature, and no further. A vector named "deepfake video-KYC
bypass" produces an account row, an onboarding session with a suspiciously short
duration, and a graph edge. It does not produce a video.

This is an ethical position and a scoring one. The judging criteria reward fidelity of
*simulated data*, which synthetic records satisfy completely. Functional fraud tooling
earns no marks and turns the repository into something a payments organisation cannot
accept, review, or showcase.

---

## The four things that make the numbers mean anything

Most submissions in this category report an F1 above 0.97 on a roughly balanced dataset
with a random split. Those numbers are not achievable in production, and any judge with
payments experience knows it. Four constraints, all enforced by tests:

**1. Single-source data.** Legitimate and fraudulent traffic come out of the same
simulator through the same code path. Public datasets calibrate distributions; they never
supply a row. Mixing two generators lets a tree separate them on timestamp precision and
amount rounding — an F1 of 0.99 that learned only which program wrote each row.
`tests/test_provenance.py` trains a provenance-only classifier and asserts it performs at
chance.

**2. Realistic prevalence.** Fraud base rate ≈1%, configurable, and stated next to every
metric without exception. The metrics contract makes `prevalence` a required field, so a
number cannot be serialised without it.

**3. Leak-free splits.** By time *and* by account, with an embargo window between them. No
`account_id` appears in both halves.

**4. Honest reporting.** Seen and unseen attack performance are separate headline figures,
never merged. Every headline is stated as percentage lift over a defined baseline —
a logistic regression on transaction-level features only, committed in `config.yaml`,
deliberately reasonable rather than a strawman.

---

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate    # source .venv/bin/activate on POSIX
pip install -e ".[dev]"
python scripts/reproduce.py
```

```bash
cd web && npm install && npm run dev
```

`scripts/reproduce.py` runs every stage that exists and names the ones that do not. On a
clean clone it regenerates every committed artefact byte for byte from the seed in
`config.yaml`.

### How long a full reproduction takes

| Stage | Time |
|---|---|
| `scripts/reproduce.py` (contracts, fixtures, tests, walkthrough, audit) | about 4 minutes |
| `scripts/run_pipeline.py --transactions 2000000` (the headline numbers) | **about 35 minutes** |
| `scripts/run_loop.py --generations 5` (the loop curve) | about 35 minutes |

**The two-million-row simulate is roughly half an hour and it is the slowest thing here.**
It prints progress every 5% with a running estimate, so a silent terminal means something
is wrong rather than something is slow. Add `--cache-ledger` and a second run of the same
seed and size skips the simulate entirely.

The ledger itself is not committed. It is 119MB of data that regenerates exactly from one
seed, and a repository that ships its own outputs cannot demonstrate that they reproduce.
Only the derived artefacts the prototype reads are in git.

---

## Layout

```
contracts/        four frozen JSON Schemas + the attack grammar
src/adl/
  common/         config, seeds, contract validation, grammar rules
  identify/       taxonomy and grammar (Pillar 1)
  generate/       simulator and reference profiling (Pillar 2)
  defend/         three-level detector (Pillar 3)
  loop/           red-team strategist and validation layer
  evaluate/       metrics, splits, ablations
fixtures/         contract-valid fixture artefacts the prototype is built against
web/              React + Vite prototype
tests/            contract, grammar, leakage and provenance guards
NOTES.md          decision log — the source material for the walkthrough
```

## The contracts

Four files in `contracts/`, frozen on 2026-08-20. Changing one is a decision requiring
agreement, not a unilateral edit — the most common cause of a failed integration in a
short project is two components built against different assumptions about the data
between them.

| Contract | Produced by | Consumed by |
|---|---|---|
| `attacks.schema.json` | taxonomy, red-team strategist | simulator, prototype |
| `ledger.schema.json` | simulator | detector, prototype |
| `misses.schema.json` | detector | red-team strategist, prototype |
| `run_manifest.schema.json` | evaluation | prototype, walkthrough |

`grammar.json` holds the 19 primitives, their stages, and the composition rules. A chain
is a valid path through it, and `validate_chain()` is what every producer — hand-authored
or model-generated — has to satisfy.

## The prototype

One continuous environment that inverts. The same scene, the same data, the same camera
position — flipped between **defender** and **attacker**, where a mule network is a
detection surface from one side and a route map from the other. Green and cyan carry the
defence, amber and magenta the attack, so colour always tells you which side you are
looking at.

Six environments: Threat Constellation, Ledger Stream, Account Nebula, Detection Surface,
Loop Helix, Fidelity Mirror. Four get WebGL; every one of them also ships a 2D chart view
of the same data, which doubles as the reduced-motion path and the venue-machine fallback.

Fixture data is flagged as fixture data in the interface. No screenshot of invented
numbers can be mistaken for a result.

## Reproducibility

Fixed seeds throughout, derived per component from one master seed so adding a component
never shifts an existing one's draws. `config.yaml` is hashed into every run manifest: two
runs claiming the same numbers can be shown to have used the same settings.

## Reference data

Not in this repository, and not redistributable — see `data/reference/README.md`. Only the
derived profile is committed.
