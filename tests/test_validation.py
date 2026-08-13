"""Tests for the corpus validation gates (PLAN-01 WI-14).

    python -m pytest tests/test_validation.py -q
"""

from __future__ import annotations

import pytest

from mfstnet.corpus.validation import (
    CorpusValidationError,
    SequenceRecord,
    Severity,
    check_class_distribution,
    check_effective_sample_size,
    check_split_disjoint,
    check_test_split_verified,
    check_transition_rate,
    check_unassigned_rate,
    validate_corpus,
)


def rec(
    seq_id: str,
    clip_id: str,
    split: str,
    labels: tuple[int, ...],
    labels_now: tuple[int, ...] | None = None,
    origin: str = "verified",
) -> SequenceRecord:
    return SequenceRecord(
        seq_id=seq_id,
        clip_id=clip_id,
        split=split,
        labels=labels,
        labels_now=labels_now if labels_now is not None else labels,
        label_origin=origin,
    )


def healthy_corpus() -> list[SequenceRecord]:
    """Balanced classes, plenty of transitions, 12 test clips, no leakage."""
    out: list[SequenceRecord] = []
    for i in range(60):
        split = "train" if i < 36 else ("val" if i < 48 else "test")
        a, b = i % 3, (i + 1) % 3          # every window transitions
        out.append(rec(f"s{i}", f"clip{i}", split, (a, b, a, b), (b, a, b, a)))
    return out


# ------------------------------------------------------ class distribution --

def test_a_balanced_corpus_passes():
    g = check_class_distribution(healthy_corpus())
    assert g.passed
    assert "LOW" in g.detail and "%" in g.detail, "the histogram is part of the output"


def test_a_rare_class_blocks_and_prints_the_histogram():
    """The fix is usually a threshold change (P1), so whoever decides needs the
    shape of the data, not just a verdict."""
    records = [rec(f"s{i}", f"c{i}", "train", (0, 0, 0, 0)) for i in range(50)]
    records.append(rec("rare", "cr", "train", (0, 0, 0, 2)))

    g = check_class_distribution(records)
    assert not g.passed
    assert g.severity is Severity.BLOCKING
    assert "MEDIUM" in g.detail and "HIGH" in g.detail
    assert "P1" in g.detail, "must point at the recalibration item"


def test_an_empty_corpus_blocks():
    assert not check_class_distribution([]).passed


# ---------------------------------------------------------- transition rate --

def test_a_corpus_that_never_transitions_blocks():
    """PRD A17 — the check that can invalidate the entire task design.

    Perfect class balance, and still unusable: every window's answer equals the
    answer now, so a last-value baseline scores 100% and nothing can be ranked.
    """
    records = [
        rec(f"s{i}", f"c{i}", "train", (i % 3, i % 3, i % 3, i % 3))
        for i in range(60)
    ]
    assert check_class_distribution(records).passed, "classes ARE balanced"

    g = check_transition_rate(records)
    assert not g.passed
    assert g.severity is Severity.BLOCKING
    assert "last-value baseline" in g.detail
    assert "~100%" in g.detail


def test_a_corpus_with_transitions_passes():
    g = check_transition_rate(healthy_corpus())
    assert g.passed
    assert "change class" in g.detail


def test_the_transition_threshold_is_a_parameter():
    records = [rec(f"s{i}", f"c{i}", "train", (0, 0, 0, 0), (0, 0, 0, 1)) for i in range(10)]
    assert check_transition_rate(records, min_rate=0.20).passed        # 25% > 20%
    assert not check_transition_rate(records, min_rate=0.30).passed    # 25% < 30%


# ------------------------------------------------------------- leakage --

def test_clean_splits_pass():
    assert check_split_disjoint(healthy_corpus()).passed


def test_a_straddling_clip_blocks():
    """Inflates a metric rather than breaking a run — which is exactly why it
    must block rather than warn."""
    records = [
        rec("a", "shared", "train", (0, 0, 0, 0)),
        rec("b", "shared", "test", (1, 1, 1, 1)),
    ]
    g = check_split_disjoint(records)
    assert not g.passed
    assert g.severity is Severity.BLOCKING
    assert "shared" in g.detail


# ------------------------------------------------------ verified test split --

