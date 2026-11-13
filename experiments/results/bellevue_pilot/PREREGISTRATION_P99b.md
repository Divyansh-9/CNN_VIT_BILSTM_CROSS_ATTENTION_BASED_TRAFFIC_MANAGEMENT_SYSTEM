# P99b — are the morning LOW labels real? Blind counts at dawn, glare and dusk

Written 2026-10-15, **before any frame was chosen, and before any candidate
detector was run on these hours.** P99a's selected candidate (M1280, COCO
YOLOv8m at 1280) has never been run on these hours.

## Why this comes before P99

Per-hour target counts (P98 corpus, the frozen 2/8 thresholds) show **297 of
the corpus's 343 LOW lane-decisions (87%)** come from three hours: Mon 06:08
(182), 07:08 (56) and 08:08 (59). Those are the dawn and low-sun-glare hours.
Hours 09:08–16:08 hold 0–5 LOW each.

P96 measured the detector only in the busy afternoon. If it undercounts
heavily in dawn light or glare, those LOW labels are a detector failure, not
quiet traffic. A model trained on them would learn that glare means LOW. P99
cannot be designed until this is known. The same hand counts also give the
confirmation that P99a requires before any detector is adopted.

## Frames — systematic, fixed by seed, not chosen

- **Hours:** Mon 06:08, 07:08 and 08:08, and Sun 19:08 (dusk, 21 LOW). That
  is 4 files from `data/_bellevue/p98/`.
- **Per hour:** the 1,800 samples are cut into 15 bins of 120 samples (4
  minutes). One sample is drawn uniformly in each bin by
  `random.Random(2028)`, hour by hour in the order above. That gives **60
  frames**, no frame selected on any detector output.
- **Decoded** at the corpus's own forward sampling with a stride of 60, which
  is the frame the detector saw.
- **Shown in a seeded shuffled order** (`random.Random(2029)`) so the hours are
  interleaved. The burnt-in clock stays visible, because masking it would hide
  the road.

## Regions and counting rules

The regions are the **three P97 lanes**, the regions the current labels are
built on: each pixel goes to the nearest of west, north and east within 0.25
(normalised). The counting rules are `AUDIT_PROTOCOL.md`'s, unchanged:

- count moving, waiting and parked vehicles, by body centre;
- count partly visible vehicles if they are recognisably vehicles;
- never count markings, pedestrians, or riderless bicycles.

Counting is **blind**: no detector boxes or counts are shown, and the
comparison runs only after all 60 frames are exported.

## Reported, for ITD-xl (R, from `data/corpus_p98/counts.csv`) and M1280

Each detector is run through `scripts/detector_benchmark.py`'s harness. R must
again reproduce its committed counts exactly.

- Per lane and per hour: MAE, signed bias, undercount, Pearson.
- **LOW validity**, the question this exists for. A lane-frame is LOW when
  its count is ≤ 2, the label threshold. This is a frame-level proxy: labels
  are 60-second means, but a frame is what can be counted. For each detector:
  - **LOW precision:** of the lane-frames the detector calls LOW, the share the
    hand count also calls LOW;
  - **LOW recall:** of the hand-LOW lane-frames, the share the detector calls
    LOW;
  - each with a frame-clustered bootstrap interval (10,000 resamples, seed 0).

## Decision rules, fixed now

1. **Morning LOW labels, under a detector.** If that detector's LOW precision
   is **below 0.80**, its morning LOW labels are judged unreliable. P99 then
   must not train on them under that detector. If it is 0.80 or above, they
   are usable, with the measured precision reported as a limitation.
2. **Adopting M1280.** P99a showed M1280 improves on R in the afternoon. It
   replaces R only if, on this set, the paired frame-bootstrap 95% interval of
   (M1280 − R) 3-lane MAE has an **upper bound below +0.25 vehicles**
   (non-inferiority), **and** its LOW precision is at least R's point
   estimate minus 0.05. Otherwise R stays.
3. **A replacement is a new corpus version.** `data/corpus_p98` and
   `data/corpus_bellevue_3lane` are not overwritten. P97 and P98 stand as
   recorded, under ITD-xl.

## What this cannot show

Detector behaviour at night (excluded throughout), on other cameras, or on
the 60-second mean itself rather than single frames.
