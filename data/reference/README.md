# Reference datasets

**Nothing in this directory is committed.** Only the derived profile
(`contracts/../artifacts/reference_profile.json`) is, and it contains summary
statistics only — marginals, quantiles, correlation matrices. No rows, ever.

Two reasons, and they point the same way:

1. **Licensing.** IEEE-CIS is distributed under Kaggle competition rules and cannot be
   redistributed. PaySim is CC BY-SA but there is no reason to vendor 470MB into a
   repository judges will clone.
2. **The single-source rule** (PDF §5). Reference data calibrates distributions. It
   never supplies a row to the ledger. Keeping the rows out of the repo makes that
   structurally true rather than merely promised.

## What to put here

| File | Serves | Source |
|---|---|---|
| `ieee-cis/train_transaction.csv` | card / CNP transaction structure — card testing, ATO, CNP fraud | kaggle.com/c/ieee-fraud-detection |
| `paysim/PS_20174392719_1491204439457_log.csv` | account-to-account transfer structure and the mule graph | kaggle.com/datasets/ealaxi/paysim1 |

Then point `config.yaml` → `fidelity.reference_profiles.*.path` at them and run:

```
python -m adl.generate.profile_reference
```

If IEEE-CIS is unavailable, run with PaySim alone. The profiler records which profiles
were present in `run_manifest.json → fidelity.reference_profiles[].available`, and the
fidelity section of the walkthrough states the gap explicitly rather than papering
over it.
