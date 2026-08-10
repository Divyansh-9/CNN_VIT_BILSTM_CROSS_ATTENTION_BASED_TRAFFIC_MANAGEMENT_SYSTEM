# MFSTNet

**A camera-only traffic congestion forecaster and reinforcement-learning signal controller for
unstructured Indian intersections.**

B.Tech CSE (ML/AI) major project · 20 weeks · 3–4 members · ₹0 cash budget · targeting IEEE ITSC / CVIP

> **Status: documentation complete, implementation not started.** Six planning and requirements
> documents, eight architecture decision records, and a feasibility audit are committed. No code
> yet. Start at [docs/README.md](docs/README.md).

---

## The problem

Indian urban intersections run mostly on fixed-time signal plans set once and rarely revised. Those
plans assume lane-disciplined, homogeneous traffic. Indian traffic is neither — two- and
three-wheelers filter between lanes, auto-rickshaws and e-rickshaws occupy a size and acceleration
class Western-trained detectors do not model, and cattle on the carriageway is routine.

Three consequences: signal timings do not match demand; off-the-shelf detectors miscount the vehicle
mix that matters; and control reacts to queues that have already formed rather than anticipating
them.

The mainstream traffic-forecasting literature (STGCN, DCRNN, Graph WaveNet) solves the first problem
using **loop detectors and probe sensors** — infrastructure most Indian intersections do not have.
This project asks whether a single camera can do the job instead.

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
forecast becomes part of the RL controller's state vector, and the whole loop runs on a laptop.

---

## Why each component — and what it buys us

This is the section to read before asking "why not just use X?". Every choice below is defended, and
where a choice is weak, that is said.

### Perception

| Component | Why this one | What we get |
|---|---|---|
| **YOLOv8s** (Ultralytics) | Best speed/accuracy trade-off at the edge, mature tooling, trivial fine-tuning. RT-DETR is stronger but heavier and slower to train | Per-lane vehicle counts — **and** the labels for MFSTNet's training corpus, which is what makes the pipeline self-supervising |
| **8 India-specific classes** | COCO has no auto-rickshaw, no e-rickshaw, no cattle. A detector blind to ~20% of the vehicle mix corrupts every downstream decision | Counts that reflect what is actually on the road |
| **Fixed lane ROI polygons** | Counting by region needs no tracking. Tracking would add a whole subsystem and another error source feeding the labels | Instantaneous per-lane occupancy from a single frame |

### The model

| Component | Why this one | What we get |
|---|---|---|
| **ResNet-50, frozen** | Local texture and vehicle-shape detail. Frozen because ~4M trainable params on a small dataset already risks overfitting (PRD R4) | The "what is here" signal |
| **DINOv2 ViT-S/14, frozen** | Global scene layout — queue extent, spatial arrangement — which convolution captures poorly. **DINOv2 rather than supervised ViT because the backbone never updates, so representation quality is the entire contribution**, and self-supervised features are markedly stronger in frozen small-data regimes ([ADR-007](docs/00-planning/decisions/ADR-007-backbones-and-training-recipe.md)) | The "how is the scene arranged" signal |
| **Bidirectional cross-attention** | Each branch queries the other, so local detail and global context inform each other rather than being concatenated. Honestly: this is co-attention, published in ViLBERT (2019) — the application is new, the mechanism is not | Fusion that adapts to content instead of fixed weighting |
| **The learned gate** | `g = σ(W[Z_A; Z_B])`, `F = g·Z_A + (1−g)·Z_B`. Hypothesis (PRD §14.2): dense chaotic scenes need CNN detail, sparse structured scenes need ViT context | **An interpretability result, not an internal detail.** We log it, chart it, and test whether it tracks scene density. If it does, that is a finding; if it collapses, we report that (BR-19) |
| **BiLSTM, 2×128, bidirectional** | Short-range dynamics — queue build-up, arrival bursts — over 60 timesteps. Mature, cheap, well understood | Temporal modelling that is not the research risk |
| **Temporal self-attention** *(Phase 2)* | Long-range cycles the LSTM compresses away | Stretch goal only — PRD §2.4 forbids it before Phase 1 converges |
| **Per-lane ROI pooling** | PRD §8.1 as written global-average-pools then applies one shared head four times, producing four *identical* predictions. ROI pooling makes each lane read its own image region | Four genuinely different lane predictions, and sources with fewer than four approaches work unchanged |

