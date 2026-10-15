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

**The camera URL is a secret.** It is read from an environment variable, never
accepted as an argument, never printed, and never written to the results or
their sidecar — only its scheme and host.
"""

from __future__ import annotations

import argparse
import csv
import os
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


def capture(url: str, seconds: int, out: Path) -> int:
    """Record the camera's stream as-is, for criterion 1 on the real codec."""
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
        drop_at: float | None = None) -> int:
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
    node = EdgeNode(intersection_id="live", transport=RecordingTransport())
    info = probe_stream(url, realtime=realtime)
    width, height = info["width"], info["height"]
    frame_bytes = width * height * 3
    print(f"  source {redact(url)}: {info['codec']} {width}x{height} @ "
          f"{info['fps']}, {seconds:.0f} s, step {step_s} s")

    started = time.perf_counter()
    deadline = started + seconds
    arrivals, step_ms, predicted_at = [], [], []
    attempts = successes = windows_lost = 0
    dropped_once = False
    while time.perf_counter() < deadline:
        command = [ffmpeg(), "-hide_banner", "-loglevel", "error",
                   *input_args(url, realtime=realtime), "-an",
                   "-vf", f"fps=1/{step_s}", "-f", "rawvideo",
                   "-pix_fmt", "bgr24", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, bufsize=frame_bytes)
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
                node.publish_prediction(prediction)
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
        "criterion_1": "measured on a capture: benchmark_decode.py file",
    }
    interval_ok = (row["interval_p95_s"] != ""
                   and abs(row["interval_p95_s"] - step_s) <= INTERVAL_TOLERANCE * step_s)
    row["passed_2_3_4"] = (lag_growth < MAX_LAG_GROWTH_S and interval_ok
                           and len(arrivals) >= expected)
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
    print(f"  wrote {out}")
    return 0 if row["passed_2_3_4"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url-env", default=URL_ENV,
                        help="environment variable holding the stream URL")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--seconds", type=int, default=300)
    c.add_argument("--out", type=Path, required=True)
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
    args = parser.parse_args(argv)
    url = source_url(args.url_env)
    if args.command == "capture":
        return capture(url, args.seconds, args.out)
    return run(url, args.graph, args.lanes, args.device, args.seconds, args.out,
               realtime=args.realtime, drop_at=args.simulate_drop_at)


if __name__ == "__main__":
    raise SystemExit(main())
