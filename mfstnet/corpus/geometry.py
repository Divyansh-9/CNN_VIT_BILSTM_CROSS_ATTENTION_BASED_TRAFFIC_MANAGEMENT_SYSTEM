"""Lane regions in normalised image coordinates (HLD S0).

A lane's region is a polygon. A detection belongs to the lane whose polygon
contains its box centroid — no tracking needed, which is why the corpus HLD
rules tracking out of scope.

Coordinates are **normalised to [0, 1]**, not pixels. Sources differ in
resolution and the same camera can be re-encoded; a polygon in pixels silently
means something different after a resize, and nothing would raise.

Point-in-polygon uses ray casting rather than Shapely so this runs before the
environment exists. Shapely can replace it later without changing the interface —
but check the boundary convention first, because they do not agree by default
(see `contains`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["Point", "Polygon", "PolygonError", "assign_lane"]

Point = tuple[float, float]

_EPS = 1e-9


class PolygonError(ValueError):
    """A polygon is malformed, or two lane polygons overlap."""


@dataclass(frozen=True)
class Polygon:
    """A closed lane region. Vertices in normalised [0, 1] coordinates.

    The polygon is implicitly closed — do not repeat the first vertex.
    """

    name: str
    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise PolygonError(
                f"lane {self.name!r}: a polygon needs at least 3 vertices, got {len(self.vertices)}"
            )
        for i, (x, y) in enumerate(self.vertices):
            if not (0.0 - _EPS <= x <= 1.0 + _EPS and 0.0 - _EPS <= y <= 1.0 + _EPS):
                raise PolygonError(
                    f"lane {self.name!r} vertex {i} is ({x}, {y}); coordinates must be "
                    f"normalised to [0, 1], not pixels. A pixel polygon means something "
                    f"different after any resize and nothing would raise."
                )
        if abs(self.area) < _EPS:
            raise PolygonError(
                f"lane {self.name!r} has zero area — vertices are collinear or duplicated"
            )

    @property
    def area(self) -> float:
        """Signed shoelace area. Sign indicates winding direction."""
        v = self.vertices
        n = len(v)
        return 0.5 * sum(
            v[i][0] * v[(i + 1) % n][1] - v[(i + 1) % n][0] * v[i][1] for i in range(n)
        )

    def contains(self, point: Point) -> bool:
        """Ray casting, counting a point on the boundary as **inside**.

        The boundary convention matters and is a real source of silent
        disagreement: Shapely's `contains` excludes the boundary, `intersects`
        includes it. A vehicle centroid landing exactly on a shared edge would be
        assigned by one and dropped by the other. We include it, and overlapping
        polygons are rejected at registration so a boundary point can belong to
        at most one lane anyway.
        """
        x, y = point
        v = self.vertices
        n = len(v)

        for i in range(n):
            if _on_segment(v[i], v[(i + 1) % n], point):
                return True

        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = v[i]
            xj, yj = v[j]
            if (yi > y) != (yj > y):
                x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < x_cross:
                    inside = not inside
            j = i
        return inside

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.vertices]
        ys = [p[1] for p in self.vertices]
        return min(xs), min(ys), max(xs), max(ys)


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cross) > 1e-9:
        return False
    return (
        min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
        and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS
    )


def assign_lane(centroid: Point, polygons: Sequence[Polygon]) -> str | None:
    """Return the lane containing this centroid, or None if no lane does.

    `None` is a normal outcome — a vehicle crossing the middle of the junction
    belongs to no approach. **The rate of `None` must be reported per clip**
    (HLD S3): a high unassigned rate means the polygons are drawn wrong, and it
    is the only early signal available before labels are compared to anything.
    """
    for poly in polygons:
        if poly.contains(centroid):
            return poly.name
    return None


def _segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    def orient(a: Point, b: Point, c: Point) -> int:
        d = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(d) < 1e-12 else (1 if d > 0 else -1)

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)

    if o1 != o2 and o3 != o4:
        return True
    # Collinear touching counts as overlap: a shared edge means a centroid on it
    # could be claimed by either lane.
    return any(
        o == 0 and _on_segment(a, b, c)
        for o, a, b, c in (
            (o1, p1, p2, p3), (o2, p1, p2, p4), (o3, p3, p4, p1), (o4, p3, p4, p2)
        )
    )


def assert_disjoint(polygons: Iterable[Polygon]) -> None:
    """Raise if any two lane polygons overlap or share an edge.

    Checked once at registration rather than per frame. If two lanes can both
    claim a centroid, every count downstream depends on iteration order — a bug
    that produces plausible numbers and never raises.

    Raises:
        PolygonError: naming the offending pair.
    """
    polys = list(polygons)
    names = [p.name for p in polys]
    if len(set(names)) != len(names):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise PolygonError(f"duplicate lane name(s): {dupes}")

    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a, b = polys[i], polys[j]
            if not _bboxes_touch(a, b):
                continue
            if _overlaps(a, b):
                raise PolygonError(
                    f"lanes {a.name!r} and {b.name!r} overlap or share an edge. "
                    f"A detection centroid in the shared region would be assigned "
                    f"by iteration order, which is not a decision anyone made."
                )


def _bboxes_touch(a: Polygon, b: Polygon) -> bool:
    ax0, ay0, ax1, ay1 = a.bbox()
    bx0, by0, bx1, by1 = b.bbox()
    return not (ax1 < bx0 - _EPS or bx1 < ax0 - _EPS or ay1 < by0 - _EPS or by1 < ay0 - _EPS)


def _overlaps(a: Polygon, b: Polygon) -> bool:
    na, nb = len(a.vertices), len(b.vertices)
    for i in range(na):
        for j in range(nb):
            if _segments_intersect(
                a.vertices[i], a.vertices[(i + 1) % na],
                b.vertices[j], b.vertices[(j + 1) % nb],
            ):
                return True
    # No edges cross, so one may be wholly inside the other.
    return a.contains(b.vertices[0]) or b.contains(a.vertices[0])
