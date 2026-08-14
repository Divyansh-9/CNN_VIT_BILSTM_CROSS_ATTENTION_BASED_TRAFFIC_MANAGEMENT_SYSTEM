# ADR-012 — Webster Saturation Flow: Sweep the Published Range, Do Not Pick a Value

| | |
|---|---|
| **Status** | Accepted · **rev 2** (S35 measured the sweep; the selection rule was not safe as written) |
| **Date** | 2026-08-10 |
| **Affects** | FR-S02, FR-R08, M3, M7; pending item P8 |
| **Closes** | [TRIAGE-002](../triage/TRIAGE-002-webster-parameterisation.md) items 1, 2 and 6 |
| **Related** | [ADR-011](ADR-011-webster-definition.md) (cycle clamping, two roles) · [ADR-010](ADR-010-sumo-heterogeneous-traffic.md) |

## Context

[TRIAGE-002](../triage/TRIAGE-002-webster-parameterisation.md) left three items open because
RESEARCH-001 returned no evidence: the saturation flow rate, the lost time, and how comparable work
parameterises its classical baselines. Those three decide whether FR-R08's headline claim — PPO beats
Webster by ≥10% — means anything.

A literature pass now answers them, and the answer is not the one that was expected.

### Finding 1 — the HCM per-lane default is structurally wrong here

For non-lane-disciplined heterogeneous traffic, published practice expresses saturation flow **per
metre of approach width**, not per lane. Lanes are not the unit of discharge when two- and
three-wheelers filter laterally, so a per-lane figure has nothing to attach to.

| Source | Formula / value | Notes |
|---|---|---|
| IRC:SP-41-1994 (Indian standard) | **S = 525 × W** PCU/h | W = approach width in metres; stated valid above 5.5 m |
| Field studies, heterogeneous traffic | **610–660 PCU/h per metre** | Approach widths 3.5–14 m |
| Ahmedabad four-arm intersection | **933W – 1283W** (IRC PCU) · **636W – 821W** (Justo & Tuladhar PCU) | The value depends on which PCU set is used |
| Banda Aceh, non-lane-based, calibrated | **S₀ = 622 × Wₑ**, R² = 0.99 | Effective widths 5–8 m. Replaced the local standard's 600Wₑ, cutting error from 21% to 4% |

### Finding 2 — the published values disagree by roughly 2.4×

525W at the low end against 1283W at the high end. That spread **is** the result. It is not noise to
be averaged away: it reflects genuine differences in PCU convention, local vehicle mix, and
measurement method.

A Webster controller parameterised at 525W and one at 1283W are materially different baselines. Pick
the low end and Webster under-serves every approach, PPO wins easily, and the win is an artifact.
Pick the high end and Webster over-serves, saturating and stacking queues. **Either single choice is
indefensible, and a reviewer can allege detuning in either direction.**

### Finding 3 — the field's baselines are visibly weak, and its reporting is thin

Published RL-TSC work reports fixed-time travel times of 552–924 s against roughly 100–120 s for
learned controllers. A five- to eight-fold gap is not what a competently tuned fixed-time plan
produces; it is the signature of a baseline nobody tuned. Separately, established baselines are
reported as **average values without variability**.

Both observations favour this project rather than threatening it — see Consequences.

## Decision

### 1. Sweep the published range; report Webster's best

Do not select a saturation flow value. Run the Webster baseline across the published range and
**report the best-performing configuration** as the baseline PPO must beat.

```yaml
# simulation/configs/webster_benchmark.yaml
saturation_flow_pcu_per_hour_per_metre_sweep: [525, 600, 660, 750, 900, 1050, 1283]
report: best_performing        # by mean wait time, the FR-R08 metric
```

Webster is fixed-time: one run per value takes seconds, so the whole sweep is cheaper than a single
PPO episode. There is no cost argument against doing it.

**This is the point of the decision.** "We swept the published range and PPO beat Webster's *best*
configuration by X%" cannot be answered with "you detuned the baseline." A single chosen value can.

### 2. Passenger-car equivalents, from measurement

Feeds both the Webster flow ratios and ADR-010's vehicle-type mix:

| Vehicle | PCE | Source |
|---|---|---|
| Car | 1.00 | Reference |
| Motorcycle | **0.24** | Calibrated, non-lane-based conditions |
| Auto-rickshaw | **0.78** | Same study; deviated 56% from the older standard value |
| Bus / truck | Use IRC values | Not measured in the sourced study — record which set is used |

Record which PCU set every experiment used. The Ahmedabad numbers show the same intersection yields
933W–1283W or 636W–821W purely by switching PCU convention, so an unrecorded convention makes a
result unreproducible.

### 3. Lost time

Start-up lost time **4–5 s**, clearance **≈3 s**, consistent with FR-A04's 3 s all-red.

Note the disagreement rather than hiding it: some Indian field observations report essentially **zero**
start-up lost time, because queued two-wheelers begin moving before the green. Include 0 s as a
sweep endpoint for the same reason as §1.

### 4. Report the sweep, not just the winner

The benchmark table carries Webster's performance at every swept value, not only the best. A reader
sees the baseline's sensitivity to a parameter the literature does not agree on — which is itself a
finding, and it pre-empts the objection instead of inviting it.

## Consequences

