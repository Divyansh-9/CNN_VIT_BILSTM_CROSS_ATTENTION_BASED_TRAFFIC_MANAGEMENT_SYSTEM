# Software Architecture Document (SAD)

| | |
|---|---|
| **Wave** | 2 (ADR-004) |
| **Status** | **Approved** by the owner's review, 2026-10-21 (accepted for HLD review, then for integration). **Corrected 2026-10-22** (PRD-CHANGELOG D8): §4.2's consumers and §6.2's server heartbeat |
| **Describes** | The system as built at commit `1967e55`, 2026-10-18 |
| **Authority** | The [PRD](../00-planning/PRD.md) for requirements, and the ADRs for every amendment. This document describes; it does not decide |
| **Audience** | The faculty guide, examiners, and team members who need the whole system in one document before reading any one subsystem |

> **What this system does not do:**
> - **No component connects to real signal hardware.**
> - **No forecast-assisted controller runs in the live edge-to-server path.**
>   The server's command endpoint proposes phases with a placeholder rule, not
>   the trained policy (§6.3).
> - **Forecast-assisted control exists only as evaluated simulation arms.**
>   PPO with a forecast in its state was trained and evaluated in SUMO. Under
>   the tested protocol it did not reduce delay compared with the tested
>   Webster baselines (P130).
> - **The vision claim C2 and the Indian-domain claim are open.** The claims
>   gate reports `domain` and `class_coverage` as red.

---

## 1. Purpose and scope

This document gives the architecture of the four subsystems the PRD defines:
- the detection and corpus pipeline;
- MFSTNet;
- the PPO controller in simulation;
- the edge-to-server prototype.

It also covers the contracts that join them.

**In scope:**
- the decomposition into subsystems;
- the runtime and offline data flows;
- the deployment topology;
- the cross-component contracts;
- the quality attributes and how each is achieved;
- the known limitations.

**Out of scope:**
- **Class and function detail:** the LLD.
- **Module-level design per subsystem:** the HLD. One HLD exists already,
  [HLD — Detection & Corpus Pipeline](HLD-detection-corpus-pipeline.md).
- **Requirements:** the [SRS](../01-requirements/SRS.md),
  [FRD](../01-requirements/FRD.md) and [NFR](../01-requirements/NFR.md).

---

## 2. Architectural drivers

These drivers shaped the structure. Each names its source.

| Driver | Source | Architectural consequence |
|---|---|---|
| **The deployed runtime neither transmits raw frames over the network nor stores them on disk** | NFR-13, which by its own text covers the deployed runtime and not the offline training corpus | The model that consumes frames runs on the edge (ADR-026). **Raw video frames do not cross the deployed runtime's network boundary.** Structured messages do, under the MQTT and HTTP contracts: counts, forecasts, emergency detections, heartbeats, and (defined though not yet published) signal commands. No endpoint, table column or payload field is designed to carry an image, and every inbound payload is capped at 4,096 bytes before parsing. Schema v2 aims to admit no free text, but at `1967e55` that is not enforced (§4.2). Unchecked payload fields are addressed by P141; the uncapped intersection id and the framework's echoes by P142. Both were applied in the 2026-10-21 batch. The live-capture tool has a separately gated recording mode, outside the normal runtime path (§8) |
| **₹0 cash budget** | Project constraint | The edge is a team laptop, not a Jetson (ADR-003). The database is SQLite (ADR-008). Training is local on cached features (ADR-005) |
| **Fallbacks are required behaviour** | FR-A06, PRD §7.2 | Three separate timeouts, each 10 s (§6.2): the edge link, the server heartbeat, and forecast freshness in simulation |
| **Safety limits are enforced, not learned** | FR-A03, FR-A04 | `server/safety.py` holds the limits with no transport code in it. The simulation runner applies the same limits |
| **Every module can be disabled by config** | NFR-15, NFR-16 | The A–H ablation runs from YAML alone, and hyperparameters live in `mfstnet/configs/` and `simulation/configs/` |
| **Reproducible from committed artifacts** | NFR-07 to NFR-10 | Seeds are fixed through one utility. Result CSVs are written by the scripts. Provenance sidecars and SHA-256 locks are kept. CI asserts the simulation versions (P137) |
| **The forecast is part of the controller's state** | PRD §13.1, ADR-020 | The 17-dim state is a versioned contract. Its layout is hashed into every PPO checkpoint sidecar |

