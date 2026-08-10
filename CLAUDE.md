# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

**No code yet — but a full SDLC documentation suite exists.** Start at [docs/README.md](docs/README.md), which indexes everything and states the reading order. It is now a git repository with Git LFS configured for model weights.

The PRD ([docs/00-planning/PRD.md](docs/00-planning/PRD.md), now v1.1) remains the single source of truth for architecture, requirements (IDs `FR-*`, `NFR-*`), milestones, and acceptance criteria. Before implementing anything, find the governing requirement ID and honor its exact numbers rather than inventing values. When implementation reveals the PRD is wrong, amend the PRD and log it in [PRD-CHANGELOG](docs/00-planning/PRD-CHANGELOG.md) — never work around a PRD statement you believe is incorrect.

Requirement IDs are defined **once**: `BR-*` in the BRD, `FR-*`/`NFR-*` in PRD §9/§10. Every other document cites IDs and never restates requirements in prose. [RTM](docs/01-requirements/RTM.md) is the join table (BR → FR/NFR → DES → TC → M); update it when requirements change.

Documents are delivered in waves (ADR-004). Wave 1 (planning + requirements + manual) is done; SAD/HLD/LLD are due Week 5, STP/STD/UAT Week 11, STR/TIM/SOP Week 16. Missing later-wave documents are scheduled, not overlooked.

Project context: 4th-year B.Tech CSE (ML/AI) major project, 20-week academic timeline, 3-4 member team, ₹0 cash budget, targeting a conference submission (IEEE ITSC / CVIP).

## Read the feasibility audit before planning any work

[docs/00-planning/FEASIBILITY-AUDIT.md](docs/00-planning/FEASIBILITY-AUDIT.md) estimates ~1,200 person-hours of specified work against ~715 hours of realistic team capacity. Its conclusions govern: annotation effort was underestimated by roughly 3×, the dashboard and production stack consume a quarter of the project for almost no assessed value, and the novelty claim must be narrowed (see [RELATED-WORK.md](docs/00-planning/RELATED-WORK.md) — the fusion mechanisms are all published; the gate-as-artifact, camera-only framing, and density-stratified evaluation are what is defensible).

ADR-006 and ADR-008 are **proposed, not accepted** — they change graded requirements and need faculty guide sign-off. Do not implement against them until that happens; do not implement against the superseded plan either without flagging the conflict.

## Decisions that override the original PRD text

Eight ADRs in [docs/00-planning/decisions/](docs/00-planning/decisions/) changed how the project executes. Read them before acting on PRD §8, §12, §15, or §20:

- **ADR-001** — dataset is two-track. YOLOv8 bootstraps on a public Indian dataset from Week 2; IndiaTrafficNet runs in parallel and swaps in at Week 8. Between Weeks 2–8 two sets of detector weights exist, so every experiment must record which it used.
- **ADR-002** — MFSTNet's training corpus is built by auto-labelling real 5-minute video clips with the fine-tuned YOLOv8 (counts → PRD §14.1 thresholds → congestion label at t+60s). The PRD originally had no corpus specification, and §20 L1's claim that MFSTNet trains on SUMO sequences was wrong. **Splits are cut by source clip, never by sequence** — overlapping windows would leak.
- **ADR-003** — the edge node is a team laptop, not a Jetson (₹0 budget). Control logic and the MQTT contract are unchanged. **Every latency figure must state its measurement host**; laptop numbers are labelled proxy measurements.
- **ADR-004** — documents ship in four waves gated on PRD §18 phases.
- **ADR-005** — training is local-first (RTX 4050 laptop) on **cached frozen-backbone features**. At batch 32 × T=60 an uncached step pushes 1,920 frames through both backbones, which does not fit 6GB and is tight even on a T4. Caching collapses the 60–90h ablation to hours. A cache is invalidated by any change to backbone, resize, or normalization — assert the `preprocessing_hash` on load and raise, never warn.
- **ADR-007** — DINOv2 ViT-S/14 replaces supervised ViT-S/16 as the default (frozen backbones mean representation quality is everything); bf16 AMP for training; INT8 ONNX only at export; LoRA instead of `unfreeze_epoch: 30`. Note patch-14 gives 257 tokens, not 197 — read token counts from config.
- **ADR-006 / ADR-008 (proposed)** — curate-then-collect dataset, and prototype descoping. Both blocked on faculty sign-off.

