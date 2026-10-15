"""What a corpus is made of, checked against what the paper claims (P58).

`build_corpus.py` admits a camera if it clears P45's density gate and P17's
unassigned-rate gate. Both are correct. Neither asks **what the camera is**, and
that is how the M6 Motorway — a British divided carriageway with enforced lane
discipline, no junction and no mixed traffic — became 41% of the evaluation
corpus and 53% of every HIGH label in a project about unstructured Indian
traffic.

Nobody chose it. It was long, clean and dense, so it passed. That is the same
lesson P45 learned about duration, repeating one level up: **the gates select
for usability, and usability is not representativeness.**

The check here is the one nothing else performs:

> the paper claims a domain; does the **evaluation set** contain that domain?

It is a `FAIL`, not a warning, when no fold-eligible camera matches the declared
target. A model tested only on cameras outside its claimed domain has not been
evaluated on its claim, and no statistic computed downstream repairs that.

Composition cannot be inferred from a filename, so it is **declared** in
`data/cameras.json`, and every entry records how it was determined. A camera
whose country is unknown counts toward nothing — an assumed attribution is worse
than an absent one, because it would silently satisfy this check.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CameraRegistry", "Composition", "compose"]

REGISTRY = Path("data/cameras.json")
UNKNOWN = {"unknown", "", None}


@dataclass(frozen=True)
class Composition:
    """What a set of cameras is made of, and whether it matches the claim."""

    by_country: Counter
    by_traffic_type: Counter
    by_viewpoint: Counter
    windows_by_country: Counter
    on_target: tuple[str, ...]
    off_target: tuple[str, ...]
    unknown: tuple[str, ...]

    @property
    def matches_claim(self) -> bool:
        return bool(self.on_target)

    def dominant_country(self) -> tuple[str, float]:
        total = sum(self.windows_by_country.values())
        if not total:
            return ("none", 0.0)
        country, count = self.windows_by_country.most_common(1)[0]
        return (country, count / total)


class CameraRegistry:
    """Declared per-camera properties, loaded once."""

    def __init__(self, payload: dict) -> None:
        self.target = payload.get("target_domain", {})
        self.cameras = payload.get("cameras", {})

    @classmethod
    def load(cls, path: Path = REGISTRY) -> "CameraRegistry":
        if not path.is_file():
            raise SystemExit(
                f"{path} does not exist. Every camera in the corpus must declare "
                f"its country, viewpoint and traffic type — P58 exists because "
                f"nothing checked what the footage was."
            )
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def get(self, camera: str) -> dict:
        return self.cameras.get(camera, {})

    def is_on_target(self, camera: str) -> bool | None:
        """True, False, or None when it cannot be decided from what is declared.

        `None` is a distinct answer on purpose. A camera of unknown country is
        not evidence for the claim and is not evidence against it, and folding
        it into either would be the guess this module exists to prevent.
        """
        entry = self.get(camera)
        if not entry:
            return None
        for field in ("country", "traffic_type", "viewpoint"):
            wanted = self.target.get(field)
            if not wanted:
                continue
            value = entry.get(field)
            if value in UNKNOWN:
                return None
            if value not in wanted:
                return False
        return True

    def partition(self, camera: str) -> str:
        """`real_india`, `real_external` or `unknown` (ADR-025).

        Derived from `is_on_target`, so the partition a camera trains in and
        the scope a claim is checked over can never disagree: both ask the
        same question of the same declaration. `unknown` is its own answer and
        belongs to no domain — a camera nobody has inspected is evidence for
        neither.
        """
        verdict = self.is_on_target(camera)
        if verdict is None:
            return "unknown"
        return "real_india" if verdict else "real_external"

    def missing(self, cameras) -> list[str]:
        return sorted(c for c in cameras if c not in self.cameras)


def compose(registry: CameraRegistry, windows_by_camera: dict) -> Composition:
    """Summarise a set of cameras and weight it by how much data each supplies.

    Counting cameras and counting windows answer different questions. Three
    Bangladeshi cameras and one British one is a three-to-one split by camera
    and closer to even by window, and the second is what a trained model
    actually saw.
    """
    by_country, by_traffic, by_view = Counter(), Counter(), Counter()
    windows = Counter()
    on, off, unknown = [], [], []
    for camera, n in windows_by_camera.items():
        entry = registry.get(camera)
        country = entry.get("country", "undeclared")
        by_country[country] += 1
        by_traffic[entry.get("traffic_type", "undeclared")] += 1
        by_view[entry.get("viewpoint", "undeclared")] += 1
        windows[country] += n
        verdict = registry.is_on_target(camera)
        (on if verdict else off if verdict is False else unknown).append(camera)
    return Composition(
        by_country=by_country, by_traffic_type=by_traffic, by_viewpoint=by_view,
        windows_by_country=windows, on_target=tuple(sorted(on)),
        off_target=tuple(sorted(off)), unknown=tuple(sorted(unknown)),
    )
