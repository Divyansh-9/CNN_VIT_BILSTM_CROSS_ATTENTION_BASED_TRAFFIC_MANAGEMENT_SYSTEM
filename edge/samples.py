"""The edge's per-lane count history, with the checks a forecast depends on.

Both edge forecasters (persistence for the class, ridge for the count;
ADR-027) read a window of 2 s samples. A window is only the scored method if
it is **contiguous, in order and plausible**, so this buffer enforces that
rather than leaving each forecaster to.

- **A gap resets the window.** If a sample arrives more than `max_gap_s` after
  the previous one, the camera or detector dropped out. The window then mixes
  two separate stretches of traffic, which is not what P94–P105 scored. The
  buffer empties, and no forecast is made until a full contiguous window has
  refilled. Out-of-order timestamps are refused.
- **Implausible counts are refused, not clipped.** A negative, non-integer or
  impossibly large count is a fault upstream, and silently clipping it would
  hide the fault.
- **Missing is not zero.** A sample must cover exactly the configured lanes.
  A lane that is absent is not filled in with 0, because 0 vehicles is an
  observation and a missing lane is not (P97a).
"""

from __future__ import annotations

from collections import deque

from contracts.mqtt import MAX_LANE_COUNT

__all__ = ["SampleError", "SampleBuffer"]

STEP_S = 2.0                     # the scored sampling step (P94)


class SampleError(ValueError):
    """A sample that must not enter a forecast window."""


class SampleBuffer:
    def __init__(self, lanes, length: int, *, max_gap_s: float = 1.5 * STEP_S) -> None:
        self.lanes = tuple(lanes)
        if not self.lanes:
            raise ValueError("a buffer needs at least one lane")
        self.length, self.max_gap_s = length, max_gap_s
        self.rings = {lane: deque(maxlen=length) for lane in self.lanes}
        self.last_ts: float | None = None
        self.resets = 0
        self.last_reset_reason = ""

    @property
    def ready(self) -> bool:
        return all(len(r) == self.length for r in self.rings.values())

    def reset(self, reason: str) -> None:
        for ring in self.rings.values():
            ring.clear()
        self.resets += 1
        self.last_reset_reason = reason

    def push(self, counts: dict[str, int], ts: float | None = None) -> None:
        if set(counts) != set(self.lanes):
            raise SampleError(f"sample covers {sorted(counts)}, lanes are {sorted(self.lanes)}; "
                              f"a missing lane is not a zero count")
        for lane, count in counts.items():
            if isinstance(count, bool) or not isinstance(count, int) \
                    or not 0 <= count <= MAX_LANE_COUNT:
                raise SampleError(f"{lane}: count {count!r} is not a whole number in "
                                  f"[0, {MAX_LANE_COUNT:.0f}]")
        if ts is not None:
            if self.last_ts is not None and ts <= self.last_ts:
                raise SampleError(f"sample at {ts} is not after the previous one at {self.last_ts}")
            if self.last_ts is not None and ts - self.last_ts > self.max_gap_s:
                self.reset(f"gap of {ts - self.last_ts:.1f} s, over {self.max_gap_s:.1f} s")
            self.last_ts = ts
        for lane, count in counts.items():
            self.rings[lane].append(count)

    def series(self, lane: str) -> list[int]:
        return list(self.rings[lane])
