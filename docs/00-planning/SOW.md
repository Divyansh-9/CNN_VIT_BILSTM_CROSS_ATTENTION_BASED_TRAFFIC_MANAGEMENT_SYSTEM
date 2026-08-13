# Statement of Work (SOW)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | SOW v1.0 |
| **Date** | 2026-08-07 |
| **Duration** | 20 weeks (Week 0 – Week 20) |
| **Type** | B.Tech CSE (ML/AI) 7th-semester major project |
| **Budget** | ₹0 cash baseline (see §8) |
| **Governing document** | [PRD v1.0](PRD.md) — authoritative for architecture, requirements, and numbers |

> **Action required:** names in §3 and dates in §5 are placeholders. Fill them in before the first
> faculty review and commit the change.

---

## 1. Purpose

This SOW defines what the team will deliver, who delivers it, by when, and what counts as done. It
is the contract between the team and the faculty guide. Where this document and the PRD differ on a
technical number, the PRD wins; where they differ on scope or schedule, this document wins.

## 2. Scope of work

### 2.1 In scope

Four subsystems, developed largely in parallel and integrated in Weeks 17–19.

| # | Subsystem | Deliverable |
|---|---|---|
| S1 | **IndiaTrafficNet** | 12,000+ frame annotated dataset, 8 India-specific classes, publicly released on Roboflow Universe and Kaggle |
| S2 | **Detection** | YOLOv8 fine-tuned on IndiaTrafficNet, benchmarked against COCO baseline |
| S3 | **MFSTNet** | Multimodal congestion prediction model + 7-configuration ablation study |
| S4 | **PPO controller** | Stable-Baselines3 PPO agent on a SUMO 4-way intersection, benchmarked over 30 runs against Fixed, Webster, and Random |
| S5 | **Prototype** | Edge node ⇄ MQTT ⇄ FastAPI server ⇄ React dashboard, running end to end |
| S6 | **Research output** | Conference paper submitted (IEEE ITSC / CVIP), full SDLC documentation suite, open-source repository |

### 2.2 Explicitly out of scope

Naming exclusions now prevents scope creep later. The following are **not** deliverables and appear
in the paper only as future work:

- Multi-intersection coordination or network-level control (PRD §20 L2)
- Nighttime, rain, or fog conditions (§20 L3)
- Vehicle tracking, re-identification, or trajectory prediction
- License plate recognition or any personally identifying inference
- Deployment to a live public road, or any interaction with real traffic infrastructure
- Mobile applications
- Fine-tuning ResNet-50 or ViT-Small backbones beyond the schedule in PRD §8.4
- Cloud hosting of any component beyond free-tier evaluation

### 2.3 Conditional scope

Governed by PRD §2.4. These are attempted **only** after all mandatory work is complete, and dropped
to Future Work without penalty if the schedule does not allow:

- Gated bidirectional cross-attention (Phase 2)
- Temporal self-attention and attention pooling (Phase 2)
- Live end-to-end PPO runtime integration (Phase 3)

## 2.4 Capacity baseline

Added 2026-08-08. The original SOW committed to deliverables without stating available effort, which
is how a plan becomes 1.6× overcommitted without anyone noticing.

| | Optimistic | **Planning baseline** |
|---|---|---|
| Students | 4 | 3.5 effective |
| Hours/week/student | 15 | 12 |
| Productive weeks | 20 | 17 (placement season + internal exams) |
| **Total person-hours** | 1,200 | **~715** |

Estimated work as originally specified: **~1,200 person-hours**. Full breakdown in
[FEASIBILITY-AUDIT §2](FEASIBILITY-AUDIT.md).

**Closed 2026-08-13.** [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) (−200 h) and
[ADR-008](decisions/ADR-008-prototype-descoping.md) (−140 h) accepted by the project owner.

| | Hours |
|---|---|
| As originally specified | ~1,200 |
| ADR-006 + ADR-008 | −340 |
| ADR-009 three-arm PPO · ADR-010 SUMO heterogeneity | +35 |
| **Current** | **~895** against ~715 available |

Still ~1.25× over, which is where a final-year project should sit: the conditional scope in §2.3
absorbs the difference and is dropped without penalty if the schedule does not allow.

## 3. Team and responsibilities

Four roles. With a three-member team, R4 is absorbed by R1 and R3.

