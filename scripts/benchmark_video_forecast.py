"""Compare the frozen Ridge and video blend on matched 60-second targets."""

from argparse import ArgumentParser
from collections import defaultdict
import json
from pathlib import Path
from statistics import fmean

from scripts.analyze_video import VIDEO_RIDGE_WEIGHT, blended_video_count
from edge.count_forecast import RECENT, T


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def errors(predictions):
    pairs = [(abs(ridge - observed), abs(blended_video_count(ridge, history) - observed))
             for ridge, history, observed in predictions]
    if not pairs:
        raise ValueError("No forecasts with a complete past and future window")
    baseline, refined = zip(*pairs)
    return {"lane_forecasts": len(pairs), "ridge_mae": round(fmean(baseline), 6),
            "blend_mae": round(fmean(refined), 6)}


def benchmark_windows(windows):
    by_clip = defaultdict(dict)
    for row in windows:
        by_clip[row["clip"]][row["start"]] = row
    by_camera = defaultdict(list)
    for clip in by_clip.values():
        for start, row in sorted(clip.items()):
            older = clip.get(start - RECENT)
            if older is None:
                continue
            by_camera[row["camera"]].extend(
                (ridge, (recent + previous) / 2, actual)
                for ridge, recent, previous, actual in zip(
                    row["count"]["ridge"], row["recent"], older["recent"], row["future"], strict=True))
    return {"recordings": len(by_clip), **errors(x for rows in by_camera.values() for x in rows),
            "by_camera": {camera: errors(rows) for camera, rows in sorted(by_camera.items())}}


def benchmark_analysis(result):
    if not str(result["models"]["number"]).startswith("ridge@"):
        raise ValueError("Use a saved Ridge-only analysis as the baseline")
    lanes = {lane["approach"]: lane["name"] for lane in result["lanes"]}
    samples = result["samples"]
    return {**errors(
        (ridge, fmean(s["counts"][lanes[approach]] for s in samples[i-T+1:i+1]), row["then"][approach]["number"])
        for i, row in enumerate(samples) if i >= T - 1 and row["number"] and row["then"]
        for approach, ridge in row["number"].items()),
        "detector": result.get("processing", {}).get("model"), "clip": result["clip"]}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=Path, default=Path("experiments/results/bellevue_pilot/p105_test_windows.json"))
    parser.add_argument("--analysis", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    record = {
        "target": "Mean detector-derived occupancy over the next 60 seconds, per approach",
        "ridge_weight": VIDEO_RIDGE_WEIGHT,
        "method": "Replay comparison. The blend was explored on P105 windows, so these are retrospective development results. "
                  "P105 rows without both historical halves are omitted from both methods. Targets are detector counts.",
        "p105": benchmark_windows(read(args.windows)),
        "saved_recordings": [benchmark_analysis(read(path)) for path in args.analysis],
    }
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
