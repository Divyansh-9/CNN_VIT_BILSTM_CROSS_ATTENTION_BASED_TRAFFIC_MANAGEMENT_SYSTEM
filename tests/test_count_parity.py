"""The parity comparison: exact or not at all (P143)."""

from scripts.count_parity import compare

OFF = [(0.0, [2, 1, 3, 2]), (2.0, [3, 2, 2, 1])]


def test_identical_counts_and_timestamps_are_parity():
    result = compare(list(OFF), list(OFF))
    assert result["parity"] is True
    assert (result["exact_lane_values"], result["lane_values"]) == (8, 8)
    assert result["mae_per_lane_value"] == 0.0


def test_one_lane_off_by_one_is_not_parity():
    online = [OFF[0], (2.0, [3, 2, 2, 2])]
    result = compare(online, OFF)
    assert result["parity"] is False
    assert result["exact_lane_values"] == 7
    assert result["exact_samples"] == 1


def test_a_shifted_timestamp_is_not_parity_even_with_equal_counts():
    online = [OFF[0], (4.0, OFF[1][1])]
    result = compare(online, OFF)
    assert result["timestamps_match"] is False
    assert result["parity"] is False


def test_a_missing_or_extra_sample_is_not_parity():
    assert compare(OFF[:1], OFF)["parity"] is False
    assert compare(OFF + [(4.0, [0, 0, 0, 0])], OFF)["parity"] is False


def test_nothing_compared_is_not_parity():
    assert compare([], [])["parity"] is False
