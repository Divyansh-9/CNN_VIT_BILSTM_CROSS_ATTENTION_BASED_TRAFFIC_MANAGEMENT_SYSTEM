"""Sequential sampling must return the same pixels the seeking path returned.

This is the only property that matters. The corpus already on disk was built by
seeking, and every count, label and cached feature derives from those exact
pixels -- so a faster reader that returns *nearly* the same frames would
silently split the corpus into two incompatible halves (the shape of P33).

The comparison is byte-for-byte on real footage, not on a synthetic clip: the
cost being avoided is H.264 keyframe distance, which a generated test video
would not reproduce.
"""

from __future__ import annotations

import pathlib

import pytest

from mfstnet.corpus.video import iter_sampled_frames, read_sampled_frames

CLIPS = pathlib.Path("data/_corpus_clips")
SAMPLES = 6


def a_real_clip() -> pathlib.Path:
    """The smallest clip available, so the test stays quick."""
    candidates = sorted(CLIPS.glob("*.mp4"), key=lambda p: p.stat().st_size)
    if not candidates:
        pytest.skip(f"no footage under {CLIPS}")
    return candidates[0]


def by_seeking(path: pathlib.Path, stride: int, limit: int) -> list:
    """The implementation being replaced, kept here as the reference."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    frames = []
    for index in range(limit):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index * stride)
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    return frames


@pytest.mark.parametrize("stride", [1, 30, 60])
def test_sequential_frames_are_byte_identical_to_seeking(stride):
    clip = a_real_clip()
    reference = by_seeking(clip, stride, SAMPLES)
    if len(reference) < SAMPLES:
        pytest.skip("clip too short for this stride")

    got = read_sampled_frames(clip, stride, limit=SAMPLES)
    assert len(got) == len(reference)
    for position, (a, b) in enumerate(zip(got, reference)):
        assert a.shape == b.shape, f"frame {position} differs in shape"
        assert (a == b).all(), (
            f"frame {position} at stride {stride} differs from the seeking "
            f"path. Every count and label in the corpus derives from these "
            f"exact pixels."
        )


def test_limit_is_respected():
    clip = a_real_clip()
    assert len(read_sampled_frames(clip, 30, limit=3)) == 3


def test_reading_past_the_end_stops_rather_than_raising():
    """A clip is finite; asking for more samples than it has is not an error."""
    clip = a_real_clip()
    frames = read_sampled_frames(clip, 100_000, limit=50)
    assert len(frames) <= 50


def test_stride_below_one_is_refused():
    with pytest.raises(ValueError):
        list(iter_sampled_frames(a_real_clip(), 0))


def test_iteration_is_lazy():
    """The point of the iterator form: a 4K clip must not be held in memory."""
    clip = a_real_clip()
    stream = iter_sampled_frames(clip, 30)
    first = next(stream)
    assert first is not None
    stream.close()


def test_a_missing_file_yields_nothing_rather_than_hanging():
    assert read_sampled_frames(CLIPS / "does-not-exist.mp4", 1, limit=5) == []
