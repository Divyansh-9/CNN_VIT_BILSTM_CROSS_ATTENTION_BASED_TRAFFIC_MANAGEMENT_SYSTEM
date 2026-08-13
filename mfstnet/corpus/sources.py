"""Source registry — stage S0 of the corpus pipeline (HLD).

A *source* is one camera position: its clips, its lane polygons, its licence,
and whether it may produce data used in a reported result.

Two things here exist to stop specific, already-identified failures.

**`kind: dev` is enforced, not conventional.** Development runs against public
non-Indian video with a COCO detector; those labels are poor and that is fine for
exercising plumbing. What is not fine is a `dev` corpus quietly producing a
number that reaches the paper. The training entry point calls
`assert_usable_for_reporting` and exits rather than trusting anyone to remember.

**Clips shorter than one sample are rejected at registration**, not silently
skipped later. PRD amendment A15: 355 seconds are needed per sequence, so a
5-minute clip yields zero. If every clip is short the recording protocol is
wrong, and that should surface when the source is registered rather than as an
empty corpus a week later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping

from .geometry import Polygon, PolygonError, assert_disjoint
from .windows import WindowGeometry

__all__ = [
    "Clip",
    "Source",
    "SourceError",
    "DevCorpusError",
    "load_source",
    "assert_usable_for_reporting",
]

Kind = Literal["dev", "production"]


class SourceError(ValueError):
    """A source definition is malformed or internally inconsistent."""


class DevCorpusError(RuntimeError):
    """A reported experiment was attempted against development data."""


@dataclass(frozen=True)
class Clip:
    clip_id: str
    path: str
    duration_s: float
    fps_native: float = 25.0

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise SourceError(f"clip {self.clip_id!r}: duration must be positive")
        if self.fps_native <= 0:
            raise SourceError(f"clip {self.clip_id!r}: fps must be positive")

    def sequence_count(self, geometry: WindowGeometry | None = None) -> int:
        return (geometry or WindowGeometry()).count_for_duration(self.duration_s)


@dataclass(frozen=True)
class Source:
    source_id: str
    kind: Kind
    licence: str
    clips: tuple[Clip, ...]
    lanes: tuple[Polygon, ...]
    notes: str = ""
    warnings: tuple[str, ...] = field(default=())

    @property
    def is_dev(self) -> bool:
        return self.kind == "dev"

    def total_sequences(self, geometry: WindowGeometry | None = None) -> int:
        g = geometry or WindowGeometry()
        return sum(c.sequence_count(g) for c in self.clips)

    def unusable_clips(self, geometry: WindowGeometry | None = None) -> list[Clip]:
        g = geometry or WindowGeometry()
        return [c for c in self.clips if c.sequence_count(g) == 0]


def load_source(
    data: Mapping[str, Any], geometry: WindowGeometry | None = None
) -> Source:
    """Build and validate a Source from a parsed config mapping.

    Takes a mapping rather than a path so it works without a YAML parser and so
    tests need no fixture files.

    Raises:
        SourceError: on a missing or malformed field.
        PolygonError: on a bad polygon, or overlapping lanes.
    """
    g = geometry or WindowGeometry()

    for key in ("source_id", "kind", "licence", "clips", "lanes"):
        if key not in data:
            raise SourceError(f"missing required key: {key!r}")

    source_id = str(data["source_id"])
    kind = data["kind"]
    if kind not in ("dev", "production"):
        raise SourceError(
            f"source {source_id!r}: kind must be 'dev' or 'production', got {kind!r}. "
            f"There is no default — a source whose status nobody stated is the one "
            f"that ends up in a reported result by accident."
        )

    licence = str(data["licence"]).strip()
    if not licence:
        raise SourceError(
            f"source {source_id!r}: licence must be stated. A licence you cannot "
            f"name is a licence you cannot cite (DATASETS §1)."
        )

    raw_clips = data["clips"]
    if not raw_clips:
        raise SourceError(f"source {source_id!r}: no clips")
    clips = tuple(
        Clip(
            clip_id=str(c["clip_id"]),
            path=str(c["path"]),
            duration_s=float(c["duration_s"]),
            fps_native=float(c.get("fps_native", 25.0)),
        )
        for c in raw_clips
    )
    ids = [c.clip_id for c in clips]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise SourceError(
            f"source {source_id!r}: duplicate clip_id(s) {dupes}. Splits are cut by "
            f"clip, so two clips sharing an id would straddle splits invisibly."
        )

    raw_lanes = data["lanes"]
    if not raw_lanes:
        raise SourceError(f"source {source_id!r}: no lanes")
    lanes = tuple(
        Polygon(name=str(name), vertices=tuple((float(x), float(y)) for x, y in verts))
        for name, verts in raw_lanes.items()
    )
    assert_disjoint(lanes)

    warnings: list[str] = []

    unusable = [c for c in clips if c.sequence_count(g) == 0]
    if unusable:
        detail = ", ".join(f"{c.clip_id} ({c.duration_s:.0f}s)" for c in unusable[:4])
        if len(unusable) == len(clips):
            raise SourceError(
                f"source {source_id!r}: EVERY clip is shorter than the {g.min_clip_s}s "
                f"a single sequence requires — {detail}. This source yields nothing. "
                f"The recording protocol is wrong, not the data (PRD A15)."
            )
        warnings.append(
            f"{len(unusable)} of {len(clips)} clips are under {g.min_clip_s}s and yield "
            f"no sequences: {detail}"
        )

    if len(lanes) < 4:
        warnings.append(
            f"only {len(lanes)} lane(s) defined. Per-lane ROI pooling handles fewer "
            f"than four approaches without padding, but the congestion head still "
            f"emits four outputs — confirm this is intended."
        )

    return Source(
        source_id=source_id,
        kind=kind,  # type: ignore[arg-type]
        licence=licence,
        clips=clips,
        lanes=lanes,
        notes=str(data.get("notes", "")),
        warnings=tuple(warnings),
    )


def assert_usable_for_reporting(
    sources: Iterable[Source], *, allow_dev: bool = False
) -> None:
    """Refuse to proceed when any source is development data.

    Call this from the training entry point, not from a code review checklist.

    Args:
        allow_dev: escape hatch for deliberate smoke tests. **Setting it must be
            recorded in the experiment record** — an override nobody wrote down
            is indistinguishable from no check at all.

    Raises:
        DevCorpusError: naming every dev source found.
    """
    dev = [s.source_id for s in sources if s.is_dev]
    if not dev:
        return
    if allow_dev:
        return
    raise DevCorpusError(
        f"reported run attempted against development source(s): {', '.join(dev)}. "
        f"Dev corpora use non-Indian video and a COCO detector, so their labels are "
        f"poor by construction — fine for exercising the pipeline, not for a result. "
        f"Pass allow_dev=True for a deliberate smoke test AND record it in the "
        f"experiment record."
    )
