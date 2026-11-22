"""Compare detector settings on a fixed sample from the official BMD-45 validation split."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import urllib.request

from scripts.benchmark_video_counts import LABELS, infer, score

SOURCE = "https://huggingface.co/datasets/iisc-aim/BMD-45/resolve/main/BMD-45-Val/"
CALIBRATION_SIZE = 16
EVALUATION_SIZE = 48
THRESHOLDS = (.15, .20, .25, .30, .35, .40, .45, .50, .55, .60)


def select_images(labels):
    return sorted(labels["images"], key=lambda row: hashlib.sha256(
        f"STMS-bmd-validation-v1:{row['file_name']}".encode()).hexdigest()
    )[:CALIBRATION_SIZE + EVALUATION_SIZE]


def fetch(path, name):
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE + name, timeout=60) as response:
            content = response.read()
        path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    annotations = args.cache / "bmd45-val-annotations.json"
    if args.download:
        fetch(annotations, "_annotations.coco.json")
    labels = json.loads(annotations.read_text(encoding="utf-8"))
    categories = {row["id"] for row in labels["categories"] if row["name"] in LABELS}
    counts = Counter(row["image_id"] for row in labels["annotations"]
                     if row["category_id"] in categories and not row.get("iscrowd"))
    examples = []
    for row in select_images(labels):
        name = row["file_name"]
        path = args.cache / "bmd45-validation" / name
        if args.download:
            fetch(path, name)
        examples.append((path, counts[row["id"]]))
    if len(examples) != CALIBRATION_SIZE + EVALUATION_SIZE:
        raise ValueError("Incomplete validation sample")
    absent = [str(path) for path, _ in examples if not path.is_file()]
    if absent:
        raise ValueError(f"Run with --download to get the {len(absent)} missing validation images")

    profiles = ((args.baseline, 640), (args.baseline, 960), (args.candidate, 640), (args.candidate, 960))
    predictions = []
    for weights, size in profiles:
        rows, ms = infer(weights, examples, size)
        print(f"Finished {weights.name} at {size}px ({ms:.0f} ms per image)", flush=True)
        predictions.append((rows, dict(model=weights.name, size=size, milliseconds_per_image=ms)))

    # Freeze the selected operating point before evaluating a single held-out score.
    calibration_error, preferred, confidence = min(
        (score(rows[:CALIBRATION_SIZE], threshold)["wape"], index, threshold)
        for index, (rows, _) in enumerate(predictions)
        for threshold in THRESHOLDS
    )
    baseline_rows, baseline = predictions[0]
    baseline = {**baseline, "confidence": .30, **score(baseline_rows[CALIBRATION_SIZE:], .30)}
    chosen_rows, chosen = predictions[preferred]
    chosen = {**chosen, "confidence": confidence, "calibration_wape": calibration_error,
              **score(chosen_rows[CALIBRATION_SIZE:], confidence)}
    report = {
        "dataset": "BMD-45 official validation split",
        "metric_scope": "Whole-frame counts of cars, motorcycles, buses and trucks",
        "calibration_images": [path.name for path, _ in examples[:CALIBRATION_SIZE]],
        "test_images": [path.name for path, _ in examples[CALIBRATION_SIZE:]],
        "baseline": baseline,
        "tuned": chosen,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "tuned": chosen}), flush=True)


if __name__ == "__main__":
    main()
