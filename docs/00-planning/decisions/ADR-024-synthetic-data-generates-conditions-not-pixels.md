# ADR-024 — Synthetic data generates *conditions*, not pixels

**Status:** Proposed · **Date:** 2026-10-14 · **Scopes what simulation is allowed to supply; changes no component, and narrows nothing in [CLAIMS.yaml](../CLAIMS.yaml)**

## Context

The question that prompted this: *we have the Bengaluru dataset and foreign
datasets, and we have a detector that already recognises the vehicle classes —
can we combine them into a synthetic dataset, and compare India against foreign
against synthetic?*

It is the right question, and answering it properly requires separating three
things that the word "synthetic" is covering at once:

| | What it is | Already in the project? |
|---|---|---|
| **(a) harmonised real union** | several real datasets mapped to one taxonomy and trained jointly | **yes** — [ADR-006](ADR-006-curate-then-collect-dataset.md) Part A, and detector arm D1 |
| **(b) generated conditions** | a simulator producing traffic state with known labels | partly — SUMO exists for control, is not used as a data source |
| **(c) generated or warped imagery** | rendered frames, style transfer, geometric augmentation | **yes** — detector arm D2 is geometric augmentation |

Two of the three are already built. What follows is about which of them should
be extended, and the answer turns on a measurement the project already holds.

### The detector's domain gap is already closed by real data

BMD-45 ([DATASETS §BMD-45](../DATASETS.md)) is **45,986 images / 481,947 boxes
from 3,679 operational Safe City CCTV cameras in Bengaluru**, CC BY 4.0 and
ungated, at the deployment viewpoint in the deployment country, carrying
**65,899 three-wheeler boxes** against 1,001 dashcam auto-rickshaw boxes in the
whole IDD test split.

The BMD-45 paper measures the alternative directly: **models fine-tuned on
UA-DETRAC reach 33.6% mAP@0.50:0.95 on Bengaluru CCTV, against 83.8% trained
in-domain.** Foreign elevated data transfers, and it transfers about 40% of the
way.

The project's own A31 arms agree, and locate the deficit:

| Arm | Trained on | dashcam | oblique | steep (pitch 1.0) |
|---|---|---|---|---|
| D0 | IDD only — Indian dashcam | 1.96 | 3.76 | **0.48** |
| D1 | IDD + BMD-45 — Indian dashcam + Indian CCTV | 1.84 | 9.72 | 4.44 |
| D2 | + geometric augmentation | 1.88 | **9.88** | **5.00** |

Detections per frame, `experiments/results/detector_arms.csv`. **These are
counts, not accuracy**, so the D1→D2 delta cannot be read as an improvement
without mAP — but D0's 0.48 at the deployment geometry is not a measurement
artefact, it is a model that cannot see.

**What the deficit was is the useful part: viewpoint, not country.** Both D0 and
D1 are Indian. Adding Indian *elevated* data recovered 9.25× at steep. No
foreign data appears in any arm.

So for the detector, generating imagery would substitute for data the project
already holds under an open licence, in the right country, at the right
viewpoint. That is not a gap worth filling with synthesis.

### The forecaster's gap is not a domain gap, and no dataset closes it

The corpus is **153 windows** — 55 train, 35 val, 63 test — at `T=60`,
`step_s=2`, `stride_s=30`. That is the whole of it.

BMD-45 cannot help. 45,986 images across 3,679 cameras is about **12.5 frames
per camera**, and a single 60-step window needs 120 consecutive seconds from one
fixed camera. IDD is dashcam. UA-DETRAC and CityFlow are foreign and
lane-disciplined. **No available dataset — Indian, foreign, or combined —
contains continuous fixed-camera video of heterogeneous junction traffic at the
hours this model needs.**

That is the gap, and it is the one synthesis can actually address.

### The thing a simulator can do that no dataset can

A real road has whatever lane discipline it has. It offers no counterfactual.

