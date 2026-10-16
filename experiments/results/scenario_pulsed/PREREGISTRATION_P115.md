# P115 — pre-registration: qualifying a simulation scenario for ADR-021

**Committed before:**
- the scenario code exists;
- any scenario episode is generated;
- any criterion below is measured.

**Owner decisions it implements:** D1–D4 of
[INVESTIGATION-P52](../../../docs/00-planning/INVESTIGATION-P52-surrogate-arm.md),
approved 2026-10-16.

**It authorises no PPO training.** ADR-021 stays blocked until this
qualification passes and ADR-021 is amended. P97a Part 1 stays passed,
Part 2 stays pending, and the controller stays disconnected from real signal
timing.

## Why

At the existing constant-rate regimes, the class 60 s ahead differs from the
current class on 6.9% of approach-decisions, and HIGH never occurs (P114).
That makes ADR-021's ceiling a test of a near-constant input. The goal is a
scenario where the forecast question can actually be answered. The three
existing regimes are not changed.

## 1. The scenario family: `pulsed`

The scenario adds demand to the existing network, vehicle types, turn ratios
and signal rules. Nothing else changes.

- **Per-approach demand:** each approach's demand is piecewise constant over
  the episode, drawn independently per approach.
  - **Segments:** each segment lasts a whole number of seconds drawn uniformly
    from [`d_min`, `d_max`].
  - **Levels:** each segment's level (veh/h/approach) is drawn uniformly from
    `levels`, and never repeats the previous segment's level.
- **Arrivals:** stochastic, as SUMO `probability` flows: per second, per turn
  movement, with probability `level × turn_share / 3600`. The episode seed is
  SUMO's `--seed`.
- **The schedule** is drawn from `numpy.random.default_rng([seed, 115])`,
  independent of SUMO's RNG. One seed is therefore one schedule plus one
  arrival realisation.
- **Parameters** live in `simulation/configs/scenarios.yaml` (NFR-16), within
  these bounds fixed now:
  - `levels` ⊂ [300, 1200] veh/h/approach: light 400 up to past the
    oversaturated 1000 (S33);
  - 60 ≤ `d_min` ≤ `d_max` ≤ 600 s.

## 2. The oracle (D2): replayed, not looked ahead

**Definition:** the oracle for seed *s* and decision time *t* is the
congestion class, under §14.1 thresholds, of each approach's count at
*t* + 60 s, in **the trajectory of the frozen no-forecast policy run on seed
*s***. This is the realised future of that policy's trajectory. It is produced
by running that episode once and recording counts at every decision, then
reading them back.

**Limitation, to be carried into ADR-021:**
- The oracle is conditioned on the frozen policy's trajectory.
- A forecast-aware policy changes traffic through its own actions, so the
  oracle is **not** the perfect forecast of the future under that policy.
- How far the two diverge is measured and reported in every evaluation that
  uses the oracle.

**Why not a SUMO state lookahead.** It was proposed in P114, then rejected on
measured evidence. A feasibility spike on the constant `saturated` regime,
with a fixed program and no scenario data (SUMO 1.27.1), found:
- **Too slow:** `saveState`/`loadState` costs about **1.4 s per lookahead**;
  an 1800 s episode took 522 s, against 6.3 s without it (about 83×).
- **Not reproducible:**
  - Even at `--save-state.precision 12` with `--save-state.rng`, two
    continuations from the same loaded state agreed on **0.97** of classes
    and **0.67** of counts.
  - The default state precision is 2 decimals.
- **Crashes:** repeated backward loads crashed SUMO in three configurations:
  - a second instance;
  - a second instance with `clearPending`;
  - a second instance with `--route-steps 0`.

**The replay oracle needs determinism, which is verified, not assumed** (Q4).

## 3. Forecast quality (D3): from persistence to oracle

For quality *q* ∈ [0, 1] the forecast is constructed from two things:

- **The oracle class O_t(a)** from §2;
- **The persistence class P_t(a):** the current count's class. The policy
  could compute this itself; it is persistence v1's rule (ADR-027).

The construction:

- **The "informed" indicator I_t** is one binary process shared by all four
  approaches, which makes errors lane-correlated.
  - It is a two-state chain over decision steps: at each step it is redrawn as
    Bernoulli(*q*) with probability 1 − ρ, and kept otherwise.
  - ρ = exp(−5 / 60): a 60 s time constant over the 5 s decision interval,
    which makes errors persistent in time. The stationary share informed is
    *q*.
- **The forecast is F_t(a) = O_t(a) if I_t, else P_t(a).**
  - q = 0 is persistence. That is the deployable baseline and the control
    arm (INVESTIGATION-P52 §4).
  - q = 1 is the oracle.
