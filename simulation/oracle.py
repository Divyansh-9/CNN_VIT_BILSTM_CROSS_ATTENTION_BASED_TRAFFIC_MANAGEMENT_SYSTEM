"""The replay oracle (ADR-021 Amendment 1, A1.2; P115).

The oracle for seed *s* at time *t* is each approach's count at *t* + 60 s
**in the trajectory of the frozen no-forecast policy on seed *s***. It is
produced by running that episode once in `TrafficSignalEnv`, recording every
approach's count after every simulated second, and reading the record back.

**Limitation (A1.2).** The oracle is conditioned on the frozen policy's
trajectory. A forecast-aware policy changes traffic through its own actions,
so this is not necessarily a perfect forecast of the future under that
policy. It carries the exogenous demand exactly, because the same vehicles
are loaded at the same seconds whichever policy acts (P115 Q4b). The
congestion that demand produces, it carries only as the frozen policy would
have produced it.

`Recording` is the one implementation of the per-second record. The P115
qualification and the training-time oracle both use it, so the oracle a
policy trains on is the oracle that was qualified.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

__all__ = ["Recording", "run_recorded", "ReplayOracle", "HORIZON_S"]

APPROACHES = ("N", "S", "E", "W")
HORIZON_S = 60
# The environment's last step can end past `episode_s`: a switch runs its 6 s
# interphase before the hold, so a decision at t can be followed by one at
# t + 11. The replay therefore runs this much beyond episode_s + 60, so the
# oracle can answer every decision of the episode it serves.
OVERRUN_S = 15


class Recording:
    """Pass-through over a TraCI handle that records after every simulated second.

    It reads state only and changes nothing the environment does.
    """

    def __init__(self, traci, lanes) -> None:
        self._traci, self._lanes = traci, lanes
        self.counts = [self._counts()]           # index = simulation time in s
        self.loaded: list[tuple] = []
        self.arrived = self.departed = 0

    def __getattr__(self, name):
        return getattr(self._traci, name)

    def _counts(self) -> tuple:
        lane = self._traci.lane
        return tuple(sum(lane.getLastStepVehicleNumber(l) for l in self._lanes[a])
                     for a in APPROACHES)

    def simulationStep(self, *args):
        self._traci.simulationStep(*args)
        sim = self._traci.simulation
        self.loaded.append(tuple(sim.getLoadedIDList()))
        self.arrived += sim.getArrivedNumber()
        self.departed += sim.getDepartedNumber()
        self.counts.append(self._counts())


def run_recorded(env, seed: int, policy) -> dict:
    """Run one episode of `env` on `seed` under `policy(obs, env) -> action`."""
    from simulation.runner import lane_ids

    obs, _ = env.reset(seed=seed)
    rec = Recording(env._traci, lane_ids())
    env._traci = rec
    decisions = []
    try:
        while True:
            queues = tuple(sum(rec.lane.getLastStepHaltingNumber(l) for l in lane_ids()[a])
                           for a in APPROACHES)
            decisions.append({"t": env._step_s, "queues": queues, "phase": env._phase})
            obs, _, terminated, truncated, _ = env.step(policy(obs, env))
            if terminated or truncated:
                break
    finally:
        env._close()
    return {"seed": seed, "counts": rec.counts, "loaded": rec.loaded, "decisions": decisions,
            "arrived_fraction": rec.arrived / rec.departed if rec.departed else 0.0}


class ReplayOracle:
    """Per-second counts of the frozen no-forecast policy, one cached file per seed.

    The cache key covers everything the trajectory depends on: the regime and
    its parameters, the frozen policy's weights, and the environment's
    dynamics. A change to any of them is a new file, never a stale read.
    """

    def __init__(self, checkpoint: Path, regime: str, *, episode_s: int,
                 lateral_resolution: float | None, decision_interval_s: int = 5,
                 cache: Path = Path("data/_oracle")) -> None:
        from simulation.scenarios import is_scenario, load_scenarios, scenario_hash

        self.checkpoint = Path(checkpoint)
        self.sha256 = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        self.regime = regime
        params = load_scenarios()[regime] if is_scenario(regime) else {"regime": regime}
        replay_s = int(episode_s) + HORIZON_S + OVERRUN_S
        self.env_kwargs = {"regime": regime, "episode_s": replay_s,
                           "lateral_resolution": lateral_resolution,
                           "decision_interval_s": int(decision_interval_s),
                           "action_space": "keep_or_switch"}
        dynamics = f"lat{lateral_resolution}_dt{decision_interval_s}_ep{episode_s}_r{replay_s}"
        self.key = f"{regime}_{scenario_hash(params)}_{self.sha256[:12]}_{dynamics}"
        self.cache = Path(cache)
        self._model = None
        self._env = None

    def describe(self) -> dict:
        return {"oracle": "replay", "frozen_policy": str(self.checkpoint),
                "frozen_policy_sha256": self.sha256, "cache_key": self.key,
                "horizon_s": HORIZON_S}

    def counts(self, seed: int) -> np.ndarray:
        """Shape (seconds + 1, 4): counts at every simulated second, N S E W."""
        path = self.cache / f"{self.key}_{int(seed)}.npy"
        if path.exists():
            return np.load(path)
        series = np.asarray(self._replay(int(seed))["counts"], dtype=np.uint16)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npy")
        np.save(tmp, series)
        tmp.replace(path)
        return series

    def _replay(self, seed: int) -> dict:
        from stable_baselines3 import PPO

        from simulation.envs.traffic_env import TrafficSignalEnv

        if self._model is None:
            self._model = PPO.load(str(self.checkpoint).removesuffix(".zip"), device="cpu")
            # No trip records: thousands of replays per training run would fill
            # the disk, which has happened here before (16,955 files, 1.5 GB).
            self._env = TrafficSignalEnv(seed=seed, tripinfo=False, **self.env_kwargs)
        model = self._model
        return run_recorded(self._env, seed,
                            lambda obs, env: int(model.predict(obs, deterministic=True)[0]))
