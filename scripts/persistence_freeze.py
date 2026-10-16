"""Freeze persistence v1 for the prototype: method, thresholds, measured performance.

    python scripts/persistence_freeze.py

Writes `experiments/results/bellevue_pilot/persistence_v1.json` (LF, hashed).
Its SHA-256 is the persistence model id `edge/persistence.py` publishes.

- **Thresholds, full precision.**
  - The three P103 cameras: recomputed from their Sunday 18:08 calibration
    hours by `edge.persistence.calibrate`. They must equal P103's own
    full-precision calibration, or the script stops.
  - NE 8th: the absolute 2 / 8 that P94–P101 used and P99b validated for LOW.
- **Confidence:** persistence's precision per predicted class, from P103's
  committed confusion matrix (calibrated, pooled over the new cameras).
- **Measured performance, as recorded:**
  - P103: pooled macro-F1 0.7056 on new cameras;
  - P100: 0.5397 on NE 8th's unseen hours.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
OUT = ROOT / "persistence_v1.json"


def main() -> int:
    from edge.persistence import calibrate
    from scripts import p103_eval as ev

    results = json.loads((ROOT / "p103_results.json").read_text(encoding="utf-8"))
    cameras = {}
    for camera in ev.CAMERAS:
        rows = ev.windows(camera)
        means = [m for w in rows if w["role"] == "calibration" for m in w["future"]]
        low, med = calibrate(means)
        if (low, med) != ev.calibrate(rows):
            raise SystemExit(f"{camera}: edge calibration differs from P103's — STOP")
        cameras[camera] = {"low": low, "med": med, "source": "P103 calibration hour, "
                           "Sun 2017-09-10 18:08 (q33/q67 of 60 s means, ADR-017)",
                           "lanes": len(rows[0]["future"])}
    cameras["NE8th"] = {"low": 2.0, "med": 8.0, "lanes": 3,
                        "source": "absolute 2/8 used by P94-P101; LOW validated by P99b"}

    confusion = results["calibrated"]["confusion"]["persistence"]
    classes = ["LOW", "MEDIUM", "HIGH"]
    precision = {c: confusion[i][i] / sum(row[i] for row in confusion)
                 for i, c in enumerate(classes)}
    spec = {
        "name": "persistence v1",
        "method": ("forecast for the next 60 s = class of the mean of each lane's last 30 "
                   "counts (2 s step); LOW if mean <= low, MEDIUM if <= med, else HIGH"),
        "decision": "project owner, after P103: the prototype's transferable forecaster",
        "cameras": cameras,
        "confidence_is_measured_precision": precision,
        "confidence_source": "P103 calibrated pooled confusion, persistence column precision",
        "measured": {
            "P103 new cameras, calibrated, pooled": {
                "macro_f1": results["calibrated"]["pooled"]["persistence"]["f1"],
                "recall": {c: results["calibrated"]["pooled"]["persistence"][c] for c in classes},
                "vs C1-L": results["primary"]["C1-L - persistence"]},
            "P100 NE 8th unseen hours": {"macro_f1": 0.5397,
                                        "recall": {"LOW": 0.5091, "MEDIUM": 0.7297, "HIGH": 0.3892}},
        },
        "not_established": ("that any signal-control policy using these forecasts is safe "
                            "or beneficial; persistence is not fed to the PPO state (P97a)"),
    }
    OUT.write_bytes((json.dumps(spec, indent=2) + "\n").encode("utf-8"))
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"  wrote {OUT}\n  sha256 {digest}\n  model id persistence@{digest[:12]}")
    for camera, entry in cameras.items():
        print(f"  {camera:<16} low {entry['low']!r}  med {entry['med']!r}")
    print("  confidence (measured precision): " +
          ", ".join(f"{c} {p:.4f}" for c, p in precision.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
