# ADR-014 — The Dashboard Shows Two Different Things, and Must Never Merge Them

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-08-13 |
| **Affects** | FR-UI01–FR-UI05, NFR-13, §14.2, §14.3; M7, M8 |
| **Related** | [ADR-002](ADR-002-mfstnet-training-corpus.md) (auto-labelling, A9 circularity) · [ADR-003](ADR-003-laptop-as-edge.md) · [ADR-013](ADR-013-artifact-hosting-and-publication.md) |

## Context

The intended dashboard feature is: *show accuracy, precision, F1 and the confusion matrix live,
against the video being processed.* It is an obvious and attractive feature. It also contains two
problems that would quietly invalidate the numbers it displays.

### Problem 1 — live accuracy cannot exist, and a plausible version of it would be circular

MFSTNet predicts congestion **60 seconds ahead**. At time *t* the prediction made at *t* is
unfalsifiable: the thing it predicts has not happened. The earliest a prediction can be scored is
*t + 60 s*.

Worse is what a live scorer would use as ground truth. The only signal available at runtime is the
detector's vehicle count passed through the §14.1 thresholds — which is **exactly how the training
labels were produced** (ADR-002). Scoring a prediction against it measures agreement between the
model and its own labelling function. Detector error cancels out of both sides.

That is the same circularity amendment A9 already fixed once, by requiring the **test split to be
human-verified**. A live accuracy panel would reintroduce it in a place where it looks authoritative
and nobody re-derives it. A number on a dashboard during a viva is the *least* likely number in the
project to be questioned.

### Problem 2 — showing the video contradicts NFR-13

NFR-13 states that raw frames are never transmitted over the network or written to disk; only derived
counts and predictions leave the edge device. That constraint is a stated contribution of the
camera-only framing, and streaming frames to a browser to display them beside the metrics breaks it —
for a cosmetic reason.

## Decision

### 1. Two panels, visually separated, never merged

**Panel A — Benchmark.** The §14 numbers: confusion matrix, per-class precision/recall/F1 with
support, macro-F1 with 95% CI, ordinal MAE, off-by-two rate, QWK. Loaded from the **committed result
CSV**, computed offline on the human-verified test split. It carries a header stating the split, *n*,
the date, and the git commit that produced it. **It does not change while the dashboard runs**, and
the fact that it does not change is the point.

**Panel B — Live monitor.** What the system is doing now: per-lane counts, the current prediction,
the gate value, inference latency, MQTT health, and which controller is active. No accuracy figure
appears in this panel.

The dashboard renders Panel A from the same CSV the paper is generated from (NFR-09/10). There is one
set of headline numbers in this project and it lives in a file.

### 2. Live correctness is shown as a *deferred agreement ribbon*, and labelled as not a benchmark

A prediction made at *t − 60 s* is displayed beside what the counts actually showed at *t*. Rolling
over the last N pairs, this gives a live sense of whether the model is tracking reality, which is the
legitimate version of what was wanted.

It is labelled, in the UI and not only in the documentation:

> **Rolling agreement with auto-labels over the last 20 predictions. Not a benchmark** — auto-labels
> come from the same detector counts the model was trained on. Benchmark figures are in Panel A.

The first 60 seconds after start show *no ribbon at all*, because no prediction is scoreable yet. An
empty state is honest; a ribbon that fills in from nothing is not.

### 3. The video is replaced by a derived overlay — and this is better, not a compromise

Instead of the frame, the dashboard draws on a blank canvas:

- lane polygons, as configured;
- one box per detection, coloured by class, positioned from the detection geometry;
- per-lane counts and the predicted class per approach.

**No pixel of the source frame ever leaves the edge device.** Boxes and polygons are derived data,
which NFR-13 already permits transmitting.

This is the better artifact on its own merits, independent of the constraint. It is legible in a
paper figure, it is legible in a screenshot, it does not leak a licence plate into a conference
slide, and it makes the privacy claim *visible* rather than asserted — a reviewer sees a system that
demonstrably has no frames to show.

### 4. Replay mode is the demo, not the live camera

A recorded clip is fed through the same pipeline with a scrubber, so the prediction at any point can
be compared with what happened 60 seconds later. Deterministic, repeatable, and it survives the venue
Wi-Fi failing.

A live camera demo depends on a camera, a network, and traffic that happens to be interesting during
the eight minutes of a viva. Replay depends on none of those, and is the same code path.

## Consequences

**Good.** The headline numbers have exactly one source. The live view stays useful without claiming
to be evidence. NFR-13 is satisfied by construction rather than by discipline. The demo is repeatable.
The overlay makes a better paper figure than a video still would.

**Bad.** The dashboard is less immediately impressive than one showing camera footage with boxes on
it. Accepted: the version that looks best is the version that breaks a stated contribution and
reports a circular metric.

**Requires.** FR-UI01–FR-UI05 to be restated in these terms; a replay driver on the edge side; and
the deferred-agreement buffer, which is ~20 predictions of state and needs no storage.

**Note for the paper.** The separation is itself worth one paragraph. "We deliberately do not report
live accuracy, because our labels derive from the same detector counts the model consumes" is a
methodological strength, and reviewers of vision-based congestion work look for exactly this.
