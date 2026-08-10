# Training Guide

| | |
|---|---|
| **Date** | 2026-08-08 |
| **Audience** | R2 (Model Lead), R1 (Detection) |
| **Decisions** | [ADR-005](../00-planning/decisions/ADR-005-local-first-training.md) local-first + caching · [ADR-007](../00-planning/decisions/ADR-007-backbones-and-training-recipe.md) backbones + recipe |

Answers three questions: **which models**, **where and how to train them**, and **what to do about
precision and quantisation**.

---

## 1. Which models, and what each one is for

| Component | Choice | What it contributes | Trained? |
|---|---|---|---|
| Detector | **YOLOv8s** (Ultralytics) | Per-lane vehicle counts. Also generates corpus labels (PRD §8.6) | **Fine-tuned** |
| CNN branch | **ResNet-50**, ImageNet | Local texture and vehicle-shape detail. The "what is here" signal | **Frozen** |
| ViT branch | **DINOv2 ViT-S/14** | Global scene context and spatial layout. The "how is the scene arranged" signal | **Frozen** |
| Fusion | Bidirectional cross-attention + gate | Lets each branch query the other; the gate weighs them per scene | Trained (~1.5M) |
| Temporal | BiLSTM (+ optional self-attention) | Queue build-up and arrival dynamics over 5 minutes | Trained (~1.3M) |
| Heads | Per-lane congestion, PPO embedding, emergency | Task outputs | Trained (~0.3M) |
| Policy | **PPO** (Stable-Baselines3) | Signal timing decisions | Trained on CPU |

Only ~4.1M parameters are trainable. **This is a small model.** The compute problem is not the
model — it is pushing 1,920 frames per batch through two frozen backbones, which §3 removes.

### Why DINOv2 rather than supervised ViT-S/16

The backbones never update, so their representation quality is the entire contribution. DINOv2's
self-supervised features are substantially stronger than ImageNet-supervised features in exactly this
frozen, small-data regime. Per ADR-007 the supervised checkpoint is retained as ablation arm BB-1, so
you report the PRD's original configuration alongside the improved one.

Watch the geometry: patch-14 at 224×224 gives 256 patch tokens + CLS, not 196 + 1. Read the token
count from config (NFR-16), never hardcode it.

---

## 2. Where to train

| Job | Machine | Why |
|---|---|---|
| Feature extraction (one-off per backbone) | Laptop RTX 4050 | GPU, batch 1–4 sequences |
| MFSTNet training + all ablations | Laptop RTX 4050, **cached features** | Seconds per epoch |
| YOLOv8s fine-tuning | Laptop RTX 4050 | Batch 8–16 at 640 fits 6 GB |
| PPO + 120-episode benchmark | Laptop **CPU** | SUMO is single-threaded; run seeds in parallel across 14 cores |
| Overflow, parallel arms | Colab free tier | Same configs, unchanged |

```powershell
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
python -c "import torch;print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Plugged in, high-performance power plan, hard surface. Sustained load throttles a laptop — that costs
throughput, never correctness.

---

## 3. The feature cache — the single most important technique here

At `batch_size: 32`, `T: 60`, one uncached step pushes **1,920 frames** through both backbones. That
exceeds 6 GB and is tight even on a 16 GB T4. It is an architecture property, not a hardware limit.

The backbones are frozen, so they emit identical features every epoch. Compute once:

```
Pass 1 (per backbone, once):  unique frame → ResNet-50 → [2048,7,7] fp16  (~200 KB)
                                           → DINOv2    → [257,384] fp16   (~200 KB)
Pass 2 (every run):           cached features → projections → fusion → BiLSTM → heads
```

Cache **unique frames, not sequences** — at a 30 s stride consecutive sequences share 54 of 60
frames. Ten hours of footage ≈ 7,200 unique frames ≈ 3 GB.

| | Uncached | Cached |
|---|---|---|
| Epoch | Minutes | Seconds |
| VRAM at batch 32 | Does not fit | Comfortable |
| 7-config ablation | 60–90 h | **Hours** — one cache serves all seven |
| Backbone ablation (3 arms) | Prohibitive | One extra pass per backbone |

This is what makes PRD R6's 50-epoch mitigation unnecessary and ADR-007's backbone ablation
affordable.

> **The failure mode.** A cache is invalidated by any change to backbone weights, input resize, or
> normalisation. A stale cache produces results that look completely normal and are wrong. Store
> `preprocessing_hash` and the git commit in the manifest; **assert on load and raise, do not warn.**

**Per-lane ROI pooling requires spatial structure.** Cache the 7×7 grid and the full token sequence,
never a pooled vector — see the corpus spec §6.

---

## 4. Precision and speed during training

| Technique | Verdict | Notes |
|---|---|---|
| **AMP, bf16** (`torch.autocast`) | **Use always** | ~2× on Ada. bf16 avoids fp16's loss-scaling fragility |
| Gradient accumulation | Uncached runs only | Batch 4 × 8 steps = effective 32 |
| `torch.compile` | Benchmark, don't assume | Windows support has historically lagged. If it fails, WSL2 or skip — it is an optimisation |
| Gradient checkpointing | Not needed | Caching already removed memory pressure |
| Multi-GPU | N/A | One GPU |

```python
scaler_free = torch.autocast(device_type="cuda", dtype=torch.bfloat16)
with scaler_free:
    out = model(feats)
    loss = criterion(out, labels)
