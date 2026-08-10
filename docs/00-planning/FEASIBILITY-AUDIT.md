# Feasibility Audit

| | |
|---|---|
| **Date** | 2026-08-08 |
| **Author** | Independent technical review |
| **Scope** | Everything committed through `edd7cac` |
| **Verdict** | **Achievable — after descoping. Not achievable as currently specified.** |

> This document exists to be disagreed with. Every number is shown so you can check the arithmetic
> rather than trust the conclusion.

---

## 1. Executive verdict

| Question | Answer |
|---|---|
| Is the *architecture* within reach of a 4th-year B.Tech CSE (ML/AI) student? | **Yes.** Comfortably. It is ~4.1M trainable parameters of standard PyTorch modules |
| Is the *research method* sound? | **Yes**, after the fixes in the corpus spec (§5 evaluation integrity) and this document |
| Is the *total scope* deliverable in 20 weeks by 3–4 part-time students? | **No.** Roughly 1.6–2× over capacity |
| Will the project fail if nothing changes? | It will not fail. It will **underdeliver the experiments** — which is the exact failure PRD §2.5.4 warns about |
| Is the current route safe? | The documentation route is strong. The **execution** route has three specific hazards (§4) |

**The honest summary:** you have designed a project that is intellectually appropriate and
logistically overcommitted. The parts that earn marks — ablation, statistics, dataset, paper — are
scheduled behind parts that earn almost none — TimescaleDB, JWT, a four-page React app, a four-hour
uptime test. That ordering is backwards, and §5 proposes reversing it.

---

## 2. Capacity arithmetic

This is the calculation the PRD never does.

**Available effort.** 3–4 students × 20 weeks. Realistic sustained output for a 7th-semester student
carrying coursework, labs, internal exams, and — critically — **placement season** is 12–15 hours per
week on a major project, not 40.

| | Optimistic | Realistic |
|---|---|---|
| Students | 4 | 3.5 effective |
| Hours/week/student | 15 | 12 |
| Weeks | 20 | 17 (placement + exam attrition) |
| **Total person-hours** | **1,200** | **~715** |

Placement season in Indian CSE programmes runs roughly through the first half of the 7th semester.
Budgeting zero attrition for it is the most common planning error in final-year projects.

**Required effort**, estimated by subsystem:

| Subsystem | Person-hours | Basis |
|---|---|---|
| IndiaTrafficNet collection + annotation | **300–400** | §3.1 — the dominant line item |
| Detection: conversion, fine-tune, benchmark | 60 | Mostly waiting on training |
| Corpus pipeline (S0–S6 per spec) | 80 | 6 stages, tests, validation |
| MFSTNet implementation | 100 | Encoders, fusion, temporal, heads, config system |
| MFSTNet experiments + ablation | 60 | Cheap after ADR-005 caching |
| SUMO environment + 3 baseline controllers | 70 | netedit is slow to learn |
| PPO + 30-run benchmark + statistics | 60 | |
| Edge node + MQTT + fallbacks | 70 | |
| FastAPI + TimescaleDB + auth | 60 | |
| React dashboard, 4 pages | **110** | Four pages with live WebSocket, charts, and auth |
| Integration + fault injection + 4h run | 70 | Always underestimated |
| Paper + report + documentation waves | 120 | |
| **Total** | **~1,160–1,260** | |

**~1,200 hours of work against ~715 hours of capacity.** That is a 1.6–1.8× overcommitment, and it
does not include debugging time for the failures PRD §2.5.1 predicts.

---

## 3. Where the estimates hurt most

### 3.1 Annotation is the schedule killer — and the manual understated it

An earlier draft of the Execution Manual targeted **400 frames/day/person**. That figure was wrong
for this domain by roughly 3×; it has been withdrawn and replaced with a measurement instruction
(Manual §1.2). The reasoning is kept here because the arithmetic drives the whole recommendation.

A peak-hour Indian intersection frame contains roughly **20–60 annotatable objects**. FR-D04 asks for
12,000 frames.

