# V1 — pre-registration DRAFT: human-verified prediction quality of the deployed forecasters

**Status: DRAFT.** It is frozen, and renamed to `PREREGISTRATION_V1.md`, only
after the inter-rater gate passes. The labelling page for the main set
refuses until that file exists. **Nothing is scored before the freeze.**

**Design approved by the owner (P135):**
- same-moment sampling from P105's test hours;
- a label-source sensitivity analysis in place of human-fed forecasters;
- the 30-moment minimum for subgroup claims.

**What stays out of scope:**
- **no model is tuned on these labels;**
- P130–P132 stay frozen;
- ADR-023 and `CLAIMS.yaml` are untouched;
- the footage licence is unresolved, so every result is internal evidence
  until V3 resolves it.

## 1. The three questions, kept distinct

| # | question | comparison | what it does **not** claim |
|---|---|---|---|
| Q1 | **Detector error** | detector count against human count, on the same frames (the 15 labelled frames of each moment) | — |
| Q2 | **Deployed-system error** | each deployed forecaster, **fed detector counts** as deployed, against the **human** next-minute target | — |
| Q3 | **Label-source sensitivity** | how the reported forecast conclusion changes under defensible alternative labels (see §5) | **not** a measurement of a forecaster fed or trained on human counts; that experiment is not performed |

**The deployed forecasters,** applied unchanged with their SHA-256 checked:
- **persistence v1** (`persistence@2431c6641b9c`), for the congestion class;
- **ridge v1** (`ridge@73532968dcf2`), for the next-minute count.

## 2. Sample

- **Source:** `v1_sample_manifest.json` (seed 20261017), drawn from P105's test
  hours. No model was fitted, selected or threshold-tuned on them.
- **The pilot:** 40 lane-moments, double-labelled. It is used only for the
  inter-rater gate and the rate and SD estimate. **It is never scored for
  Q1–Q3.**
- **The main set:** the first *n* moments of each stratum's ordered reserve.
  *n* is set at the freeze from the pilot's measured labelling rate and the
  spread of the per-moment differences. The target is a 95% CI half-width of
  **0.15 vehicles** on the ridge-minus-persistence MAE.
- **Double-labelling for quality control:** 20% of the main set is
  double-labelled. The ICC on it is reported. If it falls below 0.8, that is
  flagged.
- **Subgroups:** a stratum with fewer than **30** moments, such as Eastgate
  LOW (*n* = 8), is **descriptive only**, and no claim is made on it.

## 3. The human target

- **15 frames per lane per minute** (*t* + 2 … *t* + 30 samples, 4 s apart).
  It was chosen by V1-1, on detector series only: MAE 0.102, class agreement
  0.956.
- **Frames entered as -1 (unusable)** are excluded. A moment with more than 3
  unusable frames is dropped from scoring and counted.
- **Primary label:** the main labeller's mean over the moment's usable frames.

## 4. Endpoints and statistics

| endpoint | forecaster | baseline |
|---|---|---|
| **E1:** MAE against the human next-minute mean | ridge v1 | persistence (the previous 60 s mean) |
| **E2:** 3-class macro-F1 against the human next-minute class (P105's per-camera q33/q67) | persistence v1 | the hour prior |
| reported: detector MAE against human (Q1), by camera and by level | — | — |

**The tests:**
- the paired difference, forecaster minus baseline, per moment;
- a block bootstrap stratified by camera, with 10-minute blocks and 10,000
  resamples (seed 42);
- Holm across E1 and E2.

**The readings, named in advance:**
- **the forecaster beats its baseline on human labels;**
- **no demonstrated difference;**
- **the baseline is better.**

## 5. Q3: label-source sensitivity (reported, not tested)

For each endpoint, the same forecasts are re-scored under four alternatives:
1. **The detector-derived target on the same moments,** which is P105's label
   source. This shows how much the conclusion depends on detector labels.
2. **A sparser aggregation:** 6 of the 15 frames, every 10 s.
3. **Labeller swap:** the second labeller's counts, on the double-labelled
   subset.
4. **Unusable handling:** imputing -1 frames from their neighbours, instead of
   excluding them.

**The conclusion is called robust** if E1 and E2 keep their sign under all
four alternatives, and **label-sensitive** otherwise.

## 6. Freeze checklist

**Each of these must be true before this draft is renamed:**
1. pilot ICC(2,1) ≥ 0.80 (`v1_pilot_agreement_attempt{1,2}.json`);
2. the counting instructions are frozen;
3. *n* is computed and written here;
4. the scoring script (`v1_score.py`) and its tests are committed, and it
   refuses unless this file is committed unchanged.
