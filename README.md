<div align="center">

# 🚦 MFSTNet — CNN-ViT-BiLSTM Cross-Attention Traffic Management

**Camera-based congestion forecasting and simulation-based signal-control
research, targeting unstructured Indian intersections**

[![tests](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/tests.yml/badge.svg)](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/tests.yml)
[![docs](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/docs.yml/badge.svg)](https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM/actions/workflows/docs.yml)
![status](https://img.shields.io/badge/STATUS-BUILT%20%C2%B7%20VALIDATION%20IN%20PROGRESS-yellow?style=for-the-badge)
![licence](https://img.shields.io/badge/LICENCE-NOT%20YET%20GRANTED%20%C2%B7%20RIGHTS%20UNDER%20REVIEW-lightgrey?style=for-the-badge)

![python](https://img.shields.io/badge/PYTHON-3.14%20local%20%C2%B7%203.12%20CI-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pytorch](https://img.shields.io/badge/PYTORCH-2.13.0%20cu126-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![sim](https://img.shields.io/badge/SUMO-1.27.1%20(pinned)-FFB000?style=for-the-badge)
![sb3](https://img.shields.io/badge/SB3-2.9.0-success?style=for-the-badge)

![cnn](https://img.shields.io/badge/CNN-ResNet--50%20(frozen)-6A5ACD?style=for-the-badge)
![vit](https://img.shields.io/badge/ViT-DINOv2%20S%2F14%20(frozen)-8A2BE2?style=for-the-badge)
![fusion](https://img.shields.io/badge/FUSION-Gated%20Cross--Attention-FF1493?style=for-the-badge)
![temporal](https://img.shields.io/badge/TEMPORAL-BiLSTM%202%C3%97128-20B2AA?style=for-the-badge)

![state](https://img.shields.io/badge/PPO%20STATE-17--dim-informational?style=for-the-badge)
![adrs](https://img.shields.io/badge/ADRs-28-lightgrey?style=for-the-badge)
![budget](https://img.shields.io/badge/BUDGET-%E2%82%B90-brightgreen?style=for-the-badge)
![project](https://img.shields.io/badge/PROJECT-B.Tech%20CSE%20(ML%2FAI)-navy?style=for-the-badge)

</div>

> **The badges report what is true, not what is planned.** The two CI badges are
> live workflow results.
>
> **The system is built and measured.** What remains is validation (V1
> human counts, V2 real-camera latency), the edge deployment prerequisites the
> clean-environment check left open (D4), and the remaining handover documents.
>
> **The deployed edge path is a committed program (D3):** `python -m edge.run`.
> On recorded footage through a real broker it reproduced the earlier
> harness's forecasts payload for payload.
>
> **Two asserted claims in `docs/00-planning/CLAIMS.yaml` are red:** `domain`
> and `class_coverage`. That is why `scripts/make_paper_tables.py` is withheld,
> by design.
>
> **The forecast-for-control line closed with a measured null (P130).** Under
> its protocol, every PPO arm had more delay than both Webster arms.
>
> **The historical P82 experiment measured 19.4% lower mean wait than Webster.
> That figure is correct for what was run, but it comes from an unmatched setup
> and is citable only with its qualifications.** It is not evidence that PPO
> generally outperforms Webster ([P138](docs/00-planning/PRD-CHANGELOG.md)).

---

B.Tech CSE (ML/AI) major project · 20 weeks · 3–4 members · ₹0 cash budget

| | |
|---|---|
| **Built** | ~62,900 lines of Python in 279 files · 90 test modules · 1,525 tests: **1,522 pass, 3 skip** in a local run on 2026-10-21 (Python 3.14.4, Windows; CI runs Python 3.12 on Linux) |
| **Specified** | 28 architecture decisions · changelog P1–P143, plus D1–D45 · build steps S01–S69 |
| **Waiting on the guide** | Narrowing claim C1 (MEMO-2026-10-17, S63zm) |
| **On hold (owner, P143)** | Indian-data acquisition: the Part B evaluation set (S19) and the BMD-45 outreach (S54). Engineering proceeds on the foreign corpus; Indian-domain validation stays unestablished |
| **Waiting on the owner** | V1 labellers · the S65 camera window · licensing (handled separately) |

> **New to the project?** Start with **[EXPLAIN.md](EXPLAIN.md)**, which
> covers everything in plain English.
>
> **On the team and catching up?** **[docs/TEAM-STATUS.md](docs/TEAM-STATUS.md)** says,
> on one page, what is built, what it showed, how to see it running, and what is left.
>
> **Want the current status?** **[BUILD-LOG.md](BUILD-LOG.md)** is the status
> board. `scripts/check_build_log.py` checks it against the repository.

---

## Contents

| Section | Read it if you want |
|---|---|
| [What it does](#what-it-does) | The system as built, in one diagram |
| [Results](#results-and-what-they-support) | What has been measured, and what each result supports |
| [Reading paths](#reading-paths) | Where to start, by role |
| [Why each component](#why-each-component) | The defence of every technology choice |
| [Decisions](#decisions) | All 28 ADRs |
| [Open items](#open-items) | Everything unresolved, with its owner |
| [Claims](#what-we-claim-and-what-we-do-not) | What survives peer review |
| [Repository](#repository) · [Getting started](#getting-started) · [Rules](#working-rules) | Practicalities |

---

## The problem

Indian urban intersections run mostly on fixed-time signal plans, set once
and rarely revised. Those plans assume lane-disciplined, homogeneous traffic,
and Indian traffic is neither:
- two- and three-wheelers filter between lanes;
- auto-rickshaws and e-rickshaws occupy a size and acceleration class that
  Western-trained detectors do not model;
- cattle on the carriageway is routine.

Three consequences follow:
- signal timings do not match demand;
- off-the-shelf detectors miscount the vehicle mix that matters;
- control reacts to queues that have already formed, rather than anticipating
  them.

The mainstream forecasting literature (STGCN, DCRNN, Graph WaveNet) solves the
first problem with **loop detectors and probe sensors**, infrastructure most
Indian intersections lack. This project asks whether a single camera can do
the job instead.

## What it does

```
                 edge laptop (ADR-003, ADR-026)                       server
camera ─▶ YOLOv8 ─▶ per-lane counts ─┬─▶ persistence class forecast ─┐
   (frames stay here, NFR-13)        └─▶ ridge next-minute count ────┤
                                                                     ├─MQTT─▶ FastAPI ─▶ read-only dashboard
         MFSTNet (verified edge path, ONNX; not serving a role) ─ ─ ─┘        (SQLite)    (GET only)

SUMO + TraCI ─▶ PPO / Webster / fixed / longest-queue ─▶ 30-seed paired benchmark
   (simulation only; no forecast is connected to real signal timing — P97a)
```

**ADR-027 sets the two forecasting roles:**
- **the class role:** a persistence forecaster for the congestion class;
- **the count role:** a level-free ridge model for the next-minute count.

**Neither forecast feeds signal timing.** MFSTNet's edge path is built and
verified, and the vision claim (C2) remains open.

**Every network boundary enforces the contract (P140–P142).** A malformed or
out-of-range payload is refused rather than crashing the server path, every
field is typed and bounded, the intersection id is a closed pattern, and no
refusal or log line repeats what the sender wrote.

**The edge path is one committed program (D3):**

```powershell
python -m edge.run --source clip.mp4 --lanes lanes.json --approaches lane_0=W lane_1=N lane_2=E `
    --camera NE8th --intersection-id ne8th --broker-host 127.0.0.1 --broker-port 1883
```

It refuses bad arguments at start-up, gives the forecasters raw lane totals and
the wire the mapped class breakdown, keeps frames in memory only, and reads a
camera URL only from `STMS_CAMERA_URL` (`--source camera`). See
[PLAN-D3](docs/plans/PLAN-D3-edge-entry-point.md).

**Two fallbacks are implemented and tested (FR-A06):**
- **A missing, stale or invalid forecast:** `ForecastGate` hands the decision
  to the no-forecast policy, and invalid counts go to Webster. This is in
  simulation (`simulation/forecast_state.py`).
- **No successful publish for over 10 s:** the edge node switches to a locally
  embedded fixed cycle, 30 s per phase (`LocalWebster` in `edge/node.py`).

**The server's command endpoint is a prototype.** `POST /observation` proposes
a phase with a placeholder rule, "switch toward the busier axis". It then
applies `SignalGuard`'s limits and logs which rule fired. The trained PPO
policy is not wired into the server, and nothing drives real signal hardware.

---

## Results, and what they support

Every number below is generated from a committed CSV by a committed script
(NFR-09/10). The link is the authority, and the README is not.

| Track | Result | Where | What it supports |
|---|---|---|---|
| **MFSTNet ablation A–H** | Leave-one-camera-out, 4 folds × 5 seeds | [loco_summary.csv](experiments/results/loco_summary.csv) | Fold means with a bootstrap CI over **4 folds**. Two asserted claims are red, so no paper table is generated |
| **Forecasting roles** | Persistence is the best transferable class forecaster; the ridge model is the count forecaster | P103–P106, ADR-027 | Two separate roles, and neither drives control |
| **Forecast-for-control** | **Null.** A perfect forecast did not reduce delay against no forecast (+5.41 s, n.s.) or against persistence (+2.38 s, n.s.), over 28 seeds | [ceiling/](experiments/results/ceiling/), P130, P133 | The line is closed. P97a Part 2 is deferred |
| **PPO against Webster, P130 protocol** | Every PPO arm had more delay than both Webster arms. No-forecast PPO against tuned Webster: +3.91 s, *d* +0.61 (descriptive, unadjusted) | P130 | Under that protocol (`pulsed`, training and evaluation matched), Webster had lower delay. This is not a replication of P82 |
| **PPO against Webster, P82 (historical)** | 19.4% lower mean wait in the historical P82 experiment, which had the following limits: <br>• trained without the sublane model and evaluated with it (P119) <br>• the same arrival times across all 30 seeds (P116 b) <br>• one policy, one training seed, one traffic regime | [benchmark_ppo/](experiments/results/benchmark_ppo/) | Citable only as a qualified historical result (P138). It does **not** show that PPO generally outperforms Webster |
| **Forecast-assisted Webster** | Stopped at its pre-registered power gate (n = 347 needed, against 200 allowed) | [faw/](experiments/results/faw/), P132 | Exploratory only |
| **Edge latency (V2, stand-in)** | The model call alone is p95 325.9 ms on laptop CPU and **fails 6a** (≤ 150 ms). The whole edge step passes 6b, and transport passes 6c | P135, [v2/](experiments/results/v2/) | Measured on a laptop. The real-camera run (S65) is pending |
| **Prototype integration (Phase C)** | 300 samples of recorded footage through a real MQTT broker: 0 of 900 lane-count publishes undelivered; 271 class and 241 count forecasts stored byte-identical; the dashboard matched the API; four injected failures handled | D1–D2 in [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) | Transport and display only. The committed `edge.run` later reproduced these forecasts payload for payload (D3). **Not** evidence that the forecasts are safe for signal control |
| **Reproducibility** | The committed SUMO episode reproduces exactly on Linux CI under SUMO 1.27.1, and not under 1.28.0 | P137 | Versions are now asserted by a CI preflight |

Negative and marginal results are reported, never dropped (§2.5.5).

---

## Reading paths

| You are | Read, in order |
|---|---|
| **Faculty guide / examiner** | This page → [MEMO-2026-10-17](docs/00-planning/MEMO-2026-10-17-adr021-ceiling.md) → [PLAN-2026-10-17 validation](docs/00-planning/PLAN-2026-10-17-validation-and-publication.md) → [RTM](docs/01-requirements/RTM.md) |
| **Joining the team** | [EXPLAIN.md](EXPLAIN.md) → [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup) → [BUILD-LOG](BUILD-LOG.md) |
| **Implementing anything** | [PRD](docs/00-planning/PRD.md) for numbers → the [ADRs](docs/00-planning/decisions/) that amend it → [FRD](docs/01-requirements/FRD.md) for acceptance criteria |
| **Writing the paper** | [Related Work](docs/00-planning/RELATED-WORK.md) **before** the method section → [CLAIMS.yaml](docs/00-planning/CLAIMS.yaml) → [Bibliography](docs/00-planning/BIBLIOGRAPHY.md) |
| **Wondering why something changed** | [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) (P entries) and [decisions/](docs/00-planning/decisions/) |

---

## Why each component

The section to read before asking "why not just use X?". Where a choice is
weak, it says so.

### Perception

| Component | Why this one | What we get |
|---|---|---|
| **YOLOv8s** | The best speed/accuracy trade-off at the edge, with mature tooling | Per-lane counts, and the labels for MFSTNet's corpus |
| **India-specific classes** | COCO has no auto-rickshaw, no e-rickshaw and no cattle | Counts that reflect the actual vehicle mix |
| **Hand-placed lane geometry** | Automatic lane centres move 0.164 of the frame width when the detector changes (P23) | Lanes that do not drift with the model |

### The model

| Component | Why this one | What we get |
|---|---|---|
| **ResNet-50, frozen** | Local texture and vehicle-shape detail. It is frozen because the dataset is small | The "what is here" signal |
| **DINOv2 ViT-S/14, frozen** | Global scene layout. DINOv2 because, with a frozen backbone, representation quality is the whole contribution ([ADR-007](docs/00-planning/decisions/ADR-007-backbones-and-training-recipe.md)) | The "how is the scene arranged" signal |
| **Bidirectional cross-attention** | This is co-attention, as in ViLBERT (2019). The application is new; the mechanism is not | Fusion that adapts to the content |
| **The learned gate** | `g = σ(W[Z_A; Z_B])`, `F = g·Z_A + (1−g)·Z_B` | **An analysed artifact.** It is logged and tested against density, and reported whatever it shows |
| **BiLSTM 2×128** | Arrival bursts over 60 timesteps. It is cheap and not the research risk | Temporal modelling |
| **Per-lane ROI pooling** | PRD §8.1 as written produced four *identical* lane predictions | Four genuinely different lane predictions |
| **Linear probe (config H)** | The floor every frozen-backbone paper is expected to report (A22) | An honest baseline for the full model |

### Control

| Component | Why this one | What we get |
|---|---|---|
| **SUMO + TraCI, sublane model** | The standard open-source simulator. The sublane model is there because the traffic has no lane discipline ([ADR-010](docs/00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md)) | Identical demand for every method per seed, the precondition for paired tests |
| **PPO** (Stable-Baselines3) | Stable on discrete actions, and reproducible | A learned controller, in simulation only. **Under the P130 protocol it did not beat Webster** |
| **Hard safety constraints** | Minimum green 10 s, maximum 90 s, all-red 3 s, **enforced by actuation, not learned** (`server/safety.py`, with the same limits in `simulation/runner.py`) | Starvation-prevention constraints are enforced, and any red spell over 180 s is counted and reported as a starvation event (ADR-011). This is a bound under the tested conditions, not a proof |
| **Webster, swept** | Saturation flow is swept across the published range, and Webster's *best* configuration is the baseline ([ADR-012](docs/00-planning/decisions/ADR-012-webster-saturation-flow.md)) | The baseline cannot be called a strawman |

### System

| Component | Why this one | What we get |
|---|---|---|
| **MQTT / Mosquitto** | Per-topic QoS, attached to the topic in `contracts/mqtt.py` | Emergency at QoS 2; counts and commands at QoS 1; predictions at QoS 0 |
| **FastAPI + SQLite** | Typed and async. SQLite replaces PostgreSQL + TimescaleDB ([ADR-008](docs/00-planning/decisions/ADR-008-prototype-descoping.md)) | One less service |
| **ONNX Runtime** | Framework-independent CPU inference | The edge model path ([ADR-026](docs/00-planning/decisions/ADR-026-mfstnet-runs-on-the-edge.md)) |
| **React dashboard, read-only** | Benchmark evidence and live forecasts are kept in separate panels ([ADR-014](docs/00-planning/decisions/ADR-014-dashboard-metrics-separation.md)) | Live values and historical evidence never merge. It is GET-only, with no signal control |
| **Laptop as the edge node** | A Jetson costs ₹12–18k against a ₹0 budget ([ADR-003](docs/00-planning/decisions/ADR-003-laptop-as-edge.md)) | Every latency figure states its measurement host |

### Method

| Practice | Why | What we get |
|---|---|---|
| **Cached frozen-backbone features** | Ablation configs differ only downstream of the backbones ([ADR-005](docs/00-planning/decisions/ADR-005-local-first-training.md)) | The full A–H ablation in about 1.5 h on CUDA, extrapolated from a five-camera pilot (P35) |
| **Leave-one-camera-out** | One camera's windows are not independent ([ADR-019](docs/00-planning/decisions/ADR-019-leave-one-camera-out-evaluation.md)) | The effective n is the number of cameras, and it is quoted beside every mean |
| **Five training seeds** | On one fold, one seed moved config E by 0.24 macro-F1 (P54) | Rankings of architectures rather than of initialisations |
| **Pre-registration with locks** | Protocols, thresholds and hashes are committed before the data | One-time evaluations: scripts refuse a re-run, and the locks are re-verified before use |
| **The claims gate** | `check_claims.py` checks every paper sentence against the corpus | No overrides: either the corpus or the claim changes |

---

## Decisions

There are 28 ADRs in [decisions/](docs/00-planning/decisions/), and each one
carries its rejected alternatives.

- **Accepted** by the project owner, unless the ADR's status line says
  otherwise. None is a faculty-guide signature:
  - ADR-001 to ADR-012;
  - ADR-020, as amended;
  - ADR-026;
  - ADR-027;
  - ADR-028 (one profile per camera, D31).
- **Proposed:** ADR-013 to ADR-019 and ADR-021 to ADR-025.
  - **The status field is not a record of what is running.** ADR-019, for
    example, is fully implemented.

Start with the eight ADRs that rewrite the architecture: ADR-001 to ADR-008.

---

## Open items

| Item | Owner | Blocks |
|---|---|---|
| Narrowing C1 to the measured null (ADR-023, `CLAIMS.yaml`) | Guide (MEMO-2026-10-17) | S63zm |
| Six-viewpoint evaluation set: **on hold by the owner (P143)**; reopening needs the guide's decision on MEMO-2026-08-22 | Owner, then guide | S19, the detection dataset; Indian-domain validation |
| V1 inter-rater pilot | Owner: two independent, blind labellers | S67; the main labelling set stays locked until ICC(2,1) ≥ 0.80 |
| V2 real-camera run | Owner: the camera window and an in-memory-only authorisation | S65 |
| Edge deployment prerequisites the clean-environment check left open (D4): teammate access to the detector weights, a camera-matched lane file, and an authenticated deployment broker (both clients authenticate (D6) and use verified TLS when given a CA file (D10), tested against Mosquitto 2.1.2 in a test configuration; no deployment broker configuration or certificate is committed) | Owner (weights and licence); team (lane file, broker configuration) | Deploying the edge from the repository alone; the TIM and SOP must state them |
| Handover documents: LLD, STP/STD/UAT/STR, TIM/SOP (the SAD and HLD are delivered) | Team | S47; the TIM and SOP must state the D4 prerequisites as open, and the TIM must be validated on a clean machine |
| The seed list is defined three ways (`spec.yaml`, `run_loco.py`, the manual) | Team | A PRD amendment, not a code edit |
| Licensing and public release | Owner, handled separately | The public copy (V3) |

---

## What we claim, and what we do not

The full analysis is in [Related Work](docs/00-planning/RELATED-WORK.md) and
[CLAIMS.yaml](docs/00-planning/CLAIMS.yaml).

**We claim:**
- per-lane congestion forecasting from a single fixed camera, under
  leave-one-camera-out evaluation;
- the fusion gate as an analysed artifact;
- density-stratified evaluation;
- a measured, pre-registered answer to whether a forecast helps an RL signal
  controller in simulation. Under the tested conditions it did not.

**We do not claim:**
- novel CNN-ViT fusion (Conformer, CrossViT);
- novel bidirectional cross-attention (ViLBERT, 2019);
- a novel gating mechanism (Flamingo);
- a novel RL controller (MPLight, PressLight);
- that PPO beats Webster (P130, P138);
- evaluation on Indian traffic. The `domain` claim is red: no fold-eligible
  camera is Indian (P58);
- **any real-world reduction in waiting time.** Every control result comes
  from SUMO simulation, and no forecast is connected to real signal timing.

---

## Repository

```
docs/            The SDLC suite, indexed at docs/README.md
  00-planning/     PRD · PRD-CHANGELOG · CLAIMS.yaml · decisions/ (28 ADRs) · memos · plans
  01-requirements/ SRS · FRD · NFR · RTM
  02-design/       SAD · HLD · HLD (corpus pipeline) · LLD outstanding
  03-testing/      STP, STD, UAT and STR outstanding
  04-deployment/   TIM and SOP outstanding
  plans/           implementation plans, including PLAN-D3
  90-manual/       EXECUTION_MANUAL · TRAINING-GUIDE
mfstnet/         the model: encoders, fusion, temporal, heads, corpus, configs/spec.yaml
simulation/      SUMO environment, runner, Webster, PPO controller, forecast gate, oracle
edge/  server/  contracts/  dashboard/
experiments/results/   committed CSVs and pre-registrations (graded deliverables)
scripts/  tests/  models/ (weights gitignored; the manifest is committed)
```

## Getting started

```powershell
python scripts/check_env.py          # BEFORE installing; says what is missing
py -3.12 -m venv .venv               # 3.12 is what CI runs; this machine runs 3.14.4
.\.venv\Scripts\Activate.ps1
pip install torch==2.13.0+cu126 torchvision==0.28.0+cu126 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt      # the authority on every pin
python scripts/check_sim_versions.py # SUMO, TraCI, sumolib, gymnasium, SB3 match the pins
python -m pytest -q
```

> **Use the `cu126` index.** The `cu121` and `cu124` indexes carry no torch at
> any version. The failure looks like a network problem, and it is not (P32).

Then read [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup).

## Working rules

- **The PRD wins on numbers.** If it is wrong, amend it and log the change in
  the [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md). Never work around it.
- **Config, not code.** Hyperparameters live in YAML, because the ablation
  harness drives configs (NFR-16).
- **`set_seed()` before building any model** (NFR-07).
- **Result CSVs are written by the scripts and never transcribed.** Paper
  tables are generated from them.
- **Every latency figure states its measurement host.**
- **Negative results are reported and analysed, never dropped.**
- **Run `python scripts/check_docs.py` before any documentation commit.** It
  also runs in CI.

## Licence

- **Code:** no licence has been granted yet. MIT is planned and will be
  applied only after the licence and third-party rights review. Keeping the
  repository private does not settle those rights.
- **Data:** per-source licences, recorded in `data/sources.json`. No corpus
  data is released.
- **Third-party material in the repository:** 37 lane-survey preview frames
  are committed, and every one has an unresolved licence (SAD §10). The
  Bellevue footage and the models derived from it are for internal
  engineering only until its licence is settled. The repository is private.