SUMO's sublane model ([ADR-010](ADR-010-sumo-heterogeneous-traffic.md)) makes
lateral discipline a **parameter**. The same demand can be generated at a chosen
degree of discipline, repeatedly, with exact labels. That permits a question no
observational corpus can answer:

> How much delay per vehicle is attributable to lane indiscipline, holding
> demand and geometry fixed?

This reframes the project's weakest position — *we do not have enough Indian
video* — into a question that does not need more video to answer, and it
produces a number a transport authority can act on rather than a benchmark
delta.

## What the pilot found, before anything was built on it

`scripts/discipline_pilot.py`, 900 s, saturated, Webster at s=750, five paired
seeds, demand pre-expanded so every condition saw byte-identical traffic.
Raw results in `experiments/results/discipline_pilot.csv`.

**1. The discipline parameter is binary, not continuous.** The vehicle-type
attributes ADR-010 sets — `latAlignment`, `lcSublane`, `minGapLat` — move mean
lateral offset from 0.504 m to 0.482 m, a 4% separation. Sweeping
`--lateral-resolution` over 0.2 / 0.4 / 0.8 / 1.6 gives offsets of 0.5756 /
0.5066 / 0.5040 / 0.5453 m, which is not even monotone. **Disabling the sublane
model gives exactly 0.0000 m**, and with it disabled the vType attributes change
nothing at all — `d=0` and `d=1` returned identical 14.19 s and 0.882 arrived.

So the planned *sweep* has no gradient to sweep. The honest intervention is the
two-arm contrast ADR-010 already declares: sublane model on against off,
manipulation check 0.4803 m against 0.0000 m.

**2. The expected sign is wrong, and the reason matters more than the number.**

| seed | indisciplined | disciplined | difference |
|---|---|---|---|
| 1 | 12.35 s | 14.59 s | +2.23 |
| 7 | 14.55 s | 18.99 s | +4.44 |
| 13 | 13.49 s | 20.01 s | +6.52 |
| 21 | 12.83 s | 15.32 s | +2.49 |
| 42 | 10.85 s | 14.17 s | +3.32 |

Paired mean **+3.80 s, sd 1.75, disciplined slower in 5 of 5 seeds**, with
throughput also lower (673–698 against 684–704).

**In SUMO, lane indiscipline reduces delay.** That is not a bug. Narrow vehicles
filtering into lateral gaps discharge more per green, and the simulator models
that capacity gain faithfully. What it does not model is the cost: **SUMO has no
collision model here**, so indiscipline carries none of the crash risk,
pedestrian exposure or unpredictability that is its actual price on a real road.

The consequence is a framing change, not a result to report. **This experiment
measures the capacity effect of lateral filtering. It cannot measure the cost of
indiscipline, and publishing "+3.8 s" as a case for lane discipline — or against
it — would be an artefact of a simulator with no crashes in it.** The project
owner's own qualification anticipated exactly this: the simulated behaviour has
to be validated against observed data before any real-world effect is claimed.

**3. Seed noise exceeds the effect at small n.** Wait ranged 10.76–18.22 s
across conditions whose lateral behaviour was near-identical. Any reported
figure needs the project's 30-seed, bootstrap-CI, paired-test protocol
(NFR-07 to NFR-10); five seeds establish a manipulation, not an effect.

## Decision

**1. Simulation supplies conditions and sequences. It does not supply imagery.**
No rendered or style-transferred frames enter the detector's training set. The
existing geometric augmentation (D2) stays, because warping real BMD-45 frames
is augmentation of real data and is already evaluated as an arm.

**2. The lane-discipline *sweep* is withdrawn; a two-arm *capacity contrast*
replaces it.** The pilot found no continuous gradient to sweep, so matched
scenarios at graded discipline levels are not buildable as specified. What is
buildable, and already declared by ADR-010, is the sublane model on against off
at 30 paired seeds under the best-tuned Webster baseline
([ADR-012](ADR-012-webster-saturation-flow.md)) and under PPO, with bootstrap CI
and a paired test (NFR-07 to NFR-10).

