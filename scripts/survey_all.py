"""Survey lane polygons for every qualifying camera, for review in one pass.

    python scripts/survey_all.py --min-seconds 178 --lanes 2 --out data/lanes

P17 requires polygons per camera, and `survey_lanes.py` produces them one clip at
a time with a warning it means literally: the output is a starting point to look
at, not an authority. A polygon covering a car park is still wrong and only the
picture reveals it.

That warning is the bottleneck. Twelve cameras surveyed one at a time is twelve
context switches; **the machine half is a minute of compute and the human half is
the whole cost.** So this runs all of them, renders a preview for each, and
prints a single table with the automatic checks already applied — so the review
is "look at twelve pictures and name the bad ones" rather than twelve separate
invocations.

**Nothing here is trusted.** Every polygon set is written with `reviewed: false`
in its JSON. `build_corpus.py` should refuse an unreviewed set; the value of this
script is making review cheap, not skipping it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--triage", type=Path,
                        default=Path("experiments/results/footage_triage.csv"))
    parser.add_argument("--root", type=Path, default=Path("D:/traffic dataset"))
    parser.add_argument("--min-seconds", type=float, default=178.0,
                        help="A15 minimum at step_s=2. 355 at step_s=5")
    parser.add_argument("--lanes", type=int, default=2)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--weights", type=Path,
                        default=Path("models/detector/s15_yolov8s_joint_aug_best.pt"))
    parser.add_argument("--imgsz", type=int, default=640,
                        help="run the detector at the size it trained at; "
                             "ITD-x is 992")
    parser.add_argument("--max-box-area", type=float, default=0.05,
                        help="drop boxes over this fraction of the frame. "
                             "ADR-018 measured 65%% of ITD's bus boxes and "
                             "43%% of its trucks oversized on this footage")
    parser.add_argument("--max-radius", type=float, default=0.25,
                        help="normalised distance beyond which a detection is "
                             "unassigned")
    parser.add_argument("--max-unassigned", type=float, default=0.35,
                        help="P17's gate: above this the camera is a "
                             "misconfiguration, not sparse data")
    parser.add_argument("--out", type=Path, default=Path("data/lanes"))
    args = parser.parse_args(argv)

    import cv2
    import numpy as np
    from ultralytics import YOLO

    from mfstnet.corpus.identity import (
        group_cameras, scene_signature, stable_stem,
    )
    from mfstnet.corpus.lanes import LaneCentres, assign_to_lane
    from scripts.pilot_a17 import vehicle_ids
    from scripts.survey_lanes import centroids, cluster

    with args.triage.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    candidates = [r for r in rows
                  if r["camera_fixed"].lower() == "true"
                  and float(r["seconds"]) >= args.min_seconds]
    candidates.sort(key=lambda r: -float(r["seconds"]))
    if not candidates:
        raise SystemExit(f"no fixed-camera clip reaches {args.min_seconds}s")

    args.out.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)

    print(f"  {len(candidates)} camera(s) at >= {args.min_seconds:.0f}s\n")
    print("  {:<44}{:>7}{:>11}{:>18}".format(
        "camera", "dets", "unassigned", "status"))
    summary = []
    for row in candidates:
        clip = args.root / row["file"]
        if not clip.is_file():
            matches = list(args.root.rglob(row["file"]))
            if not matches:
                print("  {:<44}{:>7}{:>9}{:>10}".format(row["file"][:42], "-", "-", "MISSING"))
                continue
            clip = matches[0]

        # Hash-suffixed, because truncating to a fixed length collided: two
        # clips differing only after 48 characters wrote the same files and one
        # silently overwrote the other. Twelve cameras produced eleven previews.
        stem = stable_stem(str(clip))
        try:
            points = centroids(clip, model, ids, frames=args.frames,
                               conf=args.conf, imgsz=args.imgsz,
                               max_box_area=args.max_box_area)
            groups = cluster(points, args.lanes)
            centres = tuple(
                (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))
                for g in groups if g)
        except SystemExit as error:              # too few detections to cluster
            print("  {:<44}{:>7}{:>9}{:>10}".format(stem[:42], "-", "-", "TOO FEW"))
            summary.append({"camera": stem, "status": "too few detections",
                            "detail": str(error)[:120]})
            continue

        # Order left-to-right so `lane_0` means the same thing on every camera.
        centres = tuple(sorted(centres, key=lambda c: c[0]))
        names = tuple(f"lane_{i}" for i in range(len(centres)))
        lanes = LaneCentres(names=names, centres=centres,
                            max_radius=args.max_radius)

        assigned = [assign_to_lane(p, lanes) for p in points]
        unassigned = sum(1 for a in assigned if a is None)
        rate = unassigned / len(points) if points else 1.0

        target = args.out / f"{stem}.json"
        target.write_text(json.dumps({
            "clip": clip.name, "surveyed_from": str(clip),
            "detections": len(points),
            "unassigned_rate": round(rate, 4),
            "max_radius": args.max_radius,
            "reviewed": False,
            "lanes": [{"name": n, "centre": list(c)} for n, c in zip(names, centres)],
            "note": ("AUTOMATIC AND UNREVIEWED. Nearest-centre assignment is "
                     "disjoint by construction, so there is no overlap to fix "
                     "-- but whether these centres sit on real approaches is "
                     "still a question only the preview answers. P17: they "
                     "belong to THIS camera only."),
        }, indent=2), encoding="utf-8")

        capture = cv2.VideoCapture(str(clip))
        capture.set(cv2.CAP_PROP_POS_FRAMES,
                    int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
        ok, frame = capture.read()
        capture.release()
        if ok:
            height, width = frame.shape[:2]
            palette = [(80, 220, 120), (255, 170, 60), (60, 180, 255), (255, 0, 255)]

            # BOXES for the detections in THIS frame, because object detection
            # is read as boxes and a centroid hides both the extent and whether
            # the box was right. P23: drawing dots for both the detections and
            # the lane assignment made it impossible to see that the detector
            # misses four auto-rickshaws on the Mumbai camera.
            result = model.predict(source=frame, conf=args.conf,
                                   imgsz=args.imgsz, verbose=False)[0]
            for box, cls in zip(result.boxes.xyxy.tolist(),
                                result.boxes.cls.tolist()):
                if int(cls) not in ids:
                    continue
                cx = (box[0] + box[2]) / 2 / width
                cy = (box[1] + box[3]) / 2 / height
                lane = assign_to_lane((cx, cy), lanes)
                colour = palette[names.index(lane) % 4] if lane else (150, 150, 150)
                cv2.rectangle(frame, (int(box[0]), int(box[1])),
                              (int(box[2]), int(box[3])), colour, 2)
                cv2.putText(frame, model.names[int(cls)][:12],
                            (int(box[0]), max(14, int(box[1]) - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1)

            # Faint centroids from the other sampled frames, so the shape the
            # clustering actually saw stays visible behind the boxes.
            for point, lane in zip(points, assigned):
                px = (int(point[0] * width), int(point[1] * height))
                colour = palette[names.index(lane) % 4] if lane else (150, 150, 150)
                cv2.circle(frame, px, 2, colour, -1)

            for index, (name, centre) in enumerate(zip(names, centres)):
                px = (int(centre[0] * width), int(centre[1] * height))
                colour = palette[index % 4]
                cv2.drawMarker(frame, px, (255, 255, 255), cv2.MARKER_CROSS, 34, 5)
                cv2.drawMarker(frame, px, colour, cv2.MARKER_CROSS, 34, 3)
                cv2.putText(frame, name, (px[0] + 16, px[1] - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 4)
                cv2.putText(frame, name, (px[0] + 16, px[1] - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, colour, 2)

            banner = (f"{len(result.boxes)} boxes this frame  |  "
                      f"{len(points)} centroids over {args.frames} frames  |  "
                      f"{rate:.0%} unassigned")
            cv2.putText(frame, banner, (16, 42), cv2.FONT_HERSHEY_SIMPLEX,
                        0.95, (255, 255, 255), 5)
            cv2.putText(frame, banner, (16, 42), cv2.FONT_HERSHEY_SIMPLEX,
                        0.95, (25, 25, 25), 2)
            scaled = cv2.resize(frame, (960, int(frame.shape[0] * 960 / frame.shape[1])))
            cv2.imwrite(str(args.out / f"{stem}.preview.jpg"), scaled,
                        [cv2.IMWRITE_JPEG_QUALITY, 82])

        # P17's gate: a camera whose detections mostly fall outside every lane
        # is a misconfiguration, not sparse data.
        status = "ok" if rate <= args.max_unassigned else "TOO MANY OUTSIDE"
        print("  {:<44}{:>7}{:>11}{:>18}".format(
            stem[:42], len(points), f"{rate:.1%}", status))
        signature = None
        if ok:
            signature = scene_signature(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        summary.append({"camera": stem, "clip": clip.name,
                        "seconds": float(row["seconds"]),
                        "detections": len(points),
                        "unassigned_rate": round(rate, 4), "status": status,
                        "signature": signature})

    # A camera split is only leak-free if "camera" is identified correctly, and
    # a filename does not identify one. Measured: M6 Motorway and "Road traffic
    # video for object recognition" are the same motorway from the same
    # viewpoint at 0.981 correlation, under two names.
    signatures = {s["camera"]: s["signature"] for s in summary if s.get("signature")}
    groups = group_cameras(signatures) if signatures else {}
    for entry in summary:
        entry["camera_id"] = groups.get(entry["camera"], entry["camera"])
        entry.pop("signature", None)

    distinct = len(set(groups.values())) if groups else len(summary)
    duplicates = {}
    for clip, camera in groups.items():
        duplicates.setdefault(camera, []).append(clip)
    shared = {k: v for k, v in duplicates.items() if len(v) > 1}
    if shared:
        print()
        print(f"  DUPLICATE CAMERAS — {len(shared)} group(s) share a viewpoint:")
        for camera, members in shared.items():
            print(f"    {camera}")
            for member in members:
                if member != camera:
                    print(f"      = {member}")
        print("  These MUST share a split. Two files of one camera on opposite")
        print("  sides of a split means testing on a camera we trained on.")

    (args.out / "survey_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    bad = [s for s in summary if s.get("status") not in ("ok", None)]
    print()
    print(f"  wrote {args.out}")
    print(f"  {len(summary)} clip(s) surveyed  ->  {distinct} DISTINCT camera(s)")
    print(f"  {len(bad)} over the {args.max_unassigned:.0%} unassigned gate")
    print()
    print("  Nearest-centre assignment cannot overlap, so nothing needs editing.")
    print("  EVERY set is marked reviewed:false: the previews still have to be")
    print("  looked at, because a centre on a car park is as wrong as a box was.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
