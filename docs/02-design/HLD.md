# High-Level Design (HLD)

| | |
|---|---|
| **Wave** | 2 (ADR-004) |
| **Status** | **Approved** by the owner's review, 2026-10-21. Committed with the batch it describes |
| **Describes** | The modules, interfaces and data flow of each subsystem, at `1967e55` plus the **integration batch of 2026-10-21** (P140, P141, P142, D1, D2), committed with this document. **[batch]** marks what that batch changed relative to `1967e55` |
| **Builds on** | The [SAD](SAD.md), which is accepted for HLD review, and the [HLD — Detection & Corpus Pipeline](HLD-detection-corpus-pipeline.md), which this document does not repeat. **The `SAD.md` link resolves only once both documents are committed to `docs/02-design/`. It is verified there by `scripts/check_docs.py` at integration, not assumed** |
| **Edge deployment** | §4 is run by `python -m edge.run`, committed by D3 (2026-10-21), which resolves §9-C1. The clean-environment check is done (D4); the deployment prerequisites it left open are listed there |
| **Audience** | The faculty guide, examiners, and a team member about to change one subsystem |

> **What this design does not include:**
> - **No component drives signal hardware.**
> - **No forecast feeds signal timing in the live path.**
> - **The server's command endpoint is a placeholder rule** (SAD §6.3).
>
> Forecast-assisted control exists only as simulation arms, and those closed
> with a null result (P130).

---

## 1. Module map

| Subsystem | Module | Responsibility | Main interface |
|---|---|---|---|
| **Corpus** | `mfstnet/corpus/*` | video → counts → labels → folds | see the detection & corpus HLD |
| **MFSTNet** | `mfstnet/encoders.py` | frozen ResNet-50 and DINOv2 branches and projection adapters | `DualPathEncoder`, `ProjectionAdapter` |
| | `mfstnet/cache.py` | the frozen-feature cache and its preprocessing contract | `FeatureCache`, `PreprocessingSpec`, `CacheMismatchError` |
| | `mfstnet/fusion.py` | none / concat / one-way / two-way cross-attention, with an optional gate | `CrossAttentionFusion(FusionConfig)` |
| | `mfstnet/temporal.py` | per-lane ROI pooling, BiLSTM, temporal attention, pooling, head | `LanePool`, `TemporalEncoder`, `CongestionHead` |
| | `mfstnet/model.py` | assembly, and the A–H ablation table | `MFSTNet(cfg, lane_masks)`, `ablation_config(name)` |
| | `mfstnet/preprocess.py` | the one frame-preprocessing function | `preprocess_frame(frame_bgr, size)` |
| | `mfstnet/metrics.py` | macro-F1, per-class metrics, QWK | `evaluate(y_true, y_pred, classes)` |
| **Simulation** | `simulation/envs/traffic_env.py` | the Gymnasium SUMO environment and the 17-dim state | `TrafficSignalEnv`, `start_sumo` |
| | `simulation/runner.py` | the evaluation harness; tripinfo metrics | `run_episode(...) -> EpisodeResult` |
| | `simulation/controllers.py`, `webster.py`, `ppo_controller.py`, `gated_controller.py` | the baselines, the PPO policy, and the forecast-gated controller | `Controller` protocol: `decide(observation)` |
| | `simulation/forecast_state.py` | slots 11–14 and 16, and the fail-safe gate | `forecast_slots`, `ForecastGate` |
| | `simulation/forecast_producer.py`, `oracle.py`, `forecast_quality.py`, `forecast_eval.py` | the training-time forecast and the replay oracle | `NoForecast`, `Surrogate(q)`, `ReplayOracle` |
| | `simulation/scenarios.py`, `equivalence.py`, `contract.py` | demand scenarios, harness parity, the state-layout hash | `schedule`, `compare`, `contract_digest` |
| **Edge** | `edge/node.py` | publishing, heartbeat, and the FR-A06 fallback | `EdgeNode.tick(lane_counts, fps)` |
| | `edge/samples.py` | the contiguous, plausible per-lane sample window | `SampleBuffer`, `SampleError` |
| | `edge/persistence.py` | the class-role forecaster (ADR-027) | `PersistenceForecaster.step(counts, ts)` |
| | `edge/count_forecast.py` | the count-role forecaster (ADR-027) | `RidgeCountForecaster.step(counts, ts)` |
| | `edge/classes.py` **[batch: D1]** | detector classes → contract classes | `load_itd_mapping()`, `normalise()` |
| | `edge/forecaster.py` | MFSTNet on the edge, verified ONNX only; holds no role | `VerifiedGraph`, `EdgeForecaster` |
| | `edge/mqtt_transport.py` | the paho link; QoS ≥ 1 waits for the broker's acknowledgement | `MqttTransport.publish(topic, payload, qos)` |
| **Contracts** | `contracts/mqtt.py` | every topic, QoS and payload; validation; the intersection-id rule | `Topic`, payload classes, `decode`, `check_intersection_id` [batch] |
| **Server** | `server/app.py` | FastAPI endpoints, SQLite storage, evidence, the access-log filter [batch] | §6 |
| | `server/mqtt_ingest.py` | subscribes to the two forecast topics and stores through the HTTP store functions | `PredictionIngest`, `route(topic)` |
| | `server/safety.py` | limits and the signal guard; no HTTP | `SafetyLimits`, `SignalGuard.decide(...)` |
| **Dashboard** | `dashboard/src/*` | a read-only React page | §7 |

