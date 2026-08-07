# Software Requirements Specification (SRS)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | SRS v1.0 |
| **Date** | 2026-08-07 |
| **Standard** | Structured after IEEE 830, adapted for a research prototype |
| **Related** | [BRD](../00-planning/BRD.md) · [PRD](../00-planning/PRD.md) · [FRD](FRD.md) · [NFR](NFR.md) · [RTM](RTM.md) |

---

## 1. Introduction

### 1.1 Purpose

This SRS specifies the externally observable behaviour of the MFSTNet system: its actors,
interfaces, operating states, data contracts, and the scenarios it must handle. It is the reference
against which the design documents (Wave 2) and test documents (Wave 3) are written.

### 1.2 Scope and document boundaries

The suite divides responsibility deliberately, and this document stays inside its boundary:

| Document | Answers |
|---|---|
| [BRD](../00-planning/BRD.md) | *Why* — business need (BR-xx) |
| [PRD](../00-planning/PRD.md) | *What is built* — architecture, hyperparameters, milestones. **Authoritative for all numeric values** |
| **SRS** (this) | *How the system behaves* — actors, interfaces, states, scenarios, data contracts |
| [FRD](FRD.md) | *How each function is verified* — acceptance criteria per FR |
| [NFR](NFR.md) | *How each quality attribute is measured* |
| [RTM](RTM.md) | *Traceability* — BR → FR/NFR → DES → TC → M |

**Requirement IDs are defined once, in PRD §9 and §10.** This document cites them and never restates
them. Where a numeric value appears here, it is reproduced from the PRD for readability and the PRD
governs on any conflict.

### 1.3 Definitions

Glossary in PRD §24.1. Terms specific to this document:

| Term | Meaning |
|---|---|
| **Edge node** | The device running detection and local fallback control. Per PRD §15.4, a team laptop |
| **Server** | The host running the MQTT broker, FastAPI backend, PPO inference, and MFSTNet ONNX inference |
| **Lane** | One of four approaches: N, S, E, W |
| **Cycle** | One complete pass through the signal phases |
| **Preemption** | Emergency override of normal control |
| **Degraded mode** | Operation with one or more intelligent components unavailable, falling back per FR-A06 |
| **Sequence** | 60 frames at 5s intervals — one MFSTNet input (PRD §8.6) |

---

## 2. Overall description

### 2.1 System context

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │  EDGE NODE (laptop / Jetson)                                        │
   │    Camera ──▶ YOLOv8 ──▶ per-lane counts ──▶ emergency detector     │
   │                              │                                       │
   │    Signal panel ◀── local controller ◀── Webster fallback (armed)   │
   └──────────────────────────────┼───────────────────────────────────────┘
                                  │ MQTT (counts 5s · emergency on-event)
                                  │ MQTT (signal commands)
   ┌──────────────────────────────┼───────────────────────────────────────┐
   │  SERVER                      ▼                                       │
   │    Mosquitto broker ──▶ FastAPI backend                              │
   │                              │                                       │
   │           ┌──────────────────┼──────────────────┐                    │
   │           ▼                  ▼                  ▼                    │
   │      MFSTNet (ONNX)     PPO agent        TimescaleDB                 │
   │      congestion +       signal           history                     │
   │      gate value  ──────▶ decision                                    │
   └──────────────────────────────┼───────────────────────────────────────┘
                                  │ WebSocket
                                  ▼
                          React dashboard (4 pages)
