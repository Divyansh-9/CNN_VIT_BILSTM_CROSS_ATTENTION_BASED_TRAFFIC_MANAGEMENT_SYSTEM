# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

**The code exists — roughly 43,000 lines of Python across 170 files, 58 test
modules, 226 commits.** Scripts are the largest share at 25,500 lines over 71
files, which is the shape of this project: the pipeline is the deliverable.
`mfstnet/` is 4,100 lines and `tests/` 10,400. Both the documentation suite and the implementation are
live, and they can disagree; when they do, the changelog entry is usually the
newer fact. Start at [docs/README.md](docs/README.md), which indexes the
documents and states the reading order, and at [BUILD-LOG.md](BUILD-LOG.md),
which is the status board for implementation steps. Git LFS is configured for
model weights.

Built and working: the corpus pipeline, the feature cache, MFSTNet with the
full A-H ablation, leave-one-camera-out evaluation, the classical baselines,
the SUMO environment and PPO arms, the benchmark harness, ONNX export, the
FastAPI control server, the edge node with both FR-A06 fallbacks, and a
read-only React dashboard (`1102932`; see "Dashboard status" below).

The PRD ([docs/00-planning/PRD.md](docs/00-planning/PRD.md), now v1.1) remains the single source of truth for architecture, requirements (IDs `FR-*`, `NFR-*`), milestones, and acceptance criteria. Before implementing anything, find the governing requirement ID and honor its exact numbers rather than inventing values. When implementation reveals the PRD is wrong, amend the PRD and log it in [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) — never work around a PRD statement you believe is incorrect.

Requirement IDs are defined **once**, but not all in one file: `BR-*` in the BRD, `FR-*` and `NFR-01..13` in PRD §9/§10, and **`NFR-14..16` in [docs/01-requirements/NFR.md](docs/01-requirements/NFR.md)**, which introduces them as constraints the PRD implies without ever writing down as verifiable requirements. Every other document cites IDs and never restates requirements in prose. `scripts/check_docs.py` enforces both directions — an id cited nowhere-defined fails, and an id defined but absent from the RTM fails (P76). [RTM](docs/01-requirements/RTM.md) is the join table (BR → FR/NFR → DES → TC → M); update it when requirements change.

Documents are delivered in waves (ADR-004). Wave 1 (planning + requirements + manual) is done; SAD/HLD/LLD are due Week 5, STP/STD/UAT Week 11, STR/TIM/SOP Week 16. Missing later-wave documents are scheduled, not overlooked.

Project context: 4th-year B.Tech CSE (ML/AI) major project, 20-week academic timeline, 3-4 member team, ₹0 cash budget, targeting a conference submission (IEEE ITSC / CVIP).

## Read the feasibility audit before planning any work

[docs/00-planning/FEASIBILITY-AUDIT.md](docs/00-planning/FEASIBILITY-AUDIT.md) estimates ~1,200 person-hours of specified work against ~715 hours of realistic team capacity. Its conclusions govern: annotation effort was underestimated by roughly 3×, the dashboard and production stack consume a quarter of the project for almost no assessed value, and the novelty claim must be narrowed (see [RELATED-WORK.md](docs/00-planning/RELATED-WORK.md) — the fusion mechanisms are all published; the gate-as-artifact, camera-only framing, and density-stratified evaluation are what is defensible).

ADR-006 and ADR-008 were **accepted 2026-08-13 by the project owner**, and both records say in as many words that this is **not a faculty-guide signature**. Build against them — that is what the acceptance decided — but treat the scope they cut as still owing the guide a conversation, and keep the ~340 h of recovered work visible in any progress report rather than quietly gone.

## Decisions that override the original PRD text

Twenty-seven ADRs (ADR-001 to ADR-027) in [docs/00-planning/decisions/](docs/00-planning/decisions/) changed how the project executes. Read them before acting on PRD §8, §12, §15, or §20. ADR-001 to ADR-008 are the ones that rewrite the architecture; ADR-009 to ADR-023 mostly settle how something is measured, and several of them are the reason a number in the PRD is no longer the number to quote. The four newest set data scope (ADR-024 synthetic data, ADR-025 Indian-only headline folds) and deployment (ADR-026 MFSTNet on the edge, ADR-027 the two forecasting roles):

- **ADR-001** — dataset is two-track. YOLOv8 bootstraps on a public Indian dataset from Week 2; IndiaTrafficNet runs in parallel and swaps in at Week 8. Between Weeks 2–8 two sets of detector weights exist, so every experiment must record which it used.
- **ADR-002** — MFSTNet's training corpus is built by auto-labelling real 5-minute video clips with the fine-tuned YOLOv8 (counts → PRD §14.1 thresholds → congestion label at t+60s). The PRD originally had no corpus specification, and §20 L1's claim that MFSTNet trains on SUMO sequences was wrong. **Splits are cut by source clip, never by sequence** — overlapping windows would leak.
- **ADR-003** — the edge node is a team laptop, not a Jetson (₹0 budget). Control logic and the MQTT contract are unchanged. **Every latency figure must state its measurement host**; laptop numbers are labelled proxy measurements.
- **ADR-004** — documents ship in four waves gated on PRD §18 phases.
- **ADR-005** — training is local-first (RTX 4050 laptop) on **cached frozen-backbone features**. At batch 32 × T=60 an uncached step pushes 1,920 frames through both backbones, which does not fit 6GB and is tight even on a T4. Caching collapses the 60–90h ablation to hours. A cache is invalidated by any change to backbone, resize, or normalization — assert the `preprocessing_hash` on load and raise, never warn.
- **ADR-007** — DINOv2 ViT-S/14 replaces supervised ViT-S/16 as the default (frozen backbones mean representation quality is everything); bf16 AMP for training; INT8 ONNX only at export; LoRA instead of `unfreeze_epoch: 30`. Note patch-14 gives 257 tokens, not 197 — read token counts from config.
- **ADR-006 / ADR-008 (accepted 2026-08-13, project owner — not the guide)** — curate-then-collect dataset, and prototype descoping. IndiaTrafficNet is now Part A (curated from permissively-licensed public sources) + Part B (1,500–3,000 campus frames), not 12,000 self-collected ones.

