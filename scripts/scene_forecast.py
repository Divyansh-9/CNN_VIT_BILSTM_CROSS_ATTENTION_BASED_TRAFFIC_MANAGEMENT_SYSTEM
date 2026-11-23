"""A trailing-mean baseline for visible vehicles in uncalibrated footage."""

from collections import deque
from math import ceil
from statistics import fmean

HORIZONS = (30, 60, 300, 600)
METHOD = "trailing-mean-v1"
STEP_S = 2


class Horizon:
    def __init__(self, seconds):
        self.samples = seconds // STEP_S
        self.window = deque(maxlen=self.samples)
        self.previous = None
        self.errors = deque(maxlen=24)
        self.elapsed = 0
        # Require repeatable within-video observations before longer estimates.
        self.minimum_checks = 3 if seconds >= 300 else 0

    def observe(self, count):
        self.window.append(count)
        self.elapsed += 1
        if len(self.window) != self.samples:
            return None
        estimate = fmean(self.window)
        if self.elapsed % self.samples == 0:
            if self.previous is not None:
                self.errors.append(abs(estimate - self.previous))
            self.previous = estimate
        n = len(self.errors)
        if n < self.minimum_checks:
            return None
        error = sorted(self.errors)[ceil(.9 * n) - 1] if n >= 5 else None
        return {
            "mean": round(estimate, 3),
            "checks": n,
            "mae": round(fmean(self.errors), 3) if n else None,
            "range": [round(max(0., estimate - error), 3), round(estimate + error, 3)] if error is not None else None,
        }


class SceneForecast:
    def __init__(self):
        self.last = None
        self.horizons = {seconds: Horizon(seconds) for seconds in HORIZONS}

    def observe(self, timestamp, count):
        if self.last is not None and timestamp != self.last + STEP_S:
            # A gap is missing evidence. Never impute zero traffic.
            self.horizons = {seconds: Horizon(seconds) for seconds in HORIZONS}
        self.last = timestamp
        output = {}
        for seconds, horizon in self.horizons.items():
            result = horizon.observe(count)
            if result is not None:
                output[str(seconds)] = result
        return output
