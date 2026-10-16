# P52 inspection — the surrogate arm, before anything is trained

**Date:** 2026-10-16 · **Status:** inspection complete; **four decisions pending
with the project owner**, and ADR-021's go/no-go still needs the guide ·
**Nothing was trained.** No policy, environment or controller code changed. One
measurement script was added (`scripts/p52_headroom.py`), with its results in
`experiments/results/p52/`.
Related: [ADR-009](decisions/ADR-009-ppo-forecast-surrogate.md),
[ADR-020](decisions/ADR-020-forecast-staleness-channel.md) (as amended),
[ADR-021](decisions/ADR-021-forecast-quality-as-a-swept-variable.md) (Proposed),
[ADR-027](decisions/ADR-027-forecasting-roles.md),
[P112 protocol](../../experiments/results/safety/PREREGISTRATION_P112.md), and
P52, P54, P110, P113 and P114 in the [changelog](PRD-CHANGELOG.md).

## The answer first

1. **P52 stands exactly as reported.** The `surrogate` arm is still the
   `no-forecast` arm under another name. Nothing produces a forecast during
   training, and the config's note still describes a proxy that does not exist.
2. **The 17-dim layout and the gate are ready to carry a forecast.** Two
   things are missing: something that produces the forecast during training,
   and a forecast-aware policy trained on it.
3. **New finding: in the current simulation, a perfect forecast has very
   little to say.** At saturation the realised class 60 s ahead differs from
   the class right now on only **6.9%** of approach-decisions. **HIGH never
   occurs** (0 of 2,160). The policy can already compute the current class
   from its own counts.
4. **So ADR-021's ceiling would be a weak test as things stand.** A null
   result would show that a near-constant input does not help. It would not
   show that forecasting cannot help, which is what ADR-021 says a null at
   the ceiling decides. ADR-021's quality grid also has no meaning here; see
   §5.
5. **Recommendation: train nothing yet.** First:
   - give the simulation a future that differs from the present;
   - define the oracle;
   - pre-register the ceiling against a measured headroom gate.

   Then run the ceiling. These are decisions D1–D4 at the end.

## 1. What the current surrogate arm contains

| place | what is there | what it means |
|---|---|---|
| `simulation/configs/ppo_config.yaml` `arms` | `no-forecast`, `surrogate`, `mfstnet`. **Both** `no-forecast` and `surrogate` set `use_mfstnet: false` | The two arms are the same config. The `surrogate` note ("a SUMO-derived congestion proxy fills 11-14") describes behaviour that does not exist |
| `scripts/train_ppo.py` | `--arm` picks a config row and passes only `use_mfstnet` to the env. The checkpoint is named `ppo_{arm}_…` and the arm goes in the sidecar | `--arm surrogate` would train a no-forecast policy and **label it surrogate**: the P47/P52 failure. Nothing refuses it |
| `simulation/envs/traffic_env.py` `_state` | `use_mfstnet=True` raises `NotImplementedError`. Otherwise slots 11–16 come from `forecast_slots(spec, None, None)`, which gives 0.0 ×4 and age 1.0 | No forecast producer exists. Every arm trains in the no-forecast world |
| `simulation/ppo_controller.py` `observe` | Builds slots 11–16 through `forecast_slots` from `observation["forecast"]` and `observation["forecast_age_s"]`. It refuses missing or invalid counts and queues | Ready to serve a forecast-aware checkpoint unchanged |
| `simulation/gated_controller.py` | `GatedController` with `Probe` standing in for the forecast-aware policy | Ready. A real policy replaces `Probe` with no gate change |
| `scripts/benchmark.py` `controllers()` | Discovers every checkpoint under `models/ppo/` | A mislabelled `surrogate` checkpoint would appear as a separate arm |
| tests | No test compares one arm's observations with another's | The assertion whose absence let P52 go unnoticed still does not exist |

Only one PPO checkpoint exists: the no-forecast retrain (S63v, P113), at a
single training seed (42).

## 2. How the forecast-aware policy consumes the 17-dim state

No layout change is needed, and the contract digest stays `59579c2dd3be10ed`.

- **Indices 11–14:** one class per approach, through `forecast_slots`:
  LOW, MEDIUM and HIGH → 1/3, 2/3 and 1.
- **Index 16:** `min(age, 10) / 10`.
- **The forecast-aware policy is only consulted when the gate says the message
  is complete, fresh and valid.** P113 verified this on 287 decisions. In
  deployment it therefore never sees 0.0 at 11–14, and it never sees an age
  over 10 s. **Training must present exactly that distribution:** complete
  messages with an age in [0, 10]. Absence is the no-forecast policy's job,
  so the two policies' input distributions do not overlap.
- **The age must be real, not decorative.** A message of age *a* must carry
  the forecast made *a* seconds earlier, for the moment 60 s after it was
  made. If training draws the age as a random number that does not change
  the content, the policy learns to ignore index 16, and ADR-020's channel
  teaches it nothing.
  - A natural way to get a real age: refresh the forecast every *k* seconds
    and carry it in between. The cost control under D2 does exactly this.