The measurement decisions, ADR-009 to ADR-023. Each one changes what number is
correct to report, so check the ADR before quoting the PRD:

- **ADR-009** — PPO trains against a forecast surrogate, and the state vector was 16-dimensional (17 since ADR-020 as amended, P110). **ADR-021** amends it: forecast quality is a swept variable, and the perfect-forecast ceiling run comes first because it can falsify the whole RL track — if PPO with a perfect forecast does not beat PPO with no forecast, the forecast is not worth carrying.
- **ADR-010** — SUMO models heterogeneous, non-lane-disciplined traffic via the sublane model (`--lateral-resolution`), and the residual gap is declared rather than papered over.
- **ADR-011 / ADR-012** — Webster is two roles, not one, with explicit cycle clamping and starvation semantics; and saturation flow is **not chosen**. The published range is swept and Webster's *best* configuration is the baseline PPO must beat.
- **ADR-013** — code on GitHub, weights on Hugging Face, DOI from Zenodo. The public demo is deliberately smaller than the prototype.
- **ADR-014** — the dashboard shows benchmark numbers and live numbers in two visually separated panels that must never merge. Benchmark values load from the committed result CSV and carry split, *n*, date, and commit.
- **ADR-015** — success criteria, action space, and the priority order for what to work on next.
- **ADR-016** — two-phase corpus: build the pipeline on a non-Indian source, claim on India. Read together with the `domain` claim in CLAIMS.yaml, which is currently red for exactly this reason.
- **ADR-017** — congestion is defined on **PCU-weighted occupancy**, not raw vehicle count, from Indo-HCM 2017 values, with thresholds calibrated per camera at p33/p67 and recorded in the corpus manifest. An unmapped class raises rather than defaulting to 1.0.
- **ADR-018** — distil ITD-x into our YOLOv8s by pseudo-labelling, adopted **only** if pre-registered criteria are met on real labelled test data, never on pseudo-labels.
- **ADR-019** — leave-one-camera-out evaluation. This is the one that retires 60/20/20 for MFSTNet.
- **ADR-020** — **accepted as amended 2026-10-16 (project owner, not the guide) and implemented (P110).**
  - **Reserved zero:** 0.0 at indices 11–14 now means "no forecast for this approach", and no class can produce it (LOW, MEDIUM, HIGH → 1/3, 2/3, 1).
  - **Age channel:** one shared `forecast_age` is appended at index 16, so the state is 17-dim; index 15 stays `emergency_flag`.
  - **Fail-safe gate:** a forecast-aware policy may act only when every required input is complete, fresh (at most 10 s) and valid. Otherwise the no-forecast policy decides, or Webster for invalid counts (`simulation/forecast_state.py`).
- **ADR-022** — the full-model-versus-linear-probe test is pre-registered before the LOCO suite completes. A fold's test split is 140 / 252 / 44 / 136 lane-windows, 572 paired observations, 44 in the smallest.
- **ADR-023** — the two claims are stated separately: C1, the count-based forecaster plus RL controller, ships independent of C2, the vision claim.

**Read the Status field, and do not trust it as a record of what is running.**
ADR-016, ADR-019 and ADR-021 to ADR-025 are still marked *Proposed*, yet
ADR-019 is fully implemented and is what `resplit_corpus.py` does today.
ADR-020, ADR-026 and ADR-027 are *Accepted* by the project owner (not the
guide). ADR-020 is now implemented: `spec.yaml` declares `dim: 17` with
`forecast_age: 16` (P110).

Also fixed in the corpus spec: PRD §8.1 cannot produce four different lane predictions as written (global pooling then one shared head applied 4×) — **per-lane ROI pooling** replaces global pooling, which is why the feature cache must preserve spatial structure. And the evaluation was circular: labels derive from detector counts and three PRD §14.3 baselines also consume detector counts, so the **test split is human-verified** while train/val stay auto-labelled.

## What is being built

**MFSTNet** — a multimodal traffic-congestion predictor plus an RL signal controller, with an edge-to-server prototype around them. Four subsystems that are developed largely independently and only integrate late (Weeks 17-19):

1. **IndiaTrafficNet** — dataset, now Part A (curated) + Part B (1,500–3,000 campus frames) per ADR-006, with 8 India-specific classes incl. auto-rickshaw, e-rickshaw, cattle → fine-tunes YOLOv8s for edge detection. The 12,000-self-collected-frames figure is the pre-ADR-006 target and is no longer the plan.
2. **MFSTNet** — the model. ResNet-50 + DINOv2 ViT-S/14 (both frozen, ADR-007) → gated bidirectional cross-attention → BiLSTM → temporal self-attention → attention pooling → per-lane ROI pooling → per-lane congestion head (LOW/MEDIUM/HIGH, 60s ahead).
3. **PPO agent** — Stable-Baselines3 PPO on a SUMO 4-way intersection via TraCI. Consumes MFSTNet predictions as auxiliary state.
4. **Prototype** — edge node on a team laptop, not a Jetson (ADR-003; the MQTT contract and control logic are unchanged, but every latency figure must state its measurement host) ⇄ MQTT ⇄ FastAPI server (the policy, its safety guard, and storage of the forecasts it receives) ⇄ read-only React dashboard. **Forecasting runs on the edge** (ADR-026), because MFSTNet's input is frames and NFR-13 keeps frames there. Per **ADR-027**, the prototype publishes two separate forecasts: the **persistence congestion class** and the **ridge next-minute count**. MFSTNet's verified edge path is retained but does not serve them. Neither forecast is connected to the policy or to signal timing (P97a).

