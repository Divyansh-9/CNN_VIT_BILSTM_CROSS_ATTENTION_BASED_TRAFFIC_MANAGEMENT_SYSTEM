"""Read every Nth frame of a clip without seeking to it (P51).

Both halves of the corpus pipeline sample one frame every `stride` frames --
`build_corpus.py` to run the detector over it, `build_cache.py` to encode it --
and both did it the obvious way:

    capture.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = capture.read()

Measured on this footage, that costs **~105 ms per sampled frame**, against
**55 ms** for the detector itself on CUDA. The pipeline was spending most of its
time deciding which frame to look at rather than looking at it.

A seek into an H.264 stream is not a jump. The decoder has to start at the
nearest keyframe and decode forward to the target, so the cost is set by the
keyframe interval, not by the stride -- and at a stride of 60 frames the
sequential path decodes *fewer* frames than the seek does. `grab()` decodes a
frame without converting or returning it, which is the cheap half of `read()`,
so skipping is nearly free:

    seek (current)     105 ms/frame
    grab sequential     52 ms/frame     identical pixels

**Hardware-accelerated decode was measured in the same run and rejected.** It
was slower here (69 ms against 52 ms) and, more importantly, it returned
*different pixel values* from the software decoder. Every detection, every
count and every label derives from those pixels, so an NVDEC-built corpus and a
CPU-built one would silently disagree -- the same shape of defect as P33's TF32
feature divergence, and just as invisible. If it is ever revisited, it belongs
behind a flag recorded in the manifest, not as a default.

The sequential path returns byte-identical frames to the seeking one, which the
tests assert on real footage rather than assuming.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

__all__ = ["iter_sampled_frames", "read_sampled_frames"]


def iter_sampled_frames(
    path: Path | str,
    stride: int,
    *,
    limit: int | None = None,
) -> Iterator["object"]:
    """Yield every `stride`-th frame, decoding forward instead of seeking.

    Args:
        path: the video file.
        stride: frames between samples. 1 yields every frame.
        limit: stop after this many samples. `None` reads to the end.

    Yields:
        BGR frames as OpenCV returns them, in order, starting at frame 0.
    """
    import cv2

    if stride < 1:
        raise ValueError(f"stride must be at least 1, got {stride}")

    capture = cv2.VideoCapture(str(path))
    try:
        index = 0
        taken = 0
        while limit is None or taken < limit:
            if index % stride:
                # grab() decodes without converting or copying out, which is
                # what makes skipping cheaper than seeking past the same frames.
                if not capture.grab():
                    return
                index += 1
                continue
            if not capture.grab():
                return
            ok, frame = capture.retrieve()
            if not ok:
                return
            yield frame
            taken += 1
            index += 1
    finally:
        capture.release()


def read_sampled_frames(
    path: Path | str,
    stride: int,
    *,
    limit: int | None = None,
) -> list["object"]:
    """`iter_sampled_frames` collected into a list."""
    return list(iter_sampled_frames(path, stride, limit=limit))
