"""Freeze the lane-agnostic count forecasters for P103, fitted on NE 8th only.

    python scripts/c1L_freeze.py

Implements the model section of
`experiments/results/bellevue_pilot/PREREGISTRATION_P103.md`. Every NE 8th
daylight window is used, with the three lanes stacked into 3,471 lane-windows.
Each one sees only **its own lane's** 60-sample history (P101's 8 per-lane
features): no other lane, no clock, no camera.

- **C1-L:** ordinary least squares forecasting the 60 s future mean count.
  Thresholds are applied to its output, so it serves any threshold policy.
- **C1-L-cls:** unweighted logistic regression on NE 8th's absolute 2 / 8
  classes, for P103's absolute-threshold arm only.

Written as plain JSON with LF line endings and a recorded SHA-256, and checked:
a pure-Python reload reproduces scikit-learn on every lane-window. No P103
camera is read here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p99_eval import CLASSES, LANES, T, K, level  # noqa: E402
from scripts.p101_counts import features, series  # noqa: E402

CORPUS = Path("data/corpus_p99")
OUT = Path("experiments/results/bellevue_pilot/c1L_v1.json")
NAMES = ("mean60", "mean30", "mean15", "mean5", "last", "std60", "max60", "slope60")


def own_lane(c: list[list[int]], s: int, lane: int) -> list[float]:
    return features(c, s)[8 * lane: 8 * lane + 8]


def future_mean(c: list[list[int]], s: int, lane: int) -> float:
    e = s + T - 1
    return sum(c[x][lane] for x in range(e + 1, e + K + 1)) / K


def regress(artifact: dict, x: list[float]) -> float:
    z = [(v - m) / s for v, m, s in zip(x, artifact["scaler"]["mean"], artifact["scaler"]["scale"])]
    r = artifact["regression"]
    return r["intercept"] + sum(w * v for w, v in zip(r["coef"], z))


def classify(artifact: dict, x: list[float]) -> int:
    z = [(v - m) / s for v, m, s in zip(x, artifact["scaler"]["mean"], artifact["scaler"]["scale"])]
    c = artifact["classifier"]
    scores = [b + sum(w * v for w, v in zip(row, z)) for row, b in zip(c["coef"], c["intercept"])]
    return c["classes"][max(range(len(scores)), key=scores.__getitem__)]


def main() -> int:
    import numpy as np
    import sklearn
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.preprocessing import StandardScaler

    with (CORPUS / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    counts = series()
    X, y_mean, y_cls = [], [], []
    for r in rows:
        c, s = counts[r["clip_id"]], int(r["start_index"])
        for lane in range(len(LANES)):
            X.append(own_lane(c, s, lane))
            y_mean.append(future_mean(c, s, lane))
            y_cls.append(level(y_mean[-1]))
    X = np.array(X)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    reg = LinearRegression().fit(Xs, np.array(y_mean))
    cls = LogisticRegression(C=1.0, max_iter=5000).fit(Xs, np.array(y_cls))

    data_hash = hashlib.sha256((CORPUS / "sequences.csv").read_bytes()
                               + (CORPUS / "counts.csv").read_bytes()).hexdigest()
    artifact = {
        "name": "C1-L v1 (lane-agnostic count forecasters)",
        "protocol": "PREREGISTRATION_P103.md",
        "features": list(NAMES),
        "feature_note": ("one lane's own counts over input samples s..s+59 (2 s step); "
                         "no other lane, no clock, no camera identity"),
        "trained_on": {"camera": "Bellevue NE 8th", "windows": len(rows),
                       "lane_windows": len(X), "data_sha256": data_hash},
        "detector": "ITD-xl best_xl_ITD_v1.2.pt (YOLO11x), conf 0.45, imgsz 992",
        "sklearn": sklearn.__version__,
        "scaler": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()},
        "regression": {"target": "mean count over the next 30 samples (60 s)",
                       "model": "LinearRegression() (OLS)",
                       "coef": reg.coef_.tolist(), "intercept": float(reg.intercept_)},
        "classifier": {"target": "NE 8th absolute classes LOW<=2, MEDIUM<=8, HIGH>8",
                       "model": "LogisticRegression(C=1.0), unweighted",
                       "classes": [int(k) for k in cls.classes_],
                       "coef": cls.coef_.tolist(), "intercept": cls.intercept_.tolist()},
    }
    worst = max(abs(regress(artifact, list(x)) - p) for x, p in zip(X, reg.predict(Xs)))
    wrong = sum(classify(artifact, list(x)) != int(p) for x, p in zip(X, cls.predict(Xs)))
    if worst > 1e-9 or wrong:
        raise SystemExit(f"JSON reload differs from scikit-learn (regression {worst:.2e}, "
                         f"classifier {wrong} lane-windows) — STOP")

    OUT.write_bytes((json.dumps(artifact, indent=2) + "\n").encode("utf-8"))
    print(f"  wrote {OUT}")
    print(f"  sha256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")
    print(f"  {len(X)} NE 8th lane-windows; JSON reload reproduces scikit-learn exactly")
    print(f"  regression coefficients (standardised): "
          + ", ".join(f"{n} {w:+.3f}" for n, w in zip(NAMES, reg.coef_)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