### Data flow that spans components

The coupling that is easy to miss: **MFSTNet's output is not just a prediction, it is part of the PPO state vector.** The state is **17-dim** (ADR-020 as amended, P110):
- **Indices 11–14** hold one class forecast per approach, encoded 1/3, 2/3, 1, with **0.0 reserved for "no forecast"**. Under ADR-027 that forecast comes from whichever forecaster holds the role; the index names `mfst_pred_*` are kept.
- **Index 16** holds `forecast_age`.
- **History:** PRD §13.1 originally had a different 17th channel, `mfst_gate_mean`, which A16 removed.
- **Not yet connected:** no forecast feeds the policy today (ADR-027, P97a). Changing MFSTNet's output shape or normalization invalidates trained PPO checkpoints. The same predictions also flow to the server over MQTT topic `stms/{intersection_id}/congestion/prediction`, and the read-only dashboard reads them from the server's API, never from MQTT directly.

Two fallback paths are required behavior, not nice-to-haves (PRD §7.2, FR-A06): if MFSTNet inference fails, PPO must run on raw counts alone; if MQTT drops >10s, the Jetson switches to a locally-embedded Webster controller.

### The gate

`g = sigmoid(Linear([Z_A; Z_B]))`, `F_fused = g·Z_A + (1-g)·Z_B` where `Z_A` is CNN-queries-ViT and `Z_B` is ViT-queries-CNN. The gate value is a research artifact, not an internal detail — it is logged, tracked on the dashboard (FR-UI05), and analyzed in the paper. Always expose it from the forward pass; never discard it.

## Build order is non-negotiable

PRD §2.4 sets a strict priority order and it exists to prevent a known failure mode (over-engineering the architecture, under-delivering experiments). Do not implement Phase 2 features before Phase 1 converges:

- **Phase 1 (mandatory):** CNN + ViT + *standard* cross-attention + BiLSTM → congestion head.
- **Phase 2 (stretch):** gating replaces standard cross-attn; temporal self-attention on BiLSTM outputs; attention pooling replaces last-hidden-state.
- **Phase 3 (optional):** full end-to-end PPO live runtime integration.

If asked to add gating or temporal attention while Phase 1 is not yet training cleanly, say so and point at §2.4.

The ablation study (configs **A-H**, §14.4) is what makes this publishable. Design every module so a config flag can disable it — CNN-only, ViT-only, concat fusion, 1-dir cross-attn, bidir-no-gate, +TempAttn, full, and **H, the linear probe (A22)**: no fusion, no recurrence, no attention, just a mean over time and a classifier. H is the floor every frozen-backbone paper is expected to report, and it is easy to forget because §14.4 predates it. Ablation-ability is an architectural constraint, not an afterthought.

## Reproducibility requirements (NFR-07 to NFR-10, "Critical")

These are graded deliverables:

- Seeds fixed and documented across PyTorch, NumPy, and SB3 — the PRD uses `seed: 42` for both MFSTNet and PPO.
- `requirements.txt` committed; the stack must be reproducible from a clean machine. **Docker Compose is specified (NFR.md, PRD §22.3) but not committed:** no compose file exists, so do not tell anyone to run one (D4).
- Raw results committed as CSV, not just summary tables: all 30 RL evaluation runs per method, and all ablation configs.
- Statistics reported as mean ± 95% CI (bootstrap, 10000 resamples), paired t-test at α=0.05, with Cohen's d.

Negative or marginal results get reported honestly and analyzed (§2.5.5) — never quietly dropped or cherry-picked.

## What the paper claims is checked against what the corpus holds

`docs/00-planning/CLAIMS.yaml` holds every scope claim **as the sentence it
would appear as in the paper**, each with a machine-checkable assertion.
`scripts/check_claims.py` runs them and exits 1 on any failing `asserted` claim.

**Two currently fail** (P64), and that is the honest state, not a bug to work
around:

- **domain** — no fold-eligible camera is Indian. The four are three Bangladeshi
  and one British motorway (P58).
- **class_coverage** — HIGH is 0/20/9/1 across folds, and fold 2's MEDIUM is 8
  (P57).

`asserted` blocks, `aspirational` reports, and promoting one is a diff. There is
no override flag: the only ways to make a failing assertion pass are to change
the corpus or change the claim. Before writing anything that depends on a claim
holding, run it.

Camera properties are **declared** in `data/cameras.json`, never inferred from a
filename, and each records how it was determined — `frame` means the footage was
inspected, `filename` means it was not. Unknown is a third answer and counts
toward nothing.

## Two numbering schemes this file leans on constantly

`P` numbers and `S` numbers are cited throughout the docs and throughout this
file, and neither is defined where it is used.

**`P<n>` is a changelog entry in [PRD-CHANGELOG.md](docs/00-planning/PRD-CHANGELOG.md)**,
currently running to P107. It is the defect and amendment journal: what was
believed, what was measured, what changed, and what was rejected along with the
reason. Entries record rejected options on purpose — P42 rejects disabling cuDNN
for the RNN with the measurement that made it unacceptable (66.1 against 5.9
ms/step). When a measurement contradicts the PRD, the fix is a P entry plus a
PRD amendment, not a workaround. Read the P entry before re-deciding something
it already decided against.

