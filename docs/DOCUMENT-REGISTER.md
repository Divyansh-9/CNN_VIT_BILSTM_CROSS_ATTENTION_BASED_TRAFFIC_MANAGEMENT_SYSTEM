# Document Register

Document control for the MFSTNet SDLC suite. **Last reconciled: 2026-08-10.**

Every document, its version, status, owner, and when it was last checked against the decisions in
force. This register exists because the suite drifted once already: ADRs 005–008 changed the plan
while the SOW, FRD, and Execution Manual still described the superseded approach.

**Reconcile at every wave gate (W05, W11, W16) and whenever an ADR is accepted.** The reconciliation
is a fifteen-minute pass: read the register, open anything whose "checked" date predates the newest
accepted ADR, and fix or confirm it.

---

## Status vocabulary

| Status | Meaning |
|---|---|
| **Active** | Current and in force |
| **Proposed** | Written but not adopted; needs a named approval before it governs anything |
| **Scheduled** | Not yet written; has a due date |
| **Superseded** | Replaced by a named successor. Retained in `99-archive/` for the decision trail |

Superseded documents are **archived, not deleted.** An examiner may reasonably ask why an approach
changed, and the answer should be a document rather than a recollection.

---

## Planning

| Document | Ver | Status | Owner | Checked | Notes |
|---|---|---|---|---|---|
| [SOW](00-planning/SOW.md) | 1.2 | Active | All | 2026-08-10 | §2.4 capacity baseline; risks R16–R24; D-02/M1 flagged conditional |
| [BRD](00-planning/BRD.md) | 1.0 | Active | All | 2026-08-08 | BO-3 flagged conditional on ADR-006 |
| [PRD](00-planning/PRD.md) | **1.2** | Active | All | 2026-08-10 | **A1–A12 and A15–A21 applied.** §12 carries a PROPOSED banner for A13 |
| [PRD-CHANGELOG](00-planning/PRD-CHANGELOG.md) | — | Active | All | 2026-08-10 | A13/A14 blocked; A15–A21 applied; includes the why-A15-was-missed note |
| [DATASETS](00-planning/DATASETS.md) | 1.1 | Active | R1 | 2026-08-08 | §1.5 legal analysis and curate-then-collect added |
| [RELATED-WORK](00-planning/RELATED-WORK.md) | 1.0 | Active | R2 | 2026-08-08 | New |
| [FEASIBILITY-AUDIT](00-planning/FEASIBILITY-AUDIT.md) | 1.1 | Active | All | 2026-08-10 | Governs scope decisions. Revised total ~890 h after ADR-009/010 |
| [SCOPE-VARIATION-REQUEST](00-planning/SCOPE-VARIATION-REQUEST.md) | 1.0 | **Awaiting submission** | Team lead | 2026-08-10 | One page for the guide. **Submit Week 1–2** — ADR-006/008 block the plan until decided |
| [PROCESS-REVIEW](00-planning/PROCESS-REVIEW.md) | 1.0 | Active | All | 2026-08-10 | 17:1 docs-to-code ratio; five ordered actions for this week. **Stop planning after action 3** |
| [TRIAGE-001](00-planning/triage/TRIAGE-001-mqtt-payload-schema.md) | 1.0 | Open | R4 | 2026-08-10 | Six §17.1 payload defects. Pending item P7 |
| [TRIAGE-002](00-planning/triage/TRIAGE-002-webster-parameterisation.md) | 1.1 | **Partly closed** | R3 | 2026-08-10 | ADR-011 closes cycle bounds, two-role reconciliation, recalibration. **Saturation flow, lost time and prior art still open** (P8) |
| [RESEARCH-001](00-planning/research/RESEARCH-001-webster-parameterisation.md) | 1.0 | **Partial — incomplete** | R3 | 2026-08-10 | Codebase constraints answered; **prior-art half unanswered** (both web angles hit the session limit). Three interim decisions need no further evidence. Re-run at medium after the limit resets |

## Decisions

