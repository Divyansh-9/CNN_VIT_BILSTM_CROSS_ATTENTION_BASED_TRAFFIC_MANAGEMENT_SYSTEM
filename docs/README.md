# Documentation

Full SDLC suite for **MFSTNet** — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System.

## Start here

| If you are… | Read |
|---|---|
| **On the team, starting work** | [Execution Manual](90-manual/EXECUTION_MANUAL.md) — Part 0 today, Part 1 weekly |
| A faculty guide or examiner | [SOW](00-planning/SOW.md) → [BRD](00-planning/BRD.md) → [RTM](01-requirements/RTM.md) |
| Implementing a component | [PRD](00-planning/PRD.md) for numbers → [FRD](01-requirements/FRD.md) for acceptance criteria |
| Wondering why something was decided | [decisions/](00-planning/decisions/) and [PRD-CHANGELOG](00-planning/PRD-CHANGELOG.md) |

## The suite

### Planning

| Document | Answers |
|---|---|
| [SOW](00-planning/SOW.md) | Scope, team, deliverables, milestones, budget, risks |
| [BRD](00-planning/BRD.md) | Why — business needs BR-01..BR-23 |
| [PRD](00-planning/PRD.md) | What is built. **Authoritative for every number** |
| [PRD-CHANGELOG](00-planning/PRD-CHANGELOG.md) | What changed in the PRD, and why |
| [DATASETS](00-planning/DATASETS.md) | Which public datasets we use, which we reject, licensing, class mapping |
| [decisions/](00-planning/decisions/) | ADR-001 dataset · ADR-002 training corpus · ADR-003 edge hardware · ADR-004 doc delivery |

### Requirements

| Document | Answers |
|---|---|
| [SRS](01-requirements/SRS.md) | How the system behaves — actors, interfaces, modes, data contracts |
| [FRD](01-requirements/FRD.md) | How each of the 55 functional requirements is verified |
| [NFR](01-requirements/NFR.md) | How each quality attribute is measured |
| [RTM](01-requirements/RTM.md) | Traceability: BR → FR/NFR → DES → TC → M |

### Design · Testing · Deployment

Delivered in later waves — see below.

| Phase | Documents | Due |
|---|---|---|
| [Design](02-design/) | SAD, HLD, LLD | Week 5 |
| [Testing](03-testing/) | STP, STD, UAT | Week 11 · STR Week 16 |
| [Deployment](04-deployment/) | TIM, SOP | Week 16 |

### Manual and templates

| | |
|---|---|
| [Execution Manual](90-manual/EXECUTION_MANUAL.md) | Setup, week-by-week plan, dataset guide, training, SUMO/PPO, prototype, paper, troubleshooting |
| [weekly/](90-manual/weekly/) | Weekly status records |
| [templates/](templates/) | Weekly status · experiment record · risk entry |

## Why documents are missing

Documents are written in four waves gated on the PRD §18 phases, not all upfront
([ADR-004](00-planning/decisions/ADR-004-phased-document-delivery.md)):

| Wave | Gate | Documents | Status |
|---|---|---|---|
| 1 | Week 0–1 | SOW, BRD, SRS, FRD, NFR, RTM, ADRs, Execution Manual | **Delivered** |
| 2 | Week 5 | SAD, HLD, LLD | Scheduled |
| 3 | Week 11 | STP, STD, UAT | Scheduled |
| 4 | Week 16 | STR, TIM, SOP | Scheduled |

STR is a *results* document, and UAT records acceptance actually granted. Written in Week 1 they
would be fiction. Phasing keeps every document truthful at the moment it is reviewed.

## Conventions

**Requirement IDs are defined once.** `FR-*` and `NFR-*` live in PRD §9/§10; `BR-*` in the BRD;
`DES-*`, `TC-*`, and `M-*` in design, test, and SOW §5. Every other document cites IDs and never
restates a requirement in prose — so a change touches one document and the RTM shows the blast
radius.

**The PRD wins on numbers.** Any dimension, threshold, or hyperparameter reproduced elsewhere is for
readability. On conflict, the PRD governs — and if the PRD is wrong, amend it and log it in
PRD-CHANGELOG rather than working around it.

**Every latency figure states its measurement host** (NFR §2.2, ADR-003).

**Negative results are reported and analysed, never dropped** (BR-19, PRD §2.5.5).