**`S<n>` is an implementation step in [BUILD-LOG.md](BUILD-LOG.md)**, S01
through S66. It carries a status (✅ done, 🔵 in progress, ⛔ blocked, ⬜ not
started), an owner, and for anything blocked, **who** it is blocked on and
**what** would unblock it. `scripts/check_build_log.py` checks the board against
what is actually on disk, so the board cannot quietly drift from the repo.

`A<n>` also appears, as in A16, A22, A23, A28, A31. Those are PRD amendment
identifiers, cited the same way requirement IDs are.

## Current blockers, and what they gate

- **S19 is ⛔ blocked on the guide since 2026-08-22**, reply due 08-29, which has passed. The memo is [MEMO-2026-08-22-part-b.md](docs/00-planning/MEMO-2026-08-22-part-b.md). It blocks the *detection* dataset, not the model track — BUILD-LOG says so explicitly, so do not treat it as a reason MFSTNet work is stalled. The substance: one campus location is one camera, so ADR-019 cannot score it, which is why the ask changed to a six-viewpoint evaluation set.
- **The `surrogate` PPO arm is not implemented (P52).** `--arm surrogate` and `--arm no-forecast` build the same environment today. Any result that distinguishes them is wrong, and ADR-021 is the plan for fixing it.
- **`scripts/make_paper_tables.py` is withheld while `check_claims.py` is red.** That is by design and not a bug to route around: two asserted claims fail, so the tables do not generate.
- **`check_claims.py` does not run in CI.** `.github/workflows/tests.yml` has a `fast` job and a `model` job, and neither invokes it. The claims gate is real but currently depends on someone running it, so run it before writing anything that assumes a claim holds.



## Numbers to take from the PRD, never to re-derive

Take these from the PRD rather than re-deriving. MFSTNet (§8.2, §8.4): `d_model=256`, `T=60` timesteps at 5s intervals, prediction horizon 12 steps (60s), BiLSTM 2 layers hidden=128 bidirectional, temporal attn 2 layers / 4 heads, AdamW `lr=1e-4` `wd=1e-4`, CosineAnnealingLR, 100 epochs, patience 15, batch 32, CrossEntropyLoss with inverse-frequency class weights, backbones frozen until epoch 30, split 60/20/20. Note the dataset split for *detection* is 70/15/15 stratified (FR-D05) — different number, different purpose.

PPO (§13.1): `lr=3e-4`, `n_steps=2048`, `batch_size=64`, `gamma=0.99`, `gae_lambda=0.95`, `clip_range=0.2`, `ent_coef=0.01`, 500K timesteps. Action space is 12 discrete (NS/EW × 10/20/30/45/60/90s green).

Latency budgets: YOLOv8 ≥10 fps on Jetson Nano; MFSTNet ≤150ms on server CPU via ONNX; PPO decision ≤50ms; MQTT ≤200ms; dashboard refresh ≤2s.

## Layout

PRD §22.3 defines the target repo structure, and it exists on disk. Two
directories the PRD does not mention carry real weight: `contracts/` holds the
MQTT topic and payload definitions, and `experiments/results/` holds the
committed CSVs that are graded deliverables.

```
indiatrafficnet/  detection/  mfstnet/{encoders,fusion,temporal,heads,configs}
simulation/  server/  dashboard/  edge/  contracts/  experiments/results/
scripts/  tests/  notebooks/  models/ (Git LFS)
```

Config lives in YAML (`mfstnet/configs/mfstnet_config.yaml`, `simulation/configs/ppo_config.yaml`) — hyperparameters belong there, not hardcoded in training scripts, because the ablation harness drives configs.

Training runs **locally on the RTX 4050** (ADR-005), not Colab. Measured
2026-08-20 on a five-camera pilot and extrapolated to 359 sequences at 100
epochs: the full A-H ablation is **~1.5 h on CUDA against ~12.3 h on CPU**, so
the 60-90h Colab figure in PRD §21 describes an *uncached* run and no longer
applies. `--device` defaults to `auto`. PPO trains on laptop CPU.

Two things that bite here. Torch must be the **cu126** build — `cu121` and
`cu124` no longer carry torch at any version, so the old documented command
silently installed the CPU wheel. And **features stay fp16 all the way to the
device**, widening to fp32 only after the transfer: doing it earlier doubles
what `torch.stack` copies and what crosses the bus, which was half of every
epoch (P35). The widening is exact, so this is a free 2.5× and not a
precision trade. Assume notebook-and-script hybrid workflows, and that model
weights are too large for plain git.

**A cached window must be copied out of the memory map, never viewed** (P55).
`read_window` mmaps the clip and slices it, and `Tensor.to(dtype)` is a *no-op
returning self* when the dtype already matches — so asking for the cache's own
fp16 handed back a view into a mapping nothing kept alive, and training
segfaulted in threads with no Python frame. `copy=True` is load-bearing. Note
the shape of that bug: P29 (mmap) and P35 (fp16 to the device) were each right,
and composed into a use-after-free. If a crash has no Python frame, suspect the
cache before suspecting the GPU.

Training holds **`--micro-batch` windows at once (default 8) and accumulates to
the config's `batch_size`**. `batch_size` is PRD §8.2 and is not negotiable;
residency is not a hyperparameter. The gradient is summed as `loss * windows`
and divided by the windows actually seen — averaging per-micro-batch means
over-weights a short final group and does move the gradient.

## Stack

PyTorch 2.13.0+cu126 · torchvision (ResNet-50) · timm (DINOv2 ViT-S/14, per ADR-007) · Ultralytics YOLOv8 · Stable-Baselines3 2.9.0 · Gymnasium 1.3.0 · SUMO 1.27.1 / TraCI · ONNX Runtime · MLflow + TensorBoard · Python 3.14.4 on this machine · OpenCV · Paho-MQTT / Mosquitto · FastAPI + Pydantic + Uvicorn · **SQLite** · React 18 + Vite + Zustand + Recharts, native WebSocket, CSS Modules, dark-mode-only (`#0D1117` bg, `#6366F1` accent, Inter + JetBrains Mono).

