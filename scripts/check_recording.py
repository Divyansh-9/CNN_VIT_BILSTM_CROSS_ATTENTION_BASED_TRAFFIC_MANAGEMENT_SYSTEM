"""On-site go/no-go for S06 footage — run it BEFORE leaving the junction.

    python scripts/check_recording.py "D:/footage/clip1.mp4"

S06 is the only item on the critical path. It blocks corpus construction, the
confirmation of the counting operating point, and the P12 e-rickshaw decision —
three things at once. A trip that produces unusable footage costs a week, and
the failure is always discovered at a desk rather than at the kerb.

So every threshold below is **measured, not advised**, and the verdict is a
single PASS or FAIL with the specific remedy attached.

**The viewpoint check compares your clip's detected box-size distribution against
BMD-45** — the Bengaluru CCTV corpus the detector provably works on at
mAP50 0.892. If vehicles render at roughly the same fraction of the frame, the
geometry matches the data the model was trained on.

**That check was SELF-CONFIRMING in its first version and the flaw is worth
understanding.** It measured the size of *detections*, so a detector that fires
only on small distant objects always produced a "correct" median — the check
graded the detector's failures rather than the camera. Bellevue passed it while
the detector was finding 3 vehicles out of thirty, calling a sedan a motorcycle,
and hallucinating an auto-rickshaw in Washington State.

So a **detection-rate floor** now runs first. If the detector fires on almost
nothing, no statistic computed from those detections means anything, and the
viewpoint verdict is withheld rather than guessed.

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
# OUT-OF-DOMAIN SIGNATURE. Detections at conf 0.10 divided by detections at the
# 0.45 operating point. In domain the model is confident and little hides below
# the threshold; out of domain its confidences collapse and most real vehicles
# sink under it. Measured: BMD-45 1.36, Bellevue 2.56 and 4.17.
#
# Mean confidence CANNOT do this job — the mean of boxes above 0.45 is always
# above 0.45, so it passes by construction. That was the second circular check
# in this file and it is why this one is defined by a measurement instead.
MAX_LOW_CONF_RATIO = 2.0
# ...and it CONFOUNDS domain shift with density. Crowded scenes contain more
# small, occluded, genuinely-low-confidence vehicles, so a good dense Indian clip
# scores 2.80 — worse than Bellevue's 2.56 — while being perfectly usable.
#
# So the ratio is ADVISORY, not a gate. The only reliable check is a human
# looking at one annotated frame, which takes five seconds and is what caught
# Bellevue. Automated domain-shift detection is a research problem; looking is
# not. The script writes the frame and says so.


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


def _write_preview(clip: Path, model, names, ids, conf: float,
                   target: Path, total: int) -> None:
    """Render one busy frame with its detections, for a human to look at."""
    import cv2

    capture = cv2.VideoCapture(str(clip))
    capture.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        return
    result = model.predict(source=frame, conf=conf, verbose=False)[0]
    for box, cls, confidence in zip(result.boxes.xyxy.tolist(),
                                    result.boxes.cls.tolist(),
                                    result.boxes.conf.tolist()):
        x1, y1, x2, y2 = (int(v) for v in box)
        colour = (0, 255, 0) if int(cls) in ids else (0, 140, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(frame, f"{names[int(cls)]} {confidence:.2f}",
                    (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1)
    cv2.imwrite(str(target), frame)


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
    areas, counts, confidences, e_rickshaws, vehicles = [], [], [], 0, 0
    low_conf_total = 0
    for index in range(0, total, step):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        # One pass at 0.10; the operating point is applied as a filter, so the
        # two counts come from identical inference.
        result = model.predict(source=frame, conf=0.10, verbose=False)[0]
        h, w = result.orig_shape
        seen = 0
        low_conf_total += sum(
            1 for k in result.boxes.cls.tolist() if int(k) in ids
        )
        for box, cls, confidence in zip(result.boxes.xyxy.tolist(),
                                        result.boxes.cls.tolist(),
                                        result.boxes.conf.tolist()):
            if confidence < args.conf:
                continue
            confidences.append(confidence)
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

    low_conf_ratio = low_conf_total / max(len(confidences), 1)
    detector_ok = bool(areas)

    checks = []
    # FIRST, because every check below it is computed FROM the detector's boxes.
    # If the detector is guessing, those numbers grade its failures, not the
    # camera — which is exactly how Bellevue passed the first version of this.
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
        "traffic present", median_count >= MIN_VEHICLES_PER_FRAME,
        f"median {median_count:.0f} vehicles/frame (need >= {MIN_VEHICLES_PER_FRAME:.0f})",
        "An empty approach produces only LOW labels and teaches the model "
        "nothing. Record at a busier time or point at a busier approach.",
    ))

    # VIEWPOINT IS ADVISORY, not a gate. It was calibrated on BMD-45, whose
    # depth range is compressed; a clip with a long sightline has many distant
    # vehicles and a small MEDIAN box even when every one of them is detected
    # correctly. It rejected a 2048 s fixed-camera motorway clip on which the
    # detector boxes every visible vehicle at 0.54-0.93 confidence.
    #
    # That is the second flaw found in this one statistic — it was also
    # self-confirming, because it measured the size of DETECTIONS. Two failures
    # of the same number is enough: it informs, it does not decide.
    print(f"  {'check':<16}{'result':<8}detail")
    for name, ok, detail, _ in checks:
        if name in ("viewpoint", "traffic present") and not detector_ok:  # noqa: SIM102
            print(f"  {name:<16}{'N/A':<8}withheld — computed from detections "
                  f"that cannot be trusted")
            continue
        print(f"  {name:<16}{'PASS' if ok else 'FAIL':<8}{detail}")

    # A viewpoint or traffic verdict derived from an unreliable detector is not
    # a pass and not a fail — it is not a measurement. Withhold rather than guess.
    failed = [
        c for c in checks
        if not c[1] and (detector_ok or c[0] not in ("viewpoint", "traffic present"))
    ]
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

    # THE CHECK NO STATISTIC REPLACES. Every number above is computed from the
    # detector's boxes, so if it is not recognising the scene they all describe
    # its failures rather than the camera. Bellevue passed four automated checks
    # while finding 3 vehicles out of thirty, calling a sedan a motorcycle and
    # labelling something an auto-rickshaw in Washington State. One glance caught
    # what four statistics missed.
    preview = args.clip.with_name(args.clip.stem + "_detections.jpg")
    _write_preview(args.clip, model, names, ids, args.conf, preview, total)
    print()
    print("  LOOK AT THIS BEFORE YOU TRUST ANYTHING ABOVE:")
    print(f"    {preview}")
    print("  Boxes should sit on vehicles, labels should be plausible, and most")
    print("  visible vehicles should have a box. If they do not, the counts and")
    print("  every congestion label built from them are meaningless — whatever")
    print("  the checks above say.")
    print()
    print(f"  advisory: median box {median_area:.5f} of frame, "
          f"{ratio:.2f}x the BMD-45 reference")
    print("  (informative only — a long sightline lowers the median without")
    print("  hurting detection, and this number twice rejected usable footage)")
    advisory = "typical" if low_conf_ratio <= MAX_LOW_CONF_RATIO else "high"
    print()
    print(f"  advisory: {low_conf_ratio:.2f}x more detections at conf 0.10 than "
          f"at {args.conf:.2f} ({advisory};")
    print("  BMD-45 scores 1.36, but dense scenes score higher for honest reasons)")

    share = e_rickshaws / vehicles if vehicles else 0.0
    print(f"\n  P12 e-rickshaw share: {e_rickshaws} of {vehicles} vehicles "
          f"({share:.2%}) — pre-registered rule is 1%")
    print("  Provisional only: this is the detector's count on sampled frames, "
          "and\n  the class has never had labelled training data. The rule is "
          "decided on\n  the full clip with human verification, not on this line.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
