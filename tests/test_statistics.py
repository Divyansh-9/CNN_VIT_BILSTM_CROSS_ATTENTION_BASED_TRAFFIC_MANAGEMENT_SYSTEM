"""Tests for the benchmark statistics (S38, NFR-10, FR-R07).

Pure standard library, so these run in the fast CI job. That matters: these
functions decide whether "PPO beats Webster by 10%" is a finding or a
coincidence, and a statistics bug is invisible — it produces a number of exactly
the right shape.

The t-distribution is implemented here rather than pulled from SciPy, so it is
checked against **published critical values**, not against itself.

    python -m pytest tests/test_statistics.py -q
"""

from __future__ import annotations

import pytest

from experiments.statistics import (
    Comparison,
    bootstrap_ci,
    cohens_d_paired,
    compare,
    paired_t_test,
)
from experiments.statistics import _t_sf


# ------------------------------------------- the t distribution is correct --

@pytest.mark.parametrize(
    "t, df, expected_p",
    [
        (2.262, 9, 0.05),        # published two-tailed critical values
        (2.086, 20, 0.05),
        (2.045, 29, 0.05),       # df=29 is the 30-seed benchmark
        (3.250, 9, 0.01),
        (2.756, 29, 0.01),
    ],
)
def test_t_distribution_matches_published_critical_values(t, df, expected_p):
    """An approximation nobody verifies is worse than no approximation, because
    it produces a plausible number instead of an error."""
    assert 2 * _t_sf(t, df) == pytest.approx(expected_p, abs=0.001)


def test_a_large_t_is_vanishingly_improbable():
    assert 2 * _t_sf(10.0, 29) < 1e-9


def test_zero_t_is_certain():
    assert 2 * _t_sf(0.0, 29) == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------- the paired t test --

def test_paired_t_matches_a_hand_computed_value():
    """differences = [10,10,5,10,5,10,5,5,10,5]; mean 7.5, sd 2.6352,
    se 0.8333, t = 9.0 exactly."""
    a = [200, 210, 190, 205, 195, 215, 185, 200, 210, 190]
    b = [190, 200, 185, 195, 190, 205, 180, 195, 200, 185]
    t, p = paired_t_test(a, b)

    assert t == pytest.approx(9.0, abs=1e-6)
    assert p < 0.0001


def test_identical_samples_are_not_significant():
    values = [1.0, 2.0, 3.0, 4.0]
    t, p = paired_t_test(values, values)
    assert t == 0.0 and p == 1.0


def test_unequal_lengths_raise_rather_than_truncate():
    """Truncating would silently pair seed 7 against seed 8 and report a
    confident answer to a question nobody asked."""
    with pytest.raises(ValueError, match="do not truncate"):
        paired_t_test([1, 2, 3], [1, 2])


def test_pairing_is_what_makes_the_test_powerful():
    """Same difference, huge between-seed spread. Paired, it is obvious; the
    spread would swamp an unpaired comparison. This is why the benchmark runs
    every method on the same seeds."""
    a = [10, 110, 210, 310, 410]
    b = [12, 112, 212, 312, 412]

    t, p = paired_t_test(a, b)
    assert p < 0.001, "a consistent 2-unit difference must be detectable"


# ------------------------------------------------------------- effect size --

def test_cohens_d_uses_the_sd_of_differences():
    """The pooled-SD form is the UNPAIRED statistic and understates an effect a
    paired design actually achieved."""
    a = [10, 110, 210, 310, 410]
    b = [12, 112, 212, 312, 412]

    # differences are all exactly -2, so their SD is 0 -> guarded, not infinite
    assert cohens_d_paired(a, b) == 0.0

    noisy_b = [12, 112, 213, 312, 411]
    assert abs(cohens_d_paired(a, noisy_b)) > 1.0


# -------------------------------------------------------------- bootstrap --

def test_bootstrap_ci_brackets_the_mean():
    values = [10.0, 12.0, 11.0, 13.0, 9.0, 11.5, 10.5, 12.5]
    mean, low, high = bootstrap_ci(values, resamples=2000)

    assert low < mean < high
    assert mean == pytest.approx(sum(values) / len(values))


def test_bootstrap_is_deterministic():
    """A confidence interval that moves between runs of the same data is not
    reportable (NFR-07)."""
    values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
    assert bootstrap_ci(values, resamples=1000) == bootstrap_ci(values, resamples=1000)


def test_bootstrap_narrows_as_the_sample_grows():
    small = bootstrap_ci([1.0, 2.0, 3.0, 4.0] * 2, resamples=2000)
    large = bootstrap_ci([1.0, 2.0, 3.0, 4.0] * 20, resamples=2000)
    assert (large[2] - large[1]) < (small[2] - small[1])


def test_an_empty_sample_raises():
    with pytest.raises(ValueError, match="empty sample"):
        bootstrap_ci([])


# ---------------------------------------------------------------- compare --

