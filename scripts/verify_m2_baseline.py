"""M2's actual criterion: mAP improvement over COCO on the SAME test split.

PRD §18 M2 (Week 9) reads: *">=10% mAP improvement over COCO on Indian classes"*.
The detector track has been reporting S11-vs-S14 and stock-vs-tuned **counts**,
neither of which is that measurement. M2 was being claimed by implication.

    python scripts/verify_m2_baseline.py --data data/idd_yolo/data.yaml

**Why this needs a remap rather than a fresh AP implementation.** Stock YOLOv8 is
trained on 80 COCO classes with different indices; our labels use eight of our
own. Writing an AP routine to bridge them would put a subtle metric bug in the
one number a milestone turns on — the exact failure the S11 `ap_class_index`
defect already was. Instead the ground truth is rewritten into COCO indices and
**Ultralytics' own validator** computes AP for both sides.

**The comparison is only fair on shared classes.** COCO has `car`, `motorcycle`,
`bus`, `truck`. It has **no** `auto_rickshaw`, `e_rickshaw` or `cattle`
equivalent, so on those a percentage improvement is not the honest statement —
"COCO cannot represent this class at all" is stronger and truer than any number.
Both halves are reported.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# COCO index -> our class name, for the four that genuinely correspond.
COCO_TO_OURS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
NO_COCO_EQUIVALENT = ("auto_rickshaw", "e_rickshaw", "cattle")


def build_coco_indexed_copy(source: Path, split: str, names: list[str],
                            destination: Path) -> dict[str, int]:
    """Rewrite our labels into COCO indices, keeping only shared classes."""
    ours_to_coco = {v: k for k, v in COCO_TO_OURS.items()}
    images_in = source / "images" / split
    labels_in = source / "labels" / split
    images_out = destination / "images" / split
    labels_out = destination / "labels" / split
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    kept: dict[str, int] = {name: 0 for name in ours_to_coco}
    for label in labels_in.glob("*.txt"):
        lines = []
        for line in label.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split()
            name = names[int(parts[0])]
            if name not in ours_to_coco:
                continue
            kept[name] += 1
            lines.append(" ".join([str(ours_to_coco[name]), *parts[1:]]))
        if not lines:
            continue
        (labels_out / label.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        image = images_in / f"{label.stem}.jpg"
        target = images_out / image.name
        if image.exists() and not target.exists():
            try:
                target.symlink_to(image.resolve())
            except OSError:
                shutil.copy2(image, target)
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data/idd_yolo/data.yaml"))
    parser.add_argument("--tuned", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--baseline", default="yolov8s.pt",
                        help="stock COCO weights of the SAME size — comparing "
                             "against a different capacity measures the wrong thing")
    parser.add_argument("--split", default="test")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--work", type=Path, default=Path("data/_m2_coco_indexed"))
    parser.add_argument("--out", type=Path,
                        default=Path("experiments/results/m2_coco_baseline.csv"))
    args = parser.parse_args(argv)

    import yaml
    from ultralytics import YOLO

    config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    names = config["names"]
    root = args.data.parent

    kept = build_coco_indexed_copy(root, args.split, names, args.work)
    print("  shared-class boxes in the remapped ground truth:")
    for name, count in kept.items():
        print(f"    {name:<12}{count:>8,}")

    coco_names = YOLO(args.baseline).model.names
    (args.work / "data.yaml").write_text(
        yaml.safe_dump({
            "path": str(args.work.resolve()),
            "train": f"images/{args.split}", "val": f"images/{args.split}",
            "test": f"images/{args.split}",
            "nc": len(coco_names),
            "names": [coco_names[i] for i in range(len(coco_names))],
        }, sort_keys=False), encoding="utf-8",
    )

    print(f"\n  baseline: {args.baseline} on COCO-indexed ground truth")
    base = YOLO(args.baseline).val(data=str(args.work / "data.yaml"),
                                   split=args.split, device=args.device, verbose=False)
    base_ap = {}
    for position, class_id in enumerate(base.box.ap_class_index):
        if int(class_id) in COCO_TO_OURS:
            _, _, ap50, _ = base.box.class_result(position)
            base_ap[COCO_TO_OURS[int(class_id)]] = float(ap50)

    print(f"  tuned:    {args.tuned} on our ground truth")
    tuned = YOLO(str(args.tuned)).val(data=str(args.data), split=args.split,
                                       device=args.device, verbose=False)
    tuned_ap = {}
    for position, class_id in enumerate(tuned.box.ap_class_index):
        _, _, ap50, _ = tuned.box.class_result(position)
        tuned_ap[names[int(class_id)]] = float(ap50)

    rows = []
    print(f"\n  {'class':<16}{'COCO':>9}{'ours':>9}{'delta':>9}{'boxes':>9}")
    for name in COCO_TO_OURS.values():
        b, t = base_ap.get(name, 0.0), tuned_ap.get(name, 0.0)
        rows.append({"class": name, "comparable": True,
                     "coco_mAP50": round(b, 4), "ours_mAP50": round(t, 4),
                     "delta": round(t - b, 4), "boxes": kept.get(name, 0)})
        print(f"  {name:<16}{b:>9.3f}{t:>9.3f}{t - b:>+9.3f}{kept.get(name, 0):>9,}")

    for name in NO_COCO_EQUIVALENT:
        t = tuned_ap.get(name)
        rows.append({"class": name, "comparable": False, "coco_mAP50": None,
                     "ours_mAP50": round(t, 4) if t is not None else None,
                     "delta": None, "boxes": None})
        shown = f"{t:.3f}" if t is not None else "—"
        print(f"  {name:<16}{'n/a':>9}{shown:>9}{'':>9}   NO COCO CLASS EXISTS")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    comparable = [r for r in rows if r["comparable"]]
    base_mean = sum(r["coco_mAP50"] for r in comparable) / len(comparable)
    ours_mean = sum(r["ours_mAP50"] for r in comparable) / len(comparable)
    relative = (ours_mean - base_mean) / base_mean * 100 if base_mean else float("inf")

    print(f"\n  shared classes only:  COCO {base_mean:.4f}   ours {ours_mean:.4f}")
    print(f"  relative improvement  {relative:+.1f}%   (M2 requires >= +10%)")
    print(f"  M2 on shared classes: {'MET' if relative >= 10 else 'NOT MET'}")
    print("\n  On auto_rickshaw, e_rickshaw and cattle no percentage is honest:")
    print("  COCO has no such class, so the baseline is not low — it is undefined.")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
