# Decision Brief — everything awaiting a call

**To:** Faculty Guide · **From:** Project Team · **Date:** 2026-08-16
**Deadline on items 1–3: 2026-08-18** (two days). Items 4–8 have no deadline.

> This page exists because six decisions had accumulated across five documents,
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

**Both are implemented behind a config flag.** We screen at 5 seeds each and
bring you the numbers. Nothing graded is lost either way — §13.1 stays
implemented as specified.

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

## The five without one

### 4. Scope Variations A and B — narrow the novelty claim, reduce prototype infrastructure

**Record:** [Scope Variation Request](SCOPE-VARIATION-REQUEST.md) · recovers ~340 hours

Estimated work ~1,200 person-hours against ~715 available. Variation A narrows
Novel Contribution 1 to what is actually defensible; B reduces infrastructure,
not system behaviour. The ablation, the 30-run benchmark, reproducibility and
the working prototype are all protected.

### 5. `step_s` is pilot-determined, not fixed at 5 s

**Record:** A28 · pre-registered as `ceil(P75/59)`

The statistic was chosen **before** the footage exists, and deliberately biased
against our preferred answer, because an earlier version chose it afterwards and
a reviewer was right to call that out.

### 6–8. Artifact hosting · dashboard/metrics separation · prototype descoping

**Records:** [ADR-013](decisions/ADR-013-artifact-hosting-and-publication.md) ·
[ADR-014](decisions/ADR-014-dashboard-metrics-separation.md) ·
[ADR-008](decisions/ADR-008-prototype-descoping.md)

Engineering decisions with no graded consequence. Listed for completeness; we
proceed unless you object.

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