---

## 2. MFSTNet

### 2.1 Pipeline and shapes

```
frames [B, T=60, 3, 224, 224]
  -> frozen ResNet-50  -> [B, T, 2048, 7, 7]  ┐  computed ONCE into the cache (ADR-005),
  -> frozen DINOv2 S/14 -> [B, T, 384, 16, 16] ┘  fp16, guarded by preprocessing_hash
       (the ViT map is resized to the G×G grid, G = 7, before fusion)
  -> ProjectionAdapter (trainable, per branch) -> d_model = 256 on a 7×7 grid
  -> CrossAttentionFusion -> fused [B, T, 49, 256], gate g [B, T, 49, 1] or None
  -> LanePool (per-lane ROI masks [L, 7, 7]) -> [B, L, T, 256]
  -> TemporalEncoder (BiLSTM 2 × 128 bidirectional; optional 2-layer, 4-head attention;
     pooling last | attention | mean) -> [B, L, 256]
  -> CongestionHead (hidden 128, or a bare Linear for H) -> logits [B, L, 3]
```

**The output is `MFSTNetOutput(logits, gate)`.** `gate_mean` is logged, and
**is not part of the PPO state** (A16).

**The numbers are read from `mfstnet/configs/spec.yaml`:** `T`, `grid`,
`d_model`, the BiLSTM and attention sizes, and the backbone arms BB-1 to BB-3.

### 2.2 The ablation flag scheme (NFR-15)

Each configuration is data: overrides to `FusionConfig` and `TemporalConfig`,
plus the head's hidden width (`model._ABLATION_SPECS`). **No code differs
between configurations.**

| Config | Fusion `mode` | CNN / ViT | Gate | BiLSTM | Temporal attention | Pooling | Head |
|---|---|---|---|---|---|---|---|
| A | none | CNN only | — | yes | — | last | 128 |
| B | none | ViT only | — | yes | — | last | 128 |
| C | concat | both | — | yes | — | last | 128 |
| D | unidirectional | both | — | yes | — | last | 128 |
| E | bidirectional | both | — | yes | — | last | 128 |
| F | bidirectional | both | — | yes | yes | attention | 128 |
| G | bidirectional | both | **yes** | yes | yes | attention | 128 |
| H | concat | both | — | — | — | mean | Linear (A22) |

### 2.3 The cache contract (ADR-005, P35, P55)

- **The key.** A cache is keyed by `preprocessing_hash`: backbone identity,
  resize and normalisation. On a mismatch, loading **raises**
  `CacheMismatchError`.
- **Precision.** Features stay fp16 until they reach the device, then widen to
  fp32 (P35).
- **Reading a window.** A window is **copied** out of the memory map, never
  viewed (P55).

### 2.4 Training, selection and export

