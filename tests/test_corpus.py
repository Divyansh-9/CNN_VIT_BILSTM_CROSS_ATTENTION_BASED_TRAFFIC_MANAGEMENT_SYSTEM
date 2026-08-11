"""Tests for corpus construction (PLAN-01 WI-15).

Priority is the arithmetic PRD amendment A15 corrected, because it is invisible
in a loss curve: a label placed inside the observation window trains a model
that scores well on validation and is useless deployed.

Pure stdlib — no torch, no video, no GPU. These run in milliseconds and belong
in CI before any of the expensive machinery exists.

    python -m pytest tests/test_corpus.py -q
"""

from __future__ import annotations

import pytest

from mfstnet.corpus import (
    CongestionClass,
    Sequence,
    WindowGeometry,
    assert_no_clip_leakage,
    assign_splits,
    density_band,
    label_from_count,
    sequences_from_clip,
    smooth_counts,
)
from mfstnet.corpus.splits import LeakageError, ratio_deviation, split_counts


# ---------------------------------------------------------------- geometry --

def test_geometry_matches_the_prd():
    g = WindowGeometry()
    assert g.observation_span_s == 295      # 59 intervals, not 60
    assert g.horizon_frames == 12           # PRD §8.4 "prediction_horizon: 12"
    assert g.label_offset_frames == 71
    assert g.label_offset_s == 355
    assert g.min_frames == 72
    assert g.stride_frames == 6


@pytest.mark.parametrize(
    "duration_s, expected",
    [
        (300, 0),      # A15: a 5-minute clip yields NOTHING
        (354, 0),      # one second short
        (355, 1),      # exactly enough
        (360, 1),      # the protocol minimum
        (720, 13),     # ADR-002's worked example
        (3600, 109),   # the "~110 per hour" figure that hid the defect
    ],
)
def test_sequence_yield_by_clip_length(duration_s, expected):
    assert WindowGeometry().count_for_duration(duration_s) == expected


def test_label_frame_is_strictly_after_the_observation_window():
    """The A15 defect itself."""
    seq = sequences_from_clip("clip_a", 72)[0]
    assert len(seq.frame_indices) == 60
    assert seq.frame_indices[-1] == 59
    assert seq.label_index == 71
    assert seq.label_index > seq.frame_indices[-1]


def test_sequence_rejects_a_label_inside_its_window():
    """The dataclass refuses to construct the defective shape at all."""
    with pytest.raises(ValueError, match="A15"):
        Sequence("c", 0, tuple(range(60)), label_index=12)


def test_geometry_rejects_a_horizon_between_sampled_frames():
    with pytest.raises(ValueError, match="whole number of steps"):
        WindowGeometry(horizon_s=62, step_s=5)


def test_short_clip_yields_nothing_rather_than_failing():
    assert sequences_from_clip("tiny", 10) == []


def test_stride_and_overlap():
    seqs = sequences_from_clip("c", 90)
    assert [s.start_index for s in seqs] == [0, 6, 12, 18]
    shared = set(seqs[0].frame_indices) & set(seqs[1].frame_indices)
    assert len(shared) == 54, "consecutive windows share 54 of 60 frames"


# ------------------------------------------------------------------ labels --

@pytest.mark.parametrize(
    "count, expected",
    [(0, "LOW"), (4, "LOW"), (5, "MEDIUM"), (15, "MEDIUM"), (16, "HIGH"), (500, "HIGH")],
)
def test_label_boundaries(count, expected):
    """4/5 and 15/16 are where an off-by-one mislabels an entire class."""
    assert label_from_count(count).label == expected


def test_label_is_its_own_training_target():
    assert int(CongestionClass.LOW) == 0
    assert int(CongestionClass.HIGH) == 2


def test_label_uses_canonical_spelling():
    """TRIAGE-001 D1: the wire format must never emit 'MED'."""
    assert CongestionClass.MEDIUM.label == "MEDIUM"


def test_negative_count_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        label_from_count(-1)


def test_thresholds_out_of_order_are_rejected():
    with pytest.raises(ValueError, match="must be below"):
        label_from_count(5, low_max=20, med_max=10)


def test_smoothing_removes_a_dropped_detection_and_keeps_length():
    assert smooth_counts([5, 5, 40, 5, 5]) == [5, 5, 5, 5, 5]
    assert len(smooth_counts([1, 2, 3, 4, 5])) == 5


def test_smoothing_window_of_one_is_identity():
    assert smooth_counts([1, 9, 1], window=1) == [1, 9, 1]


def test_even_smoothing_window_is_rejected():
    with pytest.raises(ValueError, match="odd"):
        smooth_counts([1, 2, 3], window=2)


@pytest.mark.parametrize(
    "mean_count, band", [(0.0, "low"), (12.0, "low"), (12.1, "medium"),
                         (40.0, "medium"), (40.1, "high")]
)
def test_density_bands(mean_count, band):
    assert density_band(mean_count) == band


# ------------------------------------------------------------------ splits --

def _clips(n: int) -> list[str]:
    return [f"clip_{i:03d}" for i in range(n)]


def test_assignment_is_deterministic():
    assert assign_splits(_clips(40)) == assign_splits(_clips(40))


def test_adding_a_clip_does_not_reshuffle_existing_ones():
    """Hashing rather than shuffling: a rebuild after new footage arrives must
    not silently move earlier clips between splits."""
    before = assign_splits(_clips(40))
    after = assign_splits(_clips(40) + ["clip_new"])
    assert all(after[c] == before[c] for c in _clips(40))


def test_every_split_is_populated():
    assert all(v > 0 for v in split_counts(assign_splits(_clips(40))).values())


def test_too_few_clips_is_an_error_not_an_empty_test_split():
    with pytest.raises(ValueError, match="empty"):
        assign_splits(["just_one"])


def test_malformed_ratios_are_rejected():
    with pytest.raises(ValueError, match="sum to 1"):
        assign_splits(_clips(40), ratios=(0.5, 0.2, 0.2))


def test_ratio_deviation_is_reported_so_a_thin_test_split_is_visible():
    """A19: the bootstrap resamples clips, so effective n is the clip count."""
    dev = ratio_deviation(assign_splits(_clips(40)))
    assert set(dev) == {"train", "val", "test"}
    assert all(abs(d) < 0.25 for d in dev.values())


def test_clean_corpus_passes_the_leakage_guard():
    clips = _clips(40)
    assignment = assign_splits(clips)
    seqs = [s for c in clips for s in sequences_from_clip(c, 200)]
    assert_no_clip_leakage([s.clip_id for s in seqs],
                           [assignment[s.clip_id] for s in seqs])


def test_leakage_is_an_error_not_a_warning():
    """§2.5.1 predicts this at Week 11-12, where it looks like good accuracy."""
    with pytest.raises(LeakageError, match="span multiple splits"):
        assert_no_clip_leakage(["c1", "c1"], ["train", "test"])


def test_leakage_message_names_the_offending_clips():
    with pytest.raises(LeakageError) as exc:
        assert_no_clip_leakage(["a", "a", "b"], ["train", "test", "train"])
    assert "a" in str(exc.value)
    assert "b" not in str(exc.value).split(":")[-1]
