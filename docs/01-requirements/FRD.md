# Functional Requirements Document (FRD)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | FRD v1.0 |
| **Date** | 2026-08-07 |
| **Related** | [PRD §9](../00-planning/PRD.md) (requirement source) · [SRS](SRS.md) · [NFR](NFR.md) · [RTM](RTM.md) |

---

## 1. Purpose

PRD §9 states *what* each functional requirement is, in one line. This document states **how each one
is verified** — the acceptance criterion, the verification method, and the test case that will
exercise it.

The distinction matters because "SHALL detect vehicles per lane" is not testable as written. "Counts
are within ±10% of manual counts on a 200-frame held-out set" is. Requirements that cannot be
verified cannot be claimed as delivered, and PRD §2.5.2 identifies unmeasurable claims as the first
thing a faculty guide checks.

**Requirement text is not restated here.** IDs reference PRD §9, which is authoritative.

## 2. Verification methods

| Code | Method | Meaning |
|---|---|---|
| **T** | Test | Automated or scripted execution producing a pass/fail result |
| **D** | Demonstration | Observed live operation against a criterion |
| **A** | Analysis | Computation, statistical test, or reasoning over collected data |
| **I** | Inspection | Review of code, configuration, document, or artifact |

Test case IDs (`TC-*`) are defined in the [STD](../03-testing/), delivered in Wave 3
(~Week 11). IDs are reserved here so the RTM is complete from Wave 1.

---

## 3. Dataset and detection — FR-D01 to FR-D09

> **✅ A13 IN FORCE from 2026-08-13.** The criteria in the table below are **superseded** by this
> banner ([ADR-006](../00-planning/decisions/ADR-006-curate-then-collect-dataset.md)); the original
> rows are retained for the trail. RTM rows for BR-01/BR-03/BR-04 re-checked.
>
> | ID | Would become |
> |---|---|
> | FR-D01 | ≥3 documented public sources with verified licences (Part A) **+ ≥60 continuous sessions of ≥6 min** from ≥1 permissioned location (Part B) |
> | FR-D02 | Peak and off-peak coverage in Part B; source diversity documented for Part A |
> | FR-D03 | Unchanged — 8 classes, plus a documented mapping from each source taxonomy |
> | FR-D04 | Part A: harmonised benchmark published. Part B: **≥1,500** frames |
> | FR-D05 | Unchanged — 70/15/15 stratified, applied to both parts |
> | FR-D06 | Part A: images where licences permit, else conversion scripts + manifest. Part B: CC BY 4.0, **anonymised** |
> | FR-D07 | Additionally: per-source licence table, blurring method, consent basis, residual risk |
>
> The rows below are historical. Verify against this banner.

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-D01 | Raw footage exists from ≥6 distinct intersections, each with GPS coordinates and a capture log recorded in the datasheet | I | TC-D01 | R1 | M1 |
| FR-D02 | Capture log shows ≥1 peak session (08–10 or 17–20) **and** ≥1 off-peak session (14–16) per intersection | I | TC-D02 | R1 | M1 |
| FR-D03 | Roboflow project contains exactly the 8 classes in PRD §12.2; no extra or merged classes | I | TC-D03 | R1 | M1 |
| FR-D04 | Annotated frame count ≥12,000, verified from Roboflow dataset statistics | I | TC-D04 | R1 | M1 |
| FR-D05 | Split is 70/15/15; per-class proportion in each split is within ±2 percentage points of the whole | T | TC-D05 | R1 | M1 |
| FR-D06 | Dataset resolves at a public Roboflow Universe URL **and** a public Kaggle URL, both showing CC BY 4.0, both openable in a logged-out browser | D | TC-D06 | R1 | M1 |
| FR-D07 | Datasheet exists covering collection conditions, times of day, weather, camera height/angle, class counts, and known biases — explicitly including the absence of night and adverse weather (PRD §20 L3) | I | TC-D07 | R1 | M1 |
| FR-D08 | `detection_map.csv` committed with mAP@50 and mAP@50:95 per class, plus sample count per class (PRD §20 L7 requires the count beside the metric) | T | TC-D08 | R1 | M2 |
| FR-D09 | Same test set evaluated under both COCO-pretrained and IndiaTrafficNet-fine-tuned weights. Criterion: **≥10% overall mAP gain on Indian classes and ≥25% on auto-rickshaw** | A | TC-D09 | R1 | M2 |

