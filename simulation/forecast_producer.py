"""What fills state indices 11-14 and 16 during training (P52, ADR-021 A1.3-A1.4).

The environment asks its producer for a forecast message at every decision,
and encodes the answer through `forecast_slots`, the only route into those
indices. Nothing else in the 17-dim state depends on the producer. A test
holds the arms to that: two arms' observations differ only at 11-14 and 16.

- `NoForecast`: no message. Slots read absent (0.0) and the age reads 1.0.
  This is the `no-forecast` arm, and exactly what the environment did before.
- `Surrogate(q)`: a message whose class per approach is the replay oracle's
  while a shared, persistent "informed" chain holds, and the persistence class
  otherwise (P115 §3). q = 0 is persistence, the control arm; q = 1 is the
  oracle, an upper bound.

**The message ages honestly.** A message is made at one decision and carried
until it would be older than `max_age_s` (10 s, the gate's bound). At the 5 s
decisions the policy therefore sees ages 0, 5 and 10 s, each with content made
that long ago. An episode's last hold can be cut short, so about 1% of
observations, all at episode ends, carry an age in between. Those ages are
real and within the bound. The chain advances only when a message is made, by the time
since the last one.

**A surrogate never returns "no message".** If the oracle cannot answer, it
raises. A surrogate that silently produced no-forecast observations is exactly
the P52 defect.
"""

from __future__ import annotations

import math

import numpy as np

from simulation.forecast_quality import corruption_rng
from simulation.oracle import HORIZON_S

__all__ = ["NoForecast", "Surrogate", "CLASSES"]

APPROACHES = ("N", "S", "E", "W")
CLASSES = ("LOW", "MEDIUM", "HIGH")


class NoForecast:
    name = "none"

    def reset(self, seed: int) -> None:
        pass

    def message(self, t: int, counts: dict) -> tuple[None, None]:
        return None, None

    def describe(self) -> dict:
        return {"producer": "none"}


class Surrogate:
    def __init__(self, q: float, oracle, *, low_max: int, med_max: int,
                 max_age_s: float = 10.0, tau_s: float = 60.0) -> None:
        if not 0.0 <= float(q) <= 1.0:
            raise ValueError(f"quality q must lie in [0, 1], got {q}")
        self.q, self.oracle = float(q), oracle
        self.low_max, self.med_max = int(low_max), int(med_max)
        self.max_age_s, self.tau_s = float(max_age_s), float(tau_s)
        self.name = f"surrogate(q={self.q:g})"
        self.stats = {"messages": 0, "decisions": 0, "informed_messages": 0, "ages": {}}
        self._series = None

    def _class(self, n) -> str:
        n = int(n)
        return CLASSES[0 if n <= self.low_max else (1 if n <= self.med_max else 2)]

    def reset(self, seed: int) -> None:
        self.seed = int(seed)
        self._series = self.oracle.counts(self.seed)
        self._rng = corruption_rng(self.seed, self.q)
        self._informed = None
        self._t_msg = None
        self._msg = None

    def message(self, t: int, counts: dict) -> tuple[dict, float]:
        if self._series is None:
            raise RuntimeError("Surrogate.message() before reset(): no oracle loaded")
        t = int(t)
        if self._t_msg is None or t - self._t_msg > self.max_age_s:
            self._refresh(t, counts)
        age = float(t - self._t_msg)
        self.stats["decisions"] += 1
        self.stats["ages"][age] = self.stats["ages"].get(age, 0) + 1
        return dict(self._msg), age

    def _refresh(self, t: int, counts: dict) -> None:
        ahead = t + HORIZON_S
        if ahead >= len(self._series):
            raise RuntimeError(f"the oracle for seed {self.seed} ends at "
                               f"{len(self._series) - 1} s and cannot answer t = {t} s")
        if self._informed is None:
            self._informed = bool(self._rng.random() < self.q)
        elif self._rng.random() >= math.exp(-(t - self._t_msg) / self.tau_s):
            self._informed = bool(self._rng.random() < self.q)
        if self._informed:
            row = self._series[ahead]
            self._msg = {a: self._class(row[k]) for k, a in enumerate(APPROACHES)}
            self.stats["informed_messages"] += 1
        else:
            self._msg = {a: self._class(counts[a]) for a in APPROACHES}
        self._t_msg = t
        self.stats["messages"] += 1

    def describe(self) -> dict:
        return {"producer": "surrogate", "q": self.q, "max_age_s": self.max_age_s,
                "tau_s": self.tau_s, "corruption_rng": "default_rng([seed, round(1000 q), 52])",
                "thresholds": {"low_max": self.low_max, "med_max": self.med_max},
                **self.oracle.describe()}
