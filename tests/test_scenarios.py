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


def _sumo_command():
    from simulation.sumo_tools import ensure_sumo_home, sumo_binary

    ensure_sumo_home()
    net = "simulation/networks"
    return [str(sumo_binary("sumo")), "-n", f"{net}/intersection.net.xml",
            "-r", f"{net}/demand_saturated.rou.xml", "-a", f"{net}/vtypes.add.xml",
            "--no-step-log", "true", "--no-warnings", "true"]


def test_sumo_start_recovers_from_a_real_port_race_and_leaks_nothing(monkeypatch):
    """P126, with real SUMO: the first port is taken by a squatter that hangs up.

    This is the failure that killed a 500,000-step run. The first fix only
    passed a test with a fake TraCI; for real it blocked forever and leaked SUMO.
    """
    import socket
    import subprocess
    import threading

    traci = pytest.importorskip("traci")
    import sumolib.miscutils as misc

    from simulation.envs.traffic_env import start_sumo

    squatter = socket.socket()
    squatter.bind(("localhost", 0))
    squatter.listen()
    taken = squatter.getsockname()[1]

    def hang_up():
        while True:
            try:
                conn, _ = squatter.accept()
                conn.close()
            except OSError:
                return

    threading.Thread(target=hang_up, daemon=True).start()
    real, picks = misc.getFreeSocketPort, []

    def first_taken():
        picks.append(taken if not picks else real())
        return picks[-1]

    monkeypatch.setattr(misc, "getFreeSocketPort", first_taken)
    started = []
    real_popen = subprocess.Popen

    def recording_popen(*args, **kwargs):
        started.append(real_popen(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    try:
        start_sumo(traci, _sumo_command(), label="race_test")
        traci.switch("race_test")
        traci.simulationStep()
        assert traci.simulation.getTime() == 1.0
        assert len(picks) >= 2                                # it really retried
        assert all(p.poll() is not None for p in started[:-1])   # no SUMO leaked
        traci.close()
    finally:
        squatter.close()
        for p in started:
            if p.poll() is None:
                p.kill()


def test_sumo_start_gives_up_explicitly_after_its_attempts(monkeypatch):
    """Exhausted retries raise; an episode is never silently skipped."""
    traci = pytest.importorskip("traci")
    import sumolib.miscutils as misc

    from simulation.envs.traffic_env import start_sumo

    monkeypatch.setattr(traci, "init", lambda *a, **k: (_ for _ in ()).throw(
        traci.exceptions.FatalTraCIError("no server")))
    with pytest.raises(traci.exceptions.FatalTraCIError):
        start_sumo(traci, _sumo_command(), attempts=2, label="give_up_test")
    assert misc.getFreeSocketPort                             # module untouched


def test_a_connection_to_someone_elses_sumo_is_refused(monkeypatch):
    """If our SUMO died, a working connection on its port belongs to another process."""
    import subprocess

    traci = pytest.importorskip("traci")
    from simulation.envs.traffic_env import start_sumo

    class FakeProc:
        def __init__(self, alive):
            self.alive, self.killed = alive, False

        def poll(self):
            return None if self.alive else 1

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            return 0

    procs = iter([FakeProc(alive=False), FakeProc(alive=True)])
    made = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: made.append(next(procs)) or made[-1])
    monkeypatch.setattr(traci, "init", lambda *a, **k: None)   # the handshake "succeeds"
    start_sumo(traci, ["sumo"], label="hijack_test")
    assert len(made) == 2                                      # first connection refused
    assert made[1].alive and not made[1].killed


def test_an_interrupt_during_the_handshake_kills_our_sumo_and_is_not_retried(monkeypatch):
    """Every failure path cleans up the process we started, and only that one."""
    import subprocess

    traci = pytest.importorskip("traci")
    from simulation.envs.traffic_env import start_sumo

    class FakeProc:
        killed = False

        def poll(self):
            return None if not self.killed else -9

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            return -9

    made = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: made.append(FakeProc()) or made[-1])

    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(traci, "init", interrupted)
    with pytest.raises(KeyboardInterrupt):
        start_sumo(traci, ["sumo"], label="interrupt_test")
    assert len(made) == 1 and made[0].killed                  # cleaned up, not retried