- **Provenance:** the arm, the oracle definition, the corruption parameters and
  the corruption seed go in the checkpoint's sidecar (ADR-021 §4), never in the
  layout.

## 3. How the forecast-aware policy differs from the no-forecast fallback

This was decided in ADR-020 as amended (P110) and is not reopened here: **two
policies and a gate**, not one policy with a mask.

| | no-forecast policy (exists) | forecast-aware policy (to train) | degraded cycle |
|---|---|---|---|
| decides when | gate says `no_forecast` | gate says `forecast` | counts or queues invalid |
| slots 11–14 | always 0.0 | always a class value | n/a |
| slot 16 | always 1.0 | real age in [0, 1] | n/a |
| checkpoint | `ppo_no-forecast_saturated_keep_or_switch_seed42.zip` | separate file, separate sidecar | `Fixed(30)` |
| shared | env, reward, `keep_or_switch`, PPO hyperparameters, demand, clamps | identical | clamps |

## 4. How it is compared fairly against no-forecast

**Only slots 11–14 and 16 may differ.** Everything else is held equal and
checked:

- **The same everything else:** demand file, regime, reward, action space,
  hyperparameters (`ppo_config.yaml`), 500,000 timesteps, CPU, and clamps.
- **An automated check that the arms differ only in those slots.** Drive both
  environments through one fixed action sequence on one seed, and assert their
  observations are identical outside 11–14 and 16. This is the assertion P52
  found missing.
- **Training seeds: at least three per arm (42, 1, 7)**, not ADR-021's one.
  - P54 measured fold-0 macro-F1 moving by 0.24 across seeds while two configs
    tied, and RL is noisier than supervised training.
  - The ceiling is the run ADR-021 calls decisive, so it is the one that most
    needs replication. **The no-forecast arm has one training seed today**, so
    parity needs two more no-forecast runs as well.
- **Evaluation:** seeds 0–29, paired, through `run_episode`.
  - **The primary outcome must be named exactly.** ADR-021 says "mean total
    delay", which the runner does not report. Its fields are `mean_wait_s`,
    `max_wait_s` and throughput. Part 2 already uses `mean_wait_s`.
- **A persistence control arm.** Slots 11–14 are filled with the current
  class, which the policy could compute itself.
  - This separates **foresight** from **an extra input channel**: if the
    oracle beats no-forecast but not persistence, the gain was not
    foresight.
  - It is also the arm the deployed system could actually feed today:
    persistence v1 is the shipped class forecaster (ADR-027).
- **Webster is the secondary comparator** for the ceiling. ADR-021 §3 sets X
  against Webster.
- **Labelling:** every oracle result is **oracle-input, an upper bound, not
  achievable**. This applies everywhere, including the dashboard's evidence
  panel if one ever shows it.

## 5. The measurement: what a perfect forecast could add here

`python scripts/p52_headroom.py --regime <r>`.

- **Setup:** seeds 100–104, disjoint from the evaluation seeds 0–29 and the
  training seed; 1800 s; §14.1 thresholds (LOW ≤ 4, MEDIUM ≤ 15).
- **Pairing:** each decision is paired with the realised class 60–75 s later.
  That is what ADR-021's oracle would hand the policy.
- **Persistence** is the current class.
- **Disclosed:** an exploratory version of this ran first on seeds 0–2. Those
  are evaluation seeds, so that version is not cited. Its numbers agreed with
  the ones below.

| regime | controller | pairs | future class mix (LOW / MED / HIGH) | **oracle ≠ persistence** | persistence accuracy |
|---|---|---|---|---|---|
| light | no-forecast PPO | 2,160 | 0.917 / 0.083 / 0 | 13.6% | 0.864 |
| light | Webster | 1,984 | 0.865 / 0.135 / 0 | 21.1% | 0.789 |
| **saturated** | **no-forecast PPO** | **2,160** | **0.129 / 0.871 / 0** | **6.9%** | **0.931** |
| saturated | Webster | 2,052 | 0.088 / 0.909 / 0.002 | 12.0% | 0.880 |
| oversaturated | no-forecast PPO | 2,160 | 0 / 0.064 / 0.936 | 5.2% | 0.948 |
| oversaturated | Webster | 268 | 0 / 0.399 / 0.601 | 33.2% | 0.668 |

**What it shows:**

- **In every regime the future class is nearly constant.**
  - At saturation, under the policy a forecast-aware policy would replace,
    the class is MEDIUM 87% of the time. **HIGH occurs 0 times** in 2,160
    approach-decisions.
  - All 149 disagreements with persistence are LOW↔MEDIUM flicker.
- **Why:**
  - The demand is constant-rate `vehsPerHour` flows at the same rate on all
    four approaches. Within an episode, nothing about the future demand
    differs from the present.
  - The §14.1 thresholds were set for camera counts, not for a 2-lane SUMO
    approach.
- **The state already recovers the rest.** A logistic regression on the 9
  features the policy already sees, scored leave one episode out, predicts
  the future class with accuracy 0.919 at saturation under PPO. That is
  exploratory, from 5 episodes.