- **Errors therefore have ADR-021 §4's three properties without extra
  parameters.** A wrong forecast is a lagging one ("the future is like now"),
  so it is:
  - adjacent-class (60 s class changes are adjacent);
  - lane-correlated;
  - persistent in time.
- **The corruption RNG** is `numpy.random.default_rng([seed, round(1000 q),
  52])`, recorded in provenance.
- **Measured skill** = (acc(F) − acc(P)) / (acc(O) − acc(P)). It is computed
  against targets from **a separate simulation run** of the same seed, never
  from the oracle array the forecast was built from. 3-class macro-F1 and
  accuracy are reported beside it.
- **Grid:** q ∈ {0, 0.25, 0.5, 0.75, 1.0}.

## 4. Seeds

| use | seeds |
|---|---|
| design iterations | 300–309 |
| qualification, attempt 1 (run once) | 200–219 |
| a later attempt, if attempt 1 fails and the owner approves a redesign | 220–239 |
| confirmation with the scenario-trained no-forecast policy | 240–259 |
| PPO training episodes on this scenario | 1,000,000 + 10,000 × training seed + episode index |
| evaluation (benchmark, ADR-021, P112 Part 2) | 0–29: **never used here** |

The training-episode rule is new. Today an episode's seed is the training seed
plus the episode index, so training seeds 1 and 7 (D4) would train on
evaluation seeds 1–29. For a scenario where the seed is the demand, that is
test leakage. The rule applies only to scenario regimes, so the existing
checkpoint's training stays reproducible.

## 5. Procedure

1. **Design** on seeds 300–309. At most **5 iterations**, each logged in full
   (parameters and every criterion) to `design_log.json`, kept and committed.
   - Iteration 1 is `levels` {300, 700, 1100}, `d_min` 120, `d_max` 300.
   - Later iterations may change only §1's parameters, within the bounds.
   - The first iteration meeting every criterion on the design seeds is
     frozen: its parameters and their hash are committed **before**
     qualification.
   - If none of the 5 does: stop and report.
2. **Qualification, run once** on seeds 200–219, with the frozen parameters.
   - **The frozen policy** is `ppo_no-forecast_saturated_keep_or_switch_seed42.zip`
     (sha256 `a7f06ba8…`), the only no-forecast policy that exists.
   - **The environment** is `TrafficSignalEnv`, `keep_or_switch`, 5 s
     decisions, 1800 s: the dynamics the ceiling would train under.
   - **On failure:** stop, report, and redesign only with owner approval.
3. **Cost benchmark** (D2): 3 episodes on design seeds. Report the wall time
   of an ordinary episode, and of one that also builds its oracle by replay.
   Project the cost onto the planned training and evaluation runs.
4. **Confirmation, later** (seeds 240–259). It runs after the no-forecast
   policy has been trained on this scenario at training seed 42, which is
   allowed once qualification passes. The same criteria are rerun with that
   policy as the frozen policy, and **it becomes the oracle's policy**. On
   failure, nothing forecast-aware is trained.

## 6. Criteria (all must hold)

All are computed over approach-decisions (4 per decision step) at the
qualification seeds, under the frozen policy.

| | criterion | threshold |
|---|---|---|
| Q1 | **Headroom.** Share where the oracle class differs from the persistence class | ≥ 0.20 |
| Q2 | **Class coverage.** Each of LOW, MEDIUM and HIGH as a share of oracle labels | ≥ 0.10 each |
| Q3 | **Not recoverable from the state.** A logistic regression on the policy's own inputs (4 counts, 4 queues, phase, approach one-hot), fitted on the design seeds' episodes, disagrees with the oracle on the qualification seeds | ≥ 0.10 |
| Q4 | **Determinism.** (a) Rerunning each qualification seed gives identical counts at every decision. (b) The exogenous demand (vehicles loaded per second) is identical under the frozen policy and `Fixed(30)` on the same seed | 100% (a) and 100% (b) |
| Q5 | **The grid is attainable.** For each grid *q*, \|measured skill − *q*\| ≤ 0.05; 3-class macro-F1 strictly increases along the grid; and macro-F1(1) − macro-F1(0) ≥ 0.15 | all three |
| Q6 | **Not breakdown.** Mean arrived fraction (arrived ÷ departed) under the frozen policy | ≥ 0.85 |

**Reported, not tested:**
- the per-class transition table;
- per-approach shares;
- `Fixed(30)`'s arrived fraction;
- the mean schedule level.

Q4(b) is what licenses the replay oracle's claim that **demand is aligned
across controllers**: the exogenous part of the oracle is the same world
whichever policy acts.

## 7. Not in scope here

- **The ADR-021 outcome field.** The amendment defines it, after this
  qualification, and documents and justifies any departure from "mean total
  delay".
- **Any PPO training.**
- **The env/runner `keep_or_switch` mismatch** (recorded separately, P116).
  It must be resolved before ADR-021's evaluation, not before this
  qualification.
