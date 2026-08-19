"""Camera identity — the thing a camera-split corpus depends on being right.

Both defects pinned here were found by looking at a contact sheet, not by a
test, and both would have leaked silently into a split.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.identity import (
    assert_no_camera_leak,
    distinct_cameras,
    group_cameras,
    similarity,
    stable_stem,
)


def sig(*values: float) -> list[float]:
    return list(values)


def test_stable_stem_cannot_collide_on_a_shared_prefix():
    """The measured bug: two clips differing only after 48 characters produced
    one identifier, so the second overwrote the first's survey output. Twelve
    cameras yielded eleven previews."""
    a = "4K Road traffic video for object detection and tracking.mp4"
    b = "4K Road traffic video for object detection and tracking - free download now!.mp4"
    assert stable_stem(a) != stable_stem(b)


def test_stable_stem_is_deterministic_and_filesystem_safe():
    name = "Incredible traffic Sound in Dhaka, Bangladesh। Rampura [4K].mp4"
    first, second = stable_stem(name), stable_stem(name)
    assert first == second
    assert all(c.isalnum() or c == "_" for c in first)


def test_identical_signatures_score_one():
    s = sig(1.0, -1.0, 1.0, -1.0)
    assert similarity(s, s) == pytest.approx(1.0)


def test_opposite_signatures_score_negative():
    assert similarity(sig(1.0, -1.0), sig(-1.0, 1.0)) == pytest.approx(-1.0)


def test_the_measured_duplicate_is_grouped():
    """M6 Motorway and 'Road traffic video for object recognition' correlate at
    0.981 — the same motorway from the same viewpoint, under two filenames."""
    groups = group_cameras({
        "m6": sig(1.0, 1.0, -1.0, -1.0),
        "road_recognition": sig(1.0, 1.0, -1.0, -1.0),
        "dhaka": sig(-1.0, 1.0, 1.0, -1.0),
    })
    assert groups["m6"] == groups["road_recognition"]
    assert groups["dhaka"] != groups["m6"]
    assert distinct_cameras(groups) == 2


def test_grouping_is_transitive():
    """A chain of near matches is one camera drifting, not three cameras. If it
    were not transitive, the ends of the chain would land in different splits."""
    a = sig(1.0, 1.0, 1.0, -1.0)
    b = sig(1.0, 1.0, -1.0, -1.0)      # close to a and to c
    c = sig(1.0, -1.0, -1.0, -1.0)     # further from a
    assert similarity(a, c) < 0.80     # the ends alone would not match
    groups = group_cameras({"a": a, "b": b, "c": c}, threshold=0.45)
    assert groups["a"] == groups["b"] == groups["c"]


def test_camera_ids_are_stable_across_runs():
    """NFR-07. A group id that changes between runs changes the split."""
    sigs = {"zeta": sig(1.0, -1.0), "alpha": sig(1.0, -1.0), "mid": sig(-1.0, 1.0)}
    assert group_cameras(sigs) == group_cameras(dict(reversed(list(sigs.items()))))
    assert group_cameras(sigs)["zeta"] == "alpha"      # first name wins


def test_a_camera_split_across_two_splits_is_refused():
    with pytest.raises(ValueError, match="appears in both"):
        assert_no_camera_leak(
            {"m6.mp4": "cam_a", "road_recognition.mp4": "cam_a"},
            {"m6.mp4": "train", "road_recognition.mp4": "test"},
        )


def test_one_camera_wholly_inside_one_split_is_fine():
    assert_no_camera_leak(
        {"m6.mp4": "cam_a", "road_recognition.mp4": "cam_a", "dhaka.mp4": "cam_b"},
        {"m6.mp4": "train", "road_recognition.mp4": "train", "dhaka.mp4": "test"},
    )


def test_mismatched_signature_lengths_raise():
    with pytest.raises(ValueError, match="lengths differ"):
        similarity(sig(1.0, 2.0), sig(1.0))
