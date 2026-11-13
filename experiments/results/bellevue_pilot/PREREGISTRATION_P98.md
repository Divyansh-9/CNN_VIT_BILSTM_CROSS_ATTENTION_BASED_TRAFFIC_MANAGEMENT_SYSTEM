# P98 — out-of-time evaluation of the frozen P97 model, fixed before any new footage

Written 2026-10-15, after P97 (three lanes, 60 s sustained level: G beats the
previous-window mean, [+0.027, +0.225] on 29 test windows), and **before any
footage beyond 15:08–17:08 was on disk**. Phase 1 of the project owner's plan:
does the P97 result replicate at other times on the same camera?

## Nothing is trained

The model is **frozen**, and no retraining or reselection happens on new data.

| | |
|---|---|
| primary model | P97 60 s, G seed 13: `models/mfstnet/bellevue_3lane_sus60/mfstnet_G_seed13.pt` |
| secondary model | P97 120 s, H seed 42 (selected by P97's rule) |
| baseline | previous-window mean, as in P94/P97 |
| frozen | three-lane geometry (west, north, east), the detector (ITD-xl, conf 0.45, imgsz 992), thresholds LOW ≤ 2 / MEDIUM ≤ 8, preprocessing hash `a4142d1ab333226b`, target definitions |

## The footage, by stratum

The folder holds 23 hourly files, each starting within 4 s of an hour after the
last. The two already on disk (Monday 15:08–17:08) contain all of P97's
training, validation and test data, and are **not** reused.

| stratum | hours | role |
|---|---|---|
| **Monday daylight, 07:08–15:08** | 8 | **primary** |
| Monday 06:08 dawn, Sunday 19:08 dusk | 2 | secondary |
| Sunday 18:08 daylight, weekend | 1 | secondary |
| night, Sunday 20:08 – Monday 06:08 | 10 | **excluded.** P96 audited the detector in daylight only, so night labels have no measured validity. Night needs its own audit first |

## Building the evaluation windows

- **Each hourly file is its own clip.** No window spans two files, so no
  inter-file join has to be trusted.
- **Continuity:** each file's burnt-in clock is checked at its start, middle and
  end. A file with a gap is excluded **whole**, and the exclusion is reported.
- **Windows:** T 60, step 2 s, stride 30 s, and the 60 s and 120 s sustained
  targets exactly as defined in P94.
- **Buffer against P97's data:** the Monday 14:08 file ends where P97's
  training begins (15:08:32). Its windows whose input plus target reaches the
  last 149 samples of the file are dropped, so no evaluation window sits
  against P97's training period.
- **The detector** is run frozen, with the three reviewed lanes, through the
  existing corpus tools.

## Primary comparison — exactly one

On the primary stratum, 60 s target: **G − previous-window mean, macro-F1**, on
identical windows.

- **Uncertainty: block bootstrap.** Windows are grouped into 10-minute blocks
  (about five signal cycles, P93), and whole blocks are resampled — 10,000
  resamples. Overlapping windows and signal cycles are correlated, so the
  effective sample is the number of blocks, not of windows.
- **"Replicates"** means the 95% interval excludes zero **and** the point
  estimate is positive.

## Secondary comparisons — Holm-corrected as one family

1. The primary comparison per lane: west, north and east.
2. The 60 s comparison on the dawn/dusk stratum, and on Sunday daylight.
3. The 120 s target, primary stratum, H against the previous-window mean.
4. Accuracy and QWK for the primary comparison.

Each is reported with its interval and Holm-adjusted at a family-wise 0.05.
**None can rescue a failed primary**, and none is promoted after the fact.

## Reported regardless of outcome

- Class support per stratum. A class with fewer than 10 decisions is flagged
  and its F1 is not interpreted.
- The number of blocks and windows behind every interval.
- The detector limitation from P96: undercount 14% / 27% / 41%, measured in
  daylight on this camera.

## What this cannot show

Generalisation to another camera, which is Phase 2. Anything about night.
Anything about Indian traffic.

## Licence

Unresolved: research use only, internal engineering, not publishable (S63).
