"""Window timing for MFSTNet training sequences (PRD §8.6, amendment A15).

The arithmetic that PRD amendment A15 corrected. Stated once, here, in frame
indices rather than seconds -- seconds invite the off-by-one that caused the
original defect, because "60 frames at 5-second spacing" covers 59 intervals,
not 60.

    frame index i          <-> time i * step_s
    window starting at s   -> observed frames s .. s + T - 1
    last observed frame    -> s + T - 1
    label frame            -> s + T - 1 + horizon_frames   (strictly later)

With the PRD's values (T=60, step=5 s, horizon=60 s):

    observation span  = (60 - 1) * 5           = 295 s
    horizon in frames = 60 / 5                 = 12      (PRD §8.4's "12 steps")
    label offset      = 59 + 12                = 71 frames = 355 s
    minimum clip      = 72 frames              = 360 s

The original spec placed the label at t+60 s, which falls *inside* the 295-second
window: the model would read a frame it had already observed. Validation accuracy
would have looked excellent and the deployed model would have been useless.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

__all__ = ["WindowGeometry", "Sequence", "sequences_from_clip"]


@dataclass(frozen=True)
class WindowGeometry:
    """Timing of one training sample. Defaults reproduce PRD §8.2 and §8.4."""

    T: int = 60
    step_s: int = 5
    horizon_s: int = 60
    stride_s: int = 30

    def __post_init__(self) -> None:
        if self.T < 2:
            raise ValueError(f"T must be at least 2, got {self.T}")
        if self.step_s < 1:
            raise ValueError(f"step_s must be positive, got {self.step_s}")
        if self.horizon_s % self.step_s:
            raise ValueError(
                f"horizon_s ({self.horizon_s}) must be a whole number of steps "
                f"of {self.step_s}s -- otherwise the label falls between sampled frames"
            )
        if self.stride_s % self.step_s:
            raise ValueError(
                f"stride_s ({self.stride_s}) must be a whole number of steps "
                f"of {self.step_s}s"
            )
        if self.stride_s < self.step_s:
            raise ValueError("stride_s must be at least one step")

    # -- derived quantities; never hand-write these anywhere else --

    @property
    def observation_span_s(self) -> int:
        """Seconds covered by the observed frames. 59 intervals, not 60."""
        return (self.T - 1) * self.step_s

    @property
    def horizon_frames(self) -> int:
        return self.horizon_s // self.step_s

    @property
    def label_offset_frames(self) -> int:
        """Frames from window start to the label frame."""
        return (self.T - 1) + self.horizon_frames

    @property
    def label_offset_s(self) -> int:
        return self.observation_span_s + self.horizon_s

    @property
    def min_frames(self) -> int:
        """Fewest sampled frames a clip needs to yield one sequence."""
        return self.label_offset_frames + 1

    @property
    def min_clip_s(self) -> int:
        return self.label_offset_s

    @property
    def stride_frames(self) -> int:
        return self.stride_s // self.step_s

    def frames_for_duration(self, duration_s: float) -> int:
        """Sampled frames obtainable from a clip of this duration."""
        if duration_s < 0:
            raise ValueError(f"duration must be non-negative, got {duration_s}")
        return int(duration_s // self.step_s) + 1

    def count_for_duration(self, duration_s: float) -> int:
        """Sequences a clip of this duration yields. Zero is a valid answer."""
        return _count(self.frames_for_duration(duration_s), self)


@dataclass(frozen=True)
class Sequence:
    """One training sample: which frames are observed, and which is the target.

    Frame indices are positions in the clip's sampled-frame series, not absolute
    times. `clip_id` travels with the sequence because splits are cut by clip
    (PRD §8.6) and the guard in `splits` needs it.
    """

    clip_id: str
    start_index: int
    frame_indices: tuple[int, ...]
    label_index: int

    def __post_init__(self) -> None:
        if self.label_index <= self.frame_indices[-1]:
            raise ValueError(
                f"label frame {self.label_index} is not after the last observed "
                f"frame {self.frame_indices[-1]} -- this is the A15 defect; the "
                f"model would read a frame it has already seen"
            )


def _count(n_frames: int, g: WindowGeometry) -> int:
    if n_frames < g.min_frames:
        return 0
    return (n_frames - g.min_frames) // g.stride_frames + 1


def sequences_from_clip(
    clip_id: str, n_frames: int, geometry: WindowGeometry | None = None
) -> list[Sequence]:
    """Enumerate every sequence a clip supports.

    Returns an empty list when the clip is too short. That is a normal outcome,
    not an error -- but callers must log how often it happens. If every clip
    yields zero, the recording protocol is wrong rather than the data (A15).

    Args:
        clip_id: source clip identifier, carried into each sequence.
        n_frames: sampled frames available, indices 0 .. n_frames - 1.
        geometry: timing. Defaults to the PRD values.
    """
    g = geometry or WindowGeometry()
    if n_frames < 0:
        raise ValueError(f"n_frames must be non-negative, got {n_frames}")

    return list(_iter_sequences(clip_id, n_frames, g))


def _iter_sequences(clip_id: str, n_frames: int, g: WindowGeometry) -> Iterator[Sequence]:
    last_start = n_frames - g.min_frames
    if last_start < 0:
        return
    for start in range(0, last_start + 1, g.stride_frames):
        yield Sequence(
            clip_id=clip_id,
            start_index=start,
            frame_indices=tuple(range(start, start + g.T)),
            label_index=start + g.label_offset_frames,
        )
