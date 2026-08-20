# Decision Brief — everything awaiting a call

**To:** Faculty Guide · **From:** Project Team · **Date:** 2026-08-16
**Deadline on items 1–3: 2026-08-18** (two days). Items 4–9 have no deadline.

> This page exists because decisions kept accumulating across five documents,
> which is how sign-off stops happening. Everything is here with a
> recommendation, the evidence behind it, and what we will do if there is no
> reply. Detail is one click away in each linked record; nothing here restates it.

**How to respond:** a line per item is enough — "1 agree, 2 agree, 3 use option
B, rest agree". Anything you do not mention takes the stated default.

**On the defaults.** A default that fires on silence is not a way around
sign-off. It is what stops silence from becoming a decision nobody made. Every
default below is **reversible** — none destroys work or forecloses the
alternative, and each says what reversing it would cost.

---

## The three with a deadline

### 1. PPO action space — keep-or-switch vs (phase, duration)

**Record:** [ADR-015](decisions/ADR-015-success-criteria-and-priorities.md) · **Default: adopt keep-or-switch**

PRD §13.1 specifies 12 discrete (phase, duration) actions. Under that space the
agent only acts at phase end, by which time state index 10 `phase_remaining` is
always 0 — **one of sixteen state dimensions is structurally dead** (P11,
asserted by a test so it cannot be forgotten). Keep-or-switch at a fixed decision
interval is the standard formulation in the RL traffic-control literature and
makes the feature meaningful.

**Both are implemented, and the screen is now done.** 5 seeds each, held-out
evaluation episodes:

| action space | mean wait | sd |
|---|---|---|
| `phase_duration` (§13.1) | 25.95 s | 9.47 |
| **`keep_or_switch`** | **12.78 s** | **2.03** |

**50.8% better and a quarter as variable.** §13.1 stays implemented behind the
flag, so nothing graded is lost. This is a screen — 5 seeds, 50k timesteps — and
it is not a comparison with Webster, which was measured at a different episode
length.

**Cost of reversing:** none before the 30-seed run; total after it, because
changing the action space invalidates every trained checkpoint. That asymmetry
is the whole reason for the deadline.

### 2. What may be published from IndiaTrafficNet

**Record:** P10 · **Default: option 1 — derived annotations only, no frames**

India's DPDP Rules were notified 13 Nov 2025. Publishing frames of a public road
raises questions we are not equipped to answer confidently.

**New evidence since P10 was raised:** BMD-45 (CVPR 2026) publishes 45,986
frames of Bengaluru street CCTV under CC BY 4.0 **with faces blurred**, by a
group at IISc. That is a published precedent from an Indian institution, and it
means option 2 (frames with faces blurred) is more defensible than when P10 was
written. We still recommend option 1 for a student project.

**Cost of reversing:** low. Publishing less now does not prevent publishing more
later; the reverse is not true.

### 3. Emergency vehicles — keep the override, drop the visual detector

**Record:** [Scope Variation C](SCOPE-VARIATION-REQUEST.md) · **Default: proceed as proposed**

FR-P03 requires detecting emergency vehicles from the camera. We do not believe
that can be delivered to a reportable standard:

* **No dataset carries the class.** Not IDD, not BMD-45's 14 vehicle categories,
  not the DataCluster sample.
* **It would be the thinnest class by far.** `cattle` had 183 boxes and scored
  mAP50 0.352 — our worst. Ambulances are rarer than cattle on a junction
  approach, so the result would sit below the support floor FR-D08 enforces.
* Many Indian ambulances are ordinary vans with a sticker.

**FR-P04 and FR-A05 are kept, and the preemption policy is already built and
tested** — driven by an `EmergencyDetect` message on the existing QoS 2 topic.
We would rather demonstrate a correct override on a real trigger than publish a
detector built on fifty boxes.

**Attached:** A29 — FR-A05's "within 3 seconds" contradicts FR-A03 (10 s minimum
green) and FR-A04 (3 s all-red). Measured worst case **15 s**, floor **6 s**.
The override works; the number is unreachable without deleting clearance.

---

## The six without one

### 4. Scope Variations A and B — narrow the novelty claim, reduce prototype infrastructure

**Record:** [Scope Variation Request](SCOPE-VARIATION-REQUEST.md) · recovers ~340 hours

Estimated work ~1,200 person-hours against ~715 available. Variation A narrows
Novel Contribution 1 to what is actually defensible; B reduces infrastructure,
not system behaviour. The ablation, the 30-run benchmark, reproducibility and
the working prototype are all protected.

