"""Next-minute count forecasts for a forecast-assisted Webster split (P132).

A Webster controller reads, per approach, a vehicle count, and turns it into
flow ratios and a green split. In the forecast-assisted variant (FAW), it reads
a forecast of the **next minute's mean count** instead. Nothing else about the
rule changes. The demand sources here supply that forecast:

- **`OracleMeanCount`:** the realised mean count over (t, t + 60] in the
  trajectory of the **baseline controller itself** (W-now) on the same seed.
  The replay is self-consistent: W-oracle departs from W-now only through the
  forecast. Once its decisions differ, its own traffic differs, and the
  oracle is no longer exactly its future. That gap is measured
  (`transfer_report`).
- **`RidgeCountDemand`:** the frozen, level-free ridge v1 (ADR-027,
  `ridge@73532968dcf2`), applied unchanged to 60 samples taken 2 s apart from
  the controller's own per-second counts. Before 118 s of history exist, it
  reads the observed counts: W-now's behaviour.

`ForecastWebster` wraps a `Webster` with one source. It forwards the runner's
per-second counts to the source, and records each forecast beside the
realised next-minute mean, so every run reports how good its forecast was.

**Not connected to real signal timing.**
"""

from __future__ import annotations

import statistics
from pathlib import Path

__all__ = ["APPROACHES", "SeriesRecorder", "baseline_series", "OracleMeanCount",
           "RidgeCountDemand", "ForecastWebster", "RIDGE_SPEC"]

APPROACHES = ("N", "S", "E", "W")
HORIZON_S = 60
RIDGE_SPEC = Path("experiments/results/bellevue_pilot/p105_ridge_v1.json")


class SeriesRecorder:
    """Wraps a controller; records the runner's counts at every simulated second."""

    def __init__(self, inner) -> None:
        self.inner, self.name = inner, getattr(inner, "name", "recorded")
        self.series: dict[int, tuple] = {}

    @property
    def decision_mode(self):
        return getattr(self.inner, "decision_mode", None)

    def reset(self) -> None:
        self.inner.reset()
        self.series = {}

    def observe_second(self, step: int, counts: dict) -> None:
        self.series[int(step)] = tuple(counts[a] for a in APPROACHES)
        if hasattr(self.inner, "observe_second"):
            self.inner.observe_second(step, counts)

    def decide(self, observation: dict):
        return self.inner.decide(observation)


def baseline_series(make_baseline, regime: str, seed: int, duration_s: int) -> list[tuple]:
    """Per-second counts of the baseline controller, every second from 0 to the end.

    Raises if any second is missing: the oracle is never built from a gappy record.
    """
    from simulation.runner import run_episode

    recorder = SeriesRecorder(make_baseline())
    run_episode(recorder, regime=regime, seed=seed, duration_s=duration_s)
    last = max(recorder.series)
    missing = [s for s in range(last + 1) if s not in recorder.series]
    if missing:
        raise RuntimeError(f"baseline record has {len(missing)} missing seconds, first {missing[:3]}")
    return [recorder.series[s] for s in range(last + 1)]


def next_minute_mean(series, t: int) -> dict:
    window = series[t + 1: t + 1 + HORIZON_S]
    if len(window) < HORIZON_S:
        raise RuntimeError(f"no full minute after t = {t} s (record ends at {len(series) - 1} s)")
    return {a: statistics.fmean(row[k] for row in window) for k, a in enumerate(APPROACHES)}


class OracleMeanCount:
    """Demand = the baseline trajectory's realised mean count over the next minute."""

    kind = "oracle"

    def __init__(self, series) -> None:
        self.series = series

    def __call__(self, observation: dict) -> dict:
        return next_minute_mean(self.series, int(observation["step"]))


class RidgeCountDemand:
    """Demand = frozen ridge v1 on the controller's own 2-second samples (ADR-027)."""

    kind = "ridge"
    SAMPLES, SPACING_S = 60, 2

    def __init__(self, spec: Path = RIDGE_SPEC) -> None:
        from edge.count_forecast import RidgeCountForecaster

        self.model = RidgeCountForecaster(spec, {a: a for a in APPROACHES})
        self.history: dict[int, tuple] = {}
        self.ready_decisions = self.fallback_decisions = 0

    def reset(self) -> None:
        self.history = {}
        self.ready_decisions = self.fallback_decisions = 0

    def observe_second(self, step: int, counts: dict) -> None:
        self.history[int(step)] = tuple(counts[a] for a in APPROACHES)

    def __call__(self, observation: dict) -> dict:
        t = int(observation["step"])
        times = [t - self.SPACING_S * (self.SAMPLES - 1 - i) for i in range(self.SAMPLES)]
        if times[0] < 0 or any(s not in self.history for s in times):
            self.fallback_decisions += 1
            return dict(observation["counts"])                   # not ready: W-now's input
        self.ready_decisions += 1
        return {a: self.model.forecast([self.history[s][k] for s in times])
                for k, a in enumerate(APPROACHES)}


class ForecastWebster:
    """A Webster whose demand is a forecast; records forecast against realised."""

    def __init__(self, webster, source, name: str) -> None:
        self.webster, self.source, self.name = webster, source, name
        webster.demand_source = self._demand
        self.realised: dict[int, tuple] = {}
        self.forecasts: list[tuple[int, dict, dict]] = []

    @property
    def clamp_rate(self) -> float:
        return self.webster.clamp_rate

    def reset(self) -> None:
        self.webster.reset()
        if hasattr(self.source, "reset"):
            self.source.reset()
        self.realised, self.forecasts = {}, []

    def observe_second(self, step: int, counts: dict) -> None:
        self.realised[int(step)] = tuple(counts[a] for a in APPROACHES)
        if hasattr(self.source, "observe_second"):
            self.source.observe_second(step, counts)

    def _demand(self, observation: dict) -> dict:
        demand = self.source(observation)
        self.forecasts.append((int(observation["step"]), dict(demand),
                               dict(observation["counts"])))
        return demand

    def decide(self, observation: dict):
        return self.webster.decide(observation)

    def transfer_report(self) -> dict:
        """Mean absolute error against the realised next-minute mean, under THIS run."""
        # Every second must be present (the runner records interphase seconds too):
        # a missing second raises rather than shifting every later index.
        series = ([self.realised[s] for s in range(max(self.realised) + 1)]
                  if self.realised else [])
        err_f, err_p, n = 0.0, 0.0, 0
        for t, demand, now in self.forecasts:
            if t + HORIZON_S >= len(series):
                continue
            real = next_minute_mean(series, t)
            for a in APPROACHES:
                err_f += abs(demand[a] - real[a])
                err_p += abs(now[a] - real[a])
                n += 1
        return {"forecast_mae_vs_realised": err_f / n if n else None,
                "persistence_mae_vs_realised": err_p / n if n else None,
                "forecast_points": n}
