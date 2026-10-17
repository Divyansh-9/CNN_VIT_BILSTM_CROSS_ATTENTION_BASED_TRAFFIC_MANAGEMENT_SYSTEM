"""Feeding forecasts to a policy under evaluation (ADR-021 A1.2, A2.3).

`run_episode` gives a controller counts, queues and the phase. A forecast-aware
policy also needs the forecast message it trained with, and its age.
`ForecastFeeding` supplies both from the same producer class that
`TrafficSignalEnv` uses in training (`simulation.forecast_producer`). The
messages are therefore made by the same rule, at the same decision times, from
the same oracle.

It also measures what A1.2 requires every evaluation to report: **how often
the oracle agreed with the traffic that actually happened under the policy
being evaluated.**

- At each decision time *t*, the oracle's class for *t* (the frozen policy's
  trajectory at *t*) is compared with the class of the counts actually
  observed at *t*.
- Under the frozen policy itself the agreement is 1.0 (P115 Q4).
- Under a policy that changes traffic it is lower, and that gap is the
  limitation A1.2 names.

A producer must be reset with the episode's seed, which the runner does not
pass to controllers. So one `ForecastFeeding` is built per episode, with its
seed.
"""

from __future__ import annotations

__all__ = ["ForecastFeeding"]

APPROACHES = ("N", "S", "E", "W")


class ForecastFeeding:
    def __init__(self, inner, producer, seed: int) -> None:
        self.inner, self.producer, self.seed = inner, producer, int(seed)
        self.name = getattr(inner, "name", "forecast-fed")
        self.agree = self.compared = 0

    @property
    def decision_mode(self):
        return getattr(self.inner, "decision_mode", None)

    def reset(self) -> None:
        # The runner calls this before SUMO starts, so a replay oracle can run
        # its own episode here without sharing a live connection.
        self.inner.reset()
        self.producer.reset(self.seed)
        self.agree = self.compared = 0

    def decide(self, observation: dict) -> tuple[int, int]:
        t, counts = int(observation["step"]), observation["counts"]
        series = getattr(self.producer, "_series", None)
        if series is not None and t < len(series):
            for k, a in enumerate(APPROACHES):
                self.compared += 1
                self.agree += (self.producer._class(series[t][k])
                               == self.producer._class(counts[a]))
        message, age = self.producer.message(t, counts)
        fed = {**observation, "forecast": message, "forecast_age_s": age}
        return self.inner.decide(fed)

    def report(self) -> dict:
        return {"oracle_realised_agreement": (self.agree / self.compared
                                              if self.compared else None),
                "oracle_realised_compared": self.compared,
                **{f"producer_{k}": v for k, v in getattr(self.producer, "stats", {}).items()
                   if k != "ages"}}
