"""Indo-HCM passenger car units — road space occupied, not vehicles present.

**Status: implemented, NOT the default.** ADR-017 is proposed and changes a
graded specification (PRD §14.1), so nothing switches to it before the guide
signs off. This module exists so the decision can be argued from measurements
rather than from a description of measurements.

A vehicle count treats a motorcycle and a bus as the same unit. On the measured
Dhaka footage the fleet is **44.9% motorcycles and 6.9% buses**, and a bus
occupies roughly fifteen times the road space of a motorcycle. "Fifteen
vehicles" therefore describes anything between a nearly empty road and a
blocked one.

The Indian Highway Capacity Manual exists to solve exactly this. It defines
passenger car unit equivalences so heterogeneous traffic can be expressed in one
number, and it is the standard the ITD dataset (IIT Roorkee, 2024) annotates
against.

**The second reason is less obvious and mattered more in practice.** A raw count
over 242 samples took **24 distinct values**; PCU took **139**. Counts cluster
so heavily that 22% of samples sat exactly on the two calibration thresholds,
where an integer cut-off cannot separate them — calibrating raw counts to
balanced thirds produced 24/52/24 rather than the intended 33/33/33. PCU is
effectively continuous and lands where it is aimed: 34/34/31.

Values are Indo-HCM 2017, intermediate/two-lane urban roads. Where a class has
no Indo-HCM entry the assumption is stated in `ASSUMED` rather than buried, and
`unmapped()` reports anything the caller has not decided about.
"""

from __future__ import annotations

from typing import Mapping

__all__ = ["PCU", "ASSUMED", "NON_VEHICLE", "pcu_of", "pcu_total", "unmapped"]

# Indo-HCM 2017, intermediate/two-lane urban. Standard car is the unit.
PCU: dict[str, float] = {
    "car": 1.00,
    "motorcycle": 0.30,
    "auto_rickshaw": 1.20,
    "bus": 4.50,
    "truck": 5.00,
    "bicycle": 0.20,
}

# Classes Indo-HCM does not tabulate. Recorded as assumptions, with the
# reasoning, because an invented constant that looks like a standard value is
# worse than an obvious guess.
ASSUMED: dict[str, tuple[float, str]] = {
    "e_rickshaw": (
        1.20,
        "same footprint as an auto-rickshaw. Indo-HCM 2017 predates their "
        "spread, so no entry exists. Slower, which arguably warrants more; "
        "held equal until measured.",
    ),
    "cattle": (
        1.50,
        "between a car and an auto-rickshaw by footprint. Indo-HCM tabulates "
        "animal-drawn carts, not loose animals, and the two are not the same "
        "obstruction. Low-confidence; cattle were 0% of the measured fleet.",
    ),
}

# Present in the frame, not occupying carriageway capacity as a vehicle.
NON_VEHICLE = frozenset({"pedestrian"})


def pcu_of(class_name: str) -> float:
    """PCU for one vehicle class. Raises on anything undecided.

    Deliberately strict. A silent default of 1.0 would let a new detector class
    enter the corpus weighted as a car and change every label with nothing in
    the logs — the failure mode P17 and P19 both took, where a value nobody
    chose became a value everybody relied on.
    """
    if class_name in NON_VEHICLE:
        return 0.0
    if class_name in PCU:
        return PCU[class_name]
    if class_name in ASSUMED:
        return ASSUMED[class_name][0]
    raise KeyError(
        f"no PCU for {class_name!r}. Add it to PCU with an Indo-HCM citation, "
        f"or to ASSUMED with the reasoning. Do not let it default."
    )


def pcu_total(counts: Mapping[str, int]) -> float:
    """PCU-weighted occupancy for one frame's per-class counts."""
    return sum(pcu_of(name) * number for name, number in counts.items())


def unmapped(class_names) -> list[str]:
    """Classes with no PCU decision — check this before building a corpus."""
    return sorted(name for name in class_names
                  if name not in PCU and name not in ASSUMED
                  and name not in NON_VEHICLE)
