"""Evaluate any detector across every viewpoint condition (A31, FR-D08).

    python scripts/evaluate_detector_arms.py --weights models/detector/s14_....pt --arm D1

Keeping the old checkpoints costs nothing and buys a **controlled ablation**:
same data, same recipe, one variable changed at a time. That is a stronger thing
than "two options in a table", because it evidences the claim rather than
offering a choice.

    D0   S11   IDD only                          dashcam baseline
    D1   S14   IDD + BMD-45                      viewpoint fixed by DATA
    D2   S15   IDD + BMD-45 + geometric aug      viewpoint fixed by TRAINING

Each arm is scored on the same four conditions:

    dashcam        IDD test split          in-domain for D0
    oblique        BMD-45 test split       the deployment geometry
    steep          BMD-45 warped to pitch 1.0   near-overhead municipal CCTV
    deployment     self-recorded footage   the only unbiased test we will have

**The steep column is the point of the whole table.** D0 and D1 were trained
with `perspective=0.0`, so neither was ever asked to generalise across camera
angle, and D1 loses 56% of its detections at pitch 1.0.

**Why the deployment column stays EMPTY until S06 exists, and why the phone
footage must not be trained on.** One fifteen-minute clip is tens of thousands of
highly correlated frames of a single scene — as training data it adds little and
risks fitting that one junction, and it would burn the only unbiased test set the
project will ever have. It is worth more as an honest test than as more training
rows, for the same reason ADR-002 human-verifies the test split rather than
enlarging the train split.
"""

from __future__ import annotations

import argparse
import csv
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ARMS = {
    "D0": "S11 — IDD only (dashcam baseline)",
    "D1": "S14 — IDD + BMD-45 (viewpoint fixed by data)",
    "D2": "S15 — IDD + BMD-45 + geometric augmentation (fixed by training)",
}
RESULTS = Path("experiments/results/detector_arms.csv")


def pitch_warp(image, amount: float):
    import cv2
    import numpy as np

    if not amount:
        return image
    h, w = image.shape[:2]
    source = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    inset = amount * w * 0.35
    target = np.float32([[inset, 0], [w - inset, 0], [w, h], [0, h]])
    return cv2.warpPerspective(
        image, cv2.getPerspectiveTransform(source, target), (w, h)
    )


def detections_per_frame(model, ids, frames, conf: float, pitch: float) -> tuple:
    """Returns (detections/frame, out-of-domain ratio). Needs no labels."""
    low = high = 0
    for frame in frames:
        image = pitch_warp(frame, pitch)
        result = model.predict(source=image, conf=0.10, verbose=False)[0]
        kept = [
            c for c, k in zip(result.boxes.conf.tolist(), result.boxes.cls.tolist())
            if int(k) in ids
        ]
        low += len(kept)
        high += sum(1 for c in kept if c >= conf)
    return high / max(len(frames), 1), low / max(high, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--arm", required=True, choices=sorted(ARMS))
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--deployment", type=Path,
                        help="self-recorded clip; omitted until S06 exists")
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    import cv2

    from ultralytics import YOLO

    from scripts.pilot_a17 import vehicle_ids

    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)

    oblique = [
        cv2.imread(p)
        for p in sorted(glob.glob("data/bmd45_eval/images/test/*.jpg"))[: args.frames]
    ]
    dashcam = [
        cv2.imread(p)
        for p in sorted(glob.glob("data/idd_yolo/images/test/*.jpg"))[: args.frames]
    ]
    if not oblique:
        raise SystemExit("no BMD-45 eval images; run scripts/prepare_bmd45.py --eval-only")

    conditions = [
        ("dashcam", dashcam, 0.0),
        ("oblique", oblique, 0.0),
        ("steep", oblique, 1.0),
    ]
    if args.deployment and args.deployment.exists():
        capture = cv2.VideoCapture(str(args.deployment))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        for index in range(0, total, max(1, total // args.frames)):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if ok:
                frames.append(frame)
        capture.release()
        conditions.append(("deployment", frames[: args.frames], 0.0))

    rows = []
    if args.out.exists():
        with args.out.open(encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r["arm"] != args.arm]

    print(f"  {args.arm}: {ARMS[args.arm]}")
    print(f"\n  {'condition':<14}{'det/frame':>11}{'ood ratio':>11}  {'frames':>7}")
    for name, frames, pitch in conditions:
        if not frames:
            print(f"  {name:<14}{'—':>11}{'—':>11}  no images")
            continue
        per_frame, ratio = detections_per_frame(model, ids, frames, args.conf, pitch)
        rows.append({
            "arm": args.arm, "weights": args.weights.name, "condition": name,
            "pitch": pitch, "detections_per_frame": round(per_frame, 3),
            "ood_ratio": round(ratio, 3), "frames": len(frames),
        })
        print(f"  {name:<14}{per_frame:>11.2f}{ratio:>11.2f}  {len(frames):>7}")

    by_name = {r["condition"]: r for r in rows if r["arm"] == args.arm}
    if "oblique" in by_name and "steep" in by_name:
        flat = by_name["oblique"]["detections_per_frame"]
        steep = by_name["steep"]["detections_per_frame"]
        retained = steep / flat if flat else 0.0
        print(f"\n  PITCH RETENTION {retained:.0%}  "
              f"(A31 pre-registered target: >= 70%)")
        print(f"  {'MEETS' if retained >= 0.70 else 'BELOW'} the criterion fixed "
              f"before the retrain. D1 measured 44%.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["arm", "weights", "condition", "pitch",
                        "detections_per_frame", "ood_ratio", "frames"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {args.out}")

    if not args.deployment:
        print("\n  deployment column empty — S06 footage does not exist yet. It is")
        print("  a TEST condition, never a training source: one clip is tens of")
        print("  thousands of correlated frames of a single scene, and training on")
        print("  it would burn the only unbiased test this project will ever have.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