**FR-D09 note.** ADR-001 adds a third condition — public-bootstrap weights — giving a three-way
comparison. Reporting all three strengthens the claim; only the COCO comparison is required by M2.

---

## 4. Simulation — FR-S01 to FR-S04

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-S01 | SUMO network file loads without error and renders a 4-way intersection with ≥2 lanes per approach | D | TC-S01 | R3 | M3 |
| FR-S02 | Simulated per-lane arrival rates match IndiaTrafficNet-derived counts within ±15%, shown in a committed calibration report | A | TC-S02 | R3 | M3 |
| FR-S03 | A TraCI script reads per-lane count, queue, phase, and phase-remaining, and sets a phase, in one episode without error | T | TC-S03 | R3 | M3 |
| FR-S04 | All four methods (Fixed, Webster, Random, PPO) run in the **same** network file with the **same** demand for a given seed | T | TC-S04 | R3 | M3 |

**FR-S04 is the precondition for FR-R08.** The paired t-test is only valid if each method faces
identical demand per seed. If the environments diverge, the statistics are invalid and M7 fails —
verify this before running 120 evaluation episodes, not after.

---

## 5. Reinforcement learning — FR-R01 to FR-R08

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-R01 | PPO instantiated from Stable-Baselines3 with the exact hyperparameters in PRD §13.1, loaded from `simulation/configs/ppo_config.yaml`, not hardcoded | I | TC-R01 | R3 | M6 |
| FR-R02 | `observation_space` is `Box(shape=(16,))` — *v1.2 A16, was 17*; a printed sample matches the field order in PRD §13.1 exactly | T | TC-R02 | R3 | M6 |
| FR-R03 | `action_space` is `Discrete(12)`; each index maps to one (phase, duration) pair from {NS,EW} × {10,20,30,45,60,90} | T | TC-R03 | R3 | M6 |
| FR-R04 | Reward implementation reproduces PRD §13.1 exactly. Unit test: a lane held >180s produces a starvation penalty; a cleared emergency produces +10.0 | T | TC-R04 | R3 | M6 |
| FR-R05 | TensorBoard shows ≥500,000 timesteps; reward curve visibly plateaus over the final 100K | A | TC-R05 | R3 | M6 |
| FR-R06 | `rl_runs.csv` contains ≥120 rows — 30 seeds × 4 methods — with seed, method, and all five metrics from PRD §13.2 | T | TC-R06 | R3 | M7 |
| FR-R07 | Per method per metric: mean, std, and bootstrap 95% CI (10,000 resamples) computed from the committed CSV by a committed script | A | TC-R07 | R3 | M7 |
| FR-R08 | Paired t-test PPO vs Fixed and PPO vs Webster at α=0.05, with Cohen's d. Criterion: **≥20% mean wait reduction vs Fixed and ≥10% vs Webster, both p<0.05** | A | TC-R08 | R3 | M7 |

**FR-R08 note.** If the criterion is not met, the result is reported honestly and analysed
(BR-19, PRD §2.5.5 and R7). A well-analysed negative result is publishable; a quietly dropped one
fails the project. Do not tune until the test passes and then report only the passing run — that is
the same error, disguised.

---