**It is reported as a capacity effect and never as a case for or against lane
discipline.** The simulator has no collision model, so it prices filtering's
benefit and none of its cost. Any sentence of the form "indiscipline saves
*n* seconds" is forbidden by this ADR regardless of what the runs return.

**3. Synthetic occupancy sequences are permitted for the count-only baselines
and the linear probe, and are forbidden for the vision model.** SUMO emits
per-lane counts per step by vehicle type; those convert through the same
PCU path as the real corpus ([ADR-017](ADR-017-pcu-thresholds.md)). They
carry no pixels, so configs A–G cannot consume them, and config H and the
count-based baselines can. The purpose is narrow and worth stating: it separates
*is this task learnable at all* from *is 153 windows enough*, which are
confounded today and cannot be told apart from the real corpus alone.

**4. Every reported number from synthetic data is labelled as such, and no test
split is synthetic.** A result quoted on synthetic data with a real-data framing
is the same circularity the project already refuses for count-derived labels
(corpus spec §5.2).

**5. Synthetic data must not be used to make the `domain` claim pass.** A
simulated Indian junction is not an Indian camera. `domain` is red in
[CLAIMS.yaml](../CLAIMS.yaml) because no fold-eligible camera is Indian, and
that is a statement about the evaluation corpus which generation cannot alter.
`scripts/check_claims.py` has no override and must not acquire one.

## Alternatives considered

**Photorealistic synthetic frames (CARLA, or a game engine in the manner of
Richter et al.).** Rejected on cost and on need. The
[FEASIBILITY-AUDIT](../FEASIBILITY-AUDIT.md) puts ~1,200 h of specified work
against ~715 h of capacity; a rendering and domain-adaptation pipeline does not
fit, and §"The detector's domain gap" above shows it would be solving a problem
the project does not have.

**Generative domain translation (CycleGAN / CyCADA) from foreign footage to
Indian-looking footage.** Rejected for the same reason, plus two of its own: it
would import the licence of whatever it was trained on, and a translated frame
has no ground truth beyond what the translation preserved.

**Training the detector on foreign elevated data instead of BMD-45.** Rejected
on the published measurement: 33.6% against 83.8%.

**Spending the Bengaluru data on synthesis rather than on evaluation.** Rejected
on the same reasoning `scripts/evaluate_detector_arms.py` already applies to the
self-recorded footage: real in-domain data is worth more as an honest test set
than as more training data, and it is the only unbiased test the project will
have.

## Consequences

**Gained.** A contribution that does not depend on acquiring more video; a way
to tell a learnability failure from a data-volume failure; and an honest answer
to "India vs foreign vs synthetic" that rests on a measurement rather than on a
new pipeline.

**Cost.** The lane-discipline sweep is new work against a capacity that is
already over-subscribed. It is affordable only because it reuses
`scripts/build_sumo_demand.py`, `scripts/benchmark.py` and the existing PPO
arms, and because it renders nothing.

**Unchanged.** The claims. This ADR narrows no claim and promotes none. `domain`
and `class_coverage` remain red, and `releasable` remains aspirational while
every camera in `data/cameras.json` carries an unresolved licence.

**Owed.** A PRD amendment and a changelog entry if the sweep produces a reported
number, per the project's standing rule that a measurement contradicting the PRD
is fixed by a P entry and an amendment rather than a workaround.

## Acceptance

Unaccepted. [ADR-006](ADR-006-curate-then-collect-dataset.md) and
[ADR-008](ADR-008-prototype-descoping.md) set the precedent that the project
owner signs, and that such a signature is **not** a faculty-guide signature.
This one changes what the paper offers as its contribution, so it needs that
signature before the sweep is built.
