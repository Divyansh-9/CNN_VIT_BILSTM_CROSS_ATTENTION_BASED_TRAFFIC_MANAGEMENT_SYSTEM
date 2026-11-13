# S63b — horizon diagnostic, fixed before any 180 s or 300 s label existed

Written 2026-10-15, after P92 (60 s: neither the Bellevue pilot nor S61 beats
persistence) and before `rehorizon_corpus.py` had been run at any new horizon.

## Question

Does a longer forecast horizon leave room for a model to beat persistence on
this camera? **This is a diagnostic on one camera and one recording** — not
evidence of generalisation, and not a substitute for unseen cameras.

## Fixed

- **Data:** Bellevue NE 8th, 15:08–17:08, the same `counts.csv`. No detector
  rerun.
- **Horizons:** **180 s, then 300 s.** 60 s stays the reported baseline and is
  not re-run.
- **Everything except the horizon** is unchanged: geometry (T 60, step 2 s,
  stride 30 s), smoothing (median 3), and the buffered chronological 60/20/20
  split. The buffer grows with the horizon, so no input or target crosses a
  boundary. The tool reproduces the 60 s corpus exactly.
- **Thresholds are frozen** at the 60 s corpus's per-camera values, LOW ≤ 2 and
  MEDIUM ≤ 8. They are never recalibrated per horizon. Class support at each
  horizon is reported before any score, and a missing class is reported, not
  repaired.

## Per horizon

1. **Before any training:** report window counts, class support by split, and
   **persistence on the validation period**. This is the room-for-a-model
   diagnostic; it reads no test data.
2. **Train** G and H at seeds 42 1 7 13 21.
3. **Select** on validation macro-F1 only: the config with the higher mean,
   then its best seed.
4. **Read the test period once**, for the selected run, beside persistence and
   the majority class on the same test windows. Report macro-F1, accuracy,
   QWK, per-class support and per-lane accuracy.

**Persistence** is causal: the label of the **raw** count at the window's last
observed sample, under the same thresholds. The smoothed value there would
look one sample past the window.

## What "beats persistence" means

**The paired bootstrap 95% interval of (model − persistence) test macro-F1
excludes zero.** That is 10,000 resamples of test windows, each window's four
lanes kept together.

- An interval that contains zero is reported as **not distinguishable**, not as
  a win or a loss.
- With about 29 test windows, a raw difference alone would be noise.

## Stop rule

If neither 180 s nor 300 s beats persistence by this definition, **stop
changing the horizon** and investigate the label definition and the quality of
the detector-derived target, as the project owner decided. Both horizons are
reported whatever they show. Neither is chosen by its test result and then
presented as independent confirmation.
