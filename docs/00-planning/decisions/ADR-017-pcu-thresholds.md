# ADR-017 — Congestion thresholds: PCU units, and pre-registration

**Status:** PROPOSED — requires faculty guide sign-off · **Date:** 2026-08-19
**Affects:** PRD §14.1, §14.3, §14.5 · A30 · ADR-002 · [P20](../PRD-CHANGELOG.md)
**Supersedes nothing.** §14.1 stands until this is accepted.

## Context

Two findings collided.

[P20](../PRD-CHANGELOG.md) measured the S06 pilot on 20 minutes of elevated
Dhaka footage and found §14.1's thresholds unusable on that camera: `LOW < 5`
never occurred once, because the quietest moment in twenty minutes still had
nine vehicles in view. A30 has been open on this question since before there was
data to settle it.

Separately, the [ITD dataset](https://github.com/teg-iitr/ITD-Indian-traffic-dataset)
(IIT Roorkee, 2024, CC BY-NC 4.0) annotates against **Indo-HCM**, the Indian
Highway Capacity Manual. Indo-HCM exists because heterogeneous traffic cannot be
described by a vehicle count, and it publishes passenger car unit equivalences
to fix that.

## The measurement

All figures from `pilot_counts.csv` and the fleet-mix probe, 242 samples,
`s14_yolov8s_joint_best` at conf 0.45, one camera.

**Fleet mix:** motorcycle 44.9% · car 24.6% · auto-rickshaw 21.5% · bus 6.9% ·
truck 2.2%.

Four combinations of series and thresholds, through `analyse_counts`:

| series | thresholds | LOW | MED | HIGH | transition | naive |
|---|---|---|---|---|---|---|
| raw count | §14.1 `<5 / 5–15` | **0%** | 83% | 17% | 31.0% | **69.0%** |
| raw count | calibrated p33/p67 | 24% | 52% | 24% | 51.7% | 48.3% |
| PCU | §14.1-equivalent | **0%** | 59% | 41% | 41.4% | 58.6% |
| PCU | calibrated p33/p67 | 34% | 34% | 31% | 69.0% | **31.0%** |

### What this does *not* show

The obvious argument for PCU is that raw counts overstate congestion where
motorcycles dominate. **On this camera that argument is wrong**, and it is worth
saying so plainly. In aggregate the measured fleet weighs **1.06 PCU per
vehicle** — the many cheap motorcycles very nearly cancel the few expensive
buses. PCU does not systematically rescale this footage.

### What it does show

**Resolution.** Over 242 samples the raw count took **24 distinct values**; PCU
took **139**. Counts cluster so tightly that **22% of samples sat exactly on the
two calibration thresholds**, where an integer cut-off cannot separate them.
That is why calibrating raw counts to balanced thirds yields 24/52/24 rather
than the intended 33/33/33, while PCU yields 34/34/31.

A threshold you cannot land on is a threshold you cannot calibrate. That is the
defensible reason to prefer PCU here, and it is independent of the road-space
argument that did not survive contact with the data.

## Three detectors, one conclusion (added 2026-08-19)

The same clip counted by three independently trained detectors, each under
§14.1 and under its own calibrated p33/p67:

| detector | thresholds | LOW | MED | HIGH | transition | naive |
|---|---|---|---|---|---|---|
| COCO `yolov8n` | §14.1 | 3% | **97%** | 0% | 6.9% | 93.1% |
| COCO `yolov8n` | calibrated | 14% | 52% | 34% | 62.1% | 37.9% |
| ours `s14_joint` | §14.1 | 0% | **83%** | 17% | 31.0% | 69.0% |
| ours `s14_joint` | calibrated | 24% | 52% | 24% | 51.7% | 48.3% |
| ITD v1.2 xl | §14.1 | 0% | 14% | **86%** | 24.1% | 75.9% |
| ITD v1.2 xl | calibrated | 21% | 45% | 34% | 55.2% | 44.8% |

**Every detector produces a degenerate corpus under §14.1**, and every one
becomes usable under calibration. COCO and ours collapse into MEDIUM; ITD, which
counts ~62% more vehicles (p50 21 against 13), collapses into **HIGH** — its p10
is 16, above §14.1's HIGH boundary, so nine windows in ten are HIGH before the
clip even starts.

That §14.1 fails in *both directions* depending only on how good the detector is
is the strongest available evidence for this ADR. The thresholds are not
mis-tuned; they are the wrong kind of quantity.

### And a claim of ours that this deflates

A better detector was expected to improve the corpus labels materially. **On this
evidence it does not.** Once thresholds are calibrated, all three detectors give
a similar structure — transition 51.7-62.1%, naive 37.9-48.3%. Changing the
threshold rule moves the naive baseline by roughly **30 points**; changing the
detector moves it by about **10**.

The detector is not irrelevant — more accurate counts make the labels *truer*
even where the distribution looks similar, and nothing here measures truth
without ground truth. But "use the better detector to get a better corpus" is a
much weaker argument than the calibration one, and it should not be presented as
the reason to adopt either.

## The finding that matters more than the units

**The naive baseline is not a property of the traffic.** On identical footage it
ranges from **69.0% to 31.0%** depending only on where the thresholds sit.

That is a researcher degree of freedom sitting directly under the headline
comparison. Whoever sets the thresholds sets the difficulty of the task, and
therefore sets how impressive any model looks against "assume nothing changes".
Choosing thresholds after seeing model results would make the headline
meaningless, and nothing currently forbids it.

It also cuts against the reading that a low naive baseline is simply good. A
69% transition rate may mean the task is genuinely dynamic, or it may mean the
labels flicker because narrow bands put more windows near a boundary. **Those
two are not distinguishable from the transition rate alone**, and this ADR does
not claim to have separated them.

## Decision

1. **Congestion is defined on PCU-weighted occupancy**, not vehicle count, using
   Indo-HCM 2017 intermediate/two-lane urban values. Classes with no Indo-HCM
   entry (`e_rickshaw`, `cattle`) carry a stated assumption; an unmapped class
   raises rather than defaulting to 1.0.
2. **Thresholds are calibrated per camera** at the p33/p67 of a calibration
   period, and **recorded in the corpus manifest**. A threshold in absolute
   units describes the view, not the road.
3. **Thresholds are pre-registered.** They are fixed from a calibration split
   that is disjoint from test, written into the manifest, and **committed before
   any model trains**. Changing them afterwards voids every result computed
   under them, exactly as [ADR-012](ADR-012-webster-saturation-flow.md)'s
   disqualifications and A28's statistic are fixed in advance.
4. **The naive baseline is reported with its thresholds**, always. A bar of
   "69%" or "31%" is uninterpretable without them.
5. **`§14.1` is amended, not worked around.** Until sign-off, `mfstnet/corpus/pcu.py`
   exists and is tested but is not wired into the corpus builder, and §14.1
   remains in force.

## Consequences

- **Every count-consuming baseline changes** (P13/§14.3 LSTM, GRU, XGBoost,
  Naive). They consume the same series, so the comparison stays fair, but no
  number computed under §14.1 thresholds carries over.
- **A30 closes** on measurement rather than assertion.
- **The PPO state vector is unaffected.** It carries class predictions and the
  gate mean, not raw counts (PRD §13.1) — a contract change would have
  invalidated every checkpoint.
- **One camera.** These percentiles are Rampura's. Nothing here generalises to
  another mounting height, and the point of item 2 is that it must not try to.

## Rejected

**Keep §14.1 unchanged.** It produces a corpus with no LOW class on the only
camera measured. Macro F1 over a class with zero support is undefined, not
merely unstable.

**Recalibrate raw counts per camera, without PCU.** Cheaper and needs no new
standard. Rejected on the resolution measurement above: with 22% of samples on
the threshold values, calibration cannot reach balanced classes.

**Adopt ITD's weights to sidestep the question.** They are gated behind a request
form, are CC BY-NC, and are evaluated on their own test set — 0.91 mAP50 there
is not comparable to our 0.8915 here. See the ITD assessment in
[DATASETS.md](../DATASETS.md).

## Open

- Whether a 69% transition rate is signal or threshold-boundary flicker. Needs
  the human-verified split (A32) to settle, since a human judging congestion is
  not applying a threshold at all.
- `cattle` at 1.50 PCU is a low-confidence assumption. It was 0% of the measured
  fleet, so it has not yet mattered.

---

## Proposed amendment, 2026-08-20 — the calibration rule and its scope

**Status:** PROPOSED, folded into the same sign-off. Two defects were found by
running decision 2 against a real multi-camera corpus rather than one camera.
Evidence: [P34](../PRD-CHANGELOG.md#p34), [P37](../PRD-CHANGELOG.md#p37),
`experiments/results/corpus_yield.csv`.

### 1. `low_max = p33 − 1` makes LOW unreachable on per-lane counts

The measurement behind this ADR is on **whole-frame** counts from one camera,
where "the quietest moment in twenty minutes still had nine vehicles in view".
The corpus labels **per-lane** counts, and those are zero-inflated: with four
lanes on a camera, **41.2% of per-lane counts are zero**. So p33 = 0,
`low_max` = −1, and nothing satisfies `count ≤ −1`.

Run as written, `--calibrate` produced **0% LOW in every split** — the exact
degeneracy this ADR was raised to remove.

> **Amend decision 2 to** `low_max = max(0, p33 − 1)`, with `med_max` widened
> to at least `low_max + 1`. When p33 is zero, **LOW means "an empty lane"**,
> which is what the class should mean; the unwritten alternative expressed it
> as an impossibility.

### 2. The implementation calibrated globally, which decision 2 rejects

Decision 2 already says thresholds are per camera, and gives the reason: *"A
threshold in absolute units describes the view, not the road."* The
implementation pooled every camera into one pair. Measured on the five-camera
pilot:

| camera | p33 | p67 | zero share |
|---|---|---|---|
| 4K Road traffic | 0 | 1 | 64% |
| Mumbai Andheri | 4 | 9 | 0% |
| Pov_Thursday | 4 | 9 | 8% |
| South Extension | 8 | 18 | 9% |
| video1 | 13 | 19 | 0% |
| **pooled** | **0** | **3** | 41% |

The pooled p67 is 3 while video1's p33 alone is 13. Pooled thresholds mark
almost everything HIGH on a busy camera and LOW on a quiet one.

Resulting label distribution on the pilot:

| labelling | train | test |
|---|---|---|
| §14.1 defaults (4 / 15) | 83.5 / 12.9 / 3.5 | degenerate |
| pooled calibration | 57.2 / 19.2 / 23.6 | degenerate |
| **per camera** | **59.2 / 26.0 / 14.7** | **25 / 50 / 25** |

> **No change to decision 2 is needed — the code was wrong, and is fixed.**
> `--calibrate` now calibrates per camera and records `thresholds_by_clip` and
> `threshold_scope` in the manifest. `--calibrate-global` is kept only so the
> two arms can be compared for this sign-off.

### The honest cost of per-camera thresholds

Per-camera calibration means **HIGH is relative to the camera's own range**. On
a lane that only ever holds zero or one vehicle there is no congested state,
and calibration must not manufacture one — two vehicles on a free-flowing
motorway is not congestion however unusual it is for that camera.

So a quiet camera contributes **no HIGH examples at all**. That is the correct
behaviour and it is still a cost: the HIGH class is then carried by a subset of
cameras, and cross-camera generalisation for that class is tested on fewer
viewpoints than the other two. It should be reported alongside the per-class
results rather than discovered from them.

**This is the trade the guide is being asked to accept**: pooled thresholds
give every camera all three classes and make them mean different things;
per-camera thresholds make them mean the same thing and give some cameras
fewer.
