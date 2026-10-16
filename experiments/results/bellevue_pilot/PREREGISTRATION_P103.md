# P103 — does the count forecaster transfer to new cameras? Fixed before any new camera is counted

Written 2026-10-16, after P102. **No frame of any P103 camera has been run
through the detector, and no lane has been placed on them.** The project owner
approved a lane-agnostic count-only model, deferred boosting, and required the
threshold policy and lane placements to be locked before scoring. This file
locks the model and the threshold policy. The lanes are locked by Amendment 1
once placed and reviewed.

Frozen and untouched: P97–P102, including `c1_count_forecaster_v1.json`; the
detector (ITD-xl, conf 0.45, imgsz 992, step 2 s); the 60 s sustained target;
the window geometry (T 60, stride 15). No new download. No fitting on any P103
camera.

## Why the model must change shape

C1 v1 reads all three NE 8th lanes in a fixed west/north/east order, which no
other junction shares. It also outputs classes in NE 8th's units (LOW ≤ 2
vehicles), which mean something else on a camera whose lane regions cover
different road areas. P103 therefore uses a **lane-agnostic forecaster of the
count itself**. Thresholds are applied to its output, so the model never sees a
threshold and both threshold policies below are served by the same, unchanged
predictions.

## The models — fitted once, on NE 8th only

**Inputs.** One lane's own counts over the 60 input samples: the mean of the
last 60, 30, 15 and 5; the last value; the population standard deviation; the
maximum; the least-squares slope. That is 8 features, P101's per-lane set.
There is **no other lane, no clock, and no camera identity**.

**Training data.** Every NE 8th daylight window (`data/corpus_p99`, 1,157
windows), with the three lanes stacked as **3,471 lane-windows**. Standardisation
is fitted on these only.

**Primary model, C1-L (regression).** `sklearn` 1.9.0 `LinearRegression()`
(ordinary least squares, no tuning) predicting the **60 s future mean count**,
`mean(c[e+1 … e+30])`. Its class is the prediction passed through the camera's
thresholds.

**Secondary model, C1-L-cls.** `LogisticRegression(C=1.0, max_iter=5000)`,
unweighted, on the same features, with labels at NE 8th's absolute 2 / 8. It
is used **only** in the absolute-threshold arm, because its output is in those
units. It continues P101's model family.

Both are written to `experiments/results/bellevue_pilot/c1L_v1.json` with
their SHA-256 **before any P103 camera is counted**. They are applied
unchanged. Copying NE 8th coefficients onto a camera they were not fitted for
is exactly the transfer being tested, and it is declared as such.

## Cameras and hours — enumerated now

| camera | calibration hour (never scored) | test hours |
|---|---|---|
| 150th Eastgate | Sun 18:08 | Mon 06:08, 10:08, 14:08 |
| 150th Newport | Sun 18:08 | Mon 10:08, 14:08 |
| 150th SE38th | Sun 18:08 | Mon 09:08, 13:08 |

- **On disk:** only these files are used. A camera is identified by
  **filename, never folder**. The unextracted Newport zip (part 002) is
  excluded unless an amendment enumerates its files before any counting.
- **Eligibility:** each file passes the burnt-in clock continuity check
  (start, middle, end), and its resolution and fps are recorded, or it is
  excluded **whole** and reported. If a camera loses its calibration hour, it
  is excluded. If it loses every test hour, it is excluded. Night is excluded
  throughout. 116th NE12th is excluded, because only fragments exist.

## Threshold policy — the primary, fixed now (ADR-017)

**Primary: per-camera calibrated thresholds.** On the camera's calibration
hour, pooled over its lanes, the 60 s future means of every eligible window
are computed. Their 33rd and 67th percentiles (`numpy.percentile`, linear) are
`q33` and `q67`.

| class | rule |
|---|---|
| LOW | mean ≤ q33 |
| MEDIUM | q33 < mean ≤ q67 |
| HIGH | mean > q67 |

- The quantity is continuous, so ADR-017's integer-tie problem (P34/P37) does
  not arise. If q33 = 0, LOW means an empty lane.
- The thresholds use the **calibration hour only**, which is disjoint from
  every test hour. They are written to the corpus manifest and committed
  **before any test hour is scored**.

**Secondary: absolute NE 8th thresholds, LOW ≤ 2 and MEDIUM ≤ 8.** This is a
separately defined transfer test, reported with the class distribution shift
it produces. The thresholds are **never chosen by test score**: calibrated is
the primary whichever does better.

## Comparators, on the same test windows and thresholds

- **Persistence:** the previous-window mean, classed by the same thresholds.
  C1-L contains it as a special case, so C1-L − persistence is what the
  learned part adds.
- **Calibration prior:** for each lane, the most frequent class in the
  camera's calibration hour. It is a no-skill reference. Under calibrated
  thresholds it is near-uniform by construction, and it is reported with that
  caveat.
- **Clock prior: not applicable.** A new camera has no training hours to draw
  one from, and this is stated, not concealed.

## Statistics

- Macro-F1, with LOW, MEDIUM and HIGH recall and the confusion matrices. The
  primary pools the cameras.
- **The block bootstrap is stratified by camera**: 10-minute blocks are
  resampled within each camera, 10,000 resamples, seed 0. A camera's weight is
  therefore fixed by its own data and cannot drift between resamples.
- **Primary family, Holm at 0.05**, calibrated thresholds, all cameras pooled:
  1. C1-L − persistence;
  2. C1-L − calibration prior.
- **Secondary family, Holm at 0.05:**
  - C1-L − persistence for each camera separately;
  - LOW recall, C1-L − persistence, pooled;
  - in the absolute 2/8 arm, C1-L-cls − persistence and C1-L − persistence,
    pooled.
- **Reported always:**
  - per camera: support, the thresholds and each camera's class distribution
    under both policies;
  - pooled results only beside the per-camera ones.

## Before scoring — the checks that stop the run

Each check is reported **before** any model is scored:

- lane review and continuity;
- class support per camera under both threshold policies;
- that the calibration and test hours are disjoint.

If a camera has **fewer than 10** lane-decisions of any class in its test
hours under the primary policy, that class is flagged on that camera. If the
pooled test has fewer than 30 of any class, the run stops for an amendment
before scoring.

## Interpretation, fixed now

- **C1-L beats persistence pooled, and in at least two of the three cameras on
  point estimates:** count forecasting transfers to new cameras in this
  dataset.
- **C1-L beats persistence pooled, but one camera drives it:** transfer is
  reported as camera-dependent.
- **No improvement over persistence:** the NE 8th gain does not transfer, and
  the learned forecaster is not shown to beat the count it starts from.

Three cameras from one city, on one Sunday and Monday, can show transfer
within this dataset. They **cannot** show universal generalisation.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).
