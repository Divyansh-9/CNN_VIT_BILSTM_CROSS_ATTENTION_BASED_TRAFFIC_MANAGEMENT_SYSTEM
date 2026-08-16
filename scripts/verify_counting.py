"""Measure COUNTING accuracy, which is not detection accuracy (FR-P02).

FR-P02 — "System SHALL detect and count vehicles per lane" — is Must Have, is the
backbone of everything downstream (counts become congestion labels under ADR-002,
fill the PPO state vector, and publish over MQTT), and had **never been measured**.
Every result in `experiments/results/` was detection mAP, label noise, or SUMO.

**mAP does not answer this question.** mAP is computed per class over a
precision-recall curve at a range of IoU thresholds; a count is a single integer
per frame. A detector can hold a respectable mAP while systematically losing the
same third of the vehicles in every frame, and mAP will not say so — but every
congestion label derived from those counts will be wrong in the same direction.

S11 reports overall recall 0.545, which predicts exactly that: a systematic
UNDER-count. This measures whether it happens and by how much.

    python scripts/verify_counting.py --weights models/detector/s11_yolov8s_idd_best.pt \\
        --data data/bmd45_eval --split test

**Bias matters more than error here.** A detector that misses 30% of vehicles in
every frame has a large error and is *correctable* — the §14.1 thresholds could
be recalibrated. A detector whose error grows with density is not correctable by
a constant, because it compresses exactly the distinction between MED and HIGH
that the congestion label depends on. Both are reported.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def ground_truth_counts(label_file: Path, ids: set[int]) -> int:
    total = 0
    for line in label_file.read_text(encoding="utf-8").splitlines():
        if line.strip() and int(line.split()[0]) in ids:
            total += 1
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--out", type=Path,
        default=Path("experiments/results/counting_accuracy.csv"),
    )
    args = parser.parse_args(argv)

    import statistics

    from ultralytics import YOLO

    from scripts.pilot_a17 import vehicle_ids

    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    print(f"  counting {sorted(names[i] for i in ids)}")

    images = sorted((args.data / "images" / args.split).glob("*.jpg"))
    if args.limit:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"no images under {args.data / 'images' / args.split}")

    rows = []
    for image in images:
        label = args.data / "labels" / args.split / f"{image.stem}.txt"
        if not label.exists():
            continue
        truth = ground_truth_counts(label, ids)
        result = model.predict(source=str(image), conf=args.conf,
                               device=args.device, verbose=False)[0]
        predicted = sum(1 for c in result.boxes.cls.tolist() if int(c) in ids)
        rows.append({"image": image.stem, "true_count": truth,
                     "predicted_count": predicted, "error": predicted - truth})
        if len(rows) % 100 == 0:
            print(f"    {len(rows)} / {len(images)}")

    errors = [r["error"] for r in rows]
    truths = [r["true_count"] for r in rows]
    mae = sum(abs(e) for e in errors) / len(errors)
    bias = sum(errors) / len(errors)
    total_true, total_pred = sum(truths), sum(r["predicted_count"] for r in rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  frames                {len(rows):,}")
    print(f"  true vehicles         {total_true:,}")
    print(f"  detected vehicles     {total_pred:,}")
    print(f"  mean absolute error   {mae:.2f} vehicles/frame")
    print(f"  mean signed error     {bias:+.2f} vehicles/frame "
          f"({'UNDER' if bias < 0 else 'OVER'}-counting)")
    print(f"  detected / true       {total_pred / total_true:.3f}")

    # Does the error scale with density? A constant offset is recalibratable;
    # a proportional one compresses MED against HIGH and is not.
    ordered = sorted(rows, key=lambda r: r["true_count"])
    third = max(1, len(ordered) // 3)
    low, high = ordered[:third], ordered[-third:]
    for label, group in (("sparsest third", low), ("densest third", high)):
        true_sum = sum(r["true_count"] for r in group)
        pred_sum = sum(r["predicted_count"] for r in group)
        mean_true = true_sum / len(group)
        print(f"  {label:<20} mean true {mean_true:>5.1f}  "
              f"detected/true {pred_sum / max(true_sum, 1):.3f}")

    print(f"\n  wrote {args.out}")
    print("  FR-P02 has a measurement for the first time. Read the density rows:")
    print("  a ratio that FALLS as density rises means the shortfall is not a")
    print("  constant and cannot be fixed by moving the §14.1 thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