## 6. MFSTNet — FR-M01 to FR-M14

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-M01 | ResNet-50 loads ImageNet weights; a forward pass on `[2,3,224,224]` returns `[2,N_c,256]`; backbone params have `requires_grad=False` before epoch 30 | T | TC-M01 | R2 | M4 |
| FR-M02 | ViT-Small/16 loads via timm; forward pass returns `[2,N_v,256]`; frozen as above | T | TC-M02 | R2 | M4 |
| FR-M03 | Both cross-attention directions computed; `Z_A` and `Z_B` differ on a non-degenerate input (asserted, not assumed) | T | TC-M03 | R2 | M4 |
| FR-M04 | Gate computed per PRD §8.1. Gate value **returned from `forward()`**, not only logged internally. Test asserts `0 < g < 1` and that its histogram is not collapsed to 0 or 1 (PRD R5) | T | TC-M04 | R2 | M5 |
| FR-M05 | BiLSTM is 2 layers, hidden 128, bidirectional; output `[B,60,256]` | T | TC-M05 | R2 | M4 |
| FR-M06 | Temporal self-attention, 2 layers, 4 heads, with sinusoidal positional encoding; disableable by config flag | T | TC-M06 | R2 | M5 |
| FR-M07 | Attention pooling over all 60 timesteps; weights sum to 1.0 ±1e-5; disableable by config flag | T | TC-M07 | R2 | M5 |
| FR-M08 | Output shape `[B,4,3]`; argmax maps to LOW/MEDIUM/HIGH per lane at t+60s | T | TC-M08 | R2 | M4 |
| FR-M09 | Every baseline in PRD §14.3 evaluated on the identical test split; results in one committed CSV | A | TC-M09 | R2 | M5 |
| FR-M10 | All 7 ablation configs A–G in `ablation.csv`, each with its config hash and seed. **All configs reported, including those that do not help** (BR-19) | A | TC-M10 | R2 | M5 |
| FR-M11 | Per config: accuracy, macro F1, per-class precision/recall, latency. Criterion for M5: **macro F1 ≥ 0.80** on config G (or the best completed config, stated as such) | A | TC-M11 | R2 | M5 |
| FR-M12 | ONNX export loads in ONNX Runtime and produces outputs matching PyTorch within 1e-4 | T | TC-M12 | R2 | M5 |
| FR-M13 | Measured ONNX latency ≤150 ms on server CPU, median of 100 runs, measurement host recorded | T | TC-M13 | R2 | M5 |
| FR-M14 | PPO state vector contains the 4 lane predictions at indices 11–14 in PRD §13.1 order; an integration test asserts the contract. `mfst_gate_mean` is **not** in the state (A16). Zeroing 11–14 when MFSTNet is unavailable is asserted separately | T | TC-M14 | R2/R3 | M10 |

**Ablation-ability is an architectural requirement.** FR-M06, FR-M07, and the config A–G matrix all
require modules to be switchable by config flag. A module wired in unconditionally cannot be ablated,
and the ablation table is what makes this work publishable (PRD §2.5.3). Design for this from the
first commit, not retroactively.

**FR-M14 is the highest-risk interface in the system.** Changing MFSTNet's output shape or
normalisation silently invalidates every trained PPO checkpoint. The contract test exists to make
that failure loud.

---

## 7. Perception pipeline — FR-P01 to FR-P04

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-P01 | Sustained ≥10 fps over 60 s at 640×640, **with the measurement host recorded** (PRD §15.4 — laptop figures are proxy measurements) | T | TC-P01 | R4 | M8 |
| FR-P02 | Per-lane counts within ±10% of manual counts on a 200-frame held-out set | A | TC-P02 | R1/R4 | M8 |
| FR-P03 | An emergency vehicle in test footage raises the emergency event on the MQTT topic | D | TC-P03 | R4 | M8 |
| FR-P04 | Single frame at confidence 0.9 does **not** trigger; two consecutive frames ≥0.75 **do**. Both directions tested — the negative case is the one that matters | T | TC-P04 | R4 | M8 |

---

