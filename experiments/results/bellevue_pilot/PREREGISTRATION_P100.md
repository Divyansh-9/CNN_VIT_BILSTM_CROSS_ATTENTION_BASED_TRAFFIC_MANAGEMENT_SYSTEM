# P100 — does the model read the traffic, or the clock? Unseen-hour test, fixed before any run

Written 2026-10-16, after P99. P99's selected model beat persistence by +0.102
[+0.041, +0.177], but **not** an hour-of-day prior (−0.015 [−0.077, +0.119]).
LOW recall was 0.349, so Phase 2 failed. This experiment asks the question P99
left open, as the project owner directed. **Nothing has been trained for P100,
and no P100 score exists.**

Frozen and untouched: P97, P98, P99 and their checkpoints; the detector
(ITD-xl); the three lanes; the thresholds (LOW ≤ 2, MEDIUM ≤ 8); the 60 s
target; the preprocessing hash `a4142d1ab333226b`. The data is the existing 13
hours, with no new footage, detector change or threshold change.

## Why the P99 checkpoint cannot answer it

P99 trained on blocks of **all 13 hours**, so it has seen every hour, and an
unseen-hour test needs models that have not. The recipe is **not reselected**.
P100 trains exactly P99's validation-selected recipe, **G with unweighted
cross-entropy**, with whole hours withheld.

## Part A — content control on the P99 checkpoint (no training)

This is a diagnostic of the existing P99 model, on P99's 390 test windows.
**Those windows were already read once (P99)**, so this is a re-analysis,
labelled as such, and it changes no P99 result.

- **Swapped input.** Each test window's inputs are replaced by those of
  **another test window from the same hour**. The pairing is a derangement
  drawn by `random.Random(0)`, hour by hour, in window order. The labels stay
  those of the original window.
- **What it isolates.** Same-hour windows share lighting, shadows and time of
  day. A swap keeps all of that and removes the window's own traffic.
- **Reported:** macro-F1 on real input minus macro-F1 on swapped input, with
  the 10-minute block bootstrap (10,000 resamples, seed 0), and LOW recall
  under both.

## Part B — complete hours withheld

**Two folds, interleaved by hour.** The 13 hours are ordered chronologically,
i = 0 … 12, from Sun 18:08 to Mon 16:08.

| fold | test hours (never seen in training or validation) | trains on |
|---|---|---|
| A | odd i: Sun 19:08, Mon 07:08, 09:08, 11:08, 13:08, 15:08 | even-i hours |
| B | even i: Sun 18:08, Mon 06:08, 08:08, 10:08, 12:08, 14:08, 16:08 | odd-i hours |

- Every hour is tested **exactly once**, by a model that never saw any frame of
  it.
- Every test hour has training hours on both sides in time, or one side at the
  ends of the recording.
- **Within the training hours,** validation is block (i + 1) mod 6 of each
  hour and training is the rest. Every window lies wholly inside its block, as
  in P99, so train and validation share no frame. Test hours share no frame
  with either.

**Class support, counted before any training** (lane-decisions, targets only;
the builder must reproduce it exactly or stop):

| fold | split | windows | LOW | MEDIUM | HIGH |
|---|---|---|---|---|---|
| A | train | 525 | 191 | 1044 | 340 |
| A | val | 105 | 22 | 212 | 81 |
| A | test | 527 | 62 | 1123 | 396 |
| B | train | 437 | 57 | 919 | 335 |
| B | val | 90 | **5** | 204 | 61 |
| B | test | 630 | 213 | 1256 | 421 |

The pooled test covers all 13 hours: 1,157 windows in 78 blocks, with 275
LOW decisions.

**No selection at all.** Fold B's validation holds only 5 LOW, which is too few
to choose a seed on. So each fold trains **seeds 42, 1 and 7**, and the fold's
model is the **average of the three seeds' class probabilities**. Validation is
used only for the trainer's existing early stopping. Each seed is also
reported on its own.

**Runs:** 2 folds × 3 seeds = **6**, all G with unweighted loss, `--no-test`,
on train/val-only corpora. Measured cost in P99 was 10–15 min per run.

## Comparators, all on the same unseen-hour windows

- **Persistence:** the previous-window mean, as in P94–P99.
- **Clock prior (time only), built without any held-out-hour label.** For each
  lane, it predicts the most frequent class among the training windows of the
  **nearest training hour in absolute time**. If two are equidistant, their
  windows are pooled. A remaining tie goes to the class more frequent in that
  fold's whole training split for that lane, then to the lower ordinal. It
  never uses a test hour's labels, and it always has a training hour to draw
  on, because of the interleaving.

## Primary family — two comparisons, Holm at 0.05

On the pooled unseen-hour test, the seed-averaged fold models against:

1. **the clock prior, macro-F1**, which is the question P99 raised;
2. **persistence, macro-F1**.

Both use the 10-minute block bootstrap: 78 blocks, 10,000 resamples, seed 0.
"Beats" means the Holm-adjusted test passes **and** the point estimate is
positive.

**Reported with them:** recall for LOW, MEDIUM and HIGH; confusion matrices for
the model, the clock prior and persistence; and support.

## Secondary family — Holm at 0.05

1. **Content control on the fold models.** The same within-hour swap as Part
   A, on the unseen-hour test: real − swapped macro-F1.
2. LOW recall, the model against the clock prior and against persistence.
3. Each fold on its own, the model against the clock prior.

**Reported, not tested:** each seed alone, each lane and each period (Sunday
evening, morning, midday, afternoon), all on the same windows.

## Interpretation, fixed now

| model vs clock (unseen hours) | real vs swapped | reading |
|---|---|---|
| beats | real better | the model uses each window's traffic, beyond time of day |
| does not beat | real better | it reads the traffic, but not enough to beat the clock |
| does not beat | no difference | its predictions are explained by hour-level appearance; the next priority is representation or temporal coverage, **not more seeds** |

The Phase 2 conditions are **not** re-scored here: P99 failed them, and P100
is a diagnostic. Its LOW recall is reported against the 0.50 bar for
information only.

## What this cannot show

Another day of the week at the same hour, another camera, night, or Indian
traffic. Two Sunday hours exist, so weekday and weekend are partly confounded
with hour.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).