Two entries here used to say something else and the older text still circulates.
The database is **SQLite**, not PostgreSQL 15 + TimescaleDB — ADR-008 dropped
the production data stack. The ViT is **DINOv2 ViT-S/14**, not supervised
ViT-S/16 — ADR-007, and it is why token counts are 257 and must be read from
config. `requirements.txt` is the authority on every pin; prefer it over any
version written in prose, here or in the manual.

Privacy constraint (NFR-13): raw video frames are never transmitted over the network or written to disk — only derived counts and predictions leave the edge device.

## Commands

Everything runs through `./.venv/Scripts/python.exe` on this machine, and every
script takes `--help`. [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup)
has environment setup and the pinned `requirements.txt`.

```bash
python scripts/check_env.py          # BEFORE pip install -r requirements.txt
python -m pytest                     # whole suite (config in pyproject.toml)
python -m pytest tests/test_lanes.py::test_far_points_are_unassigned_not_snapped
python scripts/check_docs.py         # link/claim integrity, stdlib only, runs in CI
python scripts/check_build_log.py    # the status board against what is on disk
python scripts/check_claims.py       # every paper claim against the corpus
python scripts/check_claims.py --protocol headline   # ADR-025 previewed, CLAIMS.yaml untouched
python scripts/check_sources.py      # every data source against the collection gate, per role
python scripts/check_synopsis.py     # both synopses against the Department guideline
python scripts/check_progress_report.py     # the Phase-I progress report against its guideline
python scripts/verify_references.py  # every citation against OpenAlex and arXiv
python scripts/build_review_pptx.py --pdf   # review deck + PDF, from the committed CSVs
python scripts/build_synopsis.py --which all --pdf   # synopsis reports + decks
```

**The synopsis deliverables are generated, never hand-edited.** Identity
(names, roll numbers, mentor, Project Team ID) lives once in
`scripts/synopsis_content.py`, every number in the progress report comes from
`load_facts()` over the committed CSVs, and `scripts/check_synopsis.py` reads
the produced `.docx` — not the source — against the Department guideline: A4,
margins, Times New Roman 12 pt justified at 1.5, the prescribed chapter order,
chapter-wise captions **cited in the text**, chapter-wise equations cited in the
text, and citations matched both ways against the reference list. Editing a
built document in Word is lost on the next build.

**There are three submitted documents, and they answer two different Department
guidelines.** `build_synopsis.py` builds all of them and `--which` selects one:

| `--which` | Document | Guideline | Sections |
|---|---|---|---|
| `docx`, `pptx` | `MFSTNet-Synopsis-Report` | *Synopsis Format 2026-27* | the prescribed nine, with measured results |
| `phase1` | `MFSTNet-Synopsis-Phase1` | same | the same nine, written as of project start |
| `progress1` | `MFSTNet-Phase1-Progress-Report-1` | ***Progress Report – 1*, a different document** | five only: Introduction (nine named parts), Literature Survey, Literature Survey Table, Research Gap, References |

Do not add an Abstract, a methodology chapter, a requirements chapter or a
conclusion to the progress report — its guideline prescribes five sections and
`check_progress_report.py` fails the build if a tenth appears. Its comparative
table must hold **25 to 30 papers**; the bound is asserted in
`phase1_progress_content.py` and checked again against the rendered table.

**Two of the three must never quote a result.** The progress report (`MFSTNet-Phase1-Progress-Report-1.docx`)
and the Phase I proposal (`MFSTNet-Synopsis-Phase1.docx`, plus its deck) are
inception documents — the idea, the alternatives weighed, the plan, the targets
set in advance. That separation is structural, not editorial:
`scripts/synopsis_phase1_content.py` and `scripts/phase1_progress_content.py`
have no import path to `load_facts()`, and `build_synopsis.py` does not load the
facts at all for `--which phase1` or `--which progress1`. Do not add one. The
progress report's checker also refuses any four-decimal number in its prose,
which is how this project formats a measurement. A target in an inception
document is a target, and if the eventual measurement misses it, the progress
report says so with the measured value rather than the proposal being quietly
restated.

**Citations are fetched, never typed.** `docs/00-planning/BIBLIOGRAPHY.md`
records that most of its entries were once ⚠️ "named from general knowledge,
not retrieved", and sets the rule that nothing in that state enters a reference
list. A 30-row comparative table is where that rule breaks first, so
`scripts/verify_references.py` queries OpenAlex (and arXiv for the two
preprints OpenAlex does not hold at their publication year), **refuses to record
a result whose title or year does not match the expectation**, and writes
`data/references.json`. The report's reference list and its table's author, year
and title columns are generated from that file. Two consequences worth knowing
before editing: the script is **incremental** — it queries only keys not already
recorded, because OpenAlex answers `429` when all 34 are re-queried — and when a
record disagrees with the expectation, **correct the expectation from the
record, never the record from the expectation**. The 🔗 mark in BIBLIOGRAPHY.md
means the bibliographic record was retrieved; it does **not** mean anyone read
the paper, and a number quoted from a work still needs ✅.