def test_compare_pairs_by_seed_not_by_position():
    """Two lists can be misaligned by one dropped run and nothing complains.
    Dicts keyed by seed make that impossible."""
    a = {0: 10.0, 1: 20.0, 2: 30.0}
    b = {2: 31.0, 0: 11.0, 1: 21.0}          # deliberately out of order

    result = compare(a, b, name_a="A", name_b="B")
    assert result.n_pairs == 3
    assert result.mean_difference == pytest.approx(-1.0, abs=0.2)


def test_compare_excludes_unpaired_seeds_and_says_so():
    a = {0: 10.0, 1: 20.0, 2: 30.0}
    b = {0: 11.0, 1: 21.0}

    result = compare(a, b, name_a="A", name_b="B")
    assert result.n_pairs == 2
    assert any("unpaired" in note for note in result.notes)


def test_compare_warns_below_thirty_seeds():
    """FR-R07 specifies 30. Fewer is allowed for a quick check but must never
    reach a report unlabelled."""
    a = {i: float(i) for i in range(5)}
    b = {i: float(i) + 1 for i in range(5)}

    assert any("FR-R07" in note for note in compare(a, b, name_a="A", name_b="B").notes)


def test_no_shared_seeds_raises():
    with pytest.raises(ValueError, match="share no seeds"):
        compare({0: 1.0}, {5: 1.0}, name_a="A", name_b="B")


def test_improvement_percent_is_signed_so_lower_is_better():
    """For wait time, lower is better — a positive percentage must mean A won."""
    a = {i: 10.0 for i in range(30)}
    b = {i: 20.0 for i in range(30)}

    result = compare(a, b, name_a="A", name_b="B")
    assert result.improvement_percent == pytest.approx(50.0)


def test_significance_respects_alpha():
    comparison = Comparison(
        method_a="A", method_b="B", n_pairs=30, mean_a=1, mean_b=2,
        ci_a=(0, 2), ci_b=(1, 3), mean_difference=-1, ci_difference=(-2, 0),
        t=-2.0, p=0.04, cohens_d=-0.5,
    )
    assert comparison.significant
    assert not Comparison(**{**comparison.__dict__, "p": 0.06}).significant


# ----------------------------- gaps found by mutation testing (S38b) --

def test_paired_t_p_is_two_tailed_and_uses_n_minus_one_df():
    """Two mutations slipped past the original suite: returning a ONE-tailed p
    (halving it, so p=0.06 reads as 0.03), and using df=n instead of n-1.

    Both were missed because the only p assertion was a loose `p < 0.0001`.
    Tying p exactly to the separately-verified `_t_sf` at the correct df closes
    both at once.
    """
    a = [200, 210, 190, 205, 195, 215, 185, 200, 210, 190]
    b = [190, 200, 185, 195, 190, 205, 180, 195, 200, 185]

    t, p = paired_t_test(a, b)
    assert p == pytest.approx(2 * _t_sf(abs(t), len(a) - 1), rel=1e-9)
    assert p == pytest.approx(2 * _t_sf(9.0, 9), rel=1e-9)


def test_a_borderline_result_lands_on_the_right_side_of_alpha():
    """The case that actually matters. With a one-tailed p this sample would be
    reported as significant and it is not."""
    a = [10.0, 11.0, 9.0, 12.0, 8.0, 10.5, 9.5, 11.5, 8.5, 12.5]
    b = [9.0, 10.5, 8.0, 11.8, 7.0, 10.0, 9.0, 10.8, 8.0, 11.0]

    t, p = paired_t_test(a, b)
    assert p == pytest.approx(2 * _t_sf(abs(t), 9), rel=1e-9), (
        "p must be two-tailed at df = n-1; a one-tailed p makes borderline "
        "results look significant"
    )


def test_bootstrap_bounds_are_percentiles_not_extremes():
    """`low = means[0]` — the minimum resample mean rather than the 2.5th
    percentile — passed every original bootstrap test, because the minimum is
    still below the mean and the interval still narrows with n.

    For a reasonably sized sample the 95% percentile interval should sit close
    to mean +/- 1.96 * SE. The minimum of 10,000 resample means does not.
    """
    import math

    values = [10.0, 12.0, 11.0, 13.0, 9.0, 11.5, 10.5, 12.5,
              9.5, 13.5, 10.2, 11.8, 12.2, 9.8, 10.8, 11.2]
    mean, low, high = bootstrap_ci(values, resamples=4000)

    n = len(values)
    sample_mean = sum(values) / n
    sd = math.sqrt(sum((v - sample_mean) ** 2 for v in values) / (n - 1))
    expected_half_width = 1.96 * sd / math.sqrt(n)

    half_width = (high - low) / 2
    assert half_width == pytest.approx(expected_half_width, rel=0.25), (
        f"CI half-width {half_width:.4f} is not near the standard-error "
        f"prediction {expected_half_width:.4f} — the bounds are probably "
        f"extremes rather than percentiles"
    )


def test_bootstrap_low_bound_is_above_the_minimum_resample():
    """Direct statement of the same property, cheap to read."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    _, low, high = bootstrap_ci(values, resamples=4000)
    assert low > min(values), "a 2.5th-percentile bound cannot reach the data minimum"
    assert high < max(values)
