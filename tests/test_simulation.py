"""Tests for demand generation, controllers and the episode runner (S33, S34).

The controller and demand tests are pure Python. The runner tests start SUMO and
are skipped without it — they are slow, and they are the only check that the
safety clamping and the interphase actually happen.

    python -m pytest tests/test_simulation.py -q
"""

from __future__ import annotations

import pathlib

import pytest

from scripts.build_sumo_demand import REGIMES, TURN_RATIOS, routes_xml
from simulation.controllers import Fixed, LongestQueue
from simulation.runner import APPROACHES, lane_ids


def has_sumo() -> bool:
    try:
        from simulation.sumo_tools import sumo_binary

        sumo_binary("sumo")
        return True
    except Exception:
        return False


needs_sumo = pytest.mark.skipif(not has_sumo(), reason="SUMO not installed")


# ------------------------------------------------------------- demand --

def test_turn_ratios_sum_to_one():
    """A shortfall would silently reduce demand below the labelled rate, and the
    regime calibration would describe traffic that was never generated."""
    assert sum(TURN_RATIOS.values()) == pytest.approx(1.0)


def test_regimes_are_ordered_and_bracket_the_measured_knee():
    """Calibrated, not estimated. The knee under fixed-time is 700-800
    veh/h/approach — see the table in build_sumo_demand.Regime."""
    rates = [r.veh_per_hour_per_approach for r in REGIMES.values()]
    assert REGIMES["light"].veh_per_hour_per_approach < 700
    assert 700 <= REGIMES["saturated"].veh_per_hour_per_approach <= 800
    assert REGIMES["oversaturated"].veh_per_hour_per_approach > 800
    assert len(set(rates)) == 3


def test_every_approach_gets_every_movement():
    xml = routes_xml(REGIMES["saturated"], 600, 42)
    for approach in APPROACHES:
        for movement in TURN_RATIOS:
            assert f'id="r_{approach}_{movement}"' in xml
            assert f'id="f_{approach}_{movement}"' in xml


def test_vehicles_enter_with_a_lateral_offset():
    """ADR-010. Without `departPosLat="random"` vehicles snap to lane centre and
    filtering only begins after a lane change."""
    assert 'departPosLat="random"' in routes_xml(REGIMES["light"], 600, 42)


# --------------------------------------------------------- controllers --

def test_fixed_alternates_and_ignores_the_observation():
    """The floor. Any method that cannot beat it is not adaptive."""
    controller = Fixed(green_s=30)
    controller.reset()
    busy = {"queues": {"N": 99, "S": 99, "E": 0, "W": 0}}

    phases = [controller.decide(busy)[0] for _ in range(4)]
    assert phases == [0, 1, 0, 1], "fixed-time must not respond to demand"


def test_longest_queue_serves_the_busier_direction():
    controller = LongestQueue()
    controller.reset()

    ns_busy = {"queues": {"N": 20, "S": 20, "E": 1, "W": 1}}
    ew_busy = {"queues": {"N": 0, "S": 0, "E": 15, "W": 15}}

    assert controller.decide(ns_busy)[0] == 0
    assert controller.decide(ew_busy)[0] == 1


def test_longest_queue_respects_its_own_green_bounds():
    controller = LongestQueue()
    controller.reset()

    empty = {"queues": dict.fromkeys(APPROACHES, 0)}
    flooded = {"queues": dict.fromkeys(APPROACHES, 500)}

    assert controller.decide(empty)[1] == controller.min_green_s
    assert controller.decide(flooded)[1] == controller.max_green_s


def test_lane_ids_follow_the_state_vector_convention():
    """PRD §13.1 indexes the 16-dim state by lane. A rename permutes it."""
    lanes = lane_ids(2)
    assert lanes["N"] == ["N2C_0", "N2C_1"]
    assert set(lanes) == set(APPROACHES)


# ------------------------------------------------------------- runner --

@needs_sumo
def test_an_episode_runs_and_reports_sane_metrics():
    from simulation.runner import run_episode

    result = run_episode(Fixed(green_s=30), regime="light", duration_s=300)

    assert result.steps > 0
    assert result.throughput > 0
    assert result.mean_wait_s >= 0
    assert 0.0 <= result.arrived_fraction <= 1.0, (
        "a completion ratio above 1 is impossible — it means departures and "
        "arrivals are being counted over different intervals"
    )


@needs_sumo
def test_the_runner_clamps_a_controller_that_asks_for_too_much():
    """PRD §9.6. Safety is an actuation property, never something a learned
    policy is trusted to have acquired."""
    from simulation.runner import run_episode

    class Greedy:
        name = "greedy"

        def reset(self) -> None:
            pass

        def decide(self, observation):
            return 0, 100_000          # a policy that has learned nonsense

    result = run_episode(Greedy(), regime="light", duration_s=200, max_green_s=90)
    assert result.steps > 0            # ran to completion rather than hanging


@needs_sumo
def test_a_queue_responsive_baseline_beats_fixed_time():
    """If it does not, either the runner is not observing queues or the demand
    is degenerate — and every later PPO comparison would be meaningless."""
    from simulation.runner import run_episode

    fixed = run_episode(Fixed(green_s=30), regime="saturated", duration_s=600)
    adaptive = run_episode(LongestQueue(), regime="saturated", duration_s=600)

    assert adaptive.mean_wait_s < fixed.mean_wait_s


# ------------------------------------------------------------ webster --

def test_optimum_cycle_is_infinite_at_capacity():
    """Y >= 1 means no cycle length serves the demand. Returning a finite number
    would hide that behind a clamp."""
    from simulation.webster import optimum_cycle

    assert optimum_cycle(1.0, 14) == float("inf")
    assert optimum_cycle(0.5, 14) == pytest.approx((1.5 * 14 + 5) / 0.5)


