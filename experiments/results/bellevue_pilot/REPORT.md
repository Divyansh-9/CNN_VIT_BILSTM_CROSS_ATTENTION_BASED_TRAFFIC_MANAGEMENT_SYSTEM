# S63 Bellevue pilot — the seven checks

One camera (Bellevue NE 8th), two contiguous hours (Monday 11 Sep 2017,
15:08–17:08). Run under [PREREGISTRATION.md](PREREGISTRATION.md) and its
Amendment 1, both written before any label existed. **This is a single-camera
temporal evaluation and a pipeline check.** It is not unseen-camera
performance, not Indian evidence, and not publishable while the licence is
unresolved.

## Verdict

**The pipeline works end to end on Bellevue footage:** video, detection,
reviewed lanes, corpus, labels, feature cache, training, validation-only
selection, held-out test. **The model does not beat persistence.** On the
held-out final period it is below "congestion in 60 s equals congestion now" on
macro-F1 and accuracy, and above it only on ordinal agreement (QWK).

## 1. Corpus integrity — pass

- **Samples:** 3,600, against an expected 7,200 s / 2 s. Indices are contiguous
  0–3599 and every interval is exactly 2.0 s, so no decode failures and no
  missing samples.
- **Camera clock:** 15:08:32, 16:08:32 and 17:08:30 at file positions 0, 3600
  and 7198 s. The hour join is seamless.
- **Windows:** 235 built, 175 kept after the split buffers — train 127,
  validation 19, test 29.

## 7. No window or target crosses a split boundary — pass

Each window spans its 60 input samples and its target 30 samples later. The
buffer is a full window plus the horizon (149 samples).

| split | windows | samples covered, first input to last target |
|---|---|---|
| train | 127 | 0–1979 |
| validation | 19 | 2355–2714 |
| test | 29 | 3090–3599 |

There are 375 samples between train and validation, and 375 between validation
and test. No overlap.

## 2. Label distribution — task supported only in a limited sense

**Raw per-lane counts** per 2 s sample:

| lane | median | p90 | max | zero share |
|---|---|---|---|---|
| lane_0 | 7 | 11 | 16 | 0% |
| lane_1 | 8 | 14 | 19 | 1% |
| lane_2 | 0 | 1 | 4 | 63% |
| lane_3 | 6 | 10 | 19 | 1% |

| rule | HIGH, train / val / test |
|---|---|
| original fixed thresholds, LOW ≤ 4, MEDIUM ≤ 15 | 4 / **0** / **0** (0.6% overall) |
| **primary:** per-camera p33/p67, LOW ≤ 2, MEDIUM ≤ 8 | 28.1% / 23.7% / 20.7% |

- **In absolute terms this is MEDIUM traffic at most.** HIGH under the original
  rule never reaches validation or test.
- **The primary rule produces HIGH by construction**, as the busiest third of
  this camera's range. It does **not** rise toward the peak: HIGH share stays
  flat, between 21% and 32%, across all six 20-minute bins. The evening peak is
  not distinguishable in these labels.
- **lane_2, the south approach, is degenerate:** a median of 0 vehicles, empty
  in 63% of samples, and **zero HIGH under either rule**. It is a constant LOW.
- **Thresholds were frozen.** One leak is recorded, not corrected: the p33/p67
  cut points were computed over all windows, the test period included. That is
  a label definition, not training, but strictly the cut points should come
  from training alone.

## 3. Detector biases — measured, carried as limitations

| bias | measured | effect |
|---|---|---|
| US cars as `autorickshaw` | 3,041 detections, **3.6%** of vehicles | 1.2 PCU instead of 1.0 |
| `two wheeler` | 5,812, **7%** of vehicles; implausibly many for this junction | 0.3 PCU each; biases the other way |
| painted bicycle symbol | detected in **21%** of samples, 0.241 from the west centre, inside the 0.25 reach | intermittent addition to the west lane |
| far end of the north queue | missed, seen on inspection | cannot be quantified without hand annotation |

Pedestrians are absent from the corpus detections, so they are correctly
excluded. Per-camera thresholds are **not** assumed to make any of these
harmless.

## 4. Feature cache — pass

- **Frames:** all 3,600 cached (1.43 GB); the last window reads back at full
  shape.
- **Preprocessing hash:** `a4142d1ab333226b`, **identical to the S61 training
  cache**. Frames go through the shared `mfstnet/preprocess.py`, which is
  bit-identical to the original transform (P88).

## 5. G against H — not separated on validation

| config | validation macro-F1 by seed | mean |
|---|---|---|
| G | 0.7779 · 0.7733 · **0.8704** · 0.7919 · 0.7842 | 0.7995 |
| H | 0.7842 · 0.7791 · 0.7895 · 0.7813 · 0.7895 | 0.7847 |

The rule selected **G, seed 21** (`selection.json`), reading only the
`config`, `seed`, `val_macro_f1` and `epochs_run` columns.

- G's lead in the mean is **0.015**. G's seeds alone span **0.77–0.87**, and the
  mean rests on one outlier seed.
- Validation is 19 windows, 76 lane decisions, so one decision moves macro-F1
  by about 1.3 points.
- **G and H are not separated.** The selected seed is the most likely to have
  been lucky on a small validation period — selection on a noisy maximum.