```
12,000 frames × ~30 objects       = ~360,000 bounding boxes
at 3 s per box (drawing + class)  = ~300 hours from scratch
with model-assisted review        = ~120-150 hours   (review-and-correct, not draw-from-scratch)
```

Even the assisted figure is 30–40 hours per person on top of everything else. The unassisted figure
exceeds half the team's total capacity for the semester.

> **Do not trust my number either.** In Week 2, annotate a **50-frame pilot** — 25 peak, 25 off-peak
> — and time it. Objects-per-frame and seconds-per-frame from that pilot are the only estimates worth
> planning against. Commit the measurement. This single hour of work de-risks the largest line item
> in the project.

Mitigation is §5.1: change what IndiaTrafficNet *is*.

### 3.2 The dashboard is a second project

Four pages (FR-UI01–UI10) with live WebSocket, historical charts, a gate tracker, two benchmark
tables, an event log, JWT auth, and CSV export. In React, from scratch, by a student who is also
building the edge node and the MQTT layer.

110 hours is not pessimistic. It is roughly what a competent developer needs, and it buys **almost no
marks** — FR-UI06 and FR-UI07 (the benchmark tables) carry evidential weight; the rest is a viewer.

### 3.3 The production stack earns nothing

TimescaleDB, JWT with 24h expiry, MQTT broker authentication, and a 4-hour ≥95% uptime run are
production-operations concerns. They consume roughly 90 hours. No examiner has ever awarded a
distinction for a correctly configured hypertable, and no reviewer at ITSC will read your auth code.

### 3.4 What is *correctly* estimated

To be fair to the PRD: the MFSTNet architecture, the ablation harness, the SUMO/PPO work, and the
statistics are all realistically scoped. After ADR-005's feature caching, the ablation is genuinely
cheap. **The research core is sound and affordable. It is the surrounding system that is not.**

---

## 4. Three specific hazards

### H1 — Legal and ethical exposure on self-collected video *(high likelihood, high impact)*

You raised this, and you are right to. Recording public roads in India is not prohibited, but the
project intends to **publish** the footage-derived frames under CC BY 4.0, and that changes the
analysis:

- Faces and licence plates are personal data. India's **DPDP Act 2023** governs processing of
  personal data of identifiable individuals; publishing a dataset containing them without a clear
  lawful basis is at minimum an unresolved question.
- Publishing venues increasingly require an ethics statement. "We filmed strangers and released it"
  is a weak answer.
- Practically: being questioned by police or a property owner mid-recording costs a session and
  rattles the team. Restricted areas (defence, airports, some government buildings) are a real
  constraint.
- Obtaining institutional or municipal permission is possible but has **unbounded lead time**, which
  is exactly the risk you cannot absorb.

> This is a risk assessment, not legal advice. Route any publication decision through your
> institution's ethics or research committee.

**This alone justifies changing the dataset strategy.** See §5.1 and ADR-006.

### H2 — Novelty is weaker than the PRD assumes *(medium likelihood, high impact)*

"CNN + ViT with cross-attention" is not new. A reviewer will know:

- **Conformer** (Peng et al., ICCV 2021) — parallel CNN and transformer branches with feature
  coupling. Architecturally the nearest neighbour to your Stage 1–2.
- **CrossViT** (Chen et al., ICCV 2021) — dual-branch with cross-attention token fusion.
- **MobileViT**, **CMT**, **CoAtNet** — the broader hybrid family.

If the paper claims dual-path CNN-ViT fusion as the contribution, it will be desk-rejected or
savaged. The defensible claims are narrower and still real: the **learned scene-adaptive gate** as an
interpretable artifact, applied to **spatiotemporal congestion forecasting in unstructured
traffic**, with a **density-stratified** evaluation. Positioning work belongs in
[RELATED-WORK.md](RELATED-WORK.md), and it must be written before the method section, not after.

Same applies to the RL half: single-intersection PPO on SUMO is well-trodden (IntelliLight,
PressLight, MPLight, FRAP, and the RESCO benchmark). Feeding a *learned visual congestion forecast*
into the state is the new part. Say that, and only that.