---

## 3. System decomposition

| Subsystem | Code | Purpose | Status at `1967e55` |
|---|---|---|---|
| **Detection & corpus pipeline** | `mfstnet/corpus/`, `scripts/build_corpus.py` and the related scripts | Video → YOLOv8 per-lane counts → PCU-weighted congestion labels → leave-one-camera-out folds | Built. The detection dataset (S19) awaits the guide's decision on MEMO-2026-08-22, which asks for a six-viewpoint evaluation set. That is a scope decision, not a technical blocker |
| **MFSTNet** | `mfstnet/` (`encoders`, `fusion`, `temporal`, `model`, `cache`, `preprocess`, `metrics`) | Frozen ResNet-50 + DINOv2 features → gated bidirectional cross-attention → BiLSTM → temporal attention → per-lane ROI pooling → LOW/MEDIUM/HIGH at t+60 s | Built; the A–H ablation has been evaluated under LOCO. The vision claim C2 is open |
| **Simulation & control** | `simulation/`, `scripts/train_ppo.py`, `scripts/benchmark.py` | The SUMO intersection, the PPO environment, Webster, the fixed and longest-queue baselines, and the forecast gate | Built, and **simulation only**. The forecast-for-control line closed with a null (P130) |
| **Edge node** | `edge/` | Counts from video, the two forecasting roles, MQTT publishing, and the FR-A06 fallback | Built. The real-camera run (S65) is pending |
| **Contracts** | `contracts/mqtt.py` | Every topic and payload, with QoS bound to the topic | Built; schema v2 |
| **Server** | `server/app.py`, `server/safety.py`, `server/mqtt_ingest.py` | Validates and stores forecasts, serves evidence, and runs the guarded command endpoint | Built, as a prototype (§6.3) |
| **Dashboard** | `dashboard/` (React 18 + Vite) | Read-only display of the live forecasts and the committed evidence | Built (`1102932`). GET only |

---

## 4. Context and runtime view

### 4.1 The live path

```
   ┌──────────────────────── edge laptop (ADR-003, ADR-026) ───────────────────────┐
   │ camera/clip ─▶ YOLOv8 ─▶ per-lane counts ─┬─▶ PersistenceForecaster (class)    │
   │  frames in memory only (NFR-13)           ├─▶ RidgeCountForecaster  (count)    │
   │                                           └─▶ EdgeNode.tick ─▶ heartbeat       │
   │ EdgeForecaster (MFSTNet ONNX, VerifiedGraph) — built and verified; holds no    │
   │ ADR-027 role                                                                    │
   │ FR-A06: no successful publish for > 10 s ─▶ fixed 30 s alternating cycle        │
   │         (class named LocalWebster; no Webster computation)                      │
   └───────────────────────────────┬─────────────────────────────────────────────────┘
                                   │ MQTT (Mosquitto), contracts/mqtt.py, schema v2
                                   ▼
   ┌──────────────────────────── server ─────────────────────────────────────────────┐
   │ server/mqtt_ingest.py ─▶ store_prediction / store_count_forecast ─▶ SQLite        │
   │ FastAPI server/app.py: GET /prediction/{id}/latest|history,                       │
   │                        /count_forecast/{id}/latest|history,                       │
   │                        /evidence, /history/{id}, /health                          │
   │                        POST /observation (placeholder rule + SignalGuard, §6.3)   │
   │   └─ PROTOTYPE ONLY: called by tests, by no runtime component. Its command is   │
   │      returned in the HTTP response and forwarded nowhere: no MQTT publish, no   │
   │      edge, no hardware                                                          │
   └───────────────────────────────┬─────────────────────────────────────────────────┘
                                   │ HTTP GET, polled every 2 s
                                   ▼
                     dashboard (read-only; live and evidence panels kept apart, ADR-014)
```

### 4.2 MQTT topics

They are defined only in `contracts/mqtt.py`. A caller cannot pass its own
QoS.

