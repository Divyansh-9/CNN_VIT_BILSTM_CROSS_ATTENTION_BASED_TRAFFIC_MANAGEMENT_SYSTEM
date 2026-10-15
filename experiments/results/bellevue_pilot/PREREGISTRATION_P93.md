# P93 — target predictability diagnostic, fixed before computing anything

Written 2026-10-15, after S63b (neither 60 s nor 180 s beats persistence) and
before any number below was computed. **Validation and training data only.**
The held-out test period is not read by this diagnostic, so it stays available
for a later pre-registered evaluation.

## The measured quantity

`counts.csv` holds **raw vehicle counts per lane** per 2 s sample.
`count_frame` adds one per vehicle, and `pcu_total` is called nowhere in the
corpus pipeline, so ADR-017's PCU weighting was never applied to any label
(P93a). The targets below therefore use the vehicle count `c`. A PCU version
needs pre-registered class mappings for `LCV` and `two wheeler`, which the PCU
table lacks, and is deferred rather than improvised.

## Window conventions

Windows are the 60 s corpus's own validation windows (19 windows, 4 lanes).
Inputs are samples `s … s+59`, so `e = s + 59` is the last observed sample.
Every quantity below lies inside each window's original span, so nothing
crosses a split boundary.

## Targets, fixed here

| name | definition |
|---|---|
| **sustained level** (primary) | `Y = mean(c[e+1 … e+30])`, the mean count over the next 60 s, classed with the frozen thresholds (LOW ≤ 2, MEDIUM ≤ 8, else HIGH) applied to the mean |
| **direction** (secondary) | `Δ = Y − mean(c[e−29 … e])`; **fall** if Δ < −1, **rise** if Δ > +1, otherwise **stay**. The tolerance of 1 vehicle is fixed here: one vehicle, averaged over a minute, is the smallest change a controller could act on |
| instantaneous (the current target, for reference) | the smoothed count at `e + 30`, classed with the same thresholds |

## Baselines — all causal, all using samples up to `e` only

| baseline | predicts |
|---|---|
| **persistence** | level: `mean(c[e−29 … e])`, classed; direction: always **stay** |
| **naive trend** | level: `mean(c[e−29 … e]) + (mean(c[e−29 … e]) − mean(c[e−59 … e−30]))`, classed; direction: the sign of that recent change with the same ±1 tolerance |

## What is reported

1. **Class distribution** of each target, on train and validation.
2. Persistence and naive trend on **validation**: macro-F1, accuracy and QWK;
   for the level target also mean absolute error on the continuous mean.
3. **Per lane**, so the empty south lane cannot carry an aggregate.
4. **Paired bootstrap** 95% interval of (trend − persistence) macro-F1 on
   validation: 10,000 resamples, each window's lanes kept together.
5. **Autocorrelation** of each lane's count series at lags of 1–90 samples
   (2–180 s), on the **training period only**, to show whether a signal-cycle
   oscillation dominates the instantaneous count.

## Decision rules, fixed here

- **Room for a model** exists on a target only if persistence's validation
  macro-F1 is **below 0.80**, and its classes all have at least 10 validation
  lane-decisions. A target persistence already almost solves leaves nothing for
  a model to add, and one with a starved class cannot be scored.
- If **sustained level** has room: freeze it, and pre-register a G and H
  training run against it.
- If only **direction** has room: it becomes a separate forecasting task with
  its own pre-registration.
- If **neither** has room, or class coverage fails: no training. Investigate
  detector quality and the label definition first.
- **Validation is 19 windows (76 decisions).** Where an interval contains zero,
  candidates are reported as not distinguished, and no winner is chosen.
