# ADR-018 — Distil ITD-x into our YOLOv8s by pseudo-labelling deployment footage

**Status:** PROPOSED — criteria pre-registered, experiment not yet run
**Date:** 2026-08-19 · **Affects:** detector arms (S14/S15), ADR-002 corpus labels
**Reading:** [ITD-MODEL-ASSESSMENT](../research/ITD-MODEL-ASSESSMENT.md)

## The proposal this replaces

*"Use ITD as a pretrained model and fine-tune ours from it — then it will be
fast."*

The goal is right; the mechanism does not exist. ITD is a YOLOv8x-class model
(56.8 M parameters, `imgsz 992`); ours is a YOLOv8s (11.1 M, 640). Measured:

| | |
|---|---|
| tensors | ours 355 · ITD 1015 |
| same name | 162 |
| same name **and** shape | 27 |
| **our parameters initialisable from ITD** | **0.0%** |

Channel widths differ throughout — 256 where theirs are 768. A checkpoint cannot
be loaded into a different architecture. Fine-tuning *ITD itself* would leave it
at 56.8 M parameters and 0.8 fps, which is the problem, not the fix.

## What the idea was actually reaching for

**Knowledge distillation**: a large accurate teacher trains a small fast
student. The student keeps its own architecture, so it keeps its own latency.
The practical form here is **hard-label distillation** — run the teacher offline
where its 1.2 s/frame costs nothing, keep its detections as labels, train the
student on them.

**And it buys something the accuracy numbers do not show.** The frames we label
are our *actual deployment footage* — fixed elevated cameras. Our detector was
trained on IDD (largely dashcam) and BMD-45 (elevated stills). This is
self-training on the target domain at zero annotation cost, which is the A31
viewpoint gap addressed from a direction that costs nothing.

## Two failure modes found by piloting it, not by reasoning about it

### The class trap

ITD has no `e_rickshaw` and no `cattle` — two India-specific classes this
project added deliberately (PRD §5). Copying its labels would teach the student
that e-rickshaws are auto-rickshaws and cattle are background.

**Labels are merged, not copied.** ITD supplies its six shared classes; our
detector supplies `e_rickshaw` and `cattle` only, at a higher confidence, and
its boxes are dropped where they overlap an ITD box by IoU > 0.5.

### The teacher hallucinates large vehicles on this view

Box areas over 12 sampled frames, as a fraction of the frame:

| class | median | p95 | max |
|---|---|---|---|
| car | 0.0074 | 0.0250 | 0.0326 |
| auto_rickshaw | 0.0059 | 0.0236 | 0.0276 |
| **truck** | **0.1304** | **0.2273** | 0.2273 |
| **bus** | **0.1174** | **0.1806** | 0.1806 |

A truck is two to three times a car's footprint, not **eighteen**. Every truck
and bus box was oversized, and one rendered as a rectangle over a quarter of the
frame covering a tree and empty road.

This was found by **looking at a labelled frame**, which the box-area table then
confirmed. It is the same discipline that caught the Bellevue rejection.

A giant false box is worse in training than a missed one — it dominates the
regression loss and teaches the student that vehicles can be enormous.
`--max-box-area 0.05` rejects them; on the pilot it removed 11 of 360 boxes
(7 truck, 4 bus), and the count is always printed so the filter cannot quietly
do too much.

**This qualifies the assessment's headline.** ITD finds 11–27% more vehicles
than we do, but a meaningful share of its large-vehicle detections on elevated
South Asian footage are spurious. Its advantage is concentrated in the small
classes — pedestrians, two-wheelers, auto-rickshaws — which is where an
`x`-scale model at 992 px would be expected to win.

## Decision

Build the pseudo-labelled set and train a student arm. **Adopt only if the
pre-registered criteria below are met on real labelled test data.**

## Pre-registered acceptance criteria

Fixed before the run. Evaluated on the **real labelled** IDD test split (1,170
images) and the BMD-45 elevated eval set — **never on pseudo-labels**, which
would only measure agreement with the teacher.

| # | Criterion | Rationale |
|---|---|---|
| 1 | mAP50 on BMD-45 elevated **≥ 0.8915** (current), and the change is reported either way | The deployment viewpoint. No regression is acceptable |
| 2 | `e_rickshaw` and `cattle` AP50 drop by **≤ 0.02** absolute | The classes the teacher cannot see. This is what the merge exists to protect |
| 3 | **≥ 10 fps** on the measurement host, stated per ADR-003 | The entire reason not to deploy ITD directly |
| 4 | mAP50 on IDD test **does not fall by > 0.02** | Guards against overfitting to one camera's domain |

**If 1 is met and 2 is not, the merge failed and the result is not adopted.**
Trading away India-specific classes for general accuracy inverts the project's
stated contribution.

**Held fixed across arms:** architecture, `imgsz`, epochs, optimiser, seed 42,
and the evaluation split. One variable per row — the S14 discipline.

## Consequences

- **A second, larger use follows if this succeeds.** ADR-002 derives every
  MFSTNet training label from detector counts. A better detector improves every
  congestion label, and [ADR-017](ADR-017-pcu-thresholds.md) calibrates
  thresholds against exactly that count distribution.
- **Attribution.** A model distilled from ITD is a derivative work under
  CC BY-NC 4.0. It must be attributed and stays non-commercial. This propagates
  to any weights we publish, and must appear in the paper.
- **Pseudo-labels are not ground truth** and are never used for evaluation.

## Rejected

**Fine-tune ITD-x itself.** Leaves 56.8 M parameters at 0.8 fps.

**Deploy ITD and drop the latency requirement.** The requirement is a graded
NFR and the edge story is the project's applied contribution.

**Copy ITD's labels unfiltered.** Measured above: bakes in oversized boxes and
destroys two classes.

## Open

- Whether ITD's extra detections are recall or false positives is still
  unquantified on the shared classes. Criterion 1 settles it operationally —
  if they are noise, the student gets worse and the arm is rejected.
- Soft-label distillation (matching teacher logits) may beat hard labels, at the
  cost of a custom training loop. Not attempted; hard labels first, because they
  need no new machinery and the harness already exists.
