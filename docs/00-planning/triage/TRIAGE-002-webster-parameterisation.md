# Triage 002 — Webster Parameterisation Is Unspecified

| | |
|---|---|
| **Date** | 2026-08-10 |
| **Reporter** | Internal review |
| **Issue type** | **Bug** — defect in the specification artifact |
| **Severity** | **High** |
| **Reproducibility** | **Always** — deterministic; grep for "Webster" across the suite |

---

## Summary

Webster appears in the suite in two distinct roles — a benchmark baseline and an edge fallback — and
**neither role specifies where its timing parameters come from.** The baseline role is the serious
one: PRD §21 and FR-R08 stake a headline claim on beating Webster by ≥10%, and an unparameterised
Webster is a strawman.

## The raised issue was the smaller half

It was raised as a fallback-configuration question: *"the fallback must be resident on the edge node,
but nothing specifies where its timing parameters come from or whether they are recalibrated."*

That is real. But grepping the suite shows Webster carries **two independent responsibilities**:

| Role | Where | Requirement |
|---|---|---|
| **Benchmark baseline** | SUMO, compared against PPO over 30 seeds | FR-S04, FR-R08, M7, BO-1, RG3 |
| **Edge fallback** | Resident on the edge node, activates on MQTT dropout | FR-A06, PRD §7.2, SRS §2.3 M-LOCAL |

Nothing in the suite reconciles them — not whether they share an implementation, not whether they
share parameters, and not where either set of parameters originates.

**The baseline role is the higher risk.** FR-R08's criterion is "PPO ≥10% better than Webster,
p<0.05". Webster's 1958 formulation computes cycle length and green splits from saturation flow
rates, critical flow ratios, and total lost time. Choose those badly and Webster underperforms;
PPO then "wins" against a baseline the team detuned by omission. A reviewer's first question about
any RL-versus-classical comparison is *how was the classical method tuned* — and the honest answer
today is *it was not specified*.

## Reported behaviour

Grep across `docs/` returns 24 Webster references. All of them either name Webster as a comparison
target or assert the fallback exists. **None specifies a parameter, a source for a parameter, or a
calibration procedure.**

FR-S02 calibrates SUMO *arrival rates* from IndiaTrafficNet counts. That is demand volume, not
signal timing — it does not parameterise Webster.

## Expected behaviour

- Webster's inputs — saturation flow rate per approach, lost time per phase, cycle-length bounds,
  and the flow ratios used — are stated as values with a named source.
- The baseline and fallback implementations are explicitly either the same code with the same
  parameters, or different, with the difference justified.
- The recalibration policy is stated, including the case where no recalibration occurs.
- The parameters are recorded in the experiment record for every run in the 30-seed benchmark, so the
  comparison in FR-R08 is reproducible and auditable.

## Missing information

This is a problem-space gap, not a missing user-supplied fact:

1. **Saturation flow rate.** The HCM default (~1,900 pcu/h/lane) assumes lane-disciplined homogeneous
   traffic. Under ADR-010's heterogeneous sublane configuration that default is wrong, and the
   literature on saturation flow for mixed Indian traffic gives materially different figures. Which
   value, from which source?
2. **Lost time per phase.** Interacts with FR-A04's 3 s all-red.
3. **Cycle bounds.** FR-A03 fixes green at 10–90 s; Webster's optimum may fall outside that, and
   nothing says what happens when it does.
4. **Whether the two implementations are one.** If the edge fallback is parameterised from SUMO
   calibration, it is tuned for the simulated intersection, not the one the camera watches.
5. **Recalibration trigger.** Webster is fixed-time by design, but its parameters derive from measured
   flows. Recomputed never, once, or periodically? Note the constraint: the fallback activates
   *because* MQTT is down, so it cannot receive parameters at that moment — they must be embedded at
   deploy time, which is a design consequence nobody has written down.
6. **Prior art for a defensible baseline.** How do PressLight, MPLight, and the RESCO benchmark
   parameterise their fixed-time and Webster baselines? Matching an established protocol is worth
   more than inventing one, because it makes the comparison recognisable.

## Suspected areas

- `simulation/` — Webster baseline for the 30-seed benchmark
- `edge/` — resident fallback controller (FR-A06)
- PRD §13.2 evaluation protocol; FR-S04, FR-R08; SRS §2.3 M-LOCAL

## Why this is High severity

BO-1 and RG3 are headline objectives, and both are stated relative to Webster. If the baseline is not
defensibly parameterised, then M7 can be "met" while the underlying claim is empty — the worst
possible outcome, because it passes internally and fails in review.

It also interacts with [ADR-010](../decisions/ADR-010-sumo-heterogeneous-traffic.md): once the
simulation models heterogeneous non-lane-disciplined traffic, the standard saturation-flow assumption
underpinning Webster no longer holds. The two issues must be resolved together or the baseline is
parameterised for a traffic model it is no longer running in.

## Status update — 2026-08-10

[RESEARCH-001](../research/RESEARCH-001-webster-parameterisation.md) ran and returned **no external
evidence** (both open-web angles hit the session limit). [ADR-011](../decisions/ADR-011-webster-definition.md)
then settled the parts that needed none:

| Missing item (from §Missing information) | Status |
|---|---|
| 1. Saturation flow rate | **Still open** — needs the literature angle re-run |
| 2. Lost time per phase | **Still open** — same |
| 3. Cycle bounds and truncation rule | **Closed** — clamp to [26, 186] s, log every clamp, report the clamp rate |
| 4. Whether the two implementations are one | **Closed** — one implementation, two parameter files; edge config embedded at deploy time |
| 5. Recalibration policy | **Closed** — benchmark re-derives on demand-calibration change; edge never recalibrates at runtime |
| 6. Prior art for defensible tuning | **Still open** — the decisive question |

Items 1, 2 and 6 keep this triage **open**. Items 3–5 are done.

---

## Recommended next step

`/research`.

The Missing Information names a problem-space gap — which saturation-flow values apply to mixed
traffic, and how comparable published work parameterises its classical baselines — rather than a fact
the reporter withheld. Prior art exists (Webster 1958; HCM; the RESCO benchmark protocol) and should
decide this rather than a team guess.

Scope the research narrowly: *"How should a Webster baseline be parameterised for a heterogeneous
Indian intersection in SUMO such that the PPO comparison is defensible, and what do comparable RL
signal-control papers do?"* Two to three hours, and it protects the project's headline claim.

**Do this before M3 (Week 10)**, because FR-S04 requires all four methods running in the same
environment, and retrofitting a parameterisation after the benchmark has run means re-running it.
