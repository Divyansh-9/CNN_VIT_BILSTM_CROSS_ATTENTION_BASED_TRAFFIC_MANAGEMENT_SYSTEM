# P123 — pre-registration: the fixed-cycle comparator for ADR-021 on `pulsed`

**Committed before:**
- the fixed-cycle tuning runs;
- any ADR-021 ceiling result exists.

**No forecast-aware policy has been trained.**

**Why.** P122 found that every Webster configuration with 0 s lost time was
disqualified as a fixed short cycle, yet posted about 2% lower total delay
than the selected Webster. So on `pulsed` a short fixed cycle is competitive.

If ADR-021 compared PPO only against Webster, a PPO gain over Webster could be
a gain that any well-chosen fixed cycle also delivers. A fixed-cycle arm,
**tuned under the same rules as Webster and chosen before any PPO result is
seen**, closes that gap.

## Search space (fixed now)

`simulation.controllers.Fixed(green_s = g)`, which alternates the two phases
with the same green every time, under the runner's clamps. The greens are
**g ∈ {10, 15, 20, 30, 45, 60} s**:
- 10 s is the minimum green;
- 30 s is the existing benchmark arm and FR-A06's degraded-mode cycle;
- 60 s is well past any configuration P122 found useful.

## Episodes and seeds

Identical to P121:
- `run_episode` on `pulsed` (hash `8267da50f659`), 1800 s;
- the sublane model at 0.8, with `total_delay=True`;
- **tuning seeds 400–419**.

The evaluation seeds 0–29 are never used.

## Selection rule (fixed now)

1. **Disqualify** any green whose mean arrived fraction is below 0.85 (ADR-012's
   survivorship rule). A fixed cycle has no clamp rate, so that rule does not
   apply.
2. **Select the lowest mean `mean_total_delay_s`.** Exact ties go to the
   shorter green.
3. **If nothing qualifies,** report it, and ADR-021 carries no fixed-cycle arm.

All six rows are reported, including `mean_wait_s`.

## Use

- **The selected fixed cycle is frozen** as ADR-021's fixed-cycle comparator
  (Amendment 2).
- **Runs once.** `scripts/fixed_tune.py` refuses to run if its result exists,
  or if this file is not committed unchanged.
