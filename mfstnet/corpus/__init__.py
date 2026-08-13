"""Corpus construction for MFSTNet (PRD §8.6).

Turns continuous video into labelled training sequences:

    video --> frames (every step_s) --> per-lane counts --> labels --> sequences

This package holds the parts that need no GPU, no video and no PyTorch: the
timing arithmetic, the label rule, the density banding, and the split
assignment. They are pure functions over plain data so they can be tested
exhaustively before any of the expensive machinery exists.

That matters here more than usual. PRD amendment A15 records a defect in
exactly this arithmetic -- the label had been placed inside the observation
window, and the stated minimum clip length was shorter than one sample needs.
Every number was individually correct; the combination was not. These modules
exist so the combination is executable and therefore testable.

Stage mapping to the implementation plan (PLAN-01):

    S0  geometry.py lane polygons, point-in-polygon, disjointness
    S0  sources.py  source registry, clip validation, dev-corpus guard
    S4  labels.py   counts -> smoothing -> thresholds -> label + density band
    S5  windows.py  window timing, and how many sequences a clip yields
    S5  splits.py   clip-level split assignment and the leakage guard
"""

from .labels import (
    CongestionClass,
    density_band,
    label_from_count,
    smooth_counts,
)
from .windows import (
    WindowGeometry,
    Sequence,
    sequences_from_clip,
)
from .splits import (
    assign_splits,
    assert_no_clip_leakage,
)
from .geometry import (
    Polygon,
    PolygonError,
    assign_lane,
    assert_disjoint,
)
from .sources import (
    Clip,
    Source,
    SourceError,
    DevCorpusError,
    load_source,
    assert_usable_for_reporting,
)

__all__ = [
    "CongestionClass",
    "label_from_count",
    "smooth_counts",
    "density_band",
    "WindowGeometry",
    "Sequence",
    "sequences_from_clip",
    "assign_splits",
    "assert_no_clip_leakage",
    "Polygon",
    "PolygonError",
    "assign_lane",
    "assert_disjoint",
    "Clip",
    "Source",
    "SourceError",
    "DevCorpusError",
    "load_source",
    "assert_usable_for_reporting",
]
