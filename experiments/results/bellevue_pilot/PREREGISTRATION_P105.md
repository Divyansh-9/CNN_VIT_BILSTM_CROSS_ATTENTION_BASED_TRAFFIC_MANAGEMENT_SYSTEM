# P105 — does forecasting the change transfer where forecasting the level did not? Fixed before any footage is chosen

Written 2026-10-16, after P103 and P104.

- **What P103 found:** a count forecaster fitted on NE 8th carried that
  camera's level (about 6.1 vehicles per lane) into cameras averaging 1.2–2.6.
  Its forecasts ran +0.66 to +0.78 high, and it lost to persistence by −0.222.
- **The hypothesis:** forecasting each lane's **change** from its own recent
  level, with a model that cannot represent a level at all, transfers across
  cameras.
- **Status:** no footage has been chosen, downloaded, extracted or counted for
  P105.

Frozen and untouched: persistence v1 (`persistence@2431c6641b9c`), which stays
the prototype's forecaster whatever P105 finds until a promotion is decided
separately; P97–P104; the detector (ITD-xl, conf 0.45, imgsz 992, step 2 s).
**Forecasts are not connected to signal timing (P97a).**

## Target and inputs

- **Inputs:** one lane's own counts over the 60 samples (2 min) before the
  forecast time, s … e. There is no other lane, no camera identity, no clock
  and no date.
- **Target (change):** `Δ = mean(c[e+1 … e+30]) − mean(c[e−29 … e])`, the
  next 60 s mean minus the last 60 s mean.
- **The forecast count** is `max(0, mean(c[e−29 … e]) + Δ̂)`.
- **The class** is that count passed through the **test camera's** thresholds:
  LOW ≤ q33, MEDIUM ≤ q67, HIGH above. q33 and q67 are taken from the camera's
  calibration period (60 s future means, pooled over lanes, linear
  percentiles, **full precision**). They are disjoint from every test period
  and committed before scoring.

## Methods — all frozen here, with no search

| method | Δ̂ | fitted? |
|---|---|---|
| **persistence** (comparator) | 0 | no |
| **trend** (the frozen count-change baseline) | `mean(c[e−29 … e]) − mean(c[e−59 … e−30])`, the last minute-over-minute change continued | no |
| **ridge** (the one learned model) | `sklearn` 1.9.0 `Ridge(alpha=1.0, fit_intercept=False)` on 5 **difference** features (below), unstandardised | yes |

**Ridge features**, all differences of the lane's own counts:

1. `mean30 − mean60`
2. `mean15 − mean30`
3. `mean5 − mean15`
4. `last − mean30`
5. the least-squares slope over the 60 samples

`meanN` is the mean of the last N input samples. Every feature is a difference
and there is **no intercept**, so ridge's Δ̂ is unchanged by adding a constant
to a lane's counts, and scales exactly with the counts. It **cannot carry a
camera's level**, by construction. Standardising would break that property, so
none is applied.

**Training data, fixed now:** every eligible window of footage **already used**
before P105:

- NE 8th, 13 daylight hours (`data/corpus_p99`);
- the 10 P103 hours of Eastgate, Newport and SE38th (`data/corpus_p103`).

All lanes are stacked. These were spent as tests elsewhere and are not P105's
test. **No P105 test footage is ever used for fitting.** The fitted
coefficients are written with their SHA-256 and committed **before** any P105
footage is counted.

## Footage — chosen after this is committed, by rule

**Eligible test footage** must meet all of these:

- a camera or hour **never counted** in P91–P103;
- daylight, between 06:08 and 19:08 local start times, with night excluded;
- continuous by the burnt-in clock at start, middle and end, or excluded
  whole;
- identified by filename, never by folder.

**Per camera:**

- the **calibration period** is its **earliest** eligible daylight file, and is
  never scored;
- the **test** is every later eligible daylight file;
- a camera without at least one of each is excluded;
- lanes are placed by the project owner on **calibration-period frames only**,
  before any detector run, and locked by amendment, as in P103.

**Order of work:**

1. Inspect what already exists: the unextracted Newport archive (part 002) and
   116th NE12th. That means file listings, durations and the clock, but **no
   detector run and no model output**.
2. If those cannot meet the support rule below, choose new downloads from the
   source by the same eligibility rule, enumerated in an amendment before
   counting.

## Before scoring — checks that stop the run

The following are committed before scoring:

- continuity and eligibility of every file;
- the locked lanes;
- the thresholds.

On top of those:

- **Class support:** if the pooled test has fewer than **30** lane-decisions
  of any class under the calibrated thresholds, the run **stops** for an
  amendment. A camera with fewer than 10 is flagged on that camera.
- **Volume:** at least **6** ten-minute test blocks pooled, or the run stops.

## Evaluation — one read

10-minute blocks, with the **bootstrap stratified by camera** (blocks
resampled within each camera, 10,000 resamples, seed 0).

**Primary family, Holm at 0.05**, pooled:

1. **ridge − persistence, macro-F1** of the congestion class;
2. **persistence − ridge, MAE of the forecast 60 s mean count**. Positive
   means ridge's counts are closer.

**Secondary family, Holm at 0.05:**

- trend − persistence, on macro-F1 and on MAE;
- ridge − persistence macro-F1, per camera;
- ridge − persistence LOW recall, pooled.

**Reported always:**

- per camera: thresholds, support, and each method's macro-F1, per-class
  recall, MAE and mean signed error (bias);
- confusion matrices;
- the **near-empty lanes** (mean future count < 0.5), kept and marked, never
  dropped on their scores.

