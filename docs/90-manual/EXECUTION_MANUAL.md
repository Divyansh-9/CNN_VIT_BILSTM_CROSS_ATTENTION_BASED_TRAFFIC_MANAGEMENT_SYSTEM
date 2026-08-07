# MFSTNet Execution Manual

**The practical guide. Start here on day one.**

| | |
|---|---|
| **Version** | 1.0 — 2026-08-07 |
| **Audience** | The project team |
| **Companion documents** | [SOW](../00-planning/SOW.md) (what and when) · [PRD](../00-planning/PRD.md) (numbers) · [FRD](../01-requirements/FRD.md) (acceptance criteria) |

> The other documents say *what* must be true. This one says *what to do on Monday*.
> Where this manual and the PRD disagree on a number, **the PRD wins** — tell the team and log it in
> [PRD-CHANGELOG](../00-planning/PRD-CHANGELOG.md).

---

## Contents

| Part | Title | Read when |
|---|---|---|
| [0](#part-0--setup) | Setup — accounts, repository, environments | Week 0 |
| [1](#part-1--week-by-week-course-of-action) | Week-by-week course of action | Weekly |
| [2](#part-2--the-dataset) | The dataset — sources, collection, annotation, auto-labelling | Weeks 2–9 |
| [3](#part-3--training-mfstnet) | Training MFSTNet on Colab | Weeks 9–14 |
| [4](#part-4--sumo-and-ppo) | SUMO and PPO | Weeks 6–14 |
| [5](#part-5--prototype-and-dashboard) | Prototype and dashboard | Weeks 13–17 |
| [6](#part-6--experiments-statistics-and-the-paper) | Experiments, statistics, and the paper | Weeks 13–20 |
| [7](#part-7--troubleshooting) | Troubleshooting | When stuck |

---

# Part 0 — Setup

**Goal:** by end of Week 1, every member can clone the repo, run a training script, and push. Nothing
here costs money.

## 0.1 Accounts

| Service | Purpose | Cost | Notes |
|---|---|---|---|
| GitHub | Code, docs, results | ₹0 | Apply for the **Student Developer Pack** — free private repos, Copilot, and credits |
| Google (Colab) | GPU training | ₹0 | Free-tier T4. One account per member multiplies your quota |
| Google Drive | Checkpoints | ₹0 | 15 GB free. Checkpoints live here, not in Colab's ephemeral disk |
| Roboflow | Annotation + hosting | ₹0 | Free tier is unlimited for **public** projects — which you want anyway (FR-D06) |
| Kaggle | Second dataset host | ₹0 | Also a GPU fallback when Colab throttles |
| Overleaf | Paper | ₹0 | Free tier handles a conference paper |
| IDD (IIIT-H) | Public bootstrap dataset | ₹0 | Free registration; approval takes 1–3 days — **register in Week 0**, not Week 2 |

> **Do this first.** IDD approval is the only item with external lead time. Register on day one so it
> is ready when Track A starts (ADR-001).

## 0.2 Repository

Already initialised, with `.gitignore` and Git LFS configured. Each member, once per machine:

```bash
git lfs install
git clone <repo-url>
cd major-project
```

Create the directory skeleton from PRD §22.3:

```bash
mkdir -p indiatrafficnet detection \
         mfstnet/{encoders,fusion,temporal,heads,configs} \
         simulation/{configs,envs} server dashboard edge \
         experiments/results models notebooks scripts tests
```

**Branching.** `main` stays working at all times. One branch per work item:

```bash
git checkout -b feat/mfstnet-cnn-encoder
# ... work ...
git push -u origin feat/mfstnet-cnn-encoder   # then open a PR
```

Anything that breaks `main` costs the whole team a day. With four people and one deadline, that is
the most expensive mistake available.

## 0.3 Python environment

Python 3.10+. From the repo root:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Initial `requirements.txt` — **pin versions** (NFR-08 requires clean-machine reproduction, and
unpinned ranges break that within weeks):

```
torch==2.3.1
torchvision==0.18.1
timm==1.0.7
ultralytics==8.2.0
stable-baselines3==2.3.2
gymnasium==0.29.1
onnx==1.16.1
onnxruntime==1.18.0
opencv-python==4.10.0.84
numpy==1.26.4
pandas==2.2.2
scipy==1.13.1
scikit-learn==1.5.0
matplotlib==3.9.0
pyyaml==6.0.1
tensorboard==2.17.0
mlflow==2.14.1
paho-mqtt==2.1.0
fastapi==0.111.0
uvicorn==0.30.1
tqdm==4.66.4
pytest==8.2.2
```

Add `traci` and `sumolib` after installing SUMO (Part 4). Whenever anyone adds a dependency, they
add the pinned line in the same commit.

## 0.4 The seeding utility — write this before anything else

NFR-07 is Critical, and it cannot be retrofitted: seeds not set during a run cannot be recovered
afterwards. `scripts/seed.py`:

```python
import os, random
import numpy as np
import torch

def set_seed(seed: int = 42) -> None:
    """Seed every RNG the project touches. Call before building any model."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
```

For Stable-Baselines3, also pass `seed=42` to the model constructor and call `env.reset(seed=42)`.

**Verify it works** (TC-N07) before trusting it:

```bash
python scripts/train_mfstnet.py --config mfstnet/configs/smoke.yaml --epochs 1
python scripts/train_mfstnet.py --config mfstnet/configs/smoke.yaml --epochs 1
# Epoch-1 loss must match to 1e-6. If it does not, seeding is incomplete.
```

## 0.5 Roles

Fill in the names in [SOW §3](../00-planning/SOW.md#3-team-and-responsibilities) and commit. Every
deliverable needs one owner and one backup. "We'll all do it" is how a deliverable arrives in Week 19.

## 0.6 Week 0 checklist

- [ ] All accounts created; **IDD registration submitted**
- [ ] Repo cloned by everyone; LFS working (`git lfs env` runs clean)
- [ ] `requirements.txt` installs on every member's machine
- [ ] `set_seed` written and its determinism verified
- [ ] SOW §3 names and §5 dates filled in and committed
- [ ] Faculty guide has seen SOW + BRD and agreed the milestone dates

---

# Part 1 — Week-by-week course of action

Derived from PRD §18.1 and the milestones in SOW §5. Tracks run in parallel — read down your own
column.

**Legend:** owners per SOW §3 — R1 Data/Detection · R2 Model · R3 Simulation/RL · R4 Systems/UI.

| Wk | R1 — Data & Detection | R2 — Model | R3 — Sim & RL | R4 — Systems & UI | Definition of done |
|---|---|---|---|---|---|
| 0 | Register IDD; scout intersections | Env setup; read PRD §8 | Install SUMO | Install Mosquitto | Part 0 checklist complete |
| 1 | Download IDD; write class-mapping table | Implement `set_seed`; smoke-test ResNet-50 + ViT loading | SUMO tutorial; render a 4-way network | MQTT publish/subscribe hello-world | Everyone has run *something* end to end |
| 2 | **Track A:** fine-tune YOLOv8 on public data | CNN encoder + ViT encoder modules with unit tests | Build the 4-way intersection network | Camera capture + lane ROI config | Detection weights v0 exist |
| 3 | **Track B:** record intersections 1–2 | Standard cross-attention module | Fixed-time + Random controllers | Edge skeleton: capture → count → publish | v0 weights count vehicles on real video |
| 4 | Record 3–4; extract frames @2 fps | BiLSTM + congestion head; **Phase 1 assembles end to end** | Webster controller | FastAPI skeleton + TimescaleDB | Phase 1 forward pass runs on random input |
| 5 | Record 5–6; filter frames | Overfit 10 sequences to zero loss | Gym env wrapper; `check_env` passes | Dashboard scaffold | **Wave 2 gate** — write SAD, HLD, LLD |
| 6 | Annotation begins; track frames/day | Auto-label pipeline (with R1) | PPO trains without crashing | Live page renders mock data | Annotation velocity ≥ 400 frames/day/person |
| 7 | Annotation continues | First real corpus; verify no clip-level leakage | Reward function unit tests (TC-R04) | MQTT contract test across all 5 topics | ≥1,000 sequences built |
| 8 | **M1** — publish IndiaTrafficNet | Phase 1 first real training run | PPO 100K-step trial run | Event log + heartbeat | M1 accepted |
| 9 | **M2** — fine-tune on IndiaTrafficNet; mAP comparison | Rebuild corpus with final weights | Calibrate SUMO from real counts | Emergency detection path | M2 accepted |
| 10 | Datasheet; 500-sequence verification subset | Phase 1 tuning; TensorBoard watch | **M3** — all 4 methods run | Preemption logic + all-red enforcement | M3 accepted |
| 11 | Support R2 on label quality | Phase 1 converging | PPO full 500K run starts | Analytics page | **Wave 3 gate** — write STP, STD, UAT |
| 12 | Per-class detector recall report | **M4** — Phase 1 converged | PPO curve monitored | Prototype assembly starts | M4 accepted |
| 13 | — | Ablation A–E launched (parallel Colab) | **M6** — PPO converged | Edge ↔ server integration | M6 accepted; ablation running |
| 14 | — | **M5** — ablation complete, macro F1 ≥0.80 | **M7** — 30-run benchmark + statistics | Benchmark page reads result CSVs | M5, M7 accepted |
| 15 | — | Phase 2 *only if* Phase 1 is clean | Results analysis; effect sizes | Latency measurement (NFR-01..06) | Phase 2 decision recorded |
| 16 | — | ONNX export + latency (FR-M12/13) | Paper: results section | **M8** — prototype live | **Wave 4 gate** — STR, TIM, SOP |
| 17 | — | Paper: method section | Paper: experiments | **M9** — dashboard complete | M8, M9 accepted |
| 18 | Dataset section of paper | Integration support | Integration support | Full integration; fault injection | Fallbacks (FR-A06) verified |
| 19 | — | — | — | **M10** — 4-hour continuous run | M10 accepted |
| 20 | Repo cleanup; README | Final report | Final report | Demo rehearsal + backup video | **M11** — paper submitted |

## 1.1 Rules that keep the schedule honest

**Do not implement Phase 2 before Phase 1 converges.** PRD §2.4 is non-negotiable, and §2.5.4 names
the failure this prevents: eight weeks on architecture, two on experiments, no ablation, no
statistics. The Week 15 row makes the decision explicit — record it either way.

**Week 5, 11, and 16 are documentation gates, not optional.** They appear in the schedule so they are
triggered by date rather than by spare time (ADR-004). There is never spare time.

**Record a weekly status every Friday**, from `docs/templates/weekly-status.md`. Fifteen minutes.
It is also the raw material for your final report — a project reconstructed from memory in Week 20
loses detail that mattered.

**When something slips, cut conditional scope first** (SOW §2.3), then Should-Have requirements, then
talk to the guide. Never cut the experiments — they are the deliverable (§2.5.4).

---

# Part 2 — The dataset

**This part answers: where does data come from, and do we make our own?**

**Yes, you make your own** — IndiaTrafficNet is Novel Contribution 1 and PRD §2.5.2 identifies it as
the primary differentiator faculty check for. But per [ADR-001](../00-planning/decisions/ADR-001-two-track-dataset-strategy.md)
it does not block anything, because a public dataset bootstraps the pipeline from Week 2.

## 2.1 Track A — public bootstrap (Week 2)

**Use IDD Detection** (22.8 GB, 40,000 annotated images) from `idd.insaan.iiit.ac.in`. Full rationale,
the datasets deliberately rejected, licensing, and the class mapping are in
[DATASETS.md](../00-planning/DATASETS.md) — read it before downloading, because several IDD entries
look relevant and are not.

**Two things to know going in:**

**IDD is dashcam footage.** Moving camera, road level, forward-facing. Your deployment is a fixed
elevated camera looking down. Vehicle class semantics transfer; detection accuracy at your viewpoint
does not. That is fine — Track A exists to unblock the pipeline, and the measured gap becomes a
result in Week 9 ([DATASETS.md §2](../00-planning/DATASETS.md)).

**22.8 GB will not fit in a free 15 GB Drive.** Download to Colab's ephemeral local disk, convert and
subsample there, persist only the ~2–4 GB result:

```python
!mkdir -p /content/idd
# download with the portal token, extract to /content/idd (ephemeral, not Drive)
!tar -xf IDD_Detection.tar.gz -C /content/idd
```

Then convert VOC XML → YOLO, apply the class mapping, drop images with no target-class object,
subsample to ~15–20k, and save that to Drive. Record the subsample seed and count in
`indiatrafficnet/public_subset.yaml` (NFR-07).

**Enumerate the actual labels before mapping** — don't trust any second-hand class list:

```bash
grep -rhoP '(?<=<name>)[^<]+' /content/idd/**/Annotations/*.xml | sort | uniq -c | sort -rn
```

Commit that output; it is datasheet evidence (FR-D07). Keep the mapping itself in
`indiatrafficnet/class_mapping.yaml`.

**Decide the `rider` convention now** (DATASETS.md §6.1). IDD annotates a motorcyclist as a `rider`
on a `motorcycle`; our taxonomy has no `rider`. Recommended: drop `rider`, count only the vehicle —
counting both inflates counts by roughly the two-wheeler share (~30% per PRD §12.2), which would bias
every congestion label the §8.6 pipeline produces. Apply the same convention to IndiaTrafficNet
annotation.

```bash
yolo detect train model=yolov8s.pt data=indiatrafficnet/public.yaml \
     epochs=50 imgsz=640 batch=16 seed=42 project=runs/detect name=bootstrap_v0
```

## 2.2 Track B — collecting IndiaTrafficNet

### Before you record

- **Ask permission.** Campus intersections first (PRD R1) — your own institution is the easiest
  approval you will ever get. For public roads, a written note from your department explaining the
  academic purpose prevents most difficulties.
- **Do not obstruct traffic** or record from a position that puts anyone at risk. Elevated and
  set-back positions give better geometry anyway.
- **Two people minimum.** One operates, one watches surroundings.
- **Log every session** as you go: location, GPS, date, start/end time, weather, camera height and
  angle, device. FR-D01, FR-D02, and FR-D07 all need this, and it cannot be reconstructed later.

### Recording spec

| Parameter | Value | Why |
|---|---|---|
| Duration | 2–3 h per intersection | PRD §12.1 |
| Sessions | ≥1 peak (08–10 / 17–20) + ≥1 off-peak (14–16) | FR-D02 |
| Height | As elevated as safely possible (footbridge, upper floor, terrace) | Reduces occlusion, which is the dominant detection error |
| Angle | Fixed, downward. **Do not pan or zoom** | A moving camera breaks lane ROIs and makes counts meaningless |
| Framing | All four approaches visible, or one approach fully | Partial approaches produce ambiguous counts |
| Resolution | 1080p @ 30 fps | Sufficient; higher wastes storage |
| Continuity | **Keep ≥5-minute unbroken clips** | Part 3's corpus needs them (PRD §8.6). Clipped highlights are useless for sequences |

> The continuity requirement is the one teams forget. A phone that stops and restarts recording every
> two minutes gives you a good detection dataset and **no** MFSTNet corpus at all.

### Frames

```bash
ffmpeg -i raw/intersection_01_peak.mp4 -vf fps=2 \
       -q:v 2 data/frames/int01_peak_%05d.jpg
```

Then filter — blurred, overexposed, near-duplicate (PRD §12.1 step 4). Roughly 108,000 raw frames
reduce to about 15,000 clean, of which 12,000 get annotated.

### Annotating on Roboflow

1. Create a **public** project (free, and FR-D06 requires public release anyway).
2. Define exactly the 8 classes from PRD §12.2 — no extras, no merges (FR-D03).
3. Turn on **AI-assisted labelling** after the first ~500 manual boxes. It roughly halves the
   remaining time (PRD R2 mitigation).
4. **Assign one class per annotator** where possible. Consistency within a class matters more than
   speed, and it makes disagreements visible.
5. Agree the edge cases *before* starting and write them down: is a rider part of the motorcycle?
   (No — separate `pedestrian` only if dismounted.) How much occlusion still counts? (Box it if
   ≥50% visible.) Partial vehicle at frame edge? (Box it.) Undocumented conventions produce a dataset
   that disagrees with itself.
6. **Track frames/day per person weekly** (PRD R2). At 400/day/person, four people reach 12,000 in
   about 8 working days. If Week 6's velocity implies missing Week 8, escalate then — not in Week 7.
7. Augment: flip, brightness, blur, mosaic (§12.1 step 6). **Augment the training split only** —
   augmenting val or test inflates your metrics and invalidates M2.
8. Split 70/15/15, stratified (FR-D05).
9. Publish to Roboflow Universe **and** Kaggle under CC BY 4.0 (FR-D06).

### The datasheet (FR-D07)

Non-optional, and reviewers read it. Cover: collection locations and conditions; times of day;
weather; camera geometry; per-class counts **with the low-sample warning for cattle** (PRD §20 L7);
annotation process and inter-annotator conventions; and known biases — explicitly including the
absence of night and adverse weather (§20 L3).

**Also review a sample for identifiable faces and licence plates before publishing**, and state the
basis for public release. Any venue with an ethics statement will ask.

## 2.3 Building the MFSTNet corpus (PRD §8.6)

This is the bridge from detection to prediction, and it is the step the original PRD was missing.

```
5-min clip → every 5s: frame → 224×224            → X [60, 3, 224, 224]
          → every frame: YOLOv8 → per-lane counts
          → count at t+60s → §14.1 thresholds     → Y [4] ∈ {0,1,2}
```

```python
# scripts/build_corpus.py  (sketch — see LLD for the full implementation)
STRIDE_S, SEQ_LEN, STEP_S, HORIZON_S = 30, 60, 5, 60
THRESHOLDS = (5, 15)          # PRD §14.1 — LOW <5, MED 5-15, HIGH >15

def label_from_count(n: int) -> int:
    return 0 if n < THRESHOLDS[0] else (1 if n <= THRESHOLDS[1] else 2)

# For each clip:
#   1. run YOLOv8 over every frame, accumulate per-lane counts by ROI
#   2. smooth counts over a 3-frame window (single-frame counts are noisy)
#   3. for each window start t (stride 30s):
#        X = frames at t, t+5, ..., t+295   (60 frames)
#        Y = [label_from_count(count[lane][t+60]) for lane in "NSEW"]
#   4. record the source clip id alongside every sequence
```

**Three rules that decide whether your results are real:**

1. **Split by source clip, never by sequence.** Sequences from one clip overlap heavily; if some land
   in train and others in test, the model has effectively seen the test set. PRD §2.5.1 lists this
   exact failure at Week 11–12, where it looks like suspiciously good validation accuracy.
2. **Smooth the counts.** A single frame's detection count fluctuates; the label should reflect
   traffic state, not detector jitter.
3. **Verify 500 sequences by hand** (PRD §8.6). Count four lanes at the label frame yourself, compare
   to the auto-label, and report the agreement rate. This number goes in the paper as your
   label-noise estimate, and it is what turns a methodological weakness into a documented limitation.

**Rebuild the corpus in Week 9** with the IndiaTrafficNet-fine-tuned weights. Corpora built with
bootstrap weights are for pipeline development, not final results — and every experiment record must
say which weights it used.

---

# Part 3 — Training MFSTNet

## 3.0 Train locally, on cached features

Per [ADR-005](../00-planning/decisions/ADR-005-local-first-training.md), the primary training machine
is the team laptop (i5-13500HX, RTX 4050 6 GB), not Colab. Colab is overflow.

### Setup

```powershell
# CUDA build of PyTorch — the default pip wheel is CPU-only
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Plugged in, high-performance power plan, hard surface. Sustained multi-hour GPU load throttles on a
warm laptop — that costs throughput, not correctness.

### The 6 GB problem, and the fix

At `batch_size: 32` with `T: 60`, one MFSTNet batch pushes **1,920 frames** through ResNet-50 *and*
ViT-Small. That does not fit in 6 GB. It is tight even on a 16 GB T4 — this is the architecture, not
your laptop.

But the backbones are **frozen**, so they produce identical features every epoch. Recomputing them
100 times is waste; recomputing them seven times over for the ablation is worse, because configs A–G
differ only in what happens *after* the backbones.

**So compute them once and cache them.**

```
Pass 1 (once):   every unique frame → ResNet-50 → cache
                                    → ViT-S/16  → cache
Pass 2 (always): cached features → projections → fusion → BiLSTM → heads
```

Cache **unique frames, not sequences.** At a 30 s stride, consecutive sequences share 54 of their 60
frames, so caching per sequence stores each frame about ten times over.

```python
# scripts/cache_features.py (sketch)
# Save fp16, keyed by (clip_id, frame_index). Record the git commit and the
# preprocessing config in the cache manifest - see the invalidation warning below.
with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
    f_cnn = resnet_features(frames)     # [N, 2048, 7, 7]  ~200 KB/frame
    f_vit = vit_tokens(frames)          # [N, 197, 384]    ~150 KB/frame
```

Ten hours of footage at 5 s sampling is ~7,200 unique frames — roughly **2.5 GB**. Nothing locally;
impossible on a 15 GB Drive.

### What this buys you

| | Before | After |
|---|---|---|
| Epoch time | Minutes | Seconds |
| VRAM | Does not fit at batch 32 | Comfortable |
| Ablation, 7 configs | 60–90 h (PRD R6) | Hours — **one cache serves all seven** |
| R6's 50-epoch mitigation | Needed | **Not needed** — run the full 100, no paper caveat |

> **The one way this bites you.** A cache is invalidated by any change to the backbones, the input
> resize, or the normalisation. A stale cache produces results that look completely normal and are
> wrong. Record the git commit and preprocessing config in the cache manifest, and assert they match
> at load time. Regenerate rather than guess.

**Unfreezing.** Caching is only valid while backbones are frozen. Treat `unfreeze_epoch: 30` as a
**separate later experiment** on the uncached pipeline (batch 4, gradient accumulation to 32), not as
a mid-run transition. PRD §20 L4 commits to reporting frozen vs. fine-tuned anyway, so this makes it
an explicit ablation row — cleaner science regardless of hardware.

### What runs where

| Work | Where |
|---|---|
| MFSTNet training + ablation | Local |
| YOLOv8 fine-tuning | Local — batch 8–16 at 640 fits in 6 GB |
| PPO + 30-run benchmark | **Local CPU** — SUMO is single-threaded, so run many seeds in parallel across 14 cores |
| Overflow / parallel seeds | Colab (§3.1) |

Keep the Colab accounts alive. Same configs, no changes needed — that is the fallback if the laptop
is unavailable.

## 3.1 Colab workflow (overflow)

Free-tier Colab disconnects. Plan for it rather than being surprised by it.

```python
# Cell 1 — mount Drive. Checkpoints go here, never to Colab's local disk.
from google.colab import drive
drive.mount('/content/drive')
CKPT = '/content/drive/MyDrive/mfstnet/checkpoints'

# Cell 2 — clone and install
!git clone https://github.com/<you>/major-project.git
%cd major-project
!pip install -q -r requirements.txt

# Cell 3 — confirm you actually got a GPU before starting a 12-hour run
!nvidia-smi
```

**Rules that save you a lost night:**

- Checkpoint **every epoch** to Drive, not just the best model. A disconnect at epoch 60 with only
  best-so-far saved costs you the run.
- Save optimizer and scheduler state too, or resuming restarts the LR schedule and produces a visible
  discontinuity in the loss curve.
- Make `--resume` the default path, not an afterthought.
- Keep the browser tab open and the machine awake; free tier reclaims idle sessions.
- Run long jobs overnight — quota pressure is lower.
- Spread ablation configs across team accounts (PRD R6). Four accounts is four times the throughput.

```python
# Resume-capable checkpointing
torch.save({
    'epoch': epoch, 'model': model.state_dict(),
    'optim': optimizer.state_dict(), 'sched': scheduler.state_dict(),
    'best_f1': best_f1, 'config': cfg,
}, f'{CKPT}/{cfg["run_name"]}_last.pt')
```

## 3.2 Build order — follow it exactly

PRD §2.4. Each step must pass before the next begins.

| Step | Build | Passes when |
|---|---|---|
| 1 | ResNet-50 encoder | `[2,3,224,224]` → `[2,N_c,256]`; backbone frozen (TC-M01) |
| 2 | ViT-Small/16 encoder | `[2,3,224,224]` → `[2,N_v,256]`; backbone frozen (TC-M02) |
| 3 | **Standard** cross-attention | `Z_A ≠ Z_B` on non-degenerate input (TC-M03) |
| 4 | BiLSTM + congestion head | `[B,60,256]` → `[B,4,3]` (TC-M05, TC-M08) |
| 5 | **Overfit 10 sequences** | Training loss → ~0 | 
| 6 | Full Phase 1 training | Val loss decreases; **M4** |
| 7 | Ablation A–E | `ablation.csv` populated |
| 8 | *Phase 2 only now* — gate, temporal attention, attention pooling | |

**Step 5 is the one people skip, and it is the most valuable.** A model that cannot overfit ten
sequences has a bug — in the data pipeline, the loss, or the label alignment. Finding that on ten
sequences takes minutes; finding it after a 12-hour run takes a day.

## 3.3 Config-driven everything (NFR-15, NFR-16)

Hyperparameters live in YAML because the ablation harness drives configs. A numeric literal in a
training script is a bug waiting for Week 13.

```yaml
# mfstnet/configs/config_G_full.yaml
run_name: G_full
seed: 42
model:
  d_model: 256
  use_cnn: true
  use_vit: true
  fusion: bidirectional      # none | concat | unidirectional | bidirectional
  use_gate: true             # Phase 2
  bilstm: {hidden: 128, layers: 2, bidirectional: true}
  use_temporal_attn: true    # Phase 2
  temporal_attn: {layers: 2, heads: 4, d_ff: 512, dropout: 0.1}
  pooling: attention         # last | attention
train:
  epochs: 100
  batch_size: 32
  lr: 1.0e-4
  weight_decay: 1.0e-4
  optimizer: AdamW
  scheduler: CosineAnnealingLR
  patience: 15
  freeze_backbone: true
  unfreeze_epoch: 30
```

The seven ablation configs (PRD §14.4) differ **only** in the `model` block:

| Config | use_cnn | use_vit | fusion | use_gate | use_temporal_attn |
|---|---|---|---|---|---|
| A — CNN only | true | false | none | false | false |
| B — ViT only | false | true | none | false | false |
| C — Naive fusion | true | true | concat | false | false |
| D — 1-dir cross-attn | true | true | unidirectional | false | false |
| E — Bidir, no gate | true | true | bidirectional | false | false |
| F — + TempAttn | true | true | bidirectional | false | true |
| G — Full | true | true | bidirectional | true | true |

```bash
for cfg in A_cnn_only B_vit_only C_concat D_unidir E_bidir F_tempattn G_full; do
  python scripts/train_mfstnet.py --config mfstnet/configs/config_${cfg}.yaml
done
```

If total ablation time threatens the schedule, cut to 50 epochs per config (PRD R6) — **and state it
in the paper**. The trend across configs is the finding; the absolute F1 of the ablation runs is not.

## 3.4 What to watch in TensorBoard

| Signal | Healthy | If not |
|---|---|---|
| Train loss | Decreasing | See Part 7 |
| Val loss | Decreasing, then flattening | Diverging from train → overfitting; freeze longer (PRD R4) |
| Macro F1 | Rising toward ≥0.80 | Check class weights; check label balance |
| Per-class recall (HIGH) | Rising | HIGH is the class that matters operationally — a model that never predicts HIGH is useless regardless of accuracy |
| **Gate histogram** (Phase 2) | Spread across (0,1) | Collapsed at 0 or 1 → PRD R5. Add gate entropy regularisation |

Log the gate value every epoch from the first Phase 2 run. FR-M04, FR-UI05, and BR-07 all depend on
it, and it is a research artifact you will analyse in the paper — not an internal detail.

---

# Part 4 — SUMO and PPO

## 4.1 Install

```bash
# Windows: download the installer from eclipse.dev/sumo
# Then set SUMO_HOME and install the Python bindings:
pip install eclipse-sumo traci sumolib
```

Verify: `sumo-gui` opens, and `python -c "import traci; print(traci.__file__)"` succeeds.

## 4.2 Build order

1. Network — 4-way intersection, ≥2 lanes per approach (`netedit`, or `netgenerate` then edit).
2. Demand — start with plausible flows; calibrate against real counts in Week 9 (FR-S02).
3. Baselines first: **Fixed → Random → Webster**, in that order. They are simple, and they prove the
   environment works before RL complicates the picture.
4. Gym wrapper. Run `stable_baselines3.common.env_checker.check_env` and fix everything it reports
   before training. Every hour spent here saves several later.
5. PPO.

```python
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

env = SumoIntersectionEnv(config="simulation/configs/intersection.sumocfg")
check_env(env)                    # do not skip

model = PPO("MlpPolicy", env, seed=42, verbose=1,
            tensorboard_log="runs/ppo",
            **yaml.safe_load(open("simulation/configs/ppo_config.yaml")))
model.learn(total_timesteps=500_000)
model.save("models/ppo_intersection")
```

## 4.3 The state vector is a contract

PRD §13.1 — 17 dimensions, in this exact order:

```python
state = np.array([
    count_N/50, count_S/50, count_E/50, count_W/50,          #  0-3
    queue_N/200, queue_S/200, queue_E/200, queue_W/200,      #  4-7
    phase_NS, phase_EW,                                       #  8-9
    phase_remaining/90,                                       # 10
    mfst_pred_N/2, mfst_pred_S/2, mfst_pred_E/2, mfst_pred_W/2,  # 11-14
    mfst_gate_mean,                                           # 15
    emergency_flag,                                           # 16
])
```

**Changing this shape or these normalisations invalidates every trained PPO checkpoint** (FR-M14).
If MFSTNet is unavailable, zero indices 11–15 — do not shorten the vector. If Phase 2 is never
reached and there is no gate, fix index 15 at 0.5 and document it. The dimensionality must not move.

Watch the divisors. `count/50` and `queue/200` were chosen before real data existed. If Week 9
calibration shows real counts exceeding 50, the state saturates at 1.0 and the agent goes blind
exactly when traffic is heaviest — that is pending item P2 in the PRD changelog. Check it; do not
assume it.

## 4.4 The 30-run benchmark (FR-R06–FR-R08)

```python
for method in ["fixed", "webster", "random", "ppo"]:
    for seed in range(1, 31):
        # SAME network, SAME demand for a given seed, across all methods (FR-S04)
        run(method, seed, duration_s=3600)
        # append a row: method, seed, mean_wait, mean_queue, throughput,
        #               p95_wait, emergency_clearance_time
```

**The pairing is what makes the t-test valid.** If seed 7 produces different demand under Fixed than
under PPO, the paired test is meaningless and M7 fails on methodology rather than on results. Verify
FR-S04 before spending the compute on 120 episodes.

Write rows to `experiments/results/rl_runs.csv` from inside the loop. Never transcribe results by
hand — NFR-09 requires the raw CSV, and hand-copied numbers cannot be recomputed.

---

# Part 5 — Prototype and dashboard

## 5.1 The edge node (₹0 configuration)

Per [ADR-003](../00-planning/decisions/ADR-003-laptop-as-edge.md) and PRD §15.4, the edge node is a
laptop. The MQTT contract, detection pipeline, Webster fallback, and preemption logic are identical
to the Jetson configuration — only the host and the output device differ.

- Four lanes from one camera via static ROI polygons, or four looping video files for a repeatable
  demo.
- Signal output is an on-screen four-phase panel instead of GPIO LEDs.
- **Check the department lab for a Jetson or Pi first.** If you find one, real on-device numbers are
  worth having, and ₹200 of LEDs restores the physical demo.

## 5.2 MQTT — get the QoS right the first time

The contract is PRD §17.1. QoS differs per topic and is **part of the contract**:

| Topic | QoS | Why |
|---|---|---|
| `.../vehicle_count` | 1 | At-least-once; a lost count degrades the next decision |
| `.../emergency/detect` | **2** | Exactly-once. A duplicate fires a spurious preemption; a loss risks a life |
| `.../signal/command` | 1 | At-least-once; commands are idempotent by phase+duration |
| `.../congestion/prediction` | 0 | Superseded every 5 s, so a loss self-heals |
| `.../system/heartbeat` | 0 | Absence is the signal |

Three people build against this contract in different weeks. Write the contract test in Week 7 —
publish and assert on every topic — so a mismatch surfaces then, not during Week 17 integration when
there is no time to diagnose it.

## 5.3 The two fallbacks are features (FR-A06)

Test both by fault injection, and pull this forward to Week 17 rather than Week 19 (RTM §5.2 —
fault-injection testing finds real defects, and finding them one week before submission is too late):

```bash
# (a) MFSTNet dies → PPO must continue on raw counts
kill $(pgrep -f mfstnet_service)
# Expect: signal commands continue; dashboard shows prediction unavailable, not stale

# (b) Broker dies → edge must switch to Webster within 10s
sudo systemctl stop mosquitto
# Expect: local Webster control within 10s; signals keep changing; heartbeat gap logged
```

Webster must be **resident on the edge node**. A fallback fetched over the network when the network
has failed is not a fallback.

## 5.4 Dashboard

React 18 + Vite + Zustand + Recharts, native WebSocket, CSS Modules, dark mode only
(`#0D1117` background, `#6366F1` accent, Inter + JetBrains Mono).

Start it in **Week 6 against mocked data**, not Week 14. M9 carries 13 requirements into a single
week (RTM §5.2); mocking the WebSocket payloads lets the UI mature while the backend is still being
built, and the payload schemas are already fixed by PRD §17.1.

**The Benchmark page reads the committed result CSVs.** Never hardcode numbers into the frontend.
This is what makes the dashboard evidence rather than illustration — regenerate a result and the
dashboard updates itself.

---

# Part 6 — Experiments, statistics, and the paper

> PRD §2.5.4: *"The experiments are not a formality. They ARE the research."*

## 6.1 One record per run

Every training or evaluation run gets a record from `docs/templates/experiment-record.md`, written
**when the run starts**, not afterwards. Minimum: run ID, date, config file + git commit, seed,
dataset version, **detector weights** (ADR-001 — two sets exist between Weeks 2 and 8), hardware,
result CSV path, and what you expected to happen versus what did.

That last field is the one that pays off. A record of what you expected turns a surprising result
into a finding instead of a mystery.

## 6.2 Statistics (FR-R07, FR-R08)

```python
import numpy as np
from scipy import stats

def bootstrap_ci(x, n=10_000, alpha=0.05, seed=42):
    rng = np.random.default_rng(seed)
    means = [rng.choice(x, len(x), replace=True).mean() for _ in range(n)]
    return np.percentile(means, [100*alpha/2, 100*(1-alpha/2)])

def cohens_d(a, b):
    diff = np.asarray(a) - np.asarray(b)
    return diff.mean() / diff.std(ddof=1)      # paired d

t, p = stats.ttest_rel(ppo_waits, webster_waits)   # paired: same seeds
```

Report every comparison as **mean ± 95% CI, with p and Cohen's d**. PRD §2.5.2 contrasts "our model
is better" against "0.83 macro F1 vs 0.76 (p=0.003, d=0.71)" — the second is what gets marks and
what survives review.

Generate every table in the paper from the committed CSVs by a committed script. A hand-typed table
cannot be recomputed, and a number that cannot be recomputed is not evidence (BR-18).

## 6.3 If the results disappoint

Read PRD §2.5.5 before doing anything else.

- **Report it.** A well-analysed negative result is publishable at CVIP or ICIIT.
- **Analyse why.** Dataset too small? ViT freezing limiting the fusion? Sequences too short for
  temporal modelling to matter?
- **Do not** tune until a test passes and then report only the passing run. That is cherry-picking
  wearing a lab coat, and it is the failure mode BR-19 exists to prevent.

## 6.4 The paper

Target IEEE ITSC / CVIP. Draft from Week 16; do not start in Week 19.

| Section | Source |
|---|---|
| Introduction, related work | PRD §1, §3, §4 |
| Dataset | Part 2, the datasheet, FR-D08/D09 results |
| Method | PRD §8, §14; the gate is your architectural contribution |
| Experiments | `ablation.csv`, `rl_runs.csv`, §6.2 statistics |
| Limitations | PRD §20 — including L1 label noise, L1b simulation-only control, L8 proxy latency |
| Conclusion | What you found, including what did not work |

Write the limitations section honestly and early. Reviewers trust a paper that names its own
weaknesses far more than one that appears not to have any.

---

# Part 7 — Troubleshooting

Extends PRD §2.5.1.

## Data and detection

| Symptom | Likely cause | Fix |
|---|---|---|
| Annotation is behind schedule | Underestimated per-frame time | Roboflow AI-assisted labelling; one class per annotator; track frames/day weekly (R2) |
| mAP high overall, terrible on auto-rickshaw | Class imbalance | Report per-class mAP **with sample counts** (§20 L7). Oversample or augment the rare class |
| Cattle class effectively unusable | <200 samples | Expected. Report it as a limitation rather than hiding it |
| Counts jump wildly frame to frame | Detector jitter | Smooth over 3 frames before labelling (Part 2.3) |
| Counts wrong at lane boundaries | ROI polygons overlap or leave gaps | Re-draw ROIs; assert every detection maps to exactly one lane |

## MFSTNet

| Symptom | Likely cause | Fix |
|---|---|---|
| Cannot overfit 10 sequences | Bug in data pipeline, loss, or label alignment | Stop. Fix this before any full run — everything downstream is invalid until it passes |
| Val accuracy suspiciously high | **Clip-level leakage** | Splits must be by source clip, never by sequence (Part 2.3) |
| ViT overfits immediately | Small dataset | Expected (R4). Keep the backbone frozen; train only projection and cross-attention |
| BiLSTM produces garbage | Input normalisation, then sequence ordering | Debug in that order (§2.5.1). Then reduce to 1 layer and re-check |
| All predictions one class | Class imbalance | Verify inverse-frequency class weights are actually applied to the loss |
| Gate stuck at 0 or 1 | Gate collapse (R5) | Check the TensorBoard histogram; add gate entropy regularisation |
| Loss goes NaN | LR too high, or bad input | Check for NaN in inputs first; then lower LR; then add gradient clipping |
| Colab disconnected at epoch 60 | Free tier | Resume from the per-epoch Drive checkpoint (Part 3.1) |
| Ablation will take 90 h | 7 configs × 100 epochs | Cut to 50 epochs (R6) and state it in the paper; parallelise across accounts |

## SUMO and PPO

| Symptom | Likely cause | Fix |
|---|---|---|
| Reward curve flat | Normal for the first ~100K steps | Wait. If still flat at 200K, simplify the state space first (§2.5.1) |
| PPO loses to Webster | Reward shaping, or a saturated state | Check state normalisation (P2). Then reward weights. A negative result is publishable (R7) |
| `check_env` fails | Space or dtype mismatch | Fix every complaint before training. Do not suppress warnings |
| Paired t-test looks wrong | Methods faced different demand | Verify FR-S04 — same network, same demand per seed |
| Emergency never clears in sim | Preemption not wired into the env | Test the reward's emergency bonus in isolation (TC-R04) |

## Integration

| Symptom | Likely cause | Fix |
|---|---|---|
| MQTT messages lost | QoS mismatch between publisher and subscriber | Compare against the §17.1 table. Emergency is QoS **2** |
| Dashboard shows stale data as live | No staleness handling | Mark data stale after 2 missed refreshes; never render old data as current |
| Webster fallback never triggers | Dropout detection window wrong, or Webster not resident | It must be local and always loaded (FR-A06) |
| Latency budget exceeded | Queueing between stages | Measure the composed round trip, don't sum per-stage medians (NFR §2.1) |
| Demo fails on the venue network | Untested network | Test on the actual network 48 h before (R9). **Have a 5-minute recorded video backup** |

## Project

| Symptom | Fix |
|---|---|
| Behind schedule | Cut conditional scope (SOW §2.3) first, then Should-Haves. Never cut experiments |
| Tempted to add gating before Phase 1 converges | Re-read PRD §2.4. It is non-negotiable, and §2.5.4 explains why |
| Results are marginal | PRD §2.5.5. Report and analyse; do not hide |
| Week 16 panic | Re-read PRD §2.5 — it was written for this moment |

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial manual, aligned to PRD v1.1 and ADR-001..004 |
