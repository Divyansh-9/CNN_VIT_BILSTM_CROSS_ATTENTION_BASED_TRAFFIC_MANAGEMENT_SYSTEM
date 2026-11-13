# P101 — do the images add anything beyond the counts? Fixed before any count model runs

Written 2026-10-16, after P100. On unseen hours, the vision model uses each
window's traffic (content control +0.054 [+0.024, +0.087]). It beats neither
the clock prior (+0.029 [−0.005, +0.065]) nor persistence (−0.059
[−0.129, +0.031]), and its LOW recall is 0.058. The project owner directed a
count-only experiment next: no detector change, no new footage, and no
further vision training. This is the C1/C2 separation of ADR-023, measured
on one camera.

**Status: exploratory.** The test windows are P100's, and they have already
been read. This is a paired comparison on identical windows. It is **not** a
fresh, independent confirmation.

Frozen: P97–P100, the detector (ITD-xl), the three lanes, the thresholds
(LOW ≤ 2, MEDIUM ≤ 8), the 60 s target, the P100 folds and their test windows.

## The count-only model — fixed here, nothing tuned

- **Input:** the vehicle counts of the **same 60 samples** the vision model
  sees, inputs s … e. History is no longer than the vision model's, so the
  comparison isolates the modality, not the context length. **No clock or
  date feature**, because the clock is a comparator, not an input.
- **Features**, for each of the three lanes over samples s … e. That is 8
  features × 3 lanes = **24 features**, and the forecast for each lane sees
  all three lanes:
  - the mean over the last 60, 30, 15 and 5 samples;
  - the last value;
  - the standard deviation and the maximum over all 60;
  - the least-squares slope over all 60.
- **Preprocessing:** standardisation fitted on the fold's **training windows
  only**.
- **Primary model:** multinomial logistic regression, one per target lane per
  fold (`sklearn` 1.9.0, `LogisticRegression(C=1.0, max_iter=5000)`),
  **unweighted**, mirroring the vision recipe P99 selected.
- **Training data:** each fold's training windows from `p100_corpus.py`.
  Validation is not used, because **nothing is selected**: there is one
  specification, applied identically to both folds. Each test window is
  predicted by the fold that never saw its hour.
- **Two variants, reported and never selected:**
  - logistic regression with `class_weight="balanced"`;
  - `HistGradientBoostingClassifier(random_state=0)` with defaults.

## Comparisons

All on the 1,157 P100 test windows (78 blocks), against P100's committed
per-window decisions (`p100_test_windows.json`, `a6fb360`), with the
10-minute block bootstrap (10,000 resamples) and macro-F1.

**Family of three, Holm at 0.05**, for the primary count model:

1. **vision − counts**, the question this experiment asks;
2. counts − clock prior;
3. counts − persistence.

**Reported for every method:** macro-F1, LOW, MEDIUM and HIGH recall, the
confusion matrix and support. The two variants are compared with the same
three differences, untested.

**Complementarity, reported and not tested.** On the lane-decisions where the
count model and vision disagree, by true class, the numbers each gets right.
That says whether a later counts-plus-vision model has anything to combine.

## Interpretation, fixed now

| result | reading |
|---|---|
| vision − counts, interval above zero | the images add predictive value beyond the counts, on this camera and these labels |
| interval includes zero | added value **not established**; the interval bounds how large it could be |
| interval below zero | the counts alone forecast better than the vision model here |
| neither the count model nor vision beats both baselines | the next priority is wider temporal coverage, quiet periods on other days first |

The labels themselves are derived from the counts (A32), so a count model has
a structural advantage that a human-verified label would remove. That is
stated as a limitation, and the experiment is not discounted for it.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).
