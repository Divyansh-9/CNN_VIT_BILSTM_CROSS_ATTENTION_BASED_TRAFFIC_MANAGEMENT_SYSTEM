"""P99a — per-lane counting accuracy of candidate detectors against hand counts.

    python scripts/detector_benchmark.py

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P99a.md`. The
candidates, classes, operating points, metric and decision rule are all fixed
there; nothing is chosen in this file.

The reference detector is run first through the same harness and must
reproduce the corpus's committed counts exactly. A harness that cannot
reproduce the detector that built the corpus would score every candidate
against the wrong frames or regions, so it stops instead.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_bellevue")
VIDEO = Path("data/_bellevue/joined/Bellevue_NE8th_2017-09-11_15-08_to_17-08.mp4")
STRIDE = 60
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "south", "lane_3": "east"}
PRIMARY = ("lane_0", "lane_1", "lane_3")
COCO_VEHICLES = {"bicycle", "car", "motorcycle", "bus", "truck"}
SYMBOL = (0.20, 0.73)
RESAMPLES = 10_000
TIE = 0.05
CANDIDATES = {
    "R": ("models/external/best_xl_ITD_v1.2.pt", 992, 0.45),
    "S640": ("models/external/yolov8s.pt", 640, 0.25),
    "M640": ("models/external/yolov8m.pt", 640, 0.25),
    "X640": ("models/external/yolov8x.pt", 640, 0.25),
    "S1280": ("models/external/yolov8s.pt", 1280, 0.25),
    "M1280": ("models/external/yolov8m.pt", 1280, 0.25),
    "X1280": ("models/external/yolov8x.pt", 1280, 0.25),
}
SIZE_ORDER = {"S": 0, "M": 1, "X": 2}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frames_and_hand():
    samples = set(json.load(open(ROOT / "audit_frames.json"))["samples"])
    samples |= set(json.load(open(ROOT / "audit_frames_2.json"))["samples"])
    hand = {}
    for name in ("audit_manual.json", "audit_manual_2.json"):
        for f in json.loads((ROOT / name).read_text(encoding="utf-8"))["frames"]:
            hand[int(f["sample"])] = {lane: int(f[lane]) for lane in LANES}
    assert samples == set(hand), "every audited frame must have a hand count"

    from mfstnet.corpus.video import iter_sampled_frames

    wanted, frames = sorted(samples), {}
    for index, frame in enumerate(iter_sampled_frames(VIDEO, STRIDE,
                                                      limit=wanted[-1] + 1)):
        if index in samples:
            frames[index] = frame
    assert set(frames) == samples
    return wanted, frames, hand


def count(model, frames, lanes, imgsz, conf, is_reference):
    from mfstnet.corpus.counting import Detection, count_frame
    from scripts.pilot_a17 import vehicle_ids

    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    ids = (vehicle_ids(model) if is_reference
           else {i for i, n in names.items() if n in COCO_VEHICLES})
    out, symbol, elapsed = {}, 0, []
    for k, frame in frames.items():
        start = time.perf_counter()
        result = model.predict(source=frame, conf=conf, imgsz=imgsz, verbose=False)[0]
        elapsed.append(time.perf_counter() - start)
        height, width = result.orig_shape
        detections = [Detection(cls=names[int(c)], confidence=float(p),
                                x1=b[0] / width, y1=b[1] / height,
                                x2=b[2] / width, y2=b[3] / height)
                      for b, c, p in zip(result.boxes.xyxy.tolist(),
                                         result.boxes.cls.tolist(),
                                         result.boxes.conf.tolist())
                      if int(c) in ids]
        counts = count_frame(detections, lanes, min_confidence=conf)
        out[k] = {lane: counts.per_lane.get(lane, 0) for lane in LANES}
        symbol += any(d.cls == "bicycle"
                      and abs(d.centroid[0] - SYMBOL[0]) ** 2
                      + abs(d.centroid[1] - SYMBOL[1]) ** 2 < 0.06 ** 2
                      for d in detections)
    # The first call includes CUDA warm-up; the median ignores it.
    return out, symbol, statistics.median(elapsed) * 1000


def lane_stats(h, d):
    from scripts.compare_audit_combined import pearson

    err = [b - a for a, b in zip(h, d)]
    total = sum(h)
    return {"mae": round(statistics.mean(abs(e) for e in err), 3),
            "signed": round(statistics.mean(err), 3),
            "undercount": round(1 - sum(d) / total, 3) if total else None,
            "exact": round(sum(e == 0 for e in err) / len(err), 3),
            "pearson": round(pearson(h, d), 3)}


def mae3(frames, hand, det):
    return statistics.mean(abs(det[k][lane] - hand[k][lane])
                           for k in frames for lane in PRIMARY)


def main() -> int:
    from ultralytics import YOLO

    import torch

    from mfstnet.corpus.lanes import LaneCentres

    # Not resolve_device(): every detector runs on Ultralytics' default device,
    # exactly as build_corpus ran the reference, or the harness check would be
    # comparing two devices rather than two harnesses. Recorded, not chosen.
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    lanes = LaneCentres(names=tuple(c["name"] for c in manifest["lane_centres"]),
                        centres=tuple(tuple(c["centre"]) for c in manifest["lane_centres"]),
                        max_radius=float(manifest["max_radius"]))
    assert lanes.names == tuple(LANES), lanes.names
    order, frames, hand = frames_and_hand()

    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        built = {int(r["sample"]): {lane: int(r["count_" + lane]) for lane in LANES}
                 for r in csv.DictReader(handle) if int(r["sample"]) in hand}

    results, counts = {}, {}
    for cid, (weights, imgsz, conf) in CANDIDATES.items():
        path = Path(weights)
        model = YOLO(str(path))
        det, symbol, ms = count(model, frames, lanes, imgsz, conf, cid == "R")
        if cid == "R":
            mismatched = [k for k in order if det[k] != built[k]]
            if mismatched:
                raise SystemExit(f"harness check FAILED: R differs from the corpus on "
                                 f"{len(mismatched)} of {len(order)} frames, e.g. "
                                 f"{mismatched[:3]}. Nothing is reported.")
            print(f"  harness check passed: R reproduces the corpus on all "
                  f"{len(order)} frames and {len(LANES)} lanes")
        counts[cid] = det
        per_lane = {}
        for lane, name in LANES.items():
            h = [hand[k][lane] for k in order]
            d = [det[k][lane] for k in order]
            median = statistics.median(h)
            entry = lane_stats(h, d)
            for label, keep in (("quiet", [i for i, x in enumerate(h) if x <= median]),
                                ("busy", [i for i, x in enumerate(h) if x > median])):
                entry[label] = {"n": len(keep),
                                **lane_stats([h[i] for i in keep], [d[i] for i in keep])}
            per_lane[name] = entry
        results[cid] = {"weights": path.name, "sha256": sha256(path), "imgsz": imgsz,
                        "conf": conf, "mae3": round(mae3(order, hand, det), 3),
                        "ms_per_frame": round(ms, 1), "symbol_as_bicycle": symbol,
                        "per_lane": per_lane}
        lane_text = "  ".join(f"{n[0].upper()} {per_lane[n]['signed']:+.2f}/{per_lane[n]['mae']:.2f}"
                              for n in ("west", "north", "east"))
        print(f"  {cid:<6} MAE3 {results[cid]['mae3']:.3f}   bias/MAE {lane_text}   "
              f"{ms:.0f} ms/frame")

    rng = random.Random(0)
    draws = [[order[rng.randrange(len(order))] for _ in order] for _ in range(RESAMPLES)]
    for cid in CANDIDATES:
        if cid == "R":
            continue
        diffs = sorted(mae3(s, hand, counts[cid]) - mae3(s, hand, counts["R"]) for s in draws)
        point = mae3(order, hand, counts[cid]) - mae3(order, hand, counts["R"])
        ci = [round(diffs[249], 3), round(diffs[9749], 3)]
        results[cid]["vs_R"] = {"point": round(point, 3), "ci95": ci, "improves": ci[1] < 0}

    improving = [c for c in CANDIDATES if c != "R" and results[c]["vs_R"]["improves"]]
    selected = None
    if improving:
        best = min(results[c]["mae3"] for c in improving)
        near = [c for c in improving if results[c]["mae3"] - best <= TIE]
        selected = min(near, key=lambda c: (SIZE_ORDER[c[0]], results[c]["mae3"]))
    report = {"protocol": "PREREGISTRATION_P99a.md", "frames": len(order),
              "device": device, "host": "laptop RTX 4050 (proxy, ADR-003)",
              "candidates": results, "improving": improving, "selected": selected}
    (ROOT / "p99a_detector_benchmark.json").write_text(json.dumps(report, indent=2),
                                                       encoding="utf-8")
    print()
    for c in CANDIDATES:
        if c != "R":
            v = results[c]["vs_R"]
            print(f"  {c:<6} − R  {v['point']:+.3f}  {v['ci95']}  "
                  f"{'improves' if v['improves'] else 'not shown'}")
    print(f"\n  selected: {selected}  (not adopted: confirmation on the "
          f"dawn/glare set is required first)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
