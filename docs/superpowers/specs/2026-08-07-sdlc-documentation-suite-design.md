# Design — SDLC Documentation Suite and Execution Manual

**Date:** 2026-08-07
**Project:** MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System
**Status:** Approved

---

## Problem

The project has a complete PRD (1245 lines, v1.0) and no other artifact — no code, no repository, no
requirements baseline, no test strategy, no operational documentation. The team is a 3–4 member
4th-year B.Tech CSE (ML/AI) group working to a 20-week academic deadline under a zero-cash budget,
and is evaluated under a full-SDLC rubric that names its artifacts individually.

Two substantive defects in the PRD block execution:

1. **No defined training corpus for MFSTNet.** The model consumes `[B, T=60, 3, 224, 224]` image
   sequences labeled with per-lane congestion at t+60s. IndiaTrafficNet (§12) produces
   bounding-box-annotated still frames, not labeled sequences. §20 L1 asserts training happens on
   "SUMO sequences," which is not viable: SUMO renders schematic top-down geometry, and
   ImageNet-pretrained ResNet-50 / ViT-Small features on such renders carry little signal — which
   would undermine the multimodal-fusion premise the entire contribution rests on.

2. **Every downstream milestone depends on annotation velocity.** Risk R2 is rated High likelihood,
   and under §12 nothing can train until IndiaTrafficNet is annotated at Week 8. M4 (Week 12),
   M5 (Week 14), and M7 (Week 14) all sit behind a single unbuffered dependency.

A third issue is budgetary rather than technical: the Jetson Nano is the only line item requiring
cash (₹12,000–18,000, constrained supply), and it gates M8.

## Goals

- Produce the named SDLC artifacts as individually reviewable documents, traceable end to end.
- Resolve the two PRD defects and the budget dependency, recording each as a versioned amendment.
- Give the team a start-to-finish execution manual answering *where to begin, what to do, how to do
  it*, with concrete commands and worked examples.
- Hold total project cash cost at ₹0 as the baseline.

## Non-goals

- Implementing MFSTNet, the PPO agent, the dashboard, or any other code. This design covers
  documentation and project scaffolding only.
- Rewriting the PRD. It remains the source of truth for architecture and numbers; amendments are
  additive and logged.
- Changing the approved architecture, hyperparameters, or the §2.4 build order.

---

## Decisions

Four decisions were taken with the team and are recorded as ADRs in `docs/00-planning/decisions/`.

### D1 — Two-track dataset strategy (ADR-001)

YOLOv8 fine-tuning begins in Week 2 against a public Indian traffic dataset (IDD, Roboflow Universe)
so that detection, SUMO calibration, and MFSTNet corpus generation are unblocked immediately.
IndiaTrafficNet collection and annotation run in parallel and are swapped in at Week 8 as the
publication-grade dataset.

**Why:** preserves Novel Contribution 1 in full while removing annotation velocity from the critical
path. Directly mitigates R2. Also yields a free extra experiment — public-pretrained vs.
IndiaTrafficNet-fine-tuned mAP — which strengthens the M2 claim rather than merely satisfying it.

### D2 — MFSTNet corpus by YOLO-derived auto-labeling (ADR-002)

Training sequences are built from continuous 5-minute real video clips. The fine-tuned YOLOv8 model
counts vehicles per lane per frame; the congestion label at t+60s is derived from the count
thresholds already defined in PRD §14.1 (LOW <5, MED 5–15, HIGH >15).

**Why:** real imagery matched to ImageNet-pretrained backbones, zero manual sequence labeling, and a
coherent pipeline — IndiaTrafficNet → YOLOv8 → auto-labeled sequences → MFSTNet. The label rule is
the PRD's own, so no new thresholds are invented.

**Consequence:** raw video must be retained offline for training. This does not violate NFR-13, which
governs the deployed runtime (no frames leave the edge device over the network or to disk in
production), not the offline training corpus. NFR-13's wording is amended to state this boundary
explicitly.

**Known weakness, to be stated in the paper:** labels are model-derived, so YOLOv8 detection error
propagates into MFSTNet's ground truth. Mitigation is a manually-verified subset — 500 sequences
spot-checked against human counts — reported as a label-noise estimate.

### D3 — Laptop-as-edge, Jetson optional (ADR-003)

The edge node runs on a team laptop with a webcam; GPIO LEDs are replaced by an on-screen signal
panel. Department lab inventory is checked for an existing Jetson or Pi first; if one is available it
is used and real on-device latency is reported.

**Why:** satisfies M8 (≥10 fps, 10/10 emergency preemption ≤3s) at zero cost. Jetson remains the
documented deployment target, with laptop measurements reported as proxy and clearly labeled as such.

