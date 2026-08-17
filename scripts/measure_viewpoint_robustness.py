"""Measure how far the detector generalises across camera PITCH (A31).

    python scripts/measure_viewpoint_robustness.py

The deployment camera is an elevated fixed camera whose exact angle we do not
control, so viewpoint robustness is a detector requirement rather than a filter
to apply to datasets. This is the measurement that decides whether we have it.

**It needs no labels.** The metric is detections at conf 0.10 divided by
detections at the 0.45 operating point, plus detections per frame — both
computed on BMD-45 images warped to simulate a steeper camera.

Measured before A31's augmentation change (S14 weights):

    pitch 0.00   1.37   9.5 detections/frame
    pitch 1.00   1.72   4.2 detections/frame     <- 56% of detections lost

Barrel distortion over the same range costs only 17%, so **angle is the
variable that matters**, not the fisheye lens I first blamed.

**Pre-registered success criterion (A31):** after retraining with
`perspective=0.0006, degrees=8.0, shear=4.0`, detections per frame at pitch 1.0
must reach at least **70%** of the pitch-0.0 figure, against today's 44%, while
BMD-45 mAP50 stays within 2 points of 0.8915. Fixed before the run, because a
criterion chosen afterwards is a criterion chosen to pass.
"""

import os, sys, glob
os.chdir(r"d:\major project"); sys.path.insert(0, r"d:\major project")
import cv2, numpy as np
from ultralytics import YOLO
from scripts.pilot_a17 import vehicle_ids

m = YOLO("models/detector/s14_yolov8s_joint_best.pt"); ids = vehicle_ids(m)
frames = [cv2.imread(p) for p in sorted(glob.glob("data/bmd45_eval/images/test/*.jpg"))[:30]]

def pitch(img, amount):
    """amount 0 = unchanged, 1 = strongly foreshortened (steeper camera)."""
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    inset = amount * w * 0.35
    dst = np.float32([[inset, 0], [w - inset, 0], [w, h], [0, h]])
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h))

print(f"  {'pitch':>8}{'conf0.10':>10}{'conf0.45':>10}{'ratio':>8}{'det/frame':>12}")
for a in (0.0, 0.25, 0.5, 0.75, 1.0):
    lo = hi = 0
    for f in frames:
        img = pitch(f, a) if a else f
        r = m.predict(source=img, conf=0.10, verbose=False)[0]
        cs = [c for c, cl in zip(r.boxes.conf.tolist(), r.boxes.cls.tolist()) if int(cl) in ids]
        lo += len(cs); hi += sum(1 for c in cs if c >= 0.45)
    print(f"  {a:>8.2f}{lo:>10}{hi:>10}{lo/max(hi,1):>8.2f}{hi/len(frames):>12.1f}")
print("\n  reference: BMD-45 flat 1.37 @ 9.5/frame | Bellevue 2.56-4.17 @ 2-6/frame")
