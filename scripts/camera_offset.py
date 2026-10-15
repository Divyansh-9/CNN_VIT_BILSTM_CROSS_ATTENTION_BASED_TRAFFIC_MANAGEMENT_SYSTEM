"""How far each clip's view has moved from a reference, at the lane centres.

    python scripts/camera_offset.py --reference REF.mp4 --lanes LANES.json CLIP...

Frozen lanes are only valid if the camera has not moved, and a filename or
folder cannot say whether it has. A whole-frame similarity cannot either: on a
fixed camera a building's shadow sweeping the junction drops it from 0.86 to
0.22 (P98). This registers static structure instead. ORB features on
contrast-equalised frames (the clock strip masked), a RANSAC homography from
the reference, and the displacement that homography gives each lane centre,
as a fraction of frame width. Several frame pairs per clip, so one frame
dominated by shadow or glare cannot decide the answer; the median is reported,
with how many pairs registered at all.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

REFERENCE_AT = (0.1, 0.5, 0.9)
CLIP_AT = (0.05, 0.25, 0.5, 0.75, 0.95)
MIN_INLIERS = 100          # fewer is a failed registration, not a measurement


def frame(path: Path, fraction: float):
    import cv2

    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES,
                int(capture.get(cv2.CAP_PROP_FRAME_COUNT) * fraction))
    ok, image = capture.read()
    capture.release()
    if not ok:
        raise SystemExit(f"{path}: no frame at {fraction}")
    gray = cv2.createCLAHE(3.0, (8, 8)).apply(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    gray[int(gray.shape[0] * 0.94):] = 0     # the burnt-in clock changes every frame
    return gray


def main(argv: list[str] | None = None) -> int:
    import cv2
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("clips", nargs="+", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--lanes", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    lanes = json.loads(args.lanes.read_text(encoding="utf-8"))["lanes"]
    orb = cv2.ORB_create(6000)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    references = []
    for at in REFERENCE_AT:
        image = frame(args.reference, at)
        references.append((image.shape, *orb.detectAndCompute(image, None)))

    report = {}
    for clip in args.clips:
        shifts, failed = [], 0
        for at in CLIP_AT:
            keys, descriptors = orb.detectAndCompute(frame(clip, at), None)
            for (height, width), ref_keys, ref_descriptors in references:
                matches = matcher.match(ref_descriptors, descriptors)
                a = np.float32([ref_keys[m.queryIdx].pt for m in matches])
                b = np.float32([keys[m.trainIdx].pt for m in matches])
                H, inliers = cv2.findHomography(a, b, cv2.RANSAC, 3.0)
                if H is None or int(inliers.sum()) < MIN_INLIERS:
                    failed += 1
                    continue
                points = np.float32([[x * width, y * height] for x, y in
                                     (lane["centre"] for lane in lanes)]).reshape(-1, 1, 2)
                moved = cv2.perspectiveTransform(points, H) - points
                shifts.append(float(np.linalg.norm(moved.reshape(-1, 2), axis=1).max() / width))
        pairs = len(CLIP_AT) * len(REFERENCE_AT)
        entry = {"registered": f"{pairs - failed}/{pairs}",
                 "median_shift": round(statistics.median(shifts), 4) if shifts else None,
                 "max_shift": round(max(shifts), 4) if shifts else None}
        report[clip.stem] = entry
        print(f"  {clip.stem:<48} registered {entry['registered']:>5}  "
              f"median {entry['median_shift']}  max {entry['max_shift']}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
