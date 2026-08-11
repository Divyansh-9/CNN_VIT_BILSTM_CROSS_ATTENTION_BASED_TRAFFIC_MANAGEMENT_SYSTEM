# Implementation Plan 01 — Detection and Corpus Pipeline

| | |
|---|---|
| **Date** | 2026-08-08 |
| **Derived from** | [HLD — Detection & Corpus Pipeline](../02-design/HLD-detection-corpus-pipeline.md) |
| **Owner** | R1 (Data & Detection Lead) · R2 consulted on the cache contract |
| **Delivers** | FR-D08, FR-D09, PRD §8.6 · unblocks M2, M4, M5 |
| **Weeks** | 2–9 |

Work items are ordered by dependency. Each is independently verifiable and small enough to finish in
one sitting. **Do not start an item whose predecessor's verification has not passed** — every
downstream artifact inherits an upstream defect silently.

---

## Phase 0 — Measure before building (Week 2, ~3 hours)

Three measurements that replace the project's largest guesses. Manual §1.2.

### WI-01 · Annotation pilot
Annotate 50 frames (25 peak, 25 off-peak) in Roboflow. Record objects/frame and seconds/frame.
**Done when:** `docs/90-manual/weekly/W02.md` contains both numbers and the projected hours for the
full target. **Why first:** the largest line item in the project is currently a guess.

### WI-02 · Count distribution
Run COCO-pretrained YOLOv8 over any fixed-camera intersection video. Histogram per-lane counts.
**Done when:** the histogram is committed and each of LOW (<5) / MED (5–15) / HIGH (>15) has a stated
share. **Why:** if HIGH never occurs, the class is degenerate, macro F1 ≥0.80 is unreachable, and the
thresholds need recalibrating (PRD pending item P1) **before** a corpus is built around them. Highest
value hour in the semester.

### WI-03 · Feature cache sizing
Cache 100 frames through ResNet-50 and DINOv2. Measure bytes/frame.
**Done when:** measured figure recorded against ADR-005's ~350 KB/frame estimate.

---

## Phase 1 — Detector (Weeks 2–3)

### WI-04 · Acquire and convert IDD
Download IDD Detection (22.8 GB) to Colab local disk or local scratch. Enumerate the real label set
(`grep` recipe in [DATASETS §6](../00-planning/DATASETS.md)) and commit the output — do not trust any
second-hand class list. Convert VOC XML → YOLO.
**Done when:** label inventory committed; converted subset loads in Ultralytics.

### WI-05 · Class mapping
Write `indiatrafficnet/class_mapping.yaml` mapping IDD labels → the 8 PRD §12.2 classes. **Decide the
`rider` convention now** and record it: drop `rider`, count only the vehicle. Counting both inflates
counts by roughly the two-wheeler share (~30%), which would bias every congestion label the §8.6
pipeline produces.
**Done when:** mapping committed; unmapped source classes explicitly listed as dropped, not merged.

### WI-06 · Subsample and persist
Drop images with no target-class object; subsample to ~15–20k. Record the subsample seed and count in
`indiatrafficnet/public_subset.yaml`.
**Done when:** subset reproducible from the committed seed (NFR-07).

### WI-07 · Fine-tune YOLOv8s → `bootstrap_v0`
```bash
yolo detect train model=yolov8s.pt data=indiatrafficnet/public.yaml \
     epochs=50 imgsz=640 batch=16 seed=42 project=runs/detect name=bootstrap_v0
```
**Done when:** weights in `models/` via LFS; experiment record written **at run start**.

### WI-08 · FR-D08 / FR-D09 evaluation harness
Script producing `experiments/results/detection_map.csv`: mAP@50 and mAP@50:95 **per class, with
sample count per class** (PRD §20 L7 requires the count beside the metric). Same test set under
COCO-pretrained and fine-tuned weights.
**Done when:** CSV committed; the ≥10% overall / ≥25% auto-rickshaw criterion evaluated and reported
**whether or not it passes** (BR-19).

---

> ### Progress — 2026-08-10
>
> **WI-12, WI-13 and part of WI-15 are done and passing.** `mfstnet/corpus/` implements the label
> rule, window timing, and clip-level split assignment; `tests/test_corpus.py` covers them with 38
> assertions including six A15 regressions.
>
> **This reorders the plan deliberately.** WI-01..03 are blocked on a Python 3.11 environment and on
> video that does not exist yet — both human tasks with lead time. The pipeline's *structure* does not
> depend on those measurements; only its config values do, and those live in `mfstnet/configs/spec.yaml`.
> Writing the logic first means WI-02 becomes a short run when video arrives rather than a day of
> coding, and it front-loads the arithmetic that A15 got wrong.
>
> Still blocked and unchanged in priority: WI-01, WI-02, WI-03, and everything needing the detector.

## Phase 2 — Pipeline skeleton (Week 3, dev data)

Build against public fixed-camera video with COCO YOLO. These labels are throwaway — the point is
exercising plumbing.