```

**The coupling that spans components:** MFSTNet's output is not only a prediction, it is part of the
PPO state vector. PRD §13.1's 17-dimensional state includes four per-lane MFSTNet class predictions
plus `mfst_gate_mean`. Changing MFSTNet's output shape or normalisation invalidates every trained PPO
checkpoint. Any such change is a coordinated change across S3 and S4, not a local one.

### 2.2 Actors

| Actor | Type | Interacts via |
|---|---|---|
| Traffic operator | Human | Dashboard (FR-UI01–FR-UI10) |
| Emergency vehicle | External event | Detected by perception (FR-P03) |
| Vehicles / road users | External environment | Observed by camera |
| Researcher | Human | Training scripts, ablation harness, experiment records |
| Faculty guide / examiner | Human | Dashboard benchmark pages, repository, documentation |
| SUMO simulator | External system | TraCI (FR-S03) |

### 2.3 Operating modes

The system must be safely controlled in every mode. BR-12 makes this non-negotiable: a degraded
intersection is acceptable, an uncontrolled one is not.

| Mode | Entered when | Control source | Exit |
|---|---|---|---|
| **M-NORMAL** | All components healthy | PPO agent, informed by MFSTNet | — |
| **M-NO-PREDICT** | MFSTNet inference fails or exceeds its latency budget | PPO on raw counts; MFSTNet fields zeroed | MFSTNet recovers |
| **M-LOCAL** | MQTT silent >10s (FR-A06) | Webster controller embedded on the edge node | MQTT restored, then resync |
| **M-PREEMPT** | Emergency confirmed (FR-P04) | Preemption logic; overrides all others | Emergency lane cleared |
| **M-MANUAL** | Authenticated operator override (FR-UI09) | Operator | Operator releases |

**Precedence, highest first:** M-PREEMPT > M-MANUAL > M-LOCAL > M-NO-PREDICT > M-NORMAL.

Safety invariants hold in **every** mode, including M-MANUAL:

- Minimum green 10s, maximum green 90s (FR-A03)
- All-red clearance ≥3s between conflicting phases (FR-A04)
- No lane waits >180s without service (FR-R04 starvation penalty, BR-11)

### 2.4 Assumptions and dependencies

Recorded in [SOW §6 and §7](../00-planning/SOW.md#6-assumptions). Not duplicated.

---

## 3. External interfaces

### 3.1 MQTT — the cross-component contract

Reproduced from PRD §17.1. **QoS differs per topic and is part of the contract**, not a tuning
parameter. Edge, server, and dashboard are built by different owners in different weeks; a QoS
mismatch surfaces as intermittent loss during Week 17–19 integration, when there is no time to
diagnose it.

| Topic | QoS | Rate | Direction | Why this QoS |
|---|---|---|---|---|
| `stms/{id}/{lane}/vehicle_count` | 1 | 5s | Edge → Server | At-least-once; a lost count degrades the next decision |
| `stms/{id}/{lane}/emergency/detect` | **2** | On event | Edge → Server | Exactly-once. A duplicate triggers a spurious preemption; a loss risks a life |
| `stms/{id}/signal/command` | 1 | On decision | Server → Edge | At-least-once; commands are idempotent by phase+duration |
| `stms/{id}/congestion/prediction` | 0 | 5s | Server → Dashboard | Fire-and-forget; superseded every 5s, so a loss self-heals |
| `stms/{id}/system/heartbeat` | 0 | 10s | Edge → Server | Absence is the signal; delivery guarantees would defeat it |

Payload schemas are in PRD §17.1 and are normative. The prediction payload carries `gate_value` —
FR-UI05 and BR-07 depend on it, so it must be exposed by the MFSTNet forward pass and never discarded.

### 3.2 Camera interface

| Property | Value |
|---|---|
| Source | USB/integrated webcam, or looping video files for repeatable demos |
| Resolution | 640×640 model input (NFR-01); native capture downscaled |
| Lane assignment | Static region-of-interest polygons, configured per deployment |
| Frame budget | ≥10 fps sustained (NFR-01) |

### 3.3 Dashboard ⇄ Backend

| Property | Value |
|---|---|
| Transport | Native WebSocket for live state; REST for history and exports |
| Refresh | ≤2s (NFR-05) |
| Auth | JWT, 24h expiry (NFR-12) |
| Reconnect | Automatic with backoff; stale data visibly marked, never silently shown as live |

### 3.4 SUMO ⇄ RL agent

TraCI (FR-S03). All four control methods run in the same environment (FR-S04) so comparisons are
paired — the same seed produces the same demand for every method, which is what makes the paired
t-test in FR-R08 valid.

---

## 4. System features

Each feature groups related FRs. Verification criteria are in the [FRD](FRD.md); this section states
behaviour.

### SF-1 — Perception (FR-P01–FR-P04, FR-D08)

The edge node detects and classifies vehicles per lane at ≥10 fps, maintaining a per-lane count
updated every frame and published every 5 seconds.

Emergency detection requires confidence ≥0.75 **and** ≥2 consecutive detections (FR-P04). The
conjunction exists because a single high-confidence frame is not evidence — reflections, livery, and
partial occlusion produce isolated false positives, and a spurious preemption costs every other
approach its green.

### SF-2 — Congestion prediction (FR-M01–FR-M14)

Given 60 frames spanning 5 minutes, MFSTNet emits per-lane congestion in {LOW, MEDIUM, HIGH} for
t+60s, plus the gate value and the PPO state embedding.

**The gate is an output, not an internal.** BR-07, FR-M04, and FR-UI05 all depend on it being
returned from the forward pass, logged per inference, and published on the prediction topic.

**Every module must be disableable by config flag.** The ablation study (PRD §14.4, configs A–G) is
what makes the work publishable, so ablation-ability is an architectural requirement, not a testing
convenience. A module that cannot be switched off cannot be ablated.

### SF-3 — Signal control (FR-R01–FR-R08, FR-A01–FR-A06)

The PPO agent selects a phase and green duration from 12 discrete actions each decision point,
using the 17-dimensional state in PRD §13.1.

Constraints that bind regardless of what the policy prefers: minimum green 10s, maximum 90s
(FR-A03), all-red ≥3s (FR-A04), no lane starved beyond 180s (FR-R04). These are enforced by the
environment and the actuation layer, **not** left to the reward function to discover — a reward
penalty makes starvation expensive, but only a hard constraint makes it impossible.

### SF-4 — Emergency preemption (FR-P03, FR-P04, FR-A05)

On confirmed detection, the emergency lane receives green within 3 seconds, subject only to the
all-red clearance interval. Preemption overrides PPO and manual control alike. Normal control resumes
once the emergency lane is clear.

### SF-5 — Degraded operation (FR-A06)

Two fallbacks are **required behaviour, not resilience nice-to-haves**:

- MFSTNet unavailable → PPO continues on raw counts, MFSTNet state fields zeroed, and the dashboard
  shows prediction as unavailable rather than stale.
- MQTT silent >10s → the edge node switches to its locally embedded Webster controller within 10
  seconds. Webster must therefore be present on the edge node at all times, not fetched on demand.

### SF-6 — Dashboard (FR-UI01–FR-UI10)

Four pages: Live (state, counts, predictions, emergency banner), Analytics (history, prediction
accuracy, gate tracker), Benchmark (RL statistical results, MFSTNet ablation), Event log.

The Benchmark page is not decoration — it is how an examiner inspects results without reading code,
and it is where FR-UI06 and FR-UI07 surface the evidence behind BR-13 and BR-06.

### SF-7 — Experiment reproducibility (NFR-07–NFR-10)

Every training or evaluation run fixes seeds across PyTorch, NumPy, and SB3 (PRD uses 42), records
its configuration, and writes raw per-run results as CSV. Aggregate tables are derived from committed
CSVs, never hand-entered — a summary that cannot be recomputed from raw data is not evidence.

---

## 5. Data requirements

| Store | Content | Retention | Notes |
|---|---|---|---|
| TimescaleDB | Counts, predictions, signal events, gate values | Project duration | Time-series; powers FR-UI03–FR-UI08 |
| Training corpus | Auto-labelled sequences (PRD §8.6) | Project duration | **Local only.** Excluded by `.gitignore`, never published (NFR-13) |
| IndiaTrafficNet | Annotated frames | Permanent, public | CC BY 4.0 on Roboflow Universe + Kaggle (FR-D06) |
| Model weights | `.pt`, `.onnx`, PPO `.zip` | Permanent | Git LFS |
| Experiment results | Per-run CSVs | Permanent | Plain git, explicitly un-ignored (NFR-09, NFR-10) |

**Split discipline.** Detection uses 70/15/15 stratified (FR-D05). MFSTNet uses 60/20/20 (PRD §8.4)
**cut by source clip, not by sequence** — overlapping windows from one clip appearing in both train
and test would leak, and PRD §2.5.1 lists exactly this as a Week 11–12 failure. Different numbers,
different units, different purposes. Confusing them silently corrupts every reported result.

---

## 6. Non-functional requirements

Specified in [NFR.md](NFR.md) with measurement procedures. Summary of budgets (PRD §10):

| Concern | Budget |
|---|---|
| Detection throughput | ≥10 fps |
| MFSTNet inference | ≤150 ms (server CPU, ONNX) |
| PPO decision | ≤50 ms |
| MQTT end-to-end | ≤200 ms |
| Dashboard refresh | ≤2 s |
| Prototype uptime | ≥95% over 4 hours |

These compose. A sensing-to-actuation round trip is bounded by roughly 500 ms, which PRD §20 L6
accepts as immaterial against 10–90 s signal cycles.

---

## 7. Constraints

Per [SOW §7](../00-planning/SOW.md#7-constraints). The two that most shape design:

**Build order (C4, PRD §2.4).** Phase 1 — CNN + ViT + *standard* cross-attention + BiLSTM — must
train cleanly before gating or temporal attention is implemented. This is a requirement on the order
of work, and it exists to prevent the failure mode §2.5.4 describes.

**Zero budget (C2).** No component may require paid infrastructure to satisfy a Must-priority
requirement.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial SRS aligned to PRD v1.1 |
