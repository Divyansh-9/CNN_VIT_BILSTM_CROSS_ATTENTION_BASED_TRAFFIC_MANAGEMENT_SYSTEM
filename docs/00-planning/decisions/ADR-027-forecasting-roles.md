# ADR-027 — Two forecasting roles: persistence for the congestion class, ridge for the next-minute count

**Status:** Accepted by the project owner 2026-10-16. This is **not a faculty-guide signature**. · **Date:** 2026-10-16 · **Amends [ADR-026](ADR-026-mfstnet-runs-on-the-edge.md)'s deployed forecaster, and with it PRD §7's statement that MFSTNet produces the prototype's predictions** · Evidence: P103, P104, P105 in the [changelog](../PRD-CHANGELOG.md)

## Context

ADR-026 put MFSTNet on the edge, and the project owner was explicit that
MFSTNet was not to be **silently** replaced by a simpler model. Four measured
results since then bear on which forecaster the prototype should serve:

| result | what it measured |
|---|---|
| P100 | on hours it never saw, the vision model beat neither a time-of-day prior nor persistence, and its LOW recall collapsed to 0.058 |
| P101 | on those hours, counts alone beat vision by 0.188 macro-F1 (exploratory: the labels are the detector's own counts, A32) |
| P103 | a count forecaster fitted on NE 8th carried NE 8th's traffic level into new cameras: forecasts +0.7 vehicles high, −0.222 against persistence. **Persistence** (0.706) was the best method measured there, and became the prototype's class forecaster (P104) |
| P105 | a **level-free** ridge model, frozen before any untouched footage was counted, forecast the next minute's count better than persistence on three untouched cameras: MAE 0.748 against 0.972, +0.224 [+0.181, +0.271]. Its classes were **not** significantly better: +0.016 [−0.002, +0.036] |

The two outputs have different evidence behind them. Merging them into one
"forecaster" would claim more than either result shows.

## Decision

The prototype publishes **two separate forecasts, each with one role:**

| output | model | contract | basis |
|---|---|---|---|
| **congestion class**, next 60 s (LOW / MEDIUM / HIGH) | persistence v1, `persistence@2431c6641b9c` | `CongestionPrediction` on `stms/{id}/congestion/prediction` | P103/P104: best transferable class forecaster measured |
| **next-minute vehicle count** per approach | ridge v1, `ridge@73532968dcf2` | `CountForecast` on `stms/{id}/count/forecast` | P105: count MAE significantly better than persistence on untouched footage |

Rules that keep the two apart:

1. **Separate topics, payload types and tables.**
   - A count can never be decoded, stored or served as a class.
   - The contract's model-id patterns are disjoint: `ridge@` is refused for a
     class, and a class model is refused for a count.
2. **Every response names its role**, for example
   `next_minute_count (ridge)` or `congestion_class (persistence)`, together
   with the model id, the age and a `stale` flag. A forecast older than its
   60 s horizon is labelled stale, not served as current.
3. **Missing is not zero, and not LOW.**
   - An approach the edge cannot forecast is **absent** from the count payload
     and listed in `missing_approaches`.
   - Zero vehicles remains a real forecast.
   - The edge buffers refuse a sample that misses a lane, contains an
     implausible count, or arrives out of order. A time gap over 3 s resets
     the window rather than joining two stretches of traffic.
4. **Neither forecast feeds signal timing.**
   - The PPO state contract, and its 0.0-for-missing at indices 11–14, is
     unchanged and unconnected (P97a).
   - A forecasting result is not evidence that a control policy is safe or
     beneficial. That needs its own evaluation.
5. **MFSTNet is retained, not deleted.**
   - Its verified-graph edge path (`edge/forecaster.py`) still exists and
     still publishes under `[A-H]@…`.
   - The heartbeat's `mfstnet_active` reports only MFSTNet output.
   - The vision claim C2 stays open until it can be scored against
     independently verified future labels.

## Consequences

- **The prototype's forecasts are the two measured best, each in its own
  role.** The model the project is named after is not what serves them. That
  is stated here openly, as ADR-026 required of any replacement.
- **Their scope is the evidence's scope.** Two Bellevue days, four cameras
  that took part in P103/P105, detector-derived labels, and ridge's count
  result only on the three P105 cameras.
- **A dashboard is not built** (ADR-008). These outputs are what a dashboard
  would read, through `/prediction/{id}/latest` and
  `/count_forecast/{id}/latest`. ADR-014's two-panel rule applies when one is
  built.
- **The larger Option A study is deferred.** It is revisited only if class
  improvement becomes a requirement or the deployment needs stronger
  evidence, and then as a new, separately pre-registered experiment.

## Rejected

- **Ridge for both roles.** Its class gain was not significant. Promoting it
  there would be choosing on a point estimate.
- **Merging both into one payload.** A consumer could then read a count as a
  class, or a class as a count, which is exactly the confusion the project
  owner asked to prevent.
- **Zero-filling absent approaches in the count forecast.** That repeats the
  P97a defect, missing read as low, in a new place.
