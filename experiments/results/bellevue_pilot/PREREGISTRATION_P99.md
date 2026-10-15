# P99 — training coverage and class generalisation, fixed before any training

Written 2026-10-15, after P98 (the frozen P97 model never predicts LOW: 0 of
2,691), P99a and P99b (ITD-xl stays, and its morning LOW labels are usable at
precision 0.845). **No model has been trained on this design, and no P99 split
has been scored.** The project owner decided this experiment and its
acceptance conditions. This file makes them exact.

Frozen and untouched: the P97 checkpoints, `82680d9` (P98) and every earlier
result, the S61 checkpoint, the detector (ITD-xl), the three lanes, the
thresholds (LOW ≤ 2, MEDIUM ≤ 8), the 60 s sustained target (P94), and the
preprocessing hash `a4142d1ab333226b`.

## Data — existing footage only

There are 13 hours of NE 8th, all already counted by ITD-xl:

- the 11 P98 hours (`data/corpus_p98`);
- P97's two hours (`data/corpus_bellevue_3lane`), split at sample 1800 into
  15:08 and 16:08.

Night stays excluded. No download, and no detector rerun.

**Disclosed:** the P98 hours were read once as P98's test, and their per-hour
results are known (P98). P99 is a new experiment with its own split, fixed
mechanically below. No hour is chosen or dropped on the basis of a model
result.

## Split — chronological 10-minute blocks, positions rotating by hour

- The hours are ordered chronologically, h = 0 … 12: Sun 18:08, Sun 19:08,
  Mon 06:08 … Mon 16:08.
- Each hour is cut into **six 10-minute blocks**, b = 0 … 5 (samples
  300b … 300b + 299 of that hour).
- **Test:** blocks h mod 6 and (h + 3) mod 6. **Validation:** block
  (h + 1) mod 6. **Train:** the other three. The test position rotates, so no
  fixed minute of the hour, such as a signal-plan change, is always in test.
- **A window belongs to a block only if its whole span lies inside it**: inputs
  s … s+59 and target e+1 … e+30, which is 90 samples. Windows of different
  splits therefore share no frame. A window never crosses an hour.
- Start every 15 samples, as in P94–P98. That gives 15 windows per full block.

**Class support, counted before any training** (lane-decisions, targets
only):

| split | blocks | windows | LOW | MEDIUM | HIGH |
|---|---|---|---|---|---|
| train | 39 | 572 | **165** | 1139 | 412 |
| validation | 13 | 195 | 27 | 416 | 142 |
| test | 26 | 390 | 83 | 824 | 263 |

P97 trained on 1 LOW. Every class is present in every split. The corpus builder for P99 must reproduce this table exactly, or it stops.

**Stated limitation:** adjacent blocks are adjacent in time, so a test block
is near training blocks of the same hour. This tests generalisation across
blocks within the day, which is weaker than P98's across-hours test. The
shortcut diagnostic and the per-period gate below exist because of it.

## Runs

- **Models:** G and H.
- **Imbalance treatment, a controlled variable:**
  - **`inverse`** is the PRD §8.4 objective, cross-entropy with
    inverse-frequency class weights. P97 already used it: its single LOW
    example carried about 127× weight and the class was still not learned.
  - **`none`** is unweighted cross-entropy, documented as the control.
- **Seeds:** 42, 1, 7, 13 and 21.
- That makes **20 runs**: 2 models × 2 objectives × 5 seeds.
- Everything else matches P97: the training code and hyperparameters (PRD
  §8.2/§8.4 via config), the feature cache built with the same preprocessing,
  and validation-based early stopping. The objective is a recorded run
  setting, written to every result's sidecar.

## Selection — validation only, frozen before the test is read

1. **Model and objective:** the pair with the higher mean validation macro-F1
   across seeds. On an exact tie, **H**, then **`inverse`**, the simpler model
   and the PRD default.
2. **Seed, within that pair:** the highest validation macro-F1. Ties go to the
   earlier seed in 42, 1, 7, 13, 21.
3. The same rule selects one seed for each of the other three pairs, for the
   secondaries.

All selections are written to `selection_P99.json` and **committed before any
test block is read**.

## Primary comparison — exactly one

On the 26 test blocks:

- **the selected model − previous-window mean, macro-F1**, on identical
  windows;
- with a **10-minute block bootstrap**: 10,000 resamples of whole test blocks,
  seed 0;
- **"beats"** means the 95% interval excludes zero **and** the point estimate
  is positive.

**Primary metrics reported with it:** recall for LOW, MEDIUM and HIGH, for the
model and for the baseline.

## Secondary comparisons — Holm-corrected as one family

