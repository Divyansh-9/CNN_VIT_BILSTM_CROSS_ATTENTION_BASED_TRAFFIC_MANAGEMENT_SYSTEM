# P128 — pre-registration: the ADR-021 ceiling experiment on `pulsed`

**Committed before:**
- any forecast-aware policy is trained;
- any ceiling result exists.

**Implements** ADR-021 Amendments 1–3 (A1.6, A2.2, A2.3, A3).

**The code is `scripts/ceiling_eval.py`, committed with this file.** Its
`decide()` is the rule below, written as code, and it is tested on synthetic
data in `tests/test_ceiling_eval.py`. Where this text and that code disagree,
the disagreement is a defect to report, not a choice to make after the
result.

**Owner approval (2026-10-17):** this pre-registration, a smoke test, and the
ADR-021 decision record, all committed before the six training runs start.
**Not a faculty-guide signature.**

## 1. The question

Does forecast-aware PPO, given the **oracle** forecast (q = 1), lower mean
total delay against **both**:
- PPO with no forecast;
- PPO with the persistence forecast (q = 0)?

**The oracle is an upper bound.** It is the frozen no-forecast policy's own
future (A1.2), so every result here is **oracle-input** and simulation
evidence only. **It is not evidence that a deployable forecast achieves the
same, nor that real signals can be controlled safely.**

## 2. Arms (frozen, A3)

| arm | controller | policies |
|---|---|---|
| no-forecast | `PPOController`, slots absent | the 3 locked replicates (seeds 42, 1, 7; `no_forecast_lock.json`) |
| persistence | `PPOController` fed by `Surrogate(q = 0)` | 3 replicates, trained here |
| oracle | `PPOController` fed by `Surrogate(q = 1)` | 3 replicates, trained here |
| tuned Webster | `Webster(s = 660, lost 4 s)` | P122 |
| fixed 30 s | `Fixed(green_s = 30)` | P124 |
| Webster split, clamped cycle | `Webster(s = 600, lost 0 s)` | P125; its clamp rate is reported |

The intermediate qualities (0.25, 0.5, 0.75) are trained **only if** the
ceiling clears (A1.4). §3's X belongs to that sweep, and is not computed here.

## 3. Training of the six forecast replicates

- **Runs:** `train_ppo.py --arm surrogate --quality {0.0, 1.0} --regime pulsed
  --action-space keep_or_switch --seed {42, 1, 7}`.
- **Hyperparameters and steps:** those of `ppo_config.yaml`, 500,000 steps.
- **Seeds:** training-episode seeds come from P115 §4, disjoint from the
  evaluation seeds.
- **The oracle** replays the locked seed-42 no-forecast policy (SHA-256
  `8829979d…`). It is cached per episode seed and shared between the two arms
  at each training seed.
- **No arm is retrained or substituted** after any of its results is seen.

## 4. Gate before evaluation: the forecast audit (`ceiling_eval.py audit`)

**Every one of the six must pass all of the following:**
- arm `surrogate`, with its quality recorded both in the sidecar and in the
  producer;
