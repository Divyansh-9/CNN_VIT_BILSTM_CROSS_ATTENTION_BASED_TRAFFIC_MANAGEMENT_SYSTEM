"""Persistence on the edge: counts in, a `CongestionPrediction` out (P103/P104).

P103 measured persistence as the best transferable forecaster on new cameras:
macro-F1 0.706 against 0.483 for the NE 8th count model, which carried NE 8th's
traffic level into cameras where it did not hold. The project owner adopted it
for the prototype's forecasting path. MFSTNet's edge path (`forecaster.py`)
is unchanged and still available.

**The method, exactly as P94–P103 scored it.** The forecast for the next 60 s
is the class of the mean of each lane's last 30 counts (2 s apart), classed
with that camera's thresholds: LOW if mean ≤ low, MEDIUM if mean ≤ med,
otherwise HIGH. Nothing is learned, so there is no level to carry from one
camera to another. Only the thresholds are per camera.

**Thresholds come from a frozen spec, at full precision.** A camera's
thresholds are either calibrated from its own calibration period
(`calibrate`, ADR-017: q33/q67 of the 60 s means) or a validated absolute pair.
They are never rounded: means are multiples of 1/30 and sit exactly on these
boundaries, and P103 found 21 decisions moved by a four-decimal rounding.

**Confidence is measured, not invented.** The contract requires one per lane.
Persistence has no probability, so it reports P103's measured precision for
the class it predicts: how often that call was right on new cameras.

**The model id names the spec**, `persistence@<first 12 hex of its SHA-256>`,
so a forecast says which frozen thresholds produced it.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path

from contracts.mqtt import CongestionClass, CongestionPrediction

__all__ = ["PersistenceForecaster", "calibrate", "classify", "load_spec"]

CLASSES = (CongestionClass.LOW, CongestionClass.MEDIUM, CongestionClass.HIGH)
APPROACHES = ("N", "S", "E", "W")
WINDOW = 30                      # samples: 60 s at the 2 s step (P94)


def classify(mean: float, low: float, med: float) -> CongestionClass:
    return CLASSES[0 if mean <= low else (1 if mean <= med else 2)]


def calibrate(future_means: list[float]) -> tuple[float, float]:
    """ADR-017 on a calibration period: q33 and q67 of its 60 s means, linear
    interpolation, full precision. The calibration period must be disjoint from
    anything the thresholds are later scored on."""
    import numpy as np

    if not future_means:
        raise ValueError("a calibration period with no 60 s means cannot set thresholds")
    q33, q67 = np.percentile(future_means, [33, 67])
    return float(q33), float(q67)


def load_spec(path: Path) -> tuple[dict, str]:
    """The frozen spec and its model id."""
    raw = Path(path).read_bytes()
    return json.loads(raw), "persistence@" + hashlib.sha256(raw).hexdigest()[:12]


class PersistenceForecaster:
    """One camera's persistence forecaster. `step(counts)` once per 2 s sample."""

    def __init__(self, spec_path: Path, camera: str,
                 lane_to_approach: dict[str, str]) -> None:
        spec, self.model_id = load_spec(spec_path)
        if camera not in spec["cameras"]:
            raise ValueError(f"{camera} has no thresholds in {spec_path}; calibrate it "
                             f"on its own calibration period first (ADR-017)")
        entry = spec["cameras"][camera]
        self.low, self.med = float(entry["low"]), float(entry["med"])
        if not self.low < self.med:
            raise ValueError(f"{camera}: thresholds {self.low}, {self.med} are not increasing")
        bad = set(lane_to_approach.values()) - set(APPROACHES)
        if bad or len(set(lane_to_approach.values())) != len(lane_to_approach):
            raise ValueError(f"lane_to_approach must map lanes to distinct members of "
                             f"{APPROACHES}; got {lane_to_approach}")
        self.camera, self.lane_to_approach = camera, dict(lane_to_approach)
        self.precision = {CongestionClass[k]: float(v)
                          for k, v in spec["confidence_is_measured_precision"].items()}
        self.rings = {lane: deque(maxlen=WINDOW) for lane in lane_to_approach}

    @property
    def ready(self) -> bool:
        return all(len(r) == WINDOW for r in self.rings.values())

    def push(self, counts: dict[str, int]) -> None:
        if set(counts) != set(self.rings):
            raise ValueError(f"counts for {sorted(counts)}, lanes are {sorted(self.rings)}")
        for lane, count in counts.items():
            if count < 0:
                raise ValueError(f"{lane}: negative count {count}")
            self.rings[lane].append(int(count))

    def predict(self) -> CongestionPrediction:
        if not self.ready:
            raise ValueError(f"{min(len(r) for r in self.rings.values())} of {WINDOW} "
                             f"samples buffered; a shorter mean is not the scored method")
        predictions, confidences = {}, {}
        for lane, ring in self.rings.items():
            cls = classify(sum(ring) / WINDOW, self.low, self.med)
            approach = self.lane_to_approach[lane]
            predictions[approach] = cls
            confidences[approach] = self.precision[cls]
        return CongestionPrediction(predictions=predictions, confidences=confidences,
                                    gate_value=None, model=self.model_id)

    def step(self, counts: dict[str, int]) -> CongestionPrediction | None:
        """Add one sample of per-lane counts; forecast once 30 are buffered."""
        self.push(counts)
        return self.predict() if self.ready else None
