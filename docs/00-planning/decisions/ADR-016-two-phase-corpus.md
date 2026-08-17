# ADR-016 — Two-phase corpus: build the pipeline on Bellevue, claim on India

**Status:** Proposed · **Date:** 2026-08-16 · **Supersedes nothing; extends [ADR-001](ADR-001-two-track-dataset-strategy.md)**

## Context

The proposal came from the project owner: finish the whole project on data that is
easily available, prove it works, and only then take on Indian footage — so that
by the time the hard part starts, half the work is banked.

The instinct is right and it is **already this project's accepted pattern**.
ADR-001 does exactly this for the *detector*: bootstrap on public data from
Week 2, swap in self-collected data at Week 8. This applies the same shape to the
*corpus*.

Two premises behind the proposal have to be corrected first, because acting on
the stated version would send us to the wrong dataset.

### Correction 1 — Indian elevated data is no longer the scarce thing

The proposal assumes elevated Indian footage is hard to find. That was true a
week ago. It is not true now: **BMD-45** gives 45,986 images from 3,679 Safe City
CCTV cameras in Bengaluru under CC BY 4.0, and the joint detector scores
**mAP50 0.8915** on it with `auto_rickshaw` at **0.914**.

Detection at the Indian elevated viewpoint is **solved**.

### Correction 2 — the scarce thing is 360 seconds of continuous video

BMD-45 is **still images**. MFSTNet needs *sequences*, and A15 fixes the
arithmetic: T=60 steps × 5 s = 300 s of history, plus a 60 s prediction horizon,
so **a clip shorter than 360 s yields exactly zero training sequences**.

That single number eliminates almost every traffic dataset in the literature,
because they are built for detection and tracking rather than forecasting:

| source | clip length | usable? |
|---|---|---|
| UA-DETRAC | 600–1000 frames @ 25 fps = **24–40 s** | **no — 9× too short** |
| BMD-45 | still images | no |
| IDD | still images | no |
| stock footage sites | 10–30 s | no |
| the 43 clips already triaged | longest 349 s | **no — by 11 seconds** |

The blocker was never "Indian data". It is **long continuous fixed-camera video**,
and it is scarce in *every* country.

## Decision

**Adopt the two-phase corpus, and source Phase 1 from the Bellevue Traffic Video
Dataset.**

[github.com/City-of-Bellevue/TrafficVideoDataset](https://github.com/City-of-Bellevue/TrafficVideoDataset)

| | |
|---|---|
| volume | **~101 hours** |
| cameras | 5 intersections, **pole-mounted, fixed** |
| format | 1280×720 @ 30 Hz, Google Drive direct download |
| origin | City of Bellevue, Washington — released by a public body for research |
| annotations | none, **and none are needed** |

101 hours against a 360 s minimum is roughly **1,000 non-overlapping windows per
hour of footage**, from a viewpoint that matches the deployment geometry. The
absence of annotations costs nothing because ADR-002 derives every label from
detector counts, and we now have a detector calibrated for exactly that
(conf 0.45, detected/true 0.999).

### Phase 1 — pipeline, on Bellevue

Build and validate everything end to end: corpus construction, MFSTNet training,
the seven-configuration ablation, PPO integration, the prototype.

### Phase 2 — claim, on India

Swap in self-collected footage. The pipeline is already proven, so the remaining
risk is data quality alone.

## The limit of Phase 1, stated before it is reached

**Phase 1 cannot support a claim about Indian traffic.** Foreign junctions have
lane discipline, no auto-rickshaws weaving, and different congestion dynamics.
A model validated on Bellevue is validated as an *architecture*, not as a
deployment for India.

This is the same split the detector work already measured and it held there:
**viewpoint and architecture transfer across countries; behaviour does not.**

**What makes this acceptable is that our defensible claims are architectural.**
[RELATED-WORK](../RELATED-WORK.md) already narrowed the novelty to
the gate-as-artifact, the camera-only framing, and density-stratified
evaluation — because the fusion mechanisms themselves are all published. Every
one of those is a method claim that Bellevue can validate.

So the paper's structure follows the phases honestly:

* **Method and ablation** — Bellevue, and say so.
* **Indian deployment** — our own footage, and say what is different about it.

The failure this ADR is written to prevent is training on Bellevue and then
describing the result as an Indian traffic system. **Every table states which
corpus produced it**, exactly as S14's two eval configs already do.

## Consequences

1. **The critical path stops being blocked.** Corpus construction, MFSTNet
   training and the ablation can all start now instead of waiting on a recording
   trip.
2. **S06 stays required, and its purpose sharpens.** It is no longer "the thing
   that unblocks everything" but "the thing that earns the Indian claim" — and it
   still confirms the conf 0.45 operating point and settles P12.
3. **A28 gets a second, independent pilot.** `step_s` was to be fixed from S06
   footage; Bellevue lets the same pre-registered statistic be computed on 101
   hours first, which is a far better estimate than one clip.
4. **Corpus sources must be labelled.** `mfstnet.corpus.sources` already
   distinguishes dev from reportable footage; Bellevue becomes a third kind —
   **reportable, but foreign** — and any table mixing it with Indian data without
   saying so is a defect.
5. **US traffic has no auto-rickshaw, e-rickshaw or cattle.** On Bellevue the
   detector runs a 4-class taxonomy in practice. That is fine for congestion
   counts, and it means P12 cannot be answered there.

## Alternatives rejected

**Wait for S06 and do nothing else.** Rejected: it is a single point of failure
on a trip that has not happened, and the pipeline work does not depend on it.

**Use UA-DETRAC.** Rejected on arithmetic — 24–40 s clips against a 360 s
minimum. It is a tracking benchmark, not a forecasting corpus.

**Shorten the prediction horizon to fit short clips.** Rejected: the 60 s horizon
is the requirement (PRD §8.2), and cutting it to make a dataset fit is choosing
the answer to suit the data.

**Drop the Indian claim entirely and publish on Bellevue.** Rejected: the
India-specific framing is the project's reason to exist, and BMD-45 has already
shown the detector half of it works.
