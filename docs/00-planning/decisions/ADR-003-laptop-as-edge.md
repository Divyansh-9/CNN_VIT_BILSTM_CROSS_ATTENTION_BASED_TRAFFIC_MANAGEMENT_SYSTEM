# ADR-003 — Laptop-as-Edge, Jetson Optional

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-07 |
| **Deciders** | Project team |
| **Affects** | PRD §15, FR-E01..FR-E06, NFR-01, M8, R8 |

## Context

PRD §15 specifies an NVIDIA Jetson Nano running YOLOv8s with GPIO-driven LEDs as the edge node, and
M8 requires a live prototype at ≥10 fps with 10/10 emergency preemptions cleared within 3 seconds by
Week 16.

The Jetson Nano is the only component in the entire stack that costs cash — ₹12,000–18,000, against
a project budget of ₹0. Supply is also constrained: the original Nano is end-of-life and current
listings are largely resale or the more expensive Orin Nano. Ordering late, or discovering
unavailability in Week 13, puts M8 at risk with no recovery time.

Separately, R8 already anticipates the Nano being too slow (rated Medium likelihood, High impact),
with the mitigation being YOLOv8n at 416×416. So the plan already assumes the specified hardware may
not meet the specified target.

## Decision

The edge node runs on a **team laptop with a USB or built-in webcam**. GPIO LED output is replaced
by an on-screen signal panel rendering the same four-phase state. The MQTT contract, the detection
pipeline, the local Webster fallback, and the emergency preemption logic are all unchanged — only
the physical host and the output device differ.

Before committing, **check department lab inventory.** Many CSE departments hold Jetson Nanos,
Jetson Orins, or Raspberry Pis from prior cohorts. If one can be borrowed, use it and report genuine
on-device latency; the laptop path remains the fallback and the demo backup.

If the team later chooses to buy one, a single shared unit held by the edge-subsystem owner is
sufficient — the device is only needed for the Week 13–16 prototype window.

## Consequences

**Positive.** M8 becomes achievable at zero cost and with no procurement lead time. Development
velocity improves — the edge owner can iterate on their own machine rather than cross-compiling and
flashing. R8 is neutralised: a laptop CPU comfortably exceeds 10 fps on YOLOv8n, and typically on
YOLOv8s.

**Negative.** Latency figures are no longer measured on the deployment target, which weakens the
NFR-01 claim. This is handled by honesty rather than omission: every latency table states the
measurement host explicitly, laptop results are labeled as proxy measurements, and the paper's
limitations section notes that on-device validation is outstanding. PRD §20 gains this as a listed
limitation. A reviewer who sees a clearly-labeled proxy measurement will accept it; one who catches
an unlabeled laptop number presented as a Jetson number will not.

**Neutral.** The GPIO LED demo is visually appealing to an examiner in a way a screen panel is not.
If a Pi is available, wiring three LEDs to it costs under ₹100 and recovers that.

## Alternatives considered

**Buy a Jetson Nano.** Real on-device numbers, strongest claim. Not rejected — recorded as an
upgrade path, contingent on funds appearing or the department reimbursing. Order by Week 10 if so.

**Pure simulation, drop M8.** Saves three weeks. Rejected: PRD §2.5.3 lists a working hardware
prototype among the distinction-level requirements, and a live demo is disproportionately persuasive
in the viva.