| ADR | Status | Approved by | Blocks |
|---|---|---|---|
| [001](00-planning/decisions/ADR-001-two-track-dataset-strategy.md) two-track dataset | Active | Team | — |
| [002](00-planning/decisions/ADR-002-mfstnet-training-corpus.md) auto-labelled corpus | Active | Team | — |
| [003](00-planning/decisions/ADR-003-laptop-as-edge.md) laptop as edge | Active | Team | — |
| [004](00-planning/decisions/ADR-004-phased-document-delivery.md) document waves | Active | Team | — |
| [005](00-planning/decisions/ADR-005-local-first-training.md) local-first + feature cache | Active | Team | — |
| [006](00-planning/decisions/ADR-006-curate-then-collect-dataset.md) curate-then-collect | **Proposed** | *Faculty guide — pending* | PRD A13, FR-D01..D07, M1 |
| [007](00-planning/decisions/ADR-007-backbones-and-training-recipe.md) DINOv2 / bf16 / LoRA | Active | Team | — |
| [008](00-planning/decisions/ADR-008-prototype-descoping.md) prototype descoping | **Proposed** | *Faculty guide — pending* | PRD A14, FR-UI*, NFR-06, NFR-12, M9, M10 |
| [009](00-planning/decisions/ADR-009-ppo-forecast-surrogate.md) PPO forecast surrogate, 16-dim state | Active | Team | PRD A16 |
| [010](00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md) SUMO sublane + heterogeneous vTypes | Active | Team | FR-S01, FR-S02 |
| [011](00-planning/decisions/ADR-011-webster-definition.md) Webster cycle clamping, starvation semantics, two roles | Active | Team | Closes P6; advances P8; opens P9 |

## Requirements

| Document | Ver | Status | Owner | Checked | Notes |
|---|---|---|---|---|---|
| [SRS](01-requirements/SRS.md) | 1.1 | Active | All | 2026-08-10 | §2.1 updated for the 16-dim state (A16) |
| [FRD](01-requirements/FRD.md) | 1.2 | Active | All | 2026-08-10 | §3 banner for pending A13; FR-R02/FR-M14 updated for A16 |
| [NFR](01-requirements/NFR.md) | 1.1 | Active | All | 2026-08-08 | §2.2 optimistic-proxy rule; §2.3 quantised-reporting rule |
| [RTM](01-requirements/RTM.md) | 1.1 | Active | All | 2026-08-08 | §5.4 pending-change impact added |

## Design · Testing · Deployment

| Document | Status | Owner | Due |
|---|---|---|---|
| [HLD — detection & corpus pipeline](02-design/HLD-detection-corpus-pipeline.md) | **Active** (1.1 — A15 window math) | R1 | Delivered early |
| SAD | Scheduled | All | Week 5 |
| HLD (remaining subsystems) | Scheduled | Per owner | Week 5 |
| LLD | Scheduled | Per owner | Week 5 |
| STP · STD · UAT | Scheduled | All | Week 11 |
| STR | Scheduled | All | Week 16 |
| TIM · SOP | Scheduled | R4 | Week 16 |

## Plans

| Document | Ver | Status | Owner | Checked | Notes |
|---|---|---|---|---|---|
| [PLAN-01 — detection & corpus pipeline](plans/PLAN-01-detection-corpus-pipeline.md) | 1.1 | Active | R1 | 2026-08-10 | WI-01..WI-19. **WI-12/13 done, WI-15 partly**; reordered ahead of the blocked pilots, with the reason recorded |

## Repository scaffolding

Not documentation, but part of the pre-implementation deliverable and checked in the same pass.

| Artifact | Status | Notes |
|---|---|---|
| `requirements.txt` | Active | Pinned (NFR-08). PyTorch installs separately from the CUDA index |
| `.env.example` | Active | Copy to `.env`; `.env` is gitignored |
| `scripts/seed.py` | Active | NFR-07. Includes DataLoader worker seeding, which is the hole people leave open |
| `scripts/check_env.py` | Active | Pre-flight. **Catches the Python 3.13+ / torch incompatibility** that otherwise presents as a confusing pip error |
| `scripts/check_docs.py` | Active | Link check · withdrawn-claim guard · ADR registration |
| `.github/workflows/docs.yml` | Active | Runs `check_docs.py` on any markdown change |
| Directory skeleton (PRD §22.3) | Active | Created and committed |
| `mfstnet/configs/spec.yaml` | Active | **Single source of truth** for numbers that span documents (NFR-16) |
| `tests/test_spec_invariants.py` | Active | Asserts cross-document arithmetic. Its first version encoded a wrong model of lane wait (see withdrawn claims); corrected 2026-08-10 |
| `mfstnet/corpus/` | Active | **First project code.** Label rule, window timing, clip-level splits. Pure stdlib — no torch, no video, no GPU |
| `tests/test_corpus.py` | Active | 38 assertions, 6 of them A15 regressions. Runs in milliseconds |

## Manual and templates

