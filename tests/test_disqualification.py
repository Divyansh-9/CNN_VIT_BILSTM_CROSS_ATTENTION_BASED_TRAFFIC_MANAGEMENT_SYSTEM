"""ADR-012's disqualifications must apply where the headline is produced.

The rules were written after the Webster sweep produced two results that looked
good and meant nothing: a configuration clamping every decision (not running the
method) and one with the lowest wait in the sweep while completing 55% of trips
(the vehicles that waited longest never finished, so they never entered the
average).

Both checks then lived in `webster_sweep.py` only. The reported comparison —
`benchmark.py` — never applied them, and running the benchmark across three
demand regimes produced exactly the two failures the rules describe:

* at light demand, Webster clamped on **100%** of decisions and every
  saturation flow in the sweep returned an identical 6.55 s, because the
  optimum cycle falls below `min_cycle_s` and `s` only enters through `y = q/s`;
* at oversaturation, **all three** controllers completed 80-83% of trips.

These tests pin the rules to the place the numbers are reported from.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark import validate
from simulation.webster import (
    MAX_CLAMP_RATE,
    MIN_ARRIVED_FRACTION,
    disqualification,
)


def run(method: str, *, arrived: float = 0.95, clamp: float | None = None,
        seed: int = 0, wait: float = 20.0) -> dict:
    row = {"method": method, "seed": seed, "mean_wait_s": wait,
           "arrived_fraction": arrived, "regime": "saturated"}
    if clamp is not None:
        row["clamp_rate"] = clamp
    return row


def test_a_clean_row_is_not_disqualified():
    assert disqualification({"arrived_fraction": 0.95, "clamp_rate": 0.40}) is None


def test_full_clamp_is_disqualified():
    """The measured light-regime Webster arm."""
    reason = disqualification({"arrived_fraction": 0.959, "clamp_rate": 1.0})
    assert reason is not None and "clamp rate" in reason


def test_clamp_threshold_is_exclusive_at_the_boundary():
    """Exactly at the limit is allowed; the rule is 'more than half'."""
    assert disqualification({"arrived_fraction": 0.95,
                             "clamp_rate": MAX_CLAMP_RATE}) is None
    assert disqualification({"arrived_fraction": 0.95,
                             "clamp_rate": MAX_CLAMP_RATE + 0.01}) is not None


def test_low_completion_is_disqualified():
    """The measured oversaturated rows, all three of them."""
    reason = disqualification({"arrived_fraction": 0.797})
    assert reason is not None and "completed" in reason


def test_completion_threshold_is_inclusive_at_the_boundary():
    assert disqualification({"arrived_fraction": MIN_ARRIVED_FRACTION}) is None
    assert disqualification({"arrived_fraction": MIN_ARRIVED_FRACTION - 0.01}) is not None


def test_a_controller_without_clamp_rate_is_not_rejected_for_clamping():
    """`fixed` and `longest_queue` report no clamp rate. Treating a missing
    value as zero would be harmless here but wrong in principle; treating it as
    a failure would void every classical baseline."""
    assert disqualification({"arrived_fraction": 0.95}) is None
    assert disqualification({"arrived_fraction": 0.95, "clamp_rate": ""}) is None


def test_clamp_is_reported_before_completion_when_both_fail():
    """A fully-clamped controller is not running its method at all, which is the
    more fundamental objection — the mean wait is not merely biased, it is a
    measurement of a different controller."""
    reason = disqualification({"arrived_fraction": 0.50, "clamp_rate": 1.0})
    assert "clamp rate" in reason


def test_validate_aggregates_over_seeds_not_per_run():
    """One unlucky seed must not void a method, and a method that clamps on
    average must not be rescued by one seed that did not — the comparison is
    reported over seeds, so the verdict is taken over seeds."""
    rows = [run("webster", clamp=0.0, seed=0)] + [
        run("webster", clamp=1.0, seed=s) for s in range(1, 10)]
    assert validate(rows)["webster"], "mean clamp 0.90 must disqualify"

    rows = [run("webster", clamp=1.0, seed=0)] + [
        run("webster", clamp=0.0, seed=s) for s in range(1, 10)]
    assert not validate(rows)["webster"], "mean clamp 0.10 must not disqualify"


def test_validate_returns_empty_string_for_citable_methods():
    """Empty rather than None, so the value writes into a CSV cell as blank."""
    verdicts = validate([run("fixed", arrived=0.93, seed=s) for s in range(5)])
    assert verdicts == {"fixed": ""}


def test_validate_covers_every_method_present():
    rows = ([run("fixed", arrived=0.79, seed=s) for s in range(3)]
            + [run("webster", arrived=0.95, clamp=0.30, seed=s) for s in range(3)])
    verdicts = validate(rows)
    assert set(verdicts) == {"fixed", "webster"}
    assert verdicts["fixed"] and not verdicts["webster"]
