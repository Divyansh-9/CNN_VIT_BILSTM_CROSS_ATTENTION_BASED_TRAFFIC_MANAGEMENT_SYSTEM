"""ADR-017's p33/p67 calibration, against a zero-inflated distribution (P34).

The rule is `low_max = p33 - 1`, so that p33 itself falls in MEDIUM. That is
correct whenever p33 > 0 and wrong when it is not — and on real footage it is
not. An empty lane counts zero, and with four lanes per camera 41.2% of the
pilot corpus's per-lane counts are zero, which puts p33 at 0 and `low_max` at
-1. Nothing satisfies `count <= -1`, so the calibrated corpus came out **0%
LOW**: the exact degeneracy calibration exists to prevent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.labels import CongestionClass, label_from_count
from scripts.relabel_corpus import percentile


def calibrate(observed: list[int]) -> tuple[int, int]:
    """The boundaries `relabel_corpus --calibrate` derives, isolated."""
    low_max = max(0, percentile(observed, 33) - 1)
    med_max = percentile(observed, 67)
    if med_max <= low_max:
        med_max = low_max + 1
    return low_max, med_max


def shares(observed: list[int], low_max: int, med_max: int) -> dict[str, float]:
    labels = [label_from_count(v, low_max=low_max, med_max=med_max)
              for v in observed]
    return {c.name: labels.count(c) / len(labels) for c in CongestionClass}


def test_a_well_spread_distribution_is_split_near_thirds():
    """The case ADR-017 was written for, which still has to work."""
    observed = list(range(90))
    low_max, med_max = calibrate(observed)
    split = shares(observed, low_max, med_max)

    assert low_max > 0
    assert all(0.2 < share < 0.45 for share in split.values()), split


def test_a_zero_inflated_distribution_still_leaves_low_reachable():
    """The measured case: 41% zeros puts p33 at 0."""
    observed = [0] * 41 + list(range(1, 60))
    assert percentile(observed, 33) == 0

    low_max, med_max = calibrate(observed)
    assert low_max == 0, "LOW must mean an empty lane, not an impossible count"
    assert med_max > low_max

    split = shares(observed, low_max, med_max)
    assert split["LOW"] > 0, "the defect: LOW was 0% of every split"


def test_the_unclamped_rule_is_what_broke():
    """Pins the mechanism, so the clamp is not mistaken for arbitrary."""
    observed = [0] * 41 + list(range(1, 60))
    unclamped = percentile(observed, 33) - 1
    assert unclamped == -1
    assert all(label_from_count(v, low_max=unclamped, med_max=3) is not CongestionClass.LOW
               for v in observed), "no count can be <= -1"


def test_an_all_zero_distribution_does_not_produce_an_empty_medium():
    """p33 and p67 collide when the counts barely vary. Three usable classes
    matter more than honouring a percentile exactly."""
    low_max, med_max = calibrate([0] * 100)
    assert med_max > low_max


def test_a_constant_nonzero_distribution_also_survives():
    low_max, med_max = calibrate([7] * 100)
    assert med_max > low_max


def test_calibration_is_deterministic():
    """NFR-07. The boundaries must not depend on the order counts arrive in."""
    observed = [0] * 41 + list(range(1, 60))
    assert calibrate(observed) == calibrate(list(reversed(observed)))


@pytest.mark.parametrize("zeros", [0, 10, 33, 41, 60, 80])
def test_low_is_reachable_at_every_zero_share(zeros):
    observed = [0] * zeros + list(range(1, 101 - zeros))
    low_max, med_max = calibrate(observed)
    assert low_max >= 0
    assert med_max > low_max
    assert shares(observed, low_max, med_max)["LOW"] > 0


# ------------------------------------------------ per camera, not pooled (P37) --

def test_pooled_thresholds_do_not_describe_any_camera():
    """ADR-017 decision 2: 'A threshold in absolute units describes the view,
    not the road.' Measured on the pilot, the per-camera p67 runs from 1 to 19
    while the pooled p67 is 3 — so pooled thresholds mark nearly everything
    HIGH on a busy camera and LOW on a quiet one.
    """
    quiet = [0] * 60 + [1] * 40            # a near-empty motorway lane
    busy = list(range(10, 30)) * 5         # a saturated junction approach

    quiet_bounds = calibrate(quiet)
    busy_bounds = calibrate(busy)
    pooled_bounds = calibrate(quiet + busy)

    assert quiet_bounds != busy_bounds
    assert pooled_bounds != quiet_bounds

    # Under the pooled thresholds the busy camera never sees LOW at all: its
    # quietest moment is already above the pooled boundary.
    pooled_on_busy = shares(busy, *pooled_bounds)
    assert pooled_on_busy["LOW"] == 0, pooled_on_busy

    # And the quiet camera never sees HIGH.
    pooled_on_quiet = shares(quiet, *pooled_bounds)
    assert pooled_on_quiet["HIGH"] == 0, pooled_on_quiet


def test_per_camera_calibration_cannot_invent_a_class_that_never_occurs():
    """The honest limit of per-camera thresholds, and the argument against
    them.

    A lane that only ever holds zero or one vehicle has no congested state, and
    calibration must not manufacture one — two vehicles on a free-flowing
    motorway is not HIGH however rare it is for that camera. So per-camera
    calibration buys balance where the range supports it and stays silent where
    it does not, which is the right failure but means a camera can contribute
    no HIGH examples at all.
    """
    quiet = [0] * 60 + [1] * 40
    split = shares(quiet, *calibrate(quiet))

    assert split["LOW"] > 0 and split["MEDIUM"] > 0
    assert split["HIGH"] == 0, "a camera with no congestion must not report any"


def test_per_camera_calibration_spreads_the_classes_where_the_range_allows():
    busy = list(range(10, 30)) * 5
    split = shares(busy, *calibrate(busy))
    assert all(share > 0.2 for share in split.values()), split


def test_relabel_records_which_scope_it_used():
    """A corpus whose manifest does not say whether its thresholds are pooled
    or per-camera cannot be compared with another."""
    source = (Path(__file__).resolve().parent.parent
              / "scripts" / "relabel_corpus.py").read_text(encoding="utf-8")
    assert '"threshold_scope"' in source
    assert '"thresholds_by_clip"' in source


def test_calibrate_and_calibrate_global_are_exclusive():
    source = (Path(__file__).resolve().parent.parent
              / "scripts" / "relabel_corpus.py").read_text(encoding="utf-8")
    assert "choose one of --calibrate and --calibrate-global" in source
