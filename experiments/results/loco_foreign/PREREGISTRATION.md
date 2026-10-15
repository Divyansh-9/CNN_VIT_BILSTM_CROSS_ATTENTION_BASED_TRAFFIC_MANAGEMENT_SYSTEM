# S61 — foreign-domain baseline, selection rule fixed before training

Written 2026-10-15, before any run in this directory existed. The rule below is
applied by `scripts/select_checkpoint.py`, which reads only validation columns.

## What runs

| | |
|---|---|
| domain | `foreign` (ADR-025): the four `real_external` cameras; Mumbai, South Extension and video1 excluded as `unknown` |
| folds | all four leave-one-camera-out folds |
| seeds | 42 1 7 13 21 |
| configs | G (full MFSTNet) and H (linear probe), the ADR-022 pair |
| epochs | spec default, early stopping on validation macro-F1 |
| checkpoints | every run's selected model, `models/mfstnet/foreign/` |

40 runs. A failed run is recorded in `failures.csv` and is not replaced.

## How the deployment checkpoint is chosen — validation only

1. **Config:** the one with the higher mean `val_macro_f1` over all its runs.
2. **Fold:** the fold whose test *and* validation cameras are both declared
   `traffic_type: mixed`, taking the largest test set if more than one
   qualifies. Expected: fold 3, which tests the second Rampura camera and
   validates on the first. This keeps both selection and the held-out check on
   the traffic regime the project targets, and keeps M6 out of selection.
3. **Seed:** the highest `val_macro_f1` within that config and fold; ties go to
   the seed listed first above.

No test-split column is read at any step.

## What the numbers will and will not mean

- Five seeds on one fold measure **training-seed sensitivity**, not five
  independent camera samples. The camera sample is the fold count: four.
- Every number here is a **foreign-domain** result. None is Indian evidence,
  and none is reported as the headline (ADR-025).
- M6 is reported per camera beside the Dhaka cameras, never only inside an
  aggregate (P85).
- Every camera's licence is unresolved, so this is an internal engineering
  baseline, not a publishable dataset result.