### H3 — Single machine, single point of failure *(low likelihood, severe impact)*

ADR-003 and ADR-005 both land on the same laptop: edge node, training, PPO, and the demo. If it
fails in Week 15, the project stops.

Mitigations, all cheap: push checkpoints and result CSVs to the repository continuously; keep Colab
accounts warm and configs portable; record the demo video in Week 16 rather than Week 19; make sure a
second team member can run the full stack on their machine before Week 14.

---

## 5. Recommended changes

Ordered by value per hour saved.

### 5.1 Redefine Novel Contribution 1 — curate, then collect *(saves ~200 h, removes H1)*

**Stop planning a 12,000-frame field campaign.** Replace it with a two-part contribution:

**Part A — IndiaTrafficNet-Bench (curated).** A harmonised 8-class benchmark assembled from
permissively-licensed public sources (IDD, FGVD, licence-verified Roboflow Universe sets, UA-DETRAC
for fixed-camera views): one unified taxonomy, de-duplication, standardised splits, a full datasheet,
and evaluation scripts.

This is a **legitimate, citable contribution**. Benchmark-curation papers are a recognised category,
and the field genuinely lacks a harmonised Indian multi-class traffic benchmark — every existing set
uses a different taxonomy. It is also legally clean, since you redistribute only what the source
licences permit, or ship conversion scripts rather than images where they do not.

**Part B — a small self-collected fixed-camera set.** 1,500–3,000 frames from **your own campus**,
with written permission from the administration (one email, days not months), signage where
appropriate, and faces/plates blurred before release. This supplies the deployment viewpoint that no
public dataset provides — which, per [DATASETS.md §2](DATASETS.md), is the real gap.

Part B is small enough to annotate properly and is the honest core of the novelty claim: *fixed
elevated intersection views of heterogeneous Indian traffic*. Part A gives it scale.

**Net effect:** contribution preserved, arguably strengthened, legal exposure largely removed, ~200
hours recovered, and the critical path shortened by weeks.

### 5.2 Descope the prototype *(saves ~140 h)* — **requires faculty guide sign-off**

Detailed in [ADR-008](decisions/ADR-008-prototype-descoping.md). Summary:

| Component | Now | Proposed | Rationale |
|---|---|---|---|
| TimescaleDB | PostgreSQL + TimescaleDB | **SQLite + Parquet** | Same queries, zero ops, one file to back up |
| Auth | JWT, 24h expiry | **Single shared password** | Local demo; NFR-12 satisfied in spirit |
| Dashboard | 4 pages | **2 pages** — Live, and Results | FR-UI06/07 keep their evidential value; Analytics folds into Results |
| Uptime test | 4 hours ≥95% | **1 hour ≥95%** | A 4h run detects nothing a 1h run misses, and costs an afternoon per attempt |
| Edge fallbacks | Unchanged | **Unchanged** | FR-A06 is required behaviour and genuinely interesting |

These are graded requirements. **Do not cut them unilaterally** — take ADR-008 to your guide with the
capacity arithmetic in §2 and ask for a written variation. A guide shown honest arithmetic in Week 2
will nearly always agree; the same guide shown a missing dashboard in Week 18 will not.

### 5.3 Upgrade the backbones — free accuracy *(costs ~4 h, likely gains several F1 points)*

Detailed in [ADR-007](decisions/ADR-007-backbones-and-training-recipe.md).

The backbones are **frozen**, so feature quality is the single largest determinant of final accuracy,
and you are currently choosing ImageNet-supervised features from 2016 and 2021.

**Use DINOv2 ViT-S/14 instead of supervised ViT-S/16.** Self-supervised features from DINOv2 are
substantially stronger than supervised ImageNet features in frozen-backbone settings — which is
precisely your setting. PRD §23 already lists DINOv2 under future scope; promote it to the main
experiment.

Because ADR-005 caches features, **swapping a backbone costs one extra cache pass, not a retraining
run.** That makes a backbone ablation nearly free — and "ResNet-50 vs ConvNeXt-T × ViT-S-supervised
vs DINOv2" is a stronger, more publishable table than most of the seven configs already planned.

