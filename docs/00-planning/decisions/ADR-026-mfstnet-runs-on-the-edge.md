# ADR-026 — MFSTNet runs on the edge; the server receives predictions

**Status:** Accepted (architecture) by the project owner 2026-10-15 — production readiness open, see P89 · **Date:** 2026-10-15 · **Amends [ADR-008](ADR-008-prototype-descoping.md)'s placement of the forecaster; chosen by the project owner 2026-10-15 as Option A, conditional on the edge meeting its budget**

## Context

ADR-008, and the comment in `edge/node.py` that followed it, put the forecaster
on the server: "the node counts and publishes, the server holds the policy and
the forecaster". PRD §7 says the server runs ONNX MFSTNet.

That placement cannot be built. MFSTNet's inputs are ResNet-50 and DINOv2
feature maps computed **from frames**. NFR-13 says raw frames never leave the
edge and only derived counts and predictions do; feature maps are neither.
So the server can receive nothing MFSTNet can run on.

Two options were put to the project owner:

| | A: MFSTNet on the edge | B: count-based forecaster on the server |
|---|---|---|
| deployed forecaster | MFSTNet | a different model ([ADR-023](ADR-023-separate-the-two-claims.md)'s C1) |
| NFR-13 | met | met |
| ADR-008 | amended | unchanged |
| main risk | edge latency and compute | the system ships without the model the project is about |

**Chosen: A**, with B kept as the fallback if the edge cannot meet its budget.
The project owner was explicit that MFSTNet is not to be silently replaced by a
simpler model just to keep the server architecture.

## Decision

**1. The edge runs MFSTNet.** `edge/forecaster.py`. Frames → shared
preprocessing → both backbones → fp16 rounding → a ring of the last T feature
frames → the ONNX graph → a `CongestionPrediction`, published on
`stms/{id}/congestion/prediction`. Steady state costs one frame of backbones
per step; the full-window recompute is the cold start only.

**2. The server receives, validates, stores and consumes predictions.**
`POST /prediction/{id}` decodes through `contracts.mqtt.decode`, the same
validation the broker topic gets. The predictions map onto PPO state indices
11–14 through `to_state_values()`, and `GET /prediction/{id}/latest` serves the
dashboard. The server keeps the policy and the safety rules (`server/safety.py`).

**3. Only a verified graph is served.** `VerifiedGraph` refuses a graph with no
sidecar, a graph that failed `export_checkpoint.py`'s verification against its
own committed predictions, and a graph whose bytes no longer hash to what was
verified. Every prediction names the graph it came from (`config@sha256[:12]`).
That name is stored server-side, so a value on the dashboard traces to a
checkpoint.

**4. Edge and cache share one preprocessing function.**
`mfstnet/preprocess.py` is used by both `build_cache.py` and the edge, and is
verified bit-identical to the transform the cache was built with. This fixes a
latent divergence: the cache's hash records `resize_mode: "bilinear"`, but it
has always resized with `INTER_AREA` ([P88](../PRD-CHANGELOG.md)).

**5. NFR-13 is enforced by schema first and by size second.** Contract schema
v2 removes free text from every edge payload:

- `model` must match `config@12-hex-digest`;
- prediction keys must be approaches;
- emergency `type` is a closed set, today only the PRD's "ambulance".

No field can carry an encoding of anything, at any length. A 4 KB cap on encode
and decode stays as the second line, for any field added later. The project
owner noted that a size cap alone does not prove nothing visual is encoded in a
small message; the schema is what closes that, not the cap.

The server's MQTT subscriber logs a refused payload by topic, error type and
size only, never by message. Contract errors quote the offending value for the
producer's benefit, and `tests/test_mqtt_live.py` caught the first version of
the subscriber echoing it.

**6. Lanes map to approaches explicitly, per camera.** The graph predicts
`lane_0..3` and PPO indices 11–14 are N, S, E, W. The mapping is required at
start-up, must be one-to-one, and is never defaulted.

## The latency requirement, and its fallback

One step must complete within **half of `step_s`** at p95, leaving the other
half for detection, counting and the link on the same laptop. At `step_s = 2`
that is **1000 ms**. The PRD §16 figure of 150 ms for the head alone still
applies to the head.

Measured by `scripts/verify_edge.py` on the same pass that checks correctness:
per-step feature and head time, p95 step time, cold start, peak GPU and process
memory, and sustained throughput. **This ADR stays Proposed until that
measurement passes on the selected S61 checkpoint.** If it fails on the edge
laptop, the fallback is Option B, recorded as a decision and not taken
silently.

Smoke evidence, not the acceptance measurement: a 2-epoch config-H checkpoint
on CPU only, with the GPU busy training, ran real video for 35 windows. It
agreed with its committed predictions on **140 of 140** decisions, and the
server stored the verified model id with no mismatch. p95 step time was
**724 ms**: features 566 ms and head 68 ms at the median.

## Acceptance evidence — S61, 2026-10-15

Every criterion was fixed before the measurement. None was changed after it.

| Check | Required | Measured |
|---|---|---|
| runs accounted for | 40, failures recorded | 40 of 40, no failures |
| selection | validation columns only | G, fold 3, seed 13 — `selection.json` |
| checkpoint | fingerprinted | sha256 `abc8f239…3214` |
| ONNX vs PyTorch | identical argmax, drift < 1e-3 | 136/136, 2.1e-7 |
| graph vs committed predictions | ≥ 0.99 | **1.0000** (136/136) |
| fresh-weights control | below the trained graph | 0.0000 |
| real held-out video, edge, live MQTT, server | ≥ 0.99, model id exact | **1.0000**, `G@fe093966bc7d`, 0 mismatches |
| `/latest` | equals the last prediction published | yes |
| step p95, RTX 4050 | ≤ 1000 ms | **170.8 ms** (features 96 ms, head 57 ms at p50) |
| sustained throughput | ≥ 0.5 step/s | 6.42 steps/s |
| peak GPU / process memory | recorded | 194 MB / 1,318 MB |
| delivery, edge send to server store | recorded, separate | p50 11.0 ms, p95 12.4 ms (paced at `step_s`) |
| local QoS 0 send | recorded, not an acknowledgement | p95 0.71 ms |
| full suite incl. live broker | passes | 964 passed, 1 skipped (downloads 200 MB) |

**One thing the measurement does not cover**, recorded as
[P89](../PRD-CHANGELOG.md). The step time starts at a decoded frame. Cold start
was 147 s for the first full window. About 6 s of that is model work: 60
feature passes at 96 ms. The rest is decoding a **3840×2160** file at
29.97 fps, where taking one frame every 2 s still decodes every frame. By that
arithmetic, CPU decoding ran at roughly 25 fps, which is below the 30 fps a live
4K stream delivers. The figure is derived, not measured directly. The model is
inside its budget with a wide margin; a 4K camera's decoder may not be. Measure
decode at the deployment camera's resolution, with hardware (NVDEC) decoding
available, before calling the edge production-ready.

## Consequences

**Gained.** The deployed forecaster is the model the project is about. The
NFR-13 boundary holds by construction rather than by care. Every prediction on
the dashboard traces to a verified checkpoint.

**Cost.** The edge laptop carries both backbones. The heartbeat now reports
`mfstnet_active` from what the node has actually published. Schema v2 breaks v1
producers on purpose: a v1 `model` string is refused rather than coerced.

**Done since drafting.** `gate_value` is `None` for a gate-less config (A, B,
H), so the dashboard can tell an absent gate from a real 0.5 (FR-UI05). The live
link exists: `edge/mqtt_transport.py`, where a QoS 1 or 2 publish waits for the
broker's acknowledgement or raises, so FR-A06 measures the link and not a
socket buffer; and `server/mqtt_ingest.py`, which stores through the same
`store_prediction` as the HTTP endpoint. Tested end to end against a real broker
(amqtt, from its own environment). Production uses Mosquitto, which needs an
administrator install and is left to the project owner.

**Not yet done.** The dashboard (S42). PPO consuming indices 11–14 on the
server, which is P52's open surrogate arm.

## Acceptance

**Architecture accepted by the project owner on 2026-10-15**, on the S61 evidence
above. As with ADR-006 and ADR-008, this is the owner's acceptance and **not** a
faculty-guide signature.

What is accepted:

- MFSTNet runs on the edge laptop.
- Only contract-approved counts and predictions cross to the server.
- The server handles ingestion, traffic-management logic and aggregation.
- The dashboard consumes real model predictions.
- The count-based server forecaster remains the documented fallback.

**Decode benchmark, 2026-10-15 ([P89](../PRD-CHANGELOG.md)).** Four of five
configurations pass the pre-registered criteria. AV1 4K decoded in software
**fails**: lag grew 36 s in five minutes. H.264, at 4K or 1080p, passes in
software, and 1080p has the widest margins; it is the recommended deployment
format. Every pass is from re-encoded file playback, not a live camera stream.

**Production readiness is not accepted.** It waits on one measurement: the
complete live-camera pipeline at the intended resolution and frame rate —
decoding, sampling, feature extraction, inference and publishing — sustained
over a continuous run with a stable 2 s cadence ([P89](../PRD-CHANGELOG.md)).
The inference threshold does not change. Nothing here is evidence about Indian
traffic, and the Indian claims stay red.
