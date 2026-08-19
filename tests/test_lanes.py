"""Nearest-centre lane assignment (mfstnet/corpus/lanes.py).

The property that matters is the one polygons could not give: **every detection
lands in at most one lane, always, with no geometry to edit.** Eleven of twelve
surveyed cameras produced overlapping polygon boxes; none can overlap here,
because overlap is not representable.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.lanes import LaneCentres, assign_to_lane

TWO = LaneCentres(names=("left", "right"), centres=((0.25, 0.5), (0.75, 0.5)))


def test_a_point_goes_to_its_nearer_centre():
    assert assign_to_lane((0.20, 0.5), TWO) == "left"
    assert assign_to_lane((0.80, 0.5), TWO) == "right"


def test_assignment_is_disjoint_by_construction():
    """The whole reason this module exists. No point can belong to two lanes,
    so there is no overlap check to run and none to fail."""
    rng = random.Random(42)
    for _ in range(5000):
        point = (rng.random(), rng.random())
        result = assign_to_lane(point, TWO)
        assert result in ("left", "right", None)


def test_far_points_are_unassigned_not_snapped():
    """Unbounded nearest-centre would put a vehicle on the far pavement into a
    lane. The unassigned rate is the diagnostic P17 made it, so it must be able
    to be non-zero."""
    tight = LaneCentres(names=("a",), centres=((0.5, 0.5),), max_radius=0.10)
    assert assign_to_lane((0.5, 0.55), tight) == "a"
    assert assign_to_lane((0.5, 0.95), tight) is None


def test_the_boundary_is_inclusive():
    tight = LaneCentres(names=("a",), centres=((0.5, 0.5),), max_radius=0.10)
    assert assign_to_lane((0.5, 0.60), tight) == "a"       # exactly 0.10
    assert assign_to_lane((0.5, 0.601), tight) is None


def test_ties_resolve_deterministically():
    """Equidistant points must not depend on iteration order — that is the
    silent order dependency P17 found in polygon containment."""
    midpoint = (0.5, 0.5)
    first = assign_to_lane(midpoint, TWO)
    flipped = LaneCentres(names=("right", "left"),
                          centres=((0.75, 0.5), (0.25, 0.5)))
    assert first == "left"
    assert assign_to_lane(midpoint, flipped) == "right"    # earlier name wins


def test_centres_outside_the_frame_are_refused():
    """Normalised coordinates, not pixels. Passing 960 instead of 0.5 is the
    obvious mistake and it must not silently produce a lane nothing reaches."""
    with pytest.raises(ValueError, match="outside the frame"):
        LaneCentres(names=("a",), centres=((960.0, 540.0),))


def test_duplicate_and_mismatched_names_are_refused():
    with pytest.raises(ValueError, match="duplicate"):
        LaneCentres(names=("a", "a"), centres=((0.2, 0.5), (0.8, 0.5)))
    with pytest.raises(ValueError, match="name"):
        LaneCentres(names=("a",), centres=((0.2, 0.5), (0.8, 0.5)))


def test_four_approaches_partition_the_frame():
    """A junction, the shape the PRD actually specifies. Every sampled point is
    assigned to exactly one approach or to none."""
    junction = LaneCentres(
        names=("north", "south", "east", "west"),
        centres=((0.5, 0.2), (0.5, 0.8), (0.8, 0.5), (0.2, 0.5)),
        max_radius=0.9,
    )
    rng = random.Random(7)
    seen = set()
    for _ in range(2000):
        seen.add(assign_to_lane((rng.random(), rng.random()), junction))
    assert seen == {"north", "south", "east", "west"}
