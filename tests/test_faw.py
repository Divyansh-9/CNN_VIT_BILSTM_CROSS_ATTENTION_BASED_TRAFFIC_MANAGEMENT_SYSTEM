"""P132 C0: the forecast-assisted Webster pieces change nothing they should not."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.webster import (EW, EW_APPROACHES, NS, NS_APPROACHES, Webster,  # noqa: E402
                                critical_flow_ratio, optimum_cycle)


def reference_decide(w: Webster, counts: dict):
    """The pre-P132 `decide` arithmetic, verbatim, as the oracle for byte-identity."""
    scale = 3600.0 / w.observation_window_s
    ns = sum(counts[a] for a in NS_APPROACHES) * scale
    ew = sum(counts[a] for a in EW_APPROACHES) * scale
    y_ns = critical_flow_ratio(ns, w.saturation_pcu_per_hour)
    y_ew = critical_flow_ratio(ew, w.saturation_pcu_per_hour)
    total_y = min(0.95, y_ns + y_ew)
    lost = 2 * (w.lost_time_startup_s + w.all_red_s)
    cycle = optimum_cycle(total_y, lost)
    w.decisions += 1
    if cycle == float("inf") or cycle > w.max_cycle_s:
        cycle, w.clamps = float(w.max_cycle_s), w.clamps + 1
    elif cycle < w.min_cycle_s:
        cycle, w.clamps = float(w.min_cycle_s), w.clamps + 1
    eff = max(0.0, cycle - lost)
    w._phase = EW if w._phase == NS else NS
    share = y_ns if w._phase == NS else y_ew
    green = eff * (share / total_y) if total_y > 0 else eff / 2
    return w._phase, int(max(w.min_green_s, min(w.max_green_s, green)))


@pytest.mark.parametrize("s,lost", [(660.0, 4.0), (600.0, 0.0), (1283.0, 4.0)])
def test_default_webster_is_byte_identical_to_the_pre_p132_rule(s, lost):
    rng = random.Random(7)
    new, old = Webster(saturation_flow_per_metre=s, lost_time_startup_s=lost), \
        Webster(saturation_flow_per_metre=s, lost_time_startup_s=lost)
    new.reset()
    old.reset()
    for _ in range(5000):
        counts = {a: rng.randint(0, 60) for a in "NSEW"}
        assert new.decide({"counts": counts}) == reference_decide(old, counts)
    assert (new.clamps, new.decisions) == (old.clamps, old.decisions)


def test_green_for_is_pure_and_matches_decide():
    w = Webster(saturation_flow_per_metre=600.0, lost_time_startup_s=0.0)
    w.reset()
    counts = {"N": 9, "S": 4, "E": 20, "W": 13}
    before = (w.clamps, w.decisions, w._phase)
    green, _ = w.green_for(counts, NS)
    assert (w.clamps, w.decisions, w._phase) == before
    assert w.decide({"counts": counts}) == (NS, green)


def test_a_demand_source_replaces_only_the_counts_read():
    w = Webster(saturation_flow_per_metre=600.0, lost_time_startup_s=0.0,
                demand_source=lambda obs: {"N": 30, "S": 30, "E": 1, "W": 1})
    w.reset()
    phase, green = w.decide({"counts": {a: 0 for a in "NSEW"}})
    assert phase == NS and green == w.green_for({"N": 30, "S": 30, "E": 1, "W": 1}, NS)[0]


def test_the_ridge_adapter_matches_the_edge_forecaster():
    from edge.count_forecast import RidgeCountForecaster
    from simulation.count_forecasts import RIDGE_SPEC, RidgeCountDemand

    rng = random.Random(3)
    demand = RidgeCountDemand()
    edge = RidgeCountForecaster(RIDGE_SPEC, {a: a for a in "NSEW"})
    published = None
    for t in range(0, 200):
        counts = {a: rng.randint(0, 25) for a in "NSEW"}
        demand.observe_second(t, counts)
        if t % 2 == 0 and t <= 118:
            published = edge.step(counts, ts=float(t))
    got = demand({"step": 118, "counts": {a: 0 for a in "NSEW"}})
    assert published is not None
    assert all(abs(got[a] - published.counts[a]) < 1e-3 for a in "NSEW")
    early = demand({"step": 100, "counts": {"N": 7, "S": 1, "E": 2, "W": 3}})
    assert early == {"N": 7, "S": 1, "E": 2, "W": 3}               # not ready: W-now's input


def test_oracle_mean_is_the_next_minute_and_refuses_a_short_record():
    from simulation.count_forecasts import OracleMeanCount

    series = [(t, 0, 0, 0) for t in range(200)]
    got = OracleMeanCount(series)({"step": 10})
    assert got["N"] == pytest.approx(sum(range(11, 71)) / 60) and got["S"] == 0
    with pytest.raises(RuntimeError):
        OracleMeanCount(series)({"step": 150})


# ------------------------------------------------------------ needs SUMO --

def test_a_committed_webster_tuning_row_reproduces_exactly():
    """The P122 row (s=660, 4 s, seed 400) re-runs to the same numbers after P132."""
    pytest.importorskip("traci")
    from simulation.runner import run_episode

    w = Webster(saturation_flow_per_metre=660.0, lost_time_startup_s=4.0)
    row = run_episode(w, regime="pulsed", seed=400, duration_s=1800, total_delay=True).as_row()
    assert (row["mean_total_delay_s"], row["mean_wait_s"], row["throughput"],
            row["phase_switches"]) == (28.814, 16.263, 1370, 97)
    assert round(w.clamp_rate, 4) == 0.3367


def test_recording_every_second_is_complete_and_changes_nothing():
    pytest.importorskip("traci")
    from simulation.count_forecasts import SeriesRecorder, baseline_series
    from simulation.runner import run_episode

    def make():
        return Webster(saturation_flow_per_metre=600.0, lost_time_startup_s=0.0)

    series = baseline_series(make, "pulsed", 999, 300)            # raises on any gap
    assert len(series) >= 300
    plain = run_episode(make(), regime="pulsed", seed=999, duration_s=300).as_row()
    recorded = run_episode(SeriesRecorder(make()), regime="pulsed", seed=999,
                           duration_s=300).as_row()
    assert {k: v for k, v in plain.items() if k != "method"} == \
        {k: v for k, v in recorded.items() if k != "method"}
