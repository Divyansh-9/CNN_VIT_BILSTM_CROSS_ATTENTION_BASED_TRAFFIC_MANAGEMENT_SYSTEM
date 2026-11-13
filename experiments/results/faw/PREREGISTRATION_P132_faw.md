# P132 — pre-registration: forecast-assisted Webster split (FAW), design, feasibility and power

**Committed before** any FAW episode is run, and so before any feasibility or
power number exists.

**Owner approval (2026-10-17):** design (C0), feasibility (C1) and power (C2)
**only**. The study starts before the guide replies to MEMO-2026-10-17.

**Not authorised here:**
- the evaluation (C4);
- freezing its pre-registration (C3);
- any change to ADR-023 or `CLAIMS.yaml`.

**P130 stays frozen, and P131 authoritative.** Seeds 0–29 play no part in
this study.

## 1. The question

Can a next-minute vehicle-count forecast improve an already competitive
signal-timing controller?

**This is a new question.** It is not a reanalysis of P130, and not a rescue
of it.

## 2. Arms (frozen)

All arms run the same controller: `simulation.webster.Webster` at the P125
configuration.

| setting | value |
|---|---|
| saturation flow | 600 pcu/h/m |
| start-up lost time | 0 s |
| cycle | clamped to [32, 192] s |
| green split | demand-proportional, `effective green × y_phase / Y` |
| green bounds | [10, 90] s |

Every other parameter keeps its committed default. **The arms differ only in
the per-approach demand the rule reads:**

| arm | demand | source |
|---|---|---|
| **W-now** (baseline) | the counts observed at the decision | as today. Persistence is identical to it by construction |
| **W-oracle** | the realised **mean count over (t, t + 60 s]** per approach, in **W-now's own trajectory** on the same seed | `OracleMeanCount`: the replay is under the baseline itself, so W-oracle departs from W-now only through the forecast |
| **W-ridge** | the frozen ridge v1 (`ridge@73532968dcf2`, SHA-256 checked), applied unchanged to the last 60 samples, 2 s apart, of the controller's own per-approach counts | `RidgeCountDemand`. **Before 118 s of history, it reads the observed counts** (W-now's input) |

**There is no blended arm.** The plan's optional W-blend is dropped now,
before any data, to avoid a forking path.

**Same demand everywhere.** Arms on one seed face identical demand
realisations: `pulsed` (hash `8267da50f659`) with SUMO `--seed`. Loaded
vehicles are aligned across controllers (P115 Q4b).

**What the oracle means.**
- It is W-now's realised future.
- Once W-oracle's decisions differ, its own future differs, so the oracle is
  exact only for W-now's trajectory.
- Every run reports its forecast's mean absolute error against the
  next-minute mean that **that run** realised (`transfer_report`), with
  persistence's error beside it.

## 3. Episodes

- **Harness:** `run_episode`, `pulsed`, 1800 s, the sublane model at 0.8,
  `total_delay=True`.
- **Per-second record:** every simulated second, including interphase
  seconds (the P132 runner hook). It is read-only; a test shows it changes no
  outcome.
- **The oracle's source:** a W-now record of 1875 s on the same seed. Its
  first 1800 s are identical to the 1800 s W-now episode, which is
  deterministic.

## 4. C1 — feasibility gate (run once)

**Seeds:** design seeds **600–609**.

**Procedure:**
- Run W-now on each seed for 1875 s, recording every second.
- **Decisions counted (the denominator):** every W-now decision at
  *t* < 1800 s, across all ten seeds.
- For each one, take the phase *p* W-now chose, and compute:
  - `green_now`: the green W-now returned;
  - `green_oracle`: `Webster.green_for(next-minute mean at t, p)`, by the
    identical, pure arithmetic. `green_now` is checked to equal
    `green_for(observed counts, p)` on every decision; the gate refuses to
    report if it ever differs;
  - `green_ridge`: the same, with ridge's forecast, on decisions where ridge
    is ready.

