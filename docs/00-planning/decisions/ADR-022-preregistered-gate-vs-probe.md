# ADR-022 — Pre-registering the full-model-versus-linear-probe test

**Status:** Proposed · **Date:** 2026-08-22 · **Written before the results exist. See "Timestamp" below.**

## Context

Config **H** is the linear probe A22 added: no fusion, no recurrence, no
attention — a mean over time and a classifier. It is the floor every
frozen-backbone paper is expected to report, and it exists so that the
architecture has something to beat.

On the first clean fold (fold 0, seed 42) H reached **0.4710** against the full
gated model G's **0.4977**. A gap of **0.027**.

That number does not arrive alone. Three other measurements point the same way:

* the gate sits at **0.54 with a spread of 0.005** — it is barely moving, so it
  is barely choosing between the branches;
* the fusion carries a residual that reinjects both branches ungated, so a gate
  that does nothing still passes signal through;
* cross-camera performance collapses (0.8941 → 0.3500 on the detector), which is
  the regime in which extra capacity usually stops paying.

Read together they say one thing from three directions: **the fusion machinery
may not be doing measurable work on this corpus, and mean-over-time plus a
classifier may be the whole story.**

That is a survivable outcome. It is a legitimate, publishable negative result
for a frozen-backbone paper, and §2.5.5 requires it be reported rather than
dropped. It is **not** survivable if the threshold for "material" is chosen
after the 160 runs land, because then the threshold is chosen to make the
architecture survive.

## Decision

The following is fixed **before** the leave-one-camera-out suite completes.

### The test

**Paired within fold, then aggregated over folds.** For each of the four folds,
compute `G − H` at the same seed, average over the five seeds, and take the
paired mean and bootstrap 95% CI across the four fold-level differences.

Not mean-versus-mean: G and H see the same cameras in the same folds, so the
fold is a blocking factor and ignoring it discards the only thing making n=4
tolerable.

### The power, stated before the result

A paired *t*-test at n=4 folds has df=3 and `t_crit = 3.182`, so

```
minimum detectable difference = 1.591 × sd(fold-level G − H)
```

| sd of the fold differences | smallest gap this test can resolve |
|---|---|
| 0.010 | 0.016 |
| **0.017** | **0.027** |
| 0.030 | 0.048 |
| 0.050 | 0.080 |

**To resolve the observed 0.027, the fold-to-fold standard deviation of the
difference must be at most 0.017.** Given that P54 measured a *seed* spread of
0.242 on one config on one fold, a fold-to-fold sd that small is unlikely.

**So the expected outcome of this test is "cannot distinguish."** That is
written here, in advance, so that it cannot later be presented as a surprise or
as a success.

### What "cannot distinguish" means, and what it does not

A non-significant result at n=4 is **not evidence of equivalence**. It will be
reported as *underpowered to separate*, with the minimum detectable difference
printed beside it, and never as "G and H perform equivalently" or "the gate adds
nothing." Those are claims this experiment cannot support in either direction.

### The material threshold

**A gap of 0.05 macro F1 or more, with the interval excluding zero, counts as
the architecture doing measurable work.** Below that, it does not — regardless
of the *p*-value, because at this n a significant result on a 0.02 gap would be
a small-sample artifact before it was a finding.

### The consequence, also fixed now

If `G − H` does not clear the threshold:

> The paper's contribution is **the benchmark and the protocol** — the
> harmonised multi-source taxonomy, the published leave-one-camera-out splits,
> and baselines under that protocol — with the architecture reported as **not
> separable from its own floor at this corpus size**. The gate remains a
> described artifact with its measured behaviour reported, not a claimed
> improvement.

This is a narrowing of the claim, not a failure of the project, and it is the
claim ADR-019 and P45 have been pointing at for a week.

## Timestamp

Written 2026-08-22 while the suite was **13 of 160 runs** complete, with only
fold 0 seeds 42 and 1 partially in hand and no fold-level differences computed.
The commit that adds this file precedes the commit that adds
`loco_summary.csv`, which is checkable in `git log`.

## Consequences

- `scripts/run_loco.py` will gain the paired `G − H` computation and print the
  minimum detectable difference beside it, so the caveat is generated rather
  than remembered.
- The result is reported whichever way it lands (§2.5.5).
- The same reasoning applies to any other pair of configs the ablation is asked
  to separate. The 0.05 threshold and the paired-within-fold structure are
  properties of this corpus, not of this pair.

## Alternatives rejected

**Decide after seeing the numbers.** The thing this exists to prevent.

**Report the mean difference with no test.** A bare 0.027 in a table reads as a
result, and at n=4 it is not one.

**Add seeds until it is significant.** Seeds do not increase n here: the fold is
the unit, and there are four cameras eligible to be one (ADR-019). More seeds
tighten each fold's estimate and leave the denominator untouched.
