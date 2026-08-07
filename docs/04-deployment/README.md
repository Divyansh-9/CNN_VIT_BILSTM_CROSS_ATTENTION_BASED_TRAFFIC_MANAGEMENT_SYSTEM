# Deployment Phase — Wave 4

**Due Week 16**, once the system exists and has been measured.

| Document | Scope |
|---|---|
| `TIM.md` | Transition and Implementation Manual — bringing the stack up from a clean machine: Docker Compose for broker/API/database/dashboard, edge node setup, model artifact placement, configuration, smoke test, rollback |
| `SOP.md` | Standard Operating Procedures — daily start/stop, health checks, what to do when MFSTNet or the broker fails, demo-day runbook including the recorded-video backup (PRD R9), and the pre-demo network test 48 h ahead |

TIM doubles as the NFR-08 clean-machine reproduction procedure, so write it by actually following it
on a machine that has never run the project — a procedure validated only by its author is not
validated.

Why not written yet: [ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md).
