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

### First, the size of the thing being measured

A fold's test split is one camera. In lane-windows that is **140, 252, 44 and
136** across the four folds — **572 paired observations in total**, and 44 in
the smallest.

Measured on fold 0's actual class support (62 LOW, 78 MEDIUM, 0 HIGH), flipping
one window's prediction moves macro F1 by a **median of 0.0029** — finer than
the `1/n = 0.0071` a reader would estimate, because macro F1 averages per-class
F1 and an absent class contributes a constant 0. So:

* the observed `G − H` gap of 0.027 is about **9 windows**;
* the material threshold of 0.05 is about **17 windows**;
* config C to config F, the full span of the fold-0 table, is about 96.

**A doubling of parameters that changes nine argmaxes out of 140 is not
principally a statement about the architecture. It is a statement about what
this test set can resolve.** That is the finding, and it is more consequential
than any single pairwise comparison in the ablation.

### The test, and the aggregation order

**Paired within fold, then aggregated over folds.** Not mean-versus-mean: G and
H see the same cameras in the same folds, so the fold is a blocking factor and
ignoring it discards the only thing making n=4 tolerable.

The order is fixed here because it is an analytic degree of freedom and it
changes the answer:

1. within a fold, take the **mean over the five seeds** for G and for H;
2. take the **difference of those means** — one number per fold;
3. across the **four folds**, take the paired mean and a bootstrap 95% CI.

Not the reverse (difference per seed, then pooled across all twenty runs), and
not pooled. With a seed spread of the magnitude P54 reported, averaging seeds
first shrinks the within-fold noise by about √5 before the fold-level variance
is estimated; doing it the other way round mixes seed noise into the fold
denominator. **Choosing that order after seeing `loco_summary.csv` would be a
free parameter**, and this document exists to close those.

### Two tests, answering two different questions

These are **not** primary and fallback for one question. Naming them as
substitutes would invite exactly the swap this ADR exists to prevent — running
both and reporting whichever separates.

**Q1 — does the architecture generalise better to a camera it has not seen?**
This is the paper's claim. The unit is the camera, because ADR-019 makes the
camera the unit of generalisation and A28 established that consecutive windows
share 54 of 60 frames. **n = 4.** Underpowered, as quantified below. This is the
number that supports or fails to support the architectural claim, and no other
test can stand in for it.

**Q2 — on the windows we have, do G and H decide differently at all?**
A diagnostic, not a claim. G and H are scored on the same 572 lane-windows, so
the comparison is paired per window: report the **discordance count** — how many
of the 572 the two models label differently — and McNemar's test on the
discordant pairs.

The discordance count is the most informative single number here and needs no
distributional assumption at all. If G and H disagree on nine windows out of
572, that is a complete description of the difference between them, and the
`p`-value adds nothing to it.

**McNemar's `p` will be reported with its assumption violated, and labelled.**
It treats the 572 windows as independent and they are emphatically not —
consecutive windows from one camera share 90% of their frames. It will therefore
overstate significance, possibly by a large factor, and **cannot be used to
support a generalisation claim**. It is reported because "the two models are
decision-identical on this data" and "the two models differ but the fold test
cannot see it" are different situations, and Q1 alone cannot tell them apart.

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
difference must be at most 0.017.**

### The uncomfortable version of that, said plainly

P54 measured a seed spread of **0.242** on one config on one fold. The full span
of the fold-0 config table is 0.211 (C) to 0.499 (F) — about **0.29**.

**The movement from changing a random seed is comparable to the entire distance
between the best and worst architectures in the table.** Five seeds brings the
standard error of a fold mean to roughly `0.242 / √5 ≈ 0.108`, still four times
the gap being tested for.

So the honest prior, written before the results: **nothing in the eight-config
table is likely to separate from anything else.** The expected outcome of Q1 is
"cannot distinguish", and that is recorded here so it cannot later be presented
as a surprise, a disappointment, or a success.

One caveat on that prior, because it cuts the other way. **The 0.242 figure is
itself a withdrawn pre-P55 number** — measured while cached windows were views
into a released memory map. It is used here as an order-of-magnitude expectation
and nothing more.

**Re-measured on clean runs the same day: 0.1853**, from the first two seeds of
fold 0 after the fix. Lower than 0.242 and the same order, so the conclusion is
unchanged: `0.1853 / √5 ≈ 0.083`, still three times the gap being tested for.
Re-measuring it was the first thing the clean suite was asked for, because it is
the number that decides whether five seeds was ever enough — and on this
evidence it is not.

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

**Stated in the three-class-with-zeros convention** that ADR-019 fixes: macro F1
over all three classes, an absent class scored 0. On a fold whose test camera
has no HIGH window the metric caps at 0.667, so 0.05 there is **7.5% of the
reachable range**, and the same 0.05 expressed present-classes-only is
approximately **0.075**. A threshold whose meaning depends on an unfixed
convention is not pre-registered in any useful sense, which is why the
convention is named here rather than assumed.

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
  than remembered. Q2's discordance count needs per-window predictions, which
  the per-run CSVs do not carry — a metrics row cannot be un-aggregated back
  into the 572 decisions behind it.
- **The running suite is not being restarted for that.** Q2 needs only G and H,
  so it costs `2 configs × 4 folds × 5 seeds = 40` runs afterwards rather than
  160, and restarting would discard the runs already paid for while making the
  suite's artifacts inconsistent — some runs carrying predictions and some not.
  Prediction dumping is added now and the 40 runs follow the suite.
- **Report the four per-fold differences as raw numbers beside the interval.**
  Four numbers are more honest than a confidence interval computed over four
  numbers, and these folds are **not exchangeable** — one test camera has no
  HIGH window at all and another has 44 lane-windows in total
  ([P57](../PRD-CHANGELOG.md)). `run_loco.py` emits `macro_f1_per_fold`.
- **The paper is planned for the "cannot distinguish" outcome starting now**:
  benchmark, protocol, and a well-characterised negative result. If the suite
  separates something, that is an upgrade to a plan that already works, not a
  rescue of one that does not.
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