### Control

| Component | Why this one | What we get |
|---|---|---|
| **SUMO + TraCI** | The standard open-source microscopic traffic simulator; every comparable paper uses it, so results are comparable | A reproducible environment where all four control methods face identical demand per seed — the precondition for a valid paired t-test |
| **PPO** (Stable-Baselines3) | Stable on discrete action spaces, sane defaults, one of the most reproducible RL implementations available | Signal timing learned rather than tuned. **Not a contribution on its own** — single-intersection RL control is well-solved (MPLight, PressLight) |
| **MFSTNet forecast in the state** | *This* is the RL contribution: the policy sees an anticipated future, not only the present | A testable question the signal-control literature largely does not ask |
| **Fixed / Webster / Random baselines** | Fixed is the deployed reality; Webster is the classical optimum; Random is the sanity floor | A comparison an examiner recognises |
| **Hard safety constraints** | Min green 10 s, max 90 s, all-red ≥3 s, no lane starved past 180 s — **enforced by the actuation layer, not learned** | A reward penalty makes starvation expensive; only a constraint makes it impossible |

### System

| Component | Why this one | What we get |
|---|---|---|
| **MQTT / Mosquitto** | The de-facto IoT messaging standard; per-topic QoS is exactly the primitive this system needs | Emergency at QoS 2 (exactly-once — a duplicate fires a spurious preemption, a loss risks a life), counts and commands at QoS 1, predictions at QoS 0 (superseded every 5 s, so loss self-heals) |
| **FastAPI** | Async, typed, automatic OpenAPI docs | A backend that documents itself, which matters when four people integrate in Week 17 |
| **ONNX Runtime** | Framework-independent CPU inference, and the route to INT8 quantisation | The ≤150 ms server-CPU budget (FR-M13) |
| **React + Recharts** | The Benchmark page reads committed result CSVs directly | The dashboard becomes **evidence**, not illustration — regenerate a result and it updates itself |
| **SQLite + Parquet** *(proposed)* | Replaces PostgreSQL + TimescaleDB. Identical query surface at this data volume, one less service, and the analysis notebooks read the same files ([ADR-008](docs/00-planning/decisions/ADR-008-prototype-descoping.md)) | ~40 hours back, and a demo with fewer things that can fail |
| **Laptop as edge node** | Jetson Nano costs ₹12–18k against a ₹0 budget, and supply is constrained ([ADR-003](docs/00-planning/decisions/ADR-003-laptop-as-edge.md)) | M8 at zero cost. Every latency figure states its measurement host, and laptop numbers are labelled **optimistic proxies** — an RTX 4050 is not a Jetson |

### Method

| Practice | Why | What we get |
|---|---|---|
| **Cached frozen-backbone features** | Frozen backbones emit identical features every epoch, and ablation configs A–G differ only *downstream* of them ([ADR-005](docs/00-planning/decisions/ADR-005-local-first-training.md)) | The 60–90 hour ablation collapses to hours. **The highest-leverage decision in the project** — it also makes a backbone ablation nearly free |
| **Human-verified test split** | Labels derive from detector counts, and three baselines also consume detector counts — so their errors correlate with the label errors and score as correct, while MFSTNet's independent errors score as wrong | An evaluation that is not rigged against our own model |
| **Density-stratified reporting** | The hypothesis is that fusion helps *in dense scenes*. One aggregate number averages that away | "9 points better in high density, ties in sparse" is a finding; "0.81 vs 0.80" is a shrug |
| **Splits cut by source clip** | Sequences from one clip overlap by 54 of 60 frames | No leakage, asserted at load rather than hoped for |
| **Seeds, pinned deps, raw CSVs** | NFR-07–10, marked Critical | Results a third party can reproduce — which is what makes them evidence |

---

## What we claim, and what we do not

Overclaiming is the fastest way to lose a review. Full analysis in
[RELATED-WORK.md](docs/00-planning/RELATED-WORK.md).

**We claim:** a camera-only congestion forecaster for unstructured traffic where the forecasting
literature assumes sensor infrastructure · the fusion gate as an analysed interpretability artifact ·
a harmonised Indian multi-class benchmark with a fixed-camera subset · anticipatory state for RL
signal control · a density-stratified evaluation.