### 5. `step_s` is pilot-determined, not fixed at 5 s

**Record:** A28 · pre-registered as `ceil(P75/59)` · **MEASURED 2026-08-19**

The statistic was chosen **before** the footage existed, and deliberately biased
against our preferred answer, because an earlier version chose it afterwards and
a reviewer was right to call that out.

> **This is no longer a request to approve a preference. The statistic has been
> computed and it answers the question.**
>
> Measured on the S06 pilot across three independently trained detectors and two
> threshold sets, `ceil(P75/59)` returns **1 or 2 in every one of six
> combinations. Never 5.** The congestion class changes on a 20–70 s timescale;
> A28 said `step_s = 5` would be vindicated by a 300 s timescale.
>
> The pilot sampled at 5 s, so the measured dwell is an **upper bound** — finer
> sampling could only push `step_s` lower. The finding is robust in our disfavour.
>
> **Recommended: `step_s = 2`** — the conservative end of the measured range.
>
> **What it buys, measured** (`experiments/results/corpus_yield.csv`, P27):
>
> | `step_s` | independent segments | cameras contributing |
> |---|---|---|
> | 5 (today) | 29 | 7 of 11 |
> | **2** | **64** | **11 of 11** |
>
> The segment count is the lesser half of this. `step_s = 5` needs 355 s of
> footage per clip and so **deletes four cameras outright** — including the
> Andheri intersection, the best-composed Indian scene in the collection.
> Sequences from one camera are correlated; cameras are the unit the model must
> generalise over, and no augmentation manufactures a viewpoint.
>
> *An earlier version of this brief quoted 19 → 42 segments over 8 → 11
> cameras. Those figures predate the duplicate-camera finding (P22) and two
> detector fixes (P20, P24) and no longer reproduce; they are withdrawn in
> favour of the committed CSV.*
>
> **This has become the highest-priority item in this brief.** It determines
> whether a training corpus exists at all: at `step_s = 5` the only surveyed
> camera yields 29 windows, of which **1** survives leak-free splitting (P22).

### 6–8. Artifact hosting · dashboard/metrics separation · prototype descoping

**Records:** [ADR-013](decisions/ADR-013-artifact-hosting-and-publication.md) ·
[ADR-014](decisions/ADR-014-dashboard-metrics-separation.md) ·
[ADR-008](decisions/ADR-008-prototype-descoping.md)

Engineering decisions with no graded consequence. Listed for completeness; we
proceed unless you object.

### 9. The headline model comparison must be reported on human-verified labels

**Record:** [A32](PRD-CHANGELOG.md) · **Default: adopt** · costs nothing, changes
which table is the headline

This one is a **reporting rule**, not a change to any experiment, and it is here
because without it the project can run a correct experiment and publish the
wrong conclusion from it.

Congestion labels come from detector counts through §14.1's thresholds, so the
label is a deterministic function of the vehicle count. Three of §14.3's
baselines — LSTM, GRU, CongestFormer — run **on count sequences**. They
therefore observe the exact variable the label is computed from, while MFSTNet
observes pixels and has to recover the count before it can extrapolate.

On auto-labelled data those baselines should win **by construction**. That
result would say nothing about vision, but it would be the biggest and cleanest
table in the report, and the obvious reading of it is "the camera-only approach
failed".

The escape already exists: A9 human-verifies the test split. A human judging
congestion is not applying `count > 15` — they see queue length, stopped versus
moving, spatial bunching. Those are in the pixels and absent from a count.

**The rule:** the headline MFSTNet-vs-baselines comparison is reported on the
human-verified test split. Auto-labelled results may appear alongside and are
labelled as such.

**If you disagree**, the alternative is to report the auto-labelled table as
headline and explain the circularity in the discussion. We think that is worse:
the caveat arrives after the number has already landed.

---

## Where the project actually stands

Context for the calls above — all figures are committed CSVs, not estimates.

**Detection is solved at the deployment viewpoint.** The joint BMD-45 + IDD
detector scores **mAP50 0.8915 on elevated Indian CCTV**, with `auto_rickshaw` at
**0.914**. The dashcam-only predecessor scored 0.3223 on the same imagery. Dashcam
performance is unchanged (0.6174 vs 0.6201), so the gain cost nothing — provable
only because the two test splits were never merged.

**Vehicle counting is calibrated.** detected/true **0.999** at confidence 0.45,
with density dependence down to 2.8%. The operating point is fitted on BMD-45
and must be re-confirmed on our own footage.

