"""Diversify and shrink a pseudo-labelled set for upload (ADR-018).

    python scripts/pack_pseudo.py --src data/pseudo/dhaka_rampura \
        --out data/pseudo_upload --stride 2 --width 1280

`pseudo_label.py` sampled every 15th frame of a 29.97 fps clip — one every half
second. Consecutive frames of a fixed camera half a second apart are largely the
same picture, and 2,400 of them are not 2,400 independent training examples.
Keeping all of them inflates one camera's weight in the training mix without
adding information, which is how a detector learns a camera rather than a
viewpoint.

**So this drops frames on a temporal stride** — `--stride 2` leaves one second
between kept frames — and **downscales**, because the student trains at
`imgsz 640` and 1920x1080 source frames cost four times the bytes for detail no
training step will read. **Labels are normalised coordinates, so resizing does
not touch them**; they are copied verbatim.

Nothing is deleted from `--src`. The full set stays on disk for a later run at a
different stride.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=2,
                        help="keep every Nth frame in time order")
    parser.add_argument("--width", type=int, default=1280,
                        help="downscale to this width; 0 keeps the original")
    parser.add_argument("--quality", type=int, default=88)
    args = parser.parse_args(argv)

    import cv2

    images = sorted((args.src / "images").glob("*.jpg"))
    if not images:
        raise SystemExit(f"no images under {args.src / 'images'}")

    out_images = args.out / "images"
    out_labels = args.out / "labels"
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    kept = boxes = 0
    source_bytes = packed_bytes = 0
    for position, image_path in enumerate(images):
        source_bytes += image_path.stat().st_size
        if position % args.stride:
            continue
        label_path = args.src / "labels" / f"{image_path.stem}.txt"
        if not label_path.is_file():
            continue

        frame = cv2.imread(str(image_path))
        if frame is None:
            continue
        if args.width and frame.shape[1] > args.width:
            height = int(frame.shape[0] * args.width / frame.shape[1])
            frame = cv2.resize(frame, (args.width, height),
                               interpolation=cv2.INTER_AREA)

        target = out_images / image_path.name
        cv2.imwrite(str(target), frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
        packed_bytes += target.stat().st_size
        # Verbatim: YOLO labels are fractions of width and height, so a resize
        # leaves them correct. Rewriting them would only add a way to be wrong.
        shutil.copyfile(label_path, out_labels / label_path.name)
        boxes += sum(1 for line in label_path.read_text(encoding="utf-8").splitlines()
                     if line.strip())
        kept += 1

    print(f"  {len(images)} frames in, {kept} kept (stride {args.stride}), "
          f"{boxes} boxes")
    print(f"  {source_bytes/1e9:.2f} GB -> {packed_bytes/1e9:.2f} GB "
          f"({packed_bytes/max(source_bytes,1):.0%})")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