## 6. Held-out test — read once

| model, on the same 29 test windows | macro-F1 | accuracy | QWK |
|---|---|---|---|
| **G, seed 21 (selected)** | **0.5644** | 0.569 | **0.5402** |
| persistence: the label of the last observed sample | **0.5875** | **0.638** | 0.4638 |
| majority class | 0.2171 | 0.483 | — |

**Per class (G):** LOW F1 0.845 on 36, MEDIUM 0.531 on 56, HIGH **0.318** on
24.

**Per lane (G):** lane_0 12 of 29, lane_1 13 of 29, lane_2 **29 of 29**, lane_3
12 of 29. The degenerate lane is right every time, so on the three real lanes
G is right on **37 of 87, about 43%**.

- **Validation 0.8704 fell to test 0.5644.** That is what selecting the best of
  five seeds on 19 windows does.
- **Persistence beats G on macro-F1 and accuracy.** G is better only on QWK, so
  its mistakes are less often two classes off.
- **This is A32 in the data.** Labels are a deterministic function of the count,
  and one minute ahead the count mostly is what it was. A model has to beat
  that to have learned anything, and here it does not.

## What this supports

- **Supported:** the tooling processes Bellevue end to end and reproducibly.
  The P91 override was safe for building a corpus.
- **Not supported:** that MFSTNet forecasts congestion on this camera better
  than persistence.
- **Not tested:** unseen cameras. That needs at least three Bellevue cameras.

## Context: S61 against the same baseline

Persistence is also ahead of G on all four of S61's foreign folds — 0.4492
against 0.4225, 0.6924 against 0.4671, 0.6726 against 0.4089, and 0.4141
against 0.3297 (P92). The finding is not specific to Bellevue. It is a
property of the forecasting target as currently defined.

## S63b — horizon diagnostic, under PREREGISTRATION_horizon.md

Labels were re-derived from the stored counts by `scripts/rehorizon_corpus.py`,
which reproduces the 60 s corpus exactly. Thresholds stayed frozen (LOW ≤ 2,
MEDIUM ≤ 8). The paired bootstrap ran 10,000 resamples, each test window's
lanes kept together.

| horizon | test windows | selected | model F1 | persistence F1 | difference [95% CI] | verdict |
|---|---|---|---|---|---|---|
| 60 s | 29 | G s21 | 0.5644 | 0.5875 | −0.023 [−0.114, +0.079] | not distinguishable |
| **180 s** | 21 | G s21 | 0.6165 | 0.5848 | +0.032 [−0.061, +0.128] | **not distinguishable** |
| 300 s | — | — | — | — | — | **infeasible on two hours** |

- **300 s.** The buffer grows to 269 samples per boundary and empties the
  validation split. `assign_splits_temporal` refused, which is correct.
- **Validation at 180 s is 7 windows (28 decisions).** G and H **tie exactly**
  on mean validation macro-F1 (0.8254). The tie went to G alphabetically: the
  rule has no explicit config tie-break, and that is disclosed here, not
  hidden. With 28 decisions, selection is close to chance.
- **Persistence did not weaken with the horizon.** On validation it rose from
  0.6132 at 60 s to 0.6889 at 180 s, so a longer horizon showed no sign of
  opening room for a model.
- **Class support** was present at 180 s in every split (HIGH 135 / 6 / 14).

**Correction to the 60 s wording.** "The model does not beat persistence" is
supported. "Persistence beats the model" is **not** — the interval contains
zero.

**Stop rule applied.** Neither horizon beats persistence, so the horizon is not
changed again. Next is the label definition and the quality of the
detector-derived target, as decided in advance.

## Correction to check 3 (P93a)

Labels count **vehicles**, not PCU: `pcu_total` is never called by the corpus
pipeline. The PCU effects stated in check 3 are therefore wrong. A car read as
an `autorickshaw` changes no label. What changes a count:

- the painted bicycle symbol adds **one vehicle** to the west lane in 21% of
  samples;
- each `two wheeler` detection is one vehicle;
- the far queue is under-counted.

## P94 — sustained-level targets (see PRD-CHANGELOG P94)

| target | selected | test F1 | baseline F1 | difference [95% CI] |
|---|---|---|---|---|
| 60 s sustained | G seed 13 | 0.7167 | 0.6470 | +0.070 [−0.017, +0.156] |
| 120 s sustained | H seed 42 (validation tie) | 0.7718 | 0.7139 | +0.058 [−0.027, +0.147] |

Not distinguishable on either target. All point estimates favour the models,
and the test windows (25–29) are too few to resolve them.

## Label-quality audit (P95)

A blind hand count of 20 frames. The detector undercounts west by 15%, north by
39% and east by 45%; it ranks frames well on those three lanes (correlation
0.77–0.84) but compresses busy ones. The south lane is close to noise
(correlation 0.41). The painted symbol was reported as a bicycle in 6 of 20
frames.

## 60-frame audit (P96)

| lane | undercount | ranking (Pearson) |
|---|---|---|
| west | 14% [9, 19] | 0.82 |
| north | 27% [20, 33] | 0.80 |
| east | 41% [34, 47] | 0.71 |
| south | 79% [66, 88] | 0.16 — no reliable signal |

The undercount grows with traffic on every lane. The south approach is not
observable from this camera.
