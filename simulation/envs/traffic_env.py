"""Gymnasium environment for the signal controller (S36, PRD §13.1).

The **17-dim state vector is a contract** (FR-M14, A16, ADR-020 as amended). Its layout is
defined once in `mfstnet/configs/spec.yaml` and read from there, never restated
here — a second copy of an index map is a second chance to permute it, and a
permuted state invalidates every trained checkpoint silently.

    0-3    counts N S E W        / count_divisor
    4-7    queues N S E W        / queue_divisor
    8      phase == NS
    9      phase == EW
    10     phase remaining       / phase_remaining_divisor
    11-14  class forecast N S E W   LOW/MEDIUM/HIGH -> 1/3, 2/3, 1; 0.0 = none
    15     emergency flag
    16     forecast_age            min(age, 10) / 10; 1.0 when there is no forecast

**0.0 at 11-14 means "no forecast", and no class can produce it** (ADR-020 as
amended, P97a). Under the old layout LOW was 0.0, so "no forecast" read as
"clear". `simulation.forecast_state.forecast_slots` is the only route to these
indices. Shortening the vector would still break the checkpoint.

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
from ..scenarios import demand_path, episode_seed

from simulation.forecast_state import forecast_slots  # noqa: E402

__all__ = ["TrafficSignalEnv", "GREEN_DURATIONS", "STATE_DIM"]

STATE_DIM = 17                    # ADR-020 as amended: forecast_age at 16
GREEN_DURATIONS = (10, 20, 30, 45, 60, 90)     # PRD §13.1
ACTION_SPACES = ("phase_duration", "keep_or_switch")   # ADR-015
NS, EW = 0, 1
_SPEC = Path(__file__).resolve().parents[2] / "mfstnet" / "configs" / "spec.yaml"


SUMO_START_ATTEMPTS = 5


def start_sumo(traci, command: list[str], attempts: int = SUMO_START_ATTEMPTS) -> None:
    """Start SUMO, retrying a port race between parallel processes (P126).

    `traci.start` picks a free port and hands it to SUMO. With several
    trainings in parallel, another process can take that port first. SUMO then
    exits with "Address already in use" and the handshake fails, which killed a
    500,000-step run part-way. A retry starts a fresh SUMO with the same
    command, the same seed and a new port. Nothing about the simulation
    differs, so the episode is unchanged.
    """
    import struct

    from traci.exceptions import FatalTraCIError, TraCIException

    for attempt in range(1, attempts + 1):
        try:
            traci.start(command)
            return
        except (FatalTraCIError, TraCIException, struct.error, ConnectionError, OSError):
            try:
                traci.close()
            except Exception:                                  # noqa: BLE001
                pass
            if attempt == attempts:
                raise


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
        lateral_resolution: float | None = 0.8,
        forecast=None,
        tripinfo: bool = True,
    ) -> None:
        super().__init__()
        spec = _load_spec()
        self._index_map = spec["ppo_state"]["index_map"]
        self._norm = spec["ppo_state"]["normalisers"]
        self._state_spec = spec["ppo_state"]
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
        # P119: the sublane model (ADR-010), exactly as `run_episode` applies it.
        # Before this the environment never passed it, so every policy trained on
        # lane-disciplined traffic and was evaluated on sublane traffic.
        self.lateral_resolution = lateral_resolution
        # P52, ADR-021 A1.4: what fills indices 11-14 and 16. None is the
        # no-forecast arm, exactly the behaviour before producers existed.
        self.forecast = forecast
        self.write_tripinfo = tripinfo
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

        # Tripinfo goes to a MANAGED directory, not the system temp.
        #
        # A fresh file per episode is required for correctness — reusing one
        # path makes SUMO's rewrite unreliable and `mean_wait_s()` starts
        # returning 0.00. But per-episode files in %TEMP% leaked 16,955 files
        # and 1.5 GB across two sessions and eventually filled the disk, which
        # broke SUMO startup outright. Per-reset unlinking does not fix it
        # either: Windows holds the handle past SUMO's exit, so about half the
        # unlinks fail silently.
        #
        # Keeping them in one gitignored directory that is swept when the
        # environment is constructed bounds the disk cost without touching the
        # correctness of the measurement.
        self._tripinfo_dir = Path("data/_tripinfo")
        self._tripinfo_dir.mkdir(parents=True, exist_ok=True)
        for stale in self._tripinfo_dir.glob("*.tripinfo.xml"):
            try:
                stale.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------ gym api --

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._close()

        ensure_sumo_home()
        import traci

        # Unique per instance: a replay environment (simulation.oracle) can run
        # in the same process as the one training.
        self._tripinfo = (self._tripinfo_dir / f"{id(self):x}_ep{self._episode:06d}.tripinfo.xml"
                          if self.write_tripinfo else None)
        # P115: on a scenario the seed is the demand, so training episodes are
        # kept clear of the evaluation seeds; constant regimes are unchanged.
        run_seed = (episode_seed(self.regime, self.base_seed, self._episode)
                    if seed is None else seed)
        self._episode += 1
        # Before this environment's SUMO starts: a replay oracle runs its own
        # episode to answer, and must not share a live connection.
        if self.forecast is not None:
            self.forecast.reset(run_seed)
        self._traci = traci

        start_sumo(traci, [
            str(sumo_binary("sumo")),
            "-n", str(self.net_dir / "intersection.net.xml"),
            "-r", str(demand_path(self.net_dir, self.regime, run_seed)),
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
        ] + (["--tripinfo-output", str(self._tripinfo)] if self._tripinfo else [])
          + (["--lateral-resolution", str(self.lateral_resolution)]
             if self.lateral_resolution else []))

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
        self._discard_tripinfo()

    # ----------------------------------------------------------- internal --

    def _observe(self) -> np.ndarray:
        state = np.zeros(STATE_DIM, dtype=np.float32)
        index = self._index_map
        counts = {}

        for approach in APPROACHES:
            group = self._lanes[approach]
            count = sum(self._traci.lane.getLastStepVehicleNumber(l) for l in group)
            counts[approach] = count
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

        # ADR-020 as amended: no forecast in this world, so every class slot
        # reads the reserved "absent" and the age reads 1.0. Never a class.
        if self.use_mfstnet:
            raise NotImplementedError(
                "live MFSTNet in the loop is Phase 3 (PRD §2.4). Until then the "
                "forecast indices read 'no forecast', which is the declared "
                "fallback behaviour (FR-A06), not a stub."
            )
        # P52: the producer answers; `forecast_slots` is still the only encoder.
        message, age = ((None, None) if self.forecast is None
                        else self.forecast.message(self._step_s, counts))
        for i, value in forecast_slots(self._state_spec, message, age).items():
            state[i] = value

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

    def _discard_tripinfo(self) -> None:
        """Delete the previous episode's tripinfo file.

        One `NamedTemporaryFile(delete=False)` per `reset()` and nothing removing
        them: a training run resets hundreds of times, and 16,955 files
        accumulated across two sessions — 1.5 GB, and eventually a full disk that
        broke SUMO startup outright.

        This is the SECOND attempt at this fix. The first was committed as a
        no-op edit that replaced a block with itself, so the leak continued while
        the commit message said it had been fixed.
        """
        for stale in self._tripinfo_dir.glob("*.tripinfo.xml"):
            try:
                stale.unlink()
            except OSError:
                pass        # held by a still-exiting SUMO; the next sweep gets it
        self._tripinfo = None

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
