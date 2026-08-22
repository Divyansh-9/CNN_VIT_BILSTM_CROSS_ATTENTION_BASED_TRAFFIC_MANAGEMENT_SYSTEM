# ADR-023 — Separate the universal controller from the vision claim

**Status:** Proposed · **Date:** 2026-08-22 · **Reframes [PRD](../PRD.md) §2.4's phasing; does not change any component**

## Context

Every problem of the past two days — [P57](../PRD-CHANGELOG.md) HIGH support,
[P58](../PRD-CHANGELOG.md) geography, [P68](../PRD-CHANGELOG.md) licence,
[P70](../PRD-CHANGELOG.md) the n=3 power collapse — is a problem about **video**.
None of them touches the controller.

That is not a coincidence, and it points at something the project has never
stated: **there are two claims here, and they have been carried as one.**

### The chain that is already junction-invariant

```
camera -> detector -> per-lane counts -> congestion label -> PPO state -> signal
```

A count of 23 vehicles in a lane is the same measurement at every junction. The
PPO state's indices 0-7 are counts and queues, so **the controller already runs
on junction-invariant quantities and is largely built**.

**One honest qualification, because the claim is easy to overstate.** Counts are
*dimensionally* invariant; their *thresholds* are not. ADR-017's `LOW <= 8` is a
statement about a lane's capacity, and a six-lane motorway lane is not a
two-lane Dhaka street. So the residual per-junction dependency is **one capacity
scalar per lane** — measurable at install, not learned from weeks of data. That
is a very different cost from retraining a vision model per site, and it is what
"universal" honestly means here.

### Why the vision half is the part that breaks

MFSTNet does not consume counts. It consumes **frozen backbone features of raw
pixels**, which encode building facades, road colour, camera angle and lighting
— junction *identity*, not traffic *state*. That is the mechanism behind
`0.8941 -> 0.3500`, and it is why every corpus problem lands on this half.

`train_baselines.py` already states the consequence:

> congestion labels are a deterministic function of the vehicle count, so a
> count-sequence model observes **the exact variable the label is computed
> from**, while MFSTNet observes pixels and has to recover the count before
> extrapolating.

So MFSTNet's job was never "forecast congestion" — counts do that. Its job is to
beat counts using **what a count cannot see**: queue length, stopped versus
moving, spatial bunching, a bus blocking two lanes.

## Decision

**State the two claims separately, and let the first ship independent of the
second.**

| | claim | data it needs | status |
|---|---|---|---|
| **C1** | A universal, count-based congestion forecaster and RL signal controller, deployable at any junction after a lane-geometry and capacity calibration | count time series — SUMO, open city data, loop detectors: **abundant** | mostly built |
| **C2** | Visual features beat counts, and therefore transfer to unseen junctions | continuous elevated video: **scarce, and the reason the project is stuck** | unsupported |

**Every open corpus problem belongs to C2 alone.** C1's evidence is the §14.3
count baselines, the SUMO benchmark, and the PPO arms — none of which needs an
Indian video corpus.

This is a stronger position than narrowing scope: it yields **a working
universal controller, plus an honest measured finding about when vision does and
does not add to it.**

## Consequences

- The paper leads with C1 and reports C2 as a bounded sub-study. C2 failing is a
  **result**, not a project failure.
- "Universal" is claimed for the **counts**, not for the model, and the
  per-junction install cost — lane centres plus a capacity scalar — is stated
  rather than implied away.
- [ADR-022](ADR-022-preregistered-gate-vs-probe.md)'s G-versus-H test becomes
  C2's central experiment rather than the project's. Its lack of power is then a
  bounded disappointment instead of an existential one.
- **The count baselines stop being "baselines" and become C1's result.** They
  are §14.3's, they are camera-invariant, and they were run across all four
  folds for this ADR.
- Nothing is deleted and no component changes. This is a claim structure, not a
  redesign.

## What the count baselines say, measured for this decision

Four folds, seed 42, macro F1 (three-class-with-zeros, ADR-019):

| count model | mean | fold 0 | fold 1 | fold 2 | fold 3 |
|---|---|---|---|---|---|
| GRU | **0.5682** | 0.437 | 0.551 | 0.780 | 0.505 |
| **naive last-value** | **0.5571** | 0.449 | **0.692** | 0.673 | 0.414 |
| LSTM | 0.5385 | 0.405 | 0.579 | 0.780 | 0.390 |
| XGBoost | 0.4691 | 0.433 | 0.574 | 0.461 | 0.408 |

Two things to read carefully, and one not to.

**The naive last-value baseline is the second-best model in the table**, and the
best single number anywhere in it (0.692 on the M6). PRD §14.3 warned that over a
60-second horizon "the same as now" would be strong on a signal this
autocorrelated. It is. Any claim about a learned forecaster has to clear 0.557,
not 0.

**Do not read the MFSTNet comparison from this yet.** On fold 0 seed 42, G scores
0.4977 against the best count model's 0.449 — MFSTNet *ahead*. That is one fold,
one seed, and it is the fold whose test camera contains **no HIGH window**, so
it is a two-class problem where the count models' structural advantage (A32:
they observe the label-generating variable) has least room to show. It is
recorded, and it is not evidence.

The comparable numbers arrive when the suite finishes all four folds.

## Alternatives rejected

**Carry on as one claim.** The status quo, and it makes a video corpus problem
into a whole-project blocker. It also forces the paper to either overstate C2 or
report C1's working system as a footnote to C2's failure.

**Drop the vision half entirely.** Throws away the only part with a novelty
claim, and throws away a measured negative result that is worth reporting
(§2.5.5). C2 as a bounded sub-study costs nothing extra — the machinery is
already built.

**Claim universality for the model rather than the counts.** Not supportable.
`0.8941 -> 0.3500` is the measurement that says so.