| Step | Entry point | Artifact |
|---|---|---|
| Train one configuration | `scripts/train_mfstnet.py --config X` | a per-run CSV plus a sidecar; `--save-checkpoint` keeps the model |
| LOCO suite | `scripts/run_loco.py --ablation --seeds …` (one configuration per process) | per-fold CSVs and `loco_summary.csv` (mean and bootstrap CI over folds) |
| Selection | `scripts/select_checkpoint.py` | pre-registered, validation columns only |
| Export | `scripts/export_checkpoint.py` | an ONNX graph plus a verification sidecar. `edge/forecaster.py` serves only a graph whose sidecar passed and whose bytes still hash to the recorded value |

---

## 3. Simulation and control

### 3.1 Environment

`TrafficSignalEnv` runs SUMO through TraCI, with the sublane model at 0.8
(ADR-010, P119).
- **State:** 17 dimensions, with the layout in `spec.yaml` and its hash in
  every checkpoint sidecar (`simulation/contract.py`).
- **Action spaces:**
  - `phase_duration`: 12 discrete actions, NS or EW × 10/20/30/45/60/90 s;
  - `keep_or_switch`: 2 actions, every 5 s.
- **Reward:** starvation and switch penalties, from `ppo_config.yaml`.

### 3.2 Harness parity

`run_episode` applies the `keep_or_switch` rules the environment trained
under:
- it decides from t = 0;
- a keep lasts 5 s;
- a switch is refused before 10 s of green;
- 90 s of green forces a switch.

`PPOController` builds index 10 exactly as the environment does.
`simulation/equivalence.py` checks that the two harnesses produce identical
decision traces (P120).

### 3.3 Controllers

| Controller | Module | Notes |
|---|---|---|
| Fixed | `controllers.Fixed` | the untuned status quo |
| Longest queue | `controllers.LongestQueue` | — |
| Webster | `webster.Webster`, `select_best` | saturation flow swept (ADR-012); best configuration chosen; the clamp rate is reported |
| PPO | `ppo_controller.PPOController` | the checkpoint and sidecar are checked against the state contract |
| Gated | `gated_controller.GatedController` | `ForecastGate` hands each decision to the forecast policy, the no-forecast policy, or Webster |

### 3.4 Forecasts in simulation

- **Arms** (`ppo_config.yaml`): `no-forecast`, `surrogate` (quality q from 0
  to 1), and `mfstnet`. The last is not runnable in SUMO, because SUMO has no
  frames.
- **What `Surrogate(q)` does:** it mixes a replay oracle (`oracle.py`) with
  persistence.
- **How evaluation receives forecasts:** through `ForecastFeeding`.
- **Outcome:** P130 closed this line with a null result.

### 3.5 Benchmark

- **Entry point:** `scripts/benchmark.py`, with 30 seeds.
- **Statistics** (`experiments/statistics.py`): bootstrap CI with 10,000
  resamples, a paired t-test, Cohen's d, and Holm correction.
- **Results:** written as CSVs by the script, never transcribed.

---

## 4. Edge

### 4.1 One sample (2 s)

The loop below is the **intended** per-sample design. As §9-C1 records, no
committed program runs it yet.

```
frame (in memory; NFR-13)
  -> detector (ITD-xl, conf 0.45, imgsz 992) -> Detection list
  -> count_frame(detections, LaneCentres)    -> FrameCounts(per_lane, per_lane_class)
       ├─ per_lane totals ............................ FORECASTER INPUT (raw; bicycles included)
       │     -> PersistenceForecaster.step(totals, ts) -> CongestionPrediction | None
       │     -> RidgeCountForecaster.step(totals, ts)  -> CountForecast | None
       │     -> EdgeNode.publish_prediction / publish_count_forecast
       └─ per_lane_class ............................. CONTRACT COUNT
             -> EdgeNode.tick(per_lane_class, fps)
                  -> normalise() via itd_mapping [batch: D1]
                  -> VehicleCount per lane (topic not ingested by the server)
                  -> heartbeat; FR-A06 check
```

**The two count representations stay apart** (SAD §4.3):
- **The forecasters always take the raw totals**, which their frozen specs
  were calibrated on. They never take the mapped count.

**[batch: D1] How the contract count is built:**
- **A class dropped by decision** (bicycle) is left out, and tallied in
  `EdgeNode.excluded`.
- **A class with no decision** withholds the lane's count, rather than
  understating it.
- **`publish_counts` never raises.**

### 4.2 Window rules (`SampleBuffer`)