**Slide geometry is computed, never estimated, and the build now enforces it.**
`Deck.panel` in `scripts/build_review_pptx.py` draws its box at the height it
is handed and lays the rows out from the top regardless, so a height guessed by
eye fails in one direction only: the last row is clipped and the footnote is
drawn *outside* the box over whatever comes next. Size every panel with
`panel_height(items, width, footnote)` from `scripts/build_synopsis_pptx.py` —
**and pass the footnote to both**, which is the trap: the argument is optional,
and two Phase I slides shipped mis-sized because it went to `panel` and not to
`panel_height`. `panel` now raises with the shortfall in inches rather than
drawing the overflow, `panel_height` raises on a detail row that would wrap
(no height fixes that — only a shorter string), and the measurements live once
in `build_review_pptx.py` beside the code that advances by them.
`tests/test_deck_geometry.py` pins both refusals and builds both decks, so
every panel in them is checked by `python -m pytest tests/test_deck_geometry.py`.

Three more traps in the same family, all found by looking at a rendered slide
and all now build failures:

- **`Deck.content` takes its headline as a two-part sequence**, the plain
  opening and the accented remainder — not a sentence. A bare string is
  subscriptable, so passing one rendered its first two characters as the whole
  headline: "Four settled bodies of work" became "Fo" on every slide of a
  deck's first build. `content` now raises on a string.
- **`Deck.table` draws each cell into a fixed box and will not grow it**, and
  **defaults the cell font to `MONO`** — so prose columns must pass
  `{"font": BODY}`. Size cells against the measured advances, and note the
  divisor: `MONO_ADVANCE` and `BODY_ADVANCE` were measured **at 9.5 pt**, so a
  per-point figure is `advance / 9.5`. Dividing by 11, which one deck does,
  understates the advance by about 16% and a cell that "fits" still wraps onto
  the row below. Allow for the text box's own 0.05 in internal margins too.
- **Lay a variable-height list out by flowing it, not at a fixed pitch.** The
  reference slide positioned 39 IEEE entries 0.255 in apart, and every entry
  that wrapped to three lines was drawn over the next one. It now advances by
  each entry's own height and raises when a column overruns the slide — which
  is what established that 39 entries need two slides rather than a smaller
  font.

**Python 3.12 is the supported version** (D4). CI's `fast` job runs it, and
README.md and Execution Manual Part 0 both say it; the clean-environment check
of 2026-10-21 passed on it. The venv on this machine is **3.14.4**, which also
passed, and `pyproject.toml` still says `requires-python = ">=3.10"`. Install
torch with the `cu126` command in
[Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup):
`cu121` carries no torch at any version (P32). `requirements.txt` is the
authority on every pin.

**A broken torch raises `OSError`, not `ImportError`, and three scripts had to
learn that.** A torch whose DLLs fail to initialise is *installed*, so the
import raises `OSError: [WinError 1114]` rather than `ImportError` — which is
what a mismatched Visual C++ runtime produces. **The venv on this machine was in
that state and is not any more**: `check_env.py` now reports
`PyTorch -- 2.13.0+cu126` with CUDA on the RTX 4050, and the torch-importing
suites collect normally. The code changes stay, because the failure mode does
not go away by being fixed once: `check_env.py` names it as a `FAIL` in both
`check_torch()` and the package loop instead of letting a raw traceback escape
the pre-flight, and `build_review_pptx.py`'s `render_images()` degrades to its
"image slides will say so" path instead of taking a twenty-slide deck down over
three optional illustrations. Anywhere else that guards an optional torch import
with `except ImportError` has the same latent bug.

**The pre-flight's current blocker is disk, not torch.** `check_env.py` reports
`Free disk -- 25 GB` against the ~60 GB that IDD plus the feature cache needs,
and calls it blocking. That gates the detection track (ADR-001's Week 2
bootstrap), not the corpus or the documents.

**The set of tests that pass without torch locally is not the set CI skips.**
CI's `fast` job ignores exactly five files (`test_encoders.py`, `test_model.py`,
`test_cache.py`, `test_sumo_network.py`, `test_simulation.py`) and gets away with
eleven more because torch is *absent* there and `importorskip` skips them. A
torch that is *present but broken* raises `OSError`, which `importorskip` does
not catch — so while this venv was in that state, those eleven became collection
errors and `pytest` reported 14 errors before running anything. Collection
errors are not test failures; do not read them as a regression, and check
`check_env.py` before investigating one.

The `fast` job also installs **python-pptx** and builds all three submitted
documents into `$RUNNER_TEMP`, then runs `check_synopsis.py` and
`check_progress_report.py` against them. Both are there for the reason the
job's own header gives for torch: `tests/test_deck_geometry.py` and
`tests/test_progress_report.py` guard their geometry with
`importorskip("pptx")`, so a runner without it skips them and goes green over
the guards.

### The corpus pipeline, in order

Lane geometry is per camera and hand-placed — automatic centres move 0.164 of
frame width when the detector changes (P23), so they are never used unreviewed.

```bash
python scripts/triage_footage.py                       # which clips qualify at all
python scripts/survey_all.py --lanes 4 --imgsz 992     --weights models/external/best_xl_ITD_v1.2.pt --out data/lanes_k4
# then place centres by hand: docs/demo/place_lanes.html -> JSON
python scripts/import_lane_centres.py --json lane_centres.json --out data/lanes_reviewed
python scripts/corpus_yield.py                         # segments per step_s, the A28 evidence
python scripts/build_corpus.py --clips "D:/traffic dataset"     --lanes-dir data/lanes_reviewed --step-s 2 --imgsz 992 --out data/corpus
python scripts/relabel_corpus.py --corpus data/corpus --low-max 8 --med-max 20
python scripts/audit_corpus.py --corpus data/corpus            # exits 1 if anything is wrong
python scripts/build_cache.py --corpus data/corpus --clips data/_corpus_clips --cache data/cache_corpus --device cuda
python scripts/resplit_corpus.py --corpus data/corpus --clips data/_corpus_clips --fold 0 --out data/corpus_loco/fold0 --list
# --domain foreign|india|mixed (ADR-025); mixed is the default and reproduces every committed fold
```

