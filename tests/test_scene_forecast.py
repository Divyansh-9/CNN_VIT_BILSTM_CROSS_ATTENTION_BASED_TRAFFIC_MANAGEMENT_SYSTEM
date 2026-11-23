import pytest

from scripts.scene_forecast import SceneForecast


def observations(counts):
    estimator = SceneForecast()
    return [estimator.observe(2 * i, count) for i, count in enumerate(counts)]


def test_forecast_is_causal_and_error_matures_after_the_full_window():
    quiet = [2] * 15
    busy = [6] * 15
    normal = observations(quiet + busy)
    assert normal[:14] == [{}] * 14
    assert normal[14]["30"] == {"mean": 2, "checks": 0, "mae": None, "range": None}
    assert normal[28]["30"]["checks"] == 0
    assert normal[29]["30"] == {"mean": 6, "checks": 1, "mae": 4, "range": None}
    changed = observations(quiet + [200] * 15)
    assert normal[14] == changed[14]


def test_long_horizons_wait_for_comparisons_and_reset_after_a_feed_gap():
    result = observations([7] * 1200)
    assert "300" not in result[598]
    assert result[599]["300"]["checks"] == 3
    assert "600" not in result[1198]
    assert result[1199]["600"]["mean"] == 7
    assert result[1199]["30"]["range"] == [7, 7]
    estimator = SceneForecast()
    for i in range(15):
        estimate = estimator.observe(2 * i, 3)
    assert estimate["30"]["mean"] == 3
    assert estimator.observe(32, 3) == {}


@pytest.mark.parametrize("horizon,window", [("30", 15), ("60", 30), ("300", 150), ("600", 300)])
def test_uncertainty_is_withheld_until_five_non_overlapping_checks(horizon, window):
    estimates = observations([3] * window * 6)
    assert estimates[window * 6 - 2][horizon]["range"] is None
    assert estimates[-1][horizon]["range"] == [3, 3]
