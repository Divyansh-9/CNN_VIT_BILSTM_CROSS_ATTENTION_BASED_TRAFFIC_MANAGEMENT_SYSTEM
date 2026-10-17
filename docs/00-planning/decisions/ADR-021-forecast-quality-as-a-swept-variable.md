# ADR-021 — Sweep forecast quality; run the ceiling first

**Status:** Proposed · **Date:** 2026-08-21 · **Amends [ADR-009](ADR-009-ppo-forecast-surrogate.md); fixes [P52](../PRD-CHANGELOG.md)**

## Context

[P52](../PRD-CHANGELOG.md) found that `no-forecast` and `surrogate` are the same
environment: both set `use_mfstnet: false`, and nothing writes a proxy into
indices 11-14. ADR-009's central comparison has never been runnable.

The first reading of that finding was: **a proxy must be calibrated to a
measured MFSTNet accuracy, therefore the surrogate arm is blocked on S29, and
ADR-009's decoupling fails.**

**That conclusion was wrong**, and wrong in an expensive direction. It treats
forecast quality as a constant to be set. It is a variable to be swept.

## Decision

### 1. Run the ceiling before anything else

Train PPO against a **perfect** forecast — SUMO's own future congestion class at
t+60 s, uncorrupted — and benchmark it against Webster at saturation.

This is one training run, and it is the highest-value run in the whole RL track,
because it can falsify the track outright:

> **If PPO with a perfect forecast does not beat PPO with no forecast, the
> forecast contributes nothing to control and no achievable MFSTNet can change
> that.**

Nothing downstream needs to be built to learn this. It is labelled an oracle
everywhere it appears and is never reported as an achievable result — it is the
upper bound, which is exactly what makes a null result there decisive.

This step is not in the reviewer's proposal or in the first draft of ours. It
costs one run and it gates the other twenty.

### 2. Forecast quality is the independent variable

If the ceiling clears, run the surrogate arm across a **grid of degradation
levels** and report controller performance as a function of forecast quality.

The dependency inverts: S29 no longer unblocks the experiment, it **selects a
point on a curve already measured**. And the result is stronger than the point
estimate ADR-009 was going to produce — a falsifiable threshold:

> PPO beats Webster at saturation only where forecast macro-F1 exceeds **X**.

If S29 returns below X, the RL claim is cut in **Week 8 with a measured
justification** rather than discovered in Week 18 with nothing to show. Given
the cross-camera detector figure of **0.3500** and a corpus of 28 independent
segments, there is a real chance X sits above what this project can reach. That
is worth knowing early, and it is worth reporting either way (§2.5.5).

### 3. The decision rule is pre-registered, before the sweep runs

X is chosen post-hoc unless it is fixed in advance, and a threshold chosen after
seeing the curve is the cherry-picking PRD §2.5.5 forbids. So, written here
before any sweep run exists:

**X is the lowest swept forecast macro-F1 at which PPO's mean total delay beats
Webster's over 30 evaluation seeds by a paired t-test at α=0.05 with Cohen's
d ≥ 0.5.** Points that clear significance but not the effect size are reported
as "significant, not material" and do not set X.

**Go/no-go:** if the S29 fold mean lands below X, the RL contribution is
reported as *not supported at achievable forecast quality*, and the paper's
claim narrows to the vision half plus the measured threshold. That is a result,
not a failure.

### 4. Corruption is structured, not magnitude-only

A proxy read from SUMO's future state is an oracle only if it is degraded by
magnitude alone. An i.i.d. per-step class flip is simultaneously **too benign** —
independent errors average out across a decision window — and **too harsh**, in
that it manufactures jitter no real model produces.

The proxy is parameterised by three things instead:

| parameter | why |
|---|---|
| **adjacent-class-biased confusion** — MED↔HIGH dominant, LOW↔HIGH rare | congestion is ordinal; real confusions are between neighbours. §14.3 already reports `off_by_two_rate` separately for this reason |
| **lane-correlated errors** across the four approaches | all four predictions come from one frame through one camera, so their errors are not independent |
| **temporal persistence** — errors decay over a horizon rather than resampling per step | a model that is wrong about a scene stays wrong while the scene lasts |

The parameterisation is chosen so that **S29 hands back exactly this object**: a
confusion matrix, plus a lane-correlation and a persistence term measurable from
the per-fold predictions. The sweep's parameter space is directly indexable by
the eventual measurement, with no re-parameterisation step in between.

The corruption seed is recorded in the run's provenance sidecar. A degraded
forecast that cannot be reproduced is not a controlled variable.

### 5. Bounded compute

The sweep multiplies runs, so it is bounded up front:

