# Design — Detection and Corpus Pipeline

**Date:** 2026-08-08
**Project:** MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System
**Status:** Approved
**Owner:** R1 (Data & Detection Lead)
**Delivers:** FR-D08, FR-D09, PRD §8.6; unblocks M2, M4, M5

---

## Problem

Nothing downstream of data can start. The detector does not exist, and the MFSTNet training corpus
specified in PRD §8.6 has no implementation. M4 (Week 12) and M5 (Week 14) both sit behind this.

Four constraints shape the solution:

- No intersection footage exists yet; collection starts Week 3 (ADR-001 Track B).
- Two detector weight sets exist between Weeks 2 and 8 (ADR-001), so every artifact must record which
  produced it.
- Backbones are frozen and features are cached (ADR-005), so the corpus must key on unique frames.
- Congestion thresholds may need recalibration once real counts exist (PRD pending item P1).

## Goals

- A fine-tuned YOLOv8 detector with the FR-D09 comparison reported.
- A reproducible corpus builder turning fixed-camera video into MFSTNet training sequences.
- Development unblocked immediately, on public video, without waiting for Week 3.
- An evaluation set whose labels are not circular with the baselines being compared against.

## Non-goals

- Vehicle tracking, re-identification, or trajectory estimation. Counting is instantaneous occupancy;
  nothing here needs identity across frames.
- The MFSTNet model itself, the feature cache implementation, or training. Only the cache **key
  contract** is fixed here (§7).
- IndiaTrafficNet annotation workflow — that is Roboflow-side, covered in Execution Manual Part 2.
- Emergency vehicle detection (FR-P03/P04). Edge-runtime concern, not corpus.

---

## Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D1 | Public fixed-camera surveillance video for development; own footage for all reported results | Removes the Week 3 dependency. IndiaTrafficNet remains Novel Contribution 1 |
| D2 | Count = all detections whose box centroid falls inside the approach ROI, at that instant | No tracking needed; matches PRD §14.1's plain wording. The polygon becomes part of the label definition and is versioned with the corpus |
| D3 | Per-lane ROI pooling replaces global average pooling before the congestion head | PRD §8.1 as written cannot produce four different lane predictions (§6) |
| D4 | Counts and labels are separate materialised stages | Threshold recalibration (P1) must not require re-running detection |
| D5 | Test split labels are human-verified; train/val remain auto-labelled | Breaks circular evaluation (§5) |

---

## Architecture

Staged pipeline. Each stage reads the previous stage's materialised artifact, is independently
runnable, and is idempotent.

```
S0  source registry    sources/<id>.yaml — video paths, fps, lane polygons, licence, flags
S1  detector           IDD → YOLO format → fine-tune → weights + mAP report   [FR-D08, FR-D09]
S2  frame store        video → unique frames @5s, deduplicated
S3  counting           frames → detector → per-lane ROI counts                ← expensive
S4  labels + density   counts → smooth → thresholds → labels + density band   ← cheap, re-runnable
S5  sequences          windowing @30s stride → manifest with clip-level split
S6  validation         distribution gate · leakage assert · human verification of test split
```

### Why the stages are separated where they are

**S3/S4 is the important seam.** Counting is hours of GPU work over every frame; label derivation is
seconds of arithmetic. PRD pending item P1 records that the thresholds (LOW <5, MED 5–15, HIGH >15)
were fixed before anyone had real count data. If P1 fires — and the distribution gate in S6 exists
precisely because it might — a recalibration must be a thirty-second rebuild, not a re-run of
detection. Fusing these stages would make the team reluctant to recalibrate, which is the wrong
incentive to build into a pipeline.

**S2 is separate from S3** so that a detector upgrade (bootstrap → IndiaTrafficNet at Week 8, ADR-001)
re-runs counting without re-extracting frames.

**S5 is separate from S4** so that stride, sequence length, and horizon can be varied without
recomputing labels.

---

## Data contracts

### Source config — `sources/<source_id>.yaml`

```yaml
source_id: uadetrac_mvi_40701
kind: dev                      # dev | production — see §5.3
licence: "UA-DETRAC research licence, accessed 2026-08-08"
clips:
  - clip_id: mvi_40701
    path: data/raw/uadetrac/MVI_40701.mp4
    fps_native: 25
    duration_s: 1500
lanes:                          # normalised coords — survive resolution changes
  N: [[0.10,0.05],[0.45,0.05],[0.48,0.40],[0.12,0.40]]
  S: [[0.55,0.60],[0.90,0.60],[0.88,0.95],[0.52,0.95]]
  E: [[0.60,0.10],[0.95,0.12],[0.95,0.45],[0.62,0.42]]
  W: [[0.05,0.55],[0.40,0.58],[0.38,0.92],[0.03,0.90]]
```

