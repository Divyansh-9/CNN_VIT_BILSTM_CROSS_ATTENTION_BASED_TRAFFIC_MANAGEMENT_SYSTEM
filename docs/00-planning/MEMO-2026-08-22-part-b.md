# Memo — Part B cannot be scored under our own protocol

**To:** Ms Neha Pokhriyal (project guide) · **From:** Divyansh Uniyal, project owner
**Date:** 2026-08-22 · **Decision requested by:** 2026-08-29

**Recommendation: convert Part B from a 1,500–3,000-frame training set into a
~300-frame, six-viewpoint held-out evaluation set, captured from public space.**
This is a change to a Novel Contribution and therefore needs your sign-off, not
the project owner's. [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md)
already reduced this item once (12,000 → 1,500–3,000); this asks to change its
*kind*, not its size again.

## The argument in one paragraph

Part B is denominated in **frames**. Frames are the cheap thing — we already
hold hours of footage. **Viewpoints are the scarce thing**, and the project's
diagnosed central weakness is that performance collapses across viewpoints:
the detector scores **0.8941** on cameras it trained on and **0.3500** on
cameras it has not seen. Part B spends institutional permission, a capture
session, tens of thousands of annotation boxes and a face/plate blurring
pipeline to move our camera count from 11 to 12.

## The decisive objection: our own evaluation cannot score it

[ADR-019](decisions/ADR-019-leave-one-camera-out-evaluation.md) evaluates
MFSTNet by leave-one-camera-out, and a camera is eligible to be a test fold only
if it contributes at least ten windows. **One campus location is one camera.**
It enters as a single fold out of five, or — if it yields fewer than ten
windows — as always-train, contributing nothing measurable at all.

So Part B as specified would produce an artifact that **the project's own
protocol cannot report a number for**. That is not a scheduling objection and it
does not go away with more time.

## What to do instead

**Six public vantage points** — footbridges, overpasses, public space, so no
institutional permission is required — **15–20 minutes of continuous recording
each.**

One capture, two artifacts, at no extra cost:

| artifact | from | why it works |
|---|---|---|
| detection test set | ~50 sparsely sampled frames per viewpoint, ~300 total | six viewpoints is six independent evaluation surfaces |
| **forecasting folds, later** | the retained continuous clips | A15 needs ≥ 360 s of continuous video for a single window; 15–20 min clears it comfortably, so each viewpoint can become a **fold** under ADR-019 |

The second row is the reason to record continuously rather than shoot stills.
**Fifty scattered frames give a detection test set and nothing else** — windows
need continuous footage, so sparse frames can never make a camera fold-eligible.
Keeping the clip costs disk and preserves the option; discarding it forecloses
the far more valuable artifact.

### Labelling, and the circularity it would otherwise inherit

Boxes seeded by our own detector and human-corrected are **not independent of
the model being evaluated** — the test set would inherit the detector's blind
spots, which is the same circularity A32 already forced us to fix for the corpus
labels.

Disclosure of the correction rate documents that bias. **Seeding with a
different model removes most of it**, so:

* seed `car`, `bus`, `truck`, `motorcycle` with an **off-the-shelf COCO
  detector**, not ours;
* annotate `auto_rickshaw`, `e_rickshaw` and `cattle` **by hand** — COCO cannot
  seed them in any case;
* report frames corrected and boxes changed regardless.

**Do not seed with the ITD-distilled model.** ITD v1.2 is **CC BY-NC 4.0**, and
propagating a non-commercial licence into a set we intend to release would undo
the point of releasing it.

## Run this in parallel, not after

Extended annotations on **BMD-45** (CC BY 4.0, attribution only) are a
legitimate, citable data contribution requiring no capture, no permission, no
blurring and no DPDP exposure — the footage is already published.

It is also the **only route that removes a publication blocker rather than
adding an artifact**: TrafficCAM's licence is unresolved and is currently our
sole source of `e_rickshaw` boxes, so anything derived from it may not be
releasable.

## Read this section first: the evaluation has no Indian camera in it

Found today by looking at the footage rather than the filenames. The four
cameras eligible to be a leave-one-camera-out fold are:

| fold | camera | country | lane-windows | HIGH |
|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | Bangladesh | 140 | 0 |
| 1 | **M6 Motorway** | **United Kingdom** | **252** | **20** |
| 2 | Pov, footover bridge | Bangladesh | 44 | 9 |
| 3 | Dhaka Rampura (b) | Bangladesh | 136 | 1 |