1. The primary comparison per lane: west, north and east.
2. Accuracy and QWK, model − baseline.
3. Per-class recall, model − baseline: LOW, MEDIUM and HIGH.
4. **The objective as a controlled variable:** the selected `inverse` seed
   against the selected `none` seed, for the selected model, on macro-F1.
5. **Shortcut diagnostic: model − hour prior.** The hour prior predicts, for
   each lane, the most frequent class among that hour's **training** windows.
   It knows the time of day and nothing else. A model that does not beat it is
   not shown to use traffic beyond time of day. This matters here because LOW
   really is concentrated in the morning (P99b), and morning images also look
   different.

**Reported, not tested:** the **frozen P97 checkpoint (G seed 13)** on the
test blocks of the 11 P98 hours, as the control. The 15:08 and 16:08 blocks
are excluded because they were its own data. No secondary can rescue a failed
primary.

## Acceptance for Phase 2 — the owner's conditions, made exact

Phase 2 (unseen cameras) proceeds only if **all four** hold:

1. **It predicts LOW when LOW occurs.** Test LOW recall is **≥ 0.50**, on test
   LOW support of at least 30 decisions (83 are present).
2. **It beats persistence.** The primary interval excludes zero in the
   positive direction.
3. **It is not driven by one lane or one period.**
   - Removing any **one lane** leaves a positive point estimate.
   - So does removing any **one period**: Sunday evening (18:08, 19:08),
     morning (06:08–09:08), midday (10:08–13:08), or afternoon
     (14:08–16:08).
4. **It passes the existing inference checks.** The selected checkpoint
   exports through `scripts/export_checkpoint.py`, and the ONNX graph is
   proven against the checkpoint's own committed predictions. The test suite
   passes.

If any condition fails, Phase 2 stays paused and the failure is reported as
measured.

## Reported regardless of outcome

- Class support for every split, and the blocks and windows behind every
  interval.
- Confusion matrices for the model and the baseline.
- Results per period, labelled exploratory.
- The detector limits: P96's afternoon undercount (14% / 27% / 41%), and
  P99b's LOW precision of 0.845 [0.747, 0.931], with 4 of 9 at 08:08.

## What this cannot show

Generalisation to another camera, night, or Indian traffic. Generalisation to
an hour the model has never seen: blocks of every hour are in training.
P98-style out-of-time replication would need new hours, and that is a later
decision.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).

## Amendment 1 — the owner's three locks, fixed before any training

Written after the corpus build and the pre-training checks, and **before any
P99 run trained**. Nothing here was chosen with knowledge of a P99 score,
because none exists.

**Lock 1, support and containment.** These are checked and passed by
`scripts/p99_corpus.py`, which stops on any failure before writing:

- support per split equals the table above exactly: 165/1139/412, 27/416/142
  and 83/824/263;
- every window's 90-sample span lies inside its block;
- **0 of 23,205 spanned samples are shared between splits**.

**Lock 2, the shortcut baseline, frozen:**

- **The hour prior.** For each hour and each lane, it predicts the class that
  is most frequent among that hour's **training** windows. A tie goes to the
  class more frequent in the whole training split for that lane, then to the
  lower ordinal. It is scored with the primary's metric and method, macro-F1
  with the 10-minute block bootstrap, on the **same test windows** as every
  model.
- Every selected model (G and H × both objectives) is reported against the
  baseline and against the hour prior on those same windows. **Both objectives
  are reported whichever wins.**

**Lock 3, selection without test, made structural:**

- Training uses `data/corpus_p99_trainval`, which **holds no test window**.
- `train_mfstnet.py --no-test` refuses any corpus that contains one. Under
  `--no-test`, every metric, prediction file and checkpoint record is labelled
  `evaluated_on: val`, and a checkpoint's `test_macro_f1` is empty.
- `scripts/p99_eval.py select` reads validation scores only and writes
  `selection_P99.json` with each selected checkpoint's SHA-256.
- `scripts/p99_eval.py test` **refuses unless that file is committed and
  unchanged**, and refuses if any checkpoint's hash has changed.
- The evaluator is committed with this amendment, before training.

**Phase 2 is conjunctive.** All four conditions must hold, and none
compensates for another. Every lane and period ablation is reported, never
only the best. Condition 4 (ONNX parity and the full test suite) runs as a
separate step after the test read.

**Two distinctions recorded.**

- P99b's 84.5% LOW agreement supports using these labels. It does not make
  every morning LOW label correct.
- P99's within-day split measures generalisation across blocks. It does not
  replace a held-out-day or held-out-camera evaluation.

**Annotator for P99b:** still "unrecorded". It is not to be filled in without
the project owner's confirmation of who counted.
