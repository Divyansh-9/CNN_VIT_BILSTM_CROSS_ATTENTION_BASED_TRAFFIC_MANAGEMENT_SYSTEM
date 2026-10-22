# Deployment Phase — Wave 4

**Due Week 16**, once the system exists and has been measured.

| Document | Scope |
|---|---|
| [`TIM.md`](TIM.md) | Transition and Implementation Manual — bringing the stack up from a clean machine: Python environment, model weights, camera configuration, broker and credentials, server, edge, dashboard, installation check, troubleshooting, rollback. **Draft for review** |
| [`SOP.md`](SOP.md) | Standard Operating Procedures — start-up and shutdown order, routine checks, delivery checks, broker loss and recovery, malformed messages, logs, incident response, the demo-day runbook with the recorded-video backup (PRD R9) and the pre-demo test 48 h ahead. **Draft for review** |

**No Docker Compose file is committed** (D4), so neither document uses one. Both
state the four deployment prerequisites the repository does not provide.

TIM doubles as the NFR-08 clean-machine reproduction procedure, so write it by actually following it
on a machine that has never run the project — a procedure validated only by its author is not
validated.

Both are drafts. The TIM was followed in a fresh clone of the commit it describes, but not yet on a
machine that has never run the project. Delivery timing: [ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md).
