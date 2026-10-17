"""P115: scenarios must leave the constant regimes untouched, and keep seeds apart."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.forecast_quality import construct, corruption_rng, informed_mask, skill  # noqa: E402
from simulation.scenarios import (demand_path, episode_seed, load_scenarios,  # noqa: E402
                                  routes_xml, schedule)

CONFIG = load_scenarios()
PARAMS = CONFIG["pulsed"]


@pytest.mark.parametrize("regime", ["light", "saturated", "oversaturated"])
def test_constant_regimes_resolve_to_their_committed_files(regime, tmp_path):
    net = Path("simulation/networks")
    assert demand_path(net, regime, 7, cache=tmp_path) == net / f"demand_{regime}.rou.xml"
    assert not any(tmp_path.iterdir())                    # nothing generated


@pytest.mark.parametrize("regime", ["light", "saturated", "oversaturated"])
def test_constant_regimes_keep_their_historical_episode_seeds(regime):
    assert [episode_seed(regime, 42, e) for e in range(3)] == [42, 43, 44]


def test_scenario_training_seeds_avoid_every_other_seed_use():
    seeds = {episode_seed("pulsed", s, e) for s in (42, 1, 7) for e in range(2000)}
    assert len(seeds) == 6000                             # no two runs share an episode
    assert min(seeds) >= 1_000_000                        # clear of 0-29 and 200-319
    with pytest.raises(ValueError):
        episode_seed("pulsed", 1, 10_000)


def test_unknown_regime_is_refused():
    with pytest.raises(ValueError):
        demand_path(Path("x"), "rush_hour", 1)


def test_schedule_is_seeded_bounded_and_never_repeats_a_level():
    a, b = schedule(PARAMS, 5), schedule(PARAMS, 5)
    assert a == b and schedule(PARAMS, 6) != a
    for segments in a.values():
        assert segments[0][0] == 0 and segments[-1][1] == PARAMS["duration_s"]
        for (b0, e0, v0), (b1, e1, v1) in zip(segments, segments[1:]):
            assert e0 == b1 and v0 != v1
        for begin, end, _ in segments[:-1]:
            assert PARAMS["d_min"] <= end - begin <= PARAMS["d_max"]


def test_schedule_refuses_parameters_outside_the_preregistered_bounds():
    with pytest.raises(ValueError):
        schedule({**PARAMS, "levels": [300, 1500]}, 1)
    with pytest.raises(ValueError):
        schedule({**PARAMS, "d_min": 30}, 1)


def test_routes_are_probability_flows_sorted_by_begin(tmp_path):
    xml = routes_xml(PARAMS, 3)
    assert "vehsPerHour" not in xml and 'probability="' in xml
    begins = [float(line.split('begin="')[1].split('"')[0])
              for line in xml.splitlines() if "<flow " in line]
    assert begins == sorted(begins)
    path = demand_path(Path("simulation/networks"), "pulsed", 3, cache=tmp_path)
    assert path.read_text(encoding="utf-8") == xml


def test_the_informed_chain_has_the_nominal_share_and_persists():
    rng = np.random.default_rng(0)
    mask = informed_mask(200_000, 0.3, rng)
    assert abs(mask.mean() - 0.3) < 0.01
    flips = (mask[1:] != mask[:-1]).mean()
    assert flips < 0.1                                    # persistent, not i.i.d.
    assert not informed_mask(50, 0.0, rng).any() and informed_mask(50, 1.0, rng).all()


def test_construct_endpoints_and_measured_skill():
    rng = np.random.default_rng(1)
    oracle = rng.integers(0, 3, size=(20_000, 4))
    persistence = np.where(rng.random((20_000, 4)) < 0.6, oracle, (oracle + 1) % 3)
    assert (construct(oracle, persistence, 0.0, corruption_rng(1, 0.0)) == persistence).all()
    assert (construct(oracle, persistence, 1.0, corruption_rng(1, 1.0)) == oracle).all()
    forecast = construct(oracle, persistence, 0.5, corruption_rng(1, 0.5))
    assert abs(skill(forecast, persistence, oracle, oracle) - 0.5) < 0.05
    rows = construct(oracle, persistence, 0.5, corruption_rng(1, 0.5)) == oracle
    assert ((rows.all(axis=1)) | (forecast == persistence).all(axis=1)).all()  # lane-correlated


def test_total_delay_is_opt_in_and_moves_no_existing_metric():
    pytest.importorskip("traci")
    from simulation.controllers import Fixed
    from simulation.runner import run_episode

    off = run_episode(Fixed(green_s=30), regime="oversaturated", seed=3, duration_s=600).as_row()
    on = run_episode(Fixed(green_s=30), regime="oversaturated", seed=3, duration_s=600,
                     total_delay=True).as_row()
    assert "mean_total_delay_s" not in off
    assert {k: on[k] for k in off} == off                 # every existing field identical
    assert on["delay_vehicles"] > on["throughput"]        # unfinished vehicles are counted
    assert on["mean_total_delay_s"] > 0


def test_sumo_start_retries_a_port_race_then_gives_up():
    """P126: a parallel training lost its run to "Address already in use"."""
    import struct

    pytest.importorskip("traci")
    from simulation.envs.traffic_env import start_sumo

    class FlakyTraci:
        def __init__(self, failures):
            self.failures, self.starts, self.closes = failures, 0, 0

        def start(self, command):
            self.starts += 1
            if self.starts <= self.failures:
                raise struct.error("unpack requires a buffer of 3 bytes")

        def close(self):
            self.closes += 1

    flaky = FlakyTraci(failures=2)
    start_sumo(flaky, ["sumo"])
    assert flaky.starts == 3 and flaky.closes == 2

    hopeless = FlakyTraci(failures=99)
    with pytest.raises(struct.error):
        start_sumo(hopeless, ["sumo"], attempts=3)
    assert hopeless.starts == 3
