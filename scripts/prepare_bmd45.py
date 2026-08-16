"""Convert BMD-45 into our YOLO taxonomy (S13, DATASETS, P14).

BMD-45 is 45,986 images / 481,947 boxes from 3,679 operational Safe City CCTV
cameras in Bengaluru — CC BY 4.0, ungated, 1920x1080. It is the elevated fixed
camera this project deploys, and it is the answer to the viewpoint gap that
P5 rev 2 measured.

    python scripts/prepare_bmd45.py --count 8000 --out data/bmd45_yolo
    python scripts/prepare_bmd45.py --count 200 --out data/bmd45_smoke   # check

**Run this inside Kaggle, not on a student's connection.** The full dataset is
153.2 GB at 3.33 MB per PNG. Kaggle's bandwidth and disk are free; a home
connection is neither. Images are fetched individually so a subsample costs only
its own size, and downscaled to a 960 px long edge on the way out because YOLO
trains at 640.

**The mapping is not in this file.** It lives in `indiatrafficnet/class_mapping.yaml`
under `bmd45:`, for the same reason the IDD mapping does (DATASETS §6, "versioned,
not remembered"). A literal here that duplicates that file is a defect.

**This does not replace IDD.** BMD-45 carries no `pedestrian`, no `cattle` and no
`e_rickshaw`. Build both and train on the union — see `--merge-with`.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.prepare_idd import MAPPING, SPLITS, _downscale  # noqa: E402

REPO = "iisc-aim/BMD-45"
TRAIN_PREFIX = "BMD-45-Train"
ANNOTATIONS = f"{TRAIN_PREFIX}/_annotations.coco.json"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main/"


def load_bmd_mapping(path: Path = MAPPING) -> dict:
    """The `bmd45:` block of the shared authority file."""
    import yaml

    if not path.exists():
        raise SystemExit(f"no class mapping at {path}; it must not be inlined here.")
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "bmd45" not in spec:
        raise SystemExit(f"{path} has no `bmd45:` block. Add it there, not here.")

    targets = spec["target_classes"]
    mapping = {k: v for k, v in spec["bmd45"]["mapping"].items() if v is not None}
    unknown = set(mapping.values()) - set(targets)
    if unknown:
        raise SystemExit(f"bmd45 mapping targets undeclared classes: {unknown}")
    return {
        "targets": targets,
        "index": {name: i for i, name in enumerate(targets)},
        "mapping": mapping,
        "declared": set(spec["bmd45"]["mapping"]),
        "seed": spec["sampling"]["seed"],
    }


def fetch_annotations(cache: Path) -> dict:
    import urllib.request

    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    print(f"  fetching {ANNOTATIONS} ...")
    with urllib.request.urlopen(BASE + ANNOTATIONS) as handle:
        raw = handle.read().decode("utf-8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(raw, encoding="utf-8")
    return json.loads(raw)


def to_yolo(boxes: list, width: float, height: float, spec: dict,
            names: dict) -> tuple[list[str], collections.Counter]:
    """COCO xywh (absolute, top-left) -> YOLO cxcywh (normalised)."""
    lines: list[str] = []
    counts: collections.Counter = collections.Counter()
    for box in boxes:
        source = names.get(box["category_id"])
        if source is None:
            continue
        if source not in spec["declared"]:
            counts[f"UNDECLARED:{source}"] += 1     # surfaced, never silent
            continue
        target = spec["mapping"].get(source)
        if target is None:
            continue

        x, y, w, h = box["bbox"]
        x1, y1 = max(0.0, x), max(0.0, y)
        x2, y2 = min(width, x + w), min(height, y + h)
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue
        lines.append(
            f"{spec['index'][target]} {(x1 + x2) / 2 / width:.6f} "
            f"{(y1 + y2) / 2 / height:.6f} {(x2 - x1) / width:.6f} "
            f"{(y2 - y1) / height:.6f}"
        )
        counts[target] += 1
    return lines, counts


def fetch_images(pending: list, long_edge: int, workers: int) -> list:
    """Download and downscale concurrently. Returns the ones that failed.

    Serial fetching runs at roughly 6 images a minute — the cost is per-request
    latency, not bandwidth, so it barely improves on a faster connection. An hour
    for 500 images makes the elevated evaluation set feel expensive enough to
    skip, which is how a measurement stops happening.
    """
    import concurrent.futures
    import urllib.request

    failures: list = []

    def one(job) -> tuple | None:
        file_name, stem, image_dir = job
        target = image_dir / f"{stem}.jpg"
        if target.exists():
            return None
        temporary = image_dir / f"{stem}.png"
        try:
            # `urlretrieve` has NO default timeout. One hung connection blocks a
            # worker forever, and the run stalls at 498 of 499 with no error —
            # observed, not hypothesised.
            with urllib.request.urlopen(
                BASE + f"{TRAIN_PREFIX}/{file_name}", timeout=60
            ) as response:
                temporary.write_bytes(response.read())
        except Exception:                                # noqa: BLE001
            temporary.unlink(missing_ok=True)
            return (stem, image_dir)
        if long_edge and _downscale(temporary, target, long_edge):
            temporary.unlink(missing_ok=True)
        else:
            temporary.replace(target)
        return None

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for outcome in pool.map(one, pending):
            done += 1
            if outcome:
                failures.append(outcome)
            if done % 100 == 0:
                print(f"    {done:,} / {len(pending):,}  ({len(failures)} failed)")
    if failures:
        print(f"  {len(failures)} image(s) failed; their labels were removed too")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=8000,
                        help="images to convert; matched to the IDD subsample so "
                             "neither source silently dominates the union")
    parser.add_argument("--out", type=Path, default=Path("data/bmd45_yolo"))
    parser.add_argument("--long-edge", type=int, default=960)
    parser.add_argument("--cache", type=Path,
                        default=Path("data/_bmd45_annotations.json"))
    parser.add_argument("--min-boxes-per-class", type=int, default=50)
    parser.add_argument("--workers", type=int, default=16,
                        help="concurrent downloads; the cost is per-request "
                             "latency, not bandwidth")
    parser.add_argument("--no-images", action="store_true",
                        help="labels only — inspect the split without the download")
    parser.add_argument(
        "--eval-only", action="store_true",
        help="put every image in `test`. For measuring an EXISTING detector on "
             "elevated imagery, where a 70/15/15 split would spend most of the "
             "download on training data nothing is going to train on",
    )
    args = parser.parse_args(argv)

    spec = load_bmd_mapping()
    coco = fetch_annotations(args.cache)
    names = {c["id"]: c["name"] for c in coco["categories"]}

    by_image: dict[int, list] = collections.defaultdict(list)
    for annotation in coco["annotations"]:
        by_image[annotation["image_id"]].append(annotation)

    images = [i for i in coco["images"] if by_image.get(i["id"])]
    rng = random.Random(spec["seed"])
    rng.shuffle(images)
    chosen = images[: args.count]

    if args.eval_only:
        assignment = [("test", i) for i in chosen]
    else:
        n_train = int(len(chosen) * SPLITS["train"])
        n_val = int(len(chosen) * SPLITS["val"])
        assignment = (
            [("train", i) for i in chosen[:n_train]]
            + [("val", i) for i in chosen[n_train:n_train + n_val]]
            + [("test", i) for i in chosen[n_train + n_val:]]
        )

    totals: collections.Counter = collections.Counter()
    written = skipped = 0
    pending = []
    for split, image in assignment:
        lines, counts = to_yolo(
            by_image[image["id"]], float(image["width"]), float(image["height"]),
            spec, names,
        )
        if not lines:
            skipped += 1
            continue

        stem = Path(image["file_name"]).stem
        label_dir = args.out / "labels" / split
        image_dir = args.out / "images" / split
        label_dir.mkdir(parents=True, exist_ok=True)
        image_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        pending.append((image["file_name"], stem, image_dir))
        totals.update(counts)
        written += 1

    if not args.no_images:
        failures = fetch_images(pending, args.long_edge, args.workers)
        # A label without its image is a silent training-set hole: Ultralytics
        # resolves labels FROM image paths, so the orphan is simply never seen.
        for stem, image_dir in failures:
            (Path(str(image_dir).replace("images", "labels")) / f"{stem}.txt").unlink(
                missing_ok=True
            )
        written -= len(failures)
        skipped += len(failures)

    (args.out / "data.yaml").write_text(
        "# GENERATED by scripts/prepare_bmd45.py — do not edit.\n"
        f"path: {args.out.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        f"nc: {len(spec['targets'])}\nnames: {spec['targets']}\n",
        encoding="utf-8",
    )

    print(f"\n  wrote {written:,} images, skipped {skipped:,}")
    print("\n  boxes per class:")
    for name in spec["targets"]:
        print(f"    {name:<16} {totals.get(name, 0):>9,}")

    undeclared = {k: v for k, v in totals.items() if k.startswith("UNDECLARED:")}
    if undeclared:
        print("\n  CATEGORIES NOT DECLARED IN class_mapping.yaml `bmd45:` —")
        print("  decide them explicitly; silence drops them:")
        for k, v in sorted(undeclared.items(), key=lambda kv: -kv[1]):
            print(f"    {k[11:]:<20} {v:>9,}")
        return 1

    # BMD-45 has no pedestrian, cattle or e_rickshaw BY DESIGN — it is a vehicle
    # dataset. Failing on those would be failing on a documented fact; failing on
    # anything else is a real distribution surprise.
    expected_absent = {"pedestrian", "cattle", "e_rickshaw"}
    thin = {
        name: totals.get(name, 0)
        for name in spec["targets"]
        if name not in expected_absent and totals.get(name, 0) < args.min_boxes_per_class
    }
    if thin:
        print(f"\n  THIN CLASSES (< {args.min_boxes_per_class} boxes): "
              + ", ".join(f"{k}={v}" for k, v in sorted(thin.items())))
        print("  FR-D08 requires per-class support beside every metric. Raise --count.")
        return 1

    print(f"\n  wrote {args.out / 'data.yaml'}")
    print("  NOTE: no pedestrian/cattle/e_rickshaw — BMD-45 is a VEHICLE dataset.")
    print("  Train on the UNION with data/idd_yolo, jointly. Fine-tuning on IDD")
    print("  afterwards would end on a 100% dashcam corpus and un-teach the geometry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