| Role | Owner | Owns | Backup |
|---|---|---|---|
| R1 — Data & Detection Lead | *TBD* | S1, S2; annotation velocity; auto-label pipeline | R3 |
| R2 — Model Lead | *TBD* | S3; training runs; ablation harness | R1 |
| R3 — Simulation & RL Lead | *TBD* | S4; SUMO environment; 30-run benchmark | R2 |
| R4 — Systems & UI Lead | *TBD* | S5; MQTT, FastAPI, dashboard, edge node | R3 |
| All | — | S6; documentation; weekly status; paper sections | — |

**Every deliverable has exactly one named owner and one named backup.** A deliverable owned by
"everyone" is owned by no one, and this is the most common way an academic project loses two weeks.

### 3.1 Cadence

| Ceremony | Frequency | Duration | Output |
|---|---|---|---|
| Team standup | 2×/week | 15 min | Blockers only |
| Weekly status | Weekly, Friday | 30 min | `docs/90-manual/weekly/Wxx.md` filled from template |
| Faculty guide review | Fortnightly | 30 min | Guide sign-off recorded in the weekly file |
| Wave gate review | W05, W11, W16 | 60 min | Next documentation wave written (ADR-004) |
| Milestone demo | Per M1–M11 | 30 min | Acceptance recorded against §5 criteria |

## 4. Deliverables

| ID | Deliverable | Format | Due |
|---|---|---|---|
| D-01 | SDLC documentation Wave 1 | Markdown in `docs/` | Week 1 |
| D-02 | IndiaTrafficNet public release † | Roboflow Universe + Kaggle | Week 8 |
| D-03 | Fine-tuned YOLOv8 weights + mAP comparison report | `.pt` via LFS + CSV | Week 9 |
| D-04 | SUMO environment with 4 signal methods | XML + Python | Week 10 |
| D-05 | SDLC documentation Wave 2 (SAD/HLD/LLD) | Markdown | Week 5 |
| D-06 | MFSTNet Phase 1 trained model | `.pt` via LFS + TensorBoard logs | Week 12 |
| D-07 | Ablation study, configs A–G | CSV + summary table | Week 14 |
| D-08 | PPO agent + 30-run benchmark with statistics | `.zip` + raw CSVs | Week 14 |
| D-09 | SDLC documentation Wave 3 (STP/STD/UAT) | Markdown | Week 11 |
| D-10 | Working prototype | Live demo + recorded video backup | Week 16 |
| D-11 | Dashboard, 4 pages | Deployed locally, screencast | Week 17 |
| D-12 | SDLC documentation Wave 4 (STR/TIM/SOP) | Markdown | Week 16 |
| D-13 | Conference paper + submission receipt | PDF | Week 20 |
| D-14 | Final project report + open-source repository | PDF + GitHub | Week 20 |

† **A13 and A14 are IN FORCE from 2026-08-13** (project owner). D-02 is a curated benchmark plus a
≥1,500-frame permissioned set from ≥60 sessions. D-10/D-11 carry the ADR-008 reductions: SQLite +
Parquet, shared password, 2 dashboard pages, 1-hour uptime evaluation.

## 5. Milestones and acceptance criteria

Reproduced from PRD §18.2. **These numbers are the definition of done.** A milestone is accepted
only when its criterion is demonstrated with evidence committed to the repository — not asserted.

| ID | Milestone | Acceptance criterion | Due | Evidence artifact |
|---|---|---|---|---|
| M1 | IndiaTrafficNet published | **A13 in force:** Part A benchmark published with datasheet **+** Part B ≥1,500 anonymised frames from **≥60 sessions** | W8 | Public URLs |
| M2 | YOLOv8 validated | ≥10% mAP improvement over COCO on Indian classes; ≥25% on auto-rickshaw | W9 | `experiments/results/detection_map.csv` |
| M3 | SUMO running | All 4 signal methods run; traffic calibrated from dataset | W10 | Config + calibration report |
| M4 | MFSTNet core working | CNN+ViT+CrossAttn+BiLSTM trains and converges | W12 | TensorBoard loss curves |
| M5 | MFSTNet benchmarked | Macro F1 ≥ 0.80; ablation table complete | W14 | `experiments/results/ablation.csv` |
| M6 | PPO converged | Reward curve plateaued; TensorBoard stable | W13 | TensorBoard reward curve |
| M7 | RL benchmark complete | 30 runs/method; PPO ≥20% better than Fixed and ≥10% than Webster, p<0.05 | W14 | `experiments/results/rl_runs.csv` |
| M8 | Prototype live | ≥10 fps; emergency preemption 10/10 within 3s | W16 | Demo video + latency CSV |
| M9 | Dashboard complete | 4 pages live, WebSocket, all data feeds populated | W17 | Screencast |
| M10 | Full integration | PPO + MFSTNet + edge + dashboard running 4 hours continuously | W19 | Uptime log |
| M11 | Paper submitted | Submission receipt from target venue | W20 | Receipt PDF |

