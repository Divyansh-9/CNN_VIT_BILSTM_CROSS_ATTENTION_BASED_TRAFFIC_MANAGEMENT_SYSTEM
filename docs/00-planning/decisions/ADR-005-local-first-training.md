# ADR-005 — Local-First Training, with Cached Backbone Features

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-07 |
| **Deciders** | Project team |
| **Affects** | PRD §15.2, §8.4, R6; NFR-01; M4, M5, M6, M7 |
| **Related** | [ADR-003](ADR-003-laptop-as-edge.md) (same machine as edge node) |

## Context

PRD §15.2 assumes training happens on Google Colab: YOLOv8s 6–10 h, MFSTNet 10–16 h, and the 7-config
ablation 60–90 h "parallelized." R6 rates ablation overrun **High likelihood** and mitigates it by
cutting to 50 epochs.

Colab free tier imposes constraints the PRD does not account for: sessions terminate after roughly 12
hours, idle sessions are reclaimed, GPU allocation is not guaranteed on any given day, and free Drive
is 15 GB. A 16-hour training run cannot complete in a 12-hour session.

The team has an **Acer Predator Helios 16 — Intel i5-13500HX (14 cores / 20 threads), RTX 4050 Laptop
(6 GB GDDR6, Ada Lovelace)**. This was not known when §15.2 was written.

| | RTX 4050 Laptop | Colab T4 |
|---|---|---|
| FP32 throughput | ~12 TFLOPS | ~8 TFLOPS |
| VRAM | **6 GB** | 16 GB |
| Session limit | None | ~12 h, not guaranteed |
| Availability | Always | Variable |
| Disk | Local, large | 15 GB Drive persistence |

The GPU is faster than a T4 but has 6 GB against 16 GB. The CPU is the more significant asset: 14
cores is well above what §15.2 assumes for PPO.

## The VRAM problem, and what it revealed

At PRD §8.4's `batch_size: 32` with `T: 60`, one MFSTNet batch pushes **1,920 frames** through
ResNet-50 *and* ViT-Small per step. That does not fit in 6 GB. It is also uncomfortable in 16 GB —
this is a constraint of the architecture, not of the laptop.

Examining it surfaced something more useful. **The backbones are frozen** (PRD §8.4,
`freeze_backbone: true`), and PRD R4 recommends keeping them frozen because ViT overfits on a dataset
this size. Frozen backbones produce identical features on every epoch. Recomputing them 100 times is
pure waste — and worse, recomputing them seven times over for the ablation, where configs A–G differ
**only in what happens after the backbones**.

## Decision

**Train locally, on cached backbone features.**

### 1. Precompute and cache

Run every unique frame through ResNet-50 and ViT-Small **once**. Cache the pre-projection outputs;
the trainable linear projections, fusion, temporal stack, and heads then train on cached tensors.

Cache unique *frames*, not sequences. At a 30 s stride, consecutive sequences share 54 of their 60
frames — caching per sequence would store the same frame roughly ten times.

Approximate sizing, to be measured rather than trusted:

| | Per frame (fp16) |
|---|---|
| ResNet-50, 7×7×2048 | ~200 KB |
| ViT-S/16, 197×384 | ~150 KB |
| **Total** | **~350 KB** |

Ten hours of footage at 5 s sampling is ~7,200 unique frames → **~2.5 GB**. Trivial on local disk,
impossible to justify on a 15 GB Drive.

### 2. Consequences for the schedule

Training the trainable ~4.1 M parameters on cached features is a small job. Epochs drop from minutes
to seconds, and VRAM stops being the binding constraint — batch 32 fits comfortably.

**The ablation is the big win.** One feature cache serves all seven configs, because A–G diverge only
downstream of the backbones. R6's 60–90 h estimate collapses to hours, and its 50-epoch mitigation
becomes unnecessary — meaning the ablation runs at the same 100 epochs as the headline model, and the
paper does not have to carry a caveat about it.