| Situation | What happens |
|---|---|
| A sample covers exactly the configured lanes, with finite, non-negative, plausible counts | It joins the window |
| A lane is missing | The sample is refused (`SampleError`). The window is kept |
| A gap of more than 1.5 × 2 s | **The window resets**. No forecast is made until a full window has refilled: 30 samples for persistence, 60 for ridge |
| A timestamp is out of order | Refused |

### 4.3 Link and fallback (FR-A06)

- **Publishing.** `MqttTransport.publish` raises unless the broker
  acknowledges, for QoS ≥ 1.
- **Acknowledgement.** `EdgeNode.last_ack` advances only on a successful
  publish.
- **The rule** (`EdgeNode.degraded`): the node enters `Mode.LOCAL` when
  **more than 10 s have passed since the last successful publish**
  (`last_ack`). It then outputs a fixed 30 s alternating cycle
  (`LocalWebster`). A successful publish returns it to `Mode.NORMAL`.
- **What Phase C observed** is a different measurement:
  - `LOCAL` **9 s after the broker was killed**, measured from the kill, not
    from `last_ack`;
  - `NORMAL` 1 to 2 s after the broker was restarted.
- **The two are not the same quantity.** The last successful publish came
  before the kill: two headless-browser renders and the F1 check ran between
  the last main-loop publish and the kill. The harness did not record
  `last_ack`, so the size of that gap is unknown.
- **What the evidence supports:** the fallback fired and recovered.
- **What it does not establish:** an exact correspondence with the 10 s
  threshold. The node's own tests check that (`tests/test_edge_node.py`).
  D3's tests measure from `last_ack` (`tests/test_edge_run.py`), and D3's
  live run logged the switch 12.0 s after the last acknowledged publish.

### 4.4 Identity [batch: P142]

`EdgeNode` refuses an intersection id outside `[A-Za-z0-9_-]{1,32}` at
start-up.

---

## 5. Contracts (`contracts/mqtt.py`)

**Topics.** Each topic's QoS is bound to the topic itself (SAD §4.2). The
payloads are `VehicleCount`, `EmergencyDetect`, `SignalCommand`,
`CongestionPrediction`, `CountForecast` and `Heartbeat`, at schema v2.

**`decode(topic, raw)` checks, in order:**
1. the size cap of 4,096 bytes;
2. **[batch: P140]** that the input is UTF-8 JSON and a JSON **object**;
3. the schema version;
4. that the enum conversions and fields are valid inside one refusal. Every
   failure is a `ContractError` with no submitted value in its message.

**[batch: P141]** Every field of `CongestionPrediction` and `CountForecast` is
typed and bounded.

**Definitions used in the table:**
- **"Number"** means a JSON integer or float, excluding `true`/`false`.
  Python counts `bool` as an `int`.
- **"Finite"** excludes `NaN`, `±Infinity`, and integers beyond float range.

| Payload | Field | Accepted |
|---|---|---|
| both | `v` | the schema version, `2` |
| `CongestionPrediction` | `predictions` | keys in {N, S, E, W}; values in {LOW, MEDIUM, HIGH} |
| | `confidences` | the same keys as `predictions`; each a finite number in [0, 1] |
| | `gate_value` | a finite number in [0, 1], or `null` |
| | `model` | `MODEL_ID = ^(?:[A-H]\|persistence)@[0-9a-f]{12}$`, applied with `fullmatch`; for example `G@0123456789ab` or `persistence@2431c6641b9c` |
| | `horizon_sec` | **the integer `60`**. `60.0`, `"60"` and `true` are refused, even though they compare equal to 60 |
| | `ts` | a finite number with 0 < `ts` < 4,102,444,800 (2100-01-01T00:00:00Z) |
| `CountForecast` | `counts` | at least one key; keys in {N, S, E, W}; each a finite number in [0, 200] (`MAX_LANE_COUNT`) |
| | `model` | `COUNT_MODEL_ID = ^ridge@[0-9a-f]{12}$`, applied with `fullmatch` |
| | `horizon_sec` | the integer `60` |
| | `ts` | as for `CongestionPrediction` |

**On "full match":** at `HEAD` the model patterns are applied with
`re.match`, so the pattern's `$` also accepts a trailing newline. The batch
uses `fullmatch`. The constraints in the table are the contract's own; none is
added here.