| Topic | QoS | Publisher → consumer |
|---|---|---|
| `stms/{id}/{lane}/vehicle_count` | 1 | **Published by the edge; no server component subscribes to it.** The ingest takes the two forecast topics only (HLD §9-C4) |
| `stms/{id}/{lane}/emergency/detect` | 2 | **Defined, but nothing outside the tests publishes or subscribes to it** |
| `stms/{id}/signal/command` | 1 | **Defined, but nothing outside the tests publishes it**; the edge does not subscribe to it. It is reserved for the server → edge command path, which is not built |
| `stms/{id}/congestion/prediction` | 0 | edge → server (the class role) |
| `stms/{id}/count/forecast` | 0 | edge → server (the count role, ADR-027) |
| `stms/{id}/system/heartbeat` | 0 | **Published by the edge; no server component subscribes to it.** The edge's mode, including `LOCAL`, is therefore visible only in the edge's own log, not on the server or the dashboard |

**Schema v2 (ADR-026)** has the following rules:
- **its stated aim is that no free text crosses the edge boundary;**
- the model id is a constrained pattern;
- prediction keys are approaches;
- the emergency type is a closed set;
- `gate_value` may be null;
- every inbound payload is capped at 4,096 bytes before parsing.

**The aim is not enforced at `1967e55`.** The channels below are open there,
The integration batch of 2026-10-21 (P140, P141, P142), committed with
this document, closes them as the table says.

| Channel at `1967e55` | What happens | Addressed by |
|---|---|---|
| **Payload fields** | `confidences`, `horizon_sec` and `ts` are not type-checked in a `CongestionPrediction`, nor `ts` in a `CountForecast`. A string in any of them is accepted and stored, up to the 4,096-byte cap. `ts` also accepts a ~300-digit integer | **P141.** It types and bounds every field of both payloads |
| **Contract refusal messages** | They echo submitted values into the HTTP 422 body | **P141.** Refusals name only the field and the rule |
| **The intersection id** | It comes from the URL path, the MQTT topic level or the `/observation` body. It is stored, echoed and logged, and **the payload cap does not apply to it**: a 48,000-character id was stored in a test | **P142.** One closed pattern, `[A-Za-z0-9_-]{1,32}`, checked wherever an id enters, including at the edge |
| **Framework echoes** | Starlette's trailing-slash redirect repeats the path, the query and `Host` in a `Location` header. FastAPI's 422 quotes input. uvicorn's access log records refused paths and queries. The 404s quote the id | **P142.** Redirects off; one non-echoing 422 handler; fixed 404 text; and an access-log filter:<br>• a path is logged only when it matches an API route **and** every path parameter is an id passing the contract's rule;<br>• a static-mount path is logged as `/dashboard/<static>`;<br>• a query becomes `?<query>`;<br>• anything else becomes a placeholder.<br>Verified on formatted log lines and under real uvicorn with a built `dist` |
| **`/observation` fields** | Counts are any 64-bit integer, and the heartbeat age is unbounded. A `NaN` age skips the FR-A06 fallback. The emergency approach is free text | **P142.** Counts 0 to 10,000; ages finite and capped; approaches closed |

**What remains after all three, by design.** These are stated rather than
claimed away:
- **A valid id is still a small channel.** It is stored and echoed, about 24
  chosen bytes per message. Only a registry of known intersections would
  close it.
- **Numeric fields carry a few bytes each** through the precision of their
  digits. That is inherent in any numeric field.

**On the server,** `server/mqtt_ingest.py` subscribes to the two forecast
topics. It routes each message through the same store function as the HTTP
endpoint, so a payload refused over HTTP is refused over MQTT too, and a
refused payload's content is never logged.

### 4.3 Two count representations on the edge (D1)

| Count | Built from | Used by | Bicycles |
|---|---|---|---|
| **Forecaster input** | the detector's raw per-lane totals | `PersistenceForecaster`, `RidgeCountForecaster` | **included**: the corpus counted them, and the frozen specs were calibrated on them |
| **Contract count** (`vehicle_count`) | the per-class breakdown, mapped through `class_mapping.yaml` `itd_mapping` (`edge/classes.py`) | the MQTT `vehicle_count` topic; the server does not ingest it | **excluded**: not in the §12.2 taxonomy |