Lane polygons cover the **approach** side only — congestion is a property of the queue forming on the
inbound arm, not of vehicles departing. Sources may define fewer than four lanes; D3's ROI pooling
handles that without padding.

### `counts` — one row per lane per frame

```
source_id, clip_id, frame_idx, ts_s, lane, cls, n
```

Per-class breakdown is retained because it costs one column and FR-P02 / the MQTT payload
(PRD §17.1) will want it. Nothing in this spec consumes it — do not build on it yet.

### `sequences` — the manifest

```
seq_id, source_id, clip_id, start_frame, frame_indices[60],
label_N, label_S, label_E, label_W, density_band, split, label_origin
```

`label_origin` ∈ {`auto`, `verified`} — see §5.

### Frame store

```
data/frames/<source_id>/<clip_id>/<frame_idx>.jpg
```

**Sequences reference frames; they never copy them.** At a 30 s stride with 5 s sampling, consecutive
sequences share 54 of their 60 frames — materialising images per sequence would store each frame
about ten times over. It also keeps the ADR-005 feature cache coherent: one cache entry per unique
frame serves every sequence containing it.

### Provenance — on every artifact

`detector_weights`, `git_commit`, `source_id`, `config_hash`, `created_at`. Not optional: ADR-001
means two weight sets coexist for six weeks, and an experiment that cannot name its detector cannot
be interpreted.

---

## 5. Evaluation integrity

This section exists because the obvious design produces a rigged comparison.

### 5.1 The circularity problem

Labels are derived from detector counts. PRD §14.3 lists three baselines that **also consume detector
counts**: LSTM on count sequences, CongestFormer, and Naive last-value.

Those baselines' input errors are correlated with the label errors — when the detector miscounts, the
count baseline miscounts in the same direction and is scored correct. MFSTNet reads pixels, so its
errors are independent of the label noise, and detector error scores against it.

The comparison is therefore biased **against** MFSTNet by an amount that has nothing to do with
modelling quality. If MFSTNet ties or loses, the result is uninterpretable.

> To be clear about what is *not* wrong: both MFSTNet and the count baselines must extrapolate 60 s
> forward, so neither has access to the label. Pixels plausibly carry information counts lose —
> velocity, queue spatial extent, upstream arrivals, signal state. The contribution is sound. Only
> the evaluation was compromised.

### 5.2 Fix — human-verified test split

| Split | Labels | Rationale |
|---|---|---|
| train | `auto` | Volume matters more than precision; label noise is a regulariser |
| val | `auto` | Used for early stopping only |
| **test** | **`verified`** | Every reported number comes from here |

Target ~150 test sequences human-verified, with a 25-sequence subset double-counted by two people to
yield an inter-rater agreement figure.

This replaces PRD §8.6's "500 sequences spot-checked" — which is 2,000 manual lane counts, roughly 17
hours, spread thinly across a corpus, producing a number that changes no decision. Concentrating a
smaller budget on the test split costs less and buys a clean evaluation instead of a footnote.
Recorded as a PRD amendment.

Report both figures: auto-vs-verified agreement on the test split (the label-noise estimate PRD §20
L1 promises) and inter-rater agreement (the ceiling on how good any label can be).

### 5.3 Density stratification

PRD §14.2's claim is that CNN and ViT complement each other **in dense chaotic traffic**. In sparse
traffic, counts are easy and every method should tie. A single aggregate macro F1 averages a real
density-concentrated effect into invisibility against a strong count baseline.

S4 therefore records a `density_band` per sequence, derived from the mean total count across the
input window. It costs nothing — the counts are already computed — and it makes stratified reporting
possible later without rebuilding anything.

### 5.4 Dev corpora are not trainable

Development runs against public non-Indian video with a COCO-pretrained detector. Those labels are
poor, and that is acceptable for exercising plumbing.

`kind: dev` in the source config propagates to the sequence manifest, and the training entry point
**refuses to run a reported experiment on a dev-flagged corpus**. An override flag exists for
deliberate smoke tests and is recorded in the experiment record. Convention would not survive Week 13.

---

## 6. Consequence for the model — per-lane ROI pooling