- `pulsed`, `keep_or_switch`, not a smoke run, and 500,000 steps (in the
  sidecar and in the model's own count);
- sublane 0.8 and the current observation contract;
- **the producer's frozen policy SHA-256 equals the locked seed-42's**;
- at least 500,000 audited observations;
- the producer sent messages, and **its informed share equals q exactly** for
  q ∈ {0, 1};
- **clean code at launch** (`code_at_start`);
- architecture and hyperparameters equal `ppo_config.yaml`;
- **seed-999 parity with forecast messages:** identical behaviour in training
  and evaluation over a full 1800 s episode, at every decision, on all 17
  inputs.

**The lock.** Only if all six pass is `forecast_lock.json` written,
atomically.

**The evaluation itself refuses to start** unless all three of these hold:
- both locks re-verify (every checkpoint and config re-hashed);
- this file is committed unchanged;
- no result exists.

## 5. Evaluation

- **Episodes:** `run_episode`, `pulsed`, 1800 s, the sublane model at 0.8,
  `total_delay=True`.
- **Paired evaluation seeds:** 0–29, the same for every arm and policy. They
  are used nowhere else.
- **Forecast arms:** fed by `ForecastFeeding`, with a fresh producer per
  episode, made by the same rule as in training. Parity is established by §4.
- **Episode failure:**
  - an episode that raises is re-run **once**, identically;
  - if it fails again, **the whole evaluation stops** and writes
    `ceiling_FAILED.json`;
  - **no seed is dropped, replaced or analysed partially.**
- **Missing data:** any missing (arm, policy, seed) breaks the pairing, and
  the analysis refuses it.

## 6. The decision (fixed now)

**Outcome:** `mean_total_delay_s`, as defined in A1.5. Per evaluation seed, a
PPO arm's value is the mean over its three policies.

**The primary tests (2):**
- oracle − no-forecast;
- oracle − persistence.

Each is computed over the 30 paired seeds:
- a two-tailed paired t-test (`experiments.statistics`);
- Cohen's *d* on the differences;
- a percentile bootstrap 95% CI of the mean difference (10,000 resamples,
  seed 42).

**Holm** is applied across the two tests at α = 0.05.

**"Beats"** means all three of:
- Holm-significant;
- a negative mean difference;
- *d* ≤ −0.5.

**The operational gate** passes if both:
- the oracle arm's mean arrived fraction is at least 0.85;
- its mean starvation events per episode are no more than the no-forecast
  arm's plus 1.0.

**The readings, exactly one of which is reported:**

| condition | reading |
|---|---|
| beats both, and the operational gate passes | **forecast information adds control value beyond the current deployable forecast: the ceiling clears** |
| beats both, but the operational gate fails | lower delay than both comparators, but the operational gate fails: the ceiling does not clear |
| beats no-forecast only | **a forecast input channel helps; foresight beyond persistence is not shown** |
| beats persistence only | inconsistent, reported as measured: the ceiling does not clear |
| beats neither | **no demonstrated control benefit from forecasts under the tested conditions** |

**Qualifiers, attached whenever they apply:**
- **fragile:** the ceiling clears on the mean, but some training seed's own
  oracle-minus-comparator mean difference is positive;
- **oracle transfer weak:** the oracle arm's mean realised accuracy (below)
  is under 0.80;
- **harm:** a primary comparison is Holm-significant in the oracle's
  **disfavour** with *d* ≥ 0.5;
- **always:** "oracle-input: an upper bound, not achievable; simulation
  evidence only".

## 7. Reported, not decided on

**For every arm:**
- mean total delay with its bootstrap CI;
- mean wait;
- arrived fraction;
- starvation events;
- throughput;
- maximum wait;
- clamp rate (for the Webster arms).

**The secondary comparisons:** each PPO arm against each of the three
baselines, with the same statistics, **unadjusted and labelled descriptive**.
A PPO gain over Webster that another baseline also delivers is named as such.

**The oracle against what actually happened (A1.2), for the forecast arms:**
- **agreement at decision times:** the oracle's class for time *t* against the
  realised class at *t*;
- **realised accuracy at each message's own target time, *t* + 60 s,** for
  three forecasts:
  - the forecast actually sent;
  - the oracle;
  - persistence.

  Targets falling in an interphase second, which the runner does not observe,
  are skipped and counted;
- **the producer's informed share.**

**The per-training-seed differences:** the three replicates' directions, for
both primary comparisons.

**All rows** go to `ceiling_runs.csv`, with a provenance sidecar. All
statistics go to `ceiling_stats.json`. `restat` re-derives them from the CSV
alone.

## 8. What this cannot show

- That any **achievable** forecast helps. That is the sweep's question, asked
  only if the ceiling clears.
- Anything about real cameras, real traffic, or real signal timing. **The
  controller stays disconnected from signal timing.**
- Anything about **P97a Part 2**, which keeps its own protocol and its
  `mean_wait_s` outcome.