Also fixed in the corpus spec: PRD §8.1 cannot produce four different lane predictions as written (global pooling then one shared head applied 4×) — **per-lane ROI pooling** replaces global pooling, which is why the feature cache must preserve spatial structure. And the evaluation was circular: labels derive from detector counts and three PRD §14.3 baselines also consume detector counts, so the **test split is human-verified** while train/val stay auto-labelled.

## What is being built

**MFSTNet** — a multimodal traffic-congestion predictor plus an RL signal controller, with an edge-to-server prototype around them. Four subsystems that are developed largely independently and only integrate late (Weeks 17-19):

1. **IndiaTrafficNet** — self-collected, self-annotated dataset (12,000+ frames, 8 India-specific classes incl. auto-rickshaw, e-rickshaw, cattle) → fine-tunes YOLOv8s for edge detection.
2. **MFSTNet** — the model. ResNet-50 + ViT-Small/16 (both frozen) → gated bidirectional cross-attention → BiLSTM → temporal self-attention → attention pooling → per-lane congestion head (LOW/MED/HIGH, 60s ahead).
3. **PPO agent** — Stable-Baselines3 PPO on a SUMO 4-way intersection via TraCI. Consumes MFSTNet predictions as auxiliary state.
4. **Prototype** — Jetson Nano (YOLOv8 + GPIO LEDs) ⇄ MQTT ⇄ FastAPI server (PPO + ONNX MFSTNet) ⇄ React dashboard.

### Data flow that spans components

The coupling that is easy to miss: **MFSTNet's output is not just a prediction, it is part of the PPO state vector.** The 17-dim state (PRD §13.1) includes 4 per-lane MFSTNet class predictions plus `mfst_gate_mean`. Changing MFSTNet's output shape or normalization invalidates trained PPO checkpoints. The same predictions also flow to the dashboard over MQTT topic `stms/{intersection_id}/congestion/prediction`.

Two fallback paths are required behavior, not nice-to-haves (PRD §7.2, FR-A06): if MFSTNet inference fails, PPO must run on raw counts alone; if MQTT drops >10s, the Jetson switches to a locally-embedded Webster controller.

### The gate

`g = sigmoid(Linear([Z_A; Z_B]))`, `F_fused = g·Z_A + (1-g)·Z_B` where `Z_A` is CNN-queries-ViT and `Z_B` is ViT-queries-CNN. The gate value is a research artifact, not an internal detail — it is logged, tracked on the dashboard (FR-UI05), and analyzed in the paper. Always expose it from the forward pass; never discard it.

## Build order is non-negotiable

PRD §2.4 sets a strict priority order and it exists to prevent a known failure mode (over-engineering the architecture, under-delivering experiments). Do not implement Phase 2 features before Phase 1 converges:

- **Phase 1 (mandatory):** CNN + ViT + *standard* cross-attention + BiLSTM → congestion head.
- **Phase 2 (stretch):** gating replaces standard cross-attn; temporal self-attention on BiLSTM outputs; attention pooling replaces last-hidden-state.
- **Phase 3 (optional):** full end-to-end PPO live runtime integration.

If asked to add gating or temporal attention while Phase 1 is not yet training cleanly, say so and point at §2.4.

The ablation study (configs A-G, §14.4) is what makes this publishable. Design every module so a config flag can disable it — CNN-only, ViT-only, concat fusion, 1-dir cross-attn, bidir-no-gate, +TempAttn, full. Ablation-ability is an architectural constraint, not an afterthought.

## Reproducibility requirements (NFR-07 to NFR-10, "Critical")

These are graded deliverables:

- Seeds fixed and documented across PyTorch, NumPy, and SB3 — the PRD uses `seed: 42` for both MFSTNet and PPO.
- `requirements.txt` + Docker Compose committed; the stack must be reproducible from a clean machine.
- Raw results committed as CSV, not just summary tables: all 30 RL evaluation runs per method, and all ablation configs.
- Statistics reported as mean ± 95% CI (bootstrap, 10000 resamples), paired t-test at α=0.05, with Cohen's d.