**The RL baselines are honest.** Fixed-time 31.09 s mean wait vs Webster 29.32 s,
**p = 0.225 — not significant**. Longest-queue beats both at 18.51 s. We report
that rather than the flattering framing.

**M2 is met, seven weeks early and measured properly.** Its criterion is ">=10%
mAP improvement over COCO on Indian classes", which had been claimed by
implication and never actually measured. On the same test split, remapping the
ground truth so Ultralytics' own validator scores both sides:

| class | COCO | ours | delta |
|---|---|---|---|
| car | 0.605 | 0.713 | +0.108 |
| motorcycle | 0.428 | 0.678 | +0.250 |
| bus | 0.485 | 0.714 | +0.229 |
| truck | 0.310 | 0.696 | +0.386 |
| **shared mean** | **0.457** | **0.700** | **+53.2%** |

Five times the threshold. On `auto_rickshaw` (0.711) and `cattle` (0.352) no
percentage is honest — COCO has no such class, so the baseline is not low, it is
undefined. That is a stronger statement than any number.

### The schedule, stated plainly

We are at **Week 2 of 20**. Against that:

| milestone | due | status |
|---|---|---|
| M2 detector validated | Week 9 | **met at Week 2** |
| M3 SUMO running, all methods | Week 10 | **met at Week 2** |
| M4 MFSTNet core converges | Week 12 | graph verified; needs the corpus |
| §12 identify intersections, begin collection | **Week 2–3** | **not started** |

**The risk is not that we are behind. It is the shape of being ahead.** Every
unblocked track has run well clear of its milestone, and the one task actually
scheduled for this week — siting the cameras and starting collection — is the
blocker for corpus construction, for confirming the counting operating point,
and for the P12 e-rickshaw decision.

Each early win on a different track makes that one feel less urgent, and that is
precisely how a project reaches Week 8 with an excellent detector and no dataset
of its own. **Fifteen minutes of elevated footage at one junction unblocks three
things at once**, and it is the only item on the critical path.

---

## What we need from you

| # | Item | Deadline | Default if no reply |
|---|---|---|---|
| 1 | PPO action space | **18 Aug** | adopt keep-or-switch |
| 2 | Publication scope | **18 Aug** | annotations only, no frames |
| 3 | Emergency detector withdrawal | **18 Aug** | proceed as proposed |
| 4 | Scope Variations A, B | — | proceed |
| 5 | `step_s` pilot-determined | — | proceed |
| 6–8 | ADR-013 / 014 / 008 | — | proceed |

**Signature / reply:** ______________________  **Date:** ____________

---

# Addendum — 2026-08-20

Four days on from the brief above. Items 1–3 have passed their deadline and
their defaults have fired, as designed. This addendum adds **one decision that
was missing from the brief entirely**, revises one that has since been measured
again, and reports what changed underneath both.

Same protocol: a line per item is enough, and silence takes the stated default.

## 10. Congestion thresholds — PCU units, per-camera calibration, pre-registration

**Record:** [ADR-017](decisions/ADR-017-pcu-thresholds.md), with a proposed
amendment dated today · **Default: adopt ADR-017 as amended**

This should have been item 10 of the original brief and was not. It is the
decision that determines what "congested" means in every table the project
reports, so it cannot go by default without being seen at least once.

**The core proposal is unchanged:** congestion is defined on PCU-weighted
occupancy using Indo-HCM values, thresholds are calibrated per camera and
pre-registered before any model trains, and the naive baseline is always
reported with the thresholds that produced it.

**Two defects were found by running it on a real multi-camera corpus**, and both
are folded into the same sign-off:

| | what happened | fix |
|---|---|---|
| **P34** | `low_max = p33 − 1` gives **−1** on per-lane counts, because 41.2% of them are zero. Nothing satisfies `count ≤ −1`, so calibration produced **0% LOW** — the degeneracy it exists to remove. | `low_max = max(0, p33 − 1)`. LOW means "an empty lane". |
| **P37** | The code pooled every camera into one threshold pair. Decision 2 already forbids this. | Calibrate per camera, record `thresholds_by_clip` in the manifest. |

Measured on the five-camera pilot:

| labelling | train LOW/MED/HIGH | test |
|---|---|---|
| §14.1 defaults | 83.5 / 12.9 / 3.5 | degenerate |
| pooled calibration | 57.2 / 19.2 / 23.6 | degenerate |
| **per camera, clamped** | **59.2 / 26.0 / 14.7** | **25 / 50 / 25** |

Per-camera calibration is the first labelling with **all three classes present
in every split**.

