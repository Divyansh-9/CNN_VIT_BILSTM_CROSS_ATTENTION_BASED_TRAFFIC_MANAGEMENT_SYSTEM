# P112 — P97a step 5: the fail-safe gate under injected faults, in two parts. Fixed before any run

Written 2026-10-16, after P110 and P111, and approved by the project owner as
a two-part protocol. **Nothing in either part has been run.**

**The controller stays disconnected from real signal timing in both parts.**
Everything here runs in SUMO.

The system under test is the ADR-020 layout as amended, `forecast_slots` and
`ForecastGate` (`simulation/forecast_state.py`, commit `8c3413a`), with the
no-forecast policy and Webster as its fallbacks.

## Part 1 — fault-handling integrity (runs after the retrain finishes and passes its own checks)

### What it establishes

That the gate and the encoder handle faults exactly as ADR-020 (as amended)
specifies. **Not** forecasting accuracy, and **not** policy safety or benefit.

### The forecast stream, and why it is not called an oracle

- **The stream:** at each decision, the class of SUMO's **current** per-approach
  vehicle count. Counts are taken from the same lanes the runner reads, classed
  with `spec.yaml`'s `congestion.low_max: 4` and `med_max: 15` (LOW < 5, MEDIUM ≤ 15, HIGH
  above).
- **It is not a perfect forecast.** That would need the future state, and the
  future depends on the controller's own next decisions. Defining that
  lookahead is ADR-021's and P52's work, and Part 2 inherits it.
- **Its content does not matter here.** Every Part 1 invariant is about
  **validity and handling**, never about whether a class is right, so a
  ground-truth-now stream is sufficient.
- **It is labelled "ground-truth-now (not a forecast)"** everywhere it is
  reported.

### Controllers, wired through the runner's `Controller` interface

