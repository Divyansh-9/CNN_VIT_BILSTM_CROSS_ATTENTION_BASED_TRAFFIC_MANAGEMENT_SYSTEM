"""Congestion labelling from per-lane vehicle counts (PRD §14.1, §8.6).

The label rule is the PRD's own; no new thresholds are invented here.

    LOW     count <  5
    MEDIUM  5 <= count <= 15
    HIGH    count > 15

Counts come from the fine-tuned detector and are noisy frame to frame, so they
are smoothed before the threshold is applied. Smoothing uses a median rather
than a mean: a single missed detection shifts a mean but not a median, and a
dropped detection is the dominant error mode in dense scenes.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Sequence as Seq

__all__ = ["CongestionClass", "label_from_count", "smooth_counts", "density_band"]


class CongestionClass(IntEnum):
    """Ordered so the integer value is the training target directly."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @property
    def label(self) -> str:
        """Canonical spelling. TRIAGE-001 D1: never emit 'MED'."""
        return self.name


def label_from_count(count: int, *, low_max: int = 4, med_max: int = 15) -> CongestionClass:
    """Map a per-lane vehicle count to a congestion class.

    Defaults reproduce PRD §14.1. They are parameters rather than literals so a
    recalibration (pending item P1) is a config change, not a code change.

    Args:
        count: vehicles in the lane's approach region at one instant.
        low_max: highest count still LOW. PRD's "< 5" means 4.
        med_max: highest count still MEDIUM. PRD's "5-15" means 15.

    Raises:
        ValueError: on a negative count, or thresholds out of order.
    """
    if count < 0:
        raise ValueError(f"count must be non-negative, got {count}")
    if low_max >= med_max:
        raise ValueError(f"low_max ({low_max}) must be below med_max ({med_max})")

    if count <= low_max:
        return CongestionClass.LOW
    if count <= med_max:
        return CongestionClass.MEDIUM
    return CongestionClass.HIGH


def smooth_counts(counts: Seq[int], window: int = 3) -> list[int]:
    """Median-smooth a count series, preserving its length.

    Edges use the largest centred window that fits, so the first and last
    samples are less smoothed rather than dropped or padded. Dropping them would
    silently shorten a sequence; padding would invent observations.

    Args:
        counts: per-frame counts for one lane.
        window: odd window size. 1 disables smoothing.

    Raises:
        ValueError: if window is even or below 1.
    """
    if window < 1 or window % 2 == 0:
        raise ValueError(f"window must be a positive odd integer, got {window}")
    if window == 1 or not counts:
        return list(counts)

    half = window // 2
    n = len(counts)
    out: list[int] = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        chunk = sorted(counts[lo:hi])
        out.append(chunk[len(chunk) // 2])
    return out


def density_band(
    mean_total_count: float, *, low_max: float = 12.0, med_max: float = 40.0
) -> str:
    """Band a sequence by scene density, for stratified reporting (PRD A10).

    PRD §14.2's hypothesis is that CNN and ViT complement each other *in dense
    traffic*. A single aggregate metric averages a density-concentrated effect
    into invisibility, so every sequence carries a band and results are reported
    per band as well as overall.

    The input is the mean of the summed per-lane counts across the observation
    window, so the defaults are roughly four lanes' worth of the §14.1
    thresholds. They are provisional until the Week-2 count-distribution pilot
    measures the real distribution, which is why they are parameters.

    Note the deliberate asymmetry with `label_from_count`: for the **test**
    split these bands must be recomputed from human-verified counts (PRD A18),
    because banding by the detector's own output would let detector error decide
    which stratum a sequence lands in -- the residual circularity that A18
    closes.
    """
    if mean_total_count < 0:
        raise ValueError(f"mean count must be non-negative, got {mean_total_count}")
    if low_max >= med_max:
        raise ValueError(f"low_max ({low_max}) must be below med_max ({med_max})")

    if mean_total_count <= low_max:
        return "low"
    if mean_total_count <= med_max:
        return "medium"
    return "high"