- **ADR-021's grid has no meaning here.**
  - **0.33, 0.50 and 0.65 are below what the policy already has.** Persistence
    scores 3-class macro-F1 0.569 at saturation, and 0.853 averaged over the
    two classes that occur. A "surrogate at 0.50" is worse than the current
    class the policy can compute for itself.
  - **0.80 and 1.00 cannot be reached.** With HIGH absent, even the perfect
    oracle scores 3-class macro-F1 0.667.
- **Webster's higher disagreement reflects its own long cycles.** The numbers
  above are a property of the controller as well as of the demand.
  - The 33% at oversaturation comes from only 268 pairs, because Webster
    decides once every ~50 s.
  - Under a learned policy, part of what the oracle "foresees" is the
    policy's own next actions. D2 deals with that.
- **The episodes' delay figures are not a comparison** and are not
  interpreted.

## 6. Evidence required before ADR-021's ceiling and before Part 2

**Before the ceiling is trained (ADR-021 step 1):**

| # | evidence | state |
|---|---|---|
| E1 | **A headroom gate passed on the chosen scenario.** It is pre-registered: the oracle differs from persistence on at least a stated share of approach-decisions, and every class is at least a stated share of the future labels, both under the no-forecast policy. Measured with `p52_headroom.py` on seeds disjoint from 0–29 | **Fails today** (6.9%; HIGH 0%) |
| E2 | The oracle defined (D2) and implemented, with a test that it equals the realised class under its stated continuation | not built |
| E3 | `train_ppo.py` refuses `--arm surrogate` until a producer exists, and the arms-differ-only-in-slots check exists | not built |
| E4 | A ceiling pre-registration committed before any run, naming four things: outcome field, training seeds, evaluation seeds, and test and effect size. It also states what a null means **given E1's measured headroom** | not written |
| E5 | The guide told that ADR-021's go/no-go and any scenario change alter the RL claim. ADR-021 is still Proposed | not done |

**Before Part 2 (P112):**

- **Its own eligibility list:**
  - the surrogate arm is implemented;
  - the ceiling has been run;
  - a forecast-aware policy has been trained on the 17-dim layout.
- **An amendment before any Part 2 run.** It must name the regime or scenario,
  which Part 2's design never fixes; Part 1 named `saturated`. It must also
  name the forecast stream, labelled oracle-input if it is ADR-021's oracle.
- **The forecast-aware checkpoint passes `verify_ppo_checkpoint.py`,** extended
  to check the arm and the forecast producer recorded in its sidecar.

**Part 1 stays recorded as passed (P113), Part 2 stays PENDING, and the
controller stays disconnected from signal timing.**

## Decisions for the project owner

**D1 — the scenario.** The future must sometimes differ from the present.

- (a) **Keep constant demand.** The ceiling then tests a near-constant input,
  and a null decides nothing. **Not recommended.**
- (b) **Recommended:** **add** a time-varying scenario, keeping the three
  existing regimes and every result on them untouched. "Time-varying" means
  surges, or rates that change per approach over the episode, or Poisson
  arrivals.
  - It is specified and pre-registered before any PPO run.
  - It passes E1 before it is used.
  - Webster's ADR-012 sweep is rerun on it so the baseline is tuned to it
    too.
- (c) **Calibrate SUMO's class thresholds** per approach, at q33/q67 from a
  calibration run on disjoint seeds (ADR-017's method). This fixes the
  missing HIGH class but adds no foresight, so it goes **with** (b), not
  instead of it.

**D2 — what the oracle is.** The future depends on the controller, so "the
class at t+60" needs a stated continuation.

- (i) **Recommended:** **look ahead in SUMO under the frozen no-forecast
  policy.** Save the state, simulate 60 s with that policy, read the class,
  and restore.
  - This matches how a deployed forecaster learns: from footage recorded
    under the incumbent controller.
  - It does not leak the learner's own future actions.
- (ii) Look ahead under the fixed 30-s cycle. This is simpler, but further
  from deployment.
- (iii) Read future arrivals from the demand definition. This is cheap and
  policy-free, but it is a different quantity from the class MFSTNet
  predicts, and under constant demand it is a constant.

**Cost of (i).** A 500,000-step run is about 1,389 simulated episodes. A 60 s
lookahead on every 5 s step is about 13× the simulation. Refreshing the oracle
every 15 s, carried with its true age, brings that to about 4–5×. **Measure it
on one smoke run before committing.**

**D3 — the sweep axis (an ADR-021 amendment).** Replace the raw macro-F1 grid
with **quality relative to persistence**:

- q = 0 is persistence and q = 1 is the oracle;
- ADR-021's structured corruption applies in between;
- macro-F1 and accuracy are still reported at every point.

This keeps the axis meaningful when a class is rare. It also starts the curve
at what the system can already deploy.

**D4 — replication.** Three training seeds per arm for the ceiling, as in §4.
That adds two more no-forecast runs.

**Recommended order:**

1. D1 to D4 decided, and the guide informed (E5).
2. The guard and the arms check (E3).
3. The scenario, with its headroom gate measured (E1).
4. The oracle, with its test (E2).
5. The ceiling pre-registration (E4).
6. The ceiling runs.
7. Only if the ceiling clears: the sweep and Part 2's eligibility.
