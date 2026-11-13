# Design Phase — Wave 2

**Due Week 5**, before implementation hardens. Gate is scheduled in
[Execution Manual Part 1](../90-manual/EXECUTION_MANUAL.md#part-1--week-by-week-course-of-action).

## Delivered

| Document | Covers |
|---|---|
| [HLD — Detection & Corpus Pipeline](HLD-detection-corpus-pipeline.md) | The S0–S6 staged pipeline, data contracts, the counting/labelling seam, evaluation integrity (§5), and the per-lane ROI pooling fix (§6). Written ahead of the wave because it is the critical path |
| [SAD](SAD.md) | Software Architecture Document: drivers, decomposition, runtime and offline views, the cross-component contracts (MQTT topics, the 17-dim state, safety limits, the two count representations), deployment, quality attributes with evidence, and limitations. Approved 2026-10-21 |
| [HLD](HLD.md) | High-Level Design of the remaining subsystems: the module map; MFSTNet shapes and the A–H flag scheme (NFR-15); simulation; edge; contracts; server endpoints; dashboard; where values live; and the conflicts found. Approved 2026-10-21. Its §4 is run by `python -m edge.run` since [D3](../plans/PLAN-D3-edge-entry-point.md) |

## Still scheduled

| Document | Scope |
|---|---|
| `LLD.md` | Low-Level Design — class and function signatures, tensor shapes through the MFSTNet forward pass, database schema, ROI/lane mapping, the corpus builder from PRD §8.6 |

The `DES-*` IDs that the [RTM](../01-requirements/RTM.md) marks **W2** are not yet assigned. The SAD and HLD defer them, so that the IDs and the RTM rows land in one commit.

Why the LLD is not written yet: [ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md).
