"""Decide whether two clips are the same camera. A camera split depends on it.

A multi-camera corpus splits **by camera**, so that the test set is a camera the
model never trained on. That is only leak-free if "camera" is identified
correctly, and a filename does not identify one.

**Two failures found by looking at a contact sheet, both of which would have
leaked silently:**

1. **Different files, one camera.** `M6 Motorway Traffic.mp4` and
   `Road traffic video for object recognition.mp4` are the same motorway from
   the same viewpoint — frame correlation **0.981**. Split by filename they land
   in different splits, and the model is tested on a camera it trained on.

2. **Different files, one name.** Two clips whose names differ only after 48
   characters collapsed to the same identifier, so one overwrote the other's
   survey output. Twelve cameras produced eleven previews and nobody noticed
   until two cards in a review sheet showed the same picture.

Neither is exotic. A collection assembled from downloads accumulates re-uploads,
re-encodes and trimmed copies, and every one of them is a leak waiting for a
split to be drawn through it.

**Identity here is the scene, not the file.** A downscaled, contrast-normalised
frame is correlated against every other; above `threshold` the clips are one
camera and must share a split.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Sequence as Seq

__all__ = ["scene_signature", "similarity", "group_cameras", "stable_stem"]

DEFAULT_THRESHOLD = 0.80


def stable_stem(path: str, length: int = 40) -> str:
    """A filesystem-safe identifier that cannot collide.

    Truncating a name to a fixed length is the bug this exists to prevent: two
    clips differing only in a suffix produce one identifier, and the second
    silently overwrites the first. The path hash makes collision impossible
    while keeping the readable prefix that makes output browsable.
    """
    safe = "".join(c if c.isalnum() else "_" for c in path.rsplit("/", 1)[-1])
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:8]
    return f"{safe[:length]}_{digest}"


def scene_signature(gray_frame, size: tuple[int, int] = (64, 36)):
    """Contrast-normalised thumbnail of one frame, as a flat float list.

    Normalising removes exposure and colour-grade differences, so a re-encode or
    a brightness shift of the same scene still matches. It does not remove a
    genuine viewpoint change, which is the distinction that matters.
    """
    import numpy as np

    import cv2

    small = cv2.resize(gray_frame, size, interpolation=cv2.INTER_AREA)
    array = small.astype(np.float32)
    array = (array - array.mean()) / (array.std() + 1e-6)
    return array.ravel().tolist()


def similarity(a: Seq[float], b: Seq[float]) -> float:
    """Mean product of two normalised signatures: 1.0 identical, 0.0 unrelated."""
    if len(a) != len(b):
        raise ValueError(f"signature lengths differ: {len(a)} vs {len(b)}")
    if not a:
        raise ValueError("empty signature")
    return sum(x * y for x, y in zip(a, b)) / len(a)


def group_cameras(
    signatures: dict[str, Seq[float]],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, str]:
    """Map each clip to a camera id. Clips above `threshold` share an id.

    Grouping is **transitive** — if A matches B and B matches C, all three are
    one camera even when A and C fall below the threshold. A chain of near
    matches is one camera drifting, not three cameras, and treating it
    otherwise puts two of them either side of a split.

    Returns clip name -> camera id, where the id is the alphabetically first
    member so it is stable across runs (NFR-07).
    """
    names = sorted(signatures)
    parent = {n: n for n in names}

    def find(n: str) -> str:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if similarity(signatures[a], signatures[b]) >= threshold:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)

    return {n: find(n) for n in names}


def distinct_cameras(groups: dict[str, str]) -> int:
    """How many independent cameras a set of clips actually represents."""
    return len(set(groups.values()))


def assert_no_camera_leak(
    clip_to_camera: dict[str, str], clip_to_split: dict[str, str]
) -> None:
    """Raise if any camera appears in more than one split.

    The check `assert_no_clip_leakage` performs for clips, at the level that
    actually matters once duplicate files are possible.
    """
    seen: dict[str, str] = {}
    for clip, camera in clip_to_camera.items():
        split = clip_to_split.get(clip)
        if split is None:
            continue
        if camera in seen and seen[camera] != split:
            raise ValueError(
                f"camera {camera!r} appears in both {seen[camera]!r} and "
                f"{split!r}. Two files of one camera were split apart, so the "
                f"model would be tested on a camera it trained on. Group them "
                f"with group_cameras() before assigning splits."
            )
        seen.setdefault(camera, split)
