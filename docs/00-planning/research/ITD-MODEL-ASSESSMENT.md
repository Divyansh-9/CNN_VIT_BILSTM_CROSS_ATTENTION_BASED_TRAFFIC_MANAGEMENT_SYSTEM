# ITD v1.2 pretrained model — measured assessment

**Date:** 2026-08-19 · **Verdict: keep it, use it offline, do not deploy it.**

Obtained 2026-08-19 by request form (IIT Roorkee). Related:
[DATASETS.md](../DATASETS.md) · [ADR-017](../decisions/ADR-017-pcu-thresholds.md)

## Provenance

| | |
|---|---|
| File | `best_xl_ITD_v1.2.pt` |
| Size | 114,434,706 bytes |
| SHA-256 | `06006ecb5fe52a348ceed805bf0aa6b32af7e24e689d09a6582f6d53159d6b00` |
| Parameters | 56.8 M |
| Trained at | `imgsz 992` |
| Licence | CC BY-NC 4.0 — non-commercial, attribution required |
| Cite | Agarwal, Thombre, Kedia & Ghosh (2024) |
| Local path | `models/external/` — **gitignored** |

**Not committed, deliberately.** BY-NC permits redistribution, but the authors
put these behind a request form with a download counter. Re-hosting them in a
public repository defeats an access control they chose to build. Request a copy
through the form linked from their repository.

## Classes — and what is missing

    two wheeler · autorickshaw · car · bus · LCV · truck · bicycle · pedestrain

Against ours (`car · motorcycle · auto_rickshaw · e_rickshaw · bus · truck ·
pedestrian · cattle`):

| gain | loss |
|---|---|
| `LCV` — a real Indo-HCM class we fold into `truck` | **`e_rickshaw` absent** |
| `bicycle` | **`cattle` absent** |

`e_rickshaw` and `cattle` are two of the India-specific classes this project
added on purpose (PRD §5). ITD will most likely fold e-rickshaws into
`autorickshaw`, which is defensible, and miss cattle entirely, which is not.
**That alone rules it out as a drop-in replacement.**

## Measured on our own footage

Elevated Dhaka clip, five frames sampled across 20 minutes, each model at its
own trained resolution, bicycle and pedestrian excluded from both sides.

### Sensitivity — ITD wins

| conf | ours (s14 joint) | ITD v1.2 |
|---|---|---|
| 0.25 | 116 | **129** |
| 0.35 | 101 | **121** |
| 0.45 | 89 | **113** |
| 0.55 | 79 | **98** |

ITD finds **11–27% more vehicles at every threshold**, consistently.

> **A correction.** A first look at a single frame showed ITD finding fewer
> vehicles, and that reading was wrong — it was one frame, and 10 of ITD's 30
> detections there were bicycles and pedestrians, which our comparison should
> never have counted. The sweep above is the measurement; the single frame was
> an anecdote.

**No ground truth was available on these frames**, so "more detections" is not
the same as "better". It is consistent with better recall from a 5× larger model
at 2.4× the input pixels, but it could also be over-detection. Settling it needs
labelled frames — which is what the human-verified split (A32) will produce.

### Latency — ITD is disqualified

Same machine, CPU, batch 1, mean of 8 runs:

| | params | imgsz | ms/frame | fps |
|---|---|---|---|---|
| ours `s14_joint` | 11.1 M | 640 | **80.0** | **12.5** |
| ITD v1.2 | 56.8 M | 992 | **1194.7** | **0.8** |

**15× slower.** PRD requires YOLOv8 at ≥10 fps on a Jetson Nano; ADR-003 already
downgraded the edge node to a laptop and labels every figure a proxy
measurement. Our detector clears the bar on a laptop CPU with no margin to
spare. ITD misses it by more than an order of magnitude on hardware far stronger
than the target.

This is not a tuning problem. It is a 5× parameter count at 2.4× the pixels.

## How to use it

**Not as the deployed detector.** The latency result is categorical.

**1. Improve the corpus labels — the highest-leverage use.**
ADR-002 derives every MFSTNet training label from detector counts through
§14.1's thresholds. The corpus is only as good as the counting, and corpus
building is **offline**, where 1.2 s/frame is irrelevant. A detector finding
11–27% more vehicles changes the count distribution materially — and
[ADR-017](../decisions/ADR-017-pcu-thresholds.md) calibrates thresholds against
exactly that distribution.

**2. Direct human verification effort (A32).**
The test split must be human-verified to break the circularity between
detector-derived labels and detector-consuming baselines. Two independently
trained detectors let frames be ranked by disagreement, so scarce human
attention goes where the models conflict rather than being spread evenly.
ITD was trained by another group on other data — genuinely independent.

**3. A row in the detector-arms table.**
Evaluated on **our** test split, hyperparameters held fixed, one variable per
row — the S14 discipline. Their reported 0.91 mAP50 is on ITD's own split
against ours at 0.8915, and those two numbers are not comparable in either
direction. Note the arm is not like-for-like on capacity either: `x` at 992
against `s` at 640.

## Open

- ITD's advantage is unquantified without ground truth. Use 1 and 2 above are
  robust to that; use 3 is not, and should wait for the verified split.
- Whether `e_rickshaw` is silently absorbed into `autorickshaw` or dropped. A
  hundred verified frames containing e-rickshaws would settle it.
- Whether a distilled or smaller ITD-trained model exists. Only `xl` was offered.