- **saturated only** — the measured capacity knee (ADR-012). Light and
  oversaturated are run at the selected point, not across the grid.
- coarse grid first at macro-F1 ≈ **{0.33 (chance), 0.50, 0.65, 0.80, 1.00
  (oracle)}**, one training seed each, to locate the crossing;
- **30 evaluation seeds** only at the two grid points bracketing the crossing,
  and at the selected point. NFR-10's interval is spent where it decides
  something.

## Consequences

- ADR-009's three arms become four: `no-forecast`, `surrogate(q)` for swept `q`,
  `oracle`, and `mfstnet`. `oracle` is a bound and is labelled as one.
- The RL track stops being blocked on the vision track, in both directions.
- `use_mfstnet: false` on the surrogate arm is a defect to fix, not a setting.
  See [P52](../PRD-CHANGELOG.md).
- The go/no-go above is a **project-scope decision** and needs the guide, not
  only the project owner — it can narrow what the paper claims.

## Alternatives rejected

**Calibrate one proxy to the eventual MFSTNet number.** ADR-009's original
shape. It produces one point, it cannot say whether that point is near a
threshold, and it makes the RL track wait for the vision track — which is the
opposite of why the arm exists.

**Skip the surrogate and wait for `mfstnet`.** Defensible on honesty grounds and
fatal on schedule: it puts the entire RL result after S29 and after live
integration, in Weeks 17-19, with no fallback if it fails.

**Report the oracle as the result.** It is an upper bound on a quantity nothing
achieves. Reported as a bound, it is informative; reported as a result, it is
false.

---

## Amendment 1 — the scenario, the oracle, the quality axis and the outcome (2026-10-16, before any ADR-021 run)

**Decided by the project owner** (D1–D4 of
[INVESTIGATION-P52](../INVESTIGATION-P52-surrogate-arm.md)). **This is not a
faculty-guide signature.** The status stays *Proposed*, and the go/no-go above
still needs the guide. The original text above is kept unedited.

**Why this amendment exists.** P114 measured the existing constant-rate regimes
before anything was trained:

- at `saturated`, the class 60 s ahead differs from the current class on
  **6.9%** of approach-decisions;
- **HIGH never occurs**;
- persistence already scores more 3-class macro-F1 than the grid's lower
  points ask for, and with HIGH absent even a perfect forecast scores 0.667.

So the ceiling as written would test a near-constant input, and a null result
would not be the decisive result §1 says it is.

### A1.1 Scenario: `pulsed`, qualified, replacing "saturated only" in §5

- **What it is:** per-approach piecewise-constant demand with stochastic
  arrivals.
  - Levels {300, 700, 1100} veh/h/approach.
  - Segments of 120–300 s.
  - Parameter hash `8267da50f659`, frozen at design iteration 1
    (`experiments/results/scenario_pulsed/`).
- **It passed every pre-registered criterion of
  [PREREGISTRATION_P115](../../../experiments/results/scenario_pulsed/PREREGISTRATION_P115.md)**
  on its one qualification run, seeds 200–219 (P117):
  - the future class differs from now on **31.4%**;
  - LOW / MEDIUM / HIGH are **0.229 / 0.380 / 0.391** of oracle labels;
  - all 20 seeds deterministic, with demand aligned across controllers;
  - the quality grid delivered within 0.03 of nominal;
  - arrived fraction **0.938**.
- **The three constant regimes are unchanged**, and so is every result on
  them. They are not used for the forecast question, because they have no
  headroom.
- **Before any forecast-aware run**, the qualification is repeated with the
  no-forecast policy trained on `pulsed` (P115 §5.4, seeds 240–259). That
  policy then becomes the oracle's frozen policy.

### A1.2 The oracle: replayed under the frozen no-forecast policy

**Definition:** the oracle for seed *s* at decision time *t* is the §14.1 class
of each approach's count at *t* + 60 s, **in the trajectory of the frozen
no-forecast policy on seed *s***. That episode is run once and recorded every
second.

**Limitation, stated here as the owner required:**

- **It is conditioned on the frozen policy's trajectory.**
- **A forecast-aware policy changes traffic through its own actions**, so the
  oracle is **not necessarily a perfect forecast of the future under that
  policy**.
  - What it carries exactly is the exogenous demand: the same vehicles are
    loaded at the same seconds whichever policy acts (P115 Q4b, 20/20 seeds).
  - What it carries approximately is the congestion that demand produces under
    the incumbent policy. That mirrors how a deployed forecaster learns, from
    footage recorded under the incumbent controller.