## Interpretation, fixed now

| result | reading |
|---|---|
| ridge beats persistence on **both** primaries | change-forecasting transfers: on these cameras it improves counts and classes beyond persistence |
| ridge better on MAE only | it forecasts counts better, but not enough to change congestion classes |
| ridge not better on either | no transferable improvement over persistence; persistence stays |
| trend worse than persistence | naive continuation hurts, which is expected at a signalised junction (P93's 2-minute cycle) and reported, not explained away |

**No promotion follows automatically.** Even if ridge beats persistence,
replacing persistence v1 in the prototype is a separate decision. Neither
result says anything about signal-control safety.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).

## Amendment 1 — the exact footage (Option B), lanes and rules, before any download

Written after a **read-only listing** of the source folders (file names only)
and **before any P105 file was downloaded or counted**. The project owner chose
Option B: a subset fixed by rule, smaller than "every later eligible file".

**Files** (16; names and Drive ids in `p105_files.json`):

| camera | calibration (never scored) | test |
|---|---|---|
| 116th NE12th | Sun 19:08 | Mon 07:08, 12:08, 16:08 |
| 150th Eastgate | Sun 19:08 | Mon 07:08, 12:08, 16:08 |
| 150th Newport | Sun 19:08 | Mon 07:08, 12:08, 16:08 |
| 150th SE38th | Sun 19:08 | Mon 07:08, 12:08, 16:08 |

**How the subset was fixed:**

- **The calibration hour** is each camera's earliest eligible daylight hour,
  by the committed rule.
- **The test hours** are fixed to morning, midday and afternoon on every
  camera. 12:08 is used throughout because 116th has no 13:08.
- **None of these hours was counted in P91–P103.**
- **Exclusions:** NE 8th has no untouched daylight hour left. The second
  Newport archive is no longer on disk and is not used. The short local 116th
  fragments are not used; only the source files above are.

**Lanes:**

- **Eastgate, Newport and SE38th reuse their P103 lanes, frozen.** These are
  the centres in P103 Amendment 1. No region is moved.
- **116th NE12th's lanes** are placed by the project owner on frames from its
  Sun 19:08 calibration hour only, then reviewed and locked by Amendment 2
  before any detector run.

**Calibration, support and scoring — the committed rules, restated:**

- **Thresholds:** q33/q67 of the calibration hour's 60 s means, pooled over
  lanes, at full precision.
- **Stop rules:** fewer than 30 pooled lane-decisions of any class, or fewer
  than 6 ten-minute test blocks, **stops** the run. Hours are **never**
  changed on observed results. A file failing continuity is excluded whole,
  with no substitute chosen.
- **The model:** `p105_ridge_v1.json` (sha `73532968…`), applied unchanged.
  It is never refitted on these cameras or tuned on their results.
- **Scoring:** one read. The primary family is ridge − persistence on
  macro-F1 and on forecast-count MAE (Holm). The secondaries are those
  pre-registered.

**Limitations, stated now:**

- **The calibration hours run into dusk**, with sunset about 19:25. P99b's
  blind audit did cover NE 8th at Sun 19:08 (ITD-xl LOW precision 0.89). A
  Sunday-evening calibration may sit lower than Monday traffic, as P103 found
  at Eastgate.
- **About 70 blocks** gives less precision than Option A would. Clearing the
  6-block floor is not a guarantee of power, so every interval and per-camera
  result is reported.
- **The ridge specification** was chosen and fitted on footage already used.
  P105 tests its **transfer** to new cameras and hours. It does not
  independently confirm how that specification was selected.

If the result is inconclusive, more footage (Option A or other cameras) is a
**separate, newly specified experiment**. It is not an extension of this one.

## Amendment 2 — 116th NE12th lanes locked (before any detector run)

The project owner placed 116th NE12th's lanes on its Sun 19:08 calibration
frames (`scripts/p105_lane_page.py`), with no detector run.
`import_lane_centres.py` validated them: four lanes, centres ordered left to
right.

| camera | lane centres (x, y), normalised |
|---|---|
| 116th_NE12th | lane_0 (0.2019, 0.6833); lane_1 (0.4321, 0.2041); lane_2 (0.7403, 0.2808); lane_3 (0.7691, 0.7492) |

- **Review:** one region per approach queue (north, east, south-east arm,
  west). The painted central box is largely outside every region, and no two
  centres are near-duplicates.
- **Limitation:** the south-east region's lower edge includes part of a
  foreground signal head.
- **Reviewer:** "unrecorded". The placement was supplied by the project owner
  in this session, and no name is filled in on their behalf. Approaches are
  unnamed.

Eastgate, Newport and SE38th keep their P103 lanes unchanged (Amendment 1).

## Amendment 3 — build and evaluator committed before any P105 file is counted

- `scripts/p105_build.py` builds the 16 files with the frozen detector and the
  locked lanes. It records a refused file as an exclusion and substitutes
  nothing.
- `scripts/p105_eval.py`:
  - **Thresholds** come from calibration hours only, at full precision, with
    the stop rules enforced: pooled support < 30, or fewer than 6 blocks.
  - **Scoring** checks the ridge model's SHA-256 against `73532968…` and
    refuses unless the thresholds are committed.
  - **Methods and families** are exactly as registered.
  - **Near-empty lanes** (mean future count < 0.5) are marked and kept.
- **Dry run:** the evaluator ran end to end on **synthetic** counts in a
  scratch directory, never P105 data, to confirm every code path and the sign
  of each difference.
