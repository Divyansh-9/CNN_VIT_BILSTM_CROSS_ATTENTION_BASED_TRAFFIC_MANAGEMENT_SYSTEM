# ADR-001 — Two-Track Dataset Strategy

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-07 |
| **Deciders** | Project team + faculty guide |
| **Affects** | PRD §12, FR-D01..FR-D08, M1, M2, R2 |
| **Supersedes** | PRD §12.1 sequential collection plan |

## Context

PRD §12 sequences the dataset work strictly: identify intersections (W2–3) → record (W3–5) →
extract and filter (W5–6) → annotate (W6–8) → publish (W8). No model training can begin before
Week 8, because no labeled data exists before Week 8.

Every downstream milestone therefore inherits a single unbuffered dependency. M4 (MFSTNet core
converging, Week 12), M5 (benchmarked, Week 14), and M7 (RL benchmark, Week 14) all sit behind it.
Risk R2 — "12,000-frame annotation bottleneck" — is rated **High likelihood** in PRD §19, and PRD
§2.5.1 independently predicts that both collection and annotation will overrun. The plan's own risk
analysis contradicts the plan's own schedule.

A four-week slip in annotation, which the PRD considers likely, consumes the entire buffer before
the Week 20 submission.

## Decision

Split the dataset work into two tracks that run concurrently.

**Track A — Bootstrap (Week 2 onward).** Fine-tune YOLOv8s against a publicly available Indian
traffic dataset. This unblocks detection, SUMO calibration, and MFSTNet corpus generation
immediately.

**Track B — IndiaTrafficNet (Weeks 2–8, unchanged in substance).** Collection, filtering, Roboflow
annotation, and public release proceed exactly as PRD §12 specifies. At Week 8 the IndiaTrafficNet
weights replace the bootstrap weights everywhere.

Candidate public sources, in preference order:

| Source | Licence | Fit |
|---|---|---|
| IDD — India Driving Dataset (IIIT-H) | Research use, free registration | Best. Indian roads, includes auto-rickshaw and animal classes |
| Roboflow Universe — Indian traffic sets | Mostly CC-BY / MIT, varies per set | Good. Already in YOLO format. Verify licence per dataset |
| AI City Challenge | Research use | Fallback. Not Indian, but dense multi-class traffic |

Class taxonomies will not match the eight IndiaTrafficNet classes exactly. A mapping table is
maintained in Execution Manual Part 2; source classes with no target equivalent are trained as
background until the Week 8 swap.

## Consequences

**Positive.** Annotation velocity leaves the critical path entirely — R2 degrades from schedule
risk to quality risk. Downstream teams have working detection weights in Week 2 rather than Week 8,
so SUMO calibration and the MFSTNet corpus can start six weeks earlier. The swap itself yields a
free comparative experiment (public-pretrained vs. IndiaTrafficNet-fine-tuned mAP) that
strengthens the M2 claim beyond the ≥10% threshold it merely needs to clear.

**Negative.** Two sets of detection weights exist between Weeks 2 and 8, so every experiment
recorded in that window must state which weights produced it. The experiment record template
carries a mandatory `detector_weights` field for this reason. There is also a real temptation to
never complete Track B once Track A is working — the mitigation is that M1 is a graded milestone
with a Week 8 due date, and IndiaTrafficNet is Novel Contribution 1.

**Neutral.** Total effort is unchanged; only the ordering differs.

## Alternatives considered

**Own dataset only, per PRD §12.** Purest contribution narrative, and no dual-weights bookkeeping.
Rejected because it retains a High-likelihood risk on the critical path with no buffer, and the
PRD's own §2.5.1 predicts the overrun.

**Public datasets only, drop IndiaTrafficNet.** Fastest to a working model. Rejected outright:
PRD §2.5.2 identifies a genuine dataset as the primary differentiator faculty check for, and §2.5.3
lists it first among distinction-level requirements. This would drop the project to the "average
project" tier described in §2.3.
