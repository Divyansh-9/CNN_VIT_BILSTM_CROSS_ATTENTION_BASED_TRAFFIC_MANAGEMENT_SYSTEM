"""Cross-viewpoint transfer within IDD (S12, partial — ADR-001, DATASETS §2).

`class_mapping.yaml` up-weights IDD's side cameras on the argument that a
side-on view of cross traffic resembles an intersection approach more than a
forward dashcam does. That is a **prior**, and S12 was supposed to test it "on
real junction footage" — which is the same S06 blocker the corpus track has.

Most of the question does not need that footage, because **IDD is already a
multi-viewpoint dataset**. Six camera positions on a moving rig is a built-in
cross-viewpoint benchmark:

    train on sideLeft + sideRight   ->  evaluate on frontNear + frontFar
    train on frontNear + frontFar   ->  evaluate on sideLeft + sideRight

    python scripts/viewpoint_experiment.py --prepare        # build both arms
    python scripts/viewpoint_experiment.py --report         # after training

**What this can and cannot settle.** Free transfer between IDD's own viewpoints
means viewpoint matters less than assumed, and the sampling weights should go to
1.0. A sharp drop supports the prior and sizes what elevated footage will cost.

Neither outcome settles the *elevated* case — a camera looking down from a
footbridge is a different geometry again, and no IDD camera is mounted that way.
This is a lower-fidelity proxy run first because it is free of the blocker, and
because if it shows no gap at all, the elevated experiment may not be worth
waiting for.

**Both arms are matched on everything except viewpoint** — same image count,
same seed, same class mapping, same hyperparameters. Otherwise the comparison
measures dataset size as much as geometry.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.prepare_idd import IDD, SPLITS, convert, load_mapping  # noqa: E402

ARMS = {
    "side": ("sideLeft", "sideRight"),
    "front": ("frontNear", "frontFar"),
}
RESULTS = Path("experiments/results/viewpoint_transfer.csv")


def ids_for(cameras: tuple[str, ...], idd: Path) -> list[str]:
    lines = (idd / "train.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip().split("/")[0] in cameras]


def build_arm(
    name: str, cameras: tuple[str, ...], count: int, spec: dict,
    idd: Path, root: Path, long_edge: int,
) -> dict:
    """One arm: train/val from these cameras, test from the OTHER arm's cameras.

    The cross-evaluation set is the point. An arm evaluated on its own viewpoint
    would report in-domain accuracy and say nothing about transfer.
    """
    import random
    import shutil

    from scripts.prepare_idd import _downscale

    other = next(c for k, c in ARMS.items() if k != name)
    rng = random.Random(spec["seed"])

    own = ids_for(cameras, idd)
    cross = ids_for(other, idd)
    rng.shuffle(own)
    rng.shuffle(cross)

    n_train = int(count * SPLITS["train"] / (SPLITS["train"] + SPLITS["val"]))
    assignment = (
        [("train", i) for i in own[:n_train]]
        + [("val", i) for i in own[n_train:count]]
        # `test` is the OTHER viewpoint — this is the measurement.
        + [("test", i) for i in cross[: int(count * 0.25)]]
    )

    out = root / name
    totals: collections.Counter = collections.Counter()
    written = 0
    for split, identifier in assignment:
        xml_path = idd / "Annotations" / f"{identifier}.xml"
        jpg_path = idd / "JPEGImages" / f"{identifier}.jpg"
        if not xml_path.exists() or not jpg_path.exists():
            continue
        try:
            lines, counts = convert(xml_path, spec)
        except Exception:                                    # noqa: BLE001
            continue
        if not lines:
            continue

        flat = identifier.replace("/", "__")
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split / f"{flat}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        target = out / "images" / split / f"{flat}.jpg"
        if not (long_edge and _downscale(jpg_path, target, long_edge)):
            shutil.copy2(jpg_path, target)
        totals.update(counts)
        written += 1

    (out / "data.yaml").write_text(
        f"# GENERATED — arm '{name}': trained on {cameras}, tested on {other}\n"
        f"path: {out.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        f"nc: {len(spec['targets'])}\nnames: {spec['targets']}\n",
        encoding="utf-8",
    )
    return {"arm": name, "trained_on": "+".join(cameras),
            "tested_on": "+".join(other), "images": written,
            "boxes": sum(v for k, v in totals.items() if not str(k).startswith("UNDECLARED"))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--count", type=int, default=3000,
                        help="images per arm — MATCHED, so the comparison is "
                             "about geometry and not dataset size")
    parser.add_argument("--idd", type=Path, default=IDD)
    parser.add_argument("--root", type=Path, default=Path("data/viewpoint"))
    parser.add_argument("--long-edge", type=int, default=960)
    args = parser.parse_args(argv)

    if args.report:
        if not RESULTS.exists():
            raise SystemExit(
                f"no results at {RESULTS}. Train both arms first, then write "
                f"their cross-viewpoint mAP here — this script does not invent "
                f"numbers it has not seen."
            )
        rows = list(csv.DictReader(RESULTS.open(encoding="utf-8")))
        for row in rows:
            print(f"  {row}")
        return 0

    if not args.prepare:
        parser.error("give --prepare or --report")

    spec = load_mapping()
    summary = []
    for name, cameras in ARMS.items():
        info = build_arm(name, cameras, args.count, spec, args.idd,
                         args.root, args.long_edge)
        summary.append(info)
        print(f"  arm {info['arm']:<6} train {info['trained_on']:<22} "
              f"test {info['tested_on']:<22} {info['images']:>5} images  "
              f"{info['boxes']:>7,} boxes")

    counts = {s["images"] for s in summary}
    if max(counts) - min(counts) > 0.05 * max(counts):
        print(
            f"\n  WARNING: arms differ in size by more than 5% {sorted(counts)}. "
            f"The comparison would\n  measure dataset size as well as viewpoint. "
            f"Lower --count until they match."
        )
    print(f"\n  built {args.root}. Train each arm, then record cross-viewpoint "
          f"mAP in\n  {RESULTS} and run --report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
