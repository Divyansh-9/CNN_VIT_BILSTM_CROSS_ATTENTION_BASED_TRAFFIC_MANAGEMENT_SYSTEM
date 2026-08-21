# ADR-019 — Leave-one-camera-out evaluation, because seven cameras cannot be split once

**Status:** Proposed · **Date:** 2026-08-21 · **Amends [PRD](../PRD.md) §8.4 (60/20/20) for MFSTNet only; extends [ADR-002](ADR-002-mfstnet-training-corpus.md)**

## Context

The MFSTNet corpus was built on 2026-08-21: **153 sequences over 7 cameras**,
after [P45](../PRD-CHANGELOG.md)'s density gate removed four cameras whose mean
frame carries fewer vehicles than the MEDIUM→HIGH boundary itself.

PRD §8.4 says split 60/20/20, and ADR-002 says cut by source clip so overlapping
windows cannot leak. `build_corpus.py` implements both by hashing each camera id
into a bucket. That is deterministic and reproducible, and with enough cameras it
is unobjectionable.

With seven, the draw decided the entire evaluation:

| split | cameras | sequences | LOW / MED / HIGH |
|---|---|---|---|
| train | 5 | 55 | 38.2% / 53.6% / 8.2% |
| val | 1 | 35 | 44.3% / 55.7% / **0.0%** |
| test | 1 | 63 | 59.5% / 32.5% / 7.9% |

Three things are wrong with it, and none is a tuning problem.

**The test set was the M6 Motorway.** A UK motorway — free-flowing, lane-
disciplined, homogeneous — is the single least representative camera in a
project whose subject is unstructured Indian traffic. Every generalisation
number in the paper would have been measured there, and it holds 41% of the
corpus.

**Validation contained no HIGH window at all.** Macro F1 scores an absent class
0 by convention ([P31](../PRD-CHANGELOG.md)), so early stopping would have
selected checkpoints on a two-class problem while the paper reported three.

**The assignment is a function of the filename.** `_clip_fraction(clip_id, seed)`
hashes the id. Renaming a video changes which camera is the test set and
therefore changes the headline number, and no result CSV would record that
anything had moved.

## Decision

**Evaluate MFSTNet by leave-one-camera-out cross-validation**, not by a single
60/20/20 draw. `mfstnet/corpus/folds.py`, `scripts/resplit_corpus.py`.

Fold `i` tests camera `i` and validates camera `i+1` cyclically, so every
eligible camera is tested exactly once and validated exactly once. Reported
figures are the **mean over folds with a bootstrap 95% CI** — which is what
NFR-10 already requires and what the single split could not honestly supply.

### A camera must be big enough to be a test set

Rotating over all seven produced a fold whose test split held **one sequence**
and a fold whose validation split held one. A macro F1 over one sequence is not
a measurement.

So a camera is eligible to be tested only if it contributes at least
**`MINIMUM_TEST_SEQUENCES = 10`** windows. Ineligible cameras are *not*
discarded — they stay in `train` in every fold, where their data still counts.
This leaves **four folds**:

| fold | test camera | n | val camera | n | train |
|---|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | 35 | M6 Motorway | 63 | 55 |
| 1 | M6 Motorway | 63 | Pov Footover bridge | 11 | 79 |
| 2 | Pov Footover bridge | 11 | Dhaka Rampura (b) | 34 | 108 |
| 3 | Dhaka Rampura (b) | 34 | Dhaka Rampura (a) | 35 | 84 |

Mumbai (6), South Extension (3) and video1 (1) are always-train.

The eligibility threshold is a property of the corpus, **declared once here and
recorded in every fold's manifest**, never chosen per config or per result.

### Why the split is re-derived rather than rebuilt

A split depends on which camera a window came from and on nothing the detector
produced, so `resplit_corpus.py` re-cuts one in about a second from an existing
corpus, carrying `counts.csv` and `detections.csv` over untouched. This is the
same argument [P28](../PRD-CHANGELOG.md) makes for lane centres and
`relabel_corpus.py` makes for thresholds: the expensive artifact is the
detections, and everything downstream of them should re-derive cheaply.

## What this does not fix

**It creates no data.** Twenty-eight independent segments stay twenty-eight.
Every fold's test set is still **one camera**, which is the effective n however
many sequences that camera contains, and `audit_corpus.py` says so on every
fold. Two of the four folds still involve a camera with no HIGH window on one
side or the other.

It also **does not rescue the corpus's composition**: three cameras hold 86% of
it, and one of those three is the M6. Under LOCO the M6 is one fold of four
rather than the whole test set, which is a real improvement and not a cure.

The one input that changes those numbers is more dense fixed-camera footage —
[ADR-016](ADR-016-two-phase-corpus.md)'s Bellevue phase, or the narrowed
recording sessions [P45](../PRD-CHANGELOG.md) describes.

## Consequences

- PRD §8.4's `60/20/20` no longer describes MFSTNet evaluation. It still
  describes the *detector* split (70/15/15, FR-D05) and is unchanged there.
- Results carry a `fold` column. A result without one is a single-draw number
  and must not be compared against a fold mean.
- Every fold manifest records `split_protocol`, `fold`, `folds_total`,
  `fold_test_camera`, `fold_val_camera`, `fold_always_train` and
  `min_test_sequences`, so a fold view can never be mistaken for the corpus.
- The full A–H ablation multiplies by the fold count. At four folds this is
  hours, not days, on cached features (ADR-005).

## Alternatives rejected

**Re-roll the hash with a different seed.** Picks a different lottery ticket.
The next draw is as arbitrary as this one and would be chosen *after seeing* that
this one was bad, which is selection on the test set.

**Constrain the search to assignments where every split carries all three
classes.** Enumerable over 7 cameras, but it selects a split using the labels,
and the constraint would have to be re-satisfied every time thresholds move.

**Stratify by class instead of by camera.** Breaks ADR-002: windows from one
camera would land on both sides, and consecutive windows share most of their
frames.

**Report the single split and note the caveat.** The caveat would be that the
headline number is a British motorway. That is not a caveat, it is a different
paper.