**[batch: P142]** `INTERSECTION_ID` and `check_intersection_id` are the one
id rule.

---

## 6. Server

### 6.1 Endpoints

The **Batch** column names exactly what the batch changes on each route. A
dash means the route is unchanged by the batch.

| Method and path | Purpose | Validation | Refusal | Batch |
|---|---|---|---|---|
| `GET /health` | liveness, plus the safety limits | — | — | — |
| `POST /observation` | **prototype**: placeholder rule + `SignalGuard`; logged in `observations` | `Counts` model. At `HEAD`: id length 1 to 64 and an unknown-key check. After the batch: the id pattern, approaches as keys, counts 0 to 10,000, ages finite and capped, emergency approach N/S/E/W (case-normalised) | 422 | **[batch: P142]** the new bounds and closed keys; the 422 no longer echoes input |
| `POST /prediction/{id}` | store one class forecast | the id, then `decode` (§5) | 422 | **[batch: P142]** the id check. **[P140, P141]** the stricter `decode` |
| `GET /prediction/{id}/latest` | the latest class forecast, with freshness | the id | 422 for a bad id; 404 when none stored | **[batch: P142]** the id check; the 404 text no longer quotes the id |
| `POST /count_forecast/{id}` | store one count forecast | the id, then `decode` (§5) | 422 | **[batch: P142]** the id check. **[P140, P141]** the stricter `decode` |
| `GET /count_forecast/{id}/latest` | the latest count forecast, with freshness | the id | 422 / 404 | **[batch: P142]** the id check; the 404 text is fixed |
| `GET /history/{id}?limit=` | recent decisions from `observations` | the id; `limit`, clamped at 500 | 422 | **[batch: P142]** the id check; `limit ≥ 1` (at `HEAD`, `-1` returned every row) |
| `GET /evidence` | historical evaluation evidence, from committed files | — | — | — |
| `GET /dashboard/` | the built dashboard (static mount), served only when `dashboard/dist` exists | — | — | **[batch: P142]** `/dashboard` without the slash is a 404, because redirects are off |
| any route, framework errors | — | FastAPI's own 422 | — | **[batch: P142]** the 422 drops `input` and `ctx`, and keeps `loc[:2]` |

### 6.2 Storage (SQLite, `data/server/stms.sqlite`)

| Table | Columns |
|---|---|
| `observations` | time, id, 4 counts, 4 queues, phase, green, source, reason, clamped |
| `predictions` | time, id, model, payload |
| `count_forecasts` | time, id, model, payload |

Each payload is the re-encoded, validated message.

### 6.3 Ingest

`PredictionIngest` subscribes to `stms/+/congestion/prediction` and
`stms/+/count/forecast`. `route(topic)` checks the shape and **[batch]** the
id, then calls the same store function as HTTP.

**[batch: P140 and P142] Two separate records:**
- **`refused`** for contract failures, logged with a warning;
- **`failed`** for server failures, logged as an error.

In both, only the label, the type and the size are kept. An invalid topic is
labelled `<unrouted topic>`. **No exception leaves the paho callback.**

### 6.4 Access log [batch: P142]

`AccessLogFilter` on `uvicorn.access` rewrites the request target before it is
logged:

| Target | Logged as |
|---|---|
| An API route whose path parameters are all ids passing the rule | the path |
| A static-mount path | `/dashboard/<static>` |
| Anything else | `<refused path>` or `<unmatched path>` |
| A query string | `?<query>` |

### 6.5 Safety

`SignalGuard.decide` applies, in order:
1. emergency pre-emption (FR-A05);
2. a heartbeat older than 10 s: alternate the phase with 20 s of green,
   labelled `source = "webster"`;
3. hold until minimum green;
4. clamp to the 10 / 90 s limits.

The guard has no transport code.

---

## 7. Dashboard

| Module | Role |
|---|---|
| `App.jsx` | the layout: live region and results region, separated (ADR-014); the P97a banner **[batch: D2 wording]**; the id taken from `?id=`, matching `{1,32}` **[batch]** |
| `api.js` | `get(path)` over an allow-list of three GET paths. GET only, so nothing can reach `/observation` |
| `usePoll.js` | polls the live panels every 2 s |
| `validate.js` | rejects a response that is inconsistent; it is shown as invalid with the reason |
| `Panels.jsx` | the count panel (ridge), the class panel (persistence), and the evidence panel. A missing approach is shown as "no forecast", never as LOW |

