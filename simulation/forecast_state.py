"""The forecast part of the policy's state, and the gate that decides who may use it.

ADR-020, as amended 2026-10-16 (P97a, Option D). Two jobs, kept in one module
so they cannot disagree:

**1. Encoding: the only route to state indices 11–14 and 16.**

- A class forecast maps to `forecast_class_value`: LOW, MEDIUM, HIGH → 1/3,
  2/3, 1.
- **0.0 is reserved** for "no forecast for this approach" and no class can
  produce it. The old layout gave LOW 0.0, so a missing forecast read as
  "clear".
- Index 16 is `min(age, cap) / cap`, and 1.0 when there is no forecast
  message at all.

**2. The gate: who decides.** A forecast-aware policy may act only when
**every** required input is valid. The checks run in this order:

1. **Counts and queues:** present for every approach, finite and
   non-negative. Otherwise **Webster** decides (FR-A06's existing fallback),
   because nothing can use invalid counts.
2. **The forecast message:** present, its age finite, non-negative and at
   most `max_age_s` (PRD §7.2, 10 s).
3. **Each required approach:** has a valid class in that message. Partial
   coverage is not enough.

If 2 or 3 fails, the **no-forecast policy** decides. It is trained on this
layout with no forecast, so it sees exactly what it learned on.

**Recovery is not special-cased, by design.** Every decision re-checks the
current inputs, so the forecast-aware policy resumes only on a complete, fresh,
valid message, never on partial or recovering data. Every change of decider
is logged with its reasons.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = ["APPROACHES", "forecast_slots", "GateResult", "ForecastGate"]

APPROACHES = ("N", "S", "E", "W")
FORECAST, NO_FORECAST, WEBSTER = "forecast", "no_forecast", "webster"


def _valid_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def forecast_slots(state_spec: dict, predictions: dict | None,
                   age_s: float | None) -> dict[int, float]:
    """`{index: value}` for indices 11–14 and 16. Never guesses a class.

    `predictions` maps approach → class name. `None` means no forecast
    message at all. An approach that is absent or carries an unknown class
    gets the reserved 0.0. A class value never stands in for absence.
    """
    index = state_spec["index_map"]
    values = state_spec["normalisers"]["forecast_class_value"]
    cap = float(state_spec["normalisers"]["forecast_age_cap_s"])
    off = state_spec["forecast_unavailable"]
    absent = float(off["absent_value"])
    if absent in values.values():
        raise ValueError("a class maps to the reserved absent value; the layout is ambiguous")
    slots = {i: absent for i in off["class_slots"]}
    if predictions is None:
        slots[off["age_slot"]] = float(off["age_value"])
        return slots
    if not _valid_number(age_s):
        raise ValueError(f"a forecast message needs a finite, non-negative age, got {age_s!r}")
    for approach in APPROACHES:
        cls = predictions.get(approach)
        if cls in values:
            slots[index[f"mfst_pred_{approach}"]] = float(values[cls])
    slots[off["age_slot"]] = min(float(age_s), cap) / cap
    return slots


@dataclass(frozen=True)
class GateResult:
    decider: str                 # "forecast", "no_forecast" or "webster"
    reasons: tuple[str, ...]


@dataclass
class ForecastGate:
    """Decides which policy may act on one observation. Holds only a log."""

    classes: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")
    required: tuple[str, ...] = APPROACHES
    max_age_s: float = 10.0
    mode: str | None = None
    log: list[tuple[str | None, str, tuple[str, ...]]] = field(default_factory=list)

    def check(self, observation: dict) -> GateResult:
        reasons: list[str] = []
        for key in ("counts", "queues"):
            values = observation.get(key) or {}
            for approach in APPROACHES:
                if approach not in values:
                    reasons.append(f"{key}: {approach} missing")
                elif not _valid_number(values[approach]):
                    reasons.append(f"{key}: {approach} invalid ({values[approach]!r})")
        if reasons:
            return self._record(WEBSTER, reasons)

        predictions = observation.get("forecast")
        age = observation.get("forecast_age_s")
        if predictions is None:
            reasons.append("no forecast message")
        else:
            if not _valid_number(age):
                reasons.append(f"forecast age invalid ({age!r})")
            elif age > self.max_age_s:
                reasons.append(f"forecast {age:.1f} s old, over {self.max_age_s:.0f} s")
            for approach in self.required:
                cls = predictions.get(approach)
                if cls is None:
                    reasons.append(f"no forecast for {approach}")
                elif cls not in self.classes:
                    reasons.append(f"forecast for {approach} invalid ({cls!r})")
        return self._record(NO_FORECAST if reasons else FORECAST,
                            reasons or ["every required input complete, fresh and valid"])

    def _record(self, decider: str, reasons: list[str]) -> GateResult:
        result = GateResult(decider, tuple(reasons))
        if decider != self.mode:
            self.log.append((self.mode, decider, result.reasons))
            self.mode = decider
        return result
