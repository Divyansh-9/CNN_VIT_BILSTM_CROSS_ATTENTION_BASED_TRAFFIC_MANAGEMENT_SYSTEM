# Scope Variation Request

**To:** Faculty Guide · **From:** Project Team · **Date:** ______ · **Decision needed by: Week 2**

**Project:** MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System

> Hand this over as one page. Supporting analysis is in
> [FEASIBILITY-AUDIT.md](FEASIBILITY-AUDIT.md); the two decisions are
> [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) and
> [ADR-008](decisions/ADR-008-prototype-descoping.md). Bring all three, lead with this.

---

## 1. Why we are asking

We estimated the work in the approved PRD and compared it against the effort we actually have.

| | |
|---|---|
| Estimated work as specified | **~1,200 person-hours** |
| Realistic capacity — 3.5 effective students × 12 h/week × 17 productive weeks | **~715 person-hours** |
| **Overcommitment** | **~1.6–1.8×** |

The 17 weeks account for placement season and internal exams. Breakdown per subsystem is in the
feasibility audit §2.

We would rather deliver a rigorous subset than an incomplete whole. PRD §2.5.4 names the failure this
avoids: teams that spend eight weeks on architecture and two on experiments, and submit without an
ablation or statistical tests.

## 2. What we propose to change

### Variation A — redefine Novel Contribution 1 *(recovers ~200 hours)*

**From:** collect and annotate 12,000 frames across 6 public intersections; publish under CC BY 4.0.

**To:** a two-part contribution —
- **Part A:** a harmonised 8-class Indian traffic benchmark curated from permissively-licensed public
  sources (IDD, FGVD, UA-DETRAC, licence-verified Roboflow sets), with a unified taxonomy,
  standardised splits, a full datasheet, and evaluation scripts.
- **Part B:** 1,500–3,000 frames collected on **campus** with written institutional permission,
  faces and licence plates automatically blurred before release.

**Two reasons.**

*Effort.* A peak-hour Indian intersection frame carries roughly 20–60 annotatable objects, so 12,000
frames is on the order of **360,000 bounding boxes** — 300 hours drawn from scratch, 120–150 with
model-assisted review. That single deliverable is 20–40% of our total capacity.

*Legal and ethical exposure.* We would be publishing frames of identifiable people under an open
licence. Faces and licence plates are personal data; the DPDP Act 2023 makes the lawful basis for
that publication unclear, and conference venues increasingly require an ethics statement. Seeking
municipal permission is possible but has unbounded lead time.

**Why this is not a weaker contribution.** No harmonised Indian multi-class traffic benchmark
currently exists — every published set uses its own taxonomy, which is itself a documented obstacle
to comparison. Benchmark curation is a recognised, citable contribution. Part B additionally supplies
the **fixed elevated intersection viewpoint** that no public dataset provides, and which our deployed
system actually uses. Smaller, but it is the honest core of the novelty claim and small enough to
annotate well rather than hurriedly.

### Variation B — reduce prototype infrastructure *(recovers ~140 hours)*

| Component | From | To |
|---|---|---|
| Time-series store | PostgreSQL + TimescaleDB | SQLite + Parquet |
| Dashboard auth | JWT, 24 h expiry | Shared password on LAN |
| Dashboard pages | 4 | 2 — Live, and Results |
| Uptime evaluation | 4 hours ≥95% | 1 hour ≥95% |

**Unchanged:** both fallback paths (FR-A06), emergency preemption *behaviour* (FR-A05 — see
Variation C; the 3 s figure is withdrawn as unachievable, the override is not), all safety
invariants (FR-A03/A04), the MQTT contract and its per-topic QoS, and the benchmark and ablation
tables (FR-UI06/UI07) that carry the evidential weight.

This reduces *infrastructure*, not system behaviour. PRD §2.5.3 requires "a working hardware
prototype" for distinction — it does not require a production observability stack.

### Variation C — emergency vehicles: keep the override, drop the visual detector

**This is the one variation we are asking for on evidence rather than on effort.**

FR-P03 requires detecting emergency vehicles from the camera. We do not believe that can be
delivered to a reportable standard, and the reason is measured rather than felt:

- **No dataset carries the class.** Not IDD. Not BMD-45 — 45,986 CCTV images from Bengaluru, 14
  vehicle classes, no ambulance. Not the DataCluster sample. We would be annotating from zero.
- **It would be our thinnest class by far.** `cattle` had 183 boxes in the S11 test split and scored
  **mAP50 0.362** — our worst class by a wide margin. Ambulances are rarer than cattle on an Indian
  junction approach, so the result would sit below the support floor FR-D08 exists to enforce.
- **They frequently do not look distinct.** Many Indian ambulances are ordinary vans carrying a
  sticker and a light. This is a hard visual problem, not a labelling shortfall.

Camera is the wrong sensor for this. Real preemption systems use RF, GPS or siren audio.

| | From | To |
|---|---|---|
| FR-P03 | Detect emergency vehicles from video | **Withdrawn** as a graded deliverable |
| FR-P04 | Confidence ≥0.75 AND ≥2 consecutive detections | **Kept** — it governs the trigger contract, whatever raises it |
| FR-A05 | Preemption overrides the controller | **Kept and already implemented** |

**What we deliver instead, and it is already built and tested:** the preemption *policy*, driven by
an `EmergencyDetect` message on the existing QoS 2 MQTT topic — raised in the demo by an operator
control, and in evaluation by an injected event. Preemption overrides the controller (a controller
that permanently demands the wrong phase still loses), and never shortens clearance.

This separates the half we can evidence from the half we cannot. We would rather demonstrate a
correct override driven by a real trigger than publish an ambulance detector built on fifty boxes.

**A29 is attached to this variation** — FR-A05's "within 3 seconds" contradicts FR-A03 and FR-A04
and is unreachable when the emergency approach is red. Measured worst case **15 s**; floor **6 s**.

## 3. What we are protecting

Everything that is graded and everything that gets published:

- The 7-configuration ablation study, run at full 100 epochs
- The 30-run RL benchmark with paired t-tests, 95% CIs, and Cohen's *d*
- Reproducibility (NFR-07–10): fixed seeds, pinned dependencies, raw result CSVs committed
- The working prototype demo and the emergency preemption override (Variation C)
- The conference paper

## 4. Two improvements we are making regardless

Recorded for your awareness; neither needs approval.

**Evaluation correction.** Our congestion labels derive from detector counts, and three of the PRD
§14.3 baselines also consume detector counts. Their errors therefore correlate with the label errors
and score as correct, while MFSTNet reads pixels and its independent errors score as wrong — biasing
the comparison *against* our own model. We are human-verifying the **test split** so the reported
comparison is valid.

**Architecture correction.** PRD §8.1 applies global average pooling before a shared congestion head
used four times, which yields four *identical* lane predictions. We have replaced it with per-lane
ROI pooling (PRD amendment A8).

## 5. Decision

| | Approve | Decline | Discuss |
|---|---|---|---|
| **Variation A** — dataset redefinition | ☐ | ☐ | ☐ |
| **Variation B** — prototype descoping | ☐ | ☐ | ☐ |

**If declined**, we will proceed against the original PRD and cut the conditional scope in SOW §2.3
(Phase 2 gating, temporal self-attention, Phase 3 live integration) first, reporting them as future
work. We are asking now rather than absorbing the overcommitment silently and discovering it in
Week 18.

Comments: ______________________________________________________________________

Signed: ____________________  Date: __________