**We do not claim:** novel CNN-ViT fusion (Conformer, CrossViT) · novel bidirectional cross-attention
(this is ViLBERT co-attention, 2019) · a novel gating mechanism (Flamingo) · a novel RL controller
(MPLight, PressLight) · any real-world wait-time reduction — **every control result is
SUMO-simulated**.

---

## Repository

```
docs/            The SDLC suite — start at docs/README.md
  00-planning/     SOW · BRD · PRD · DATASETS · RELATED-WORK · FEASIBILITY-AUDIT · decisions/
  01-requirements/ SRS · FRD · NFR · RTM
  02-design/       Wave 2, Week 5
  03-testing/      Wave 3, Week 11 · STR Week 16
  04-deployment/   Wave 4, Week 16
  90-manual/       EXECUTION_MANUAL · TRAINING-GUIDE · weekly/
indiatrafficnet/ detection/ mfstnet/ simulation/ server/ dashboard/ edge/
experiments/results/  models/ (Git LFS)
```

## Getting started

```bash
git lfs install && git clone <repo-url> && cd major-project
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

Then [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup).

| You are | Read |
|---|---|
| On the team, day one | [Execution Manual](docs/90-manual/EXECUTION_MANUAL.md) Part 0, then Part 1 weekly |
| Training models | [Training Guide](docs/90-manual/TRAINING-GUIDE.md) |
| Faculty guide or examiner | [Feasibility Audit](docs/00-planning/FEASIBILITY-AUDIT.md), then [SOW](docs/00-planning/SOW.md) and [RTM](docs/01-requirements/RTM.md) |
| Writing the paper | [Related Work](docs/00-planning/RELATED-WORK.md) |
| Implementing anything | [PRD](docs/00-planning/PRD.md) for numbers, [FRD](docs/01-requirements/FRD.md) for acceptance criteria |

## Decisions

| ADR | Decision |
|---|---|
| [001](docs/00-planning/decisions/ADR-001-two-track-dataset-strategy.md) | Bootstrap the detector on public data; own dataset runs in parallel, off the critical path |
| [002](docs/00-planning/decisions/ADR-002-mfstnet-training-corpus.md) | Build MFSTNet's corpus by auto-labelling real video with the fine-tuned detector |
| [003](docs/00-planning/decisions/ADR-003-laptop-as-edge.md) | Laptop as edge node; Jetson optional |
| [004](docs/00-planning/decisions/ADR-004-phased-document-delivery.md) | Documents ship in four waves gated on project phases |
| [005](docs/00-planning/decisions/ADR-005-local-first-training.md) | Train locally on cached frozen-backbone features |
| [006](docs/00-planning/decisions/ADR-006-curate-then-collect-dataset.md) | **Proposed** — curate a benchmark, collect a small campus set. Replaces the 12,000-frame public-road campaign |
| [007](docs/00-planning/decisions/ADR-007-backbones-and-training-recipe.md) | DINOv2, bf16, LoRA instead of unfreezing, INT8 at export |
| [008](docs/00-planning/decisions/ADR-008-prototype-descoping.md) | **Proposed** — reduce infrastructure, protect the experiments |

ADR-006 and ADR-008 change graded requirements and need faculty guide sign-off. Take them with the
[Feasibility Audit](docs/00-planning/FEASIBILITY-AUDIT.md) in Week 1–2.

## Working rules

- **The PRD wins on numbers.** If it is wrong, amend it and log it in
  [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) — never work around it.
- **Build order is non-negotiable** (PRD §2.4). Phase 1 converges before gating or temporal attention
  is written.
- **Config, not code.** Hyperparameters live in YAML because the ablation harness drives configs.
- **Every module disableable by flag.** A module that cannot be switched off cannot be ablated.
- **`set_seed(42)` before building any model.**
- **Result CSVs are written by the script, never transcribed.** Paper tables are generated from
  committed CSVs by a committed script.
- **Every latency figure states its measurement host.**
- **Negative results are reported and analysed, never dropped.**

## Licence

Code: MIT (planned). IndiaTrafficNet-Bench: per-source licences, documented in its datasheet.
Campus-collected subset: CC BY 4.0, anonymised before release.