### WI-09 · S0 source registry
`sources/<id>.yaml` per the HLD contract: clips, fps, **normalised** lane polygons, licence,
`kind: dev|production`. Validate polygons non-overlapping at registration.
**Done when:** a dev source loads; an overlapping-polygon fixture fails with a clear error.

### WI-10 · S2 frame store
Video → unique frames at 5 s → `data/frames/<source>/<clip>/<idx>.jpg`. Idempotent.
**Done when:** re-running adds nothing; frame count matches `duration / 5`.

### WI-11 · S3 counting
Frames → detector → per-lane counts by centroid-in-polygon (Shapely). Long-format Parquet.
Provenance columns mandatory: `detector_weights`, `git_commit`, `config_hash`.
**Done when:** counts written; **unassigned-detection rate reported per clip** — a high rate means
the polygons are wrong, and it is the only early signal you get.

### WI-12 · S4 labels + density — ✅ **done**
Counts → 3-frame smoothing → §14.1 thresholds → labels; plus `density_band` from mean total count
over the window. **Separate executable from S3** — this is the seam that makes threshold
recalibration a 30-second rebuild instead of a re-run of detection.
**Done when:** labels regenerate from committed counts without touching the detector.

### WI-13 · S5 sequence assembly — ✅ **done**
Windowing at 30 s stride → manifest with `frame_indices[60]`, four labels, `density_band`, `split`,
`label_origin`. **Split assigned at clip level.**
**Done when:** manifest written; no sequence spans two clips.

### WI-14 · S6 validation gates
Distribution gate (any class <5% → **fail**, print histogram). Leakage assert (train/val/test clip
sets disjoint → **raise at load**). Unassigned-rate report.
**Done when:** a deliberately-leaked fixture raises; a degenerate-class fixture fails.

### WI-15 · Tests — 🟡 **partly done** (labels, windows, splits covered; ROI and golden clip pending)
Unit: `label_from_count` at **4/5/15/16** (off-by-one there mislabels a whole class);
centroid-in-polygon including on-edge; 3-frame smoothing. Golden: synthetic 6-frame clip with
hand-written counts → known labels. Property: 60 indices per sequence, no index out of range, splits
disjoint. Integration: one short clip end to end.
**Done when:** `pytest` green; golden test catches a deliberately introduced horizon off-by-one.

---

## Phase 3 — Production corpus (Weeks 8–10)

### WI-16 · Re-run with IndiaTrafficNet weights
Swap detector, re-run S3–S5. S2 is untouched — that separation is why this is cheap.
**Done when:** corpus carries `detector_weights: indiatrafficnet_v1`; the dev corpus remains flagged
`kind: dev`.

### WI-17 · Dev-corpus guard
Training entry point **refuses** a reported run on a `dev`-flagged corpus. Override flag exists for
smoke tests and is recorded in the experiment record.
**Done when:** attempting a reported run on dev data exits non-zero. Convention would not survive
Week 13.

### WI-18 · Human-verify the test split
~150 test sequences verified against human counts; 25 double-counted by two people.
**Done when:** `label_origin: verified` on the test split; auto-vs-verified agreement and inter-rater
agreement both reported. **This is what makes the §14.3 baseline comparison valid** — without it the
count baselines are scored on labels derived from their own inputs.

### WI-19 · Feature cache handoff to R2
Freeze the key contract: `(source_id, clip_id, frame_idx, preprocessing_hash)` → `cnn_feat [2048,7,7]`,
`vit_feat [257,384]` fp16. **Spatial structure preserved** — per-lane ROI pooling depends on it.
`preprocessing_hash` mismatch at load **raises, never warns**.
**Done when:** R2 has the contract in writing and a 100-frame sample cache to build against.

---

## Sequencing

```
W2   WI-01 WI-02 WI-03        (pilots — do these first)
     WI-04 WI-05 WI-06 WI-07
W3   WI-08 | WI-09 WI-10 WI-11 WI-12 WI-13 WI-14 WI-15
W8   WI-16 WI-17
W9   WI-18 WI-19
```

WI-08 and WI-09..15 are independent and can run in parallel if two people are available.

## Definition of done for the whole plan

- [ ] `detection_map.csv` committed; FR-D09 criterion evaluated and reported either way
- [ ] Production corpus built, split by clip, distribution gate passed
- [ ] Test split human-verified; both agreement figures reported
- [ ] `pytest` green including the golden test
- [ ] Every artifact carries `detector_weights`, `git_commit`, `config_hash`
- [ ] Feature cache contract handed to R2 with a sample
- [ ] Experiment records exist for every training run, written at run start

## Risks specific to this plan

| Risk | Signal | Response |
|---|---|---|
| HIGH class degenerate | WI-02 histogram | Recalibrate thresholds now; log against P1. Cheap because of the S3/S4 seam |
| Lane polygons drawn badly | High unassigned rate in WI-11 | Redraw before building any corpus on them |
| IDD lacks a mapped class | WI-04 label inventory | Train as background until Week 8; record in the datasheet |
| Verification slips | WI-18 not started by W9 | It is ~150 sequences, not 500. If it slips, the paper cannot claim a valid baseline comparison — escalate, do not skip |
