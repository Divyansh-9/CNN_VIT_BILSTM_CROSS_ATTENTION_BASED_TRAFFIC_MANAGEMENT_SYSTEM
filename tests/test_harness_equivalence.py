"""P116 / P119: evaluation must apply the rules a policy trained under.

The same scripted `keep_or_switch` policy is driven through `TrafficSignalEnv`
(training) and `run_episode` (evaluation) on the same seed. Every decision's
time, phase and per-approach count must be identical. Explicit checks pin the
three rules:

- a "keep" lasts 5 s, not a minimum green;
- a switch is refused until 10 s of green has run;
- 90 s of green forces the change, also across a run of keeps.

Needs SUMO.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("traci")

from simulation.runner import APPROACHES, NS, EW, lane_ids, run_episode  # noqa: E402

DURATION = 600


def busier_red(counts: dict, phase: int) -> bool:
    green = ("N", "S") if phase == NS else ("E", "W")
    red = sum(counts[a] for a in APPROACHES if a not in green)
    return red > sum(counts[a] for a in green) + 2


POLICIES = {
    "reactive": busier_red,
    "always_keep": lambda counts, phase: False,
    "always_switch": lambda counts, phase: True,
}


def env_trace(rule, regime, seed):
    from simulation.envs.traffic_env import TrafficSignalEnv

    env = TrafficSignalEnv(regime=regime, seed=seed, episode_s=DURATION,
                           action_space="keep_or_switch")
    env.reset(seed=seed)
    lanes, trace = lane_ids(), []
    try:
        while True:
            counts = {a: sum(env._traci.lane.getLastStepVehicleNumber(l) for l in lanes[a])
                      for a in APPROACHES}
            trace.append((env._step_s, env._phase, tuple(counts[a] for a in APPROACHES)))
            _, _, done, truncated, _ = env.step(1 if rule(counts, env._phase) else 0)
            if done or truncated:
                break
    finally:
        env.close()
    return trace


class Scripted:
    decision_mode = "keep_or_switch"
    name = "scripted"

    def __init__(self, rule):
        self.rule, self.trace = rule, []

    def reset(self):
        self.trace = []

    def decide(self, observation):
        counts, phase = observation["counts"], observation["phase"]
        self.trace.append((observation["step"], phase, tuple(counts[a] for a in APPROACHES)))
        switch = self.rule(counts, phase)
        return ((EW if phase == NS else NS) if switch else phase), 5


def runner_trace(rule, regime, seed):
    controller = Scripted(rule)
    run_episode(controller, regime=regime, seed=seed, duration_s=DURATION)
    return controller.trace


@pytest.mark.parametrize("name", sorted(POLICIES))
@pytest.mark.parametrize("regime,seed", [("pulsed", 999), ("saturated", 5)])
def test_runner_reproduces_the_training_environment(name, regime, seed):
    a = env_trace(POLICIES[name], regime, seed)
    b = runner_trace(POLICIES[name], regime, seed)
    n = min(len(a), len(b))
    assert n > 50
    assert a[:n] == b[:n]
    assert abs(len(a) - len(b)) <= 1                # only the last, truncated decision


@pytest.mark.parametrize("regime", ["pulsed", "light"])
def test_a_trained_policy_acts_identically_in_training_and_evaluation(regime):
    """P120: the whole observation vector, every decision, a real checkpoint."""
    checkpoint = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
    if not checkpoint.exists():
        pytest.skip("needs a trained keep_or_switch checkpoint")
    from stable_baselines3 import PPO

    from simulation.equivalence import compare, trace_env, trace_runner

    model = PPO.load(str(checkpoint).removesuffix(".zip"), device="cpu")
    result = compare(trace_env(model, regime, 999, DURATION),
                     trace_runner(checkpoint, regime, 999, DURATION))
    assert result["identical"], result


def test_a_keep_lasts_five_seconds_and_max_green_forces_the_change():
    trace = runner_trace(POLICIES["always_keep"], "saturated", 5)
    times = [t for t, _, _ in trace]
    assert times[:19] == list(range(0, 95, 5))      # decisions every 5 s from t = 0
    changes = [t for (t, p, _), (_, q, _) in zip(trace[1:], trace) if p != q]
    assert changes, "a run of keeps was never forced to change"
    assert changes[0] == 90 + 6 + 5                 # forced at 90 s, interphase, one hold


def test_a_switch_is_refused_until_ten_seconds_of_green():
    trace = runner_trace(POLICIES["always_switch"], "saturated", 5)
    phases = [p for _, p, _ in trace]
    times = [t for t, _, _ in trace]
    # decisions at 0 and 5 are refused; the switch at 10 is honoured
    assert phases[:3] == [NS, NS, NS] and times[:3] == [0, 5, 10]
    assert phases[3] == EW and times[3] == 10 + 6 + 5


@pytest.mark.parametrize("q", [0.0, 0.5, 1.0])
def test_a_forecast_fed_policy_acts_identically_in_training_and_evaluation(q, tmp_path):
    """ADR-021 A2.3: parity holds with forecast messages too, every input, every decision."""
    checkpoint = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
    if not checkpoint.exists():
        pytest.skip("needs a trained keep_or_switch checkpoint (stand-in policy)")
    from stable_baselines3 import PPO

    from simulation.equivalence import compare, trace_env, trace_runner
    from simulation.forecast_producer import Surrogate
    from simulation.oracle import ReplayOracle

    def producer():
        oracle = ReplayOracle(checkpoint, "pulsed", episode_s=DURATION,
                              lateral_resolution=0.8, cache=tmp_path)
        return Surrogate(q, oracle, low_max=4, med_max=15)

    model = PPO.load(str(checkpoint).removesuffix(".zip"), device="cpu")
    a = trace_env(model, "pulsed", 999, DURATION, forecast=producer())
    b = trace_runner(checkpoint, "pulsed", 999, DURATION, producer=producer())
    result = compare(a, b)
    assert result["identical"], result
    assert any(row[3][11] > 0 for row in b)                   # a forecast really was fed


def test_evaluation_reports_oracle_agreement_with_realised_traffic(tmp_path):
    """A1.2: under the frozen policy itself the oracle matches what happened."""
    checkpoint = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
    if not checkpoint.exists():
        pytest.skip("needs a trained keep_or_switch checkpoint")
    from simulation.forecast_eval import ForecastFeeding
    from simulation.forecast_producer import NoForecast, Surrogate
    from simulation.oracle import ReplayOracle
    from simulation.ppo_controller import PPOController

    class Blind(PPOController):
        """The frozen policy, deliberately blind to the forecast, so traffic matches the replay."""

        def decide(self, observation):
            plain = {k: v for k, v in observation.items()
                     if k not in ("forecast", "forecast_age_s")}
            return super().decide(plain)

    oracle = ReplayOracle(checkpoint, "pulsed", episode_s=DURATION, lateral_resolution=0.8,
                          cache=tmp_path)
    feeding = ForecastFeeding(Blind(checkpoint, action_space="keep_or_switch"),
                              Surrogate(1.0, oracle, low_max=4, med_max=15), 999)
    run_episode(feeding, regime="pulsed", seed=999, duration_s=DURATION)
    assert feeding.report()["oracle_realised_agreement"] == 1.0
    assert feeding.report()["oracle_realised_compared"] > 100
    assert NoForecast().message(0, {}) == (None, None)