The two counts are kept apart on purpose:
- **Never feed the forecasters the contract count.** It would move their input
  away from their calibration, with no visible sign in their output.
- **Never publish the raw totals as a contract count.**

At NE8th the two differ mostly by the painted bicycle-lane symbol P95
documented: 224 detections in 300 samples in the Phase C run.

### 4.4 The two forecasting roles (ADR-027)

| Role | Implementation | Output | Feeds signal timing? |
|---|---|---|---|
| **Congestion class** | `edge/persistence.py` (`PersistenceForecaster`) | LOW, MEDIUM or HIGH per approach | **No** |
| **Next-minute count** | `edge/count_forecast.py` (`RidgeCountForecaster`), level-free ridge | A count per approach | **No** |

**MFSTNet on the edge** is `edge/forecaster.py` (`EdgeForecaster`). It serves
only a graph whose sidecar records a passed verification and whose bytes still
hash to the verified value. It is built and verified, and it holds neither
role.

---

## 5. Offline and research view

### 5.1 Corpus → model

```
clips ─▶ triage ─▶ survey + hand-placed lanes (P23) ─▶ build_corpus (counts.csv)
      ─▶ relabel (PCU thresholds, ADR-017) ─▶ audit ─▶ build_cache (frozen features, fp16)
      ─▶ resplit (leave-one-camera-out, ADR-019) ─▶ train_mfstnet / run_loco (A–H × 5 seeds)
      ─▶ select_checkpoint (validation only) ─▶ export_checkpoint (ONNX, proven) ─▶ edge
```

- **Labels are derived from counts.** `counts.csv` does not depend on the
  threshold, so relabelling and resplitting take seconds and need no new
  detector run.
- **The feature cache is invalidated by any change to the backbone, the
  resize or the normalisation.** `preprocessing_hash` is asserted on load
  (ADR-005).

### 5.2 Simulation and control

```
build_sumo_network / build_sumo_demand / scenarios.yaml (pulsed)
   ─▶ TrafficSignalEnv (Gymnasium, sublane 0.8) ─▶ train_ppo (arms: no-forecast | surrogate | mfstnet)
   ─▶ run_episode (simulation/runner.py, identical harness rules, P120)
   ─▶ benchmark / ceiling_eval ─▶ committed CSV + statistics (bootstrap CI, paired t, Cohen's d, Holm)
```

- **The training and evaluation harnesses produced identical decision traces
  in the P120 equivalence check** (`simulation/equivalence.py`). With the real
  no-forecast checkpoint on full 1,800 s episodes in four regimes, time,
  phase, counts and every element of the observation matched at every
  decision. That is trace equivalence under the tested setup, not a general
  proof.
- **The forecast is supplied during training by a producer:** `NoForecast`,
  or `Surrogate(q)`, which mixes a replay oracle with persistence (P115).
- **Every checkpoint carries a provenance sidecar.** Pre-registered runs are
  additionally locked by SHA-256.

---

## 6. Cross-component contracts

### 6.1 The PPO state vector: 17 dimensions

The layout is defined once, in `mfstnet/configs/spec.yaml`.

| Index | Field |
|---|---|
| 0–3 | count per approach (÷ 50) |
| 4–7 | queue per approach (÷ 200) |
| 8–9 | phase one-hot |
| 10 | phase remaining (÷ 90) |
| 11–14 | class forecast per approach: 1/3, 2/3 or 1; **0.0 is reserved for "no forecast"** |
| 15 | emergency flag |
| 16 | forecast age, capped at 10 s |

**Encoding.** Indices 11–14 and 16 are written only by
`forecast_slots()` in `simulation/forecast_state.py`, following the spec's
`forecast_unavailable` block.

| Situation | Indices 11–14 | Index 16 |
|---|---|---|
| No forecast message | all 0.0 (reserved: absent) | 1.0 |
| A message, but an approach missing | 0.0 for that approach; the class value for the others | `min(age, 10) / 10` |
| A message, but an approach holding a string that is not LOW, MEDIUM or HIGH | the same as a missing approach: 0.0 for it | `min(age, 10) / 10` |
| A complete message | 1/3, 2/3 or 1 per approach | `min(age, 10) / 10` |

