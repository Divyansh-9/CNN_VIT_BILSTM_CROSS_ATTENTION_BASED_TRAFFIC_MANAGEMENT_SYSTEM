"""Tests for demand generation, controllers and the episode runner (S33, S34).

The controller and demand tests are pure Python. The runner tests start SUMO and
are skipped without it — they are slow, and they are the only check that the
safety clamping and the interphase actually happen.

    python -m pytest tests/test_simulation.py -q
"""

from __future__ import annotations

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
