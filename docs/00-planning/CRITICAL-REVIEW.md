# Critical review — is the formulation right, not just the implementation?

**Date:** 2026-08-18 · **Scope:** the scientific premise, not the code

Every audit so far has asked "is this implemented correctly?" — and found real
defects: P15, P16, the metrics index bug, the self-confirming viewpoint check.
This one asks the question underneath: **is the thing being built the right
thing?**

## What checks out

Three things I expected to find missing are already specified, and finding them
present is the reason the rest of this review can be sharp rather than
foundational.

**A persistence baseline exists.** §14.3 lists `Naive — last-value prediction`.
For a 60-second horizon on a highly autocorrelated signal, "the same as now" is a
strong predictor, and a project that omits it can claim a win it has not earned.

**Count-sequence baselines exist.** LSTM, GRU and CongestFormer all run on count
sequences, so the comparison between "pixels" and "counts" is set up rather than
assumed away.

**The PPO forecast arm is honestly labelled.** ADR-009's `surrogate` arm fills
state indices 11–14 from a SUMO-derived proxy and its own config note says it is
"NOT evidence that MFSTNet helps". That is the correct framing and it is written
where someone would otherwise be tempted.

## Risk 1 — the label definition may make the vision claim unwinnable

**This is the most important thing in this document.**

ADR-002 derives every congestion label from detector counts through the §14.1
thresholds:

    LOW < 5 vehicles · MEDIUM 5–15 · HIGH > 15

So the label is, by construction, **a deterministic function of the vehicle
count**. Now consider the two model families being compared:

| | what it observes | relation to the label |
|---|---|---|
| LSTM / GRU / CongestFormer | the count sequence | **the exact variable the label is computed from** |
| MFSTNet | pixels | must first *recover* the count, then extrapolate |

A count-sequence model sees the label-generating variable directly. MFSTNet sees
a noisy encoding of it and has to invert the encoding first. **On auto-labelled
data the count baselines should win by construction, and MFSTNet can at best
match them minus detector error.**

That is not a flaw in the experiment. It is a flaw in the *premise*: if
congestion is **defined** as a count threshold, then vision cannot beat counting,
and "camera-only congestion prediction" is unfalsifiable in the wrong direction —
it is set up to lose.

### The escape hatch already exists, and it must be made load-bearing

A9 human-verifies the **test split**. That breaks the circularity, because a
human judging congestion is not applying `count > 15` — they see queue length,
whether vehicles are stopped or moving, spatial bunching, blocked turns. Those
are visible in pixels and **absent from a count**.

So the vision claim is winnable, but only on human-verified labels.

**Recommendation, and it is a one-line change with large consequences:**

> The headline MFSTNet-vs-baselines comparison SHALL be reported on the
> human-verified test split. Auto-labelled results may be reported alongside and
> must be labelled as such.

Without that sentence, the obvious thing happens: the biggest, cleanest table is
the auto-labelled one, the count baselines top it, and the project concludes its
own approach failed — when what actually failed was the label definition.

A11 already notes that count-consuming baselines "share error structure with
auto-derived labels", but frames it as a bias *against* MFSTNet. It is stronger
than a bias. It is a structural guarantee, and the mitigation needs to be stated
as a reporting rule rather than left as an observation.

## Risk 2 — frozen backbones cap what vision can contribute

Both encoders are frozen (ADR-005 caches their outputs, which only works because
they are). So the model cannot learn features for this task; it can only
recombine ImageNet and DINOv2 features.

The things that distinguish congestion from vehicle count — queue length,
stopped-versus-moving, spatial bunching — are exactly the task-specific
properties a frozen generic encoder is least likely to expose. Per-lane ROI
pooling (A8) recovers spatial structure, which helps, and DINOv2 (ADR-007) is a
much better frozen representation than supervised ViT. But the ceiling is set by
what the frozen features already encode.

**This interacts badly with Risk 1.** If the vision advantage lives in properties
frozen features do not expose, then even on human-verified labels the advantage
may not materialise.

ADR-007 already schedules a late LoRA experiment. **That experiment is more
important than it currently looks** — it is the only mechanism in the plan that
lets the encoder learn anything task-specific, and it should be treated as a
planned arm rather than an optional extra.

## Risk 3 — the gate has no evidence (P16, already raised)

Recorded here only to place it in the ranking. The gate is the narrowed novelty
claim and currently sits at its initialisation. The falsification test is
pre-registered.

## What I would change, in priority order

1. **Add the reporting rule from Risk 1.** One sentence, prevents the project
   from concluding the wrong thing from a correct experiment.
2. **Promote the LoRA arm** from optional to planned, because it is the only
   route to task-specific visual features and Risk 2 otherwise caps the result.
3. **Run P13 and the Naive baseline early**, before MFSTNet trains. If
   last-value or XGBoost-on-counts already scores well on human-verified labels,
   that number reframes the entire contribution — and it is far better to know
   at Week 3 than at Week 14.

## What is genuinely right about this project

Stated plainly, because a review that only lists risks is not an assessment.

The **negative results are reported**: A31 missed its criterion and was recorded
as missed; P15 voided a headline and it was voided; the DataCluster and Bellevue
rejections were both reversals of my own recommendations.

The **thresholds are pre-registered**: A28's statistic, A31's two criteria, P16's
falsification bounds and P12's 1% rule were all fixed before the data that would
settle them existed.

The **comparisons hold one thing fixed**: S14 changed data and not
hyperparameters; the detector arms table changes one variable per row; the
benchmark runs every controller through one measurement path.

Those three habits are why the defects above were findable at all. A project
without them would have shipped P15 into a paper.
