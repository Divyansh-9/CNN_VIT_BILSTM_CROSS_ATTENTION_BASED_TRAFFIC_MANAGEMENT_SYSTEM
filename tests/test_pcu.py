"""Indo-HCM PCU weighting (ADR-017, proposed).

These pin the two things that make PCU worth proposing and the one thing that
makes it dangerous: an unmapped class must never quietly weigh 1.0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.pcu import (
    ASSUMED,
    NON_VEHICLE,
    PCU,
    pcu_of,
    pcu_total,
    unmapped,
)

DETECTOR_CLASSES = ("car", "motorcycle", "auto_rickshaw", "e_rickshaw",
                    "bus", "truck", "pedestrian", "cattle")


def test_every_detector_class_has_a_decision():
    """The corpus cannot be built until each class is either tabulated,
    explicitly assumed, or declared a non-vehicle."""
    assert unmapped(DETECTOR_CLASSES) == []


def test_an_unknown_class_raises_rather_than_defaulting():
    """The defect this guards is the shape of P17 and P19: a value nobody chose
    becoming a value everybody relies on. A new detector class must stop the
    corpus, not silently enter it weighted as a car."""
    with pytest.raises(KeyError, match="no PCU"):
        pcu_of("tractor")


def test_pedestrians_occupy_no_carriageway_capacity():
    assert pcu_of("pedestrian") == 0.0
    assert pcu_total({"car": 2, "pedestrian": 9}) == pytest.approx(2.0)


def test_indo_hcm_values_are_the_published_ones():
    """Indo-HCM 2017, intermediate/two-lane urban. If one of these drifts, every
    label built on it drifts with it."""
    assert PCU["car"] == 1.00
    assert PCU["motorcycle"] == 0.30
    assert PCU["auto_rickshaw"] == 1.20
    assert PCU["bus"] == 4.50
    assert PCU["truck"] == 5.00


def test_assumed_values_carry_their_reasoning():
    """An assumption without a stated reason is indistinguishable from a
    standard value once it is in the code."""
    for name, (value, why) in ASSUMED.items():
        assert value > 0, name
        assert len(why) > 40, f"{name} has no real justification"


def test_a_bus_outweighs_fifteen_motorcycles():
    """The whole argument in one assertion. Raw counting calls this 15 vs 1."""
    assert pcu_total({"motorcycle": 15}) == pytest.approx(4.5)
    assert pcu_total({"bus": 1}) == pytest.approx(4.5)


def test_the_measured_dhaka_fleet_mix():
    """Measured over 242 samples: 44.9% motorcycle, 24.6% car, 21.5%
    auto-rickshaw, 6.9% bus, 2.2% truck.

    **This is the result that keeps the claim honest.** In aggregate the mix
    weighs 1.06 PCU per vehicle — the many cheap motorcycles very nearly cancel
    the few expensive buses. So PCU does NOT systematically rescale this
    camera's counts, and anyone arguing for it on "raw counts overstate
    congestion" grounds is arguing past the data.

    The real benefit is resolution: raw counts took 24 distinct values over
    these samples, PCU took 139. That is what lets calibrated thresholds land
    where they are aimed. Per-frame the mix still varies, which is where the
    two series come apart.
    """
    fleet = {"motorcycle": 1421, "car": 777, "auto_rickshaw": 679,
             "bus": 218, "truck": 69}
    total_vehicles = sum(fleet.values())
    total_pcu = pcu_total(fleet)

    assert total_vehicles == 3164
    assert total_pcu == pytest.approx(3344.1, abs=0.1)
    assert 1.05 < total_pcu / total_vehicles < 1.07


def test_non_vehicle_classes_are_not_in_the_pcu_table():
    """A class cannot be both weighted and excluded."""
    assert not (NON_VEHICLE & set(PCU))
    assert not (NON_VEHICLE & set(ASSUMED))


def test_empty_frame_is_zero():
    assert pcu_total({}) == 0.0
