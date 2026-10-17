# V2 / S65 — pre-registration: the live-camera validation criteria

**Frozen 2026-10-17, before any real-camera run.**

**Owner decisions:**
- the criterion-6 split (P135);
- no raw video on disk (P134).

**This is technical validation of the edge pipeline. It is not evidence that
the controller is production-ready. The controller stays disconnected from
signal timing.**

## Data handling (unchanged, enforced in code)

- **In memory only.** No frame, clip, image or video is written to disk during
  any V2 run, real or stand-in. `capture` refuses unless
  `--allow-disk-recording` is passed, and that flag needs an explicit
  data-handling authorisation first.
- **What is kept:**
  - timestamps;
  - prediction times;
  - latency samples;
  - freshness values;
  - counts of samples, losses and reconnects.
- **The URL** is read only from `STMS_CAMERA_URL`. It is never printed or
  stored: only its scheme and host are kept.

## Criteria (all frozen)

| # | criterion | measured by | pass statistic |
|---|---|---|---|
| 1 | decode at least 1.0× real time on the camera's own codec, resolution and bitrate | `decode-throughput`: encoded packets held in memory, decoded flat out | speed ≥ 1.0× |
| 2 | no backlog | arrival drift | lag growth < one step |
| 3 | regular predictions | prediction interval | p95 within 25% of `step_s` |
| 4 | no lost samples | samples received | received ≥ `seconds / step_s` |
| 5 | timestamp correctness | the stream's own presentation timestamps (`showinfo`) | strictly increasing within each connection, **and** ≥ 99% of spacings within 25% of `step_s` |
| **6a** | model-call latency | `session.run` alone (ONNX, CPU provider): the PRD's "MFSTNet ≤ 150 ms on server CPU via ONNX". Window stacking and softmax are outside it, because the PRD's scope does not include them | **p95 ≤ 150 ms** |
| **6b** | whole edge step | every `forecaster.step`: both backbones, the ring, and the model when the window is full | **p95 ≤ 1,000 ms** (half the 2 s step) **and max ≤ 2,000 ms** (no step longer than the sampling interval) |
| **6c** | transport | publish to the server's acknowledgement (`--server`) | **p95 ≤ 200 ms** (the PRD's MQTT budget, over the HTTP stand-in) |
| 7 | freshness at the consumer | `GET /prediction/{id}/latest`, every 1 s after the first prediction | ≥ 99% of polls at 10 s or less (the gate's bound, ADR-020) |

**For every latency part, p50, p90, p95, p99 and max are reported** beside the
pass statistic. The pass statistic is the one written here. No other
statistic is substituted after the run.

**Reported beside the criteria, never folded into them:**
- reconnect attempts and successes;
- windows lost to reconnects;
- arrival jitter.

## Hosts

Every latency figure states its measurement host (ADR-003): the CPU, the GPU
used for the backbones, and the ONNX execution provider. Laptop numbers are
proxy measurements for the edge device.

## Runs

| run | source | status |
|---|---|---|
| stand-in | a local footage file played at camera pace (`--realtime`), with a real local server | allowed now; labelled "stand-in"; does not close S65 |
| **real camera** | `STMS_CAMERA_URL`, a 300 s `decode-throughput` and a 600 s `run` with `--server` | in the confirmed camera window. **S65 closes only on this run** |

**Failure handling.**
- Any criterion that fails is reported as measured.
- A network failure is told apart from a pipeline failure by the reported
  jitter and reconnects.
- **No threshold changes after a real-camera result.**