India contributes **9 sequences of 153** — Mumbai Andheri, South Extension
Delhi, and one unlabelled clip. All three fall below the ten-window eligibility
bar, so **none of them is ever tested**. The forecaster's evaluation is
Bangladesh and Britain.

Worse, the **M6 is 41% of the evaluation corpus and 53% of every HIGH label in
the project**. It is a divided motorway: enforced lane discipline, no junction,
no auto-rickshaws, no mixed traffic. It is the canonical counterexample to the
premise of the project, and it is our largest fold.

It entered by passing the density and lane-assignment gates, which is to say
**nobody chose it**. Both gates are correct; neither asks what country a camera
is in.

**The trade this creates.** Dropping the M6 for coherence costs 53% of the HIGH
windows and leaves exactly three eligible cameras — the bare minimum the
protocol allows. Domain coherence and HIGH support are in direct conflict, and
the M6 causes the first problem while supplying the second.

## The two problems are one coupled decision

Presented separately, the domain problem and the class problem each look
solvable. They are the same problem and they pull in opposite directions:

> **Fix the domain honestly and you drop the M6. Dropping the M6 removes 44% of
> the windows and 20 of the 30 HIGH labels, leaving about 10 HIGH in the whole
> corpus. The three-class task is then not underpowered — it does not exist.
> Keep HIGH estimable and you keep a British motorway as the majority of the
> evaluation.**

The corpus we have cannot do both. Deciding them in sequence means approving the
domain fix this week and discovering the class collapse next week, so they are
put here together.

**And dropping the M6 does not make the corpus Indian — it makes it
Bangladeshi.** That is the part that collapses the options:

| option | folds | lane-windows | HIGH | domain |
|---|---|---|---|---|
| **A** — re-frame to South Asian, drop the M6 | 3 (protocol minimum) | 320 | **10 (3.1%)** | coherent |
| **B** — re-frame to South Asian, keep the M6 | 4 | 572 | 30 | **still incoherent** — the UK is not South Asia |
| **C** — obtain Indian footage | depends | depends | depends | the only route to the claim as written |

Option B is not a compromise between A and C; it is A's domain problem retained
for C's class support. **We recommend A, and C in parallel**, with the paper's
class claim reduced to binary under the pre-registered rule below.

### There is a third coupling, and it changes the economics

The footage that supplies our training sequences is **twelve third-party
uploads with no licence declared**. That was already a publication blocker
before any of the above — nothing derived from them is releasable, and the
detector that counted them is ITD v1.2, CC BY-NC 4.0.

**So the domain problem and the licence problem have the same solution and the
same cost: the corpus has to be re-sourced either way.** Re-sourcing was
previously one option among three; it is now the only route that fixes both, and
that changes what the capture in option C is worth.

### A recommendation we are reversing, stated as a reversal

Earlier in this memo's drafting we recommended **cutting Part B** as the
cheapest thing to drop. That was correct when the alternative was eleven usable
cameras. **It is not correct now that the number of on-domain fold-eligible
cameras is zero.**

Capture may be the only route to a corpus that can carry the paper's stated
claim — with **this memo's spec** (few viewpoints, chosen for congestion, at
peak, 15–20 minutes continuous), **not** ADR-006's campus-frames spec. We are
flagging the reversal explicitly so the two recommendations are not read as
inconsistent.

### And the recommendation is still the other branch

With placements running, re-sourcing is weeks that are not available. Three
Dhaka cameras and about ten HIGH windows cannot support a three-class Indian
forecasting claim, and no amount of statistical care fixes that.

What **is** measured and defensible today is the harmonised benchmark, the
leave-one-camera-out protocol, and the audit apparatus itself: sixty-plus
recorded defects with causes, a composition gate that fails honestly, paper
claims as machine-checkable assertions, contract hashing, and pre-registration
committed before results existed. That is an unusual contribution and it is the
only part of this project not blocked on data we do not have.

**Our recommendation: lead the thesis with the benchmark, the protocol and the
methodology, and report MFSTNet as measured and not separable from its floor.**
File the permission request and keep C open, but do not plan on it.

Verified today so that C is costed honestly:

* **Dhaka-a and Dhaka-b are genuinely different cameras** — a junction with a
  police box against a divided boulevard past South Point School, checked at
  several timestamps. So option A really does leave three cameras, which is the
  protocol's minimum, not two.
