"""A trained PPO checkpoint, wearing the `Controller` interface (S38).

`benchmark.py` has said since it was written that "PPO arms appear here
automatically once checkpoints exist under `models/ppo/`". They did not — the
factory listed `fixed`, `longest_queue` and `webster` and nothing else, so the
docstring described behaviour the code did not have. That is the same shape as
[P52](../docs/00-planning/PRD-CHANGELOG.md), where `ppo_config.yaml` described a
surrogate arm that was never implemented: **a comment asserting a capability is
indistinguishable from the capability until someone runs it.**

**The checkpoint is verified, not trusted.** `assert_compatible` refuses a
policy whose observation-contract digest does not match the current
`spec.yaml`, and one that records no digest at all. A benchmark evaluating a
policy against a state layout it never trained on produces numbers that look
entirely normal, which is the failure P52 and P53 exist to prevent — and the
30-seed benchmark is exactly the place those numbers would end up being
reported from.

**Safety clamping is still the runner's job.** This class returns whatever the
policy asked for, and `runner.run_episode` bounds it (PRD §9.6). A wrapper that
clamped here would hide from the results how often the policy requested
something out of range, which is a thing worth knowing about a learned
controller.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["PPOController", "discover_checkpoints"]

NS, EW = 0, 1
APPROACHES = ("N", "S", "E", "W")


class PPOController:
    """Wraps a Stable-Baselines3 policy as a `runner.Controller`.

    The observation is rebuilt here from the runner's dict using the **same
    spec** the environment uses, so the policy sees at benchmark time what it
    saw at training time. Building it from a hand-written index list would be a
    second copy of the layout, and a permuted index keeps the shape while
    changing the meaning ([P53](../docs/00-planning/PRD-CHANGELOG.md)).
    """

    def __init__(self, checkpoint: Path, *, action_space: str,
                 name: str | None = None) -> None:
        import yaml
        from stable_baselines3 import PPO

        from simulation.contract import assert_compatible

        self.sidecar = assert_compatible(checkpoint, action_space=action_space)
        self.model = PPO.load(str(checkpoint).removesuffix(".zip"), device="cpu")
        self.action_space = action_space
        self.name = name or Path(checkpoint).stem

        spec = yaml.safe_load(
            Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
        state = spec["ppo_state"]
        self.index = state["index_map"]
        self.norm = state["normalisers"]
        self.dim = state["dim"]
        self.state_spec = state
        # NFR-16: read from the spec, and RAISE if it is not there. The first
        # version of this line used `.get("green_durations", [10, 20, ...])`
        # against a spec key actually named `green_durations_s`, so it silently
        # fell back to a literal that happened to match — a duplicated config
        # value that would have survived any change to the real one.
        signal = spec.get("signal") or {}
        if "green_durations_s" not in signal:
            raise SystemExit(
                "mfstnet/configs/spec.yaml has no signal.green_durations_s. "
                "The action ladder is a config value (NFR-16); a default here "
                "would be a second copy of it that never changes when the "
                "first one does."
            )
        self.greens = list(signal["green_durations_s"])
        # `keep_or_switch` holds each phase for one decision interval; the
        # duration is not in the action. Default matches TrafficSignalEnv's.
        self.decision_interval_s = int(signal.get("decision_interval_s", 5))

    def reset(self) -> None:
        pass

    def observe(self, observation: dict) -> "object":
        """The runner's dict -> the spec's vector. One layout, read from YAML."""
        import numpy as np

        from simulation.forecast_state import _valid_number, forecast_slots

        vector = np.zeros(self.dim, dtype=np.float32)
        counts, queues = observation["counts"], observation["queues"]
        for approach in APPROACHES:
            # P97a, same rule as the forecast: a missing count is not zero
            # vehicles. Refused, so the caller's gate falls back (ADR-020 A1).
            for name, values in (("counts", counts), ("queues", queues)):
                if approach not in values or not _valid_number(values[approach]):
                    raise ValueError(f"{name}: {approach} missing or invalid; "
                                     f"a missing value is not zero (P97a)")
            vector[self.index[f"count_{approach}"]] = (
                counts[approach] / self.norm["count_divisor"])
            vector[self.index[f"queue_{approach}"]] = (
                queues[approach] / self.norm["queue_divisor"])
        phase = observation["phase"]
        vector[self.index["phase_NS"]] = 1.0 if phase == NS else 0.0
        vector[self.index["phase_EW"]] = 1.0 if phase == EW else 0.0
        # ADR-020 as amended: the forecast slots come from the one encoder.
        # With no forecast message (the no-forecast policy's world) every class
        # slot reads "absent" and the age reads 1.0; never a class.
        for i, value in forecast_slots(self.state_spec, observation.get("forecast"),
                                       observation.get("forecast_age_s")).items():
            vector[i] = value
        return vector

    def decide(self, observation: dict) -> tuple[int, int]:
        action, _ = self.model.predict(self.observe(observation),
                                       deterministic=True)
        return self._interpret(int(action), observation["phase"])

    def _interpret(self, action: int, phase: int) -> tuple[int, int]:
        """Action index -> (phase, green seconds), matching `traffic_env.step`.

        The two spaces are **not** the same shape, and assuming they were is a
        mistake this class made in its first version:

        * `keep_or_switch` is `Discrete(2)`. Action 1 requests a switch, 0 keeps,
          and the green is the fixed `decision_interval_s` — **the duration is
          not part of the action at all**. The first version here decoded a
          green from `action // 2`, which on a two-action space is always 0, so
          every green would have been the ladder's smallest. The policy would
          have been benchmarked under rules it never trained under, and the
          numbers would have looked entirely ordinary.
        * `phase_duration` is `Discrete(2 * len(greens))`: phase from
          `action // len(greens)`, duration from `action % len(greens)`.

        Kept beside each other, with the env's own decoding quoted, because the
        only defence against this drifting again is that the two are visibly the
        same arithmetic.
        """
        if self.action_space == "keep_or_switch":
            switch = int(action) == 1
            return ((EW if phase == NS else NS) if switch else phase,
                    self.decision_interval_s)
        target = int(action) // len(self.greens)
        return target, self.greens[int(action) % len(self.greens)]


def discover_checkpoints(directory: Path = Path("models/ppo")) -> list[Path]:
    """Every checkpoint at the top level of `directory`.

    Deliberately not recursive: `models/ppo/_pre_p47/` holds twelve checkpoints
    of unknown training length ([P74](../docs/00-planning/PRD-CHANGELOG.md)),
    archived precisely so a benchmark cannot pick them up. Recursing would undo
    that in one line.
    """
    return sorted(p for p in directory.glob("*.zip"))