- **`GatedController`** passes each observation, plus the injected forecast
  message, to `ForecastGate.check`:
  - **`webster`:** the frozen ADR-012 Webster (`s = 750`, the benchmark's)
    decides;
  - **`no_forecast`:** the retrained no-forecast PPO checkpoint decides, on the
    17-dim state built by `forecast_slots` with no message;
  - **`forecast`:** a **probe** decides.
- **No forecast-aware policy exists yet (P52), so the probe stands in for
  one.** It records the exact inputs and the 17-dim state it was handed, then
  delegates the action to the no-forecast policy so that traffic keeps
  running. The probe is how invariant I1 is observed.
- **Ground truth is independent of the gate.** The harness keeps its own
  record of what it injected at each decision, and the invariants compare the
  gate's behaviour against that record, never against the gate's own reasons.

### Injection schedule (fixed)

- **Episodes:** 5. Seeds 42, 1, 7, 13 and 21 (PRD §14.4's list), regime
  `saturated`, 1800 s, `keep_or_switch` with a 5 s decision interval.
- **The fault RNG** for an episode is `random.Random(10_000 + seed)`,
  independent of SUMO's seed.
- **A healthy message** has all four classes, with its age drawn uniform in
  [0, 8] s.
- **Message and forecast faults** (F1–F4) are drawn independently for each
  decision. A burst continues for its drawn length, and the drawn faults are
  applied together.
- **Count and queue faults** (F5, F6) are drawn independently too, and take
  precedence: Webster decides.

| fault | rate per decision | detail | expected decider |
|---|---|---|---|
| F1 missing message | 10% start a burst | burst length uniform {1 … 6} decisions | `no_forecast` |
| F2 stale message | 8% | age uniform (10.0, 30] s, strictly over the bound | `no_forecast` |
| F2b boundary ages | 2% at exactly 10.0 s, 2% at 9.9 s | — | `forecast` if nothing else is wrong (the bound is inclusive) |
| F3 approach dropout | 10% | one or two approaches, chosen uniformly, removed from the message | `no_forecast` (partial coverage is not enough) |
| F4 invalid class | 3% | one approach's class replaced by `"MED"`, `""` or `None` (equal thirds) | `no_forecast` |
| F5 corrupt count | 5% | one approach's count missing, `-1` or `NaN` (equal thirds) | `webster` |
| F6 corrupt queue | 2% | one approach's queue missing, `-1` or `NaN` (equal thirds) | `webster` |

### Recovery, defined

A message is **complete, fresh and valid** when all of these hold:

- it is present;
- its age is finite and at most 10 s, measured on the server-side clock the
  harness simulates;
- **all four** approaches carry a class in {LOW, MEDIUM, HIGH};
- the same decision's counts and queues are present, finite and non-negative
  for all four.

**Age is per message (ADR-020 as amended), and there are no per-approach
timestamps.** **No approach is ever carried forward from an earlier
message.** A message is judged only on its own contents, so recovery cannot
assemble a complete forecast from parts of different messages.

### Invariants — strict

**Any single violation fails Part 1. Nothing is averaged across seeds.**

| id | invariant |
|---|---|
| I1 | every probe invocation happened at a decision whose injected message was complete, fresh and valid |
| I2 | in every state built, each class slot is in {1/3, 2/3, 1} **exactly when** that approach had a valid class in the delivered message, and **exactly 0.0** otherwise; slot 16 = `min(age, 10) / 10` with a message and 1.0 without |
| I3 | every change of decider appears in `ForecastGate.log` with at least one reason, and the number of logged changes equals the number of observed changes |
| I4 | every decision with an F5 or F6 fault was decided by Webster, and the action applied was Webster's |
| I5 | after any fault, the first `forecast` decision falls on a decision whose message is complete, fresh and valid; F2b's ages of 10.0 and 9.9 s are accepted when otherwise valid |
| I6 | the episode completes: no exception escapes the controller, and the runner's safety clamps still apply |

**Reported for each seed:** decisions by decider, faults by type, the number
of probe invocations, the transition log, and every violation in full. Part 1
**passes only if all five seeds show zero violations.**

## Part 2 — non-inferiority under faults (frozen now; run only when eligible)

**Eligibility, all required, and otherwise recorded as PENDING, not passed:**

- P52's `surrogate` arm is implemented;
- ADR-021's perfect-forecast ceiling run has been done;
- a forecast-aware PPO policy has been trained on the amended 17-dim layout.

The forecast stream is then ADR-021's. If that is an oracle (SUMO's realised
future), every result is labelled **oracle-input**, because a real deployment
forecast is worse.

### Design

- **Arms:**
  - `gated`: `GatedController` with the forecast-aware policy, the
    no-forecast policy and Webster;
  - `baseline`: the no-forecast policy alone, with Webster when counts are
    invalid, as the gate would do.
- **Seeds:** 0 … 29, the benchmark's 30, paired. Arms share a seed's demand
  and its fault draws.
- **Conditions (3):**
  - **C0:** no faults;
  - **C1:** the Part 1 schedule;
  - **C2:** heavy, with F1 at 50% and bursts uniform {1 … 12}, everything else
    as C1.

### Outcomes and margins (fixed now)

| outcome | definition | non-inferiority margin (gated − baseline) |
|---|---|---|
| delay | `mean_wait_s`: mean per-vehicle waiting time over completed trips (runner, tripinfo) | **+5% of the baseline's mean `mean_wait_s` in that condition** |
| starvation | `starvation_events`: approach-red stretches reaching 180 s per episode (runner, ADR-011) | **+1.0 event per episode** |

### Statistics

- **The test:** for each outcome and condition, the paired difference
  `gated − baseline` over the 30 seeds, with a bootstrap of the mean
  difference: 10,000 resamples of seeds, `random.Random(0)`, percentile
  interval.
- **Non-inferior** means the **upper bound of the one-sided 95% interval** (the
  95th percentile of the bootstrap) is below the margin.
- **Six tests** (2 outcomes × 3 conditions) under **Holm**: each test's
  one-sided p-value is the bootstrap share at or above the margin, compared
  with Holm's thresholds at α = 0.05.
- **Also reported, not tested:** paired mean differences with two-sided 95%
  CIs, Cohen's d, throughput and `max_wait_s` (NFR-10).
- **Part 2 passes** only if **all six** tests show non-inferiority. A failure
  is reported as measured. **No margin, outcome or condition changes after any
  Part 2 result is seen.**

### What Part 2 can and cannot show

**It can show** that the gated system is not meaningfully worse than the
no-forecast baseline under these failures. That is safety evidence for the
fallback design.

**It cannot show** that forecasts help, which is ADR-021's question, nor
anything about real cameras or real signal timing.
