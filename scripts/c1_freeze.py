"""Freeze the C1 count forecaster: P101's specification, fitted once on all 13 hours.

    python scripts/c1_freeze.py

P101 (exploratory) made the count-only logistic regression the working
forecasting candidate under ADR-023's C1. This fits **exactly P101's
specification**, with nothing changed, on every window of the 13 NE 8th
daylight hours (`data/corpus_p99`). P99's and P100's splits are spent, so
nothing here is held out. **The test of this artifact is footage none of
those hours came from.** The class-balanced and boosted variants are not
promoted.

The artifact is plain JSON: the feature definition, the scaler's mean and
scale, each lane's coefficients, intercepts and classes, the thresholds, the
training data's hash and the library version. It is executable without
pickle, so it can be audited and served. Its own SHA-256 is printed and
recorded. The script refuses to finish unless a pure-Python reload of the JSON
reproduces scikit-learn's predictions on every training window, and it times
CPU inference.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p99_eval import CLASSES, LANES  # noqa: E402
from scripts.p101_counts import features, series  # noqa: E402

CORPUS = Path("data/corpus_p99")
OUT = Path("experiments/results/bellevue_pilot/c1_count_forecaster_v1.json")
LANE_KEYS = tuple(LANES)


def predict(artifact: dict, x: list[float]) -> list[int]:
    """The served path: standardise, then argmax of each lane's linear scores."""
    z = [(v - m) / s for v, m, s in zip(x, artifact["scaler"]["mean"], artifact["scaler"]["scale"])]
    out = []
    for lane in artifact["lanes"]:
        scores = [b + sum(w * v for w, v in zip(row, z))
                  for row, b in zip(lane["coef"], lane["intercept"])]
        out.append(lane["classes"][max(range(len(scores)), key=scores.__getitem__)])
    return out


def main() -> int:
    import numpy as np
    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    with (CORPUS / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    counts = series()
    X = np.array([features(counts[r["clip_id"]], int(r["start_index"])) for r in rows])
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    lanes, sk_pred = [], []
    for lane in LANE_KEYS:
        y = np.array([CLASSES.index(r[f"label_{lane}"]) for r in rows])
        model = LogisticRegression(C=1.0, max_iter=5000).fit(Xs, y)
        lanes.append({"lane": lane, "approach": LANES[lane],
                      "classes": [int(c) for c in model.classes_],
                      "coef": model.coef_.tolist(), "intercept": model.intercept_.tolist()})
        sk_pred.append(model.predict(Xs).tolist())

    data_hash = hashlib.sha256((CORPUS / "sequences.csv").read_bytes()
                               + (CORPUS / "counts.csv").read_bytes()).hexdigest()
    artifact = {
        "name": "C1 count forecaster v1", "adr": "ADR-023 C1",
        "specification": "PREREGISTRATION_P101.md, primary model, unchanged",
        "model": "multinomial logistic regression, C=1.0, unweighted, one per lane",
        "features": ("per lane over input samples s..s+59 (2 s step), lanes in order "
                     "west, north, east: mean of last 60, 30, 15, 5; last value; "
                     "population std of 60; max of 60; least-squares slope over 60. "
                     "24 values. No clock feature."),
        "target": "class of mean raw ITD-xl count over the next 30 samples (60 s)",
        "classes": list(CLASSES), "thresholds": {"LOW": "<= 2", "MEDIUM": "<= 8", "HIGH": "> 8"},
        "detector": "ITD-xl best_xl_ITD_v1.2.pt (YOLO11x), conf 0.45, imgsz 992, step 2 s",
        "camera": "Bellevue NE 8th only; lanes west/north/east (P97 geometry)",
        "trained_on": {"windows": len(rows), "hours": 13, "corpus": str(CORPUS),
                       "data_sha256": data_hash},
        "sklearn": sklearn.__version__,
        "scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
        "lanes": lanes,
        "limitations": ("labels are the detector's own future counts (A32); P101 was "
                        "exploratory; not yet tested on footage it has not seen; one camera"),
    }

    # The JSON alone must reproduce scikit-learn on every training window.
    mismatches = sum(predict(artifact, list(x)) != [sk_pred[l][i] for l in range(3)]
                     for i, x in enumerate(X))
    if mismatches:
        raise SystemExit(f"the JSON reproduces scikit-learn on all but {mismatches} windows — STOP")
    started = time.perf_counter()
    for x in X:
        predict(artifact, list(x))
    per_window_us = (time.perf_counter() - started) / len(X) * 1e6

    # LF on every platform, so the recorded hash matches any checkout.
    OUT.write_bytes((json.dumps(artifact, indent=2) + "\n").encode("utf-8"))
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"  wrote {OUT}")
    print(f"  sha256 {digest}")
    print(f"  {len(rows)} windows, 13 hours; JSON reload reproduces scikit-learn on all")
    print(f"  pure-Python CPU inference {per_window_us:.0f} microseconds per window "
          f"(features excluded; this laptop, proxy host)")
    print(f"  training support: " + ", ".join(
        f"{LANES[l]} " + "/".join(str(sum(r[f'label_{l}'] == c for r in rows)) for c in CLASSES)
        for l in LANE_KEYS))
    assert all(math.isfinite(v) for v in artifact["scaler"]["scale"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