`counts.csv` is threshold-independent, so `relabel_corpus.py` re-derives labels
in seconds without re-running the detector. A threshold decision is a config
change, never a reason to delay building the corpus. The same holds for the
**split**: it depends on which camera a window came from and on nothing the
detector produced, so `resplit_corpus.py` re-cuts one in about a second.

**The split is not 60/20/20 any more (ADR-019).** Seven cameras hashed into
three buckets put a UK motorway alone in `test` and a camera with no HIGH
window alone in `val`, and the assignment is a function of the filename.
MFSTNet is evaluated by **leave-one-camera-out** over the cameras contributing
at least 10 windows — four folds today — with the other three always in train.
`--list` prints the fold table. Detection is unaffected and stays 70/15/15
(FR-D05).

### Training and the ablation

```bash
python scripts/overfit_check.py --all                  # plumbing: must reach ~0 loss
python scripts/train_mfstnet.py --corpus data/corpus --cache data/cache --config G
# --save-checkpoint DIR keeps the selected model; --init-from PT fine-tunes from one (P87)
python scripts/train_mfstnet.py --corpus data/corpus_loco/fold0 --cache data/cache_corpus --ablation
python scripts/run_loco.py --corpus data/corpus --clips data/_corpus_clips --cache data/cache_corpus --ablation --device cuda --seeds 42 1 7 13 21
python scripts/run_loco.py --restat                    # rebuild the summary, retrain nothing
# --device auto|cpu|cuda (default auto). Results record which one ran.
python scripts/train_baselines.py --corpus data/corpus_loco/fold0 --seed 42 --out experiments/results/baselines_loco/fold0_seed42.csv
python scripts/train_baselines.py --corpus data/corpus --restat experiments/results/baselines_loco   # the aggregate
python scripts/make_paper_tables.py --which all       # withheld while check_claims is red
python scripts/select_checkpoint.py                  # S61: pre-registered rule, validation columns only
python scripts/export_checkpoint.py --checkpoint PT --cache data/cache_corpus   # trained ONNX, proven against committed predictions
python scripts/verify_edge.py --graph ONNX --lanes lane_0=N lane_1=S lane_2=E lane_3=W --device cuda   # real video, edge, server; ADR-026
python scripts/benchmark_decode.py run --work DIR --graph ONNX   # decode + pipeline at camera resolution; P89
python scripts/benchmark_live.py run --graph ONNX --seconds 600   # S65; camera URL from STMS_CAMERA_URL only
python scripts/backup_models.py pack --dest E:/backup   # weights are gitignored; verify against the committed manifest
AMQTT_PYTHON=<python with amqtt> python -m pytest tests/test_mqtt_live.py   # real broker, edge to server
```

`run_loco.py` is the one to run for a reportable number: it trains every fold
and writes `experiments/results/loco_summary.csv` — **mean and bootstrap 95% CI
across folds**, generated from the per-fold CSVs by a committed script, never
transcribed (NFR-09/10). Quote the fold mean, not a single fold, and quote
`n_folds` beside it: an interval over four points is not an interval over
thirty. Every fold's test split is one camera, which is the effective n.

**Always pass `--seeds 42 1 7 13 21`** (PRD §14.4). A one-seed table ranks
initialisations, not architectures: on fold 0 config E moved 0.4469 / 0.2385 /
0.2046 across three seeds while config B moved 0.039, and at seed 42 the two
were identical to four decimal places (P54). `run_loco.py` reports
`macro_f1_seed_spread` — movement on *one* fold from the seed alone — and warns
when it exceeds the closest gap between two configs, because those two are then
not separated. It runs **one config per process**: eight models built back to
back exhausted a 6 GB card, and a fresh interpreter is the only thing that
reliably hands the whole allocation back.

**The seed list is specified in three places and they do not agree, which is a
defect under this repo's own config-not-code rule.** `mfstnet/configs/spec.yaml`
declares `ablation.seeds: [42, 43, 44, 45, 46]` citing A23.
`scripts/run_loco.py` hardcodes `DEFAULT_SEEDS = (42, 1, 7, 13, 21)` and then
defaults the `--seeds` argument to `[42]`, so the constant it defines is not the
value it uses. The instruction above is a third value. Until one wins, pass the
seeds explicitly on every reportable run and record which list produced the
CSV — and do not "fix" this by editing whichever file is nearest. The seed list
is a config value, so `spec.yaml` should own it and `run_loco.py` should read
it; changing the published list is a PRD amendment with a changelog entry, not
a code edit.

`--out` defaults to `experiments/results/ablation.csv`, a graded deliverable
(NFR-09/10). A short run will refuse to overwrite results recorded from a
longer one — send verification runs elsewhere with `--out`, or pass `--force`
if replacing is what you mean. **PPO checkpoints have the same rule** (P47): a
`--smoke` run will not overwrite a 500,000-step one, and every `.zip` carries a
`.provenance.json` recording its length and device.

### Simulation and benchmark

```bash
python scripts/corpus_gap.py                                    # how far the corpus is from enough
python scripts/camera_audit.py                                  # what each camera contributes, and the M6 ablation
python scripts/fold_table.py                                    # fold composition behind every aggregate
python scripts/discipline_pilot.py --seeds 42 1 7 13 21         # ADR-024 manipulation check
python scripts/build_sumo_network.py
python scripts/build_sumo_demand.py --regime saturated          # light|saturated|oversaturated
python scripts/train_ppo.py --arm surrogate --regime saturated  # arms: no-forecast|surrogate|mfstnet
python scripts/benchmark.py --seeds 30                          # --restat re-derives stats from CSV
python scripts/webster_sweep.py                                 # ADR-012 saturation flow
```

