# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

**This repository contains no code yet** — only [PRD_MFSTNet_CNN_ViT_BiLSTM_CrossAttention_TrafficManagement_v1.md](PRD_MFSTNet_CNN_ViT_BiLSTM_CrossAttention_TrafficManagement_v1.md), a 1246-line PRD (v1.0, dated 2026-07-31) that fully specifies the system. It is not a git repository.

The PRD is the single source of truth for architecture, requirements (IDs `FR-*`, `NFR-*`, `RG*`, `SG*`), milestones, and acceptance criteria. Before implementing anything, find the governing requirement ID in the PRD and honor its exact numbers (dimensions, thresholds, hyperparameters) rather than inventing values. When implementation reveals the PRD is wrong, update the PRD — §24.3 has a revision history table, and the doc declares itself a living document.

Project context: 4th-year B.Tech CSE (ML/AI) major project, 20-week academic timeline, 3-4 member team, targeting a conference submission (IEEE ITSC / CVIP).

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

None exist yet. As tooling lands, replace this section with the real invocations (training, ablation, ONNX export, SUMO benchmark, backend, dashboard, and how to run a single test).
