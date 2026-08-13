<div align="center">

# 🚦 MFSTNet — CNN-ViT-BiLSTM Cross-Attention Traffic Management

**Camera-only congestion forecasting and reinforcement-learning signal control
for unstructured Indian intersections**

[![tests](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/tests.yml/badge.svg)](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/tests.yml)
[![docs](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/docs.yml/badge.svg)](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/docs.yml)
![status](https://img.shields.io/badge/STATUS-PRE--IMPLEMENTATION-orange?style=for-the-badge)
![week](https://img.shields.io/badge/WEEK-2%20of%2020-blue?style=for-the-badge)
![licence](https://img.shields.io/badge/LICENCE-MIT-green?style=for-the-badge)

![python](https://img.shields.io/badge/PYTHON-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pytorch](https://img.shields.io/badge/PYTORCH-2.3.1-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![detector](https://img.shields.io/badge/DETECTOR-YOLOv8s-00FFFF?style=for-the-badge&logoColor=black)
![sim](https://img.shields.io/badge/SIMULATOR-SUMO%201.19-FFB000?style=for-the-badge)

![cnn](https://img.shields.io/badge/CNN-ResNet--50%20(frozen)-6A5ACD?style=for-the-badge)
![vit](https://img.shields.io/badge/ViT-DINOv2%20S%2F14%20(frozen)-8A2BE2?style=for-the-badge)
![fusion](https://img.shields.io/badge/FUSION-Gated%20Cross--Attention-FF1493?style=for-the-badge)
![temporal](https://img.shields.io/badge/TEMPORAL-BiLSTM%202%C3%97128-20B2AA?style=for-the-badge)

![rl](https://img.shields.io/badge/RL-PPO%20%2F%20SB3-success?style=for-the-badge)
![state](https://img.shields.io/badge/STATE-16--dim-informational?style=for-the-badge)
![horizon](https://img.shields.io/badge/HORIZON-60s%20ahead-critical?style=for-the-badge)
![budget](https://img.shields.io/badge/BUDGET-%E2%82%B90-brightgreen?style=for-the-badge)

![docs](https://img.shields.io/badge/DOCS-44%20files%20%C2%B7%2013%20ADRs-lightgrey?style=for-the-badge)
![target](https://img.shields.io/badge/TARGET-IEEE%20ITSC%20%2F%20CVIP-darkred?style=for-the-badge)
![project](https://img.shields.io/badge/PROJECT-B.Tech%20CSE%20(ML%2FAI)-navy?style=for-the-badge)

</div>

> **Badges report what is true, not what is planned.** Status reads
> **PRE-IMPLEMENTATION** because no model has trained and no frame has been detected. The two CI
> badges are live workflow results, not pictures of them. When the system runs, the status badge
> changes — and not before.

---

B.Tech CSE (ML/AI) major project · 20 weeks · 3–4 members · ₹0 cash budget

| | |
|---|---|
| **Week** | 2 of 20 |
| **Specified** | 43 documents · 12 architecture decisions · 35 catalogued references |
| **Built** | 1,339 lines of Python · 44 tests passing |
| **Blocked on you** | Python 3.11 install · faculty scope sign-off · first video |

> **New to the project, or the documents feel heavy?** Start with **[EXPLAIN.md](EXPLAIN.md)** —
> everything below in plain English with worked examples, no prior knowledge assumed.
>
> **Want to know what to do right now?** **[BUILD-LOG.md](BUILD-LOG.md)** — every step S01–S48 with
> its status, plus a running record of what broke and how it was fixed.

> **Read the status column in every table below.** This project is mostly specification so far. A
> README that reads as though the system exists would mislead the team and an examiner alike, so
> everything here is marked **Specified**, **Built**, or **Blocked**.

---

## Contents

| Section | Read it if you want |
|---|---|
| **[EXPLAIN.md](EXPLAIN.md)** | **Everything, in simple English with examples** |
| **[BUILD-LOG.md](BUILD-LOG.md)** | **What to do next · what is blocked · what went wrong and how we fixed it** |
| [The problem](#the-problem) | Why this project exists |
| [What it does](#what-it-does) | The system in one diagram |
| [Reading paths](#reading-paths) | **Start here** — 5, 30, or 120 minutes by role |
| [Why each component](#why-each-component) | The defence of every technology choice |
| [The four subsystems](#the-four-subsystems) | Structural plan and build order |
| [Where we are](#where-we-are-and-what-happens-next) | Current plan, week by week |
| [Decisions](#decisions) | All twelve ADRs |
| [Defects found and fixed](#defects-found-and-fixed) | What planning has bought so far |
| [Open items](#open-items) | Everything unresolved, with owners and deadlines |
| [Claims](#what-we-claim-and-what-we-do-not) | What survives peer review |
| [Repository](#repository) · [Getting started](#getting-started) · [Rules](#working-rules) | Practicalities |

---

## The problem

Indian urban intersections run mostly on fixed-time signal plans set once and rarely revised. Those
plans assume lane-disciplined, homogeneous traffic. Indian traffic is neither — two- and
three-wheelers filter between lanes, auto-rickshaws and e-rickshaws occupy a size and acceleration
class Western-trained detectors do not model, and cattle on the carriageway is routine.

Three consequences follow. Signal timings do not match demand. Off-the-shelf detectors miscount the
vehicle mix that matters. And control reacts to queues that have already formed rather than
anticipating them.

The mainstream traffic-forecasting literature — STGCN, DCRNN, Graph WaveNet — solves the first
problem using **loop detectors and probe sensors**, infrastructure most Indian intersections do not
have. This project asks whether a single camera can do the job instead.

## What it does

```
camera ──▶ YOLOv8 ──▶ per-lane counts ─────────────┐
                                                    │
       ──▶ MFSTNet ──▶ congestion at t+60s, per lane┤──▶ PPO agent ──▶ signal timing
                       + fusion gate value          │
                                                    │
                                              MQTT ─┴──▶ dashboard
```

Five minutes of video in; per-lane LOW / MEDIUM / HIGH congestion sixty seconds ahead out; that
forecast becomes part of the RL controller's state vector; the whole loop runs on a laptop.

---

## Reading paths

The suite is 8,000 lines. Nobody should read it linearly.

### Five minutes — anyone

**[EXPLAIN.md](EXPLAIN.md)** if you want it in plain language. Otherwise this page, plus the [Feasibility Audit](docs/00-planning/FEASIBILITY-AUDIT.md). The audit is the
single most important document: it contains the capacity arithmetic that governs every scope
decision.

### Thirty minutes — joining the team

1. [Process Review](docs/00-planning/PROCESS-REVIEW.md) — where the project actually stands, bluntly
2. [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup) — get your machine working
3. [Execution Manual Part 1](docs/90-manual/EXECUTION_MANUAL.md#part-1--week-by-week-course-of-action) — find your column, read your week
4. Your own subsystem's section in the [PRD](docs/00-planning/PRD.md)

### Two hours — owning a subsystem

Add the [SRS](docs/01-requirements/SRS.md) for behaviour, the [FRD](docs/01-requirements/FRD.md) for
your acceptance criteria, [PLAN-01](docs/plans/PLAN-01-detection-corpus-pipeline.md) if you own data
or detection, and the [Training Guide](docs/90-manual/TRAINING-GUIDE.md) if you own the model.

### By role

| You are | Read, in order |
|---|---|
| **Faculty guide / examiner** | [Feasibility Audit](docs/00-planning/FEASIBILITY-AUDIT.md) → [Scope Variation Request](docs/00-planning/SCOPE-VARIATION-REQUEST.md) → [SOW](docs/00-planning/SOW.md) → [RTM](docs/01-requirements/RTM.md) |
| **Writing the paper** | [Related Work](docs/00-planning/RELATED-WORK.md) — **before** the method section — then [Bibliography](docs/00-planning/BIBLIOGRAPHY.md) and clear its verification queue |
| **Implementing anything** | [PRD](docs/00-planning/PRD.md) for numbers → [FRD](docs/01-requirements/FRD.md) for acceptance criteria |
| **Checking a document is current** | [Document Register](docs/DOCUMENT-REGISTER.md) |
| **Wondering why something changed** | [decisions/](docs/00-planning/decisions/) and [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) |

---

## Why each component

The section to read before asking "why not just use X?". Where a choice is weak, that is said.

### Perception

| Component | Why this one | What we get |
|---|---|---|
| **YOLOv8s** | Best speed/accuracy trade-off at the edge, mature tooling, trivial fine-tuning. RT-DETR is stronger but heavier and slower to train | Per-lane counts — **and** the labels for MFSTNet's corpus, which is what makes the pipeline self-supervising |
| **8 India-specific classes** | COCO has no auto-rickshaw, no e-rickshaw, no cattle. A detector blind to ~20% of the vehicle mix corrupts every downstream decision | Counts that reflect what is actually on the road |
| **Fixed lane ROI polygons** | Counting by region needs no tracking. Tracking would add a subsystem and another error source feeding the labels | Instantaneous per-lane occupancy from a single frame |

### The model

| Component | Why this one | What we get |
|---|---|---|
| **ResNet-50, frozen** | Local texture and vehicle-shape detail. Frozen because ~4M trainable parameters on a small dataset already risks overfitting | The "what is here" signal |
| **DINOv2 ViT-S/14, frozen** | Global scene layout, which convolution captures poorly. **DINOv2 rather than supervised ViT because the backbone never updates, so representation quality is the entire contribution** ([ADR-007](docs/00-planning/decisions/ADR-007-backbones-and-training-recipe.md)) | The "how is the scene arranged" signal |
| **Bidirectional cross-attention** | Each branch queries the other, so detail and context inform each other rather than being concatenated. Honestly: this is co-attention, published in ViLBERT (2019) — the application is new, the mechanism is not | Fusion that adapts to content |
| **The learned gate** | `g = σ(W[Z_A; Z_B])`, `F = g·Z_A + (1−g)·Z_B`. Hypothesis: dense chaotic scenes need CNN detail, sparse structured scenes need ViT context | **An interpretability result, not an internal detail.** Logged, charted, and tested against scene density. If it collapses, we report that |
| **BiLSTM 2×128** | Queue build-up and arrival bursts over 60 timesteps. Mature, cheap, not the research risk | Temporal modelling that will not surprise us |
| **Per-lane ROI pooling** | PRD §8.1 as written global-average-pooled then applied one shared head four times — producing four *identical* predictions. ROI pooling makes each lane read its own image region | Four genuinely different lane predictions |

### Control

| Component | Why this one | What we get |
|---|---|---|
| **SUMO + TraCI** | The standard open-source microsimulator; comparable papers use it, so results are comparable | An environment where all four methods face identical demand per seed — the precondition for a valid paired t-test |
| **Sublane model + 5 vehicle types** | SUMO's default assumes lane discipline; the paper is about traffic that has none ([ADR-010](docs/00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md)) | The control half and the vision half describe the same traffic |
| **PPO** (Stable-Baselines3) | Stable on discrete actions, sane defaults, reproducible | Learned timing. **Not a contribution on its own** — single-intersection RL control is well-solved |
| **MFSTNet forecast in the state** | *This* is the RL contribution: the policy sees an anticipated future, not only the present | A question the signal-control literature largely does not ask |
| **Hard safety constraints** | Min green 10 s, max 90 s, all-red ≥3 s, no lane starved past 180 s — **enforced by actuation, not learned** | A reward penalty makes starvation expensive; only a constraint makes it impossible |
| **Webster baseline, cycle-clamped** | Clamped into [26, 186] s with every clamp logged and the **clamp rate reported** ([ADR-011](docs/00-planning/decisions/ADR-011-webster-definition.md)) | A baseline pinned to its ceiling is being compared in an oversaturated regime — disclosed, not hidden |
| **Saturation flow swept, not chosen** | Non-lane-disciplined traffic measures saturation flow **per metre of approach width**, not per lane. Published values span 525W–1283W — a 2.4× range ([ADR-012](docs/00-planning/decisions/ADR-012-webster-saturation-flow.md)) | "PPO beat Webster's **best** across the published range" cannot be answered with "you detuned the baseline." A single chosen value can |

### System

| Component | Why this one | What we get |
|---|---|---|
| **MQTT / Mosquitto** | Per-topic QoS is exactly the primitive this system needs | Emergency at QoS 2 (a duplicate fires a spurious preemption; a loss risks a life), counts and commands at QoS 1, predictions at QoS 0 |
| **FastAPI** | Async, typed, self-documenting | A backend four people can integrate against in Week 17 |
| **ONNX Runtime** | Framework-independent CPU inference, and the route to INT8 | The ≤150 ms server-CPU budget |
| **React + Recharts** | The Benchmark page reads committed result CSVs directly | The dashboard becomes **evidence**, not illustration |
| **SQLite + Parquet** *(proposed)* | Replaces PostgreSQL + TimescaleDB. Same queries, one less service, and the notebooks read the same files ([ADR-008](docs/00-planning/decisions/ADR-008-prototype-descoping.md)) | ~40 hours back |
| **Laptop as edge node** | Jetson costs ₹12–18k against a ₹0 budget ([ADR-003](docs/00-planning/decisions/ADR-003-laptop-as-edge.md)) | M8 at zero cost. Every latency figure states its host, and laptop numbers are labelled **optimistic** proxies |

### Method

| Practice | Why | What we get |
|---|---|---|
| **Cached frozen-backbone features** | Frozen backbones emit identical features every epoch, and ablation configs differ only *downstream* of them ([ADR-005](docs/00-planning/decisions/ADR-005-local-first-training.md)) | The 60–90 hour ablation collapses to hours. **The highest-leverage decision in the project** |
| **Human-verified test split** | Labels derive from detector counts, and three baselines also consume detector counts — their errors correlate with the label errors and score as correct | An evaluation not rigged against our own model |
| **Density-stratified reporting** | The hypothesis is that fusion helps *in dense scenes*. One aggregate number averages that away | "9 points better in high density" is a finding; "0.81 vs 0.80" is a shrug |
| **Transition-window recall** | Congestion over 60 s is highly persistent, so a last-value baseline may sit near the ceiling | A metric that can actually rank models |
| **Cluster bootstrap over clips** | Sequences from one clip share 54 of 60 frames; resampling them overstates precision | Confidence intervals that reflect the real sample size |
| **Splits cut by source clip** | Same overlap, other direction | No leakage — asserted at load, not hoped for |

---

## The four subsystems

Developed largely in parallel, integrated in Weeks 17–19.

| # | Subsystem | Delivers | Status |
|---|---|---|---|
| **S1** | **IndiaTrafficNet** — curated benchmark + campus-collected fixed-camera set | The dataset contribution | **Blocked** on ADR-006 sign-off |
| **S2** | **Detection** — YOLOv8 fine-tuned, benchmarked against COCO | Counts, and the corpus labels | Specified · [PLAN-01](docs/plans/PLAN-01-detection-corpus-pipeline.md) |
| **S3** | **MFSTNet** — the model plus a 7-config ablation | The primary research result | Specified · corpus logic **built** |
| **S4** | **PPO controller** — SUMO, three policy arms, 30-seed benchmark | The control result | Specified |
| **S5** | **Prototype** — edge ⇄ MQTT ⇄ server ⇄ dashboard | The demo | Specified · descoping proposed |
| **S6** | **Research output** — paper, SDLC suite, open repository | The deliverable | In progress |

### Build order — non-negotiable

PRD §2.4 exists to prevent a known failure: over-engineering the architecture and under-delivering
the experiments.

```
Phase 1 (MANDATORY)   CNN + ViT + STANDARD cross-attention + BiLSTM → congestion head
Phase 2 (STRETCH)     gating replaces standard cross-attn; temporal self-attention; attention pooling
Phase 3 (OPTIONAL)    full end-to-end PPO live runtime integration
```

**Do not implement Phase 2 before Phase 1 trains cleanly.** If Phase 2 is never reached, it is
reported as future work — that is a professional decision, not a failure.

### The coupling that spans subsystems

MFSTNet's output is not only a prediction — it is part of the PPO state vector. PRD §13.1's
16-dimensional state carries four per-lane predictions at indices 11–14. **Changing MFSTNet's output
shape or normalisation invalidates every trained PPO checkpoint.** During SUMO training those fields
come from a noise-calibrated surrogate, not from MFSTNet itself
([ADR-009](docs/00-planning/decisions/ADR-009-ppo-forecast-surrogate.md)) — SUMO has no camera.

---

## Where we are, and what happens next

### Built and passing

| Artifact | What it does |
|---|---|
| `mfstnet/corpus/labels.py` | §14.1 count rule, median smoothing, density banding |
| `mfstnet/corpus/windows.py` | Window timing — the arithmetic amendment A15 corrected |
| `mfstnet/corpus/splits.py` | Clip-level split assignment, leakage guard |
| `mfstnet/configs/spec.yaml` | Single source of truth for numbers that span documents |
| `tests/` | **44 tests**, including six A15 regressions |
| `scripts/check_env.py` | Pre-flight — caught the Python 3.14 / torch incompatibility |
| `scripts/check_docs.py` | Link check, withdrawn-claim guard, ADR registration. Runs in CI |
| `scripts/seed.py` | NFR-07 seeding, including DataLoader workers |

### This week — in order

| # | Action | Effort | Owner | Why it is in this position |
|---|---|---|---|---|
| 1 | **Submit the [Scope Variation Request](docs/00-planning/SCOPE-VARIATION-REQUEST.md)** | 20 min | Team lead | Unblocks ~340 hours and removes every conditional branch from the plan |
| 2 | **Install Python 3.11**, then `pip install -r requirements.txt` | 30 min | Everyone | Nothing else runs until this does |
| 3 | **Run the three Week-2 pilots** ([Manual §1.2](docs/90-manual/EXECUTION_MANUAL.md)) | 3 h | R1 | First contact with reality. One pilot can invalidate the task design |
| 4 | **Doc walkthrough** — each owner presents their subsystem back to the group | 90 min | All | 8,000 lines in one voice is a liability until it is shared understanding |
| 5 | Continue [PLAN-01](docs/plans/PLAN-01-detection-corpus-pipeline.md) from WI-04 | rest of week | R1 | Ends the documentation-to-code imbalance |

**Stop writing planning documents after item 4.** Wave 2 design documents are scheduled for Week 5;
leave them there.

### The 20 weeks

| Weeks | Focus | Milestones |
|---|---|---|
| 0–2 | Setup, pilots, scope sign-off | — |
| 2–3 | Detector bootstrap on public data; pipeline skeleton | — |
| 3–8 | Dataset curation and campus collection; corpus build | **M1** dataset published (W8) |
| 5 | **Wave 2 gate** — SAD, HLD, LLD | — |
| 9–10 | Detector benchmarked; SUMO calibrated | **M2** (W9) · **M3** (W10) |
| 11 | **Wave 3 gate** — STP, STD, UAT | — |
| 11–14 | MFSTNet trains and ablates; PPO trains and benchmarks | **M4**–**M7** |
| 15 | Phase 2 decision; LoRA experiment; latency measurement | — |
| 16 | **Wave 4 gate** — STR, TIM, SOP | **M8** prototype live |
| 17–19 | Dashboard; integration; fault injection | **M9** (W17) · **M10** (W19) |
| 20 | Paper submission, final report | **M11** |

Full detail: [Execution Manual Part 1](docs/90-manual/EXECUTION_MANUAL.md#part-1--week-by-week-course-of-action).
Acceptance criteria per milestone: [SOW §5](docs/00-planning/SOW.md).

### Capacity — the number that governs scope

| | |
|---|---|
| Work as originally specified | ~1,200 person-hours |
| Realistic capacity (3.5 students × 12 h × 17 weeks) | **~715 person-hours** |
| After the proposed descoping | ~890 person-hours |

Still over, and deliberately so — the conditional scope in SOW §2.3 absorbs the difference. Full
breakdown: [Feasibility Audit §2](docs/00-planning/FEASIBILITY-AUDIT.md).

---

## Decisions

Eleven architecture decision records. Each carries its rejected alternatives and the reason.

| ADR | Decision | Status |
|---|---|---|
| [001](docs/00-planning/decisions/ADR-001-two-track-dataset-strategy.md) | Bootstrap the detector on public data; own dataset runs in parallel, off the critical path | Active |
| [002](docs/00-planning/decisions/ADR-002-mfstnet-training-corpus.md) | Build MFSTNet's corpus by auto-labelling real video with the fine-tuned detector | Active |
| [003](docs/00-planning/decisions/ADR-003-laptop-as-edge.md) | Laptop as edge node; Jetson optional | Active |
| [004](docs/00-planning/decisions/ADR-004-phased-document-delivery.md) | Documents ship in four waves gated on project phases | Active |
| [005](docs/00-planning/decisions/ADR-005-local-first-training.md) | Train locally on cached frozen-backbone features | Active |
| [006](docs/00-planning/decisions/ADR-006-curate-then-collect-dataset.md) | Curate a benchmark, collect a small permissioned campus set | **Proposed** |
| [007](docs/00-planning/decisions/ADR-007-backbones-and-training-recipe.md) | DINOv2, bf16, LoRA instead of unfreezing, INT8 at export | Active |
| [008](docs/00-planning/decisions/ADR-008-prototype-descoping.md) | Reduce infrastructure, protect the experiments | **Proposed** |
| [009](docs/00-planning/decisions/ADR-009-ppo-forecast-surrogate.md) | Noise-calibrated forecast surrogate; 16-dimensional state | Active |
| [010](docs/00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md) | SUMO sublane model and heterogeneous vehicle types | Active |
| [011](docs/00-planning/decisions/ADR-011-webster-definition.md) | Webster cycle clamping, starvation semantics, two roles reconciled | Active |
| [012](docs/00-planning/decisions/ADR-012-webster-saturation-flow.md) | Sweep the published saturation-flow range rather than picking a value | Active |
| [013](docs/00-planning/decisions/ADR-013-artifact-hosting-and-publication.md) | Code on GitHub, weights on Hugging Face, citation on Zenodo; Git LFS retired for weights | **Proposed** |
| [014](docs/00-planning/decisions/ADR-014-dashboard-metrics-separation.md) | The dashboard's benchmark panel and live monitor are separate and never merge | **Proposed** |

**ADR-006 and ADR-008 change graded requirements and need faculty sign-off.** Until then the project
plans against two incompatible futures.

---

## Defects found and fixed

What the planning phase actually bought. Each of these would have cost days to weeks if found during
implementation, and two would have shipped undetected.

| Defect | Would have surfaced | Fix |
|---|---|---|
| No MFSTNet training corpus specified at all | Week 10 | [ADR-002](docs/00-planning/decisions/ADR-002-mfstnet-training-corpus.md) |
| **Label placed inside the observation window** | Week 12, as "great validation, useless model" | Amendment A15 |
| A 5-minute clip yields **zero** sequences | Week 9, as an empty corpus | A15 — minimum clip is 6 minutes |
| Global pooling produced four *identical* lane predictions | Week 12, misdiagnosed as a training bug | Amendment A8 — per-lane ROI pooling |
| PPO forecast fields had no producer during SUMO training | Week 11, improvised under deadline | [ADR-009](docs/00-planning/decisions/ADR-009-ppo-forecast-surrogate.md) |
| **Evaluation was circular** against count-based baselines | Never — it would have shipped | Amendment A9 — human-verified test split |
| Bootstrap resampled sequences, not clips | Never — intervals would have looked tight and been wrong | Amendment A19 |
| Annotation effort underestimated ~3× | Week 7 | [ADR-006](docs/00-planning/decisions/ADR-006-curate-then-collect-dataset.md) |
| Novelty overclaimed against published prior art | At peer review | [Related Work](docs/00-planning/RELATED-WORK.md) |
| SUMO modelled traffic the paper is not about | At peer review | [ADR-010](docs/00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md) |
| Webster baseline unparameterised — a strawman | At peer review | [ADR-011](docs/00-planning/decisions/ADR-011-webster-definition.md) + [ADR-012](docs/00-planning/decisions/ADR-012-webster-saturation-flow.md) |
| HCM per-lane saturation flow structurally wrong for filtering traffic | At peer review, or as a silently mis-tuned baseline | ADR-012 — per metre of width, swept |
| **C1 overclaimed** — the vision-based congestion literature was never surveyed | At peer review, on the abstract's framing | [RELATED-WORK §2.6](docs/00-planning/RELATED-WORK.md) |

### Two findings we withdrew

Recording our own errors is part of the method, not an embarrassment. Full list:
[Document Register § Withdrawn claims](docs/DOCUMENT-REGISTER.md).

**"400 frames/day/person" annotation velocity** — wrong by roughly 3× for scenes carrying 20–60
objects. Replaced with an instruction to measure it.

**"The 180 s starvation limit contradicts a 186 s cycle" (P6)** — wrong. It conflated *cycle length*
with *lane wait*. A lane waits for the other phase's green plus two all-reds, 96 s, not a full cycle.
The threshold was correct all along. The spec-invariant test that "found" it had encoded a plausible
assumption built on a wrong model of the system.

---

## Open items

| ID | Item | Owner | Due |
|---|---|---|---|
| **ADR-006** | Dataset redefinition — needs faculty sign-off | Team lead | **This week** |
| **ADR-008** | Prototype descoping — needs faculty sign-off | Team lead | **This week** |
| P1 | Congestion thresholds may be degenerate on real data | R1 | Week 2 pilot |
| P2 | PPO state normalisers chosen before real counts existed | R3 | Week 10 |
| P3 | Backbone adaptation — frozen vs LoRA vs full | R2 | Week 15 |
| P4 | Ablation epoch count (likely unnecessary after caching) | R2 | Week 13 |
| P5 | Label-noise estimate from the verification subset | R1 | Week 12 |
| P7 | Six MQTT payload schema defects | R4 | Before Week 7 |
| ~~P8~~ | ~~Webster saturation flow~~ — **closed** by ADR-012 | — | Done |
| P9 | Is phase repetition legal? | R3 | Before Week 13 |
| R22 | Verify ITSC / CVIP deadlines against a ~Dec 2026 finish | Team lead | **This week** |
| R25 | Detector may fail on the India-specific classes the dataset exists to add — published evidence says it does | R1 | Week 9 (M2) |
| R26 | Novelty overclaimed twice. **Search by task, not only architecture**, before drafting | R2 | Before Week 16 |
| **B10, B16, B18, B29, B30** | Five load-bearing citations still unverified — [verification queue](docs/00-planning/BIBLIOGRAPHY.md#verification-queue) | R2 | Before the paper |

Open triage: [TRIAGE-001](docs/00-planning/triage/TRIAGE-001-mqtt-payload-schema.md) ·
[TRIAGE-002](docs/00-planning/triage/TRIAGE-002-webster-parameterisation.md).
Incomplete research: [RESEARCH-001](docs/00-planning/research/RESEARCH-001-webster-parameterisation.md).

---

## What we claim, and what we do not

Overclaiming is the fastest way to lose a review. Full analysis:
[Related Work](docs/00-planning/RELATED-WORK.md).

**We claim** — per-lane congestion forecasting from a single fixed camera in **non-lane-disciplined
heterogeneous** traffic, coupled to a controller (narrowed — see below) · the fusion gate as an
analysed interpretability artifact ·
a harmonised Indian multi-class benchmark with a fixed-camera subset · anticipatory state for RL
signal control, with a forecast-quality sensitivity curve · a density-stratified evaluation.

**We do not claim** — novel CNN-ViT fusion (Conformer, CrossViT) · novel bidirectional
cross-attention (this is ViLBERT co-attention, 2019) · a novel gating mechanism (Flamingo) · a novel
RL controller (MPLight, PressLight) · **any real-world wait-time reduction — every control result is
SUMO-simulated**.

---

## Repository

```
docs/               The SDLC suite — index at docs/README.md
  00-planning/        SOW · BRD · PRD · DATASETS · RELATED-WORK · BIBLIOGRAPHY
                      FEASIBILITY-AUDIT · PROCESS-REVIEW · SCOPE-VARIATION-REQUEST
                      decisions/ · triage/ · research/
  01-requirements/    SRS · FRD · NFR · RTM
  02-design/          HLD (corpus pipeline delivered early) · SAD, LLD due Week 5
  03-testing/         STP, STD, UAT due Week 11 · STR Week 16
  04-deployment/      TIM, SOP due Week 16
  90-manual/          EXECUTION_MANUAL · TRAINING-GUIDE · weekly/
  plans/              PLAN-01 detection & corpus pipeline
  99-archive/         Superseded documents, retained for the decision trail
  DOCUMENT-REGISTER.md  Version and status of every document

mfstnet/            corpus/ (built) · encoders, fusion, temporal, heads (planned) · configs/
detection/  indiatrafficnet/  simulation/  server/  dashboard/  edge/
experiments/results/  models/ (Git LFS)  scripts/  tests/  notebooks/
```

## Getting started

```bash
git lfs install && git clone <repo-url> && cd major-project
python scripts/check_env.py          # tells you what is missing, in plain language
```

> **Use Python 3.11.** PyTorch 2.3.1 publishes no wheels above 3.12, and a newer interpreter fails
> with `No matching distribution found for torch` — which looks like a network problem and is not.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
cp .env.example .env

python scripts/check_env.py          # should now report no blockers
python -m pytest -q                  # 44 tests
```

Then [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup).

## Working rules

- **The PRD wins on numbers.** If it is wrong, amend it and log it in
  [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) — never work around it.
- **Build order is non-negotiable.** Phase 1 converges before gating or temporal attention exists.
- **Config, not code.** Hyperparameters live in YAML because the ablation harness drives configs.
- **Every module disableable by flag.** A module that cannot be switched off cannot be ablated.
- **`set_seed(42)` before building any model.**
- **Result CSVs are written by the script, never transcribed.** Paper tables are generated from
  committed CSVs by a committed script.
- **Every latency figure states its measurement host.**
- **Negative results are reported and analysed, never dropped.**
- **Run `python scripts/check_docs.py` before any documentation commit.** It also runs in CI.

## Licence

Code: MIT (planned). Curated benchmark: per-source licences, documented in its datasheet.
Campus-collected subset: CC BY 4.0, faces and plates blurred before release.
