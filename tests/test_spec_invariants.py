"""Assert the numeric relationships that span documents and subsystems.

Why this file exists
--------------------
PRD amendment A15 corrected a defect that nearly produced a corpus of size zero:
the label was placed at t+60s, which falls INSIDE the 295-second observation
window, and the stated minimum clip length (5 min) was shorter than one sample
requires (355 s).

Every individual number was correct. T=60 was right, step=5s was right,
horizon=60s was right, "5-minute clips" was wrong only in combination. Nobody
caught it because nobody added 295 and 60 and compared the result against the
clip length. Prose review does not reliably catch arithmetic that spans three
documents; a test does.

These tests need no ML dependencies and run in milliseconds, so they belong in
CI from day one -- before any model code exists.

    python -m pytest tests/test_spec_invariants.py -q
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml required; pip install -r requirements.txt")

SPEC_PATH = pathlib.Path(__file__).resolve().parent.parent / "mfstnet" / "configs" / "spec.yaml"


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Corpus window arithmetic -- the A15 defect class
# --------------------------------------------------------------------------

def test_window_span_matches_T_and_step(spec):
    s = spec["sequence"]
    assert (s["T"] - 1) * s["step_s"] == 295, (
        "Observation window must span 295 s. 60 frames at 5 s spacing covers "
        "59 intervals, not 60 -- an off-by-one here shifts every label."
    )


def test_label_falls_strictly_after_the_observation_window(spec):
    """The A15 bug, as an assertion.

    A label inside the window is not a forecast: the model reads a frame it has
    already observed. This shows up as excellent validation accuracy and a
    useless deployed model, which is the most expensive way to find a bug.
    """
    s = spec["sequence"]
    window_span = (s["T"] - 1) * s["step_s"]
    label_offset = window_span + s["horizon_s"]

    assert label_offset > window_span, "label must be AFTER the last observed frame"
    assert label_offset == 355, f"expected 355 s, got {label_offset}"


def test_minimum_clip_length_can_actually_produce_a_sequence(spec):
    """The other half of A15: a 5-minute clip yields zero sequences."""
    s = spec["sequence"]
    required = (s["T"] - 1) * s["step_s"] + s["horizon_s"]

    assert s["min_clip_s"] >= required, (
        f"min_clip_s={s['min_clip_s']} < {required} required. Every clip would "
        f"be skipped by the HLD rule and the corpus would be empty."
    )
    assert 300 < required, "a 5-minute (300 s) clip must NOT satisfy the requirement"


def test_sequences_per_hour_is_what_the_documents_claim(spec):
    s = spec["sequence"]
    required = (s["T"] - 1) * s["step_s"] + s["horizon_s"]
    per_hour = (3600 - required) // s["stride_s"] + 1

    assert per_hour == 109, (
        f"Documents claim ~110 sequences per continuous hour; formula gives "
        f"{per_hour}. If this fails, either the claim or a constant is wrong."
    )


# --------------------------------------------------------------------------
# Congestion labelling
# --------------------------------------------------------------------------

def test_congestion_thresholds_are_ordered_and_gapless(spec):
    c = spec["congestion"]
    assert c["low_max"] < c["med_max"], "thresholds out of order"
    # LOW <5, MED 5..15, HIGH >15 -- no count may be unclassifiable
    for n in range(0, 40):
        cls = 0 if n <= c["low_max"] else (1 if n <= c["med_max"] else 2)
        assert cls in (0, 1, 2)


def test_class_names_use_the_canonical_spelling(spec):
    """TRIAGE-001 D1: PRD §17.1 emits 'MED' while §14.1 defines 'MEDIUM'."""
    assert spec["congestion"]["classes"] == ["LOW", "MEDIUM", "HIGH"]


# --------------------------------------------------------------------------
# PPO state contract -- PRD §13.1 as amended by A16
# --------------------------------------------------------------------------

def test_state_index_map_is_dense_and_matches_declared_dim(spec):
    st = spec["ppo_state"]
    indices = sorted(st["index_map"].values())

    assert indices == list(range(st["dim"])), (
        "index_map must cover 0..dim-1 exactly once -- no gaps, no duplicates. "
        "A gap means a dead input; a duplicate means two fields overwrite."
    )


def test_gate_mean_is_absent_from_the_state(spec):
    """A16 removed it: no SUMO analogue, so it would be a constant dead input."""
    assert "mfst_gate_mean" not in spec["ppo_state"]["index_map"]
    assert spec["ppo_state"]["dim"] == 16


def test_mfstnet_fields_zeroed_on_unavailability_are_exactly_the_prediction_slots(spec):
    st = spec["ppo_state"]
    expected = [st["index_map"][f"mfst_pred_{l}"] for l in spec["lanes"]]

    assert sorted(st["zero_when_mfstnet_unavailable"]) == sorted(expected), (
        "FR-A06 zeroes the MFSTNet slots and nothing else. Shortening the "
        "vector instead would invalidate every trained checkpoint."
    )


def test_prediction_normaliser_maps_classes_into_unit_range(spec):
    div = spec["ppo_state"]["normalisers"]["mfst_pred_divisor"]
    n_classes = len(spec["congestion"]["classes"])

    assert div == n_classes - 1, (
        f"divisor {div} should be n_classes-1 = {n_classes - 1} so the highest "
        f"class maps to 1.0"
    )


# --------------------------------------------------------------------------
# Signal safety invariants -- FR-A03, FR-A04, FR-R04
# --------------------------------------------------------------------------

def test_action_space_durations_lie_within_green_bounds(spec):
    sig = spec["signal"]
    for d in sig["green_durations_s"]:
        assert sig["min_green_s"] <= d <= sig["max_green_s"], (
            f"action duration {d}s violates FR-A03 bounds "
            f"[{sig['min_green_s']}, {sig['max_green_s']}] -- the policy could "
            f"emit a command the actuation layer must reject"
        )


def test_action_space_size_is_twelve(spec):
    sig = spec["signal"]
    assert len(sig["phases"]) * len(sig["green_durations_s"]) == 12, "FR-R03"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN CONTRADICTION, pending item P6. FR-R04 penalises a lane waiting "
        ">180s, but FR-A03 (max green 90s) and FR-A04 (all-red 3s) permit a "
        "worst-case cycle of 2*(90+3) = 186s. A policy that legally grants NS "
        "then EW maximum green is penalised for starvation while fully "
        "compliant. Either the threshold rises above 186s or the 180s figure is "
        "declared deliberate soft pressure against max-green stacking -- both "
        "are defensible, neither is currently written down. Remove this marker "
        "when the PRD records the decision."
    ),
)
def test_starvation_bound_exceeds_a_full_worst_case_cycle(spec):
    """A starvation limit shorter than one legal cycle penalises legal operation."""
    sig = spec["signal"]
    worst_cycle = len(sig["phases"]) * (sig["max_green_s"] + sig["all_red_s"])

    assert sig["starvation_s"] > worst_cycle, (
        f"starvation limit {sig['starvation_s']}s <= worst-case cycle "
        f"{worst_cycle}s -- FR-R04 would penalise legal operation"
    )


# --------------------------------------------------------------------------
# Splits
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["detection", "mfstnet"])
def test_splits_sum_to_one(spec, name):
    assert abs(sum(spec["splits"][name]) - 1.0) < 1e-9


def test_detection_and_mfstnet_splits_are_deliberately_different(spec):
    """FR-D05 is 70/15/15; PRD §8.4 is 60/20/20. Different numbers, different
    units (frames vs source clips), different purposes. Asserting the difference
    stops a well-meaning tidy-up from unifying them."""
    assert spec["splits"]["detection"] != spec["splits"]["mfstnet"]
