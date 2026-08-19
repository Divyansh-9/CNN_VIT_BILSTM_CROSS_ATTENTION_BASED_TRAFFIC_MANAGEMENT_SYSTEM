# TrafficCAM — measured assessment

**Date:** 2026-08-19 · **Verdict: adopt as a detector training and test source.
It is the best data this project has.**

[Repository](https://github.com/Math-ML-X/TrafficCAM) · human-annotated instance
segmentation of Indian traffic.

## What it is

| | |
|---|---|
| Format | LabelMe 5.0.1 polygons, 1920×1080, `imageData` embedded |
| Fully annotated | 78 sequences × 30 frames = **2,340 frames** |
| First-frame annotated | 336 sequences × 1 = **336 frames** |
| Density | ~50 polygons per frame |
| Cities | Bengaluru, Delhi, Mumbai, Noida, NITK |
| Viewpoint | **elevated fixed camera** |
| Unlabelled surplus | 9,744 frames from the same cameras |

After conversion: **2,676 frames, ~72,000 boxes**, split 1,884 / 323 / 469 by
**sequence** (seed 42).

## Why it matters more than anything else acquired so far

Every previous source compromised on one of two axes — being Indian, and being
the deployment viewpoint, annotated by people:

| source | Indian | elevated | human-annotated | video |
|---|---|---|---|---|
| IDD | yes | **no** (largely dashcam) | yes | no |
| BMD-45 | yes | yes | yes | **no** (stills) |
| ITD pseudo-labels | yes | yes | **no** (model-generated) | yes |
| **TrafficCAM** | **yes** | **yes** | **yes** | **yes** |

It also cost no annotation budget, against a feasibility audit that put
annotation at roughly three times the original estimate.

## The find that a strict label map produced

The converter refuses to guess at unrecognised labels and prints what it
dropped. On the first run that reported **3,140 dropped annotations**, of which
**1,700 were `e-Rickshaw`**.

`e_rickshaw` is the class this project has **never been able to evaluate** —
zero test boxes in IDD, zero in BMD-45, `evaluated: False` in every metrics CSV
we have produced, and absent from ITD entirely. It was present all along under a
spelling the map did not list.

After normalising the annotator variants (`Bike`, `Motor Bike`, `Moterbike`,
`Pesestrian`, `e-Rickshaw`):

| class | train | val | test |
|---|---|---|---|
| car | 19,144 | 3,070 | 5,275 |
| motorcycle | 18,027 | 1,557 | 6,052 |
| pedestrian | 5,601 | 283 | 1,593 |
| auto_rickshaw | 4,172 | 468 | 1,235 |
| truck | 2,047 | 156 | 617 |
| bus | 1,308 | 161 | 372 |
| **e_rickshaw** | **1,254** | **76** | **370** |

**A permissive default that folded unknown labels into a nearest neighbour would
have silently buried this.** Strict-and-report is why it surfaced on the first
run rather than never.

`cattle` remains absent from every external source and can only come from IDD or
our own annotation.

## What it is not

**Not a forecasting corpus.** A sequence is 30 frames at stride 2 — roughly two
seconds. A15 requires 360 s of continuous fixed-camera video for one prediction
window, so a TrafficCAM sequence is about **180× too short**. It trains the
detector; it cannot build the MFSTNet corpus. The Dhaka Rampura clip remains the
only corpus-capable footage.

**Splits are by sequence, never by frame.** Thirty frames two seconds apart from
one camera are near-duplicates; a frame-level split would put the same vehicles
in train and test. Same rule ADR-002 applies to the corpus.

## Consequences

1. **ADR-018 criterion 2b is upgraded.** It used a prediction-rate proxy because
   `e_rickshaw` had no labelled test data. It now has 370 test boxes, so the
   criterion becomes a real AP50 measurement.
2. **TrafficCAM outranks the ITD pseudo-labels as training data.** Human
   annotation in the target domain beats a teacher whose bus and truck
   predictions were 65% and 43% spurious on comparable footage. The S16
   distillation run still answers its own question and is worth finishing, but
   the next detector arm should be TrafficCAM.
3. **`Tractor` folds into `truck`** — 251 instances. Indo-HCM tabulates it
   separately at PCU 7.0; our label set has no tractor class. Recorded as a
   deliberate loss of granularity.
4. **`LCV` folds into `truck`** — the same trade, and the one place ITD's label
   set was richer than ours.
5. **The 9,744 unlabelled frames are a pseudo-labelling target** with a
   human-annotated test split from the same cameras to verify against — which is
   exactly what the ITD arm lacked.

## Licence

Not yet established. The repository must be checked before any distribution or
publication claim, and before weights trained on it are released.