### Detector work

```bash
python scripts/prepare_idd.py && python scripts/prepare_bmd45.py
python scripts/build_joint_dataset.py
python scripts/verify_detector_metrics.py --weights <pt>        # maps metrics to the RIGHT classes
python scripts/verify_counting.py                               # counting != detection accuracy
python scripts/evaluate_detector_arms.py --weights <pt>         # A31 viewpoint arms
```

ONNX export, the FastAPI control server and the edge node all exist —
`server/app.py`, `server/safety.py`, `edge/node.py`, `contracts/mqtt.py`. The
deployed edge path runs as `python -m edge.run` (D3; `--help` lists the flags,
and `--source camera` reads the stream URL from `STMS_CAMERA_URL`).

### Dashboard status

**Built:** a read-only React dashboard (`dashboard/`), committed as `1102932`,
to ADR-008's descoped shape and ADR-014's two-panel rule.

- **Live forecasts:** the ridge next-minute vehicle count and the persistence
  congestion class, displayed in separate, validated panels.
- **Historical results:** evaluation evidence loaded from committed result
  files through `GET /evidence`, explicitly not a live performance guarantee.
- **Safety boundary:** the dashboard is GET-only, with no signal-control
  integration. It shows a missing approach as missing, never as LOW, and its
  banner states the controller's encoding since P110 (0.0 = no forecast,
  LOW = 1/3). P97a Part 2, the controller's behaviour under forecast faults,
  remains deferred; the dashboard does not address it.
- **Refresh:** HTTP polling every 2 seconds.
- **Validation:** browser-checked at desktop and phone widths, including a
  real-data end-to-end test, stale responses, missing approaches and API error
  states. `cd dashboard && npm test` runs its tests.

**Not implemented:** WebSocket updates, charts, the ADR-014 agreement ribbon,
the detection overlay and authentication. Dashboard tests do run in CI: the
`dashboard (vitest + build)` job runs `npm test`.

**Forecasting roles:** ADR-027 remains authoritative. MFSTNet's edge path
remains intact, and vision claim C2 remains open. The end-to-end test shows
that forecasts are transported and displayed correctly for the cases tested.
It does **not** show that they are safe to use for adaptive signal control.

## Working conventions

- **Config, not code.** Hyperparameters live in YAML (`mfstnet/configs/`, `simulation/configs/`) because the ablation harness drives configs (NFR-16). A numeric literal in a training script that duplicates a config value is a defect.
- **Every module disableable by flag** (NFR-15). The 7-config ablation must run from config alone, with no code edit between configs.
- **`set_seed(42)` before building any model**, seeding Python/NumPy/PyTorch/SB3 (NFR-07). Verify determinism by running one epoch twice.
- **Result CSVs are written by the training script**, never transcribed. Paper tables are generated from committed CSVs by a committed script (NFR-09/10, BR-18).
- **The 17-dim PPO state vector is a contract** (PRD §13.1 as amended by A16 and ADR-020, FR-M14). A16 removed `mfst_gate_mean`: SUMO has no camera, so a feature that is always zero in training and non-zero in deployment is worse than absent.
  - **Where the layout lives:** once, in `mfstnet/configs/spec.yaml`.
  - **When a forecast is unavailable:** apply the spec's `forecast_unavailable` operation (class slots read absent, age reads 1.0), only through `simulation.forecast_state.forecast_slots`. **Never encode a missing approach or a missing count as a value** (P97a, P109, P110), and never shorten the vector.
  - **When a policy may use forecasts:** only through `ForecastGate`. `simulation/contract.py` hashes the layout into every checkpoint sidecar, because a permuted index keeps the shape and changes the meaning (P53). **Note P52: the `surrogate` arm is not implemented** — it and `no-forecast` are currently the same environment.
- **MQTT QoS differs per topic and is part of the contract** (PRD §17.1): emergency is QoS 2, counts and commands QoS 1, predictions and heartbeat QoS 0.
- **`contracts/mqtt.py` is the only place a topic or payload is defined.** QoS is attached to the topic there, not accepted as an argument at the call site — a caller that can pass its own QoS can silently downgrade emergency traffic, and the type system should not allow it. Import the topic; never format one from a string.
- **`use_utf8()` from `scripts/console.py` goes at the top of any script that prints a path.** Forty-seven of fifty-seven scripts call it. It exists because a cache build died on `UnicodeEncodeError: 'charmap' codec can't encode character '।'` — the Devanagari danda in a Dhaka filename — and lost twenty minutes of GPU work to a progress line. Console encoding is not cosmetic on this machine.
- **`resolve_device()` from `scripts/device.py` and `set_seed()` from `scripts/seed.py` are the only ways to get a device or seed the world** (P32, NFR-07). A script that calls `torch.cuda.is_available()` itself will not honour `--device`, and one that seeds inline will miss SB3.
- **Safety rules live outside the transport that carries them.** `server/safety.py` holds `SafetyLimits` (`min_green_s` 10, `max_green_s` 90, `all_red_s` 3, `emergency_response_s` 3, `mqtt_timeout_s` 10), `Decision`, and `SignalGuard`, and contains no HTTP whatsoever; `simulation/runner.py` clamps with the same limits; `edge/node.py` takes a `Transport` protocol so the FR-A06 fallback is testable with no broker running. A clamp that only exists in the HTTP handler is not a clamp.
- **New provenance facts go in the sidecar, never as new CSV columns.** `experiments/provenance.py::write_sidecar` records device, config and run length beside a result or a checkpoint (P39, P47). Deliberately no timestamp and no username. The 27 CSVs that predate it get no retroactive sidecar — absence there means "written before the rule", not "unknown".
