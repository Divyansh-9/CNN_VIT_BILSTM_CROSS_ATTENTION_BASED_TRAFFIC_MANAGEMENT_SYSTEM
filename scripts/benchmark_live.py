"""S65: the edge pipeline against a real camera stream (P89, ADR-026).

    set STMS_CAMERA_URL=rtsp://user:pass@camera/stream     (never on the command line)
    python scripts/benchmark_live.py capture --seconds 300 --out <dir>/camera.mp4
    python scripts/benchmark_live.py run --graph models/onnx/<selected>.onnx --seconds 600

`benchmark_decode.py` measured re-encoded files played from disk. A camera adds
what a file cannot: a network, a camera-side encoder, jitter, and disconnects.
This measures the same pipeline against the stream itself.

**The acceptance criteria are `benchmark_decode.py`'s, unchanged.**

1. *Decode at least 1.0x real time.* A live camera delivers at its own rate, so
   decode-only throughput cannot be measured against it. `capture` records the
   camera's own stream, copied rather than re-encoded, and
   `benchmark_decode.py file` measures criterion 1 on that recording — the real
   codec, resolution and bitrate. The criterion is moved to where it can be
   measured, not dropped.
2. *Lag growth under one step,* measured as arrival drift: sample k should
   arrive k × `step_s` after sample 0, and a growing excess is a backlog.
3. *Prediction interval p95 within 25% of `step_s`.*
4. *No lost sample:* samples received against `seconds / step_s`.

**Measured beside them, never folded into them:** reconnect attempts and
successes, windows lost to reconnects, and arrival jitter — the absolute
deviation of each inter-arrival from `step_s`.

**After a reconnect the window starts again.** A ring that straddles a gap
holds frames that are not T × `step_s` apart, and a prediction from it puts the
label at the wrong horizon (A15). So the ring is cleared, the next prediction
waits for a full window, and the windows lost are counted.

**No raw camera video is written to disk** (owner decision 2026-10-17,
NFR-13). `capture` refuses unless `--allow-disk-recording` is passed, and that
needs an explicit data-handling authorisation first. Criterion 1 is instead
measured by `decode-throughput`: it reads the stream's **encoded packets into
memory**, then decodes that buffer as fast as it can. The codec, resolution
and bitrate are the camera's own, and nothing touches disk.

**V2 adds three criteria** (PLAN-2026-10-17-validation-and-publication):

5. **Timestamp correctness.** The stream's own presentation timestamps, read
   from ffmpeg's `showinfo`, are strictly increasing within each connection.
   At least 99% of sample spacings are within 25% of `step_s`.
6. **End-to-end latency.** It runs from frame arrival, to prediction ready, to
   the server acknowledging it, with `--server` pointing at the real FastAPI
   server. Pass if processing p95 ≤ 150 ms (the PRD's MFSTNet budget, on
   **this** host; ADR-003) **and** transport p95 ≤ 200 ms (the PRD's MQTT
   budget, over the HTTP stand-in).
7. **Prediction freshness at the consumer.** `GET /prediction/{id}/latest` is
   polled every second. Pass if at least 99% of polls after the first
   prediction report an age of 10 s or less, the gate's freshness bound
   (ADR-020).

**Without `--server`,** criteria 6 (its transport part) and 7 are reported as
not measured, and V2 cannot pass.

**The camera URL is a secret.** It is read from an environment variable, never
accepted as an argument, never printed, and never written to the results or
their sidecar — only its scheme and host.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.benchmark_decode import (  # noqa: E402
    INTERVAL_TOLERANCE, MAX_LAG_GROWTH_S, ffmpeg, parse_probe)

URL_ENV = "STMS_CAMERA_URL"
RESULTS = Path("experiments/results/live_benchmark.csv")
BACKOFF_S = (1, 2, 4, 8, 10)
PTS = re.compile(r"pts_time:\s*([-0-9.]+)")


def redact(url: str) -> str:
    """scheme://host:port only — no credentials, path or query, which can
    carry tokens on some cameras."""
    # A local file has no "://". Testing the scheme instead would read a
    # Windows drive letter ("C:/...") as one.
    if "://" not in url:
        return Path(url).name
    parts = urlsplit(url)
    host = parts.hostname or "?"
    return f"{parts.scheme}://{host}" + (f":{parts.port}" if parts.port else "")


def source_url(env: str) -> str:
    url = os.environ.get(env, "").strip()
    if not url:
        raise SystemExit(f"set {env} to the camera's stream URL. It is read from "
                         f"the environment so it never reaches shell history.")
    return url


def input_args(url: str, *, realtime: bool) -> list[str]:
    args = []
    if url.startswith("rtsp://") or url.startswith("rtsps://"):
        # TCP so a lossy network shows up as delay rather than as corrupted
        # frames, and a socket timeout so a dead camera ends the read instead
        # of hanging it, which is what lets a reconnect happen.
        args += ["-rtsp_transport", "tcp", "-timeout", "5000000"]
    if realtime:
        args += ["-re"]                  # a file standing in for a camera
    return args + ["-i", url]


def probe_stream(url: str, *, realtime: bool) -> dict:
    out = subprocess.run([ffmpeg(), "-hide_banner", *input_args(url, realtime=False)],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=30).stderr
    return parse_probe(out)


SPACING_TOLERANCE, SPACING_SHARE = 0.25, 0.99
PROCESSING_P95_MS, TRANSPORT_P95_MS = 150.0, 200.0
FRESH_AGE_S, FRESH_SHARE = 10.0, 0.99


def _p95(values):
    return sorted(values)[int(0.95 * (len(values) - 1))] if values else None


def timestamp_report(segments: list[list[float]], step_s: float) -> dict:
    """Criterion 5, from the stream's own timestamps, one list per connection."""
    deltas = [b - a for seg in segments for a, b in zip(seg, seg[1:])]
    if not deltas:
        return {"c5_spacings": 0, "c5_monotonic": None, "c5_spacing_ok_share": None,
                "passed_5": False}
    ok = sum(abs(d - step_s) <= SPACING_TOLERANCE * step_s for d in deltas) / len(deltas)
    monotonic = all(d > 0 for d in deltas)
    return {"c5_spacings": len(deltas), "c5_monotonic": monotonic,
            "c5_spacing_ok_share": round(ok, 4),
            "passed_5": monotonic and ok >= SPACING_SHARE}


