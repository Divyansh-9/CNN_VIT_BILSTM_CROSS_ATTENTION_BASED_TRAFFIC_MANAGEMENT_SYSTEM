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
