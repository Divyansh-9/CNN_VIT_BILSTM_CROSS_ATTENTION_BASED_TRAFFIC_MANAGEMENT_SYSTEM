# Plan — after the ADR-021 ceiling (P130)

**Date:** 2026-10-17
**Owner:** project owner
**Decisions with the guide:** [MEMO-2026-10-17](MEMO-2026-10-17-adr021-ceiling.md)
**Status:** Track A is done; Tracks B–E wait on the decisions named in each.

This plan does three things:
- **closes the forecast-for-control experiment** without changing it;
- **parks what should wait;**
- **specifies the one new study worth doing.** It is built so that it can
  fail cheaply, and fail early.

## Principles carried forward

| principle | in practice |
|---|---|
| **P130 is frozen** | no rerun, reanalysis, re-exclusion or new threshold; a new question gets a new study |
| **pre-register before data** | protocol, code and decision rule are committed before the first evaluation episode |
| **cheap gates first** | every study opens with a no-evaluation-cost check that can stop it (as P114 did) |
| **fresh seeds per study** | evaluation seeds already observed (0–29) are not reused for a new hypothesis |
| **locks and parity** | artifacts are hashed and locked; training and evaluation reproduce each other |
| **honest scope** | simulation evidence is labelled as such; the controller stays disconnected from signal timing |

## Track A — close out ADR-021 (done in this commit, apart from A4)

| # | task | output | status |
|---|---|---|---|
| A1 | adopt the owner's conclusion wording as the record | ADR-021 "Conclusion" section, P131 | done |
| A2 | inform the guide before any citation | `MEMO-2026-10-17-adr021-ceiling.md` | done; reply due 2026-10-24 |
| A3 | do not run the quality sweep | recorded in ADR-021 and P131 | done |
| A4 | narrow claim C1 (ADR-023) | `CLAIMS.yaml` and ADR-023 wording | **waits on the guide** |
| A5 | keep the synopsis documents untouched | none; they stay hands-off by owner instruction | standing |

**A4 is deliberately not done here.** Changing a paper claim is the guide's
decision. When it is approved, the change is one commit:
- a C1 wording change;
- a `CLAIMS.yaml` entry recording the measured null as the claim's sentence;
- a changelog entry.

## Track B — P97a Part 2, the safety non-inferiority test (deferred)

**State.** Its eligibility conditions in P112 are met: the surrogate arm
exists, the ceiling has run, and forecast-aware policies are trained. **The
motivating benefit was not shown,** so it is deferred, not run.

**Run it only if** the guide judges this narrower question worth answering on
its own: *is a forecast-aware controller, gated as ADR-020 specifies,
non-inferior in safety and delay to the no-forecast controller under fault
injection?*

**Before any run, it needs a frozen amendment to `PREREGISTRATION_P112.md`
specifying:**
1. **The scenario.** `pulsed` is recommended, because it is qualified. Part 2
   never fixed one.
2. **The forecast source.** The oracle, labelled oracle-input. The training
   seed it uses must be chosen without looking at P130's per-seed results:
   recommended rule, the locked seed 42, the same policy as the oracle's.
3. **The controller and baseline.** `GatedController` with the forecast-aware
   policy, against the no-forecast policy, with the fixed 30 s cycle under
   corrupt counts.
4. **Endpoints, margins and statistics.** P112 fixes these already (+5% wait,
   +1 starvation, Holm over 6). Restate them, or amend them explicitly.
5. **Training-seed variability.** One replicate or three. Three is
   recommended, given P130's spread.
6. **Sample size.** Seeds 0–29 overlap the ceiling's evaluation, so use fresh
   seeds.
7. **The interpretation if safety is non-inferior but delay does not
   improve.** Stated in advance: "the gate is safe; the forecast adds no
   benefit".

**Estimated cost if approved:** about half a day. No training is needed for
one replicate.

## Track C — new study: forecast-assisted Webster split (FAW)

### C.1 Why this study, and why this design

**What P130 left open:** whether forecast information helps a controller that
is **already competitive**. PPO was not, trailing both Webster arms.

**FAW answers that, with three properties that remove P130's main
weaknesses:**

| P130 weakness | FAW design |
|---|---|
| training-seed variance as large as the effect | **a deterministic controller,** with no training and no replicate spread |
| oracle transfer 77%: the oracle came from a different policy's trajectory | **a self-consistent oracle:** a replay under the baseline controller itself, which FAW departs from only through the forecast |
| a 3-class label carries little information to a timing rule | **a count forecast** of the next minute's mean, the quantity Webster's flow ratios actually use; it is ADR-027's ridge role |

**The controller.** `Webster` at the P125 configuration (s = 600 pcu/h/m,
0 s lost time, cycle clamped to [32, 192] s), the best measured controller.
Its rule is unchanged except for **the demand it reads**:

| arm | demand input to the flow ratios | role |
|---|---|---|
| **W-now** (baseline) | the counts at the decision, as today | the P125 arm; persistence is identical to it by construction |
| **W-oracle** | the next-minute mean count, from the replay under W-now | the ceiling: an upper bound |
| **W-ridge** | the frozen ridge v1 forecast (ADR-027, `ridge@73532968dcf2`) | the achievable arm, from a deployable forecaster |
| **W-blend** *(optional; decided at C2)* | one pre-specified blend, e.g. (now + forecast)/2 | only if C2 motivates it, and fixed before C4 |

