"""Vehicle-class resolution must not depend on whose taxonomy wrote it (P24).

`vehicle_ids` used a fixed inclusion list of OUR class names. Against ITD-x it
matched `bus`, `car` and `truck` and silently ignored `two wheeler`,
`autorickshaw` and `LCV` — on Indian footage, most of the traffic. Every ITD
count in the corpus builder and the lane survey was over a third of the vehicles,
and it voided a published conclusion before anyone noticed.

The same defect had been found and fixed in `pilot_counts.py` earlier the same
day and not fixed here. These tests exist so the third occurrence is a red test
rather than a wrong number.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pilot_a17 import NON_VEHICLE_NAMES, vehicle_ids


class FakeModel:
    """Just the `names` mapping — vehicle_ids reads nothing else."""

    def __init__(self, names):
        self.names = dict(enumerate(names))


def resolved(names):
    model = FakeModel(names)
    return sorted(model.names[i] for i in vehicle_ids(model))


def test_our_taxonomy_resolves_to_the_six_vehicle_classes():
    ours = ["car", "motorcycle", "auto_rickshaw", "e_rickshaw",
            "bus", "truck", "pedestrian", "cattle"]
    assert resolved(ours) == ["auto_rickshaw", "bus", "car", "e_rickshaw",
                              "motorcycle", "truck"]


def test_itd_taxonomy_keeps_two_wheelers_and_autorickshaws():
    """The measured defect. An inclusion list returned 3 of these 7."""
    itd = ["two wheeler", "autorickshaw", "car", "bus", "LCV", "truck",
           "bicycle", "pedestrain"]
    got = resolved(itd)
    assert "two wheeler" in got
    assert "autorickshaw" in got
    assert "LCV" in got
    assert len(got) == 7, f"expected all 7 non-pedestrian classes, got {got}"


def test_coco_taxonomy_resolves_without_being_listed_anywhere():
    """A taxonomy nobody wrote a rule for still resolves sensibly."""
    coco = ["person", "bicycle", "car", "motorcycle", "bus", "truck",
            "traffic light", "stop sign", "bench", "dog"]
    got = resolved(coco)
    assert "person" not in got and "traffic light" not in got
    assert {"car", "motorcycle", "bus", "truck", "bicycle"} <= set(got)


def test_pedestrians_cattle_and_riders_are_never_counted():
    """§14.1 counts vehicles. A crowded footpath is not congestion, a cow is an
    obstacle, and a rider is already counted as the motorcycle (S09)."""
    names = ["car", "pedestrian", "pedestrain", "person", "cattle", "rider"]
    assert resolved(names) == ["car"]


def test_a_model_of_only_non_vehicles_is_refused():
    """Counting nothing would report every frame as LOW, which looks like data
    rather than like a misconfiguration."""
    with pytest.raises(SystemExit, match="non-vehicle"):
        vehicle_ids(FakeModel(["person", "traffic light"]))


def test_the_exclusion_set_covers_both_spellings_of_pedestrian():
    """ITD spells it `pedestrain`. A typo in someone else's dataset must not
    become a vehicle in ours."""
    assert "pedestrian" in NON_VEHICLE_NAMES
    assert "pedestrain" in NON_VEHICLE_NAMES
