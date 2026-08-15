"""Re-validate a detector and map metrics to the RIGHT classes (S11, FR-D08).

Written because the first S11 metrics table was wrong in a way that looked fine.

Ultralytics' `DetMetrics.class_result(i)` does **not** index into your class-name
list. It indexes into the classes that actually had instances in the validation
set, and `ap_class_index` is the array that maps those positions back to real
class ids. When a class has zero instances it is simply absent, so every class
after it shifts up by one and the last index falls off the end as `nan`.

The S11 run had `e_rickshaw` at zero boxes (expected — no public dataset carries
it, pending item P12). The published table therefore reported:

    e_rickshaw   mAP50 0.7288   with 0 boxes      <- impossible
    cattle       nan            with 183 boxes    <- impossible

Both are arithmetically impossible and both were printed without complaint. Every
row from `e_rickshaw` onward named the wrong class.

    python scripts/verify_detector_metrics.py --weights best.pt

This re-runs validation locally and writes the table keyed by `ap_class_index`,
so a missing class is reported as missing rather than silently borrowing the next
class's numbers.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_names(data_yaml: Path) -> list[str]:
    import yaml

    return yaml.safe_load(data_yaml.read_text(encoding="utf-8"))["names"]


def support(root: Path, split: str, names: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in names}
    for label_file in (root / "labels" / split).glob("*.txt"):
        for line in label_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[names[int(line.split()[0])]] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data/idd_yolo/data.yaml"))
    parser.add_argument("--split", default="test")
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--out", type=Path,
        default=Path("experiments/results/s11_detector_metrics.csv"),
    )
    args = parser.parse_args(argv)

    from ultralytics import YOLO

    names = load_names(args.data)
    boxes = support(args.data.parent, args.split, names)

    model = YOLO(str(args.weights))
    metrics = model.val(
        data=str(args.data), split=args.split, device=args.device, verbose=False
    )

    # THE FIX. `ap_class_index` maps each result row to its true class id.
    present = list(metrics.box.ap_class_index)
    rows = []
    for position, class_id in enumerate(present):
        precision, recall, ap50, ap = metrics.box.class_result(position)
        rows.append({
            "class": names[int(class_id)],
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "mAP50": round(float(ap50), 4),
            "mAP50_95": round(float(ap), 4),
            "test_boxes": boxes[names[int(class_id)]],
            "evaluated": True,
        })

    # Classes with no instances are reported as absent, never as numbers.
    for index, name in enumerate(names):
        if index not in present:
            rows.append({
                "class": name, "precision": None, "recall": None,
                "mAP50": None, "mAP50_95": None,
                "test_boxes": boxes[name], "evaluated": False,
            })

    rows.sort(key=lambda r: names.index(r["class"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'class':<16}{'P':>8}{'R':>8}{'mAP50':>9}{'mAP50-95':>10}{'boxes':>8}")
    for row in rows:
        if row["evaluated"]:
            print(f"{row['class']:<16}{row['precision']:>8.3f}{row['recall']:>8.3f}"
                  f"{row['mAP50']:>9.3f}{row['mAP50_95']:>10.3f}{row['test_boxes']:>8,}")
        else:
            print(f"{row['class']:<16}{'—':>8}{'—':>8}{'—':>9}{'—':>10}"
                  f"{row['test_boxes']:>8,}   NOT EVALUATED (no instances)")

    print(f"\noverall mAP50 {float(metrics.box.map50):.4f}  "
          f"mAP50-95 {float(metrics.box.map):.4f}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
