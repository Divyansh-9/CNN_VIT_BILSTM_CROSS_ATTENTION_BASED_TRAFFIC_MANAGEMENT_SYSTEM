"""P99b — detector counts against blind hand counts at dawn, glare and dusk.

    python scripts/p99b_compare.py

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P99b.md`. It
refuses unless every selected frame has been counted. ITD-xl (R) is run
through the P99a harness and must reproduce `data/corpus_p98/counts.csv`
exactly; M1280 is then run through the same harness. Both decision rules are
applied as written there.
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_p98")
SOURCE = Path("data/_bellevue/p98")
STRIDE = 60
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "east"}
DETECTORS = {"R": ("models/external/best_xl_ITD_v1.2.pt", 992, 0.45),
             "M1280": ("models/external/yolov8m.pt", 1280, 0.25)}
LOW_MAX, PRECISION_FLOOR, MARGIN, SLACK = 2, 0.80, 0.25, 0.05
RESAMPLES = 10_000


def key(clip: str, sample: int) -> str:
    return f"{clip[-19:]}#{sample}"


def low_rates(keys, hand, det):
    pairs = [(hand[k][l] <= LOW_MAX, det[k][l] <= LOW_MAX) for k in keys for l in LANES]
    called = [h for h, d in pairs if d]
    actual = [d for h, d in pairs if h]
    return (sum(called) / len(called) if called else None,
            sum(actual) / len(actual) if actual else None,
            len(called), len(actual))


def mae3(keys, hand, det):
    return statistics.mean(abs(det[k][l] - hand[k][l]) for k in keys for l in LANES)


def interval(values):
    values = sorted(v for v in values if v is not None)
    return [round(values[int(.025 * len(values))], 3),
            round(values[int(.975 * len(values)) - 1], 3)]


def main() -> int:
    from ultralytics import YOLO

    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.corpus.video import iter_sampled_frames
    from scripts.detector_benchmark import count, lane_stats, sha256

    selection = json.loads((ROOT / "p99b_frames.json").read_text(encoding="utf-8"))["frames"]
    manual = json.loads((ROOT / "p99b_manual.json").read_text(encoding="utf-8"))
    hand = {f["sample"]: {lane: int(f[lane]) for lane in LANES} for f in manual["frames"]}
    keys = [key(f["clip"], f["sample"]) for f in selection]
    missing = sorted(set(keys) - set(hand))
    if missing or len(hand) != len(keys):
        raise SystemExit(f"{len(missing)} of {len(keys)} frames not counted "
                         f"(or extras present): {missing[:5]}")

    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    lanes = LaneCentres(names=tuple(c["name"] for c in manifest["lane_centres"]),
                        centres=tuple(tuple(c["centre"]) for c in manifest["lane_centres"]),
                        max_radius=float(manifest["max_radius"]))
    assert lanes.names == tuple(LANES)

    frames = {}
    by_clip: dict[str, set[int]] = {}
    for f in selection:
        by_clip.setdefault(f["clip"], set()).add(f["sample"])
    for clip, samples in by_clip.items():
        for index, frame in enumerate(iter_sampled_frames(SOURCE / f"{clip}.mp4", STRIDE,
                                                          limit=max(samples) + 1)):
            if index in samples:
                frames[key(clip, index)] = frame
    assert set(frames) == set(keys)

    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        built = {key(r["clip_id"], int(r["sample"])): {l: int(r["count_" + l]) for l in LANES}
                 for r in csv.DictReader(handle)}

    counts, report = {}, {"protocol": "PREREGISTRATION_P99b.md", "frames": len(keys),
                          "annotator": manual.get("annotator"), "detectors": {}}
    for name, (weights, imgsz, conf) in DETECTORS.items():
        det, symbol, ms = count(YOLO(weights), frames, lanes, imgsz, conf, name == "R")
        # The P99a harness reports its own four lane names; these regions have three.
        det = {k: {l: v[l] for l in LANES} for k, v in det.items()}
        if name == "R":
            wrong = [k for k in keys if det[k] != built[k]]
            if wrong:
                raise SystemExit(f"harness check FAILED on {len(wrong)} frames: {wrong[:3]}")
            print(f"  harness check passed: R reproduces corpus_p98 on all {len(keys)} frames")
        counts[name] = det
        per_lane = {LANES[l]: lane_stats([hand[k][l] for k in keys], [det[k][l] for k in keys])
                    for l in LANES}
        per_hour = {}
        for hour in sorted({k.split("#")[0] for k in keys}):
            sub = [k for k in keys if k.startswith(hour)]
            per_hour[hour] = {"frames": len(sub), "mae3": round(mae3(sub, hand, det), 3),
                              "signed": round(statistics.mean(det[k][l] - hand[k][l]
                                                              for k in sub for l in LANES), 3),
                              "low_precision": low_rates(sub, hand, det)[0]}
        precision, recall, n_called, n_actual = low_rates(keys, hand, det)
        report["detectors"][name] = {
            "weights": Path(weights).name, "sha256": sha256(Path(weights)),
            "imgsz": imgsz, "conf": conf, "mae3": round(mae3(keys, hand, det), 3),
            "per_lane": per_lane, "per_hour": per_hour,
            "low": {"precision": round(precision, 3) if precision is not None else None,
                    "recall": round(recall, 3) if recall is not None else None,
                    "detector_low": n_called, "hand_low": n_actual}}

    rng = random.Random(0)
    draws = [[keys[rng.randrange(len(keys))] for _ in keys] for _ in range(RESAMPLES)]
    for name in DETECTORS:
        low = report["detectors"][name]["low"]
        rates = [low_rates(s, hand, counts[name]) for s in draws]
        low["precision_ci95"] = interval(r[0] for r in rates)
        low["recall_ci95"] = interval(r[1] for r in rates)
    diffs = [mae3(s, hand, counts["M1280"]) - mae3(s, hand, counts["R"]) for s in draws]
    point = mae3(keys, hand, counts["M1280"]) - mae3(keys, hand, counts["R"])
    ci = interval(diffs)

    r_low = report["detectors"]["R"]["low"]["precision"]
    m_low = report["detectors"]["M1280"]["low"]["precision"]
    report["decisions"] = {
        "morning_low_labels_usable": {name: (report["detectors"][name]["low"]["precision"] or 0)
                                      >= PRECISION_FLOOR for name in DETECTORS},
        "m1280_minus_r_mae3": {"point": round(point, 3), "ci95": ci},
        "m1280_non_inferior": ci[1] < MARGIN,
        "m1280_low_precision_ok": m_low is not None and r_low is not None
                                  and m_low >= r_low - SLACK,
    }
    report["decisions"]["adopt_m1280"] = (report["decisions"]["m1280_non_inferior"]
                                          and report["decisions"]["m1280_low_precision_ok"])
    (ROOT / "p99b_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for name in DETECTORS:
        d = report["detectors"][name]
        print(f"\n  {name}: MAE3 {d['mae3']}   LOW precision {d['low']['precision']} "
              f"{d['low']['precision_ci95']} ({d['low']['detector_low']} called)   "
              f"recall {d['low']['recall']} {d['low']['recall_ci95']} ({d['low']['hand_low']} hand-LOW)")
        for lane, s in d["per_lane"].items():
            print(f"    {lane:<6} MAE {s['mae']:.2f}  bias {s['signed']:+.2f}  "
                  f"undercount {s['undercount']}  r {s['pearson']}")
        for hour, s in d["per_hour"].items():
            print(f"    {hour}  MAE3 {s['mae3']:.2f}  bias {s['signed']:+.2f}  "
                  f"LOW precision {s['low_precision']}")
    print(f"\n  decisions: {json.dumps(report['decisions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