**The trade you are being asked to accept.** Per-camera thresholds make HIGH
relative to a camera's own range. A lane that never holds more than one vehicle
has no congested state and calibration must not invent one — so a quiet camera
contributes **no HIGH examples at all**. HIGH is then carried by a subset of
viewpoints and its cross-camera generalisation is tested on fewer cameras than
LOW's. We will report that beside the per-class results.

Pooled thresholds are the alternative: every camera gets all three classes, and
the classes mean different things on each. We think that is worse, and it is
what decision 2 already rejected in principle before there was data to show it.

**Reversal cost: minutes.** `relabel_corpus.py` re-derives every label from the
committed counts without re-running the detector, so this choice can be changed
after the fact and the corpus rebuilt in seconds.

## 5 (revised). `step_s = 2` — the segment figures are corrected

The original item 5 quoted 19 independent segments rising to 42. **Those figures
no longer reproduce** and are withdrawn: the footage set has changed, a
duplicate camera was found, and the detector has been corrected twice. Measured
today and committed as `experiments/results/corpus_yield.csv`:

| `step_s` | independent segments | cameras contributing |
|---|---|---|
| 5 (PRD §8.2) | 29 | 7 of 11 |
| **2 (proposed)** | **64** | **11 of 11** |

**The stronger argument is the second column, not the first.** `step_s = 5`
requires 355 s of continuous footage per clip and so **deletes four cameras
outright**, including the Andheri intersection. Sequences from one camera are
correlated; cameras are the unit the model must generalise over, and no
augmentation manufactures a viewpoint.

Recommendation unchanged: **adopt `step_s = 2`**.

## What changed underneath, since 2026-08-16

Reported because it affects what the decisions above cost, not for approval.

- **The corpus pipeline runs end to end on real footage.** Every documented
  step now has a real run behind it — corpus, cache, overfit check, all eight
  ablation configs, and the count-sequence baselines.
- **Lane geometry is per camera and revisable.** Placing lanes by hand was the
  remaining manual step; re-placing one now costs **0.66 s** rather than a
  detector pass over every clip, so a placement no longer has to be right first
  time.
- **Training moved to the GPU.** The full A–H ablation is **~1.5 h**, against
  the 60–90 h PRD §21 budgets for an uncached run on a Colab T4. Two causes had
  to be fixed: the documented install command pointed at a CUDA index that no
  longer carries PyTorch, and the training script had no device handling at all.
- **The gate has been shown to work.** Given a task that requires it, the gate
  separates by 0.17–0.27 and routes toward whichever branch carries the signal.
  On the pilot corpus it stays flat — which is now a statement about five
  cameras rather than an open question about the architecture.

## What we still need

1. **A28** — `step_s = 2`. Determines whether a corpus exists at 11 cameras or 7.
2. **ADR-017 as amended** — item 10 above. Determines what every table means.
3. **IDD scope** — unchanged from the original brief.

Nothing else is blocked. The pipeline, the tooling and the training path are
all in place and measured; these three decide what the numbers are *of*.

## 11. TrafficCAM's licence is unresolved, and it gates publication

**Record:** [TrafficCAM assessment](research/TRAFFICCAM-ASSESSMENT.md) ·
**Default: treat it as unlicensed until checked — nothing derived from it is
released or published**

Surfaced while assembling the dataset provenance for the review deck, and it is
the one item here that can stop a submission rather than shape it.

Our own assessment of TrafficCAM opens with *"the best data this project has"*.
It is a detector **training** source, a **test** source, and the **only** supply
of `e_rickshaw` examples anywhere in the project — the class that went from
0.000 to 0.4787 once it was used. Under **Licence** the same document says, in
full:

> Not yet established. The repository must be checked before any distribution or
> publication claim, and before weights trained on it are released.

That was written as a to-do and has not been actioned. Until it is:

- **weights trained on it cannot be released**, which affects the reproducibility
  package NFR-08 asks for;
- **results computed on it cannot be published**, which includes the
  cross-camera generalisation number the honest framing of this project rests on;
- an IEEE ITSC or CVIP submission that includes either would be making a claim
  we cannot support.

**What we propose to do:** check the repository for a licence file, and write to
the authors if there is none. Meanwhile results from TrafficCAM stay clearly
separated in the record so nothing has to be untangled later.

**Cost of the default:** none today. It only becomes expensive if we discover the
answer at submission rather than now.

**For contrast, the rest of the data is clean.** BMD-45 is CC BY 4.0 and ungated;
IDD needs a citation (Varma et al., WACV 2019); ITD is CC BY-NC 4.0, so anything
derived from it is non-commercial. Those are all manageable. This one is not,
until somebody checks.
