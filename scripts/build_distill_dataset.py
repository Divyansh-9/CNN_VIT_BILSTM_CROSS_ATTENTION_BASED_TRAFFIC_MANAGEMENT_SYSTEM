"""Add pseudo-labelled deployment footage as a third TRAIN source (ADR-018).

    python scripts/build_distill_dataset.py --pseudo data/pseudo/dhaka_rampura

Emits `data/distill/distill.yaml`. The evaluation configs are **not** rewritten
— `eval_bmd45.yaml` and `eval_idd.yaml` from `build_joint_dataset.py` stay
exactly as they are, because ADR-018's acceptance criteria are measured on them
and a criterion whose measuring instrument moves with the treatment measures
nothing.

**Pseudo-labels enter training only. Never val, never test.** Evaluating on them
would measure agreement with the teacher, which is guaranteed and meaningless —
the student is *trained* to agree with the teacher. Every number that decides
whether this arm is adopted comes from human-annotated data.

**Nothing is copied.** Ultralytics accepts a list of image directories and
resolves labels by substituting `images` for `labels` in each path, so the union
is a config file rather than duplicated gigabytes — the same approach
`build_joint_dataset.py` takes.

**Training starts from our existing checkpoint, not from scratch.** The point is
to *add* target-domain knowledge to a detector that already meets its
requirement, not to retrain one and hope it lands in the same place. Starting
fresh would also discard the BMD-45 elevated adaptation that closed A31.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CLASSES = ["car", "motorcycle", "auto_rickshaw", "e_rickshaw",
           "bus", "truck", "pedestrian", "cattle"]


def census(labels: Path) -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    for file in labels.glob("*.txt"):
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[int(line.split()[0])] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pseudo", type=Path, nargs="+", required=True,
                        help="pseudo_label.py output directories")
    parser.add_argument("--idd", type=Path, default=Path("data/idd_yolo"))
    parser.add_argument("--bmd45", type=Path, default=Path("data/bmd45_yolo"))
    parser.add_argument("--out", type=Path, default=Path("data/distill"))
    args = parser.parse_args(argv)

    train_dirs: list[Path] = []
    missing_sources: list[str] = []
    for root in (args.idd, args.bmd45):
        candidate = root / "images" / "train"
        if candidate.is_dir():
            train_dirs.append(candidate.resolve())
        else:
            missing_sources.append(str(candidate))
            print(f"  SKIP {candidate} — not present")

    # BMD-45's training split is the elevated CCTV data that closed A31: S11 on
    # IDD alone scored 0.3223 on elevated, the joint model 0.8915. It is not
    # stored locally — S14 trained on Kaggle and pulled 8,000 images from the
    # HuggingFace Hub, and only the 498-image eval split lives here.
    #
    # Training without it would leave a corpus that is IDD dashcam plus one
    # elevated camera's pseudo-labels, and ADR-018 criterion 1 is measured on
    # elevated BMD-45. Losing that arm would look like the pseudo-labels
    # failing when the cause was the missing training source.
    if any("bmd45" in source for source in missing_sources):
        print("\n  BMD-45 TRAIN IS MISSING, and it is the elevated data that")
        print("  took mAP50 from 0.3223 to 0.8915. ADR-018 criterion 1 is")
        print("  measured on it. Training without it does not test this arm —")
        print("  it tests a different, weaker one.")
        print("  Run this where BMD-45 train exists (Kaggle, as S14 did), or")
        print("  fetch it locally first with scripts/prepare_bmd45.py.")
    if not train_dirs:
        raise SystemExit(
            "no real training data found. Pseudo-labels alone would drop "
            "e_rickshaw and cattle entirely and overfit to one camera; refusing."
        )

    pseudo_total = 0
    for directory in args.pseudo:
        images, labels = directory / "images", directory / "labels"
        if not images.is_dir() or not labels.is_dir():
            raise SystemExit(f"{directory} has no images/ and labels/ pair")
        counts = census(labels)
        frames = len(list(images.glob("*.jpg")))
        pseudo_total += frames
        print(f"\n  {directory.name}: {frames} frames, {sum(counts.values())} boxes")
        for index, name in enumerate(CLASSES):
            if counts[index]:
                print(f"    {name:<16}{counts[index]:>7}")
        absent = [CLASSES[i] for i in range(len(CLASSES)) if not counts[i]]
        if absent:
            print(f"    absent: {', '.join(absent)}")
        train_dirs.append(images.resolve())

    # A pseudo-labelled set that swamps the real data would let the teacher's
    # errors dominate, and no amount of downstream evaluation recovers a model
    # that learned mostly from them.
    real_frames = sum(len(list(d.glob("*.jpg"))) + len(list(d.glob("*.png")))
                      for d in train_dirs[:2] if d.is_dir())
    if real_frames and pseudo_total > 2 * real_frames:
        print(f"\n  WARNING: {pseudo_total} pseudo frames against {real_frames} "
              f"real. The teacher's errors will dominate. Lower --max-frames or "
              f"raise --every in pseudo_label.py.")

    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "distill.yaml"
    lines = ["# GENERATED by scripts/build_distill_dataset.py — do not edit.",
             "# Pseudo-labels are TRAIN ONLY (ADR-018). val is real data.",
             "train:"]
    lines += [f"  - {path.as_posix()}" for path in train_dirs]
    validation = (args.idd / "images" / "val").resolve()
    lines += [f"val: {validation.as_posix()}",
              f"nc: {len(CLASSES)}",
              f"names: {CLASSES}"]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n  wrote {target}")
    print(f"  {len(train_dirs)} train source(s), {pseudo_total} pseudo frames")
    print("\n  Train from the EXISTING checkpoint, not from scratch:")
    print("    yolo detect train "
          "model=models/detector/s14_yolov8s_joint_best.pt \\")
    print(f"      data={target.as_posix()} epochs=40 imgsz=640 batch=16 seed=42")
    print("\n  Then report BOTH eval configs against ADR-018's four criteria.")
    print("  Criterion 2 (e_rickshaw and cattle within 0.02) is the one this")
    print("  arm is most likely to fail — the teacher cannot see either class.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