def test_an_auto_labelled_test_split_blocks():
    records = healthy_corpus()
    records[-1] = rec(records[-1].seq_id, records[-1].clip_id, "test", (0, 1, 0, 1),
                      (1, 0, 1, 0), origin="auto")
    g = check_test_split_verified(records)
    assert not g.passed
    assert "AGAINST MFSTNet" in g.detail, "must say which way the bias runs"


def test_a_verified_test_split_passes():
    assert check_test_split_verified(healthy_corpus()).passed


def test_an_empty_test_split_blocks():
    records = [rec(f"s{i}", f"c{i}", "train", (0, 1, 2, 0)) for i in range(9)]
    assert not check_test_split_verified(records).passed


# ------------------------------------------------------- effective sample n --

def test_a_thin_test_split_advises_rather_than_blocks():
    """PRD A19. Does not make results wrong — makes intervals look tighter than
    the evidence supports. Advisory, and reported beside the results."""
    records = [rec(f"s{i}", f"c{i % 3}", "test", (0, 1, 2, 0)) for i in range(500)]
    g = check_effective_sample_size(records)

    assert not g.passed
    assert g.severity is Severity.ADVISORY, "must not block"
    assert "3 clip" in g.detail
    assert "however many sequences" in g.detail


def test_enough_clips_passes():
    assert check_effective_sample_size(healthy_corpus()).passed


# --------------------------------------------------------- unassigned rate --

def test_a_high_unassigned_rate_advises():
    g = check_unassigned_rate({"good": 0.02, "bad": 0.40})
    assert not g.passed
    assert g.severity is Severity.ADVISORY
    assert "bad 40.0%" in g.detail
    assert "polygons" in g.detail


def test_low_unassigned_rates_pass():
    assert check_unassigned_rate({"a": 0.01, "b": 0.03}).passed


def test_not_measured_is_not_a_failure():
    assert check_unassigned_rate({}).passed


# ------------------------------------------------------------ orchestration --

def test_a_healthy_corpus_produces_no_blocking_failures():
    report = validate_corpus(healthy_corpus(), {"clip0": 0.02})
    assert report.ok
    report.raise_if_blocking()


def test_blocking_failures_raise_with_every_reason_named():
    """One exception listing all of them — not the first one found. Fixing them
    one round-trip at a time is how a morning disappears."""
    records = [rec(f"s{i}", "one_clip", "train", (0, 0, 0, 0)) for i in range(20)]
    records.append(rec("x", "one_clip", "test", (0, 0, 0, 0), origin="auto"))

    report = validate_corpus(records)
    assert not report.ok

    with pytest.raises(CorpusValidationError) as exc:
        report.raise_if_blocking()

    message = str(exc.value)
    assert "class_distribution" in message
    assert "transition_rate" in message
    assert "split_disjoint" in message


def test_advisories_do_not_block():
    records = [rec(f"s{i}", f"c{i % 2}", "test", (0, 1, 2, 0), (1, 2, 0, 1))
               for i in range(30)]
    records += [rec(f"t{i}", f"d{i}", "train", (0, 1, 2, 0), (1, 2, 0, 1))
                for i in range(30)]

    report = validate_corpus(records, {"c0": 0.9})
    assert report.ok, "advisories alone must never block"
    assert len(report.advisories) >= 2
    report.raise_if_blocking()


def test_the_report_renders_every_gate():
    text = str(validate_corpus(healthy_corpus()))
    for name in ("class_distribution", "transition_rate", "split_disjoint",
                 "effective_sample_size", "split_balance", "test_split_verified"):
        assert name in text


def test_verification_can_be_waived_only_explicitly():
    records = [rec(f"s{i}", f"c{i}", "train" if i < 40 else "test",
                   (0, 1, 2, 0), (1, 2, 0, 1), origin="auto") for i in range(60)]

    assert not validate_corpus(records).ok
    assert validate_corpus(records, require_verified_test=False).ok


# ------------------------------------------------------------ record shape --

def test_a_record_rejects_mismatched_label_lengths():
    with pytest.raises(ValueError, match="differ in length"):
        SequenceRecord("s", "c", "train", (0, 1), (0, 1, 2))


def test_a_record_rejects_an_unknown_split():
    with pytest.raises(ValueError, match="unknown split"):
        SequenceRecord("s", "c", "holdout", (0,), (0,))


def test_transitions_counts_per_lane():
    r = rec("s", "c", "train", (0, 1, 2, 0), (0, 2, 2, 1))
    assert r.transitions == 2