**A changed split** is a decision where |`green_oracle` − `green_now`| ≥ 1 s,
using the integer greens the rule returns.

**Gate:** pass if changed oracle splits ÷ decisions counted ≥ **0.10**.

**On failure the study STOPS.**
- The controller is not redesigned around the result.
- The stop is recorded as the finding: "the timing rule's decisions are
  insensitive to perfect next-minute counts".

**Reported, not gating:**
- the share changed by ≥ 3 s;
- the mean |Δ green|;
- the ridge figures, over its ready decisions, with its readiness share;
- the oracle's and ridge's MAE against the realised next-minute mean,
  persistence's MAE, and the clamp rate.

## 5. C2 — power gate (run once, only if C1 passes)

**Seeds:** pilot seeds **610–639** (30).

**Procedure:** for each seed, run W-now and W-oracle, paired. W-ridge is run
as descriptive only.

**The frozen procedure for the later evaluation** (§6) is two-sided paired
t-tests with Holm across two tests. So the planning α is **0.025**, Holm's
first threshold.

**The quantities:**
- δ = **2%** of the pilot's mean W-now total delay, the minimum effect of
  interest;
- σ = the SD of the paired differences (W-oracle − W-now);
- **n** = the smallest number of pairs giving power ≥ **0.80** for a
  two-sided paired t-test at α = 0.025 against effect δ / σ, by the
  non-central t (`scipy.stats.nct`).

**Gate:**
- **if n > 200, the study STOPS:** not adequately powered within its budget;
- otherwise the evaluation size is **max(30, n)**.

**Pilot effect estimates are reported and labelled "pilot: not evidence".**
They are used for **n only**. They change no arm, rule, metric or threshold.

## 6. The evaluation protocol (frozen now; C4 not authorised)

- **Seeds:** **700 … 700 + N − 1**, with N from C2. Paired: every arm on every
  seed. These are fresh seeds, not used anywhere else.
- **Primary tests (2):**
  - W-oracle − W-now;
  - W-ridge − W-now.

  Each is computed on `mean_total_delay_s`:
  - a two-tailed paired t-test (`experiments.statistics`);
  - Cohen's *d*;
  - a bootstrap 95% CI (10,000 resamples, seed 42).

  **Holm** is applied across the two.
- **"Improves"** means all three of:
  - Holm-significant;
  - a negative mean difference;
  - **a magnitude ≥ 2% of W-now's mean total delay** (the minimum effect of
    interest).
- **The operational gate:**
  - the arm's arrived fraction is at least 0.85;
  - its mean starvation is no more than W-now's plus 1.0 per episode.
- **The readings, exactly one of which is reported:**

  | W-oracle | W-ridge | reading |
  |---|---|---|
  | improves (and passes the gate) | improves (and passes the gate) | **an achievable count forecast improves this competitive controller, in simulation** |
  | improves | does not | **forecast quality is the limiting factor** |
  | does not | does not | **no demonstrated benefit from foresight with this timing rule under the tested conditions.** This is not proof that no controller can benefit |
  | does not | improves | inconsistent, reported as measured |

- **Qualifiers:**
  - **harm:** a Holm-significant **increase** of at least the minimum effect;
  - the forecast's MAE against realised, beside persistence's;
  - "simulation evidence only; the controller is disconnected from signal
    timing".
- **Reported for every arm:**
  - mean total delay with its CI;
  - mean wait;
  - arrived fraction;
  - starvation;
  - clamp rate;
  - ridge readiness.
- **Missing data:**
  - an episode that raises is re-run once, identically;
  - a second failure stops the evaluation;
  - **no seed is dropped, replaced or partially analysed.**

**Changes after C2.** Before C4, a C3 commit can change **N only** (from C2)
and add the evaluation script with its tests. Anything else is a new
amendment, with its reason, made before any evaluation episode.
