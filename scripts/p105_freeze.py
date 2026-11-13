"""P105 — fit and freeze the change forecaster on footage already used.

    python scripts/p105_freeze.py

Implements the model section of
`experiments/results/bellevue_pilot/PREREGISTRATION_P105.md`, before any P105
footage is chosen or counted.

- **Training:** every eligible window of NE 8th's 13 hours (`data/corpus_p99`)
  and the 10 P103 hours (`data/corpus_p103`), all lanes stacked, windows cut
  per file (a start every 15 samples, inputs s … s+59, target e+1 … e+30).
- **Model:** `Ridge(alpha=1.0, fit_intercept=False)` on five unstandardised
  **difference** features, predicting Δ = next 60 s mean − last 60 s mean.
  With no intercept and only differences, adding a constant to a lane's counts
  leaves Δ̂ unchanged, and scaling them scales Δ̂: the model cannot carry a
  camera's level. Both properties are checked numerically before writing.

Writes `experiments/results/bellevue_pilot/p105_ridge_v1.json`, LF, with its
SHA-256 printed for the record.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

T, K, STRIDE = 60, 30, 15
OUT = Path("experiments/results/bellevue_pilot/p105_ridge_v1.json")
SOURCES = [Path("data/corpus_p99")] + [Path(f"data/corpus_p103/{c}") for c in
                                       ("150th_Eastgate", "150th_Newport", "150th_SE38th")]
NAMES = ("mean30-mean60", "mean15-mean30", "mean5-mean15", "last-mean30", "slope60")


def change_features(v: list[float], s: int) -> list[float]:
    """Five differences of one lane's own counts over inputs s … s+59."""
    w = v[s:s + T]
    m60, m30 = statistics.fmean(w), statistics.fmean(w[-30:])
    m15, m5 = statistics.fmean(w[-15:]), statistics.fmean(w[-5:])
    xs = range(T)
    x_mean = statistics.fmean(xs)
    slope = (sum((x - x_mean) * (y - m60) for x, y in zip(xs, w))
             / sum((x - x_mean) ** 2 for x in xs))
    return [m30 - m60, m15 - m30, m5 - m15, w[-1] - m30, slope]


def recent_mean(v: list[float], e: int) -> float:
    return sum(v[e - K + 1:e + 1]) / K


def future_mean(v: list[float], e: int) -> float:
    return sum(v[e + 1:e + K + 1]) / K


def trend(v: list[float], s: int) -> float:
    """The frozen baseline: the last minute-over-minute change, continued."""
    e = s + T - 1
    return recent_mean(v, e) - sum(v[e - 59:e - 29]) / 30


def lane_series(root: Path) -> list[list[float]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    lanes = manifest["lanes"]
    clips: dict[str, list[list[int]]] = {}
    with (root / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            clips.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in lanes])
    out = []
    for clip in sorted(clips):
        c = clips[clip]
        # P97's joined NE 8th clip is two hours; it is one continuous recording.
        out += [[row[j] for row in c] for j in range(len(lanes))]
    return out


def main() -> int:
    import numpy as np
    import sklearn
    from sklearn.linear_model import Ridge

    X, y, digests = [], [], {}
    for root in SOURCES:
        digests[str(root)] = hashlib.sha256((root / "counts.csv").read_bytes()).hexdigest()
        for v in lane_series(root):
            for s in range(0, len(v), STRIDE):
                e = s + T - 1
                if e + K >= len(v):
                    continue
                X.append(change_features(v, s))
                y.append(future_mean(v, e) - recent_mean(v, e))
    X, y = np.array(X), np.array(y)
    model = Ridge(alpha=1.0, fit_intercept=False).fit(X, y)

    # The two properties the design depends on, checked on a real series.
    v = lane_series(SOURCES[0])[0]
    base = float(np.dot(model.coef_, change_features(v, 300)))
    shifted = float(np.dot(model.coef_, change_features([c + 7 for c in v], 300)))
    scaled = float(np.dot(model.coef_, change_features([c * 3 for c in v], 300)))
    if abs(base - shifted) > 1e-9 or abs(scaled - 3 * base) > 1e-9:
        raise SystemExit("the model is not level-free — STOP")

    artifact = {
        "name": "P105 ridge v1 (change forecaster)", "protocol": "PREREGISTRATION_P105.md",
        "target": "next 60 s mean minus last 60 s mean, one lane",
        "features": list(NAMES), "model": "Ridge(alpha=1.0, fit_intercept=False), unstandardised",
        "coef": model.coef_.tolist(), "intercept": 0.0,
        "trained_on": {"lane_windows": int(len(y)), "sources_counts_sha256": digests},
        "sklearn": sklearn.__version__,
        "checks": {"shift_by_7_changes_prediction_by": abs(base - shifted),
                   "scale_by_3_error": abs(scaled - 3 * base)},
    }
    OUT.write_bytes((json.dumps(artifact, indent=2) + "\n").encode("utf-8"))
    print(f"  wrote {OUT}\n  sha256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")
    print(f"  {len(y)} lane-windows from {len(SOURCES)} cameras; level-free checks passed")
    print("  coefficients: " + ", ".join(f"{n} {c:+.4f}" for n, c in zip(NAMES, model.coef_)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