| Document | Ver | Status | Checked | Notes |
|---|---|---|---|---|
| [EXECUTION_MANUAL](90-manual/EXECUTION_MANUAL.md) | 1.2 | Active | 2026-08-10 | Week plan revised; §1.2 Week-2 pilots added; annotation velocity corrected; campus collection SOP |
| [TRAINING-GUIDE](90-manual/TRAINING-GUIDE.md) | 1.0 | Active | 2026-08-08 | New |
| [templates/](templates/) | 1.0 | Active | 2026-08-08 | Weekly status · experiment record · risk entry |

## Archive

| Document | Superseded by | Why |
|---|---|---|
| [2026-08-07 SDLC suite design](99-archive/2026-08-07-sdlc-suite-design-SUPERSEDED.md) | [ADR-004](00-planning/decisions/ADR-004-phased-document-delivery.md) + [docs/README](README.md) | Its content is fully carried by the ADR and the index. Retained for the decision trail |

---

## Withdrawn claims

Statements that appeared in an earlier revision and are **wrong**. Listed explicitly so nobody
rediscovers them in an old draft and acts on them.

| Withdrawn | Where it appeared | Correction |
|---|---|---|
| "400 frames/day/person" annotation velocity | Execution Manual Part 2 | Wrong by roughly 3× for dense Indian scenes (20–60 objects/frame). Measure it in Week 2 — Manual §1.2 |
| "MFSTNet trains on SUMO sequences" | PRD §20 L1 (original) | Never viable with frozen ImageNet backbones. Corpus is auto-labelled real video — PRD §8.6 |
| Global average pooling before the congestion head | PRD §8.1 (original) | Produces four identical lane predictions. Replaced by per-lane ROI pooling — A8 |
| `unfreeze_epoch: 30` | PRD §8.4 (original) | R4 predicts it fails, and it breaks the feature cache. Replaced by a LoRA experiment — A12 |
| "500 sequences spot-checked" | PRD §8.6 (original) | ~17 h producing a number that changed no decision. Concentrated on the test split — A9 |
| Ablation limited to 50 epochs (R6 mitigation) | PRD §19 R6 | No longer needed; feature caching makes the full 100-epoch ablation cheap — A7 |
| "FR-R04's 180 s starvation limit contradicts a 186 s worst-case cycle" (P6) | PRD-CHANGELOG, TRIAGE-002, ADR-011 draft | **My own finding, withdrawn.** Conflated cycle length with lane wait: a lane waits for the *other* phase's green plus two all-reds = 96 s, not a full cycle. No contradiction — [ADR-011](00-planning/decisions/ADR-011-webster-definition.md) §Decision 2 |
| IDD Temporal as a source of MFSTNet sequences | Considered, never adopted | Provides ±15 frames (~1–2 s), not the ~6 minutes §8.6 needs — [DATASETS §4](00-planning/DATASETS.md) |
| Label at `t+60s`; "5-minute clips" | PRD §8.6, ADR-002, manual (original) | **Fatal.** `t+60s` sits inside the 295 s observation window, and 355 s are needed per sample so a 5-min clip yields zero sequences. Corrected by A15 — label at `t0+355s`, minimum clip 6 min |
| 17-dimensional PPO state with `mfst_gate_mean` | PRD §13.1 (original) | The gate has no SUMO analogue, so it would be a constant dead input during 500K training steps. Removed by A16 — 16 dims |
| Aggregate macro F1 as the headline metric | PRD §14.5 (original) | Persistence over a 60 s horizon may put Naive near the ceiling. Transition-window recall is the headline metric (A17) |
| Bootstrap over sequences | Implied by FR-R07 wording | Sequences within a clip are correlated; resample **clips** (A19) |

---

## Reconciliation checklist

Run at each wave gate and after any ADR is accepted.

- [ ] Every **Active** document's "checked" date is at or after the newest accepted ADR
- [ ] No document contradicts an Active ADR
- [ ] Every **Proposed** ADR has a named approver and a date it was raised
- [ ] Superseded documents are in `99-archive/` with a supersession header
- [ ] Withdrawn claims table covers anything corrected since the last reconciliation
- [ ] **Any spec stating two independent durations has one worked example with real numbers.**
      Added after A15: the corpus window bug survived because 295 s and 60 s were each stated
      correctly and never added together
- [ ] [RTM](01-requirements/RTM.md) counts match the requirement documents
- [ ] `python scripts/check_docs.py` exits 0 — links resolve, no withdrawn claim resurrected, every
      ADR registered. This also runs in CI on any markdown change

> The checker handles the mechanical half. The half that needs judgement — *does this document still
> say the right thing* — is this reconciliation pass. Do not let a green CI substitute for reading.