No class can map to 0.0; `forecast_slots` raises if the spec allowed it. A
message whose age is not finite and non-negative is refused rather than
encoded.

**Missing approach and unknown class are one verified behaviour, not two.**
`forecast_slots` writes 0.0 for any approach whose value is not a known
class, and `ForecastGate` sends both cases to the no-forecast policy. The two
differ only in the gate's logged reason: "no forecast for N" against "forecast
for N invalid".

**Where an unknown class can come from:**
- **In simulation,** forecasts come from the forecast producer, so an unknown
  class does not reach this code in practice.
- **On the wire,** `contracts.mqtt.decode` refuses an unknown class before
  anything is stored. At `1967e55`, though, that refusal surfaces as an HTTP
  500, not a 422, and it can escape the MQTT ingest thread. Phase C reproduced
  that on a live broker; P140, applied in the 2026-10-21 batch, fixes it.

**Who decides (`ForecastGate`, checked on every decision):**
- **counts or queues missing or invalid for any approach → Webster.** Counts
  are never encoded as a substitute value (P97a), and `PPOController` also
  refuses them.
- **no forecast message, an age over 10 s, or any required approach missing
  or invalid → the no-forecast policy.**
- **otherwise → the forecast-aware policy.**

The gate exists in simulation; no forecast-aware policy runs in the live path.
- **The layout is hashed into every checkpoint sidecar**
  (`simulation/contract.py`), because a permuted index keeps the shape and
  changes the meaning (P53).

### 6.2 Safety limits

`SafetyLimits` in `server/safety.py`:

| Limit | Value |
|---|---|
| minimum green | 10 s |
| maximum green | 90 s |
| all-red | 3 s |
| emergency response | 3 s |
| MQTT timeout | 10 s |

`SignalGuard` applies them, and the module contains no HTTP. The simulation
runner clamps with the same limits.

**Starvation.** The runner counts any red spell that reaches 180 s as a
starvation event, and reports it beside every result (ADR-011). That is a
measurement rule. It is not proof that starvation is impossible, nor that every
starvation condition is prevented. The safety contract is a bound under the
tested conditions, with no hardware involved.

**The three 10-second timeouts.** All are "greater than 10 s", and they are
different mechanisms:

| Where | Trigger | Behaviour |
|---|---|---|
| **Edge** (`EdgeNode.degraded`) | More than 10 s since the node's last successful publish | `Mode.LOCAL`: a fixed 30 s alternating cycle. The class is named `LocalWebster`, but it does no Webster computation |
| **Server** (`SignalGuard.decide`) | The heartbeat age **reported by the caller** of `POST /observation` (`seconds_since_heartbeat`) is more than 10 s. This is not the MQTT heartbeat, which no server component receives (§4.2) | It switches to the opposite phase, with the Webster green if one is supplied, otherwise 20 s (2 × minimum green), clamped. The decision is labelled `source="webster"`, and the policy output is not trusted. `/observation` supplies no Webster green, so it is 20 s |
| **Simulation** (`ForecastGate`) | The forecast is more than 10 s old | The no-forecast policy decides |

**Emergency pre-emption** (`SignalGuard`, FR-A05) gives the emergency approach's
phase a minimum green, with all-red only when the phase changes.

### 6.3 The command path, stated exactly

`POST /observation` takes counts and returns one command, with the rule that
produced it:
1. **The proposal** comes from `propose()`, which is **a documented
   placeholder**: switch toward the busier axis, with a 30 s green.
2. **The guard** then applies the limits, emergency pre-emption and the
   heartbeat timeout.
3. **The command is stored in SQLite.**

Two consequences:
- **The trained PPO policy is not wired into the server.**
- **No component sends a command to signal hardware.** Connecting forecasts or
  a learned policy to real timing is out of scope until it is separately
  validated (P97a Part 2 is deferred).

### 6.4 Model artifacts

- **Weights are gitignored.** Their SHA-256 manifest is committed
  (`experiments/results/model_artifacts.sha256`).
- **The committed manifest covers every artifact (P139).** It lists all 301
  under the five model folders; the earlier manifest covered 83. `pack` and
  `check` refuse a manifest that disagrees with the disk.
