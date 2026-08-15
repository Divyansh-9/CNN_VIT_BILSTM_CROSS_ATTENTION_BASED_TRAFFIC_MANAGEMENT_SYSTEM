"""Convert IDD Detection into a YOLO training set (S08–S09, ADR-001, FR-D03/D05).

IDD ships Pascal-VOC XML at 24 GB across 46,588 annotated images. Ultralytics
wants YOLO text labels and a `data.yaml`. This does that conversion, applies the
`indiatrafficnet/class_mapping.yaml` mapping, and subsamples.

    python scripts/prepare_idd.py --count 8000
    python scripts/prepare_idd.py --count 200 --out data/idd_smoke   # quick check

**Nothing here is hardcoded that the mapping file already states.** The class
list, the drops, the `rider` decision and the sampling weights all come from
`class_mapping.yaml` (DATASETS §6: "versioned, not remembered"). A literal in
this script that duplicates that file is a defect.

**Why the subsample is stratified by camera position.** IDD is captured from a
car-mounted rig — `frontFar`, `frontNear`, `sideLeft`, `sideRight`, `rearNear`,
plus the better-annotated `highquality_16k`. The deployment target is an
elevated, stationary camera looking down at a junction, which is the viewpoint
gap DATASETS §2 opens with. Camera position is recorded per image, so weighting
toward the side views costs nothing and is not a guess.

It is still a *prior*, and it is labelled as one in the mapping file: S12 tests
it by fine-tuning on side-weighted and front-weighted subsets and reporting the
mAP gap on real junction footage.

**Splits are 70/15/15 stratified (FR-D05)** — note this differs from MFSTNet's
60/20/20 (§8.4). Different number, different purpose; conflating them is an easy
mistake to make once.
"""

from __future__ import annotations

import argparse
import collections
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

IDD = Path("D:/traffic dataset/downloads/idd-detection/IDD_Detection")
MAPPING = Path("indiatrafficnet/class_mapping.yaml")
SPLITS = {"train": 0.70, "val": 0.15, "test": 0.15}      # FR-D05


def load_mapping(path: Path = MAPPING) -> dict:
    import yaml

    if not path.exists():
        raise SystemExit(
            f"no class mapping at {path}. It is the authority for how a public "
            f"label becomes one of ours (DATASETS §6) and must not be inlined here."
        )
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = spec["target_classes"]
    index = {name: i for i, name in enumerate(targets)}
    # Drop entries are explicit nulls, not omissions — an unmapped label should
    # be noticed, not silently discarded.
    mapping = {k: v for k, v in spec["mapping"].items() if v is not None}
    unknown = {v for v in mapping.values()} - set(targets)
    if unknown:
        raise SystemExit(f"mapping targets classes not in target_classes: {unknown}")
    return {
        "targets": targets,
        "index": index,
        "mapping": mapping,
        "declared": set(spec["mapping"]),
        "weights": spec["sampling"]["weights"],
        "seed": spec["sampling"]["seed"],
    }


