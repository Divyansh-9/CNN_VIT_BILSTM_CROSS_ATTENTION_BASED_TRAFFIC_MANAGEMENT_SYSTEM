"""Derive lane polygons for ONE camera from where vehicles actually appear (P17).

    python scripts/survey_lanes.py clip.mp4 --lanes 4 --out data/lanes.json
    python scripts/survey_lanes.py clip.mp4 --lanes 4 --preview

P17: a lane polygon is defined in the image plane, so it belongs to one camera.
Applied to another it counts the wrong region, and every label built on those
counts is arbitrary. Measured across 13 clips sharing one polygon set, the share
of detections falling inside any lane ranged from **13.5% to 94%**.

So polygons have to be surveyed per camera. Doing that by hand means reading
coordinates off a screenshot, which is slow and gets redone every time the camera
moves.

**This surveys them from the footage instead.** Vehicles only appear on the road,
so the spatial distribution of detection centroids IS the road. Cluster those
centroids into `--lanes` groups and each cluster's extent is an approach.

**It is a starting point, not an authority.** The output is JSON meant to be
looked at — `--preview` renders it over a real frame — and edited. A surveyed
polygon that includes a car park is still wrong, and only a human looking at the
picture will notice.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def centroids(clip: Path, model, ids, *, frames: int, conf: float) -> list:
    """Normalised (x, y) of every vehicle detection across sampled frames."""
    import cv2

    capture = cv2.VideoCapture(str(clip))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total // max(frames, 1))
    points = []
    for index in range(0, total, step):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        result = model.predict(source=frame, conf=conf, verbose=False)[0]
        height, width = result.orig_shape
        for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
            if int(cls) not in ids:
                continue
            points.append((
                (box[0] + box[2]) / 2 / width,
                (box[1] + box[3]) / 2 / height,
            ))
    capture.release()
    return points


def cluster(points: list, k: int, *, seed: int = 42, iterations: int = 40) -> list:
    """k-means on the centroids. Deterministic given the seed (NFR-07)."""
    import random

    if len(points) < k:
        raise SystemExit(
            f"only {len(points)} vehicle detections — too few to survey {k} lanes. "
            f"Sample more frames, or check the detector works on this clip."
        )
    rng = random.Random(seed)
    # k-means++ style seeding: spread the initial centres out, because random
    # picks from a dense cluster produce empty lanes on the first pass.
    centres = [points[rng.randrange(len(points))]]
    while len(centres) < k:
        far = max(points, key=lambda p: min((p[0]-c[0])**2 + (p[1]-c[1])**2
                                            for c in centres))
        centres.append(far)

    for _ in range(iterations):
        groups: list[list] = [[] for _ in centres]
        for point in points:
            best = min(range(len(centres)),
                       key=lambda i: (point[0]-centres[i][0])**2
                                     + (point[1]-centres[i][1])**2)
            groups[best].append(point)
        moved = False
        for index, group in enumerate(groups):
            if not group:
                continue
            new = (sum(p[0] for p in group)/len(group),
                   sum(p[1] for p in group)/len(group))
            if new != centres[index]:
                moved = True
            centres[index] = new
        if not moved:
            break
    return groups


def extent(group: list, *, margin: float = 0.02) -> tuple:
    """Axis-aligned box around a cluster, clamped to the frame.

    A box rather than a convex hull: `corpus.geometry.assert_disjoint` requires
    lanes not to overlap, and hulls of adjacent approaches routinely do. A box
    is also what a human can sanity-check at a glance.
    """
    xs = [p[0] for p in group]
    ys = [p[1] for p in group]
    x1 = max(0.0, min(xs) - margin)
    x2 = min(1.0, max(xs) + margin)
    y1 = max(0.0, min(ys) - margin)
    y2 = min(1.0, max(ys) + margin)
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("clip", type=Path)
    parser.add_argument("--lanes", type=int, default=4)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--weights", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--names", nargs="*",
                        help="lane names; defaults to lane_0, lane_1, ...")
    parser.add_argument("--preview", action="store_true",
                        help="render the polygons over a frame — LOOK AT IT")
    parser.add_argument("--out", type=Path, default=Path("data/lanes.json"))
    args = parser.parse_args(argv)

    import cv2

    from ultralytics import YOLO

    from mfstnet.corpus.geometry import Polygon, assert_disjoint
    from scripts.pilot_a17 import vehicle_ids

    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)

    points = centroids(args.clip, model, ids, frames=args.frames, conf=args.conf)
    print(f"  {len(points)} vehicle detections over {args.frames} sampled frames")

    groups = cluster(points, args.lanes)
    names = args.names or [f"lane_{i}" for i in range(args.lanes)]
    if len(names) != args.lanes:
        raise SystemExit(f"{len(names)} names for {args.lanes} lanes")

    order = sorted(range(len(groups)), key=lambda i: -len(groups[i]))
    polygons = []
    print(f"\n  {'lane':<16}{'detections':>12}  extent")
    for name, index in zip(names, order):
        group = groups[index]
        if not group:
            raise SystemExit(f"lane {name} came out empty — try fewer --lanes")
        box = extent(group)
        polygons.append(Polygon(name, box))
        print(f"  {name:<16}{len(group):>12}  "
              f"x {box[0][0]:.2f}-{box[1][0]:.2f}  y {box[0][1]:.2f}-{box[2][1]:.2f}")

    try:
        assert_disjoint(polygons)
        overlap = None
    except Exception as error:                           # noqa: BLE001
        overlap = str(error)
        print(f"\n  OVERLAPPING LANES: {overlap}")
        print("  Clusters ran together, which usually means --lanes is too high")
        print("  for this view, or two approaches genuinely share image space.")
        print("  Edit the JSON before using it; overlapping lanes double-count.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "clip": args.clip.name,
        "surveyed_from": str(args.clip),
        "detections": len(points),
        "disjoint": overlap is None,
        "lanes": [{"name": p.name, "points": [list(v) for v in p.vertices]}
                  for p in polygons],
        "note": (
            "P17: these polygons belong to THIS camera only. Reusing them on "
            "other footage counts the wrong region and every label built on it "
            "is arbitrary. Surveyed automatically from detection density — a "
            "starting point to check by eye, not an authority."
        ),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")

    if args.preview:
        capture = cv2.VideoCapture(str(args.clip))
        capture.set(cv2.CAP_PROP_POS_FRAMES,
                    int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
        ok, frame = capture.read()
        capture.release()
        if ok:
            import numpy as np

            height, width = frame.shape[:2]
            for index, polygon in enumerate(polygons):
                pts = np.array([[int(x * width), int(y * height)]
                                for x, y in polygon.vertices], np.int32)
                colour = [(0, 255, 0), (255, 160, 0), (0, 160, 255),
                          (255, 0, 255)][index % 4]
                cv2.polylines(frame, [pts], True, colour, 3)
                cv2.putText(frame, polygon.name, tuple(pts[0] + [4, 20]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
            target = args.out.with_suffix(".preview.jpg")
            cv2.imwrite(str(target), frame)
            print(f"  preview {target}")
            print("  LOOK AT IT. A polygon covering a car park is still wrong,")
            print("  and only the picture will tell you.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
