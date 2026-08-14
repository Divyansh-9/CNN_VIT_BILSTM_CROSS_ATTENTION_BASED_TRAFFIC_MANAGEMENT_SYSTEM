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
| [SOW](00-planning/SOW.md) | 1.3 | Active | All | 2026-08-10 | §2.4 capacity baseline; risks R16–R26; D-02/M1 flagged conditional |
| [BRD](00-planning/BRD.md) | 1.0 | Active | All | 2026-08-08 | BO-3 flagged conditional on ADR-006 |
| [PRD](00-planning/PRD.md) | **1.2** | Active | All | 2026-08-10 | **A1–A12 and A15–A21 applied.** §12 carries a PROPOSED banner for A13 |
| [PRD-CHANGELOG](00-planning/PRD-CHANGELOG.md) | — | Active | All | 2026-08-10 | A13/A14 blocked; A15–A21 applied; includes the why-A15-was-missed note |
| [DATASETS](00-planning/DATASETS.md) | 1.2 | Active | R1 | 2026-08-10 | §1.5 legal analysis; §2.05 published evidence that detection fails on India-specific classes (risk R25) |
| [RELATED-WORK](00-planning/RELATED-WORK.md) | 1.1 | Active | R2 | 2026-08-10 | **§2.6 added — vision-based congestion prediction, missed by the first survey. C1 narrowed** |
| [FEASIBILITY-AUDIT](00-planning/FEASIBILITY-AUDIT.md) | 1.1 | Active | All | 2026-08-10 | Governs scope decisions. Revised total ~890 h after ADR-009/010 |
| [BIBLIOGRAPHY](00-planning/BIBLIOGRAPHY.md) | 1.0 | Active | R2 | 2026-08-10 | 35 references with a **verified/unverified** mark. Nothing enters the paper while marked ⚠️. Five-item verification queue |
| [SCOPE-VARIATION-REQUEST](00-planning/SCOPE-VARIATION-REQUEST.md) | 1.0 | **Decided — accepted** | Project owner | 2026-08-13 | One page for the guide. **Submit Week 1–2** — ADR-006/008 block the plan until decided |
| [PROCESS-REVIEW](00-planning/PROCESS-REVIEW.md) | 1.0 | Active | All | 2026-08-10 | 17:1 docs-to-code ratio; five ordered actions for this week. **Stop planning after action 3** |
| [TRIAGE-001](00-planning/triage/TRIAGE-001-mqtt-payload-schema.md) | 1.1 | **CLOSED** | R4 | 2026-08-13 | All six defects closed by A26 + `contracts/mqtt.py`. A seventh found while building: QoS was overridable |
| [TRIAGE-002](00-planning/triage/TRIAGE-002-webster-parameterisation.md) | 1.2 | **CLOSED** | R3 | 2026-08-10 | ADR-011 closed items 3–5; [ADR-012](00-planning/decisions/ADR-012-webster-saturation-flow.md) closed 1, 2 and 6 from literature. P8 closed |
| [RESEARCH-001](00-planning/research/RESEARCH-001-webster-parameterisation.md) | 1.1 | **Superseded by ADR-012** | R3 | 2026-08-10 | The agent run was incomplete; a direct literature pass answered the same questions. Retained for the trail |

## Decisions

