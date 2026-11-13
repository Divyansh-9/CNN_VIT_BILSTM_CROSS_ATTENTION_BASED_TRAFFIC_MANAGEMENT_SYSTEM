# P94 — G and H against sustained-level targets, fixed before any training

Written 2026-10-15, after P93 and before either corpus below existed. The S61
model and every earlier test result are untouched. No Bellevue footage is added.

## Data, unchanged

Bellevue NE 8th, 15:08–17:08: `data/corpus_bellevue/counts.csv`, raw **vehicle
counts** per lane per 2 s sample. PCU weighting is **not** activated (P93a);
that is a separate, later decision. The detector limitations from the S63
report and P93a — the painted bicycle symbol, `two wheeler` detections, the
north-queue undercount — are carried into every result as label noise.

## Targets, exact

For a window of inputs `s … s+59`, the last observed sample is `e = s + 59`.
Let `c[i]` be a lane's vehicle count at sample `i`.

| | primary | secondary |
|---|---|---|
| future window K | 30 samples (60 s) | 60 samples (120 s, about one signal cycle — P93) |
| target value | `mean(c[e+1 … e+30])` | `mean(c[e+1 … e+60])` |
| class | LOW if value ≤ 2, MEDIUM if ≤ 8, else HIGH | same |
| `label_index` recorded | `e + 30` (last future sample) | `e + 60` |

- The mean is taken over **raw** counts, with no smoothing and **no rounding**
  before thresholding.
- **The thresholds are frozen** at the 60 s corpus's per-camera values (LOW ≤ 2,
  MEDIUM ≤ 8). They are not recalibrated for either target.

## Split, buffered so no input or future window crosses a boundary

The same chronological 60/20/20 split (`assign_splits_temporal`). Its buffer is
`T + label offset`: 149 samples for K=30, which gives exactly the existing
split, and 179 samples for K=60. For K=60 every window's 60-sample future lies
inside its own split; `tests/test_sustained_corpus.py` checks this.

## Baseline — the previous-window mean, causal

`mean(c[e−K+1 … e])`, the mean over the **same length** of the immediate past,
classed with the same thresholds. It uses samples up to `e` only. The majority
class is reported beside it.

## Training and selection

- **Runs:** G and H × seeds 42 1 7 13 21, for each target — 20 runs. Same
  feature cache (`data/cache_bellevue`) and same training code as S63.
- **Per target:**
  1. **Config:** the higher mean validation macro-F1. **On an exact tie, H**,
     the simpler model.
  2. **Seed, within each config:** the highest validation macro-F1; ties go to
     the earlier seed in 42 1 7 13 21.
- **All four selections are written to `selection_P94.json` before any test
  period is read.**

## Test — read once, after every selection is frozen

For each target, on the same eligible test windows:

- **Models:** G's selected seed, H's selected seed, the previous-window mean,
  and the majority class.
- **Metrics:** macro-F1, accuracy, QWK, class support and per-lane correctness.
- **Uncertainty:** a paired bootstrap 95% interval of (model − previous-window
  mean) macro-F1, for both G and H — 10,000 resamples of test windows, each
  window's lanes together.

"Beats the baseline" means **the interval excludes zero**. Otherwise the result
is **not distinguishable**.

## Interpretation, fixed

- **If a model beats its baseline on the 120 s target and not the 60 s,** that
  supports the full-cycle target for the next stage.
- **If neither model beats its baseline on either target,** the honest result
  stands, and the labels are investigated before any dataset expansion.
- **Everything is one camera and one recording:** a diagnostic, not
  generalisation.