def latency_report(samples: list[tuple[float, float, float | None]]) -> dict:
    """Criterion 6 from (arrival, ready, acknowledged) times in seconds.

    `acknowledged` is None when no server was configured, and the transport
    part is then not measured.
    """
    processing = [(r - a) * 1000 for a, r, _ in samples]
    transport = [(k - r) * 1000 for _, r, k in samples if k is not None]
    total = [(k - a) * 1000 for a, _, k in samples if k is not None]
    measured = bool(transport) and len(transport) == len(samples)
    out = {"c6_predictions": len(samples),
           "c6_processing_p50_ms": round(statistics.median(processing), 1) if processing else None,
           "c6_processing_p95_ms": round(_p95(processing), 1) if processing else None,
           "c6_transport_p95_ms": round(_p95(transport), 1) if transport else None,
           "c6_total_p50_ms": round(statistics.median(total), 1) if total else None,
           "c6_total_p95_ms": round(_p95(total), 1) if total else None,
           "c6_total_max_ms": round(max(total), 1) if total else None,
           "c6_transport_measured": measured}
    out["passed_6"] = (measured and out["c6_processing_p95_ms"] is not None
                       and out["c6_processing_p95_ms"] <= PROCESSING_P95_MS
                       and out["c6_transport_p95_ms"] <= TRANSPORT_P95_MS)
    return out


def freshness_report(ages: list[float]) -> dict:
    """Criterion 7 from the ages the consumer saw, polled after the first prediction."""
    if not ages:
        return {"c7_polls": 0, "c7_fresh_share": None, "c7_age_p95_s": None, "passed_7": False}
    fresh = sum(a <= FRESH_AGE_S for a in ages) / len(ages)
    return {"c7_polls": len(ages), "c7_fresh_share": round(fresh, 4),
            "c7_age_p95_s": round(_p95(ages), 2), "passed_7": fresh >= FRESH_SHARE}


