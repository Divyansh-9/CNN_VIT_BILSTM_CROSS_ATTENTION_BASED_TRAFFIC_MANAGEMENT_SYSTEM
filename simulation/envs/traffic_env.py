"""Gymnasium environment for the signal controller (S36, PRD §13.1).

The **16-dim state vector is a contract** (FR-M14, amendment A16). Its layout is
defined once in `mfstnet/configs/spec.yaml` and read from there, never restated
here — a second copy of an index map is a second chance to permute it, and a
permuted state invalidates every trained checkpoint silently.

    0-3    counts N S E W        / count_divisor
    4-7    queues N S E W        / queue_divisor
    8      phase == NS
    9      phase == EW
    10     phase remaining       / phase_remaining_divisor
    11-14  MFSTNet class N S E W / mfst_pred_divisor
    15     emergency flag

Indices 11-14 are **zeroed, never dropped**, when MFSTNet is unavailable
(PRD §7.2, FR-A06). Shortening the vector would change the observation space and
break the checkpoint; zeroing keeps the contract and states "no forecast".

`mfst_gate_mean` was in the original 17-dim spec and A16 removed it: SUMO has no
camera, so there is no gate to read, and a state feature that is always zero in
training and non-zero in deployment is worse than absent.

The action space is the PRD's 12 discrete (phase, duration) pairs. Safety bounds
are **not** enforced here — `runner.run_episode` clamps them, so a policy that has
learned to request an unsafe green still cannot produce one (PRD §9.6).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as error:      # pragma: no cover
    raise ImportError(
        "the RL environment needs gymnasium: pip install gymnasium stable-baselines3"
    ) from error

from ..runner import APPROACHES, lane_ids
from ..sumo_tools import ensure_sumo_home, sumo_binary

__all__ = ["TrafficSignalEnv", "GREEN_DURATIONS", "STATE_DIM"]

STATE_DIM = 16
GREEN_DURATIONS = (10, 20, 30, 45, 60, 90)     # PRD §13.1
ACTION_SPACES = ("phase_duration", "keep_or_switch")   # ADR-015
NS, EW = 0, 1
_SPEC = Path(__file__).resolve().parents[2] / "mfstnet" / "configs" / "spec.yaml"


def _load_spec() -> dict:
    import yaml

    return yaml.safe_load(_SPEC.read_text(encoding="utf-8"))


class TrafficSignalEnv(gym.Env):
    """One intersection, one episode per `reset()`.

    Deliberately **not** a wrapper around `run_episode`: that function owns its
    own loop, and an agent needs to be stepped from outside. The safety clamping
    and interphase logic are duplicated in structure but read the same bounds
    from the same spec, and `test_simulation.py` asserts they agree.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        net_dir: Path = Path("simulation/networks"),
        regime: str = "saturated",
        seed: int = 42,
        episode_s: int = 1800,
        use_mfstnet: bool = False,
        starvation_penalty: float = 1.0,
        switch_penalty: float = 0.05,
        action_space: str = "phase_duration",
        decision_interval_s: int = 5,
    ) -> None:
        super().__init__()
        spec = _load_spec()
        self._index_map = spec["ppo_state"]["index_map"]
        self._norm = spec["ppo_state"]["normalisers"]
        self._zeroed = spec["ppo_state"]["zero_when_mfstnet_unavailable"]
        signal = spec["signal"]

        if spec["ppo_state"]["dim"] != STATE_DIM:
            raise ValueError(
                f"spec.yaml declares a {spec['ppo_state']['dim']}-dim state but this "
                f"environment builds {STATE_DIM}. The state vector is a contract "
                f"(FR-M14) — reconcile them, do not adjust one to fit."
            )

        self.net_dir = Path(net_dir)
        self.regime = regime
        self.base_seed = seed
        self.episode_s = episode_s
        self.use_mfstnet = use_mfstnet
        self.starvation_penalty = starvation_penalty
        self.switch_penalty = switch_penalty

        self.yellow_s = int(signal["yellow_s"])
        self.all_red_s = int(signal["all_red_s"])
        self.min_green_s = int(signal["min_green_s"])
        self.max_green_s = int(signal["max_green_s"])
        self.starvation_s = int(signal["starvation_s"])

        # ADR-015: BOTH action spaces exist behind a flag, so the choice is made
        # on measured numbers rather than on argument. Screening costs a fraction
        # of one arm; discovering the answer after a 30-seed run costs every
        # checkpoint, because changing the action space invalidates them all.
        if action_space not in ACTION_SPACES:
            raise ValueError(
                f"action_space must be one of {sorted(ACTION_SPACES)}, got "
                f"{action_space!r}"
            )
        self.action_mode = action_space
        self.decision_interval_s = int(decision_interval_s)
        if self.action_mode == "keep_or_switch":
            # The literature-standard formulation: decide every fixed interval,
            # keep the current phase or switch. This is what makes state index 10
            # `phase_remaining` carry information — under (phase, duration) the
            # agent only acts at phase end, so it is structurally 0 (P11).
            self.action_space = spaces.Discrete(2)
        else:
            self.action_space = spaces.Discrete(2 * len(GREEN_DURATIONS))
        self.observation_space = spaces.Box(
            low=0.0, high=np.inf, shape=(STATE_DIM,), dtype=np.float32
        )

        self._traci = None
        self._tripinfo = None
        self._episode = 0

    # ------------------------------------------------------------ gym api --

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._close()

        ensure_sumo_home()
        import tempfile

        import traci

        handle = tempfile.NamedTemporaryFile(
            suffix=".tripinfo.xml", delete=False, mode="w"
        )
        handle.close()
        self._tripinfo = Path(handle.name)
        self._traci = traci
        run_seed = self.base_seed + self._episode if seed is None else seed
        self._episode += 1

        traci.start([
            str(sumo_binary("sumo")),
            "-n", str(self.net_dir / "intersection.net.xml"),
            "-r", str(self.net_dir / f"demand_{self.regime}.rou.xml"),
            "-a", str(self.net_dir / "vtypes.add.xml"),
            "--seed", str(run_seed),
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--time-to-teleport", "-1",
            "--waiting-time-memory", str(self.episode_s),
            # Per-vehicle trip records, for the SAME reason run_episode collects
            # them: the reward is a lane-sum shaping signal and the §14.3
            # headline is a per-vehicle mean. Screening two action spaces on the
            # shaping signal and then benchmarking on tripinfo would be a
            # comparison of two different quantities, and could pick the wrong
            # arm. `mean_wait_s()` reads this after an episode ends.
            "--tripinfo-output", str(self._tripinfo),
        ])

        self._lanes = lane_ids()
        self._step_s = 0
        self._phase = NS
        self._remaining = self.min_green_s
        # Tracked separately from `_remaining` because keep-or-switch may cut a
        # green short, and the minimum-green guarantee is about how long the
        # phase has ACTUALLY run, not how long was requested.
        self._green_elapsed = 0
        self._red_since = dict.fromkeys(APPROACHES, 0)
        self._prev_wait = 0.0
            # setPhase ALONE DOES NOT HOLD. SUMO's built-in program keeps
            # advancing on its own schedule, so the controller sets a phase and
            # the light immediately cycles past it — measured: we set 0 and SUMO
            # went 0, 3, 5, 0, 3, 4 over sixty seconds. setPhaseDuration pins it
            # until the controller says otherwise (pending item P15).
        traci.trafficlight.setPhase("C", self._phase * 3)
        traci.trafficlight.setPhaseDuration("C", 100_000)

        return self._observe(), {}

    def step(self, action: int):
        if self._traci is None:
            raise RuntimeError("step() before reset()")

        if self.action_mode == "keep_or_switch":
            # Decide every `decision_interval_s`; action 1 requests a switch.
            # A switch is REFUSED until the minimum green has actually elapsed —
            # safety is an actuation property, not something a policy is trusted
            # to have learned (PRD §9.6), exactly as in the runner.
            want_switch = int(action) == 1
            switched = want_switch and self._green_elapsed >= self.min_green_s
            if switched:
                self._interphase()
                self._phase = EW if self._phase == NS else NS
                self._traci.trafficlight.setPhase("C", self._phase * 3)
                self._traci.trafficlight.setPhaseDuration("C", 100_000)
                self._green_elapsed = 0
            elif self._green_elapsed >= self.max_green_s:
                # FR-A03's maximum green is an actuation bound too. Without this
                # a policy that always says "keep" would hold one phase forever.
                self._interphase()
                self._phase = EW if self._phase == NS else NS
                self._traci.trafficlight.setPhase("C", self._phase * 3)
                self._traci.trafficlight.setPhaseDuration("C", 100_000)
                self._green_elapsed = 0
                switched = True
            green = self.decision_interval_s
            # `phase_remaining` is now the time left before max green forces a
            # change — a real quantity, which is the point of this arm.
            self._remaining = max(0, self.max_green_s - self._green_elapsed)
        else:
            phase = int(action) // len(GREEN_DURATIONS)
            green = GREEN_DURATIONS[int(action) % len(GREEN_DURATIONS)]
            green = max(self.min_green_s, min(self.max_green_s, green))

            switched = phase != self._phase
            if switched:
                self._interphase()
                self._phase = phase
                self._traci.trafficlight.setPhase("C", self._phase * 3)
                self._traci.trafficlight.setPhaseDuration("C", 100_000)
            self._remaining = green

        starved = 0
        for _ in range(green):
            if self._step_s >= self.episode_s:
                break
            self._traci.simulationStep()
            self._step_s += 1
            self._remaining -= 1
            self._green_elapsed += 1
            starved += self._advance_starvation()

        observation = self._observe()
        reward = self._reward(starved, switched)
        truncated = self._step_s >= self.episode_s
        return observation, reward, False, truncated, {"starvation_events": starved}

    def close(self) -> None:
        self._close()

    # ----------------------------------------------------------- internal --

    def _observe(self) -> np.ndarray:
        state = np.zeros(STATE_DIM, dtype=np.float32)
        index = self._index_map

        for approach in APPROACHES:
            group = self._lanes[approach]
            count = sum(self._traci.lane.getLastStepVehicleNumber(l) for l in group)
            queue = sum(self._traci.lane.getLastStepHaltingNumber(l) for l in group)
            state[index[f"count_{approach}"]] = count / self._norm["count_divisor"]
            state[index[f"queue_{approach}"]] = queue / self._norm["queue_divisor"]

        state[index["phase_NS"]] = 1.0 if self._phase == NS else 0.0
        state[index["phase_EW"]] = 1.0 if self._phase == EW else 0.0
        # STRUCTURALLY ZERO at every decision point, and that is a finding, not
        # a bug in this line — see pending item P11.
        #
        # The agent acts only at the END of a phase, so by the time `step()`
        # observes, the green it requested has fully elapsed and `_remaining` is
        # 0. PRD §13.1 lists this feature assuming a controller that can observe
        # MID-phase; the §13.1 action space (12 discrete phase-and-duration
        # pairs) is precisely one that cannot. One of sixteen dimensions
        # therefore carries no information.
        #
        # It is kept and computed rather than removed, because the vector length
        # is a contract (FR-M14) and dropping an index breaks every checkpoint.
        # Resolving it means changing the action space to a fixed decision
        # interval, which is a PRD amendment, not a code edit.
        state[index["phase_remaining"]] = (
            max(0, self._remaining) / self._norm["phase_remaining_divisor"]
        )

        # Indices 11-14 stay zero when there is no forecast. Zeroed, never
        # dropped — shortening the vector breaks every trained checkpoint.
        if self.use_mfstnet:
            raise NotImplementedError(
                "live MFSTNet in the loop is Phase 3 (PRD §2.4). Until then the "
                "forecast indices stay zeroed, which is the declared fallback "
                "behaviour (FR-A06), not a stub."
            )

        return state

    def _reward(self, starved: int, switched: bool) -> float:
        """Negative total wait delta, penalised for starvation and churn.

        Wait is read as the lane-sum here rather than per-vehicle: a reward must
        be computable at every step, and tripinfo only exists for completed
        trips. That makes it a *shaping* signal, not the reported metric — §14.3
        numbers still come from `run_episode`'s tripinfo, and the two must never
        be conflated.
        """
        total_wait = sum(
            self._traci.lane.getWaitingTime(l)
            for group in self._lanes.values()
            for l in group
        )
        delta = total_wait - self._prev_wait
        self._prev_wait = total_wait

        reward = -delta / 100.0
        reward -= self.starvation_penalty * starved
        if switched:
            reward -= self.switch_penalty
        return float(reward)

    def _advance_starvation(self) -> int:
        served = ("N", "S") if self._phase == NS else ("E", "W")
        events = 0
        for approach in APPROACHES:
            if approach in served:
                self._red_since[approach] = 0
            else:
                self._red_since[approach] += 1
                if self._red_since[approach] == self.starvation_s:
                    events += 1
        return events

    def _interphase(self) -> None:
        self._traci.trafficlight.setPhase("C", self._phase * 3 + 1)
        for tick in range(self.yellow_s + self.all_red_s):
            if tick == self.yellow_s:
                self._traci.trafficlight.setPhase("C", self._phase * 3 + 2)
            self._traci.simulationStep()
            self._step_s += 1
            self._advance_starvation()

    def _close(self) -> None:
        if self._traci is not None:
            try:
                self._traci.close()
            except Exception:
                pass
            self._traci = None

    def mean_wait_s(self) -> float:
        """Per-vehicle mean wait over COMPLETED trips, from tripinfo.

        This is the §14.3 headline and the metric `run_episode` reports, so a
        screened action space and a benchmarked controller are compared on the
        same quantity. The reward is deliberately NOT this — it is a lane-sum
        shaping signal, and `traci.lane.getWaitingTime` is a SUM over vehicles
        rather than a mean, which is how a 468 s "mean wait" was once reported.

        Call after the episode ends; SUMO writes tripinfo on close.
        """
        import xml.etree.ElementTree as ET

        self._close()
        if self._tripinfo is None or not self._tripinfo.exists():
            return float("nan")
        try:
            root = ET.parse(self._tripinfo).getroot()
        except ET.ParseError:
            return float("nan")
        waits = [float(t.get("waitingTime", 0.0)) for t in root.findall("tripinfo")]
        return sum(waits) / len(waits) if waits else float("nan")
