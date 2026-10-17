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
        self.realised: dict[int, tuple] = {}
        self.messages: list[tuple[int, dict, tuple]] = []

    @property
    def decision_mode(self):
        return getattr(self.inner, "decision_mode", None)

    def reset(self) -> None:
        # The runner calls this before SUMO starts, so a replay oracle can run
        # its own episode here without sharing a live connection.
        self.inner.reset()
        self.producer.reset(self.seed)
        self.agree = self.compared = 0
        self.realised, self.messages = {}, []

    def observe_second(self, step: int, counts: dict) -> None:
        """The traffic that actually happened, every second the runner observes."""
        self.realised[int(step)] = tuple(counts[a] for a in APPROACHES)

    def decide(self, observation: dict) -> tuple[int, int]:
        t, counts = int(observation["step"]), observation["counts"]
        series = getattr(self.producer, "_series", None)
        if series is not None and t < len(series):
            for k, a in enumerate(APPROACHES):
                self.compared += 1
                self.agree += (self.producer._class(series[t][k])
                               == self.producer._class(counts[a]))
        before = getattr(self.producer, "_t_msg", None)
        message, age = self.producer.message(t, counts)
        if message is not None and getattr(self.producer, "_t_msg", None) != before:
            self.messages.append((t, dict(message), tuple(counts[a] for a in APPROACHES)))
        fed = {**observation, "forecast": message, "forecast_age_s": age}
        return self.inner.decide(fed)

    def realised_accuracy(self) -> dict:
        """Each message against the class that actually occurred at its target time.

        A message made at t is a forecast for t + 60 s. Its target is the
        realised class at t + 60 s, under the policy being evaluated. Targets
        that fall in an interphase second, which the runner does not observe,
        are skipped and counted.

        Three accuracies are reported against the same targets:
        - the forecast actually sent;
        - the oracle, which is the frozen policy's trajectory;
        - persistence, the class at t.
        """
        series = getattr(self.producer, "_series", None)
        cls = self.producer._class
        hits = {"forecast": 0, "oracle": 0, "persistence": 0}
        n = skipped = 0
        for t, message, now in self.messages:
            target = self.realised.get(t + 60)
            if target is None or series is None or t + 60 >= len(series):
                skipped += 1
                continue
            for k, a in enumerate(APPROACHES):
                real = cls(target[k])
                hits["forecast"] += message[a] == real
                hits["oracle"] += cls(series[t + 60][k]) == real
                hits["persistence"] += cls(now[k]) == real
                n += 1
        out = {f"acc_{k}_realised": (v / n if n else None) for k, v in hits.items()}
        return {**out, "realised_targets": n, "targets_skipped": skipped}

    def report(self) -> dict:
        stats = getattr(self.producer, "stats", {})
        messages = stats.get("messages", 0)
        return {"oracle_realised_agreement": (self.agree / self.compared
                                              if self.compared else None),
                "oracle_realised_compared": self.compared,
                **self.realised_accuracy(),
                "producer_messages": messages,
                "producer_informed_share": (stats.get("informed_messages", 0) / messages
                                            if messages else None)}
