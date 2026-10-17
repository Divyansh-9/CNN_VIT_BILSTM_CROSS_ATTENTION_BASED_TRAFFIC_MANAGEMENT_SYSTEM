# P125 — pre-registration: a clamped, demand-proportional Webster arm for ADR-021

**Committed before:**
- any ADR-021 ceiling result exists;
- any forecast-aware policy is trained.

The three no-forecast replicates are training while this is written.

**Why.** P124 corrected P122's reading. The zero-lost-time Webster
configurations that ADR-012's clamp rule disqualifies are **not** fixed-time
cycles:

- **the cycle length** sits at a clamp;
- **the green split** still follows each direction's measured flow ratio.

That is a distinct controller: fixed-length and demand-proportional. On
`pulsed`'s tuning seeds it posted the lowest delays of any baseline
(≈ 38.5 s, against 39.42 s for the selected Webster and 44.88 s for the best
fixed cycle).

The project owner approved reporting it as a **separate arm**. It strengthens
the operational baseline comparison.

**It does not replace either of these:**
- ADR-021's primary comparisons: forecast-aware against no-forecast PPO and
  against persistence;
- the frozen Webster (s = 660 pcu/h/m with 4 s lost time) and fixed-cycle
  (30 s) comparators, which stay unchanged.

**It is not called "Webster's best".** ADR-012 reserves that name for
configurations whose cycle formula actually decides.

## The controller, exactly

`simulation.webster.Webster` as committed (`95a496e`), with
`lost_time_startup_s = 0` and the saturation flow chosen below. Every other
parameter keeps its committed default.

| setting | value |
|---|---|
| cycle length | Webster's optimum `(1.5 L + 5) / (1 − Y)`, **clamped to [32, 192] s** |
| lost time *L* | `2 × (0 + 3 s all-red)` = 6 s |
| Y | `min(0.95, y_NS + y_EW)` |
| flow ratio y | `y = demand / (s × 6.4 m)`, with demand from counts over a 120 s window |
| green-split rule | effective green = cycle − *L*. The phases alternate, and each phase's green is `effective green × y_phase / Y`, clamped to [10, 90] s |
| actuation | the runner's minimum and maximum green, plus 3 s yellow and 3 s all-red (FR-A03, FR-A04) |

Its label is **"Webster split, clamped cycle (s, 0 s lost time)"**. Its clamp
rate is reported beside every number it appears in.

## Selection (fixed now; from committed tuning data, never evaluation seeds)

The data are P122's committed tuning rows (`webster_tuning.csv`, `95a496e`,
seeds 400–419). The rule:

1. **Candidates:** the seven configurations with 0 s lost time.
2. **Disqualify** any whose mean arrived fraction is below 0.85 (ADR-012's
   survivorship rule). The clamp-rate rule is deliberately **not** applied:
   clamping is what defines this arm.
3. **Select the lowest mean `mean_total_delay_s`.** Ties go to the lower
   saturation flow.

`scripts/select_clamped_webster.py` computes it from the CSV, writes
`clamped_selection.json`, and refuses to run twice or before this file is
committed. **No new episode is run**, and the evaluation seeds 0–29 are never
used.

## Role in ADR-021 (Amendment 3)

- **Reported** with the same statistics as every arm, over evaluation seeds
  0–29.
- **Not used for X:** A1.6's X stays defined against the frozen Webster.
- **Not used for the ceiling decision.** That remains forecast-aware against
  no-forecast and persistence (A1.6, A2.2).
- **A PPO gain over Webster that this arm also delivers is named as such.**