### D4 — Full separate documents, phased delivery (ADR-004)

All sixteen named artifacts exist as individual files, written in four waves aligned to the §18 phase
gates rather than all upfront.

**Why:** academic rubrics name artifacts individually. But STR is a *results* document — writing it
before experiments exist produces fiction requiring wholesale rewrite. Phasing keeps every document
truthful at the moment it is reviewed.

---

## Structure

```
docs/
  README.md              Front door — what each document is, and reading order
  00-planning/           SOW · BRD · PRD (relocated) · PRD-CHANGELOG · decisions/ADR-*
  01-requirements/       SRS · FRD · NFR · RTM
  02-design/             SAD · HLD · LLD
  03-testing/            STP · STD · STR · UAT
  04-deployment/         TIM · SOP
  90-manual/             EXECUTION_MANUAL.md · weekly/W01..W20.md
  templates/             Weekly status report · risk entry · experiment record
```

### The traceability spine

One ID scheme runs through every document. Each document cites IDs; none restates a requirement in
prose.

```
BR-xx   Business need                    BRD
  ↓
FR-xx / NFR-xx   Requirement             PRD §9/§10 (reused verbatim), SRS, FRD, NFR
  ↓
DES-xx  Design element                   SAD, HLD, LLD
  ↓
TC-xx   Test case                        STD
  ↓
M-xx    Milestone acceptance             PRD §18.2, UAT
```

The RTM is the join table across all five levels. This is what makes the suite an engineering
instrument rather than a binder: a requirement change touches exactly one document, and the RTM shows
the blast radius. It is also the artifact examiners probe hardest, because it cannot convincingly be
reconstructed after the fact.

**Rule:** requirement IDs already defined in PRD §9/§10 are reused unchanged. New IDs are only minted
for requirements the PRD does not cover, and each new ID is logged in PRD-CHANGELOG.

### Delivery waves

| Wave | When | Documents |
|---|---|---|
| 1 | Now (Week 0–1) | SOW, BRD, SRS, FRD, NFR, RTM, PRD-CHANGELOG, ADR-001..004, EXECUTION_MANUAL |
| 2 | ~Week 5 | SAD, HLD, LLD |
| 3 | ~Week 11 | STP, STD, UAT |
| 4 | ~Week 16 | STR (measured results), TIM, SOP |

---

## PRD amendments (logged as v1.1)

| # | Section | Change |
|---|---|---|
| A1 | New §8.6 | MFSTNet training-corpus construction via YOLO auto-labeling (D2) |
| A2 | §12 | Two-track dataset plan; public bootstrap added (D1) |
| A3 | §15 | Laptop-as-edge primary; Jetson optional (D3) |
| A4 | §20 L1 | Rewritten — no longer claims SUMO-trained; states model-derived-label noise instead |
| A5 | New §24.4 | Cost / BOM appendix establishing the ₹0 baseline |
| A6 | NFR-13 | Clarified to govern deployed runtime, not the offline training corpus |

---

## Execution Manual

Eight parts, in `docs/90-manual/EXECUTION_MANUAL.md`.

| Part | Covers |
|---|---|
| 0 | Free tooling setup, repository bootstrap, Git LFS, team roles |
| 1 | Week-by-week course of action, W1–W20, each with definition-of-done and owner |
| 2 | Dataset guide — public sources, own collection, annotation SOP, auto-labeling pipeline |
| 3 | Training guide — Colab workflow, surviving disconnects, checkpointing, ablation harness |
| 4 | SUMO and PPO guide |
| 5 | Prototype and dashboard |
| 6 | Experiments, statistics, and paper |
| 7 | Troubleshooting — seeded from PRD §2.5.1, extended |

Every part carries runnable commands and worked examples, not description alone.

---

## Scaffolding delivered alongside

- Git repository initialized; `.gitignore` excluding raw video and regenerable artifacts while
  explicitly *including* result CSVs (NFR-09); `.gitattributes` routing weights to LFS.
- `docs/README.md` as the front door.
- CLAUDE.md updated to point future sessions at the suite and the amended decisions.

## Risks to this plan

| Risk | Mitigation |
|---|---|
| Documents drift from code as implementation proceeds | RTM review is a standing item in the weekly status template; each wave gate re-checks the prior wave |
| Auto-labeling produces noisy ground truth (D2) | 500-sequence manually-verified subset; label-noise estimate reported in the paper |
| Public-dataset class taxonomy does not match the 8 IndiaTrafficNet classes | Mapping table defined in Manual Part 2; unmapped classes trained as background until Week 8 swap |
| Waves 2–4 never get written under deadline pressure | Wave gates are tied to §18 milestones, not to spare time; W05, W11, W16 entries in the weekly plan name them explicitly |