loss.backward()          # bf16 needs no GradScaler
```

**Quantisation is not a training technique.** Train in bf16. Quantise at export (§6). Confusing the
two is common and leads people to quantise during training for no benefit.

---

## 5. Recipe

```yaml
optimizer:   AdamW            # PRD §8.4
lr:          1.0e-4
weight_decay: 1.0e-4
scheduler:   CosineAnnealingLR
epochs:      100
patience:    15
batch_size:  32               # cached; 4 + accum 8 uncached
loss:        CrossEntropyLoss  # inverse-frequency weights; focal loss as one ablation arm
seed:        42
precision:   bf16
```

**Order of work** (PRD §2.4 — non-negotiable):

1. ResNet-50 encoder → shape test passes
2. DINOv2 encoder → shape test passes
3. Standard cross-attention → assert `Z_A ≠ Z_B`
4. BiLSTM + per-lane ROI-pooled head → `[B,4,3]`
5. **Overfit 10 sequences to ~zero loss** ← never skip
6. Full Phase 1 training → M4
7. Ablation A–E, then backbone arms BB-1..BB-3
8. *Only now* Phase 2: gate, temporal attention, attention pooling

Step 5 is the highest-value hour in the whole schedule. A model that cannot overfit ten sequences has
a bug in the data pipeline, the loss, or the label alignment. Finding it on ten sequences takes
minutes; finding it after a full run takes a day.

### Adapting the backbone — LoRA, not unfreezing

PRD §8.4 sets `unfreeze_epoch: 30`; PRD R4 predicts unfreezing will overfit. Per ADR-007, run **LoRA
(r=8, attention projections)** on the ViT as a separate Week-15 experiment instead, and report all
three arms:

| Arm | Trainable | Cache valid |
|---|---|---|
| Frozen | ~4.1 M | Yes |
| LoRA | ~4.2 M | No |
| Full fine-tune | ~30 M+ | No |

This satisfies PRD §20 L4's promised comparison and turns an expected failure into a result.

---

## 6. Deployment — where quantisation belongs

FR-M13: ≤150 ms on server CPU via ONNX. Try in this order and stop when you hit the target.

**1. Export and measure.**

```python
torch.onnx.export(model.eval(), sample, "mfstnet.onnx",
                  opset_version=17, dynamic_axes={"input": {0: "batch"}})
```

Median of 100 runs after 10 warm-ups. Often sufficient on its own.

**2. Dynamic INT8** — no calibration data needed, typically 2–4× on CPU for transformer-heavy models.

```python
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic("mfstnet.onnx", "mfstnet.int8.onnx", weight_type=QuantType.QInt8)
```

**3. Static INT8** with calibration from the training corpus — only if still short.

> **Report accuracy before and after.** An INT8 model that meets the latency target by losing two F1
> points is a trade-off to state, not a free win. **If a quantised model produces the reported
> latency, the reported accuracy must come from that same model.** Quoting fp32 accuracy beside INT8
> latency is the kind of thing a reviewer catches.

TensorRT is worth it only if a Jetson materialises (ADR-003).

---

## 7. What to watch

| Signal | Healthy | Otherwise |
|---|---|---|
| Overfit-10 loss | → ~0 | **Stop everything.** Pipeline bug |
| Train loss | Decreasing | Check LR, check inputs for NaN |
| Val loss | Falls then flattens | Diverging from train → overfitting; keep backbones frozen (R4) |
| Macro F1 | → ≥0.80 | Check class weights and label balance |
| Per-class recall, HIGH | Rising | A model that never predicts HIGH is useless whatever its accuracy |
| **Gate histogram** | Spread across (0,1) | Collapsed at 0/1 → R5; add gate entropy regularisation |
| **Gate vs. density** | Correlated | This *is* claim C2. If uncorrelated, that is a reportable negative result |

Log the gate from the first Phase 2 run. BR-07, FR-M04, and FR-UI05 all depend on it, and
[RELATED-WORK §3](../00-planning/RELATED-WORK.md) makes the gate analysis your second-strongest
claim.

---

## 8. Cost of every experiment

Zero rupees. Laptop electricity and Colab free tier. Nothing in this guide requires paid compute.
