"""Tests for lane geometry and the source registry (PLAN-01 WI-09).

Pure standard library — no Shapely, no YAML, no fixture files.

    python -m pytest tests/test_sources.py -q
"""

from __future__ import annotations

import pytest

from mfstnet.corpus import (
    DevCorpusError,
    Polygon,
    PolygonError,
    SourceError,
    assert_disjoint,
    assert_usable_for_reporting,
    assign_lane,
    load_source,
)

# Four disjoint quadrants with a gap in the middle for the junction itself.
N = Polygon("N", ((0.0, 0.0), (0.45, 0.0), (0.45, 0.45), (0.0, 0.45)))
S = Polygon("S", ((0.55, 0.55), (1.0, 0.55), (1.0, 1.0), (0.55, 1.0)))
E = Polygon("E", ((0.55, 0.0), (1.0, 0.0), (1.0, 0.45), (0.55, 0.45)))
W = Polygon("W", ((0.0, 0.55), (0.45, 0.55), (0.45, 1.0), (0.0, 1.0)))
LANES = [N, S, E, W]
LANES_CFG = {p.name: p.vertices for p in LANES}

GOOD = {
    "source_id": "campus_gate",
    "kind": "production",
    "licence": "institutional permission 2026-08",
    "clips": [
        {"clip_id": "c1", "path": "a.mp4", "duration_s": 1800},
        {"clip_id": "c2", "path": "b.mp4", "duration_s": 900},
    ],
    "lanes": LANES_CFG,
}


# ---------------------------------------------------------------- polygon --

def test_area_is_computed_from_the_shoelace_formula():
    assert N.area == pytest.approx(0.45 * 0.45)


@pytest.mark.parametrize(
    "point, inside", [((0.2, 0.2), True), ((0.8, 0.8), False), ((0.44, 0.01), True)]
)
def test_containment(point, inside):
    assert N.contains(point) is inside


def test_a_point_on_the_boundary_counts_as_inside():
    """Shapely's `contains` excludes the boundary and `intersects` includes it.
    A centroid landing on a shared edge would be assigned by one and dropped by
    the other, so the convention is pinned here and tested."""
    assert N.contains((0.45, 0.2)), "edge"
    assert N.contains((0.0, 0.0)), "vertex"


def test_degenerate_polygons_are_rejected():
    with pytest.raises(PolygonError, match="at least 3"):
        Polygon("x", ((0, 0), (1, 1)))
    with pytest.raises(PolygonError, match="zero area"):
        Polygon("x", ((0, 0), (0.5, 0.5), (1.0, 1.0)))


def test_pixel_coordinates_are_rejected():
    """A polygon in pixels means something different after any resize, and
    nothing downstream would raise."""
    with pytest.raises(PolygonError, match="normalised"):
        Polygon("x", ((0, 0), (640, 0), (640, 480)))


# ---------------------------------------------------------- lane assignment --

@pytest.mark.parametrize(
    "centroid, lane",
    [((0.2, 0.2), "N"), ((0.8, 0.8), "S"), ((0.8, 0.2), "E"), ((0.2, 0.8), "W")],
)
def test_assigns_to_the_containing_lane(centroid, lane):
    assert assign_lane(centroid, LANES) == lane


def test_the_junction_centre_belongs_to_no_lane():
    """None is a normal outcome, not an error — but S3 must report its rate.
    A high unassigned rate is the only early signal that polygons are wrong."""
    assert assign_lane((0.5, 0.5), LANES) is None


# ------------------------------------------------------------ disjointness --

def test_quadrants_are_disjoint():
    assert_disjoint(LANES)


@pytest.mark.parametrize(
    "other, case",
    [
        (Polygon("X", ((0.2, 0.2), (0.6, 0.2), (0.6, 0.6), (0.2, 0.6))), "crossing"),
        (Polygon("X", ((0.45, 0.0), (0.9, 0.0), (0.9, 0.45), (0.45, 0.45))), "shared edge"),
        (Polygon("X", ((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2))), "nested"),
    ],
)
def test_overlap_is_rejected(other, case):
    """If two lanes can claim one centroid, every count depends on iteration
    order — a bug that produces plausible numbers and never raises."""
    with pytest.raises(PolygonError, match="overlap"):
        assert_disjoint([N, other])


def test_duplicate_lane_names_are_rejected():
    with pytest.raises(PolygonError, match="duplicate"):
        assert_disjoint([N, N])


# --------------------------------------------------------------- registry --

def test_a_valid_source_loads_without_warnings():
    src = load_source(GOOD)
    assert src.source_id == "campus_gate"
    assert src.warnings == ()


def test_sequence_count_follows_the_a15_arithmetic():
    """1800s and 900s clips, 355s per sequence, 30s stride."""
    expected = (1800 - 355) // 30 + 1 + (900 - 355) // 30 + 1
    assert load_source(GOOD).total_sequences() == expected == 68


def test_missing_keys_are_rejected():
    with pytest.raises(SourceError, match="missing required"):
        load_source({"source_id": "x"})


def test_kind_has_no_default():
    """A source whose status nobody stated is the one that reaches a reported
    result by accident."""
    with pytest.raises(SourceError, match="must be 'dev'"):
        load_source({**GOOD, "kind": "maybe"})


def test_a_blank_licence_is_rejected():
    with pytest.raises(SourceError, match="licence"):
        load_source({**GOOD, "licence": "   "})


def test_duplicate_clip_ids_are_rejected():
    """Splits are cut by clip, so two clips sharing an id straddle splits."""
    clips = [
        {"clip_id": "same", "path": "a", "duration_s": 900},
        {"clip_id": "same", "path": "b", "duration_s": 900},
    ]
    with pytest.raises(SourceError, match="duplicate clip_id"):
        load_source({**GOOD, "clips": clips})


def test_every_clip_too_short_is_an_error_not_an_empty_corpus():
    """PRD A15. If nothing yields a sequence, the recording protocol is wrong."""
    clips = [
        {"clip_id": "s1", "path": "a", "duration_s": 300},
        {"clip_id": "s2", "path": "b", "duration_s": 200},
    ]
    with pytest.raises(SourceError, match="recording protocol"):
        load_source({**GOOD, "clips": clips})


def test_some_clips_too_short_warns_rather_than_fails():
    clips = [
        {"clip_id": "ok", "path": "a", "duration_s": 1800},
        {"clip_id": "short", "path": "b", "duration_s": 300},
    ]
    src = load_source({**GOOD, "clips": clips})
    assert len(src.warnings) == 1
    assert "300s" in src.warnings[0]
    assert src.total_sequences() == (1800 - 355) // 30 + 1


def test_fewer_than_four_lanes_warns():
    src = load_source({**GOOD, "lanes": {"N": N.vertices, "S": S.vertices}})
    assert any("only 2 lane" in w for w in src.warnings)


# --------------------------------------------------------- dev-corpus guard --

def test_production_sources_pass():
    assert_usable_for_reporting([load_source(GOOD)])


def test_a_dev_source_blocks_a_reported_run():
    """Enforced, not conventional. Convention would not survive Week 13."""
    dev = load_source({**GOOD, "source_id": "uadetrac", "kind": "dev",
                       "licence": "research use"})
    with pytest.raises(DevCorpusError, match="uadetrac"):
        assert_usable_for_reporting([load_source(GOOD), dev])


def test_the_override_exists_but_must_be_explicit():
    dev = load_source({**GOOD, "kind": "dev"})
    assert_usable_for_reporting([dev], allow_dev=True)
