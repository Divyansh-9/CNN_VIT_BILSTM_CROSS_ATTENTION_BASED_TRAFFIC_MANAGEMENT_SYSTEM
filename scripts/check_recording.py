"""On-site go/no-go for S06 footage — run it BEFORE leaving the junction.

    python scripts/check_recording.py "D:/footage/clip1.mp4"

S06 is the only item on the critical path. It blocks corpus construction, the
confirmation of the counting operating point, and the P12 e-rickshaw decision —
three things at once. A trip that produces unusable footage costs a week, and
the failure is always discovered at a desk rather than at the kerb.

So every threshold below is **measured, not advised**, and the verdict is a
single PASS or FAIL with the specific remedy attached.

**The viewpoint check is the interesting one.** "Mount the camera five to ten
metres up" is guidance nobody can verify while standing there. Instead this
compares the *detected box-size distribution* of your clip against BMD-45 — the
Bengaluru CCTV corpus the detector provably works on at mAP50 0.892. If your
vehicles render at roughly the same fraction of the frame, the geometry matches
the data the model was trained on, whatever height the camera happens to be at.
That is checkable in ninety seconds on a phone clip.

Reference, from `data/bmd45_eval` (5,273 boxes over 498 frames):

    median box area   0.00802 of the frame     (p25 0.00313, p75 0.02004)
    vehicles/frame    median 9, p10 3
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# A15: T=60 steps x 5 s = 295 s of history, plus the 60 s prediction horizon.
MIN_CLIP_S = 355
# Measured on BMD-45, the viewpoint the detector demonstrably works on.
REFERENCE_BOX_AREA = 0.00802
BOX_AREA_TOLERANCE = 3.0        # within a factor of three either way
MIN_VEHICLES_PER_FRAME = 3.0    # BMD-45's 10th percentile
MAX_DRIFT_PX = 12.0             # handheld wobble a fixed camera should not have


def stability(path: Path, samples: int = 40) -> float:
    """Median frame-to-frame shift in pixels, by phase correlation.

    A fixed camera is a premise of the whole corpus: sequences assume the scene
    does not move, and a drifting frame turns a parked car into traffic.
    """
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(path))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // samples)
    shifts, previous = [], None
    for index in range(0, total, step):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        grey = np.float32(cv2.cvtColor(cv2.resize(frame, (480, 270)),
                                       cv2.COLOR_BGR2GRAY))
        if previous is not None:
            (dx, dy), _ = cv2.phaseCorrelate(previous, grey)
            shifts.append((dx * dx + dy * dy) ** 0.5)
        previous = grey
    capture.release()
    return statistics.median(shifts) if shifts else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("clip", type=Path)
    parser.add_argument("--weights", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--conf", type=float, default=0.45,
                        help="the pinned counting operating point, S14b")
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args(argv)

    import cv2

    from ultralytics import YOLO

    from scripts.pilot_a17 import vehicle_ids

    if not args.clip.exists():
        raise SystemExit(f"no such clip: {args.clip}")

    capture = cv2.VideoCapture(str(args.clip))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps if fps else 0.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    print(f"  {args.clip.name}")
    print(f"  {width}x{height}  {fps:.1f} fps  {duration:.0f} s\n")

    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))
    e_rickshaw_id = next((i for i, n in names.items() if n == "e_rickshaw"), None)

    capture = cv2.VideoCapture(str(args.clip))
    step = max(1, total // max(args.frames, 1))
    areas, counts, e_rickshaws, vehicles = [], [], 0, 0
    for index in range(0, total, step):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        result = model.predict(source=frame, conf=args.conf, verbose=False)[0]
        h, w = result.orig_shape
        seen = 0
        for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
            if int(cls) == e_rickshaw_id:
                e_rickshaws += 1
            if int(cls) not in ids:
                continue
            seen += 1
            vehicles += 1
            areas.append(((box[2] - box[0]) * (box[3] - box[1])) / (w * h))
        counts.append(seen)
    capture.release()

    drift = stability(args.clip)
    median_area = statistics.median(areas) if areas else 0.0
    median_count = statistics.median(counts) if counts else 0.0
    ratio = median_area / REFERENCE_BOX_AREA if median_area else 0.0

    checks = []
    checks.append((
        "duration", duration >= MIN_CLIP_S,
        f"{duration:.0f} s (need >= {MIN_CLIP_S} s)",
        "A15: 60 steps x 5 s of history plus a 60 s horizon. Record 15 minutes — "
        "it costs nothing extra and yields many windows instead of one.",
    ))
    checks.append((
        "camera fixed", drift <= MAX_DRIFT_PX,
        f"median drift {drift:.1f} px (need <= {MAX_DRIFT_PX:.0f})",
        "Put the phone on a wall, railing or tripod and do not hold it. A moving "
        "frame turns parked cars into traffic and every count downstream is wrong.",
    ))
    checks.append((
        "viewpoint", 1 / BOX_AREA_TOLERANCE <= ratio <= BOX_AREA_TOLERANCE,
        f"median box {median_area:.5f} of frame, {ratio:.2f}x the BMD-45 reference",
        "Too LARGE means the camera is too low or too close — move higher or "
        "further back. Too SMALL means too far — move closer or zoom in. The "
        "detector scores 0.892 on footage in this range and 0.322 outside it.",
    ))
    checks.append((
        "traffic present", median_count >= MIN_VEHICLES_PER_FRAME,
        f"median {median_count:.0f} vehicles/frame (need >= {MIN_VEHICLES_PER_FRAME:.0f})",
        "An empty approach produces only LOW labels and teaches the model "
        "nothing. Record at a busier time or point at a busier approach.",
    ))

    print(f"  {'check':<16}{'result':<8}detail")
    for name, ok, detail, _ in checks:
        print(f"  {name:<16}{'PASS' if ok else 'FAIL':<8}{detail}")

    failed = [c for c in checks if not c[1]]
    print()
    if failed:
        print("  VERDICT: DO NOT LEAVE YET — this clip is not usable.\n")
        for name, _, _, remedy in failed:
            print(f"  {name}:")
            for line in remedy.split(". "):
                if line.strip():
                    print(f"    {line.strip().rstrip('.')}.")
        print("\n  Fix and re-record now. Discovering this at a desk costs a week.")
    else:
        print("  VERDICT: USABLE. Record a second clip at a different time of day")
        print("  before leaving — one clip is one traffic condition, and the corpus")
        print("  needs LOW, MEDIUM and HIGH to exist at all.")

    share = e_rickshaws / vehicles if vehicles else 0.0
    print(f"\n  P12 e-rickshaw share: {e_rickshaws} of {vehicles} vehicles "
          f"({share:.2%}) — pre-registered rule is 1%")
    print("  Provisional only: this is the detector's count on sampled frames, "
          "and\n  the class has never had labelled training data. The rule is "
          "decided on\n  the full clip with human verification, not on this line.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