- **A cloud backup of the 301-artifact inventory was reported as downloaded
  and verified by the owner on 2026-10-18** (S66). The verification output
  was not retained. The checks before upload are recorded in P139: an
  inventory check, 18 of 18 lock hashes, and a full extract-and-rehash.

---

## 7. Deployment view

| Node | Runs | Measured on |
|---|---|---|
| **Edge laptop** | `edge/node.py`, YOLOv8, the forecasters, optionally MFSTNet ONNX on the CPU EP | the team laptop. **Every latency figure states its host** (ADR-003) |
| **Broker** | Mosquitto | localhost in the tests |
| **Server** | `uvicorn server.app:app`, `python -m server.mqtt_ingest`, SQLite at `data/server/stms.sqlite` | the same laptop in all measurements so far |
| **Dashboard** | the Vite build, polling the server's GET endpoints every 2 s | browser-checked at desktop and phone widths |
| **Training** | MFSTNet on CUDA (RTX 4050) over cached features; PPO on the CPU | the same laptop |
| **CI** | GitHub Actions: `fast`, `model`, `dashboard`, `docs`. Python 3.12 on Linux, with the simulation stack pinned and asserted | GitHub-hosted runners |

**No Docker Compose file exists today.** The TIM (Wave 4) is where the
clean-machine procedure will be written and then tested on a second machine.

---

## 8. Quality attributes

| Attribute | How it is achieved | Evidence | Limitation |
|---|---|---|---|
| **Privacy** (NFR-13, deployed runtime) | **Normal runtime keeps raw frames in the edge's memory**, and no payload, endpoint or table has a field designed to carry a frame. Every inbound payload is capped at 4,096 bytes, but free text can still get in two ways (§4.2). At `1967e55`, unchecked payload fields accept strings within that cap; P141, applied in the 2026-10-21 batch, closes them. At `1967e55` the intersection id, taken from the URL path or the MQTT topic, is stored and logged with no size cap. P142, applied in the 2026-10-21 batch, closes it to a 32-character pattern and stops the framework's echoes, including the access log. **The exception is gated:** `benchmark_live.py capture` records to disk only with `--allow-disk-recording`, which requires an explicit data-handling authorisation and is outside the normal runtime path | `server/app.py` and the contract design; V2's decode test wrote 0 files | Structural, not formally verified. **Outside NFR-13's scope:** offline research tools work on stored source clips, and some write stills from them:
<br>• **pseudo-labelling** writes to `data/pseudo/`, which is gitignored;
<br>• **the V1 labelling page** writes to `data/v1/`, which is gitignored;
<br>• **the lane survey** (`survey_lanes.py`) writes a `.preview.jpg` beside its JSON, and **37 such third-party frames are committed** under `data/`. 18 of them are the frames already tracked as having been public on `main`; the other 19 exist only on the private feature branch. The public-copy builder excludes them, but the git history holds them (§10) |
| **Availability of control** (FR-A06) | Edge timeout → fixed 30 s cycle; server timeout → guarded alternation; forecast gate → no-forecast policy (§6.2) | `tests/test_edge_node.py`, `tests/test_safety.py`; P97a Part 1 (0 violations under fault injection) | P97a Part 2 (non-inferiority under faults) is deferred |
| **Safety** | Limits enforced by actuation, in one module with no transport | `tests/test_safety.py` | A bound under the tested conditions, not a proof. No hardware |
| **Reproducibility** | Seeds, pinned requirements, CSVs written by scripts, provenance sidecars, SHA-256 locks, the CI version preflight | P137: the episode reproduces exactly on Linux CI under SUMO 1.27.1 | Results move under SUMO 1.28.0. Not yet reproduced on a clean machine |
| **Latency** | ONNX Runtime; MFSTNet streams one frame per step | V2 stand-in (P135): the model call p95 is 325.9 ms, **failing 6a** (≤ 150 ms); the whole edge step passes 6b; transport passes 6c | Laptop CPU, a stand-in run. S65 on the real camera is pending |
| **Testability** | Transports behind protocols, pure rule modules, contract types | 1,209 Python tests: 1,206 pass and 3 skip in a local run, 2026-10-18. CI runs the `fast`, `model`, `dashboard` (vitest + build) and `docs` jobs | The live-broker test (`test_mqtt_live.py`) is listed in the CI `model` job, but it skips unless an amqtt broker is available, and CI does not install one |
| **Evaluability** | LOCO folds, five training seeds, pre-registration with one-time runs, the claims gate | `loco_summary.csv`, `check_claims.py` | Four folds is the effective n. Two asserted claims are red |

