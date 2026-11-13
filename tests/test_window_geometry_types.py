"""A15's geometry must reject non-integral timings at construction.

`30.0 % 2.0` is `0.0`, so the divisibility checks pass for floats and the
derived frame counts come out as floats. The failure then surfaces as
`TypeError: 'float' object cannot be interpreted as an integer` from inside
`range()`, several calls away from the value that caused it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.windows import WindowGeometry, sequences_from_clip


def test_float_timings_are_refused_at_construction():
    with pytest.raises(ValueError, match="whole number of seconds"):
        WindowGeometry(T=60, step_s=2.0, horizon_s=60.0, stride_s=30.0)


def test_a_fractional_step_is_refused():
    """2.5s steps are not supported, and saying so beats a TypeError later."""
    with pytest.raises(ValueError):
        WindowGeometry(T=60, step_s=2.5, horizon_s=60, stride_s=30)


def test_integral_floats_are_still_refused():
    """`2.0` reads as harmless and is not: every derived count turns float."""
    with pytest.raises(ValueError, match="whole number of seconds"):
        WindowGeometry(step_s=2.0)


def test_a_float_T_is_refused():
    with pytest.raises(ValueError, match="whole number"):
        WindowGeometry(T=60.0)


def test_the_supported_values_still_build_and_enumerate():
    """A28's candidates, which is what this guard exists to keep working."""
    for step in (1, 2, 5):
        g = WindowGeometry(T=60, step_s=step, horizon_s=60, stride_s=30)
        assert isinstance(g.stride_frames, int)
        assert isinstance(g.min_frames, int)
        assert isinstance(g.label_offset_frames, int)
        seqs = sequences_from_clip("clip", g.min_frames + g.stride_frames * 3, g)
        assert len(seqs) == 4
        assert all(isinstance(s.label_index, int) for s in seqs)


def test_bool_is_not_an_acceptable_int():
    """`True` is an int in Python and a nonsense step size."""
    with pytest.raises(ValueError):
        WindowGeometry(step_s=True)
