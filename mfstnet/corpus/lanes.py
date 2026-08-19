"""Assign detections to lanes by nearest centre — disjoint by construction.

**Why this replaces polygons for the assignment step.** `survey_lanes.py`
clusters detection centroids with k-means, then draws an axis-aligned box around
each cluster and calls it a lane polygon. Run across all twelve qualifying
cameras, **eleven produced overlapping boxes.**

That is not bad luck. Roads run diagonally across a frame, and the axis-aligned
extent of a diagonal cluster necessarily reaches into its neighbour's. Convex
hulls do not fix it either — `survey_lanes.extent` already documents that hulls
of adjacent approaches routinely overlap, which is why boxes were chosen.

Overlapping lanes double-count every vehicle in the shared region, so eleven of
twelve cameras needed hand-editing before they could be used. That was the whole
cost the batch survey was meant to remove.

**The polygon was always a lossy re-encoding of a decision k-means had already
made.** Clustering assigns every detection to exactly one centre; drawing a
region around each cluster and re-testing containment can only lose information
and introduce overlap. So keep the centres and assign by nearest.

* **Disjoint by construction.** A point has one nearest centre. There is no
  overlap to check for, edit, or get wrong.
* **Reproduces the clustering exactly**, rather than approximating it.
* **Still per-camera** — P17 is unchanged. Centres live in the image plane and
  belong to one camera exactly as polygons did.

**What still needs a human.** Whether the clusters correspond to real approaches.
A centre sitting on a car park is as wrong as a polygon over one, and only the
rendered picture reveals it. This removes the overlap-editing, not the looking.

**`max_radius` matters.** Nearest-centre assignment alone is unbounded: a vehicle
parked far off the carriageway is still nearest to *something*. Detections beyond
`max_radius` are unassigned, which is the analogue of falling outside every
polygon, and the unassigned rate stays the diagnostic P17 made it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence as Seq

__all__ = ["LaneCentres", "assign_to_lane"]


@dataclass(frozen=True)
class LaneCentres:
    """Per-camera lane centres in normalised image coordinates.

    Args:
        names: lane names, in the same order as `centres`.
        centres: (x, y) per lane, each in [0, 1].
        max_radius: normalised distance beyond which a detection is unassigned.
            Defaults to 0.25 — a quarter of the frame diagonal-ish, wide enough
            not to discard legitimate distant vehicles and tight enough to drop
            things on the far pavement.
    """

    names: tuple[str, ...]
    centres: tuple[tuple[float, float], ...]
    max_radius: float = 0.25

    def __post_init__(self) -> None:
        if len(self.names) != len(self.centres):
            raise ValueError(
                f"{len(self.names)} name(s) for {len(self.centres)} centre(s)")
        if not self.names:
            raise ValueError("at least one lane is required")
        if len(set(self.names)) != len(self.names):
            raise ValueError(f"duplicate lane names: {self.names}")
        for name, (x, y) in zip(self.names, self.centres):
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(
                    f"lane {name!r} centre ({x}, {y}) is outside the frame. "
                    f"Coordinates are normalised, not pixels."
                )
        if self.max_radius <= 0:
            raise ValueError(f"max_radius must be positive, got {self.max_radius}")


def assign_to_lane(point: tuple[float, float], lanes: LaneCentres) -> str | None:
    """Nearest lane centre, or None if beyond `max_radius`.

    Ties go to the earlier lane in `names`. A tie means the point is exactly
    equidistant from two centres, which is a measure-zero case on real
    coordinates — it is resolved deterministically rather than left to
    iteration order, because a silent order dependency is the defect P17 found
    in polygon containment.
    """
    x, y = point
    best_name: str | None = None
    best_distance = math.inf
    for name, (cx, cy) in zip(lanes.names, lanes.centres):
        distance = math.hypot(x - cx, y - cy)
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name if best_distance <= lanes.max_radius else None