**The comparators carried from P130 as context:** tuned Webster and fixed
30 s, with no-forecast PPO reported only descriptively.

### C.2 Stages and gates

Every gate has a stop rule. **A stop is a result, and it is recorded.**

| stage | what | seeds | stop rule | estimate |
|---|---|---|---|---|
| **C0 Design** | the exact FAW demand rule; the ridge adapter for SUMO counts (2 s samples, per approach); the replay oracle under W-now; unit tests | none | — | 0.5 day |
| **C1 Feasibility (pre-registered)** | **Does the forecast change decisions?** Share of cycles where W-oracle's green split differs from W-now's by ≥ 1 s; the ridge forecast's MAE against the realised next-minute mean, compared with persistence | design 600–609 | **stop if W-oracle changes < 10% of splits**: the forecast cannot matter to this rule | 0.5 day |
| **C2 Pilot and power** | the paired SD of W-oracle − W-now total delay; sample size for a pre-set minimum effect of interest (**2% of W-now's delay**) at power 0.8 | pilot 610–639 | **stop if the required n > 200**: the effect could not be resolved | 0.5 day |
| **C3 Pre-registration** | protocol + code + `decide()` + tests, committed **before** C4 | none | — | 0.5 day |
| **C4 Evaluation, once** | all arms, paired, on **fresh** seeds | 700 – (700 + n) | — | under 1 h of compute |
| **C5 Report** | P entry, the reading, the limits | none | — | 0.25 day |

**Primary question (C3 to fix):** does W-oracle lower mean total delay against
W-now? It is **two-sided**, reports *d*, and requires a pre-set minimum
effect. W-ridge against W-now is the second primary test, with **Holm across
the two**.

**Readings, named in advance:**
- **the oracle helps and ridge helps:** an achievable forecast improves a
  competitive controller;
- **the oracle helps and ridge does not:** forecast quality is the
  bottleneck;
- **the oracle does not help:** the timing rule cannot use foresight.

**Evaluation discipline:** the same locks, parity, sublane model and
`total_delay` outcome as P128. Seeds 0–29 are not used for any decision.

### C.3 Implementation tasks (C0)

1. `simulation/webster.py`: an optional `demand_source` hook, defaulting to
   today's counts so every existing caller is unchanged. Test that the
   default is byte-identical to the current rule.
2. `simulation/count_forecasts.py`, holding:
   - `OracleMeanCount`: the replay oracle's next-minute mean, under the
     W-now trajectory;
   - `RidgeCount`: the frozen ridge v1 on 2 s per-approach samples. It is
     refused if the SHA-256 differs from `RIDGE_V1_SHA256`.
3. The replay oracle generalised from "frozen PPO policy" to "any
   controller", reusing `simulation/oracle.py`'s recorder, cache and keying.
4. `scripts/faw_feasibility.py` (C1) and `scripts/faw_eval.py` (C2–C4), on
   P128's pattern: once-only, lock-checked, with `restat`.
5. Tests:
   - the default demand path is unchanged;
   - the oracle is deterministic;
   - the ridge adapter matches `edge.count_forecast` on the same samples;
   - `decide()` is correct for every reading.

### C.4 Risks

| risk | mitigation |
|---|---|
| W-now already saturates the gain available, so the null repeats | C1 measures exactly that, cheaply, before anything else |
| the ridge was trained on Bellevue camera counts and SUMO counts differ | it is level-free by design (P103/P105); C1 reports its MAE on SUMO first |
| the clamped cycle limits how much a forecast can change | C1 measures how often the split changes; the cycle clamp itself is not tuned |
| forking paths in the design | design and pilot seeds are disjoint from the evaluation seeds; the rule is frozen at C3 |

## Track D — a stronger RL controller (deferred; low priority)

**Do this only if FAW shows forecasts can help a competitive controller,**
and the project then wants a learned controller to exploit them. The first
milestone would be **a PPO that matches tuned Webster with no forecast.**
Without that, any forecast question about RL repeats P130's weakness.

**Candidate changes,** each a pre-registered screen on tuning seeds:
- a delay-based reward;
- longer training;
- an action space with green durations;
- an observation history.

Not scheduled.

## Track E — the rest of the roadmap (unchanged by P130)

| item | blocker | next action |
|---|---|---|
| prediction quality on fresh, human-verified labels | labels | the owner's labelling session (C2 claim) |
| real-world validation (S65: the live camera stream) | camera access via `STMS_CAMERA_URL` | the owner provides the stream |
| GitHub publication | the repository is public; the Bellevue licence is unresolved | the owner makes it private, then a draft PR (PUBLICATION-READINESS) |
| guide decisions | the memos of 2026-08-22 and 2026-10-17 | replies |

## Decision summary

| decision | who | recommendation |
|---|---|---|
| narrow C1's RL half to the measured null | guide | yes |
| run P97a Part 2 | guide | defer; if yes, amend first (Track B) |
| start FAW at C0–C1 | owner, guide informed | yes: cheap, and it can stop at C1 |
| quality sweep / rerun P130 | — | no |
