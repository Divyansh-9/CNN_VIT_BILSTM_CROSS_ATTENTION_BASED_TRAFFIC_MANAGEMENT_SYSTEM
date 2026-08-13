"""Per-lane vehicle counting from detections — stage S3 (HLD).

The detector is blocked on the environment, but this half is not: given boxes,
assigning them to lanes is geometry. Separating the two means the counting logic
is testable now and the detector drops in later without touching it.

Counting is **instantaneous occupancy**, not flow and not queue length: every
detection whose box centroid falls inside a lane's approach polygon, at that
frame. No tracking — which is why the corpus HLD rules tracking out of scope.

The unassigned rate is returned alongside the counts and is not optional. Some
unassigned detections are correct — a vehicle crossing the middle of a junction
belongs to no approach — but a high rate means the polygons are wrong, and it is
the only signal available before labels are compared to anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .geometry import Polygon, assign_lane

__all__ = ["Detection", "FrameCounts", "count_frame", "count_clip"]


@dataclass(frozen=True)
class Detection:
    """One detection in **normalised** image coordinates, matching the polygons.

    `(x1, y1)` is the top-left corner and `(x2, y2)` the bottom-right.
    """

    cls: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError(
                f"box corners are inverted: ({self.x1}, {self.y1}) to ({self.x2}, {self.y2}). "
                f"Expected top-left then bottom-right."
            )

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


@dataclass(frozen=True)
class FrameCounts:
    """Counts for one frame, plus what could not be assigned."""

    per_lane: Mapping[str, int]
    per_lane_class: Mapping[str, Mapping[str, int]]
    unassigned: int
    total: int

    @property
    def unassigned_rate(self) -> float:
        return self.unassigned / self.total if self.total else 0.0


def count_frame(
    detections: Iterable[Detection],
    lanes: Sequence[Polygon],
    *,
    min_confidence: float = 0.25,
    exclude_classes: frozenset[str] = frozenset(),
) -> FrameCounts:
    """Count detections per lane for a single frame.

    Args:
        detections: boxes in normalised coordinates.
        lanes: approach polygons, already validated disjoint at registration.
        min_confidence: detections below this are dropped. Recorded in provenance —
            changing it changes every label downstream.
        exclude_classes: classes counted by the detector but not as vehicles.
            **`rider` belongs here** (DATASETS §6.1): counting a motorcyclist
            separately from the motorcycle inflates counts by roughly the
            two-wheeler share, biasing every congestion label the §8.6 pipeline
            produces.
    """
    per_lane: Counter[str] = Counter({p.name: 0 for p in lanes})
    per_class: dict[str, Counter[str]] = {p.name: Counter() for p in lanes}
    unassigned = 0
    total = 0

    for det in detections:
        if det.confidence < min_confidence or det.cls in exclude_classes:
            continue
        total += 1
        lane = assign_lane(det.centroid, lanes)
        if lane is None:
            unassigned += 1
            continue
        per_lane[lane] += 1
        per_class[lane][det.cls] += 1

    return FrameCounts(
        per_lane=dict(per_lane),
        per_lane_class={k: dict(v) for k, v in per_class.items()},
        unassigned=unassigned,
        total=total,
    )


def count_clip(
    frames: Sequence[Iterable[Detection]],
    lanes: Sequence[Polygon],
    **kwargs: object,
) -> tuple[dict[str, list[int]], float]:
    """Count every frame of a clip.

    Returns:
        `(counts_by_lane, unassigned_rate)` — one count series per lane, in frame
        order, plus the clip's overall unassigned rate for the S6 gate.
    """
    series: dict[str, list[int]] = {p.name: [] for p in lanes}
    unassigned = 0
    total = 0

    for dets in frames:
        fc = count_frame(dets, lanes, **kwargs)  # type: ignore[arg-type]
        for name in series:
            series[name].append(fc.per_lane.get(name, 0))
        unassigned += fc.unassigned
        total += fc.total

    return series, (unassigned / total if total else 0.0)
