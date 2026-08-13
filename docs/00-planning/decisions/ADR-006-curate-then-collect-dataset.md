# ADR-006 — Curate, Then Collect: Redefining IndiaTrafficNet

| | |
|---|---|
| **Status** | Proposed — **requires faculty guide sign-off** |
| **Date** | 2026-08-08 |
| **Affects** | PRD §12, FR-D01..FR-D07, M1, BR-03, BR-04, R2 |
| **Supersedes** | ADR-001 Track B scope (Track A unchanged) |
| **Evidence** | [FEASIBILITY-AUDIT §3.1, §4-H1, §5.1](../FEASIBILITY-AUDIT.md) |

## Context

PRD §12 commits to collecting 15 hours of video across 6 public intersections and annotating 12,000
frames across 8 classes, published under CC BY 4.0.

Two independent problems make this the wrong plan.

**Effort.** A peak-hour Indian intersection frame carries roughly 20–60 annotatable objects. Twelve
thousand frames is on the order of 360,000 bounding boxes — 300 hours drawn from scratch, perhaps
120–150 with model-assisted review. Against a realistic team capacity of ~715 person-hours for the
whole project, this single deliverable consumes 20–40% of everything available.

**Legal and ethical exposure.** The plan is to *publish* frames of public roads. Faces and licence
plates are personal data; India's DPDP Act 2023 governs their processing, and publishing them under
an open licence without a clear lawful basis is an unresolved question. Conference venues
increasingly require an ethics statement. Obtaining municipal or institutional permission is possible
but has unbounded lead time — the one risk category the schedule cannot absorb.

Neither problem is solved by working harder.

## Decision

Split Novel Contribution 1 into a curated part and a collected part.

### Part A — IndiaTrafficNet-Bench (curated)

A harmonised 8-class benchmark assembled from permissively-licensed public sources: IDD, FGVD,
licence-verified Roboflow Universe sets, and UA-DETRAC or equivalent for fixed-camera views.

Deliverables: one unified taxonomy with a documented mapping from each source; de-duplication;
standardised stratified splits; a full datasheet recording every source, its licence, and its
contribution; and evaluation scripts.

Where a source licence permits redistribution, ship the converted images. Where it does not, **ship
the conversion scripts and a manifest** so a user reproduces the benchmark from their own copies of
the sources. This is standard practice and keeps redistribution lawful without weakening the
contribution.

### Part B — a small self-collected fixed-camera set

1,500–3,000 frames from **your own campus**, recorded from a fixed elevated position.

- Written permission from the institution's administration — one email, days rather than months.
- Signage at the recording location where practical.
- **Faces and licence plates blurred** before any release, automatically, with the blurring script
  committed.
- Datasheet section documenting consent basis, blurring method, and residual risk.

This supplies the deployment viewpoint — fixed, elevated, looking down at an intersection — that no
public dataset provides. Per [DATASETS.md §2](../DATASETS.md), that gap is the real one.

**Amended 2026-08-13 — a clip-count requirement nobody had stated.** Part B was specified in *frames*
(1,500–3,000) and said nothing about how many separate recording sessions those frames come from.
Measured against the actual splitter:

| Source clips | train / val / test | Usable? |
|---|---|---|
| 24 | 11 / 5 / 8 | No — bootstrap has no power |
| 40 | 21 / 8 / 11 | Marginal |
| **60** | **32 / 13 / 15** | **Minimum viable** |
| 120 | 71 / 24 / 25 | Comfortable |

Splits are cut by clip, so **the clip count *is* the statistical sample size** (PRD A19). Below ~60
clips, validation and test each hold fewer than ten, and no confidence interval separates a two-point
F1 difference however many sequences those clips contain.

**Requirement: ≥60 continuous recording sessions of ≥6 minutes.** At 12 minutes each that is ~12
hours of footage — the same order the original plan assumed, but the *unit* is sessions, not hours,
and that distinction was missing.

**Limitation to declare (§20).** Sixty clips from one campus position are not sixty independent
scenes. Clip-level splitting prevents *frame* leakage; it does not prevent overfitting to one
intersection's geometry, lighting and vehicle mix. The test split measures temporal generalisation,
not spatial. Record from at least two distinct positions if the schedule allows, and state the
limitation either way.

## Consequences

**Positive.** The contribution is preserved and arguably strengthened: the field genuinely lacks a
harmonised Indian multi-class traffic benchmark, because every existing set uses its own taxonomy.
Benchmark curation is a recognised, citable category of contribution. Legal exposure drops to
near-zero. Roughly 200 person-hours are recovered. Annotation leaves the critical path entirely, so
R2's High-likelihood rating stops threatening M4, M5, and M7.

Part B is small enough to annotate *well* — consistent conventions, double-checked edge cases —
rather than 12,000 frames annotated hurriedly by four people under deadline. For the fixed-camera
subset that matters most, quality beats quantity.

**Negative.** "We curated existing data" is a less immediately impressive sentence than "we collected
our own." It reads as a smaller claim to an examiner who does not think about it, and it must
therefore be *argued* — the datasheet and the paper must both make the harmonisation case
explicitly, with the taxonomy-mismatch evidence that motivates it.

**Negative.** Part A depends on source licences that must each be verified and recorded. A source
whose licence turns out to prohibit derivative benchmarks must be dropped, and that is discovered
during curation, not before. Budget for one source falling out.

**Negative.** M1's acceptance criterion changes (12,000 frames → Part A published + Part B ≥1,500
frames). This is a graded milestone, which is why this ADR requires sign-off rather than being
adopted unilaterally.

**Neutral.** ADR-001 Track A is unchanged. The detector still bootstraps on IDD from Week 2.

## Alternatives considered

**Proceed as specified in PRD §12.** Strongest-sounding contribution. Rejected on the arithmetic in
FEASIBILITY-AUDIT §3.1 and the exposure in §4-H1. A plan whose largest line item is 1.5× the team's
realistic capacity for that line item is not a plan.

**Reduce to ~4,000 self-collected frames, keep the field campaign.** Halfway house. Rejected because
it addresses effort but not legal exposure — publishing 4,000 frames of strangers raises the same
DPDP question as publishing 12,000.

**Curate only; no collection at all.** Cheapest and fully compliant. Rejected because it abandons the
fixed-camera viewpoint, which is both the genuine gap in the literature and the viewpoint the
deployed system actually uses. Part B is small precisely so that it remains affordable.

**Use public traffic-camera feeds instead of campus recording.** Attractive — right viewpoint, no
recording effort. Rejected for *published* data: terms of service on most feeds prohibit
redistribution, and provenance is hard to document. Retained for the **unpublished** MFSTNet corpus,
where redistribution never occurs (see the corpus spec, D1).