- **Every evaluation that uses the oracle reports** its agreement with the
  classes actually realised under the policy being evaluated. Every result
  carries the label **oracle-input, an upper bound, not achievable**.

**Rejected: a SUMO state lookahead from the current state** (P115). It is the
"truer" oracle, and it is not usable on SUMO 1.27.1:

- about 83× slower (1.4 s per lookahead);
- two continuations from one loaded state agreed on 0.97 of classes;
- repeated loads crashed SUMO.

**The replay oracle costs about 3× the environment stepping, about +2.3 h per
500,000-step run on the team laptop (ADR-003, CPU)**
(`experiments/results/scenario_pulsed/cost.json`). It depends only on (seed,
frozen policy), so it is cached and shared by every arm with that training
seed.

### A1.3 Quality: from persistence (q = 0) to oracle (q = 1), replacing §5's macro-F1 grid

- **Construction:** P115 §3 (`simulation/forecast_quality.py`). The forecast
  is the oracle while a shared, persistent "informed" chain holds, and the
  persistence class otherwise.
- **Errors are lagging ones.** That makes them adjacent-class, lane-correlated
  and persistent in time, which is §4 satisfied without extra parameters.
- **Grid:** q ∈ {0, 0.25, 0.5, 0.75, 1.0}. q = 0 is persistence v1 (ADR-027),
  the deployable control arm; q = 1 is the oracle.
- **The nominal q is never assumed.** Each run reports its measured skill,
  (acc − acc_persistence) / (acc_oracle − acc_persistence), against the
  classes realised in its own evaluation episodes. It also reports accuracy
  and 3-class macro-F1.
  - In qualification the delivered skills were 0.00 / 0.25 / 0.52 / 0.71 /
    1.00.
  - The macro-F1 values were 0.676 / 0.758 / 0.844 / 0.905 / 1.000.
- **The curve is reported against both measured skill and macro-F1,** so a
  measured forecaster (S29) is located on it by its skill over persistence.

### A1.4 Arms, replication and seeds (D4)

| arm | slots 11–14 | role |
|---|---|---|
| `no-forecast` | absent (0.0); age 1.0 | the floor |
| `surrogate(0)` = persistence | the current class | **control**: separates foresight from an extra input channel |
| `surrogate(q)`, q ∈ {0.25, 0.5, 0.75} | constructed | the sweep: **only if the ceiling clears** |
| `oracle` = `surrogate(1)` | the replay oracle | the ceiling: an **upper bound** |
| `mfstnet` | unchanged | not runnable in SUMO |

- **Training:** every arm at **training seeds 42, 1 and 7**, independently,
  with the same 500,000 steps, hyperparameters, reward, action space and
  scenario.
  - The no-forecast arm needs three new runs on `pulsed`. The existing
    checkpoint was trained on `saturated`.
  - Training episodes use seeds from 1,000,000 upward (P115 §4), so no
    training episode shares an evaluation seed's demand.
- **Evaluation:** seeds 0–29, paired across arms. These seeds are never used
  in training or design.
- **The forecast age is real.** The oracle is refreshed every 15 s and carried
  with its true age (0, 5 or 10 s at the 5 s decisions). The age channel
  therefore means what ADR-020 says it means.

### A1.5 Outcome: mean total delay, defined exactly

**Primary: `mean_total_delay_s`**, the mean over **every vehicle loaded in the
episode** of SUMO tripinfo `timeLoss + departDelay`. "Every vehicle" includes
those still driving and those still waiting to enter when the episode ends
(`--tripinfo-output.write-unfinished` and `.write-undeparted`).
`run_episode(..., total_delay=True)` reports it, and a test shows that turning
it on moves no existing field.

**Why this, and not `mean_wait_s`:**

- §3 says "mean total delay", and SUMO's documented decomposition of a
  vehicle's total delay is exactly `timeLoss` (against free flow) plus
  `departDelay` (waiting to be inserted).
- **`mean_wait_s` is a different quantity:**
  - it counts stopped time only;
  - it counts **completed trips only**, which the runner's own docstring
    records as understating congestion exactly when congestion is worst;
  - a policy that holds vehicles back can look better on it.
- **The substitution is made here, documented, and before any run.**

**Secondary, reported and not tested:** `mean_wait_s`, `arrived_fraction`,
`starvation_events`, throughput and `max_wait_s`.

**P112 Part 2 keeps `mean_wait_s` and its own protocol.** Nothing here amends
it.

### A1.6 The ceiling decision, fixed now

**The test:**

- **Per evaluation seed,** an arm's value is the mean of `mean_total_delay_s`
  over its three trained policies.
