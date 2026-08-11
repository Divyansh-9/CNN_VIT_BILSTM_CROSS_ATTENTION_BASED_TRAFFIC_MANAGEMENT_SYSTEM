# ADR-011 — Webster Definition: Cycle Clamping, Starvation Semantics, and Two Roles

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-10 |
| **Affects** | FR-A03, FR-A04, FR-A06, FR-R04, FR-R08, FR-S04; PRD §13.1, §13.2; pending items P6, P8 |
| **Related** | [TRIAGE-002](../triage/TRIAGE-002-webster-parameterisation.md) · [RESEARCH-001](../research/RESEARCH-001-webster-parameterisation.md) · [ADR-010](ADR-010-sumo-heterogeneous-traffic.md) |

## Context

RESEARCH-001 could not answer what saturation flow value to use, because both open-web angles
returned no evidence. It did establish that three questions about Webster need **no external
evidence at all** and can be settled from this project's own numbers. This ADR settles them.

It also corrects a mistake in the analysis that produced pending item P6.

## Decision 1 — Clamp Webster's cycle, log every clamp, report the rate

Webster's optimum cycle `C₀ = (1.5L + 5) / (1 − Y)` diverges as the sum of critical flow ratios `Y`
approaches 1. The project's timing rules bound what is admissible:

| Bound | Derivation | Value |
|---|---|---|
| Minimum cycle | `2 × (min_green + all_red)` = `2 × (10 + 3)` | **26 s** |
| Maximum cycle | `2 × (max_green + all_red)` = `2 × (90 + 3)` | **186 s** |

`C₀` is clamped into `[26, 186]`. Splits are then allocated proportionally to critical flow ratios,
each split clamped to `[10, 90]`, and any residual redistributed proportionally among unclamped
phases. If no feasible allocation exists, use an equal split and log it.

**Every clamp is logged, and the clamp rate is reported beside the benchmark results.** This is the
part that matters. A Webster pinned to its 186 s ceiling in most cycles is operating in an
oversaturated regime, where fixed-time control is known to do badly. "PPO beats Webster by 10%" then
partly means "PPO beats a saturated fixed-time controller" — a materially weaker claim. Disclosing
the clamp rate turns a hidden confound into a reported number.

## Decision 2 — P6 was a mis-analysis; the 180 s threshold is correct

**The earlier finding was wrong and is withdrawn.**

P6 claimed FR-R04's 180 s starvation limit contradicted a 186 s worst-case cycle. That conflated
**cycle length** with **lane wait**. A lane is served in one phase, so it waits for the *other*
phase's green plus two all-reds:

```
worst wait under strict alternation = max_green + 2 × all_red = 90 + 6 = 96 s
```

96 s is comfortably below 180 s. **No contradiction exists**, and no PRD value changes.

The threshold turns out to be well calibrated for the situation it actually governs — a phase served
twice in succession:

| Scenario | Lane wait | Outcome |
|---|---|---|
| Strict alternation, any durations | ≤ 96 s | Never penalised |
| Two consecutive 60 s greens | 129 s | Tolerated |
| Two consecutive 90 s greens | 189 s | **Penalised** — the behaviour BR-11 exists to prevent |

It permits one skipped service, tolerates repetition at moderate green, and penalises stacked maximum
greens. That is the intended shaping, and it was correct before anyone examined it.

**How the mistake happened, recorded so it is not repeated.** The spec-invariant test asserted
`starvation_s > worst_cycle`. The invariant was plausible and the arithmetic was right; the *model*
behind it was wrong. A test encodes an assumption about the system, and an assumption stated
precisely can still be precisely wrong. The corrected tests now assert the wait model directly, and
one of them asserts that the penalty remains reachable — a penalty that can never fire is dead code,
which is the opposite failure.

**What the correction exposed, which is real.** Nothing in the PRD says whether the controller may
serve the same phase twice in a row. The action space is (phase, duration) with no alternation
constraint. If repetition is forbidden, starvation is structurally impossible and FR-R04 is dead
code. If permitted, the penalty is load-bearing. Recorded as **pending item P9**, with
`phase_repetition_allowed: true` as the working default so the two readings cannot diverge silently.

## Decision 3 — One implementation, two parameter files

Webster serves as both the benchmark baseline (FR-R08, FR-S04) and the edge fallback (FR-A06). These
share **one implementation and one test suite**, parameterised by two separate config files:

| | Benchmark | Edge fallback |
|---|---|---|
| Parameters from | SUMO calibration (FR-S02) | Embedded at deploy time |
| Config | `simulation/configs/webster_benchmark.yaml` | `edge/configs/webster_edge.yaml` |
| Recalibration | Re-derived if demand calibration changes | **Never at runtime** |

The edge file must be embedded before deployment because the fallback activates *precisely when the
network is unavailable*. A fallback that fetches parameters over a failed network is not a fallback.

**Stated limitation for §20:** unless real per-lane counts are measured at the deployment site, the
edge fallback is parameterised from SUMO calibration and is therefore tuned for the simulated
intersection rather than the observed one. This is acceptable for a bench prototype and must be
declared rather than discovered.

## Consequences

**Positive.** Three blockers clear without waiting on the literature. P6 closes as a mis-analysis
rather than lingering as an unresolved contradiction. The clamp-rate disclosure pre-empts a reviewer
objection that would otherwise land after the benchmark has run. One implementation means one set of
tests covering both roles.

**Negative.** Saturation flow and lost time remain unspecified (P8). Decisions 1 and 3 are the
*scaffolding* around a parameterisation that does not exist yet; they do not substitute for it. The
benchmark cannot run credibly until P8 is settled.

**Negative.** `phase_repetition_allowed: true` is a working default chosen so that the penalty stays
meaningful, not a researched conclusion. It should be confirmed against how comparable work defines
its action space when RESEARCH-001 is re-run.

**Neutral.** No PRD numeric value changes. Decision 2 withdraws a finding rather than amending a
requirement.

## Alternatives considered

**Raise the starvation threshold above 186 s.** This was the recommendation before the arithmetic was
redone. Rejected because the premise was false — 186 s is a cycle length, not a wait — and raising
the threshold would have weakened a correctly calibrated fairness constraint to fix a problem that
did not exist.

**Let Webster exceed the green bounds when its optimum demands it.** Simpler, and arguably truer to
Webster's method. Rejected: FR-A03 and FR-A04 are safety invariants that SRS §2.3 applies to *every*
control source. A baseline exempt from the constraints the learned controller obeys is not a fair
comparison.

**Two separate Webster implementations.** Would let each role be tuned independently. Rejected as
unnecessary divergence: the difference is entirely in parameters, and two implementations means two
places for a timing bug to hide.
