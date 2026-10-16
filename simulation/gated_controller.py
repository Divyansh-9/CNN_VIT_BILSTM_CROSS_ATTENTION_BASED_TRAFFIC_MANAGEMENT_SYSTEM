"""The fail-safe gate wired to real controllers (ADR-020 as amended, P112).

`GatedController` is a runner `Controller`. On every decision it hands the
observation, with whatever forecast message accompanies it, to
`ForecastGate`, and lets exactly one policy act:

| gate verdict | who decides |
|---|---|
| `webster` (counts or queues invalid) | the degraded-mode fixed cycle, `Fixed(30)`: FR-A06's `LocalWebster`, which trusts no counts (P112 Amendment 1) |
| `no_forecast` | the no-forecast PPO policy, on a state with no forecast message |
| `forecast` | the forecast-aware policy |

**No forecast-aware policy exists yet** (P52). Until one does, the
`forecast` branch is a `Probe`: it records exactly what it was given, then
delegates the action to the no-forecast policy so traffic keeps running.
Every decision is recorded, so an evaluation can check the gate against what
was actually injected rather than against the gate's own reasons.

**This is not connected to real signal timing**, and nothing here changes
that (ADR-027 rule 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.forecast_state import ForecastGate, forecast_slots

__all__ = ["Probe", "Decision", "GatedController"]


@dataclass
class Probe:
    """Stands in for the forecast-aware policy that P52 has not produced."""

    no_forecast: object
    calls: list = field(default_factory=list)
    name: str = "probe"

    def reset(self) -> None:
        self.calls.clear()

    def decide(self, observation: dict, *, state_slots: dict) -> tuple[int, int]:
        self.calls.append({"step": observation.get("step"), "slots": dict(state_slots),
                           "forecast": observation.get("forecast"),
                           "age": observation.get("forecast_age_s")})
        plain = {k: v for k, v in observation.items() if k not in ("forecast", "forecast_age_s")}
        return self.no_forecast.decide(plain)


@dataclass
class Decision:
    step: int
    decider: str
    reasons: tuple
    action: tuple
    slots: dict | None          # the state slots built for the deciding policy


@dataclass
class GatedController:
    no_forecast: object                  # the no-forecast PPO policy
    degraded: object                     # Fixed(30): FR-A06's degraded-mode cycle
    forecast_aware: object | None = None # None -> a Probe over the no-forecast policy
    state_spec: dict | None = None
    gate: ForecastGate = field(default_factory=ForecastGate)
    name: str = "gated"
    decisions: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.forecast_aware is None:
            self.forecast_aware = Probe(self.no_forecast)
        if self.state_spec is None:
            import yaml
            from pathlib import Path

            self.state_spec = yaml.safe_load(
                Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))["ppo_state"]

    def reset(self) -> None:
        for policy in (self.no_forecast, self.degraded, self.forecast_aware):
            policy.reset()
        self.gate = ForecastGate()
        self.decisions = []

    def decide(self, observation: dict) -> tuple[int, int]:
        verdict = self.gate.check(observation)
        if verdict.decider == "webster":
            action, slots = self.degraded.decide(observation), None
        elif verdict.decider == "no_forecast":
            plain = {k: v for k, v in observation.items() if k not in ("forecast", "forecast_age_s")}
            slots = forecast_slots(self.state_spec, None, None)
            action = self.no_forecast.decide(plain)
        else:
            slots = forecast_slots(self.state_spec, observation["forecast"],
                                   observation["forecast_age_s"])
            action = (self.forecast_aware.decide(observation, state_slots=slots)
                      if isinstance(self.forecast_aware, Probe)
                      else self.forecast_aware.decide(observation))
        self.decisions.append(Decision(observation.get("step", -1), verdict.decider,
                                       verdict.reasons, tuple(action), slots))
        return action