- **The comparison:** paired differences over seeds 0–29, by paired t-test at
  α = 0.05, with Cohen's *d*, a bootstrap 95% CI (10,000 resamples) and Holm
  correction across the two tests.

**Outcomes:**

- **The ceiling clears** only if `oracle` beats `no-forecast` **and** beats
  `surrogate(0)`, each with *d* ≥ 0.5.
  - Beating `no-forecast` alone is reported as "**an input channel helps;
    foresight not shown**". It does not clear the ceiling.
- **A null at the ceiling,** on a scenario with qualified headroom, is reported
  as **"forecast information does not improve control in this simulation"**.
  That is the decisive result §1 intended.
- **Per training seed, the three replicates' directions are reported.** A
  ceiling that clears on the mean while one replicate reverses is reported as
  fragile.

**§3's X is re-expressed on the q axis:** the lowest swept q at which PPO
beats Webster on `mean_total_delay_s` by the same test, with *d* ≥ 0.5.
Webster's ADR-012 saturation-flow sweep is rerun on `pulsed` first, so the
baseline is tuned to the scenario it is compared on.

### A1.7 Prerequisites still open before any forecast-aware training

1. **Confirmation (A1.1).** It needs the no-forecast policy trained on
   `pulsed`, at seed 42.
2. **P116.** The runner and the training environment apply `keep_or_switch`
   differently:
   - the runner clamps each 5 s "keep" up to a 10 s green, and never applies
     the 90 s maximum to a run of keeps;
   - all arms, PPO and baselines alike, must be evaluated under the rules the
     policies trained under.
3. **The forecast producer in the environment,** with a test that two arms'
   observations differ only at indices 11–14 and 16. **This is what closes
   P52 in code.**
4. **`train_ppo.py` refuses an arm whose producer does not exist.**
5. **Webster's sweep on `pulsed`.**

---

## Amendment 2 — the comparators are frozen, a fixed-cycle arm is added, and the three readings are named (2026-10-17, before any ceiling result)

**Decided by the project owner**, not a faculty-guide signature. The status
stays *Proposed*.

**When this was decided:**
- items 2–5 of A1.7 were closed (P119–P122);
- the no-forecast replicates were training;
- **no forecast-aware policy existed, and no ADR-021 result existed.**

### A2.1 Baselines, frozen

- **Webster:** s = 660 pcu/h/m with 4 s start-up lost time (P122), chosen once
  on tuning seeds 400–419 by mean total delay.
- **Fixed cycle (new):** the green chosen once under
  [PREREGISTRATION_P123](../../../experiments/results/scenario_pulsed/PREREGISTRATION_P123_fixed.md),
  on the same seeds by the same rule.
  - **Why:** P122 found short fixed cycles about 2% better than the selected
    Webster on `pulsed`. Without this arm, a PPO gain over Webster could be a
    gain that any well-chosen fixed cycle also delivers.
- **Nothing is retuned after any PPO result is seen.**

### A2.2 Three readings, named before the result

A1.6's test decides between them. Each is reported in these words:

| outcome | reading |
|---|---|
| `oracle` beats `no-forecast` and `surrogate(0)`, each with *d* ≥ 0.5 | **forecast information adds control value beyond the current deployable forecast**: the ceiling clears |
| `oracle` beats `no-forecast` but not `surrogate(0)` | **a forecast input channel helps; foresight beyond persistence is not shown** |
| `oracle` beats neither | **no demonstrated control benefit from forecasts under the tested conditions** |

**Each is simulation evidence only.** None shows safe real-world signal
control, and the controller stays disconnected from signal timing.

**The baselines' role.** Webster and the fixed cycle are reported beside every
arm, with the same statistics. A1.6's X uses Webster. A gain over Webster that
the fixed cycle also delivers is named as such.

### A2.3 Evaluation parity is a gate, not an assumption

Before any ceiling evaluation:

- **Every checkpoint passes `verify_ppo_checkpoint.py`,** with:
  - `--expect-regime pulsed`;
  - its arm;
  - `--equivalence-seed 999`.
- **Parity covers the forecast arms too.** A forecast-aware policy must act
  identically in training and evaluation, with its forecast messages, on a
  non-evaluation seed.
  - Seed 999 is a **parity** check.
  - The requalification seeds 240–259 answer a different question: **whether
    the scenario stays informative under the trained policy**.

---

## Amendment 3 — the complete arm list, with a clamped demand-proportional Webster arm (2026-10-17, before any ceiling result)

**Decided by the project owner**, not a faculty-guide signature. The status
stays *Proposed*.

**When this was decided:**
- after P124 corrected P122's reading;
- while the no-forecast replicates were training;
- **before any forecast-aware policy or ceiling result existed.**