PRD §8.1 collapses the fused feature map with `Global AvgPool → [B, D]`, carries it to `h [B, 256]`,
then applies the congestion head **"per lane, shared weights… Applied 4x (N, S, E, W)"**.

Same input, same weights, four applications — four identical predictions. Nothing tells the head
which lane it is predicting. This would surface around Week 12 as an apparent training bug, and PRD
§2.5.1 would misdirect the team to class weights or normalisation.

**Resolution (D3):** replace global pooling with per-lane ROI pooling over the fused feature map,
producing four lane-specific features fed to one shared head.

Consequences that land in this spec:

- Lane polygons must reach the model, not stop at the corpus. They are carried in the sequence
  manifest's `source_id` and resolved through the source registry.
- The **feature cache must preserve spatial structure** — the 7×7 CNN grid and 197 ViT tokens — not a
  pooled vector. ADR-005 already specifies caching pre-projection outputs, so this is compatible.
- Sources with fewer than four visible approaches work without padding.

Recorded as a PRD amendment; the model-side implementation belongs to R2.

---

## 7. Interface to the feature cache (ADR-005)

Fixed here because D3 depends on it; implemented by the model track.

```
key:   (source_id, clip_id, frame_idx, preprocessing_hash)
value: cnn_feat [2048, 7, 7] fp16 · vit_feat [197, 384] fp16
```

`preprocessing_hash` covers backbone identity, input resize, and normalisation. A mismatch at load is
an **error, not a warning** — a stale cache produces results that look entirely normal and are wrong.

---

## 8. Error handling

| Condition | Behaviour |
|---|---|
| Corrupt or missing frame | Drop the whole sequence, log `seq_id` and reason. Never pad |
| Clip shorter than **355 s** (295 s window + 60 s horizon) | Skip with reason. Never truncate the window. **Log the count of skipped clips prominently** — if it is 100%, the recording protocol is wrong, not the data (PRD A15) |
| Detection below confidence floor | Excluded. Floor is configurable and recorded in provenance |
| Centroid outside every lane polygon | Counted as unassigned; reported as a per-clip rate. A high rate means the polygons are wrong |
| Centroid inside two polygons | Fail at S0 — polygons are validated non-overlapping at registration |
| Any class < 5% of labels | **S6 fails loudly** with the histogram. A degenerate class makes macro F1 ≥ 0.80 unreachable |
| Train/val/test clip sets intersect | **Assertion failure at load**, not a warning |

The last two are the ones that matter. §2.5.1 predicts leakage at Week 11–12, where it presents as
suspiciously good validation accuracy; an assertion converts a week of confusion into an immediate
stack trace.

---

## 9. Testing

| Level | Cases |
|---|---|
| Unit | `label_from_count` at 4/5/15/16 — off-by-one there mislabels an entire class. Centroid-in-polygon including on-edge. Count smoothing over a 3-frame window |
| Golden | A synthetic 6-frame clip with hand-written counts → known labels. Catches ordering and horizon-offset errors that unit tests miss |
| Property | No sequence spans two clips. No frame index out of range. Splits disjoint at clip level. Every sequence has exactly 60 frame indices |
| Integration | End-to-end on one short public clip: video in, manifest out |

---

## 10. Amendments this design requires to the PRD

| # | Section | Change |
|---|---|---|
| A8 | §8.1, §8.4 | Per-lane ROI pooling replaces global average pooling before the congestion head (D3, §6) |
| A9 | §8.6 | Verification budget concentrated on the test split (~150 sequences + 25 double-counted) rather than 500 spread across the corpus (D5, §5.2) |
| A10 | §14.5 | Add density-stratified reporting alongside aggregate metrics (§5.3) |
| A11 | §14.3 | Note that count-consuming baselines share error structure with auto-derived labels; verified test labels are what make the comparison valid (§5.1) |

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Thresholds produce a degenerate class on real data (P1) | S6 distribution gate fails before any training run. S3/S4 seam makes recalibration cheap |
| Lane polygons drawn inconsistently across sources, making counts incomparable | Polygons versioned with the corpus; unassigned-detection rate reported per clip as a drawing-quality signal |
| Human verification of the test split slips | Smaller than the PRD's original ask and concentrated where it changes results. Scheduled as a W10 deliverable, not spare-time work |
| Dev corpus accidentally used for a reported result | Enforced by the training entry point, not by convention (§5.4) |
| Detector upgrade at Week 8 invalidates the corpus | Expected. S2/S3 separation means re-running counting, not re-extracting frames. Provenance makes stale artifacts identifiable |