**The canonical URL is `http://<server>/dashboard/`, with the trailing slash.**

---

## 8. Where values live

| Value | File |
|---|---|
| MFSTNet numbers, the state layout, normalisers, signal limits, ablation seeds | `mfstnet/configs/spec.yaml` |
| The A–H configuration table | `mfstnet/model.py` (`_ABLATION_SPECS`); see §9-C2 |
| PPO hyperparameters, arms, environment | `simulation/configs/ppo_config.yaml` |
| Demand scenarios | `simulation/configs/scenarios.yaml` |
| Class mappings: IDD and **[batch: D1]** ITD | `indiatrafficnet/class_mapping.yaml` |
| Frozen forecaster specs | `experiments/results/bellevue_pilot/persistence_v1.json` and `p105_ridge_v1.json` (hash-checked) |
| Safety limits | `server/safety.py` `SafetyLimits`; the simulation reads the same values from `spec.yaml` |

---

## 9. Conflicts found while writing this HLD (recorded, not reconciled)

**C1 — There was no committed edge program for the deployed path. Material; resolved by D3.**
- **The gap.** `edge/node.py`'s docstring says
  `python -m edge.node --source clip.mp4 --lanes …`, but **no module in
  `edge/` has an entry point**. Nothing in the repository runs detector →
  counting → persistence + ridge → publish.
- **What did run it:** only the Phase C harness, which lives outside the
  repository.
- **Why it matters.** The TIM and SOP (Wave 4) cannot describe starting a
  program that does not exist.
- **Decision (owner's review):** tracked as **D3**, **outside** the current
  batch, and to be resolved before the TIM or SOP claim a reproducible edge
  deployment. Until then, §4 is the intended design, not a runnable
  deployment.
- **What "done" means** is set out in [PLAN-D3](../plans/PLAN-D3-edge-entry-point.md): a committed program
  that preserves the Phase C behaviour, with tests for:
  - start-up arguments;
  - the two count representations;
  - window warm-up and reset;
  - publishing and acknowledgement;
  - fallback and recovery measured from `last_ack`;
  - frames kept in memory only.

  Moving the harness loop is not enough.
- **Resolved by D3 (2026-10-21).** `edge/run.py` is the committed program and
  `tests/test_edge_run.py` covers each item above. On the Phase C footage, a
  live run reproduced Phase C's stored forecasts payload for payload
  (PRD-CHANGELOG, D3). §4 is no longer only an intended design.

**C2 — The A–H table is in code, not YAML.** It meets NFR-15 (no code edit
between configurations), but not the project's "config, not code" convention
(NFR-16).

**C3 — `CLAUDE.md` points to `mfstnet/configs/mfstnet_config.yaml`, which does
not exist.** The values are in `spec.yaml` and `model.py`.

**C4 — `vehicle_count` is published but not ingested.** PRD §17 defines the
topic on the edge-to-server link (QoS 1, every 5 s), but nothing on the server
subscribes to it: the ingest takes only the two forecast topics. Today the
counts are carried over the broker and then dropped. The dashboard and the
guard do not need them, and `/observation` takes counts over HTTP.

**C5 — The seed list is defined in three places** (`spec.yaml`,
`run_loco.py`, the manual). This is already recorded, and is listed here only
so that this HLD does not appear to resolve it.

**C6 — The PRD still states things later decisions changed.** These are
decided elsewhere; this HLD follows the decisions:

| PRD statement | Superseded by |
|---|---|
| a 16-dim state (§13.1) | the 17-dim state (ADR-020) |
| a 60/20/20 split (§8.4) | leave-one-camera-out (ADR-019) |
| PPO on the server | the placeholder rule (SAD §6.3) |

**C7 — The MFSTNet model call misses its 150 ms budget** on laptop CPU (V2,
6a). MFSTNet holds no deployed role (ADR-027), so this does not block the
deployed path.

---

## 10. Traceability

As in the SAD, no `DES-*` IDs are assigned here. They land together with the
RTM rows, in one commit, after approval (`scripts/check_docs.py`).
