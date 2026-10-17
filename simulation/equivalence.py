"""Does evaluation reproduce training, decision for decision? (P116, P119, P120)

`trace_env` runs a policy in `TrafficSignalEnv`, where it trained. `trace_runner`
runs the same policy through `run_episode` and `PPOController`, where it is
evaluated. Both record every decision's time, phase, per-approach counts and
the full observation vector the policy acted on. On the same seed the two
traces must be identical.

Three mismatches were found this way, and each made a policy act on rules or
inputs it never trained on:

- the runner's `keep_or_switch` actuation (P116);
- the environment's missing sublane model (P119);
- `phase_remaining` left at 0 by `PPOController` (P120).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

__all__ = ["trace_env", "trace_runner", "compare"]

APPROACHES = ("N", "S", "E", "W")


def trace_env(model, regime: str, seed: int, duration_s: int) -> list[tuple]:
    from simulation.envs.traffic_env import TrafficSignalEnv
    from simulation.runner import lane_ids

    env = TrafficSignalEnv(regime=regime, seed=seed, episode_s=duration_s,
                           action_space="keep_or_switch")
    obs, _ = env.reset(seed=seed)
    lanes, trace = lane_ids(), []
    try:
        while True:
            counts = tuple(sum(env._traci.lane.getLastStepVehicleNumber(l) for l in lanes[a])
                           for a in APPROACHES)
            trace.append((env._step_s, env._phase, counts, tuple(np.round(obs, 6))))
            action = int(model.predict(obs, deterministic=True)[0])
            obs, _, done, truncated, _ = env.step(action)
            if done or truncated:
                break
    finally:
        env.close()
    return trace


def trace_runner(checkpoint: Path, regime: str, seed: int, duration_s: int) -> list[tuple]:
    from simulation.ppo_controller import PPOController
    from simulation.runner import run_episode

    inner = PPOController(checkpoint, action_space="keep_or_switch")

    class Tracing:
        decision_mode = inner.decision_mode
        name = inner.name

        def __init__(self):
            self.trace = []

        def reset(self):
            inner.reset()
            self.trace = []

        def decide(self, observation):
            obs = inner.observe(observation)
            counts = tuple(observation["counts"][a] for a in APPROACHES)
            self.trace.append((observation["step"], observation["phase"], counts,
                               tuple(np.round(obs, 6))))
            return inner.decide(observation)

    tracing = Tracing()
    run_episode(tracing, regime=regime, seed=seed, duration_s=duration_s)
    return tracing.trace


def compare(a: list[tuple], b: list[tuple]) -> dict:
    """The first decision where the traces differ, and in what."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            fields = ("time", "phase", "counts", "observation")
            diff = [f for f, x, y in zip(fields, a[i], b[i]) if x != y]
            detail = {}
            if "observation" in diff:
                detail["indices"] = [k for k, (x, y) in enumerate(zip(a[i][3], b[i][3])) if x != y]
            return {"identical": False, "decision": i, "time": a[i][0], "differs_in": diff,
                    **detail, "compared": n}
    return {"identical": abs(len(a) - len(b)) <= 1, "compared": n,
            "lengths": (len(a), len(b))}