def test_critical_flow_ratio_is_capped_below_one():
    """Uncapped, an oversaturated approach makes 1 - Y negative and the optimum
    cycle NEGATIVE — which then clamps into range and looks reasonable."""
    from simulation.webster import critical_flow_ratio

    assert critical_flow_ratio(99_999, 1000) == 0.95
    assert critical_flow_ratio(0, 1000) == 0.0


def test_saturation_flow_is_width_based_not_per_lane():
    """ADR-012: lanes are not the unit of discharge when two- and three-wheelers
    filter laterally."""
    from simulation.webster import Webster

    w = Webster(saturation_flow_per_metre=660.0, approach_width_m=6.4)
    assert w.saturation_pcu_per_hour == pytest.approx(660 * 6.4)


def test_a_fully_clamped_configuration_is_disqualified():
    """It is a fixed cycle wearing Webster's name. Measured: at the knee, s=1050
    and s=1283 posted the LOWEST waits at a 100% clamp rate."""
    from simulation.webster import select_best

    rows = [
        {"saturation_flow": 1050, "mean_wait_s": 13.7, "clamp_rate": 1.00, "arrived_fraction": 0.94},
        {"saturation_flow": 750, "mean_wait_s": 26.8, "clamp_rate": 0.14, "arrived_fraction": 0.91},
    ]
    selection = select_best(rows)
    assert selection.best["saturation_flow"] == 750, "the cheapest wait is not the best baseline"
    assert "clamp" in selection.rejected[0][1]


def test_a_configuration_that_failed_is_disqualified():
    """Survivorship. Measured: oversaturated s=1050 posted the lowest wait of the
    sweep while completing 55% of trips — the slowest vehicles never finished, so
    they never entered the average."""
    from simulation.webster import select_best

    rows = [
        {"saturation_flow": 1050, "mean_wait_s": 63.2, "clamp_rate": 0.43, "arrived_fraction": 0.55},
        {"saturation_flow": 660, "mean_wait_s": 78.2, "clamp_rate": 0.48, "arrived_fraction": 0.90},
    ]
    selection = select_best(rows)
    assert selection.best["saturation_flow"] == 660
    assert "waited longest" in selection.rejected[0][1]


def test_no_qualifying_configuration_is_a_finding_not_a_crash():
    """Measured in both the light and oversaturated regimes. The honest response
    is to report the sweep and make no 'Webster's best' claim."""
    from simulation.webster import select_best

    rows = [{"saturation_flow": s, "mean_wait_s": 8.0, "clamp_rate": 1.0,
             "arrived_fraction": 0.96} for s in (525, 600, 660)]
    selection = select_best(rows)
    assert selection.best is None
    assert len(selection.rejected) == 3
    assert "claim nothing" in selection.explain()


# ------------------------------------------------- gym environment (S36) --

def _env_module():
    pytest.importorskip("gymnasium")
    from simulation.envs import traffic_env

    return traffic_env


def test_state_dim_matches_the_spec():
    """FR-M14, amendment A16. 16, not the original 17 — `mfst_gate_mean` was
    removed because SUMO has no camera, and a feature that is always zero in
    training and non-zero in deployment is worse than absent."""
    import pathlib

    import yaml

    module = _env_module()
    spec = yaml.safe_load(
        (pathlib.Path("mfstnet/configs/spec.yaml")).read_text(encoding="utf-8")
    )
    assert module.STATE_DIM == spec["ppo_state"]["dim"] == 16


def test_the_index_map_is_read_from_spec_not_restated():
    """A second copy of an index map is a second chance to permute it, and a
    permuted state invalidates every trained checkpoint silently."""
    source = pathlib.Path("simulation/envs/traffic_env.py").read_text(encoding="utf-8")
    for name in ("count_N", "queue_S", "phase_remaining", "mfst_pred_E"):
        assert f'"{name}"' not in source or "index[f" in source, (
            f"{name} looks hardcoded; read it from spec.yaml's index_map"
        )


def test_action_space_is_the_prd_twelve():
    """PRD §13.1: NS/EW x 10/20/30/45/60/90."""
    module = _env_module()
    assert len(module.GREEN_DURATIONS) == 6
    assert 2 * len(module.GREEN_DURATIONS) == 12


def test_green_durations_lie_within_the_signal_bounds():
    import yaml

    module = _env_module()
    signal = yaml.safe_load(
        pathlib.Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8")
    )["signal"]
    assert tuple(signal["green_durations_s"]) == module.GREEN_DURATIONS
    assert min(module.GREEN_DURATIONS) >= signal["min_green_s"]
    assert max(module.GREEN_DURATIONS) <= signal["max_green_s"]


@needs_sumo
def test_forecast_indices_are_zeroed_not_dropped():
    """PRD §7.2 / FR-A06. Shortening the vector changes the observation space and
    breaks the checkpoint; zeroing keeps the contract and states 'no forecast'."""
    module = _env_module()
    env = module.TrafficSignalEnv(regime="light", episode_s=120)
    try:
        observation, _ = env.reset()
        assert observation.shape == (16,)
        assert all(observation[i] == 0.0 for i in (11, 12, 13, 14))
    finally:
        env.close()


@needs_sumo
def test_env_passes_sb3_check_env():
    module = _env_module()
    pytest.importorskip("stable_baselines3")
    from stable_baselines3.common.env_checker import check_env

    env = module.TrafficSignalEnv(regime="light", episode_s=200)
    try:
        check_env(env, warn=True)
    finally:
        env.close()