**This is the complete list, frozen.** No arm is added, removed or retuned
after any ceiling result is seen.

| arm | purpose | how it is fixed |
|---|---|---|
| no-forecast PPO | performance without forecast inputs | 3 training seeds (A1.4) |
| persistence, `surrogate(0)` | whether a simple deployable forecast helps | 3 training seeds |
| forecast-quality PPO, `surrogate(q)` up to `oracle` | the value of increasingly informative forecasts | A1.3 and A1.4. The sweep runs only if the ceiling clears |
| tuned Webster | the selected demand-responsive baseline | s = 660 pcu/h/m with 4 s lost time (P122) |
| fixed-time, 30 s green | the frozen fixed-cycle floor | P124 |
| **Webster split, clamped cycle** | the distinct controller P124 identified: a clamped cycle length with demand-proportional splits | [PREREGISTRATION_P125](../../../experiments/results/scenario_pulsed/PREREGISTRATION_P125_clamped.md): the exact clamp and split rule, selected from committed tuning data, never from evaluation seeds |

**The primary question is unchanged:** does forecast-aware control improve on
**both** no-forecast PPO and persistence (A1.6, A2.2)?

**The three baselines strengthen the operational comparison and replace
nothing.** X stays defined against the tuned Webster. A PPO gain over Webster
that either other baseline also delivers is named as such.

---

## Decision record — the go for the ceiling stage (2026-10-17)

**Who decided.** The project owner approved proceeding to the ceiling stage.
**This is not a faculty-guide signature.** ADR-021 stays *Proposed*.

The go/no-go in §3, which decides whether the RL claim narrows, remains a
guide-level decision. **The guide should be informed before any ceiling
result is cited.**

**What was established first, all recorded:**

| gate | record | result |
|---|---|---|
| scenario qualified | P117, `scenario_pulsed/qualification.json` | all six criteria passed (seeds 200–219) |
| training and evaluation reproduce each other | P116a, P119, P120 | identical in time, phase, counts and all 17 inputs, every decision, 4 regimes |
| no-forecast replicates audited and locked | P126, P127, `no_forecast_lock.json` (SHA-256 `d4ba4d57…`) | seeds 42, 1 and 7 at 18/18, including seed-999 parity; `--verify` OK |
| requalification under the trained policy | P127, `requalification.json` (SHA-256 `2ae820f8…`) | all six criteria passed (seeds 240–259); oracle ≠ persistence 0.362 |
| the oracle's frozen policy | locked seed 42, SHA-256 `8829979d7b293f19…` | used by every forecast arm |
| baselines frozen | P122, P124, P125 | Webster (660, 4 s), fixed 30 s, Webster split with a clamped cycle (600, 0 s) |
| evaluation pre-registered with its code | P128, `PREREGISTRATION_P128_ceiling.md` (SHA-256 `d16ef310…`) | committed before any forecast-aware training |

**What the go authorises:**
- a real-policy smoke test into scratch;
- six training runs: persistence (q = 0) and oracle (q = 1) at seeds 42, 1
  and 7;
- their audit and lock (P128 §4);
- **one** evaluation on paired seeds 0–29 under P128.

**What it does not authorise:**
- the quality sweep, which runs only if the ceiling clears, and still subject
  to the guide's go/no-go;
- any change to the protocol after a result is seen;
- any claim about achievable forecasts, real cameras or real signal timing.

**The controller stays disconnected from signal timing.**

**Limits carried into every result:**
- **The oracle is an upper bound,** conditioned on the frozen policy's
  trajectory (A1.2).
- **One simulated intersection, one scenario family,** with the §14.1
  thresholds.
- **The sidecars' `git_commit` is the commit at the end of training.** From
  now on, `code_at_start` records what actually ran.
- **P97a Part 2 is separate** and still pending.

### Ceiling result (P130), appended 2026-10-17

The run was made once under P128 with Amendment 1, deciding on 28 primary
seeds.

| comparison | mean difference | *d* | Holm |
|---|---|---|---|
| oracle − no-forecast | +5.41 s | +0.19 | n.s. |
| oracle − persistence | +2.38 s | +0.08 | n.s. |

**Reading: no demonstrated control benefit from forecasts under the tested
conditions.** The ceiling does not clear, so the sweep and X are not run.

**Qualifiers:**
- oracle transfer weak (0.774);
- oracle-input, simulation only;
- the PPO controllers trail both Webster arms even with no forecast, so the
  null is "not shown with this controller", not "forecasts cannot help".

**The go/no-go in §3, which narrows the RL claim, is now for the guide.**

