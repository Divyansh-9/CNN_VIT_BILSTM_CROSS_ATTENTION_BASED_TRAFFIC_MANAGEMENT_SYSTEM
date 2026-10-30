"""Each forecast beside what it forecast, paired at the edge (D26, ADR-014 §2).

**What is compared.** Both live forecasters (ADR-027) forecast the mean of each
lane's next 30 samples, 2 s apart, of the raw per-lane total, bicycles
included. P105 scored the count exactly so (`future_mean(v, e)` is the mean of
`v[e+1..e+30]`, `scripts/p105_freeze.py`), and P94–P103 scored the class as the
class of that same mean under the same thresholds. So a forecast made after
sample *e* is checked against the mean of samples *e+1* to *e+30*: the same
quantity the forecasters read, from the same counts. The published
`VehicleCount`, which leaves bicycles out (D1), is not used.

**How pairs are formed: by sample count, never by clock.** A replay's sample
time is video time and a camera's a monotonic clock, while the server has a
third. The checker keeps its own `SampleBuffer` under the forecasters' rules.
A forecast becomes due when the 30th sample after it has been taken.

- **A gap:** a reset of that buffer, which follows any gap over 3 s, drops
  every pending forecast. The minute it was about is broken, and it is never
  matched to the nearest observation instead.
- **A refused sample:** it never enters the buffer, so it never counts toward
  the 30.
- **A restart:** the pending queue lives in the process, so a new session
  never pairs with the last one's forecasts.

**One pair per message.** The checker reports facts. The server spaces them a
minute apart and counts the denominators where they are shown.
"""

from __future__ import annotations

from collections import deque

from contracts.mqtt import CongestionPrediction, CountForecast, ForecastCheck
from edge.persistence import WINDOW, classify
from edge.samples import SampleBuffer

__all__ = ["ForecastChecker"]


class ForecastChecker:
    def __init__(self, lane_to_approach: dict[str, str], low: float, med: float,
                 session: str) -> None:
        self.lane_to_approach = dict(lane_to_approach)
        self.low, self.med, self.session = low, med, session
        self.buffer = SampleBuffer(lane_to_approach, WINDOW)
        # (made_ts, samples still to come, class forecasts, count forecasts, models)
        self.pending: deque = deque()
        self.dropped = 0                 # forecasts a gap left uncheckable

    def step(self, counts: dict[str, int], ts: float,
             prediction: CongestionPrediction | None,
             count: CountForecast | None) -> list[ForecastCheck]:
        """Take the sample the forecasters just took, return the checks it
        completes, then hold this step's forecasts for checking. Raises
        `SampleError` for a sample the forecasters would refuse too."""
        resets = self.buffer.resets
        self.buffer.push(counts, ts)
        if self.buffer.resets != resets:
            self.dropped += len(self.pending)
            self.pending.clear()
        done = []
        for entry in self.pending:
            entry[1] -= 1
        while self.pending and self.pending[0][1] == 0:
            done.append(self._check(self.pending.popleft(), ts))
        classes = ({a: c.value for a, c in prediction.predictions.items()}
                   if prediction is not None else {})
        forecasts = dict(count.counts) if count is not None else {}
        if classes or forecasts:
            self.pending.append([ts, WINDOW, classes, forecasts,
                                 (prediction.model if prediction else None,
                                  count.model if count else None)])
        return done

    def _check(self, entry: list, checked_ts: float) -> ForecastCheck:
        made_ts, _, classes, forecasts, (class_model, count_model) = entry
        # Exactly the 30 samples after the forecast: the buffer holds 30, and
        # 30 have been taken since, with no reset in between.
        observed = {self.lane_to_approach[lane]: sum(self.buffer.series(lane)) / WINDOW
                    for lane in self.buffer.lanes}
        pairs_cls = {a: {"forecast": c, "observed": classify(observed[a], self.low, self.med).value}
                     for a, c in classes.items() if a in observed}
        pairs_cnt = {a: {"forecast": v, "observed": round(observed[a], 4)}
                     for a, v in forecasts.items() if a in observed}
        return ForecastCheck(session=self.session, made_ts=made_ts, checked_ts=checked_ts,
                             classes=pairs_cls, counts=pairs_cnt,
                             class_model=class_model if pairs_cls else None,
                             count_model=count_model if pairs_cnt else None)
