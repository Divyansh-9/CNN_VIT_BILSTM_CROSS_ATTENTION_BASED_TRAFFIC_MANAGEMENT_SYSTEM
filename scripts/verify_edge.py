"""Frames to server, through the verified graph — the S61 deployment check.

    python scripts/verify_edge.py --graph models/onnx/<selected>.onnx \\
        --lanes lane_0=N lane_1=S lane_2=E lane_3=W --device cuda

This is the end-to-end test, with no step stubbed:

1. the test camera's **actual video** is decoded on the edge at the corpus's
   sampling stride;
2. every frame goes through `EdgeForecaster` — shared preprocessing, both
   backbones, fp16 rounding, the ring buffer, the verified ONNX graph;
3. each prediction is published by `EdgeNode` through a recording transport,
   which is what the MQTT client would carry;
4. each published payload is posted to the server's `/prediction` endpoint and
   read back from `/prediction/{id}/latest`.

**What passes.** The edge's decisions are compared with the per-window
predictions training committed for the same run (P59) — the model's decisions
on the same windows, computed from the cache. Agreement must reach
`MIN_AGREEMENT`; it cannot be required to be exact, because the edge recomputes
features from video on possibly a different device than the cache was built
on, and a near-tie can flip (P39). And every prediction the server stores must
name the verified graph and equal what the edge published.

**What is measured on the same pass**, because ADR-026's condition is that the
edge meets its budget: per-step feature extraction, head inference and total
time; cold-start time for the first full window; peak GPU memory and process
memory; and sustained throughput against the real-time requirement — one step
must finish inside `step_s`, with `HEADROOM` to spare.

Results go to `experiments/results/edge_verification.csv` with a sidecar.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

MIN_AGREEMENT = 0.99
#: p95 per-step time must stay under this fraction of `step_s`. Half the step
#: is left for detection, counting and the link, which share the same laptop.
HEADROOM = 0.5
RESULTS = Path("experiments/results/edge_verification.csv")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1) + 0.5))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--lanes", nargs="+", required=True,
                        help="lane=approach pairs, e.g. lane_0=N; none is "
                             "assumed (PPO indices 11-14 are N S E W)")
    parser.add_argument("--clips", type=Path, default=Path("data/_corpus_clips"))
    parser.add_argument("--results", type=Path,
                        default=Path("experiments/results/loco_foreign"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--broker", default=None, metavar="HOST:PORT",
                        help="deliver the predictions over live MQTT to this "
                             "broker, received by server/mqtt_ingest.py, "
                             "instead of the HTTP stand-in")
    args = parser.parse_args(argv)

    import cv2
    import psutil
    import torch
    from fastapi.testclient import TestClient

    import server.app as server
    from edge.forecaster import EdgeForecaster, VerifiedGraph
    from edge.node import EdgeNode, RecordingTransport
    from experiments.provenance import write_sidecar
    from mfstnet.corpus.video import iter_sampled_frames
    from scripts.device import resolve_device
    from scripts.train_mfstnet import load_corpus

    device = resolve_device(args.device)
    graph = VerifiedGraph.load(args.graph)          # refuses unverified graphs
    meta = graph.sidecar
    mapping = dict(pair.split("=", 1) for pair in args.lanes)
    T, step_s = int(meta["timesteps"]), float(meta["step_s"])

    ckpt = torch.load(meta["checkpoint"], map_location="cpu",
                      weights_only=True)["meta"]
    rows, manifest = load_corpus(Path(ckpt["corpus"]))
    test = [r for r in rows if r["split"] == "test"]
    clips = sorted({r["clip_id"] for r in test})
    pattern = (f"fold{meta['fold']}_seed{meta['seed']}_{meta['config']}_"
               f"{meta['config']}.predictions.csv")
    with (args.results / pattern).open(encoding="utf-8") as handle:
        committed = {(r["clip_id"], int(r["start_index"]), r["lane"]): r["pred"]
                     for r in csv.DictReader(handle)}
    wanted = {(r["clip_id"], int(r["start_index"])) for r in test}

    forecaster = EdgeForecaster(graph, mapping, timesteps=T, device=device)
    transport = RecordingTransport()
    node = EdgeNode(intersection_id="verify", transport=transport)
    approach_of = forecaster.lane_to_approach

    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    process = psutil.Process()
    feature_ms, head_ms, step_ms = [], [], []
    agree = total = published = 0
    cold_start_ms = None

    # By stem, as build_cache.py does. A glob on the name would read "[4K
    # ASMR]" in a Dhaka title as a character class and match nothing.
    videos = {p.stem: p for p in args.clips.rglob("*.mp4")}
    for clip in clips:
        video = videos.get(clip)
        if video is None:
            raise SystemExit(f"no video for test clip {clip[:50]}")
        probe = cv2.VideoCapture(str(video))
        fps = probe.get(cv2.CAP_PROP_FPS) or 25.0
        probe.release()
        stride = max(1, int(round(fps * step_s)))   # as build_cache.py
        forecaster.rings = {k: type(v)(maxlen=T) for k, v in
                            forecaster.rings.items()}
        clip_started = time.perf_counter()
        last_start = max(s for c, s in wanted if c == clip)
        for index, frame in enumerate(iter_sampled_frames(video, stride)):
            started = time.perf_counter()
            features = forecaster.features(frame)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            extracted = time.perf_counter()
            forecaster.push(features)
            if not forecaster.ready:
                continue
            prediction = forecaster.predict()
            done = time.perf_counter()
            if cold_start_ms is None:
                cold_start_ms = (done - clip_started) * 1000.0
            feature_ms.append((extracted - started) * 1000.0)
            head_ms.append((done - extracted) * 1000.0)
            step_ms.append((done - started) * 1000.0)

            start = index - T + 1
            if (clip, start) in wanted:
                for lane in forecaster.lanes:
                    agree += (prediction.predictions[approach_of[lane]].value
                              == committed[(clip, start, lane)])
                    total += 1
                node.publish_prediction(prediction)
                published += 1
            if start >= last_start:
                break

    # Server side. The edge loop above publishes into a recording transport so
    # that step timing measures inference, not the network. The recorded
    # payloads — exactly what the edge produced — are then delivered either
    # over live MQTT (--broker) or through the HTTP stand-in.
    predictions_sent = [(t, p, q) for t, p, q in transport.sent
                        if t.endswith("/congestion/prediction")]
    last_sent = predictions_sent[-1][1] if predictions_sent else None
    mqtt_publish_ms: list[float] = []
    sent_at: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        server.DATABASE = Path(tmp) / "verify.sqlite"
        client = TestClient(server.app)
        mismatched = 0
        if args.broker:
            from edge.mqtt_transport import MqttTransport
            from server.mqtt_ingest import PredictionIngest

            host, port = args.broker.rsplit(":", 1)
            ingest = PredictionIngest(host, int(port),
                                      client_id="verify-ingest")
            live = MqttTransport(host, int(port), client_id="verify-edge")
            try:
                if not ingest.start():
                    raise SystemExit(f"server could not subscribe at {args.broker}")
                if not live.start():
                    raise SystemExit(f"edge could not connect to {args.broker}")
                for index, (topic, payload, qos) in enumerate(predictions_sent):
                    # Paced at the real step interval: the edge sends one
                    # prediction per step_s, and a back-to-back replay queues
                    # each message behind the last one's store and reports a
                    # delivery time the deployment would never see.
                    if index:
                        time.sleep(max(0.0, step_s - (time.perf_counter()
                                                      - sent_at[-1])))
                    started = time.perf_counter()
                    sent_at.append(started)
                    live.publish(topic, payload, qos)
                    mqtt_publish_ms.append((time.perf_counter() - started) * 1000.0)
                deadline = time.time() + 15
                while ingest.stored + len(ingest.refused) < len(predictions_sent)                         and time.time() < deadline:
                    time.sleep(0.05)
            finally:
                live.stop()
                ingest.stop()
            if ingest.refused:
                raise SystemExit(f"server refused {len(ingest.refused)} "
                                 f"prediction(s): {ingest.refused[:2]}")
            if ingest.stored != len(predictions_sent):
                raise SystemExit(f"server stored {ingest.stored} of "
                                 f"{len(predictions_sent)} published")
            # Delivery: edge send to server store, per message, one clock.
            # QoS 0 over one TCP connection from one publisher keeps order,
            # so the i-th arrival is the i-th send.
            delivery_ms = [(a - b) * 1000.0
                           for a, b in zip(ingest.arrivals, sent_at)]
            with server.closing(server.connect()) as connection:
                models = [r[0] for r in connection.execute(
                    "SELECT model FROM predictions")]
            mismatched = sum(m != graph.model_id for m in models)
        else:
            for topic, payload, _qos in predictions_sent:
                response = client.post("/prediction/verify", content=payload,
                                       headers={"content-type": "text/plain"})
                if response.status_code != 200:
                    raise SystemExit(f"server refused a prediction: {response.text}")
                if response.json()["model"] != graph.model_id:
                    mismatched += 1
        latest = client.get("/prediction/verify/latest").json()

    # /latest must return the last prediction the edge made, not merely one
    # with the right model name.
    from contracts.mqtt import Topic, decode
    expected = decode(Topic.PREDICTION, last_sent) if last_sent else None
    latest_matches = bool(expected) and latest.get("predictions") == {
        k: v.value for k, v in expected.predictions.items()}

    agreement = agree / total if total else 0.0
    p95 = percentile(step_ms, 0.95)
    budget = HEADROOM * step_s * 1000.0
    row = {
        "graph": str(args.graph), "model_id": graph.model_id,
        "device": device, "windows_compared": total // len(forecaster.lanes),
        "decisions_compared": total, "agreement_with_committed": round(agreement, 4),
        "published": published, "server_model_mismatches": mismatched,
        "server_latest_model": latest.get("model"),
        "feature_ms_p50": round(statistics.median(feature_ms), 1),
        "feature_ms_p95": round(percentile(feature_ms, 0.95), 1),
        "head_ms_p50": round(statistics.median(head_ms), 1),
        "head_ms_p95": round(percentile(head_ms, 0.95), 1),
        "step_ms_p50": round(statistics.median(step_ms), 1),
        "step_ms_p95": round(p95, 1),
        "step_budget_ms": round(budget, 1), "step_s": step_s,
        "cold_start_ms": round(cold_start_ms or 0.0, 1),
        "sustained_steps_per_s": round(1000.0 / statistics.mean(step_ms), 2),
        "peak_gpu_mb": (round(torch.cuda.max_memory_allocated() / 2**20, 1)
                        if device.startswith("cuda") else ""),
        "process_rss_mb": round(process.memory_info().rss / 2**20, 1),
    }
    row["path"] = "mqtt" if args.broker else "http"
    row["latest_matches_last_published"] = latest_matches
    row["mqtt_publish_ms_p95"] = (round(percentile(mqtt_publish_ms, 0.95), 2)
                              if mqtt_publish_ms else "")
    delivery = delivery_ms if args.broker else []
    row["delivery_ms_p50"] = (round(statistics.median(delivery), 1)
                              if delivery else "")
    row["delivery_ms_p95"] = (round(percentile(delivery, 0.95), 1)
                              if delivery else "")
    passed = (agreement >= MIN_AGREEMENT and mismatched == 0
              and latest.get("model") == graph.model_id and latest_matches
              and p95 <= budget)
    row["passed"] = passed

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    write_sidecar(args.out, device=device, graph_sha256=meta["graph_sha256"],
                  lane_to_approach=mapping, min_agreement=MIN_AGREEMENT,
                  headroom=HEADROOM)

    print(f"\n  {row['windows_compared']} windows from real video, "
          f"{total} lane decisions")
    print(f"    agreement with committed predictions  {agreement:.4f} "
          f"(needs {MIN_AGREEMENT})")
    print(f"    published {published} over {row['path']}, server stored model "
          f"{latest.get('model')}, mismatches {mismatched}, /latest equals the "
          f"last published: {latest_matches}"
          )
    if mqtt_publish_ms:
        print(f"    MQTT, three separate numbers: local send p95 "
              f"{row['mqtt_publish_ms_p95']} ms (QoS 0, no broker ack); "
              f"edge send to server store p50 {row['delivery_ms_p50']} ms, "
              f"p95 {row['delivery_ms_p95']} ms; inference is the step time below")
    print(f"    per step: features p50 {row['feature_ms_p50']} ms, head p50 "
          f"{row['head_ms_p50']} ms, total p95 {row['step_ms_p95']} ms "
          f"(budget {budget:.0f} ms of a {step_s:.0f} s step)")
    print(f"    cold start {row['cold_start_ms']} ms, peak GPU "
          f"{row['peak_gpu_mb']} MB, RSS {row['process_rss_mb']} MB")
    print(f"\n  {'PASS' if passed else 'FAIL'}  wrote {args.out}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
