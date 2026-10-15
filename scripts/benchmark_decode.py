"""The live-camera pipeline at deployment resolution, decode included (P89).

    python scripts/benchmark_decode.py prepare --work <dir>
    python scripts/benchmark_decode.py run --work <dir> --graph models/onnx/<selected>.onnx

`verify_edge.py` times a step from an already-decoded frame. P89 found that
leaves out the stage most likely to fail in deployment: decoding the camera's
stream, every frame, in real time — sampling one frame every 2 s does not let a
decoder skip the others. This script measures exactly that, two ways.

**1. Decode-only throughput.** ffmpeg decodes each stream to nothing as fast as
it can, in software and on the GPU (NVDEC). Reported as frames per second and
as a multiple of real time.

**2. The sustained live pipeline.** ffmpeg plays the stream at its real rate
(`-re`), as a camera would deliver it, and hands Python one frame every
`step_s`. Each frame goes through `EdgeForecaster` — the shared preprocessing,
both backbones, the verified graph — and the prediction is published. A camera
does not wait for a slow consumer, so the measure is **lag**: when sample k
arrives, against when it would arrive at real time. A pipeline that keeps up has
bounded lag. One that does not has lag that grows without limit, which on a
live stream means dropped frames.

**Test streams.** The corpus clip is AV1, YouTube's re-encode of a 4K upload.
Surveillance cameras emit H.264 or H.265 instead, so `prepare` cuts one segment
of the same footage and encodes it the way a camera would: H.264 at 4K and at
1080p, one-second GOP, constant bitrate. The original AV1 segment is kept as
the worst case.

**Pass criteria, fixed before the first run:**

- decode-only throughput at least 1.0x real time;
- across the sustained run, lag grows by less than one step from the first
  prediction to the last (`MAX_LAG_GROWTH_S`);
- the interval between consecutive predictions has p95 within 25% of `step_s`;
- no sample is lost.

A configuration passes only if all four hold.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

SOURCE = Path("data/_corpus_clips/🎧 Incredible traffic Sound in Dhaka, "
              "Bangladesh। Rampura [4K ASMR] #TheSoundOfDhaka.mp4")
RESULTS = Path("experiments/results/decode_benchmark.csv")
SEGMENT_START_S, SEGMENT_S = 60, 300
MAX_LAG_GROWTH_S = 2.0
INTERVAL_TOLERANCE = 0.25

#: name -> (width, height, encoder arguments). One-second GOP and CBR are what
#: a surveillance camera's default profile looks like.
STREAMS = {
    "av1_4k_original": None,
    "h264_4k": (3840, 2160, ["-c:v", "h264_nvenc", "-b:v", "16M", "-maxrate",
                             "16M", "-bufsize", "16M", "-g", "30", "-bf", "0"]),
    "h264_1080p": (1920, 1080, ["-c:v", "h264_nvenc", "-b:v", "6M", "-maxrate",
                                "6M", "-bufsize", "6M", "-g", "30", "-bf", "0"]),
}
#: Which decoder configurations to run against which stream.
RUNS = [
    ("av1_4k_original", "software"), ("av1_4k_original", "nvdec"),
    ("h264_4k", "software"), ("h264_4k", "nvdec"),
    ("h264_1080p", "software"),
]


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_probe(stderr: str) -> dict:
    """Codec, size and rate from ffmpeg's banner, read off the stream line.

    Not from the first line mentioning "Video:" — a clip's embedded title can
    contain the word, and the corpus's 4K Rampura clip's does.
    """
    video = next(l for l in stderr.splitlines()
                 if l.strip().startswith("Stream #") and "Video:" in l)
    size = re.search(r", (\d{3,5})x(\d{3,5})", video)
    fps = re.search(r"([\d.]+) fps", video)
    codec = re.search(r"Video: (\w+)", video)
    length = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr)
    duration = (int(length.group(1)) * 3600 + int(length.group(2)) * 60
                + float(length.group(3))) if length else None
    return {"width": int(size.group(1)), "height": int(size.group(2)),
            "fps": float(fps.group(1)), "codec": codec.group(1),
            "duration_s": duration}


def probe(path: Path) -> dict:
    out = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace").stderr
    return parse_probe(out)


def prepare(work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    for name, spec in STREAMS.items():
        out = work / f"{name}.mp4"
        if out.exists():
            print(f"  {name}: exists")
            continue
        command = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", str(SEGMENT_START_S), "-t", str(SEGMENT_S),
                   "-i", str(SOURCE), "-an", "-map", "0:v:0",
                   "-map_metadata", "-1"]
        if spec is None:
            command += ["-c:v", "copy"]
        else:
            width, height, encoder = spec
            command += ["-vf", f"scale={width}:{height}", *encoder]
        subprocess.run(command + [str(out)], check=True)
        info = probe(out)
        print(f"  {name}: {info['codec']} {info['width']}x{info['height']} "
              f"{info['fps']} fps, {out.stat().st_size / 1e6:.0f} MB")


def decoder_args(decoder: str) -> list[str]:
    # NVDEC decodes on the GPU and copies each frame back to system memory,
    # which is the cost a CPU-side pipeline actually pays.
    return ["-hwaccel", "cuda"] if decoder == "nvdec" else []


def decode_only(path: Path, decoder: str) -> dict:
    command = [ffmpeg(), "-hide_banner", "-benchmark", *decoder_args(decoder),
               "-i", str(path), "-an", "-f", "null", "-"]
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - started
    frames = [int(m) for m in re.findall(r"frame=\s*(\d+)", result.stderr)]
    if result.returncode != 0 or not frames:
        return {"decode_fps": "", "decode_error": result.stderr.strip()[-200:]}
    return {"decode_fps": round(frames[-1] / elapsed, 1), "decode_error": ""}


def sustained(path: Path, decoder: str, forecaster, node, step_s: float) -> dict:
    info = probe(path)
    width, height = info["width"], info["height"]
    frame_bytes = width * height * 3
    command = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-re",
               *decoder_args(decoder), "-i", str(path), "-an",
               "-vf", f"fps=1/{step_s}", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "pipe:1"]
    import numpy as np

    forecaster.rings = {k: type(v)(maxlen=v.maxlen)
                        for k, v in forecaster.rings.items()}
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, bufsize=frame_bytes)
    started = time.perf_counter()
    lags, step_ms, predicted_at = [], [], []
    samples = 0
    while True:
        buffer = process.stdout.read(frame_bytes)
        if len(buffer) < frame_bytes:
            break
        arrived = time.perf_counter() - started
        frame = np.frombuffer(buffer, np.uint8).reshape(height, width, 3)
        begun = time.perf_counter()
        prediction = forecaster.step(frame)
        done = time.perf_counter()
        if prediction is not None:
            node.publish_prediction(prediction)
            predicted_at.append(done - started)
            step_ms.append((done - begun) * 1000.0)
            lags.append(done - started - samples * step_s)
        samples += 1
    process.wait()
    # From the stream's own duration, so a camera capture of any length is
    # held to the same no-lost-sample criterion as the prepared segments.
    expected = int((info["duration_s"] or SEGMENT_S) / step_s)
    intervals = [b - a for a, b in zip(predicted_at, predicted_at[1:])]
    growth = (lags[-1] - lags[0]) if len(lags) > 1 else float("inf")
    return {
        "samples": samples, "samples_expected": expected,
        "predictions": len(predicted_at),
        "lag_first_s": round(lags[0], 2) if lags else "",
        "lag_last_s": round(lags[-1], 2) if lags else "",
        "lag_growth_s": round(growth, 2),
        "interval_p50_s": round(statistics.median(intervals), 3) if intervals else "",
        "interval_p95_s": (round(sorted(intervals)[int(0.95 * (len(intervals) - 1))], 3)
                           if intervals else ""),
        "step_ms_p95": (round(sorted(step_ms)[int(0.95 * (len(step_ms) - 1))], 1)
                        if step_ms else ""),
    }


def run(work: Path, graph_path: Path, lanes: list[str], device: str,
        out: Path, runs: list[tuple[Path, str, str]] | None = None) -> int:
    """`runs` is (path, stream name, decoder); by default the prepared set."""
    from edge.forecaster import EdgeForecaster, VerifiedGraph
    from edge.node import EdgeNode, RecordingTransport
    from experiments.provenance import write_sidecar
    from scripts.device import resolve_device

    device = resolve_device(device)
    graph = VerifiedGraph.load(graph_path)
    step_s = float(graph.sidecar["step_s"])
    mapping = dict(pair.split("=", 1) for pair in lanes)
    forecaster = EdgeForecaster(graph, mapping,
                                timesteps=int(graph.sidecar["timesteps"]),
                                device=device)
    node = EdgeNode(intersection_id="bench", transport=RecordingTransport())

    rows = []
    runs = runs or [(work / f"{s}.mp4", s, d) for s, d in RUNS]
    for path, stream, decoder in runs:
        info = probe(path)
        print(f"\n  {stream} ({info['codec']} {info['width']}x{info['height']} "
              f"@ {info['fps']}) — {decoder}")
        row = {"stream": stream, "codec": info["codec"],
               "resolution": f"{info['width']}x{info['height']}",
               "stream_fps": info["fps"], "decoder": decoder}
        row.update(decode_only(path, decoder))
        realtime = (row["decode_fps"] / info["fps"]) if row["decode_fps"] else 0.0
        row["decode_x_realtime"] = round(realtime, 2)
        print(f"    decode only: {row['decode_fps']} fps = {realtime:.2f}x real time"
              + (f"  ERROR {row['decode_error']}" if row["decode_error"] else ""))
        if row["decode_error"]:
            row["passed"] = False
            rows.append(row)
            continue
        row.update(sustained(path, decoder, forecaster, node, step_s))
        interval_ok = (row["interval_p95_s"] != "" and
                       abs(row["interval_p95_s"] - step_s) <= INTERVAL_TOLERANCE * step_s)
        row["passed"] = (realtime >= 1.0
                         and row["lag_growth_s"] < MAX_LAG_GROWTH_S
                         and interval_ok
                         and row["samples"] >= row["samples_expected"])
        print(f"    sustained {SEGMENT_S} s at real time: {row['samples']}/"
              f"{row['samples_expected']} samples, {row['predictions']} predictions, "
              f"lag {row['lag_first_s']} -> {row['lag_last_s']} s "
              f"(growth {row['lag_growth_s']} s), interval p95 "
              f"{row['interval_p95_s']} s, step p95 {row['step_ms_p95']} ms")
        print(f"    {'PASS' if row['passed'] else 'FAIL'}")
        rows.append(row)

    out.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k)
                    if k in rows[0] else 99)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    write_sidecar(out, device=device, graph=str(graph_path),
                  graph_sha256=graph.sidecar["graph_sha256"],
                  segment_start_s=SEGMENT_START_S, segment_s=SEGMENT_S,
                  source=str(SOURCE), max_lag_growth_s=MAX_LAG_GROWTH_S,
                  interval_tolerance=INTERVAL_TOLERANCE)
    print(f"\n  wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--work", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--graph", type=Path, required=True)
    r.add_argument("--lanes", nargs="+",
                   default=["lane_0=N", "lane_1=S", "lane_2=E", "lane_3=W"])
    r.add_argument("--device", default="cuda")
    r.add_argument("--out", type=Path, default=RESULTS)
    f = sub.add_parser("file", help="the same criteria on one recording, e.g. "
                                    "a capture from the real camera (S65)")
    f.add_argument("--stream", type=Path, required=True)
    f.add_argument("--graph", type=Path, required=True)
    f.add_argument("--lanes", nargs="+",
                   default=["lane_0=N", "lane_1=S", "lane_2=E", "lane_3=W"])
    f.add_argument("--device", default="cuda")
    f.add_argument("--decoders", nargs="+", default=["software", "nvdec"])
    f.add_argument("--out", type=Path,
                   default=Path("experiments/results/decode_benchmark_capture.csv"))
    args = parser.parse_args(argv)
    if args.command == "file":
        return run(args.stream.parent, args.graph, args.lanes, args.device,
                   args.out, runs=[(args.stream, args.stream.stem, d)
                                   for d in args.decoders])
    if args.command == "prepare":
        prepare(args.work)
        return 0
    return run(args.work, args.graph, args.lanes, args.device, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