class HttpTransport:
    """The edge's prediction topic over the server's HTTP stand-in, timed.

    Same validation as MQTT ingest (`server.app.store_prediction`). `post` is
    injectable for tests. Failure raises ConnectionError, so the node reports
    the link down as it does for MQTT.
    """

    def __init__(self, server: str, intersection_id: str, post=None) -> None:
        self.url = f"{server.rstrip('/')}/prediction/{intersection_id}"
        self.post = post or self._post
        self.acknowledged: list[float] = []

    @staticmethod
    def _post(url: str, body: str) -> int:
        import urllib.request

        request = urllib.request.Request(url, data=body.encode("utf-8"), method="POST",
                                         headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status

    def publish(self, topic: str, payload: str, qos: int) -> None:
        if not topic.endswith("/congestion/prediction"):
            return                                   # only predictions are timed here
        try:
            status = self.post(self.url, payload)
        except OSError as error:
            raise ConnectionError(str(error)) from None
        if status != 200:
            raise ConnectionError(f"server answered {status}")
        self.acknowledged.append(time.perf_counter())


def poll_freshness(server: str, intersection_id: str, stop: threading.Event,
                   ages: list[float], started_after: threading.Event) -> None:
    """Every second until stopped: the age the consumer sees, by the server's clock."""
    import json as _json
    import urllib.request

    url = f"{server.rstrip('/')}/prediction/{intersection_id}/latest"
    while not stop.wait(1.0):
        if not started_after.is_set():
            continue
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                ages.append(float(_json.loads(response.read())["age_s"]))
        except OSError:
            ages.append(float("inf"))                # unreachable reads as not fresh


def decode_throughput(url: str, seconds: int, step_s: float, out: Path, *,
                      realtime: bool = False) -> int:
    """Criterion 1 without touching disk: encoded packets into RAM, then decode them flat out."""
    grab = [ffmpeg(), "-hide_banner", "-loglevel", "error",
            *input_args(url, realtime=realtime), "-t", str(seconds), "-an",
            "-c:v", "copy", "-f", "mpegts", "pipe:1"]
    received = subprocess.run(grab, capture_output=True)
    packets = received.stdout
    if not packets:
        raise SystemExit(f"no packets received (ffmpeg exit {received.returncode})")
    decode = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
              "-an", "-vf", f"fps=1/{step_s}", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    begun = time.perf_counter()
    decoded = subprocess.run(decode, input=packets, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    decode_s = time.perf_counter() - begun
    buffer_mb = len(packets) / 1e6
    del packets                                      # held in memory only; nothing persisted
    speed = seconds / decode_s if decode_s > 0 else float("inf")
    row = {"source": redact(url), "seconds": seconds, "buffer_mb": round(buffer_mb, 2),
           "decode_s": round(decode_s, 3), "speed_x_realtime": round(speed, 2),
           "decoder_exit": decoded.returncode, "on_disk": False,
           "passed_1": decoded.returncode == 0 and speed >= 1.0}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    from experiments.provenance import write_sidecar

    write_sidecar(out, source=redact(url), held_in_memory_only=True)
    print(f"  {seconds} s of packets ({buffer_mb:.1f} MB, memory only) decoded in "
          f"{decode_s:.2f} s: {speed:.2f}x real time -> criterion 1 "
          f"{'PASS' if row['passed_1'] else 'FAIL'}")
    return 0 if row["passed_1"] else 1


def capture(url: str, seconds: int, out: Path, *, allow_disk: bool = False) -> int:
    """Record the camera's stream as-is. Refused by default: no raw video on disk."""
    if not allow_disk:
        raise SystemExit("capture writes raw camera video to disk, which the owner's "
                         "2026-10-17 decision and NFR-13 do not permit. Use "
                         "`decode-throughput` (memory only). --allow-disk-recording "
                         "requires an explicit data-handling authorisation first.")
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
               *input_args(url, realtime=False), "-t", str(seconds),
               "-an", "-c:v", "copy", str(out)]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        # stderr can quote the URL; report the code, not the text.
        raise SystemExit(f"capture failed (ffmpeg exit {result.returncode})")
    info = parse_probe(subprocess.run(
        [ffmpeg(), "-hide_banner", "-i", str(out)], capture_output=True,
        text=True, encoding="utf-8", errors="replace").stderr)
    print(f"  captured {seconds} s from {redact(url)}: {info['codec']} "
          f"{info['width']}x{info['height']} @ {info['fps']}")
    print(f"  next: python scripts/benchmark_decode.py file --stream {out} "
          f"--graph <graph>   (criterion 1 on the camera's own codec)")
    return 0


def run(url: str, graph_path: Path, lanes: list[str], device: str,
        seconds: float, out: Path, *, realtime: bool = False,
        drop_at: float | None = None, server: str | None = None) -> int:
    import numpy as np

    from edge.forecaster import EdgeForecaster, VerifiedGraph
    from edge.node import EdgeNode, RecordingTransport
    from experiments.provenance import write_sidecar
    from scripts.device import resolve_device

    device = resolve_device(device)
    graph = VerifiedGraph.load(graph_path)
    step_s = float(graph.sidecar["step_s"])
    T = int(graph.sidecar["timesteps"])
    forecaster = EdgeForecaster(graph, dict(p.split("=", 1) for p in lanes),
                                timesteps=T, device=device)
    transport = HttpTransport(server, "live") if server else RecordingTransport()
    node = EdgeNode(intersection_id="live", transport=transport)
    info = probe_stream(url, realtime=realtime)
    width, height = info["width"], info["height"]
    frame_bytes = width * height * 3
    print(f"  source {redact(url)}: {info['codec']} {width}x{height} @ "
          f"{info['fps']}, {seconds:.0f} s, step {step_s} s")

    started = time.perf_counter()
    deadline = started + seconds
    arrivals, step_ms, predicted_at = [], [], []
    stamp_segments: list[list[float]] = []
    latency: list[tuple[float, float, float | None]] = []
    ages: list[float] = []
    stop_polling, first_prediction = threading.Event(), threading.Event()
    poller = None
    if server:
        poller = threading.Thread(target=poll_freshness, daemon=True,
                                  args=(server, "live", stop_polling, ages, first_prediction))
        poller.start()
    attempts = successes = windows_lost = 0
    dropped_once = False
    while time.perf_counter() < deadline:
        # showinfo reports each sampled frame's stream timestamp (criterion 5).
        # Only the numbers are parsed: stderr can quote the URL, and is never
        # printed or stored.
        command = [ffmpeg(), "-hide_banner", "-loglevel", "info",
                   *input_args(url, realtime=realtime), "-an",
                   "-vf", f"fps=1/{step_s},showinfo", "-f", "rawvideo",
                   "-pix_fmt", "bgr24", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=frame_bytes)
        segment: list[float] = []
        stamp_segments.append(segment)

        def read_stamps(stream=process.stderr, into=segment):
            for raw in stream:
                match = PTS.search(raw.decode("utf-8", "replace"))
                if match:
                    into.append(float(match.group(1)))

        threading.Thread(target=read_stamps, daemon=True).start()
        if drop_at is not None and not dropped_once:
            # Test-only: cut the connection once, to exercise the reconnect
            # path without a real network fault.
            timer = threading.Timer(max(0.0, started + drop_at - time.perf_counter()),
                                    process.kill)
            timer.daemon = True
            timer.start()
        got_frame = False
        while time.perf_counter() < deadline:
            buffer = process.stdout.read(frame_bytes)
            if len(buffer) < frame_bytes:
                break
            got_frame = True
            arrivals.append(time.perf_counter() - started)
            frame = np.frombuffer(buffer, np.uint8).reshape(height, width, 3)
            begun = time.perf_counter()
            prediction = forecaster.step(frame)
            if prediction is not None:
                ready = time.perf_counter()
                acked_before = len(getattr(transport, "acknowledged", []))
                node.publish_prediction(prediction)
                acks = getattr(transport, "acknowledged", [])
                latency.append((begun, ready, acks[-1] if len(acks) > acked_before else None))
                first_prediction.set()
                predicted_at.append(time.perf_counter() - started)
                step_ms.append((time.perf_counter() - begun) * 1000.0)
        process.kill()
        process.wait()
        if time.perf_counter() >= deadline:
            break
        dropped_once = dropped_once or drop_at is not None
        # Disconnected before the deadline. A window spanning the gap is not
        # T x step_s apart, so it is discarded, not predicted from.
        if any(len(r) for r in forecaster.rings.values()):
            windows_lost += 1
        forecaster.rings = {k: type(v)(maxlen=v.maxlen)
                            for k, v in forecaster.rings.items()}
        for wait in BACKOFF_S:
            attempts += 1
            time.sleep(wait)
            probe = subprocess.run(
                [ffmpeg(), "-hide_banner", *input_args(url, realtime=False)],
                capture_output=True, timeout=30)
            if b"Stream #" in probe.stderr:
                successes += 1
                break
        else:
            break                        # camera gone; stop and report
        _ = got_frame

    stop_polling.set()
    if poller is not None:
        poller.join(timeout=3)
    expected = int(seconds / step_s)
    intervals = [b - a for a, b in zip(predicted_at, predicted_at[1:])]
    inter_arrivals = [b - a for a, b in zip(arrivals, arrivals[1:])]
    jitter = [abs(x - step_s) for x in inter_arrivals]
    drift = [a - arrivals[0] - k * step_s for k, a in enumerate(arrivals)] \
        if arrivals else []

    def p95(values):
        return sorted(values)[int(0.95 * (len(values) - 1))] if values else None

    lag_growth = (drift[-1] - drift[0]) if len(drift) > 1 else float("inf")
    row = {
        "source": redact(url), "codec": info["codec"],
        "resolution": f"{width}x{height}", "stream_fps": info["fps"],
        "seconds": seconds, "samples": len(arrivals), "samples_expected": expected,
        "predictions": len(predicted_at),
        "lag_growth_s": round(lag_growth, 2),
        "interval_p95_s": round(p95(intervals), 3) if intervals else "",
        "step_ms_p95": round(p95(step_ms), 1) if step_ms else "",
        "jitter_ms_p50": round(statistics.median(jitter) * 1000, 1) if jitter else "",
        "jitter_ms_p95": round(p95(jitter) * 1000, 1) if jitter else "",
        "reconnect_attempts": attempts, "reconnect_successes": successes,
        "windows_lost_to_reconnect": windows_lost,
        "criterion_1": "measured by decode-throughput (memory only)",
        "server": redact(server) if server else "",
        **timestamp_report(stamp_segments, step_s),
        **latency_report(latency),
        **freshness_report(ages),
    }
    interval_ok = (row["interval_p95_s"] != ""
                   and abs(row["interval_p95_s"] - step_s) <= INTERVAL_TOLERANCE * step_s)
    row["passed_2_3_4"] = (lag_growth < MAX_LAG_GROWTH_S and interval_ok
                           and len(arrivals) >= expected)
    row["passed_2_to_7"] = (row["passed_2_3_4"] and row["passed_5"] and row["passed_6"]
                            and row["passed_7"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    write_sidecar(out, device=device, source=redact(url),
                  graph_sha256=graph.sidecar["graph_sha256"],
                  max_lag_growth_s=MAX_LAG_GROWTH_S,
                  interval_tolerance=INTERVAL_TOLERANCE,
                  simulated_drop_at_s=drop_at)

    print(f"  samples {len(arrivals)}/{expected}, predictions {len(predicted_at)}, "
          f"lag growth {row['lag_growth_s']} s, interval p95 "
          f"{row['interval_p95_s']} s, step p95 {row['step_ms_p95']} ms")
    print(f"  jitter p50 {row['jitter_ms_p50']} ms, p95 {row['jitter_ms_p95']} ms; "
          f"reconnects {successes}/{attempts}, windows lost {windows_lost}")
    print(f"  criteria 2-4: {'PASS' if row['passed_2_3_4'] else 'FAIL'}   "
          f"criterion 1: run benchmark_decode.py file on a capture")
    print(f"  criterion 5 timestamps: {'PASS' if row['passed_5'] else 'FAIL'} "
          f"(monotonic {row['c5_monotonic']}, spacing ok {row['c5_spacing_ok_share']})")
    print(f"  criterion 6 latency: {'PASS' if row['passed_6'] else 'FAIL'} (processing p95 "
          f"{row['c6_processing_p95_ms']} ms, transport p95 {row['c6_transport_p95_ms']} ms)")
    print(f"  criterion 7 freshness: {'PASS' if row['passed_7'] else 'FAIL'} "
          f"({row['c7_polls']} polls, fresh {row['c7_fresh_share']})")
    print(f"  wrote {out}")
    return 0 if row["passed_2_to_7"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url-env", default=URL_ENV,
                        help="environment variable holding the stream URL")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--seconds", type=int, default=300)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--allow-disk-recording", action="store_true",
                   help="only with an explicit data-handling authorisation (NFR-13)")
    d = sub.add_parser("decode-throughput", help="criterion 1, memory only")
    d.add_argument("--seconds", type=int, default=300)
    d.add_argument("--step-s", type=float, default=2.0)
    d.add_argument("--out", type=Path, default=Path("experiments/results/live_decode.csv"))
    d.add_argument("--realtime", action="store_true",
                   help="the source is a FILE standing in for a camera")
    r = sub.add_parser("run")
    r.add_argument("--graph", type=Path, required=True)
    r.add_argument("--lanes", nargs="+",
                   default=["lane_0=N", "lane_1=S", "lane_2=E", "lane_3=W"])
    r.add_argument("--device", default="cuda")
    r.add_argument("--seconds", type=float, default=600)
    r.add_argument("--out", type=Path, default=RESULTS)
    r.add_argument("--realtime", action="store_true",
                   help="the source is a FILE standing in for a camera; play "
                        "it at its real rate. Never for a real stream")
    r.add_argument("--simulate-drop-at", type=float, default=None,
                   help="test only: cut the connection once at this many seconds")
    r.add_argument("--server", help="FastAPI server base URL; needed for criteria 6 and 7")
    args = parser.parse_args(argv)
    url = source_url(args.url_env)
    if args.command == "capture":
        return capture(url, args.seconds, args.out, allow_disk=args.allow_disk_recording)
    if args.command == "decode-throughput":
        return decode_throughput(url, args.seconds, args.step_s, args.out,
                                 realtime=args.realtime)
    return run(url, args.graph, args.lanes, args.device, args.seconds, args.out,
               realtime=args.realtime, drop_at=args.simulate_drop_at, server=args.server)


if __name__ == "__main__":
    raise SystemExit(main())
