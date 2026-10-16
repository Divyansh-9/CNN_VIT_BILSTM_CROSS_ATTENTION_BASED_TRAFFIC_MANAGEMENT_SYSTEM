"""Ridge on the edge: counts in, a `CountForecast` out (ADR-027, P105).

P105 measured the frozen, level-free ridge model on untouched cameras and
hours. It forecast the next minute's mean count with an MAE of 0.748 vehicles,
against persistence's 0.972 (+0.224 [+0.181, +0.271]). Its congestion classes
were not significantly better, so the project owner gave it **one role only**:
the next-minute count. The congestion class stays with persistence
(`edge.persistence`), and nothing here feeds signal timing.

**Exactly as P105 scored it:**

- Δ̂ is the ridge coefficients times five difference features of the lane's
  last 60 samples (2 min);
- the forecast count is `max(0, mean of the last 30 + Δ̂)`;
- there is no intercept and no standardisation, so the model cannot carry one
  camera's level into another (P103).

**Only the frozen spec is served.** The spec's SHA-256 must equal the one
recorded when it was frozen (`p105_ridge_v1.json`), and the model id is
`ridge@<first 12 hex>`. A forecast that is non-finite or out of range is
refused rather than published.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from contracts.mqtt import MAX_LANE_COUNT, CountForecast
from edge.samples import SampleBuffer

__all__ = ["RIDGE_V1_SHA256", "RidgeCountForecaster", "change_features"]

RIDGE_V1_SHA256 = "73532968dcf24b2533089687530ca435d2f09bc8cebcb159b44d97dd55c7c74c"
APPROACHES = ("N", "S", "E", "W")
T, RECENT = 60, 30


def change_features(w: list[float]) -> list[float]:
    """P105's five differences over one lane's last 60 samples."""
    m60, m30 = statistics.fmean(w), statistics.fmean(w[-30:])
    m15, m5 = statistics.fmean(w[-15:]), statistics.fmean(w[-5:])
    x_mean = (T - 1) / 2
    slope = (sum((x - x_mean) * (y - m60) for x, y in enumerate(w))
             / sum((x - x_mean) ** 2 for x in range(T)))
    return [m30 - m60, m15 - m30, m5 - m15, w[-1] - m30, slope]


class RidgeCountForecaster:
    """One camera's next-minute count forecaster. `step(counts, ts)` per 2 s sample."""

    def __init__(self, spec_path: Path, lane_to_approach: dict[str, str], *,
                 expected_sha256: str = RIDGE_V1_SHA256) -> None:
        raw = Path(spec_path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ValueError(f"{spec_path} hashes to {digest[:12]}, not the frozen "
                             f"{expected_sha256[:12]}; only the P105 spec is served")
        spec = json.loads(raw)
        if spec.get("intercept", 0.0) != 0.0 or len(spec["coef"]) != 5:
            raise ValueError(f"{spec_path} is not a level-free 5-feature ridge spec")
        bad = set(lane_to_approach.values()) - set(APPROACHES)
        if bad or len(set(lane_to_approach.values())) != len(lane_to_approach):
            raise ValueError(f"lane_to_approach must map lanes to distinct members of "
                             f"{APPROACHES}; got {lane_to_approach}")
        self.coef = [float(c) for c in spec["coef"]]
        self.model_id = "ridge@" + digest[:12]
        self.lane_to_approach = dict(lane_to_approach)
        self.buffer = SampleBuffer(lane_to_approach, T)

    @property
    def ready(self) -> bool:
        return self.buffer.ready

    def forecast(self, series: list[int]) -> float:
        delta = sum(c * f for c, f in zip(self.coef, change_features(series)))
        value = max(0.0, statistics.fmean(series[-RECENT:]) + delta)
        if not math.isfinite(value) or value > MAX_LANE_COUNT:
            raise ValueError(f"forecast {value!r} is outside [0, {MAX_LANE_COUNT:.0f}]; refused")
        return value

    def predict(self) -> CountForecast:
        if not self.ready:
            raise ValueError("the 2-minute window is not full; no forecast is made from less")
        return CountForecast(
            counts={self.lane_to_approach[lane]: round(self.forecast(self.buffer.series(lane)), 4)
                    for lane in self.lane_to_approach},
            model=self.model_id)

    def step(self, counts: dict[str, int], ts: float | None = None) -> CountForecast | None:
        """Add one sample; forecast once 60 contiguous samples are buffered."""
        self.buffer.push(counts, ts)
        return self.predict() if self.ready else None
