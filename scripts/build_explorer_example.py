"""Extract the Project Explorer example from a saved Bellevue analysis and its video."""

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
HORIZON_S = 60


def timestamp(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


def read_frame(path, seconds):
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0, seconds - 2) * 1000)
        while capture.grab():
            if capture.get(cv2.CAP_PROP_POS_MSEC) < seconds * 1000:
                continue
            ok, frame = capture.retrieve()
            if ok:
                return frame
            break
    finally:
        capture.release()
    raise ValueError(f"Could not decode {path.name} at {timestamp(seconds)}")


def build_example(video, analysis, output, at, detector):
    import cv2

    result = json.loads(analysis.read_text(encoding="utf-8"))
    if result["clip"] != video.stem or result["camera"] != "Bellevue_116th_NE12th":
        raise ValueError("Choose the Bellevue recording that produced this analysis")
    step = int(result["step_s"])
    samples = {sample["t"]: sample for sample in result["samples"]}
    sample = samples[at]
    recent = [samples[t] for t in range(at + step - HORIZON_S, at + step, step)]
    if not (sample["number"] and sample["then"]):
        raise ValueError("Choose a timestamp with a forecast and the following minute of results")
    boxes = [
        {"label": label, "confidence": confidence, "bounds": bounds, "lane": lane}
        for bounds, (label, confidence, lane) in zip(sample["boxes"], sample["detections"], strict=True)
        if confidence >= result["min_confidence"]
    ]
    assigned = Counter(box["lane"] for box in boxes if box["lane"] is not None)
    if any(sample["counts"][lane] != assigned[lane] for lane in sample["counts"]):
        raise ValueError("Saved boxes and lane counts disagree at the chosen timestamp")

    lanes = [{
        **lane, "count": sample["counts"][lane["name"]],
        "forecast": sample["number"][lane["approach"]],
        "baseline": fmean(row["counts"][lane["name"]] for row in recent),
        "observed": sample["then"][lane["approach"]]["number"],
    } for lane in result["lanes"]]
    example = {
        "site": "Bellevue, Washington, USA",
        "timestamp": timestamp(at),
        "forecastWindow": f"{timestamp(at + step)}–{timestamp(at + HORIZON_S)}",
        "detector": result.get("processing", {}).get("model") or detector,
        "model": result["models"]["number"],
        "boxes": boxes,
        "lanes": lanes,
    }
    if not example["detector"]:
        raise ValueError("The saved analysis does not name its detector. Supply --detector.")
    frame = read_frame(video, at)
    output.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output / "bellevue.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 88]):
        raise OSError("Could not write the Bellevue example image")
    (output / "bellevue.json").write_text(json.dumps(example, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_count_audit(output):
    evidence = ROOT / "experiments/results/bellevue_pilot/p99b_comparison.json"
    comparison = json.loads(evidence.read_text(encoding="utf-8"))
    detector = comparison["detectors"]["R"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "count-audit.json").write_text(json.dumps({
        "frames": comparison["frames"], "model": detector["weights"],
        "lanes": detector["per_lane"], "hours": detector["per_hour"],
    }), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "dashboard/src/explorer-example")
    parser.add_argument("--at", type=int, default=152, help="Timestamp in seconds on the analysis sampling grid")
    parser.add_argument("--detector", help="Checkpoint name for older analyses without model metadata")
    parser.add_argument("--audit-out", type=Path, help="Optional local output directory for the separate count audit")
    args = parser.parse_args()
    build_example(args.video, args.analysis, args.out, args.at, args.detector)
    if args.audit_out:
        write_count_audit(args.audit_out)
