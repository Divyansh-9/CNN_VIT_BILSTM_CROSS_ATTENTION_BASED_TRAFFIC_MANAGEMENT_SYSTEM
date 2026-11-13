# S63 Bellevue pilot — fixed before any label or result existed

Written 2026-10-15 while `data/corpus_bellevue` was still building. No count,
label, feature or score from this corpus had been seen.

## What this is, and is not

A **pipeline check** on one camera: it shows the existing architecture and
tooling can take Bellevue footage end to end. It is **not** evidence of
performance on an unseen camera, of Indian traffic, or of a publishable
dataset (the licence is unresolved; internal engineering only). The S61
checkpoint and the original corpus are frozen and untouched.

| | |
|---|---|
| camera | Bellevue NE 8th, Monday 11 Sep 2017, 15:08–17:08 (two contiguous hours, continuous by its burnt-in clock; see Amendment 1) |
| corpus | `data/corpus_bellevue`, built with the original corpus's settings: ITD-xl, conf 0.45, imgsz 992, step 2 s, T 60, horizon 60 s, stride 30 s |
| A30 | exclusion overridden for this corpus only, explicitly (P91) |
| lanes | four, hand-placed by the project owner |

## Amendment 1 — before any label existed: two contiguous hours, not one

The first build ran the detector over 16:08–17:08 (1,800 samples, 115 windows)
and then **refused to split**, which is correct. The split is the one fixed
below. A window spans 149 samples (60 steps plus the label horizon), and each
boundary discards one window's width on both sides. The 20% validation band of
one hour is 360 samples, which leaves **62 samples after the buffers — less
than one window**. `assign_splits_temporal` raised rather than return an empty
validation split.

The build failed before writing anything, so no count, label or score had been
seen. **Changed:** the corpus covers **15:08–17:08**, the preceding hour of the
same camera concatenated by stream copy (no re-encoding), with continuity across
the join checked against the burnt-in clock. The validation band becomes 720
samples, or 422 after the buffers. **Not changed:** the ratios, the buffers,
the label rule, the models and the selection rule. Shrinking the buffers to fit
one hour would have weakened the one property the temporal split exists for.

## Labels — the rule is fixed here

- **Primary:** per-camera thresholds at the p33 and p67 of this camera's own
  PCU occupancy (`relabel_corpus.py --calibrate`), as ADR-017 specifies.
- **Also reported:** the same counts under the original corpus's fixed
  thresholds (`low_max 4`, `med_max 15`), for comparison.
- **Neither rule is adjusted after the label distribution is seen.** If HIGH
  is absent or rare, that is reported as the finding, and whether the data
  supports the task is decided from it. Classes are not balanced by moving a
  threshold.

Per-camera percentiles split this hour's own range into thirds. "HIGH" then
means "the busiest third of this hour", not congestion in any absolute sense,
and the report must say so.

## Split

Chronological, by time, never by shuffled window:

- **train:** the first 60% of the hour;
- **validation:** the next 20%;
- **test:** the last 20%.

**No window may overlap a boundary.** A window spans 120 s plus a 60 s horizon,
so any window whose span crosses into the next split is dropped rather than
assigned.

## Models and selection

- **Configs:** G (full MFSTNet) and H (linear probe), the ADR-022 pair.
- **Seeds:** 42 1 7 13 21.
- **Selection:** on validation macro-F1 only — first the config with the higher
  mean, then that config's best seed.
- **Test:** the held-out final period is read **once**, after selection, and
  reported as a single-camera temporal evaluation.

## Known detector biases, carried into every result

From P91: the painted bicycle symbol detected in every frame, inside the west
lane's reach; cars occasionally labelled `autorickshaw`; the far end of the
north queue under-counted. These are limitations of the labels, not effects the
thresholds are assumed to remove.