### 5.4 Replace unfreezing with LoRA *(costs ~8 h, converts a limitation into a result)*

PRD §8.4 unfreezes backbones at epoch 30; PRD R4 predicts this will overfit. Both cannot be right,
and the PRD currently plans to do something it expects to fail.

**Use LoRA adapters on the ViT instead of full unfreezing.** Low-rank adaptation adds ~0.1–0.5% extra
parameters, adapts the backbone to your domain, and overfits far less than full fine-tuning on a
small dataset. It is standard practice in the LLM world and transfers directly to vision
transformers.

This turns PRD §20 L4's promised frozen-vs-fine-tuned comparison into a three-way result — frozen /
LoRA / full — which is a genuinely interesting row for a small-data paper. Caveat: LoRA invalidates
the feature cache, so schedule it as a late experiment (Week 15), not as a mid-run transition.

### 5.5 Measure before you plan *(costs ~2 h, de-risks the largest estimate)*

Three measurements in Week 2, each under an hour, each replacing a guess with a number:

1. **Annotation pilot** — 50 frames, timed. Gives real objects/frame and seconds/frame (§3.1).
2. **Count distribution** — run COCO YOLO over any fixed-camera intersection video and histogram
   per-lane counts. Tells you immediately whether the LOW/MED/HIGH thresholds are degenerate (PRD
   pending item P1) *before* you build a corpus around them.
3. **Feature cache sizing** — cache 100 frames, measure bytes. Validates ADR-005's ~350 KB/frame.

---

## 6. Revised capacity after changes

| | Hours |
|---|---|
| Original estimate | ~1,200 |
| §5.1 dataset redefinition | −200 |
| §5.2 prototype descoping | −140 |
| §5.3 backbone upgrade | +4 |
| §5.4 LoRA experiment | +8 |
| ADR-009 three-arm PPO benchmark | +15 |
| ADR-010 SUMO heterogeneity (sublane + vTypes + sensitivity check) | +20 |
| **Revised** | **~890** |

Against ~715 realistic hours this is still tight — roughly 1.2× — which is the correct place for a
final-year project to sit. It means the conditional scope in SOW §2.3 (Phase 2 gating, temporal
attention, Phase 3 integration) is genuinely conditional, and that is the intended design.

---

## 7. What is already good — do not change it

Being brutal cuts both ways.

- **The build order** (PRD §2.4) is correct and the reason this project will not collapse.
- **Reproducibility as a first-class requirement** (NFR-07–10) is better than most published work.
- **ADR-002's auto-labelling** turns a fatal gap into a coherent pipeline.
- **ADR-005's feature caching** is the highest-leverage decision in the project. It converts the
  ablation from a 60–90 hour risk into an afternoon, and makes §5.3's backbone ablation possible.
- **The corpus spec's §5** (human-verified test split, density stratification) is what separates a
  credible evaluation from a rigged one.
- **PRD §2.5** is unusually honest for a planning document and should be re-read at Week 12.

---

## 8. Decision required

| # | Change | Owner decision | Needs guide sign-off |
|---|---|---|---|
| 1 | Redefine IndiaTrafficNet as curate-then-collect (§5.1, ADR-006) | Team | **Yes** — changes a graded contribution |
| 2 | Descope prototype (§5.2, ADR-008) | Team | **Yes** — changes graded requirements |
| 3 | DINOv2 + backbone ablation (§5.3, ADR-007) | Team | No |
| 4 | LoRA instead of unfreezing (§5.4, ADR-007) | Team | No |
| 5 | Week 2 measurement pilots (§5.5) | Team | No |

Items 3–5 are engineering decisions and are already recorded as accepted. Items 1–2 change what was
promised and must be taken to the faculty guide **with this document**, in Week 1 or 2 — not later.

The conversation to have is short: *"We did the capacity arithmetic. Here it is. We would rather
deliver a rigorous subset than an incomplete whole. May we vary the scope?"* That is a conversation
that reflects well on a team. The alternative conversation, in Week 18, does not.