Negative or marginal results get reported honestly and analyzed (§2.5.5) — never quietly dropped or cherry-picked.

## Key specified values

Take these from the PRD rather than re-deriving. MFSTNet (§8.2, §8.4): `d_model=256`, `T=60` timesteps at 5s intervals, prediction horizon 12 steps (60s), BiLSTM 2 layers hidden=128 bidirectional, temporal attn 2 layers / 4 heads, AdamW `lr=1e-4` `wd=1e-4`, CosineAnnealingLR, 100 epochs, patience 15, batch 32, CrossEntropyLoss with inverse-frequency class weights, backbones frozen until epoch 30, split 60/20/20. Note the dataset split for *detection* is 70/15/15 stratified (FR-D05) — different number, different purpose.

PPO (§13.1): `lr=3e-4`, `n_steps=2048`, `batch_size=64`, `gamma=0.99`, `gae_lambda=0.95`, `clip_range=0.2`, `ent_coef=0.01`, 500K timesteps. Action space is 12 discrete (NS/EW × 10/20/30/45/60/90s green).

Latency budgets: YOLOv8 ≥10 fps on Jetson Nano; MFSTNet ≤150ms on server CPU via ONNX; PPO decision ≤50ms; MQTT ≤200ms; dashboard refresh ≤2s.

## Planned layout

PRD §22.3 defines the target repo structure. Create directories to match it as work starts:

```
indiatrafficnet/  detection/  mfstnet/{encoders,fusion,temporal,heads,configs}
simulation/  server/  dashboard/  edge/  experiments/results/  models/ (Git LFS)
```

Config lives in YAML (`mfstnet/configs/mfstnet_config.yaml`, `simulation/configs/ppo_config.yaml`) — hyperparameters belong there, not hardcoded in training scripts, because the ablation harness drives configs.

Training runs on Google Colab T4 (MFSTNet ~10-16h; ablation 60-90h, parallelized); PPO trains on laptop CPU. Assume notebook-and-script hybrid workflows, and that model weights are too large for plain git.

## Stack

PyTorch 2.x · torchvision (ResNet-50) · timm (ViT-Small/16) · Ultralytics YOLOv8 · Stable-Baselines3 · SUMO 1.19+ / TraCI · ONNX Runtime · MLflow + TensorBoard · Python 3.10+ · OpenCV · Paho-MQTT / Mosquitto · FastAPI · PostgreSQL 15 + TimescaleDB · React 18 + Vite + Zustand + Recharts, native WebSocket, CSS Modules, dark-mode-only (`#0D1117` bg, `#6366F1` accent, Inter + JetBrains Mono).

Privacy constraint (NFR-13): raw video frames are never transmitted over the network or written to disk — only derived counts and predictions leave the edge device.

## Commands

None exist yet. As tooling lands, replace this section with the real invocations (training, ablation, ONNX export, SUMO benchmark, backend, dashboard, and how to run a single test). [Execution Manual Part 0](docs/90-manual/EXECUTION_MANUAL.md#part-0--setup) has the environment setup and the pinned `requirements.txt` to start from.

## Working conventions

- **Config, not code.** Hyperparameters live in YAML (`mfstnet/configs/`, `simulation/configs/`) because the ablation harness drives configs (NFR-16). A numeric literal in a training script that duplicates a config value is a defect.
- **Every module disableable by flag** (NFR-15). The 7-config ablation must run from config alone, with no code edit between configs.
- **`set_seed(42)` before building any model**, seeding Python/NumPy/PyTorch/SB3 (NFR-07). Verify determinism by running one epoch twice.
- **Result CSVs are written by the training script**, never transcribed. Paper tables are generated from committed CSVs by a committed script (NFR-09/10, BR-18).
- **The 17-dim PPO state vector is a contract** (PRD §13.1, FR-M14). Changing MFSTNet's output shape or normalization invalidates every trained PPO checkpoint. If MFSTNet is unavailable, zero indices 11–15 — never shorten the vector.
- **MQTT QoS differs per topic and is part of the contract** (PRD §17.1): emergency is QoS 2, counts and commands QoS 1, predictions and heartbeat QoS 0.