def convert(xml_path: Path, spec: dict) -> tuple[list[str], collections.Counter]:
    """VOC XML -> YOLO lines. Returns (lines, per-class box counts)."""
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    width = float(size.find("width").text)
    height = float(size.find("height").text)
    if width <= 0 or height <= 0:
        return [], collections.Counter()

    lines: list[str] = []
    counts: collections.Counter = collections.Counter()
    for obj in root.findall("object"):
        name_node = obj.find("name")
        if name_node is None:
            continue
        name = (name_node.text or "").strip()
        target = spec["mapping"].get(name)
        if target is None:
            if name not in spec["declared"]:
                counts[f"UNDECLARED:{name}"] += 1     # surfaced, never silent
            continue

        box = obj.find("bndbox")
        x1, y1 = float(box.find("xmin").text), float(box.find("ymin").text)
        x2, y2 = float(box.find("xmax").text), float(box.find("ymax").text)
        x1, x2 = sorted((max(0.0, x1), min(width, x2)))
        y1, y2 = sorted((max(0.0, y1), min(height, y2)))
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue

        cx, cy = (x1 + x2) / 2 / width, (y1 + y2) / 2 / height
        bw, bh = (x2 - x1) / width, (y2 - y1) / height
        lines.append(f"{spec['index'][target]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        counts[target] += 1

    return lines, counts


def choose(ids: list[str], spec: dict, count: int) -> list[str]:
    """Weighted stratified sample by camera position, deterministic."""
    by_camera: dict[str, list[str]] = collections.defaultdict(list)
    for i in ids:
        by_camera[i.split("/")[0]].append(i)

    weights = {c: spec["weights"].get(c, 1.0) for c in by_camera}
    total_weight = sum(w * len(by_camera[c]) for c, w in weights.items())
    rng = random.Random(spec["seed"])

    picked: list[str] = []
    for camera, pool in sorted(by_camera.items()):
        share = weights[camera] * len(pool) / total_weight if total_weight else 0
        take = min(len(pool), round(count * share))
        picked.extend(rng.sample(pool, take))
    rng.shuffle(picked)
    return picked[:count]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=8000,
                        help="images to convert (FEASIBILITY-AUDIT: annotation "
                             "effort is the constraint, not image supply)")
    parser.add_argument("--idd", type=Path, default=IDD)
    parser.add_argument("--out", type=Path, default=Path("data/idd_yolo"))
    parser.add_argument("--copy-images", action="store_true",
                        help="copy JPEGs (24 GB source; symlink-free but slow)")
    args = parser.parse_args(argv)

    if not (args.idd / "train.txt").exists():
        raise SystemExit(f"IDD not found at {args.idd}")

    spec = load_mapping()
    ids = [l.strip() for l in (args.idd / "train.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    chosen = choose(ids, spec, args.count)

    rng = random.Random(spec["seed"])
    rng.shuffle(chosen)
    n_train = int(len(chosen) * SPLITS["train"])
    n_val = int(len(chosen) * SPLITS["val"])
    assignment = (
        [("train", i) for i in chosen[:n_train]]
        + [("val", i) for i in chosen[n_train:n_train + n_val]]
        + [("test", i) for i in chosen[n_train + n_val:]]
    )

    totals: collections.Counter = collections.Counter()
    per_split: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    written = skipped = 0

    for split, identifier in assignment:
        xml_path = args.idd / "Annotations" / f"{identifier}.xml"
        jpg_path = args.idd / "JPEGImages" / f"{identifier}.jpg"
        if not xml_path.exists() or not jpg_path.exists():
            skipped += 1
            continue
        try:
            lines, counts = convert(xml_path, spec)
        except ET.ParseError:
            skipped += 1
            continue
        if not lines:
            # No box survived the mapping. Keeping it would teach the detector
            # that a busy Indian street contains nothing.
            skipped += 1
            continue

        flat = identifier.replace("/", "__")
        label_dir = args.out / "labels" / split
        image_dir = args.out / "images" / split
        label_dir.mkdir(parents=True, exist_ok=True)
        image_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / f"{flat}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if args.copy_images:
            shutil.copy2(jpg_path, image_dir / f"{flat}.jpg")
        else:
            (image_dir / f"{flat}.txt").write_text(str(jpg_path), encoding="utf-8")

        totals.update(counts)
        per_split[split].update(counts)
        written += 1

    data_yaml = args.out / "data.yaml"
    data_yaml.parent.mkdir(parents=True, exist_ok=True)
    data_yaml.write_text(
        "# GENERATED by scripts/prepare_idd.py — do not edit.\n"
        f"path: {args.out.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        f"nc: {len(spec['targets'])}\n"
        f"names: {spec['targets']}\n",
        encoding="utf-8",
    )

    print(f"  wrote {written} images, skipped {skipped}")
    for split in ("train", "val", "test"):
        n = sum(1 for s, _ in assignment if s == split)
        print(f"    {split:<6} {n:>6} assigned  {sum(per_split[split].values()):>7,} boxes")
    print("\n  boxes per class:")
    for name in spec["targets"]:
        print(f"    {name:<16} {totals.get(name, 0):>8,}")
    undeclared = {k: v for k, v in totals.items() if k.startswith("UNDECLARED:")}
    if undeclared:
        print("\n  LABELS NOT DECLARED IN class_mapping.yaml — decide them explicitly:")
        for k, v in sorted(undeclared.items(), key=lambda kv: -kv[1]):
            print(f"    {k[11:]:<20} {v:>8,}")
    print(f"\n  wrote {data_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
