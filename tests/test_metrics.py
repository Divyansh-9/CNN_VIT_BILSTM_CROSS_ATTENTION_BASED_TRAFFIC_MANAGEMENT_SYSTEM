"""Tests for classification metrics (PRD §14.5, amendment A25).

Expected values are hand-computed and written into the test, not produced by
the code under test. A metric suite that verifies itself against its own output
verifies nothing.

    python -m pytest tests/test_metrics.py -q
"""

from __future__ import annotations

import pytest

from mfstnet.metrics import (
    confusion_matrix,
    evaluate,
    format_confusion_matrix,
    off_by_two_rate,
    ordinal_mae,
    quadratic_weighted_kappa,
)

# Worked by hand:
#   y_true = [0,0,1,1,2,2]
#   y_pred = [0,1,1,1,2,0]
#   cm = [[1,1,0],
#         [0,2,0],
#         [1,0,1]]
Y_TRUE = [0, 0, 1, 1, 2, 2]
Y_PRED = [0, 1, 1, 1, 2, 0]
CM = [[1, 1, 0], [0, 2, 0], [1, 0, 1]]


def test_confusion_matrix_rows_are_truth_columns_are_prediction():
    """ADR-009 reads row t as 'what the model predicts when the truth is t'.
    Transposing this silently inverts the PPO surrogate's noise model."""
    assert confusion_matrix(Y_TRUE, Y_PRED) == CM
    assert CM[2][0] == 1, "one HIGH was predicted LOW"
    assert CM[0][2] == 0, "no LOW was predicted HIGH"


def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError, match="length mismatch"):
        confusion_matrix([0, 1], [0])


def test_out_of_range_label_is_rejected():
    with pytest.raises(ValueError, match="out of range"):
        confusion_matrix([0, 3], [0, 0])


@pytest.mark.parametrize(
    "index, precision, recall, f1",
    [
        (0, 0.5, 0.5, 0.5),                 # LOW    tp1 fp1 fn1
        (1, 2 / 3, 1.0, 0.8),               # MEDIUM tp2 fp1 fn0
        (2, 1.0, 0.5, 2 / 3),               # HIGH   tp1 fp0 fn1
    ],
)
def test_per_class_figures(index, precision, recall, f1):
    m = evaluate(Y_TRUE, Y_PRED).per_class[index]
    assert m.precision == pytest.approx(precision)
    assert m.recall == pytest.approx(recall)
    assert m.f1 == pytest.approx(f1)
    assert m.support == 2


def test_aggregate_figures():
    r = evaluate(Y_TRUE, Y_PRED)
    assert r.accuracy == pytest.approx(4 / 6)
    assert r.macro_f1 == pytest.approx((0.5 + 0.8 + 2 / 3) / 3)
    assert r.weighted_f1 == pytest.approx(r.macro_f1), "equal support: the two coincide"
    assert r.n == 6


# ------------------------------------------------ ordinal-aware metrics --

def test_ordinal_mae_counts_distance_not_just_wrongness():
    """0 + 1 + 0 + 0 + 0 + 2 = 3 over 6 samples."""
    assert ordinal_mae(CM) == pytest.approx(0.5)


def test_ordinal_mae_separates_a_two_step_error_from_a_one_step_error():
    """The whole reason this metric exists. Both cases have accuracy 0.5."""
    one_step = confusion_matrix([0, 0], [0, 1])
    two_step = confusion_matrix([0, 0], [0, 2])
    assert ordinal_mae(one_step) == pytest.approx(0.5)
    assert ordinal_mae(two_step) == pytest.approx(1.0)

    from mfstnet.metrics import accuracy
    assert accuracy(one_step) == accuracy(two_step), "accuracy cannot tell them apart"


def test_off_by_two_rate():
    assert off_by_two_rate(CM) == pytest.approx(1 / 6)
    assert off_by_two_rate(confusion_matrix([0, 1], [0, 1])) == 0.0


def test_quadratic_weighted_kappa():
    assert quadratic_weighted_kappa(CM) == pytest.approx(1 - 1.25 / 1.75)


def test_perfect_prediction_scores_one_everywhere():
    r = evaluate([0, 1, 2, 0, 1, 2], [0, 1, 2, 0, 1, 2])
    assert r.accuracy == 1.0
    assert r.macro_f1 == pytest.approx(1.0)
    assert r.qwk == pytest.approx(1.0)
    assert r.ordinal_mae == 0.0
    assert r.off_by_two_rate == 0.0
    assert r.warnings == []


# ------------------------------------------------------ support guards --

def test_a_rare_class_raises_a_warning_rather_than_a_flattering_number():
    """The distribution-gate signal (A17). A model that always predicts LOW on a
    95/4/1 split scores 0.95 accuracy — the macro F1 is what exposes it."""
    r = evaluate([0] * 95 + [1] * 4 + [2] * 1, [0] * 100)

    assert r.accuracy == pytest.approx(0.95)
    assert r.macro_f1 < 0.4, "macro F1 must not be flattered by the majority class"
    assert len(r.warnings) == 2, "both MEDIUM and HIGH are below the 5% gate"
    assert any("MEDIUM" in w for w in r.warnings)
    assert any("HIGH" in w for w in r.warnings)


def test_an_absent_class_is_called_out_explicitly():
    r = evaluate([0, 0, 1, 1], [0, 0, 1, 1])
    assert any("NO samples" in w and "HIGH" in w for w in r.warnings)


def test_support_is_reported_beside_every_class():
    """FR-D08 requires this for detection; A25 extends it here. A figure without
    its sample count cannot be interpreted."""
    r = evaluate([0] * 10 + [1] * 3 + [2] * 87, [0] * 100)
    assert [m.support for m in r.per_class] == [10, 3, 87]


# ------------------------------------------------------------- outputs --

def test_csv_row_carries_every_confusion_cell():
    """ADR-009 needs the full matrix from the committed CSV, not a summary."""
    row = evaluate(Y_TRUE, Y_PRED).as_row()
    cells = [k for k in row if k.startswith("cm_")]
    assert len(cells) == 9
    assert row["cm_high_as_low"] == 1
    assert row["cm_low_as_high"] == 0
    assert "support_high" in row


def test_formatted_matrix_labels_its_axes():
    """Direction is the point. A matrix without axis labels gets transposed."""
    text = format_confusion_matrix(CM)
    assert "predicted" in text
    assert "true" in text
    assert "MEDIUM" in text


def test_empty_input_is_rejected_rather_than_returning_zero():
    with pytest.raises(ValueError, match="no samples"):
        evaluate([], [])