## 8. Signal control and actuation — FR-A01 to FR-A06

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-A01 | Server consumes live counts and MFSTNet predictions and publishes a signal command within the PPO decision budget | D | TC-A01 | R3/R4 | M10 |
| FR-A02 | Command published on `stms/{id}/signal/command` at QoS 1 and acted on by the edge node | T | TC-A02 | R4 | M10 |
| FR-A03 | No green shorter than 10 s or longer than 90 s across a 1-hour run — asserted over the event log, not sampled | T | TC-A03 | R4 | M10 |
| FR-A04 | All-red ≥3 s between every conflicting phase transition in the same log | T | TC-A04 | R4 | M10 |
| FR-A05 | Emergency lane green within 3 s of confirmed detection, **10 out of 10 trials** | D | TC-A05 | R4 | M8 |
| FR-A06 | Two fallbacks, each tested by fault injection: (a) MFSTNet killed → PPO continues on raw counts, dashboard marks prediction unavailable; (b) broker stopped → edge switches to Webster within 10 s and keeps controlling | T | TC-A06 | R4 | M10 |

**FR-A03 and FR-A04 are enforced constraints, not learned behaviour.** The actuation layer rejects
any command violating them, whatever the policy emits. A reward penalty makes a violation expensive;
only a hard constraint makes it impossible, and BR-11/BR-12 require impossible.

**FR-A06 is required behaviour, not resilience polish.** Webster must be resident on the edge node at
all times — a fallback fetched over the network when the network has failed is not a fallback.

---

## 9. Dashboard — FR-UI01 to FR-UI10

| ID | Acceptance criterion | Method | TC | Owner | Milestone |
|---|---|---|---|---|---|
| FR-UI01 | Live page shows signal state, count, and predicted congestion for all 4 lanes, refreshing ≤2 s | D | TC-UI01 | R4 | M9 |
| FR-UI02 | Emergency banner appears within one refresh of preemption and clears when it ends | D | TC-UI02 | R4 | M9 |
| FR-UI03 | Analytics page renders 1 h / 6 h / 24 h count history from TimescaleDB | D | TC-UI03 | R4 | M9 |
| FR-UI04 | Prediction accuracy tracker compares each t+60s prediction against the count actually observed at that time | A | TC-UI04 | R4 | M9 |
| FR-UI05 | Gate value plotted over time, labelled so a reader can tell CNN-reliance from ViT-reliance (BR-07) | D | TC-UI05 | R4 | M9 |
| FR-UI06 | Benchmark page renders the RL results table with 95% CI for all 4 methods, read from the committed CSV | D | TC-UI06 | R4 | M9 |
| FR-UI07 | Benchmark page renders the ablation table for configs A–G, read from the committed CSV | D | TC-UI07 | R4 | M9 |
| FR-UI08 | Event log lists every signal event with timestamp and source (`ppo_agent`, `webster_fallback`, `emergency`, `manual`) | D | TC-UI08 | R4 | M9 |
| FR-UI09 | Authenticated operator can override; override is logged with the operator identity; safety invariants still enforced | T | TC-UI09 | R4 | M9 |
| FR-UI10 | Analytics data exports as CSV | D | TC-UI10 | R4 | M9 |

**FR-UI06 and FR-UI07 read from the committed result CSVs.** Values are never hardcoded into the
frontend. This is what makes the dashboard evidence rather than illustration — and it means a
regenerated result updates the dashboard automatically.

---

## 10. Priority summary

Per PRD §9. Conditional-scope items (SOW §2.3) are marked.

| Priority | Count | IDs |
|---|---|---|
| Must Have | 51 | All except those below |
| Should Have | 3 | FR-M06 †, FR-M07 †, FR-UI09 |
| Could Have | 1 | FR-UI10 |
| **Total** | **55** | D:9 · S:4 · R:8 · M:14 · P:4 · A:6 · UI:10 |

† Phase 2 per PRD §2.4 — attempted only after Phase 1 trains cleanly. FR-M04 (gating) is marked Must
Have in PRD §9 but is Phase 2 in §2.4. **§2.4 governs the order of work.** If Phase 2 is not reached,
FR-M04, FR-M06, and FR-M07 are formally descoped and reported as future work (BRD §6) rather than
left silently unmet.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial FRD. Acceptance criteria and TC IDs assigned for all 55 functional requirements |