---

## 9. Key decisions

The full list is the 27 ADRs in [decisions/](../00-planning/decisions/). These
are the ones that set the structure:

| ADR | Decision |
|---|---|
| ADR-003 | A laptop is the edge node; the MQTT contract is unchanged |
| ADR-005 | Local training on cached frozen-backbone features |
| ADR-007 | DINOv2 ViT-S/14; INT8 only at export |
| ADR-008 | SQLite; a descoped, read-only dashboard |
| ADR-014 | Benchmark and live panels never merge |
| ADR-019 | Leave-one-camera-out evaluation |
| ADR-020 | 17-dim state with a reserved "absent" value and the fail-safe gate |
| ADR-026 | MFSTNet runs on the edge, because its input is frames |
| ADR-027 | Two forecasting roles: persistence for the class, ridge for the count |

---

## 10. Known limitations and risks

1. **No forecast is connected to live control.** Forecast-assisted PPO was
   evaluated only in simulation, and that line closed with a null (P130, P133).
2. **The domain claim is red.** No fold-eligible camera is Indian (P58).
   Class coverage is also red (P57).
3. **The historical "PPO beats Webster by 19.4%" (P82) is not a matched
   comparison,** and is citable only with its qualifications (P138).
4. **The MFSTNet model call misses its latency budget** on laptop CPU (6a).
5. **The server's command endpoint is a placeholder rule** (§6.3).
6. **The clean-machine reproduction has not been run.** No Docker Compose
   file exists.
7. **Licensing is unresolved** for the Bellevue data, the third-party weights,
   and **37 committed third-party preview frames**. A per-file inventory exists
   (`frames-inventory.csv`, held with the review drafts outside the
   repository). For each frame it records the source clip, the camera record,
   the licence status, whether the frame is on `origin/main`, the commit that
   added it, and whether the public-copy builder excludes it. All 37 are
   excluded by that builder, and all 37 have an unresolved licence. **The
   per-file rights review is unresolved, and a count is not a clearance.**
   - **18 are in `main`'s history** and were public before the repository
     went private;
   - **19 exist only on the feature branch,** which was pushed only while
     private. A merge or a visibility change would carry them too.

   The repository is private.
8. **The cloud backup's download check is owner-reported** and its output
   was not retained (§6.4). The backup tool itself covers every artifact
   since P139.
9. **The safety contract is a bound under the tested conditions, not a
   proof** (§6.2).
10. **At `1967e55`, a malformed current-schema payload is not refused
    cleanly.** It returns HTTP 500 rather than 422, and it stops the MQTT
    ingest thread silently. Both were reproduced, the second on a live broker
    in Phase C. **Fixed by P140**, applied in the 2026-10-21 batch.
11. **Schema v2's no-free-text aim was not enforced at `1967e55`** (§4.2).
    - **Unchecked payload fields and echoing refusal messages:** fixed by
      P141.
    - **The intersection id, framework echoes and `/observation` bounds:**
      fixed by P142. That includes the `NaN` heartbeat that skipped the FR-A06
      fallback.
    - Both were applied in the 2026-10-21 batch.
    - **Residual after both:** a valid 32-character id (about 24 bytes) and
      the digits of numeric fields.
12. **The dashboard URL is `/dashboard/`** once P142 is applied. Without the
    slash it is a 404, because redirects are off.

---

## 11. Traceability

The [RTM](../01-requirements/RTM.md) reserves `DES-*` IDs for Wave 2 and
currently marks them **W2**. This draft deliberately assigns none.

**Assigning them is one change touching two documents:**
- the IDs, defined here;
- the RTM rows that join them.

Both must land in the same commit, because `scripts/check_docs.py` fails if
either half is missing. That commit waits on the owner's approval of this
draft.