### 5.1 Definition of Done (applies to every deliverable)

A deliverable is done when **all** of the following hold. Partial completion is reported as
in-progress, never as done.

- [ ] Acceptance criterion in §5 demonstrably met, with evidence committed
- [ ] Code merged to `main`, passing whatever tests exist for it
- [ ] Seed fixed and recorded; run reproducible from committed config (NFR-07)
- [ ] Raw results committed as CSV, not only as a summary table (NFR-09)
- [ ] Owning document updated (RTM row closed; relevant design/test doc current)
- [ ] Demonstrated to the faculty guide or recorded in the weekly status

## 6. Assumptions

| # | Assumption | If it proves false |
|---|---|---|
| A1 | Google Colab free tier provides sufficient T4 access for ~100h of training | Reduce ablation to 50 epochs/config (PRD R6); stagger runs across team accounts |
| A2 | A public Indian traffic dataset with a compatible licence is available | Fall back to AI City Challenge; failing that, IndiaTrafficNet returns to the critical path |
| A3 | Team can safely record video at 6 public intersections | Start with campus intersections (PRD R1); supplement with dashcam footage |
| A4 | At least one laptop can run SUMO, YOLOv8, and MQTT concurrently | Split across two machines over LAN |
| A5 | Faculty guide is available fortnightly | Escalate to project coordinator; keep written status regardless |
| A6 | All four members remain through Week 20 | Backup owners (§3) take over; conditional scope (§2.3) is dropped first |

## 7. Constraints

| # | Constraint | Source |
|---|---|---|
| C1 | 20-week fixed deadline, no extension | Academic calendar |
| C2 | ₹0 cash budget | ADR-003 |
| C3 | No GPU beyond Colab free tier | A1 |
| C4 | Build order in PRD §2.4 is non-negotiable | PRD |
| C5 | Raw frames never leave the edge device at runtime | NFR-13 |
| C6 | Results reported honestly, including negative results | PRD §2.5.5 |

## 8. Budget

| Item | Cost | Note |
|---|---|---|
| Google Colab (free tier) | ₹0 | T4 access, session limits apply |
| Roboflow (free tier) | ₹0 | Public dataset projects are free |
| Kaggle, GitHub, MLflow, TensorBoard | ₹0 | |
| Overleaf (free tier) | ₹0 | Sufficient for a conference paper |
| SUMO, PyTorch, Ultralytics, SB3, Mosquitto, FastAPI, React | ₹0 | Open source |
| Edge device | ₹0 | Team laptop + webcam (ADR-003) |
| Conference submission fee | *Deferred* | Only on acceptance; ITSC/CVIP student rates apply. Not committed at submission time |
| **Baseline total** | **₹0** | |

| Optional upgrade | Cost | Trigger |
|---|---|---|
| Jetson Nano / Orin Nano | ₹12,000–18,000 | Only if department funds it or a lab unit is unavailable and the team elects to buy |
| LEDs + jumper wires | <₹200 | Only if a Pi or Jetson is obtained |
| Colab Pro | ₹1,100/month | Only if free-tier limits block the ablation in Week 13 |

## 9. Risks