### 3. Division of labour

| Work | Where | Why |
|---|---|---|
| MFSTNet training + ablation | **Local** | Cached features; no session limit |
| Feature extraction (one-off) | Local or Colab | Batch of 1–4 sequences; either works |
| YOLOv8 fine-tuning | **Local** | Batch 8–16 at 640 fits in 6 GB; hours, not days |
| PPO training + 30-run benchmark | **Local CPU** | SUMO is single-threaded; 14 cores runs many seeds in parallel |
| Overflow, and a second opinion | Colab | Keep accounts alive as fallback and for parallel seeds |

Colab is retained as **overflow, not primary**. If the laptop is unavailable or a run needs to
proceed in parallel, the same configs run there unchanged.

### 4. Unfreezing

PRD §8.4 sets `unfreeze_epoch: 30`. Cached features are only valid while the backbones are frozen.

Fine-tuning the backbones is therefore reclassified as a **separate, later, optional experiment**,
run with the uncached pipeline at a reduced batch size and gradient accumulation. PRD R4 already
anticipates that unfreezing may hurt, and PRD §20 L4 commits to reporting frozen vs. fine-tuned as an
ablation row. This decision makes that comparison an explicit experiment rather than an implicit
mid-run transition — which is cleaner science regardless of hardware. Recorded as pending item P3.

## Consequences

**Positive.** No session limits, no disconnects, no GPU lottery, no 15 GB ceiling. The ablation
becomes cheap enough to run at full epochs, which removes a paper caveat. PPO parallelises across 14
cores — the 120-episode benchmark (FR-R06) becomes hours rather than days. Iteration speed on the
model improves by roughly two orders of magnitude, which matters more than raw throughput when
debugging.

**Negative.** Single point of failure: one machine holds training, PPO, and the edge node. Mitigation
— checkpoints and result CSVs push to the repository continuously, and Colab accounts stay live so
any config can move there unchanged.

**Negative.** Cached features are invalidated by any change to the backbones, the input resize, or
the normalisation. The cache must record the git commit and preprocessing config that produced it,
and be regenerated when either changes. A stale cache produces results that look fine and are wrong —
this is the main risk this decision introduces.

**Negative.** Sustained multi-hour GPU load on a laptop. Keep it plugged in, on a hard surface, with
the Windows power plan on high performance. Thermal throttling degrades throughput but does not
affect correctness.

**Consequence for NFR-01 — this one matters for honesty.** An RTX 4050 vastly outperforms a Jetson
Nano. Under [ADR-003](ADR-003-laptop-as-edge.md) the edge node is this laptop, so YOLOv8 fps will
comfortably exceed the ≥10 fps target — but that figure says nothing about Jetson feasibility. It is
an **optimistic** proxy, not a representative one. Report it as "RTX 4050 Laptop, GPU inference" and
state plainly that on-target validation is outstanding (PRD §20 L8). Also measure and report a
**CPU-only** figure, which is a far better proxy for constrained edge hardware and costs one extra
run.

## Alternatives considered

**Colab-primary, per PRD §15.2.** No local setup, no thermal concern, 16 GB VRAM. Rejected: session
limits make a 16-hour run impossible without checkpoint-resume gymnastics, GPU availability is not
guaranteed, and the 15 GB Drive ceiling conflicts with both the feature cache and the IDD subset.

**Local without feature caching.** Simpler; no cache-invalidation risk. Rejected: batch 32 does not
fit in 6 GB, and it discards a roughly hundred-fold speedup on the ablation for no benefit. If
caching proves troublesome, the fallback is batch 4 with gradient accumulation to an effective 32 —
correct, and slow.

**Split: model on Colab, PPO local.** Reasonable, and close to what §15.2 implies. Rejected as
strictly worse than local-primary-with-Colab-overflow, which keeps the same fallback while removing
the session limits from the default path.