**Positive.** P8 closes. The baseline becomes defensible against the strongest available objection,
at negligible compute cost. The sweep doubles as a sensitivity analysis nobody asked for and every
reviewer will value.

**Positive, and worth stating in the paper.** Published RL-TSC baselines are weak (5–8× gaps) and
reported without variability. This project runs 30 seeds with bootstrap confidence intervals, paired
t-tests and Cohen's *d*, against a swept baseline. That protocol is **above the field's current
standard**, and saying so — with the citation — converts methodological care into a claim.

**Negative.** The sourced calibration studies are Indonesian and Indian, not from the deployment
intersection. The values transfer by similarity of traffic composition, not by measurement. State
this as a limitation; it is the honest position and the sweep already bounds the consequence.

**Negative.** ADR-010's `vType` widths and the PCE values must stay consistent. If the SUMO vehicle
mix changes, the flow ratios change and the sweep must be re-run. Cheap, but it must actually happen.

**Neutral.** IRC:SP-41-1994's formula is stated valid above 5.5 m approach width. If the modelled
approach is narrower, use the narrow-width form (`S₀ = 1020 + 459·Wₑ`) and record the substitution.

## Alternatives considered

**Pick the Indian standard, S = 525W.** Defensible by authority, one number, no sweep. Rejected: it
is the **lowest** value in the published range, so it produces the weakest Webster and the largest
apparent PPO win. Choosing the number that most flatters your own method is exactly what a reviewer
looks for.

**Measure saturation flow from our own footage.** Most rigorous, and the right answer for a project
with more time. Rejected on schedule: it needs sustained saturated-queue observation at a calibrated
site, which is a study in itself. Recorded as future work.

**Take the mean of the published range.** Simple. Rejected — averaging incompatible PCU conventions
produces a number that belongs to no methodology and cannot be cited.


---

## Rev 2 — running the sweep broke the selection rule (S35, 2026-08-13)

This ADR said: report the **best-performing** saturation flow. Building it and running all seven
values across three regimes showed that rule is not safe on its own. Two configurations can post the
lowest wait while being the wrong answer, and both cases occurred in real data rather than in theory.

### Measured sweep (1200 s, seed 42, `experiments/results/webster_sweep.csv`)

| s (PCU/h/m) | light wait | saturated wait | saturated clamp | oversat wait | oversat arrived |
|---|---|---|---|---|---|
| 525 | 8.1 s | 34.9 s | 5% | 74.9 s | 0.78 |
| 600 | **7.7 s** | 38.0 s | 4% | 80.2 s | 0.77 |
| 660 | 7.7 s | 36.4 s | 8% | 78.2 s | 0.77 |
| 750 | 7.7 s | **26.8 s** | **14%** | 81.0 s | 0.77 |
| 900 | 7.7 s | 13.8 s | 85% | 84.4 s | 0.77 |
| 1050 | 8.1 s | **13.7 s** | **100%** | **63.2 s** | **0.55** |
| 1283 | 8.2 s | 13.7 s | 100% | 86.1 s | 0.75 |

**Finding 1 confirmed with force.** At the capacity knee the saturation flow changes Webster's mean
wait from 13.7 s to 38.0 s — a **2.8× spread** from a parameter choice alone. Picking one value would
have decided the headline comparison before any agent was trained. The sweep was the right call.

### Finding 7 — a fully-clamped Webster is not Webster

The naive best at the knee is s=1050 at 13.7 s. Its **clamp rate is 100%**: every cycle hit a bound,
so `C0 = (1.5L + 5)/(1 − Y)` never decided anything and the method degenerated to a fixed 32 s cycle.
Reporting that as "Webster's best" would put a fixed-time controller in the results table under
Webster's name — neither an honest Webster nor an honest fixed-time.

### Finding 8 — a low mean wait can be survivorship

In the oversaturated regime s=1050 posts the **lowest** wait of the sweep, 63.2 s, while completing
**55%** of trips against ~77% elsewhere, with a mean queue of 211 against ~85. Its wait looks good
because the vehicles that waited longest never finished and so never entered the tripinfo average.
`runner.run_episode` documents this bias; here it is caught in the wild.

### Amended decision

`simulation.webster.select_best` picks the lowest mean wait **among configurations that are genuinely
running the method and genuinely serving the traffic**: clamp rate ≤ 50% and arrived fraction ≥ 85%.
Both thresholds are parameters, both disqualifications are reported with reasons, and the full sweep
is committed regardless.

Applied to the measured data:

| Regime | Result |
|---|---|
| light | **No configuration qualifies** — all seven clamp 100% of the time. At light demand `C0` falls below the minimum cycle, so Webster is not applicable |
| saturated | **s = 750, 26.8 s**, clamp 14%, arrived 91% |
| oversaturated | **No configuration qualifies** — every one fails the completion threshold |

**When nothing qualifies, that is the finding.** Report the sweep, claim no "Webster's best".

### What this does to the headline claim

Webster's honest best at the knee is **26.8 s**. The longest-queue baseline is **21.7 s**. So the
number PPO has to beat is **longest-queue, not Webster** — and FR-R08's "beats Webster by ≥10%" is
the *weaker* of the two comparisons the project can now make. Reporting only against Webster would
now be the softer claim, which is the opposite of the assumption the requirement was written under.
