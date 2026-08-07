# Testing and QA Phase — Waves 3 and 4

| Document | Scope | Due |
|---|---|---|
| `STP.md` | Software Test Plan — strategy, levels (unit/integration/system), environments, entry and exit criteria, roles | Week 11 |
| `STD.md` | Software Test Description — the `TC-*` cases reserved in the [FRD](../01-requirements/FRD.md) and [NFR](../01-requirements/NFR.md), with steps, data, and expected results | Week 11 |
| `UAT.md` | User Acceptance Test — milestone acceptance procedures against [SOW §5](../00-planning/SOW.md#5-milestones-and-acceptance-criteria), run with the faculty guide | Week 11 |
| `STR.md` | Software Test Report — **measured** results, defects found, and their resolution | Week 16 |

STR is deliberately last. It is a results document; written before the tests run it would be
fiction ([ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md)).

**Pull FR-A06 fallback verification forward to Week 17**, not Week 19 — fault-injection testing finds
real defects, and Week 19 leaves no time to fix them ([RTM §5.2](../01-requirements/RTM.md)).
