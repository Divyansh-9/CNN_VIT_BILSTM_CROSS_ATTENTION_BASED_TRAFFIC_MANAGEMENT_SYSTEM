"""Cross-check the hand-rolled metrics against scikit-learn and SciPy.

`mfstnet/metrics.py` and `experiments/statistics.py` are pure standard library
by deliberate choice, and that choice is defensible: the arithmetic is auditable
line by line and runs before the environment exists.

But it carries a risk the choice does not remove. Macro F1, quadratic weighted
kappa, the paired t-test and Cohen's d are **graded reported numbers**
(FR-M11, FR-R07, FR-R08). A hand-rolled statistic that nobody checks against a
reference is a number the whole results section rests on and nothing validates.
`_t_sf`'s own docstring says as much: "an approximation nobody verifies is worse
than none."

So this module verifies it. Reference implementations are compared on random
inputs including the degenerate shapes — a class that never appears, perfect
agreement, total disagreement — because those are where a bespoke implementation
and a library implementation part company.

These tests SKIP rather than fail when scikit-learn or SciPy is absent, since
the production path must not acquire the dependency. Both are pinned in
requirements.txt, so CI runs them.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.statistics import cohens_d_paired, paired_t_test
from mfstnet.metrics import confusion_matrix, evaluate

sklearn_metrics = pytest.importorskip("sklearn.metrics")
scipy_stats = pytest.importorskip("scipy.stats")

LABELS = ("LOW", "MEDIUM", "HIGH")
CLASS_IDS = [0, 1, 2]


def samples(seed: int, n: int = 120, classes: int = 3):
    """Random truth/prediction pairs. Correlated, so the metrics are non-trivial."""
    rng = random.Random(seed)
    y_true = [rng.randrange(classes) for _ in range(n)]
    # 60% agreement — neither perfect nor chance, so every cell gets mass.
    y_pred = [t if rng.random() < 0.6 else rng.randrange(classes) for t in y_true]
    return y_true, y_pred


@pytest.mark.parametrize("seed", range(8))
def test_confusion_matrix_matches_sklearn(seed):
    y_true, y_pred = samples(seed)
    mine = confusion_matrix(y_true, y_pred, 3)
    theirs = sklearn_metrics.confusion_matrix(y_true, y_pred, labels=CLASS_IDS)
    assert mine == theirs.tolist(), "row=truth column=prediction convention broken"


@pytest.mark.parametrize("seed", range(8))
def test_macro_and_weighted_f1_match_sklearn(seed):
    y_true, y_pred = samples(seed)
    report = evaluate(y_true, y_pred, LABELS)

    assert report.macro_f1 == pytest.approx(
        sklearn_metrics.f1_score(y_true, y_pred, labels=CLASS_IDS,
                                 average="macro", zero_division=0), abs=1e-9)
    assert report.weighted_f1 == pytest.approx(
        sklearn_metrics.f1_score(y_true, y_pred, labels=CLASS_IDS,
                                 average="weighted", zero_division=0), abs=1e-9)
    assert report.accuracy == pytest.approx(
        sklearn_metrics.accuracy_score(y_true, y_pred), abs=1e-9)


@pytest.mark.parametrize("seed", range(8))
def test_per_class_precision_recall_match_sklearn(seed):
    y_true, y_pred = samples(seed)
    report = evaluate(y_true, y_pred, LABELS)
    precision, recall, f1, support = sklearn_metrics.precision_recall_fscore_support(
        y_true, y_pred, labels=CLASS_IDS, zero_division=0)

    for index, metrics in enumerate(report.per_class):
        assert metrics.precision == pytest.approx(precision[index], abs=1e-9)
        assert metrics.recall == pytest.approx(recall[index], abs=1e-9)
        assert metrics.f1 == pytest.approx(f1[index], abs=1e-9)
        assert metrics.support == support[index]


@pytest.mark.parametrize("seed", range(8))
def test_qwk_matches_sklearn(seed):
    """QWK is the ordinal metric the paper reports; F1 is blind to ordering."""
    y_true, y_pred = samples(seed)
    report = evaluate(y_true, y_pred, LABELS)
    assert report.qwk == pytest.approx(
        sklearn_metrics.cohen_kappa_score(y_true, y_pred, labels=CLASS_IDS,
                                          weights="quadratic"), abs=1e-9)


def test_qwk_on_perfect_and_inverted_agreement():
    """The two ends of the scale, where a bespoke kappa most often goes wrong."""
    perfect = [0, 1, 2] * 20
    assert evaluate(perfect, perfect, LABELS).qwk == pytest.approx(
        sklearn_metrics.cohen_kappa_score(perfect, perfect, labels=CLASS_IDS,
                                          weights="quadratic"), abs=1e-9)

    inverted = [2 - c for c in perfect]
    assert evaluate(perfect, inverted, LABELS).qwk == pytest.approx(
        sklearn_metrics.cohen_kappa_score(perfect, inverted, labels=CLASS_IDS,
                                          weights="quadratic"), abs=1e-9)


def test_metrics_hold_when_a_class_never_appears():
    """HIGH absent from truth AND prediction — the shape a quiet clip produces.

    A real corpus split can contain no HIGH windows at all, so this is not a
    contrived case, and it is exactly where zero-division handling diverges.
    """
    y_true = [0, 0, 1, 1, 0, 1] * 10
    y_pred = [0, 1, 1, 0, 0, 1] * 10
    report = evaluate(y_true, y_pred, LABELS)

    assert report.macro_f1 == pytest.approx(
        sklearn_metrics.f1_score(y_true, y_pred, labels=CLASS_IDS,
                                 average="macro", zero_division=0), abs=1e-9)
    assert any("HIGH" in w for w in report.warnings), "absent class must warn"


@pytest.mark.parametrize("seed", range(8))
def test_paired_t_test_matches_scipy(seed):
    """FR-R07. The p-value decides whether a result is reported as significant."""
    rng = random.Random(seed)
    a = [rng.gauss(30.0, 6.0) for _ in range(30)]
    b = [x + rng.gauss(-2.5, 4.0) for x in a]

    t, p = paired_t_test(a, b)
    reference = scipy_stats.ttest_rel(a, b)

    assert t == pytest.approx(float(reference.statistic), rel=1e-9)
    assert p == pytest.approx(float(reference.pvalue), rel=1e-6), (
        "_t_sf continued fraction disagrees with SciPy — every reported "
        "p-value is affected"
    )


@pytest.mark.parametrize("df", [1, 2, 5, 29, 100])
def test_t_survival_function_matches_scipy_in_the_tails(df):
    """The tails are what alpha=0.05 actually reads, and where a continued
    fraction loses precision first."""
    from experiments.statistics import _t_sf

    for t in (0.5, 1.0, 2.045, 3.0, 6.0, 12.0):
        assert _t_sf(t, df) == pytest.approx(
            float(scipy_stats.t.sf(t, df)), rel=1e-8), f"t={t} df={df}"


@pytest.mark.parametrize("seed", range(5))
def test_cohens_d_paired_matches_manual_definition(seed):
    """Cohen's d for paired data is mean difference over the SD OF DIFFERENCES.

    SciPy has no paired-d function, so the reference here is NumPy applying the
    textbook definition with the same ddof=1 SciPy uses.
    """
    numpy = pytest.importorskip("numpy")
    rng = random.Random(seed)
    a = [rng.gauss(30.0, 6.0) for _ in range(30)]
    b = [x + rng.gauss(-2.5, 4.0) for x in a]

    differences = numpy.array(a) - numpy.array(b)
    expected = differences.mean() / differences.std(ddof=1)
    assert cohens_d_paired(a, b) == pytest.approx(float(expected), rel=1e-9)
