# Design Phase — Wave 2

**Due Week 5**, before implementation hardens. Gate is scheduled in
[Execution Manual Part 1](../90-manual/EXECUTION_MANUAL.md#part-1--week-by-week-course-of-action).

| Document | Scope |
|---|---|
| `SAD.md` | Software Architecture Document — subsystem decomposition, deployment view, the cross-component contracts (MQTT topics, the 17-dim PPO state vector), architectural drivers and their trade-offs |
| `HLD.md` | High-Level Design — module structure per subsystem, interfaces, data flow, the config-flag scheme that makes ablation possible (NFR-15) |
| `LLD.md` | Low-Level Design — class and function signatures, tensor shapes through the MFSTNet forward pass, database schema, ROI/lane mapping, the corpus builder from PRD §8.6 |

These assign the `DES-*` IDs that the [RTM](../01-requirements/RTM.md) currently marks **W2**.

Why not written yet: [ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md).