* **BMD-45 cannot supply sequences.** It is on-target in every other way —
  Bengaluru CCTV, elevated, mixed traffic, CC BY 4.0, already in the project —
  and it is **isolated still images**, sampled by its authors for "spatial and
  temporal diversity", with no timestamps or ordering. 45,986 images across
  3,679 cameras is about **12.5 frames per camera**, against the **90
  consecutive observations** A15 requires for one window. Confirmed against the
  dataset card, not the abstract. **There is no free route to Indian sequences
  in data we already hold.**

## The finding that may change this conversation entirely

Measured today, after the memo above was drafted. The MFSTNet corpus is built,
and its **HIGH** class — the one a signal controller actually acts on — is
almost absent from it:

| fold | test camera | lane-windows | **HIGH** | share |
|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | 140 | **0** | 0.0% |
| 1 | M6 Motorway | 252 | 20 | 7.9% |
| 2 | Pov footover bridge | 44 | 9 | 20.5% |
| 3 | Dhaka Rampura (b) | 136 | **1** | 0.7% |

**Thirty HIGH windows in 572.** Two folds are effectively binary. The ablation
now running can distinguish architectures on LOW-versus-MEDIUM and cannot
distinguish them on the distinction that matters for control
([P57](PRD-CHANGELOG.md)).

We are **not** recalibrating the ADR-017 thresholds to fix this. Adjusting
thresholds until the class balance improves is fitting labels to a desired
outcome, and P45 already established that per-camera percentile calibration
manufactures a HIGH class out of an empty road.

**One distinction, because these will otherwise sound identical.** Changing the
*sample* and changing the *ruler* are different acts:

* **Selecting footage for the presence of congestion — or for geography — is
  sampling design.** Declared in advance, reported in the paper, and entirely
  legitimate. It is what options 1–3 above amount to.
* **Moving the thresholds until the balance looks better is fitting labels to a
  desired outcome.** We will not do it, and we would have to disclose it if we
  did.

We are asking for the first and refusing the second. If a decision leans toward
re-selection, it is sampling design and we will pre-register the selection rule
before applying it.

A third legitimate move, if HIGH cannot be made to exist: **a pre-registered
collapse to binary — LOW versus MEDIUM+HIGH — triggered by class support, not by
results.** Support is a property of the data and is known before any metric is
computed, so declaring the rule now, with the table above as its justification,
is defensible. Declaring it after the 160 runs land would not be. We would like
your view on whether to fix that trigger now.

**Why it belongs in this memo.** The recommendation above optimises for
*viewpoint diversity*. If the corpus cannot express HIGH, the binding constraint
may instead be **density** — footage of genuinely congested traffic — and the
right capture target changes accordingly: fewer viewpoints, chosen for
congestion, at peak hours. A decision about which dataset to build should be
made knowing this, and it was not known when ADR-006 was accepted.

## What we are asking, precisely

1. **Approve** converting Part B to the six-viewpoint evaluation set above, or
   direct us to keep it as a training set, or cut it.
2. Note that the permission request will be **filed regardless** this week —
   twenty minutes, runs asynchronously, and preserves the option if Part B
   revives in its original form.
3. Note that **S19 is marked "blocked on this decision" on the build log as of
   today**, not "not started". A board showing *awaiting guide since 22 Aug* is
   defensible at week 18; a purple square is not.

### The default, so the date is not a wish

**If no decision is received by 2026-08-29, Part B is cut.** ADR-006 will be
amended to record that Novel Contribution 1 is Part A alone, the amendment will
name this memo and the silence as its cause, and S19/S20/S21 will close as
descoped rather than remaining open.

This is stated so that inaction has a defined result. It is reversible at any
point — reviving Part B later costs a decision, not rework — and the permission
request is being filed this week precisely to keep that reversal cheap. What is
not reversible is another two months of a board square that means nothing.

## What is not affected

S19 is the **detection** dataset. The **MFSTNet corpus** is a separate artifact
([ADR-002](decisions/ADR-002-mfstnet-training-corpus.md)) built from existing
footage, and it is already built — 153 sequences over 7 cameras, audited, with
the ablation running. S28 and S29 do not wait on this decision. Conflating the
two is why "recording sessions" read as the project's only blocker for two
weeks.