| ADR | Status | Approved by | Blocks |
|---|---|---|---|
| [001](00-planning/decisions/ADR-001-two-track-dataset-strategy.md) two-track dataset | Active | Team | — |
| [002](00-planning/decisions/ADR-002-mfstnet-training-corpus.md) auto-labelled corpus | Active | Team | — |
| [003](00-planning/decisions/ADR-003-laptop-as-edge.md) laptop as edge | Active | Team | — |
| [004](00-planning/decisions/ADR-004-phased-document-delivery.md) document waves | Active | Team | — |
| [005](00-planning/decisions/ADR-005-local-first-training.md) local-first + feature cache | Active | Team | — |
| [006](00-planning/decisions/ADR-006-curate-then-collect-dataset.md) curate-then-collect | **Accepted** | Project owner, 2026-08-13 | — |
| [007](00-planning/decisions/ADR-007-backbones-and-training-recipe.md) DINOv2 / bf16 / LoRA | Active | Team | — |
| [008](00-planning/decisions/ADR-008-prototype-descoping.md) prototype descoping | **Accepted** | Project owner, 2026-08-13 | — |
| [009](00-planning/decisions/ADR-009-ppo-forecast-surrogate.md) PPO forecast surrogate, 16-dim state | Active | Team | PRD A16 |
| [010](00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md) SUMO sublane + heterogeneous vTypes | Active | Team | FR-S01, FR-S02 |
| [011](00-planning/decisions/ADR-011-webster-definition.md) Webster cycle clamping, starvation semantics, two roles | Active | Team | Closes P6; advances P8; opens P9 |
| [012](00-planning/decisions/ADR-012-webster-saturation-flow.md) Sweep the published saturation-flow range | Active | Team | **Closes P8** |
| [013](00-planning/decisions/ADR-013-artifact-hosting-and-publication.md) GitHub for code, Hugging Face for use, Zenodo for citation | **Proposed** | Guide | Retires Git LFS for weights. **Opens P10** — what may be published from IndiaTrafficNet |
| [014](00-planning/decisions/ADR-014-dashboard-metrics-separation.md) Benchmark panel and live monitor are separate and never merge | **Proposed** | Guide | Live accuracy would be circular (A9). Derived overlay replaces video (NFR-13) |

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
| `BUILD-LOG.md` (root) | Active | **The live journal.** Step board S01–S48 with status and owner, blockers with their age, and a problem/fix entry per step. Written the day a step starts and closed the day it ends — the raw material for the report's *challenges faced* section |
| `EXPLAIN.md` (root) | Active | **Plain-English explainer with worked examples.** Written for a reader with no background — the onboarding path for the team, and the answer to "nobody has read the documents" |
| `mfstnet/configs/spec.yaml` | Active | **Single source of truth** for numbers that span documents (NFR-16) |
| `tests/test_spec_invariants.py` | Active | Asserts cross-document arithmetic. Its first version encoded a wrong model of lane wait (see withdrawn claims); corrected 2026-08-10 |
| `mfstnet/corpus/` | Active | **First project code.** Label rule, window timing, clip-level splits. Pure stdlib — no torch, no video, no GPU |
| `mfstnet/encoders.py` | Active | Dual-path backbones + A24 grid alignment. **Verified on real tensors**: 49 vs 257 native, both aligned to 49 |
| `notebooks/README.md` | Active | Notebook policy: presentation and driver layer only, never model or training code |
| `notebooks/03_results.ipynb` | Active | Renders committed result CSVs. Computes no metric of its own |
| `tests/test_spec_matches_code.py` | Active | Binds Python defaults to `spec.yaml`. Runs in both CI jobs |
| `simulation/webster.py` | Active | Webster + `select_best`. Two disqualifications found by running the sweep |
| `simulation/envs/traffic_env.py` | Active | Gymnasium env. 16-dim contract read from `spec.yaml`, `check_env` clean |
| `simulation/configs/ppo_config.yaml` | Active | PRD §13.1 hyperparameters + the three ADR-009 arms |
| `mfstnet/cache.py` | Active | ADR-005 cache. Stores the frozen half only; hash mismatch raises (SOW R20) |
| `tests/test_cache.py` | Active | 23 tests, mostly refusals. CI `model` job |
| `mfstnet/fusion.py` | Active | Cross-attention, 4 modes. Gate behind a Phase 2 flag (PRD §2.4) |
| `mfstnet/temporal.py` | Active | Lane ROI pooling (A8), BiLSTM, temporal attention, congestion head |
| `mfstnet/model.py` | Active | Assembly + the §14.4 ablation table as data. Consumes cached features (ADR-005) |
| `scripts/overfit_check.py` | Active | S26 gate. Found the dead `weight_hh_reverse` and the invented learning rate |
| `tests/test_model.py` | Active | 43 tests. Runs in the CI `model` job |
| `tests/test_encoders.py` | Active | 16 tests. The only guard on the A24 defect; runs in the CI `model` job |
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
| "PyTorch requires Python ≤3.12, so the project is blocked on installing 3.11" | Execution Manual §0.3, `check_env.py`, `pyproject.toml`, several status summaries | **Wrong, and self-inflicted.** torch 2.13 supports 3.14. The cap came from our own `torch==2.3.1` pin, chosen from memory and then treated as a fact about the world. Cost three days. **A pin is a decision, not a fact** |
| "400 frames/day/person" annotation velocity | Execution Manual Part 2 | Wrong by roughly 3× for dense Indian scenes (20–60 objects/frame). Measure it in Week 2 — Manual §1.2 |
| "MFSTNet trains on SUMO sequences" | PRD §20 L1 (original) | Never viable with frozen ImageNet backbones. Corpus is auto-labelled real video — PRD §8.6 |
| Global average pooling before the congestion head | PRD §8.1 (original) | Produces four identical lane predictions. Replaced by per-lane ROI pooling — A8 |
| `unfreeze_epoch: 30` | PRD §8.4 (original) | R4 predicts it fails, and it breaks the feature cache. Replaced by a LoRA experiment — A12 |
| "500 sequences spot-checked" | PRD §8.6 (original) | ~17 h producing a number that changed no decision. Concentrated on the test split — A9 |
| Ablation limited to 50 epochs (R6 mitigation) | PRD §19 R6 | No longer needed; feature caching makes the full 100-epoch ablation cheap — A7 |
| "C1: camera-only forecasting is novel because the literature assumes sensors" | RELATED-WORK §3 (original) | **Overstated.** Vision-based congestion prediction is an active field that the original review missed — it searched by architecture, not by task. C1 narrowed to the conjunction: per-lane + non-lane-disciplined heterogeneous + controller-coupled ([RELATED-WORK §2.6](00-planning/RELATED-WORK.md)) |
| "Use the HCM ~1900 pcu/h/lane saturation flow default" | TRIAGE-002 §Missing information | Structurally wrong for non-lane-disciplined traffic — lanes are not the unit of discharge. Published practice is per metre of approach width ([ADR-012](00-planning/decisions/ADR-012-webster-saturation-flow.md)) |
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