The full register is PRD §19 (R1–R10). Risks introduced or altered by the ADRs:

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R11 | Auto-labels carry YOLOv8 detection error into MFSTNet ground truth | High | Medium | 500-sequence manual verification; report label-noise estimate (ADR-002) | R1 |
| R12 | Public dataset taxonomy does not map cleanly to 8 target classes | Medium | Low | Mapping table, Manual Part 2; unmapped classes as background until W8 | R1 |
| R13 | Track B (IndiaTrafficNet) is deprioritised once Track A works | Medium | High | M1 is a graded Week 8 milestone; weekly frames/day velocity tracked | R1 |
| R14 | Documentation Waves 2–4 not written under deadline pressure | Medium | Medium | Wave gates scheduled at W05/W11/W16 as milestones (ADR-004) | All |
| R15 | Laptop-proxy latency figures challenged in viva | Low | Low | Every latency table states its measurement host; **also report CPU-only figures** — an RTX 4050 is an optimistic proxy for a Jetson, not a representative one | R4 |
| ~~R16~~ | ~~Scope remains 1.6× overcommitted~~ | — | — | **Closed 2026-08-13** — ADR-006 and ADR-008 accepted; ~340 h recovered | — |
| R17 | Annotation velocity turns out worse than the Week-2 pilot suggests | Medium | High | Pilot in Week 2 (Manual §1.2); track weekly; Part B's smaller target gives headroom the 12,000-frame plan did not | R1 |
| R18 | Congestion thresholds produce a degenerate class on real data | Medium | High | Week-2 count-distribution pilot; S6 distribution gate fails before training; S3/S4 seam makes recalibration a 30-second rebuild (P1) | R1/R2 |
| R19 | Reviewer identifies the fusion mechanisms as prior art (Conformer, ViLBERT, Flamingo) | **High** | Medium | Narrow the claim per [RELATED-WORK §3](RELATED-WORK.md); cite the precedents in the related-work section rather than being informed of them | R2 |
| R20 | Feature cache goes stale and silently corrupts results | Low | **High** | `preprocessing_hash` + git commit in the manifest; **assert on load and raise, never warn** | R2 |
| R21 | **Task is persistence-degenerate** — ~90% of windows do not change class over 60 s, so Naive ties every model | Medium | **High** | Week-2 pilot measurement 4 (Manual §1.2). Transition-window recall becomes the headline metric (PRD A17); below 5% transitions, revisit horizon or class boundaries before M4 | R1/R2 |
| R22 | **Venue deadline falls outside the project window** | Medium | High | Project ends ~Dec 2026. **Verify IEEE ITSC 2027 and CVIP submission dates in Week 1** and record them in the weekly status. CVIP's annual cycle may close before Week 20; if so, pick the venue that fits and adjust §5 M11 rather than discovering it in Week 19 | Team lead |
| R23 | Label noise concentrated in the HIGH class, where the claim lives | High | Medium | Occlusion is worst at high density, so the detector undercounts exactly where C5 is evaluated. Stratify human verification by density and re-derive **test** density bands from human counts (PRD A18); report per-stratum label noise rather than one average | R1 |
| R24 | SUMO models lane-disciplined traffic while the paper is about unstructured traffic | High | **High** | [ADR-010](decisions/ADR-010-sumo-heterogeneous-traffic.md) — sublane model + heterogeneous vTypes + a baseline sensitivity check. Fallback if capacity fails: vTypes only, ~5 h | R3 |
| R25 | **Detector fails on the India-specific classes the dataset exists to add** | High | **High** | Published evidence (Rashmi & Shantala 2020, [RELATED-WORK §2.6](RELATED-WORK.md)): YOLO reaches 92–99% on bus/car/motorcycle in Indian footage but drops below usable accuracy on zone-specific modes. This is a direct threat to FR-D09's ≥25% auto-rickshaw criterion. Report per-class mAP **with sample count**; if auto-rickshaw stays low after fine-tuning, that is a reportable finding about detector transfer, not a hidden failure | R1 |
| R26 | Novelty overclaimed a second time — a task-level literature was missed | Medium | High | §2.6 correction. **Search by task, not only by architecture**, before the paper is drafted. Two overclaims found by review; assume a third exists | R2 |

## 10. Acceptance and sign-off

The project is complete when D-01 through D-14 are delivered and M1–M11 are accepted. Faculty guide
sign-off is recorded per milestone in the corresponding weekly status file.

| Party | Name | Signature | Date |
|---|---|---|---|
| Project team lead | *TBD* | | |
| Faculty guide | *TBD* | | |
| Project coordinator | *TBD* | | |

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial SOW, incorporating ADR-001 through ADR-004 |
