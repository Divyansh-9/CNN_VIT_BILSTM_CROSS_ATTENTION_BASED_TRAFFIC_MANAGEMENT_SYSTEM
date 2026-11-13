# P97 — three-lane Bellevue retrain, fixed before any training

Written 2026-10-15, after the project owner approved Option 1 (P96): rebuild
Bellevue with the west, north and east lanes only, because the south approach
is not observable from this camera. The four-lane corpora, the P94 results and
S61 are unchanged and still reproducible.

## What changes, and only this

| | four-lane, P94 | three-lane, P97 |
|---|---|---|
| lanes | W, N, S, E | **W, N, E** |
| lane names | lane_0 W, lane_1 N, lane_2 S, lane_3 E | lane_0 W, lane_1 N, **lane_2 E** |
| counts | as built | re-derived by `relane_corpus.py` from the same `detections.csv` |

- **Counts:** west and north are identical in 3,600 of 3,600 samples. East is
  identical in 3,577: with the south centre gone, 23 border samples (0.6%) now
  fall to the nearest remaining centre.
- **Splits:** carried over verbatim. The 60 s and 120 s sustained corpora have
  exactly P94's windows and splits.
- **Unchanged:** the detector, the counts' source, the frozen thresholds (LOW ≤
  2, MEDIUM ≤ 8), the target definitions (P94), the feature cache, the seeds,
  and the selection and test rules (P94, including H on an exact config tie).

## Runs

- **Targets:** 60 s and 120 s sustained level, three lanes.
- **Models:** G and H × seeds 42 1 7 13 21 — 20 runs.
- **Selections** are written to `selection_P97.json` and committed **before any
  test is read**.
- **Test, read once:** G and H against the previous-window mean, with a paired
  bootstrap 95% interval. "Beats" means the interval excludes zero.

## How the result may be compared

**This is a different task from P94, and its scores are not compared with
P94's as if they were the same.** Three lanes against four changes the label
population: the near-constant south lane is gone, and it was right almost by
default. The comparison that counts is **within P97** — each model against the
previous-window mean on the same three lanes and the same test windows.

It is reported as a **three-lane, single-camera temporal evaluation**. The
audit's detector undercount — west 14%, north 27%, east 41%, worse when busy —
remains a limitation of every label here. Removing the south lane fixed an
invalid region, not the detector.

## Interface note (not changed by this run)

The contract maps a missing approach to 0.0, which is also the value of LOW,
so absence and "no congestion" are indistinguishable in PPO's state (P97a).
This run trains and evaluates the forecaster only; nothing consumes indices
11–14 live. The state-vector question is the project owner's decision,
because changing it invalidates every PPO checkpoint.
