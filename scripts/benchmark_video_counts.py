"""Compare video detector profiles against annotated BMD-45 still-image counts."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import fmean
from time import perf_counter

VEHICLES = {"car", "motorcycle", "bus", "truck"}
LABELS = {"Hatchback", "Sedan", "SUV", "MUV", "Van", "Two-wheeler", "Bus",
          "Mini-bus", "Tempo-traveller", "Truck", "LCV"}
BASELINE_CONF = .45
THRESHOLDS = (.20, .25, .30, .35, .40, .45)


def score(rows, threshold):
    pairs = [(truth, sum(c >= threshold for c in confidences)) for truth, confidences in rows]
    errors = [abs(truth - predicted) for truth, predicted in pairs]
    total = sum(truth for truth, _ in pairs)
    return {"images": len(rows), "reference_total": total, "mae": round(fmean(errors), 4),
            "wape": round(sum(errors) / total, 4),
            "exact_frames": sum(error == 0 for error in errors),
            "detected_total": sum(predicted for _, predicted in pairs)}


def infer(weights, examples, size=640, region=None):
    import torch
    from ultralytics import YOLO

    from edge.classes import load_video_mapping

    torch.set_num_threads(4)
    model = YOLO(str(weights))
    mapping = load_video_mapping()
    classes = [k for k, label in model.names.items() if mapping.get(label, label) in VEHICLES]
    if not classes:
        raise ValueError(f"{weights.name} does not detect the supported vehicle classes")
    rows, timings = [], []
    for path, truth in examples:
        start = perf_counter()
        result = model.predict(source=str(path), conf=.10, imgsz=size, classes=classes, device="cpu", verbose=False)[0]
        timings.append(perf_counter() - start)
        confidences = result.boxes.conf.tolist()
        if region is not None:
            x0, y0, x1, y1 = region
            confidences = [conf for (x, y, _, _), conf in zip(result.boxes.xywh.tolist(), confidences)
                           if x0 <= x <= x1 and y0 <= y <= y1]
        rows.append((truth, confidences))
    return rows, round(1000 * fmean(timings[1:]), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    labels = json.loads(args.annotations.read_text(encoding="utf-8"))
    categories = {item["id"] for item in labels["categories"] if item["name"] in LABELS}
    if not categories:
        raise ValueError("The annotation taxonomy does not include the supported vehicle classes")
    counts = Counter(a["image_id"] for a in labels["annotations"] if a["category_id"] in categories and not a.get("iscrowd"))
    images = {path.name: path for path in args.images.rglob("*.png")}
    overlap = [(images[name], counts[row["id"]]) for row in labels["images"]
               if (name := Path(row["file_name"]).name) in images]
    overlap.sort(key=lambda pair: hashlib.sha256(("STMS-bmd-count-v1:" + pair[0].name).encode()).hexdigest())
    if len(overlap) < 120:
        raise ValueError(f"Need 120 matching annotated images, found {len(overlap)}")
    calibration, held_out = overlap[:40], overlap[40:120]
    examples = calibration + held_out
    baseline_rows, baseline_ms = infer(args.baseline, examples)
    candidate_rows, candidate_ms = infer(args.candidate, examples)
    choice = min(((score(rows[:40], conf)["wape"], model, conf)
                  for model, rows in (("baseline", baseline_rows), ("candidate", candidate_rows))
                  for conf in THRESHOLDS))
    _, model, conf = choice
    baseline = {"model": args.baseline.name, "size": 640, "confidence": BASELINE_CONF,
                "milliseconds_per_image": baseline_ms, **score(baseline_rows[40:], BASELINE_CONF)}
    rows, latency, weights = (candidate_rows, candidate_ms, args.candidate) if model == "candidate" else (
        baseline_rows, baseline_ms, args.baseline)
    tuned = {"model": weights.name, "size": 640, "confidence": conf,
             "milliseconds_per_image": latency, **score(rows[40:], conf)}
    report = {"dataset": "BMD-45 Train source, cached CCTV still images",
              "metric_scope": "Whole-frame counts of cars, motorcycles, buses and trucks",
              "calibration_images": len(calibration), "test_images": [p.name for p, _ in held_out],
              "baseline": baseline, "tuned": tuned}
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "tuned": tuned}), flush=True)


if __name__ == "__main__":
    main()
