# ADR-007 — Backbone Selection and Training Recipe

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-08 |
| **Affects** | PRD §8.2, §8.4, §14.4, §20 L4, §23; FR-M01, FR-M02, FR-M12, FR-M13 |
| **Related** | [ADR-005](ADR-005-local-first-training.md) (feature caching makes this cheap) |

## Context

PRD §8.2 fixes ResNet-50 (ImageNet-supervised) and ViT-Small/16 (ImageNet-supervised via timm), both
**frozen**, with `unfreeze_epoch: 30`.

Two observations follow from the freezing decision that the PRD does not draw.

**Frozen means feature quality is everything.** When a backbone never updates, the only thing it
contributes is the quality of its representation. Every downstream module — projection, fusion,
BiLSTM, head — is working with whatever the backbone hands it. Choosing a backbone is therefore the
single highest-leverage accuracy decision in the model, and the PRD chose 2016-era and
2021-era supervised checkpoints without evaluating alternatives.

**The plan contains a contradiction.** §8.4 unfreezes at epoch 30. PRD R4 predicts that unfreezing
will overfit and prescribes keeping the backbone frozen. The plan schedules an action it expects to
fail.

Separately, ADR-005's feature caching changes the economics: because features are computed once,
**swapping a backbone costs one extra cache pass, not a retraining run.**

## Decision

### 1. Add DINOv2 ViT-S/14 as the primary ViT branch

Replace ImageNet-supervised ViT-Small/16 with **DINOv2 ViT-S/14** (`vit_small_patch14_dinov2` in
timm) as the default, retaining the supervised checkpoint as an ablation arm.

Self-supervised DINOv2 features are markedly stronger than supervised ImageNet features in
frozen-backbone, linear-probe, and small-data regimes — which is exactly this project's setting. PRD
§23 already lists DINOv2 under future scope; this promotes it to the main experiment.

Practical notes: patch size is 14, so a 224×224 input yields 16×16 = 256 patch tokens plus CLS
(vs. 196+1 for patch-16). Token count feeds the cross-attention K/V length and the cache size
estimate in ADR-005; adjust both. Verify the checkpoint loads at 224 rather than its native
resolution before committing to it.

### 2. Backbone ablation as a first-class experiment

| Arm | CNN branch | ViT branch |
|---|---|---|
| BB-1 | ResNet-50 (ImageNet) | ViT-S/16 (ImageNet) — the PRD baseline |
| BB-2 | ResNet-50 (ImageNet) | **DINOv2 ViT-S/14** |
| BB-3 | ConvNeXt-T | DINOv2 ViT-S/14 |

Four cache passes total (three ViT/CNN combinations reuse two CNN caches). Each arm then reruns the
existing config matrix on cached features in minutes.

This table is more publishable than several of configs A–G, because "which frozen representation
matters most for unstructured traffic" is a question the literature has not answered for this domain.

### 3. LoRA instead of full unfreezing

Replace `unfreeze_epoch: 30` with a **late, separate LoRA experiment** on the ViT branch.

Low-rank adaptation injects trainable rank-*r* matrices into attention projections while the base
weights stay frozen, adding roughly 0.1–0.5% extra parameters. It adapts the representation to the
domain while overfitting far less than full fine-tuning on a small dataset — the standard
parameter-efficient-tuning result from the language-model literature, which transfers directly to
vision transformers.

This converts PRD §20 L4's promised frozen-vs-fine-tuned comparison into a three-way result:

| Arm | Trainable params | Cache valid? |
|---|---|---|
| Frozen | ~4.1 M | Yes |
| **LoRA (r=8, attention only)** | ~4.2 M | **No** — backbone weights change |
| Full fine-tune | ~30 M+ | No |

Scheduling: Week 15, after the main results exist. LoRA and full fine-tuning both invalidate the
feature cache and must run the uncached pipeline at batch 4 with gradient accumulation to an
effective 32.

### 4. Training precision and speed

| Technique | Use | Why |
|---|---|---|
| **AMP** — `torch.autocast`, bf16 | Always | ~2× throughput on Ada; bf16 avoids the loss-scaling fragility of fp16 |
| Gradient accumulation | Only for uncached runs | Recovers an effective batch of 32 at batch 4 |
| `torch.compile` | Optional, benchmark first | Real gains, but Windows support has historically lagged. If it fails, use WSL2 or skip it — it is an optimisation, not a requirement |
| Gradient checkpointing | Not needed | Feature caching already removed the memory pressure |

**Quantisation is not a training technique.** It belongs to deployment (§5) and should not be
confused with mixed-precision training. Train in bf16; quantise at export.

### 5. Deployment precision

FR-M13 requires ≤150 ms on server CPU via ONNX. The path, in order of what to try:

1. Export to ONNX, measure. Often sufficient on its own.
2. If not, apply **dynamic INT8 quantisation** (`onnxruntime.quantization.quantize_dynamic`) — it
   quantises weights and computes activations dynamically, needs no calibration data, and typically
   gives 2–4× on CPU for transformer-heavy models.
3. Only if still short, static INT8 with a calibration set from the training corpus.

**Report accuracy before and after quantisation.** An INT8 model that hits the latency target by
losing two F1 points is a trade-off to state, not a free win. If quantisation is used for the
reported latency, the reported accuracy must come from the same quantised model.

### 6. Loss

Keep `CrossEntropyLoss` with inverse-frequency class weights (PRD §8.4) as the default. Add **focal
loss** as one ablation arm — it usually helps when a minority class is both rare and hard, which is
the expected profile of HIGH. One config flag; report both.

## Consequences

**Positive.** DINOv2 is the cheapest accuracy improvement available and directly raises the odds of
clearing M5's macro F1 ≥ 0.80. The backbone ablation is nearly free after ADR-005 and adds a
publishable table. LoRA resolves the §8.4/R4 contradiction and turns an expected failure into a
reportable three-way comparison. bf16 halves training time at no cost.

**Negative.** More experimental arms means more discipline required in experiment records. The
`detector_weights` field already exists; a `backbone_config` field must join it, or the results
become uninterpretable.

**Negative.** DINOv2's patch-14 geometry changes token counts and therefore cache sizes and
cross-attention shapes. Anything that hardcodes 197 tokens breaks. This is a good reason for the
token count to come from the config, not a literal — NFR-16 already requires that.

**Negative.** Deviating from the PRD's stated backbones needs recording. §8.2 is amended rather than
contradicted, and the supervised checkpoint remains as BB-1 so the PRD's original configuration is
still reported.

## Alternatives considered

**Keep ImageNet-supervised backbones only.** Simplest, matches the PRD, one fewer variable. Rejected:
with frozen backbones, this leaves the largest available accuracy gain unclaimed for the sake of not
editing a config.

**CLIP or SigLIP image encoders.** Strong general features and increasingly common. Rejected as a
default — text-aligned representations optimise for semantic matching rather than the dense spatial
detail that per-lane ROI pooling needs. Reasonable as a fourth ablation arm if time allows.

**Mamba / state-space temporal model instead of BiLSTM.** Currently strong on long sequences.
Rejected as scope creep: T=60 is short, the PRD fixes BiLSTM, and PRD §2.4 puts architectural novelty
behind experimental rigour. Note it as future work.

**Quantisation-aware training.** Better INT8 accuracy than post-training quantisation. Rejected —
substantially more complexity for a latency target that dynamic quantisation will almost certainly
meet.
