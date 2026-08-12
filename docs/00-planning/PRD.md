# 📄 Product Requirements Document (PRD) — v1.2
# MFSTNet: CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System
### Multimodal Fusion Spatio-Temporal Network with Gated Cross-Attention and Hybrid Temporal Modeling

---

| Field              | Details                                                                          |
|--------------------|----------------------------------------------------------------------------------|
| **Document ID**    | PRD-MFSTNET-001                                                                  |
| **Version**        | 1.2                                                                              |
| **Status**         | Active                                                                           |
| **Created**        | 2026-07-31                                                                       |
| **Last amended**   | 2026-08-08 — A1–A12 applied; **A13, A14 proposed, awaiting sign-off**. See [PRD-CHANGELOG](PRD-CHANGELOG.md) |
| **Supersedes**     | PRD-STMS-002 (CongestFormer variant)                                             |
| **Authors**        | [Your Name / Team Name]                                                          |
| **Reviewers**      | [Faculty Guide / Project Mentor]                                                 |
| **Target Release** | Academic Prototype — Week 20                                                     |
| **Target Venues**  | IEEE ITSC 2027 / CVIP 2026-2027 / Springer LNCS / National Conference (backup)  |

---

> ### Why MFSTNet?
> The previous design (CongestFormer) used a standalone lightweight Transformer — single encoder, single modality, no fusion. MFSTNet introduces three architectural advances:
>
> 1. **Dual-Path Spatial Encoding** — CNN (local texture, vehicle shape) + ViT (global intersection context) in parallel
> 2. **Gated Bidirectional Cross-Attention Fusion** — both encoders attend to each other; a learned gate adaptively weighs them per scene
> 3. **Hybrid Temporal Modeling** — BiLSTM captures short-range patterns; Temporal Self-Attention captures long-range cycles
>
> Together, these address the core failure mode of single-encoder models: **poor generalization to unseen intersection geometries and traffic densities.**

---

## Table of Contents

1. Executive Summary
2. Brutally Honest Self-Assessment for B.Tech CSE (ML/AI)
3. Novel Contributions and Research Claims
4. Problem Statement
5. Goals and Success Criteria
6. Scope
7. System Architecture
8. MFSTNet — Core Architecture Specification
9. Functional Requirements
10. Non-Functional Requirements
11. Technology Stack
12. Novel Contribution 1 — IndiaTrafficNet Dataset
13. Novel Contribution 2 — RL Signal Control via SUMO and PPO
14. Novel Contribution 3 — MFSTNet Multimodal Fusion Model
15. Hardware Requirements
16. UI/UX Requirements — Dashboard
17. Integration and Communication Protocol
18. Project Timeline and Milestones
19. Risk Analysis and Mitigation
20. Open Issues and Known Limitations
21. Success Metrics and KPIs
22. Publication and Research Output Plan
23. Future Scope
24. Appendix

---

## 1. Executive Summary

Traffic congestion in Indian cities costs the economy an estimated **Rs.1.47 lakh crore annually** (TERI, 2022). Existing adaptive traffic control research relies overwhelmingly on either single-modality vision models (CNN-only or ViT-only) or purely temporal models (LSTM/GRU) — never both, and never with a principled fusion mechanism. They also fail on Indian-specific traffic characteristics: auto-rickshaws, e-rickshaws, lane-less driving, cattle on roads.

**MFSTNet** introduces a novel **multimodal fusion architecture** that combines:

- **CNN (ResNet-50)** — local spatial feature extraction per frame
- **ViT (Vision Transformer, ViT-Small)** — global spatial context encoding per frame
- **Gated Bidirectional Cross-Attention** — scene-adaptive fusion of both encoders
- **BiLSTM + Temporal Self-Attention** — short-range and long-range temporal modeling
- **PPO Reinforcement Learning** — downstream adaptive signal control using fused representation

The system operates on the **IndiaTrafficNet** dataset (India's first publicly released annotated urban intersection dataset, 12,000+ frames, 8 India-specific classes).

Three novel contributions are claimed, each independently measurable and publishable:

| Contribution | Description |
|---|---|
| **IndiaTrafficNet** | First publicly released annotated Indian urban intersection dataset |
| **PPO Signal Controller** | RL agent trained on Indian traffic patterns, benchmarked vs. fixed-timer and rule-based |
| **MFSTNet** | Multimodal CNN-ViT cross-attention + BiLSTM hybrid for congestion prediction |

---

## 2. Brutally Honest Self-Assessment for B.Tech CSE (ML/AI)

> **This section exists to prevent scope disasters. Read it before committing.**

### 2.1 Is This Architecture Level Appropriate for B.Tech?

**Short answer: Yes — with clear scoping.**

| Component | Difficulty Level | B.Tech Feasibility |
|---|---|---|
| IndiaTrafficNet dataset collection + annotation | Medium | Yes — Very feasible |
| YOLOv8 fine-tuning on custom dataset | Medium | Yes — Standard practice, Colab-feasible |
| SUMO simulation + PPO RL training | Medium-High | Yes — Feasible with Stable-Baselines3 |
| CNN (ResNet-50) feature extraction | Low-Medium | Yes — torchvision, standard |
| ViT feature extraction (pretrained) | Medium | Yes — timm library, 5 lines of code |
| Cross-Attention fusion | Medium | Yes — PyTorch nn.MultiheadAttention built-in |
| BiLSTM temporal modeling | Medium | Yes — PyTorch built-in |
| **Gated Bidirectional Cross-Attention** | **High** | STRETCH GOAL — implement after core works |
| **Temporal Self-Attention on BiLSTM output** | **High** | STRETCH GOAL — significant complexity |
| Full end-to-end training pipeline | Very High | Needs careful engineering discipline |

### 2.2 Recommended Execution Strategy

```
Phase 1 (MANDATORY — Core that MUST work):
  CNN (ResNet-50) + ViT (ViT-Small) + Standard Cross-Attention Fusion + BiLSTM
  --> Congestion prediction head
  This alone is novel and publishable for B.Tech level.

Phase 2 (STRETCH — Add after Phase 1 works):
  + Gated bidirectional cross-attention (replace standard cross-attn)
  + Temporal Self-Attention on BiLSTM outputs
  + Attention pooling (replace last hidden state)

Phase 3 (OPTIONAL — Only if time permits):
  + Full end-to-end integration with PPO live runtime
```

### 2.3 Honest Comparison to Peer Projects

| Project Type | Typical B.Tech Traffic | MFSTNet Core | MFSTNet Full |
|---|---|---|---|
| Architecture novelty | YOLOv8 + rule-based timer | HIGH | VERY HIGH |
| Dataset contribution | None (uses COCO) | HIGH (IndiaTrafficNet) | HIGH |
| RL component | None | Present (PPO) | Present |
| Publication potential | Low | High (IEEE ITSC / CVIP) | Very High |
| Implementation risk | Low | Medium | High |
| Suitable for? | Average project | B.Tech distinction grade | PhD lite |

**Bottom line**: MFSTNet Core (Phase 1) is the sweet spot for a 4th year B.Tech CSE ML/AI specialization project. Well above average, legitimately novel, achievable in 20 weeks with a 3-4 member team. The full MFSTNet is ambitious but achievable with discipline.

---

### 2.4 Blunt Recommendation

> **Read this. Then read it again.**

**Ship Phase 1 first.**

The gate mechanism and Temporal Self-Attention are stretch goals — full stop. A clean, well-tuned `CNN + ViT + Cross-Attention + BiLSTM` with a proper 7-configuration ablation study and a publicly released IndiaTrafficNet dataset is already **distinction-level** for any B.Tech CSE ML/AI program in India. That combination has never been applied to Indian intersection traffic before. That is your novelty. That is enough.

Do not fall into the trap of over-engineering the architecture and under-delivering on the experiments. A simple model with rigorous, reproducible experiments beats a complex model with sloppy results **every single time** — in conferences, in interviews, and in faculty evaluations.

> **Don't let perfect be the enemy of submitted.**

The ablation table is what turns a project into a paper. The gate and temporal attention are what you add when Phase 1 is already working cleanly and you have weeks to spare. If you do not have weeks to spare, they go into the "Future Work" section — and that is not a failure, that is a professional research decision.

**Priority order, non-negotiable:**

```
1. IndiaTrafficNet dataset collected, annotated, published        <-- Week 8
2. YOLOv8 fine-tuned and benchmarked vs. COCO                    <-- Week 9
3. MFSTNet Phase 1 (CNN+ViT+CrossAttn+BiLSTM) training           <-- Week 12
4. MFSTNet ablation (configs A-G, at least A-E)                  <-- Week 14
5. PPO training + 30-run SUMO benchmark                          <-- Week 14
6. Hardware prototype                                             <-- Week 16
7. Dashboard                                                     <-- Week 17
8. Paper draft                                                   <-- Week 19

Only AFTER all of the above are done:
9. Add gating mechanism (Phase 2)
10. Add Temporal Self-Attention (Phase 2)
```

---

### 2.5 Full Brutal Reality Check

> **This section is written so that in Week 16, when things are harder than expected, you have something to re-read instead of panicking or cutting corners.**

#### 2.5.1 Things That Will Go Wrong (and What to Do)

| What Will Go Wrong | When | What to Do |
|---|---|---|
| Data collection takes twice as long as planned | Week 3-4 | Start with your own college intersection. One intersection is enough to start annotation. Do not wait for all 6. |
| Roboflow annotation is slower than expected | Week 6-7 | Use Roboflow's AI-assisted labeling. Assign one class per annotator. Track frames/day velocity weekly. |
| ViT overfits immediately on your dataset size | Week 10-11 | Freeze the entire ViT backbone. Only train the linear projection and cross-attention layers. This is expected and fine. |
| BiLSTM doesn't converge or produces garbage | Week 11-12 | Debug input normalization first. Then check sequence ordering (no data leakage). Then reduce to 1 layer and debug. |
| Gate collapses (all predictions identical class) | Week 12-13 | Check class weights in CrossEntropyLoss. Add a small gate entropy regularization term. Check that gate histogram in TensorBoard is not stuck at 0 or 1. |
| PPO reward curve doesn't improve | Week 11-12 | This is normal for the first 100K steps. Check that CongestFormer/MFSTNet auxiliary state is properly normalized. If still flat at 200K steps, reduce state space complexity first. |
| Jetson Nano runs YOLOv8s at 6fps not 10fps | Week 15 | Immediately switch to YOLOv8n. Reduce input from 640 to 416. Both are acceptable for the prototype demo. |
| MFSTNet ablation takes 90 hours total | Week 13 | Cut epochs to 50 per config for ablation. The trend matters, not the absolute F1 value. Document this in your paper. |
| Dashboard WebSocket drops during demo | Week 18-19 | Test on the actual demo network 48h before. Have a pre-recorded 5-minute video of the system running as backup. |

#### 2.5.2 What Your Faculty Guide Actually Evaluates

Most students think the faculty guide cares about architecture complexity. They do not. What they actually check:

| What Faculty Actually Check | What Most Students Deliver | What You Should Deliver |
|---|---|---|
| Are your claims measurable? | "Our model is better" | "MFSTNet achieves 0.83 macro F1 vs. 0.76 for CNN-only LSTM (p=0.003, Cohen's d=0.71)" |
| Is the dataset genuine? | Uses COCO or Kaggle datasets | IndiaTrafficNet — your own, documented, public |
| Is the ablation honest? | No ablation, or cherry-picked | 7 configs, all reported, including the ones that didn't help |
| Is the code reproducible? | "It works on my machine" | Fixed seeds, requirements.txt, Docker, 30-run CSVs on GitHub |
| Can you defend every design choice? | "We used ViT because it's new" | "ViT captures global spatial context that CNN misses; gate value analysis confirms this" |

#### 2.5.3 What "Distinction Level" Actually Requires

You do not need the full MFSTNet to get distinction. You need:

```
[x] A genuine dataset contribution (IndiaTrafficNet — your own collection)
[x] A working novel model (CNN+ViT+CrossAttn+BiLSTM Phase 1)
[x] A rigorous ablation (at least configs A, B, C, D, G — show CNN and ViT are both needed)
[x] Statistical significance on RL results (30 runs, paired t-test, p<0.05)
[x] A working hardware prototype (even a 4-camera Jetson tabletop setup)
[x] A paper submission (submission receipt counts — acceptance is not required for B.Tech)
[x] Clean, documented, open-source code on GitHub
```

Everything else — the gate, temporal attention, FPN, DINOv2 backbone — is icing. Great if you have it. Not required for distinction.

#### 2.5.4 The Single Most Common B.Tech Project Failure Mode

> **Teams spend 8 weeks on the architecture, 2 weeks on the experiments, and submit with no ablation, no statistical tests, and a dashboard that crashes during the demo.**

Do not be that team. Allocate your time as follows:

```
Architecture design:    2 weeks  (you already did this)
Implementation:         6 weeks  (Phase 1 first, Phase 2 if time)
Experiments + ablation: 4 weeks  (this is the publication material)
Hardware + integration: 3 weeks
Dashboard:              2 weeks
Paper + report:         3 weeks
```

The experiments are not a formality. They ARE the research. Treat them as the most important deliverable, not the last.

#### 2.5.5 If the Results Are Disappointing

If MFSTNet Phase 1 only marginally outperforms CNN+BiLSTM (e.g., +2% F1 instead of +5%):

- **Do not hide it.** Report it honestly.
- **Analyze why.** Is your dataset too small? Is the ViT freezing limiting the cross-attention? Are the traffic sequences too short for temporal modeling to matter?
- **A well-analyzed negative result is publishable at CVIP or ICIIT.** "We find that CNN-ViT fusion improves over CNN-only by 2% F1 in low-data regimes, but this marginal gain does not justify the computational overhead — suggesting that data scale is the primary bottleneck for multimodal fusion in traffic applications" is a publishable finding.
- **A covered-up negative result is a failed project.** Reviewers and faculty guides can tell.

---

## 3. Novel Contributions and Research Claims

Every claim below is measurable and falsifiable.

### 3.1 Contribution 1 — IndiaTrafficNet Dataset

| Attribute | Detail |
|---|---|
| **Claim** | First publicly released annotated dataset of Indian urban intersection traffic with India-specific vehicle classes |
| **Gap Addressed** | COCO, CityScapes, BDD100K do not include auto-rickshaw, e-rickshaw, cattle, or lane-less multi-directional flow |
| **Dataset Size** | 12,000+ annotated frames from 6+ real Indian intersections |
| **Classes** | car, motorcycle, auto-rickshaw, e-rickshaw, bus, truck, pedestrian, cattle |
| **Release** | Public on Roboflow Universe + Kaggle under CC BY 4.0 |
| **Validation** | YOLOv8 on IndiaTrafficNet vs. COCO-only baseline: mAP comparison on Indian held-out test set |

### 3.2 Contribution 2 — RL-based Signal Control

| Attribute | Detail |
|---|---|
| **Claim** | PPO agent trained on Indian traffic flow patterns outperforms fixed-timer and rule-based baselines |
| **Environment** | SUMO with custom Indian traffic flow calibration from IndiaTrafficNet |
| **Algorithm** | Proximal Policy Optimization (PPO) via Stable-Baselines3 |
| **Baselines** | Fixed-timer, Webster formula (rule-based), Random agent |
| **Rigor** | 30 independent runs; 95% CI (bootstrap); paired t-test; Cohen's d |

### 3.3 Contribution 3 — MFSTNet

| Attribute | Detail |
|---|---|
| **Claim** | Multimodal CNN-ViT cross-attention fusion with BiLSTM temporal modeling outperforms single-encoder baselines on 60s congestion prediction |
| **Architecture** | ResNet-50 + ViT-Small --> Gated Bidirectional Cross-Attn --> BiLSTM --> TempAttn --> Congestion head |
| **Input** | Video frames (spatial) over T=60 timesteps (5-minute window at 5s intervals) |
| **Output** | Congestion level per lane: LOW / MEDIUM / HIGH, predicted 60 seconds ahead |
| **Baselines** | CNN-only LSTM, ViT-only LSTM, vanilla LSTM, GRU, CongestFormer (Transformer-only) |
| **Key Novelty** | Gated bidirectional cross-attention: both CNN and ViT attend to each other; adaptive gate weights them scene-conditionally |

---

## 4. Problem Statement

### 4.1 Background

Urban traffic lights in most Indian cities operate on **pre-timed fixed cycles**. These systems are:
- **Open-loop, not adaptive:** No real-time stimulus
- **Calibrated for average load:** Fail at both peak and off-peak extremes
- **Blind to emergencies:** No mechanism to prioritize ambulances
- **Producing no data:** City planners have no granular intersection-level data

### 4.2 The AI/ML Research Gap

| Problem | Impact |
|---|---|
| Single-modality vision models | CNN misses global spatial context; ViT misses fine-grained local patterns — both generalize poorly |
| No principled fusion for traffic | Most papers use concatenation — no cross-modal attention for traffic video |
| Temporal modeling ignores spatial richness | LSTM on raw counts discards all visual information |
| Western datasets dominate | Models miss auto-rickshaws (~15-30% of Indian urban vehicles), e-rickshaws, cattle |

### 4.3 Quantified Pain Points

| Issue | Data Point |
|---|---|
| Economic cost of congestion | Rs.1.47 lakh crore per year (TERI, 2022) |
| Emergency vehicle delay | Estimated 45-second average delay per intersection |
| Pedestrian fatalities | 43% of all road deaths in India (MoRTH, 2023) |
| Fuel waste from idling | ~2.8 billion liters per year at Indian traffic signals (CPCB estimate) |

### 4.4 Root Cause — Two-Layer Failure

1. **No rich spatial perception** — Single encoders miss complementary visual information
2. **No integrated spatiotemporal modeling** — Spatial and temporal reasoning are siloed

MFSTNet closes both gaps.

---

## 5. Goals and Success Criteria

### 5.1 Research Goals

| ID | Goal | Measurable Target |
|---|---|---|
| RG1 | Release IndiaTrafficNet publicly | 12,000+ frames, 8 classes, CC BY 4.0 |
| RG2 | PPO outperforms fixed-timer in SUMO | >=20% reduction in avg wait time, p < 0.05 |
| RG3 | PPO outperforms Webster rule-based | >=10% reduction in avg wait time, p < 0.05 |
| RG4 | MFSTNet outperforms CNN-only+LSTM | >=5% improvement in macro F1-score |
| RG5 | MFSTNet outperforms ViT-only+LSTM | >=3% improvement in macro F1-score |
| RG6 | MFSTNet outperforms CongestFormer | >=3% improvement in macro F1-score |
| RG7 | YOLOv8 on IndiaTrafficNet outperforms COCO-only | >=10% mAP improvement on India-specific classes |
| RG8 | Paper submitted | Submission receipt by Week 20 |

### 5.2 System Goals

| ID | Goal | Target |
|---|---|---|
| SG1 | Emergency vehicle preemption | 100% success, <=3 seconds, 10/10 lab trials |
| SG2 | Hardware prototype uptime | >=95% over 4-hour demo session |
| SG3 | Dashboard data lag | <=2 seconds |
| SG4 | Edge inference speed (YOLOv8) | >=10 fps on Jetson Nano |
| SG5 | MFSTNet inference latency | <=150ms on server CPU |

### 5.3 Non-Goals (v1.0)

- Real public intersection deployment
- Multi-intersection coordination
- V2X communication
- Nighttime robustness
- GPS-based emergency preemption
- Production-grade security

---

## 6. Scope

### In Scope (v1.0)

- Self-collection and annotation of IndiaTrafficNet (12,000+ frames, 8 classes)
- YOLOv8 fine-tuning on IndiaTrafficNet + comparison vs. COCO baseline
- SUMO simulation environment with Indian traffic flow calibration
- PPO agent training + 30-run benchmarking (4 methods, CI, paired t-test)
- MFSTNet design, training, and benchmarking vs. all baselines
- MFSTNet ablation study (7 configurations)
- MFSTNet output integrated as auxiliary PPO state input
- Hardware prototype: Jetson Nano + 4 cameras + LED signal modules
- MQTT-based edge-server communication
- FastAPI backend + PostgreSQL/TimescaleDB
- React dashboard: live monitor, benchmark, analytics, event log
- Emergency vehicle preemption
- Research paper draft for conference submission
- Open-source GitHub release

---

## 7. System Architecture

### 7.1 Two-Phase Design

```
PHASE A: OFFLINE TRAINING (Weeks 2-14)
========================================
  [Real Intersections] --> Video --> [Roboflow Annotation]
                                          |
                               IndiaTrafficNet Dataset
                              (12,000+ frames, 8 classes)
                                          |
                             +------------------------+
                             |                        |
                      [YOLOv8 Fine-tuning]   [SUMO Traffic Simulation]
                      (Google Colab T4 GPU)  (Calibrated from dataset)
                             |                        |
                      Trained YOLOv8s          +------+-------+
                      weights (.pt)            |              |
                                          [PPO Training]  [MFSTNet Training]
                                          SB3 + TraCI     PyTorch (Colab T4)
                                               |              |
                                          Trained PPO.zip  model.onnx

PHASE B: ONLINE PROTOTYPE (Weeks 13-19)
=========================================
  PERCEPTION
  [Camera N/S/E/W] --> [Jetson Nano]
                            |
                      YOLOv8s inference (fine-tuned)
                      Vehicle count + type per lane
                      Emergency vehicle flag
                            |
                         MQTT (QoS 1)
                            |
  INTELLIGENCE         [Central Server]
                            |
                   +--------+--------+
                   |                 |
             [MFSTNet]          [PPO Agent]
             CNN+ViT+CrossAttn  Uses counts +
             +BiLSTM+TempAttn   MFSTNet predictions
             60s prediction
                   |                 |
                   +--------+---------+
                            |
                       Signal command --> MQTT --> [Jetson Nano GPIO] --> [LED x4]

  STORAGE/API      [PostgreSQL + TimescaleDB] | [FastAPI REST + WebSocket]
  PRESENTATION     [React Dashboard] Live | Analytics | Benchmarks | Events
```

### 7.2 Graceful Degradation

```
If MFSTNet inference fails:
  PPO falls back to raw vehicle counts only (no fusion predictions)
  Dashboard displays "MFSTNet offline" badge

If MQTT drops (edge <-> server):
  Jetson Nano detects timeout > 10 seconds
  Switches to embedded Webster rule-based algorithm (local fallback)
  Logs event; resumes PPO + MFSTNet when connectivity restores
```

---

## 8. MFSTNet — Core Architecture Specification

### 8.1 Architecture Overview

```
================================================================
STAGE 1: DUAL-PATH SPATIAL ENCODING (Per Frame, Per Timestep)
================================================================

  Input Frame [B, 3, 224, 224]
       |
       +──────────────────────────────────────+
       |                                      |
  CNN Encoder (ResNet-50)           ViT Encoder (DINOv2 ViT-S/14)   <-- v1.2 A12
  ImageNet pretrained               Self-supervised (LVD-142M)
                                    [ViT-S/16 supervised = ablation arm BB-1]
  Avgpool + Flatten + Linear        Patch tokens + CLS + Linear
  F_cnn: [B, N_c, D]               F_vit: [B, N_v, D]

  SPATIAL GRID ALIGNMENT  (v1.2 amendment A24 -- REQUIRED before Stage 2)
    CNN : [B, 2048, 7, 7]          -> 1x1 Linear -> [B, D, G, G]
    ViT : [B, N_v, 384]            -> drop CLS -> reshape to its native
          grid (16x16 for patch-14 at 224) -> bilinear resize to GxG
          -> Linear -> [B, D, G, G]
    Both branches flatten to [B, G*G, D] with G*G tokens each.
    G is a config value; default G = 7.  See A24 note below.


================================================================
STAGE 2: GATED BIDIRECTIONAL CROSS-ATTENTION
================================================================

  CrossAttn A:  Q=F_cnn, K/V=F_vit  -->  Z_A
  "Local features ask: what global context is relevant?"

  CrossAttn B:  Q=F_vit, K/V=F_cnn  -->  Z_B
  "Global context asks: what local detail matters here?"

  Both Z_A and Z_B are [B, G*G, D] because A24 aligned the grids.

  GATING (scene-adaptive weighting):
    g = sigmoid( Linear( concat(Z_A, Z_B) ) )      # concat on feature axis
    F_fused = g x Z_A + (1 - g) x Z_B              # elementwise
    F_fused = LayerNorm(F_fused + residual)
    F_fused: [B, G*G, D] -> reshape [B, D, G, G] for ROI pooling below

    PER-LANE ROI POOLING  (v1.2 amendment A8 -- replaces Global AvgPool)
      For each lane L in {N,S,E,W}:
        F_L = ROIPool(F_fused, polygon_L)  -->  [B, D]
      Output: [B, 4, D]

      Rationale: Global AvgPool collapses all spatial information, so a
      shared head applied 4x to the same vector yields 4 IDENTICAL
      predictions. ROI pooling makes each lane read its own image region.
      Sources with fewer than 4 visible approaches work without padding.
      See docs/02-design/HLD-detection-corpus-pipeline.md section 6.

> **v1.2 amendment A24 — the two branches did not have the same number of tokens.**
>
> A cross-attention layer returns one output per **query**. So `CrossAttn A` (queries = CNN) returns
> as many tokens as the CNN supplies, and `CrossAttn B` (queries = ViT) returns as many as the ViT
> supplies. At 224×224:
>
> | Branch | Tokens | Z output |
> |---|---|---|
> | ResNet-50, final conv 7×7 | **49** | `Z_A` = [B, 49, D] |
> | ViT-S/16 (original spec) | 196 + CLS = **197** | `Z_B` = [B, 197, D] |
> | DINOv2 ViT-S/14 (current) | 256 + CLS = **257** | `Z_B` = [B, 257, D] |
>
> `g·Z_A + (1−g)·Z_B` is elementwise and requires identical shapes. **49 ≠ 197 and 49 ≠ 257, so the
> gate as written cannot execute.** This defect predates A12 — it was present in v1.0 with the
> supervised ViT and is not a consequence of switching to DINOv2.
>
> Per-lane ROI pooling (A8) has a second, related requirement: pooling a *region* needs a spatial
> feature **map**, and a flat sequence of 257 tokens is not one until it is reshaped to its grid.
>
> One change fixes both: **align both branches onto a shared G×G grid before Stage 2.**
>
> **Choosing G.** Attention cost scales with the square of the token count:
>
> | G | Tokens | Cost per batch of 32 × T=60, one direction |
> |---|---|---|
> | **7** (default) | 49 | **1.2 G MAC** |
> | 14 | 196 | 18.9 G MAC — **16×** |
> | 16 (ViT native) | 256 | 32.2 G MAC — 27× |
>
> Cross-attention is trainable, so it runs every epoch and is **not** covered by the ADR-005 feature
> cache. On a 6 GB RTX 4050, G=7 is the affordable choice and is the default.
>
> **The cost of G=7 is ROI granularity.** A lane occupying a quarter of the frame covers roughly 12
> of 49 cells; small or distant approaches may cover only two or three. If the Week-2 pilots show
> lanes occupying a small share of the frame, raise G to 14 and accept the compute. **Do not
> hardcode G** — it is a config value for exactly this reason.


  Gate semantics:
    g --> 1.0: Dense/chaotic traffic  --> trust CNN local patterns more
    g --> 0.0: Sparse/structured flow --> trust ViT global context more


================================================================
STAGE 3: HYBRID TEMPORAL MODELING
================================================================

  Sequence: [F_fused_1, ..., F_fused_T]  Shape: [B, T=60, D]

  BiLSTM (Short-range):
    2 layers | hidden=128 | bidirectional | Dropout=0.2
    Output: H_bilstm [B, T, 256]
    Captures: frame transitions, queue build-up, arrival patterns

  Temporal Self-Attention (Long-range):
    2 Transformer encoder layers | nhead=4 | d_ff=512 | Dropout=0.1
    + Sinusoidal positional encoding
    Output: H_temporal [B, T, 256]
    Captures: peak-hour cycles, wave propagation, recurring patterns

  Temporal Attention Pooling:
    alpha = softmax( Linear(H_temporal) )
    h = sum(alpha_t x H_temporal_t)
    Output: h [B, 256]  -- NOT just last hidden state


================================================================
STAGE 4: TASK HEADS
================================================================

  h [B, 4, 256]   <-- one vector PER LANE from ROI pooling (A8)
      |
      +---> Congestion Head (per lane, shared weights)
      |       Linear(256->128) -> ReLU -> Dropout(0.1) -> Linear(128->3)
      |       Applied to each lane's own feature --> LOW / MEDIUM / HIGH
      |       Output: [B, 4, 3]
      |
      |     (Heads below consume the mean over lanes, h_bar [B, 256])
      |
      +---> PPO State Embedding
      |       Linear(256->64) --> auxiliary input to RL agent
      |
      +---> Emergency Detection Head
              Linear(256->64) -> ReLU -> Linear(64->1) -> Sigmoid
```

### 8.2 Model Dimensions

| Hyperparameter | Value | Rationale |
|---|---|---|
| D (shared embedding dim) | 256 | Balance expressiveness and compute |
| T (sequence length) | 60 timesteps | 5 min at 5s intervals |
| BiLSTM hidden | 128 (x2 bidir = 256) | Standard for sequence modeling |
| BiLSTM layers | 2 | Depth without vanishing gradient |
| Temporal Attn heads | 4 | D=256 --> d_k=64 per head |
| Temporal Attn layers | 2 | Lightweight; avoids overfitting |
| Dropout | 0.1-0.2 | Regularization for generalization |

### 8.3 Total Parameter Estimate

| Component | Trainable Params (approx.) |
|---|---|
| ResNet-50 (frozen backbone, linear head only) | ~0.5M |
| ViT-Small (frozen backbone, linear head only) | ~0.5M |
| Gated Bidirectional Cross-Attention | ~1.5M |
| BiLSTM (2 layers, hidden=128, bidir) | ~0.8M |
| Temporal Self-Attention (2L, 4H) | ~0.5M |
| Attention pooling + Task heads | ~0.3M |
| **Total Trainable (frozen backbones)** | **~4.1M** |

Feasible on Google Colab T4 GPU. Training: 10-16 hours for 100 epochs.

### 8.4 Training Configuration

```yaml
d_model:            256
n_heads:            4
bilstm_hidden:      128
bilstm_layers:      2
temporal_layers:    2
dropout:            0.1
T:                  60
prediction_horizon: 12          # 60s ahead (12 x 5s)
num_classes:        3           # LOW, MEDIUM, HIGH
batch_size:         32
learning_rate:      1.0e-4
optimizer:          AdamW
weight_decay:       1.0e-4
scheduler:          CosineAnnealingLR
epochs:             100
patience:           15
loss:               CrossEntropyLoss (inverse-frequency class weights)
seed:               42
train_val_test:     [0.60, 0.20, 0.20]
freeze_backbone:    true
unfreeze_epoch:     null        # v1.2 A12 - was 30; see below
precision:          bf16        # v1.2 A12
pooling:            roi_per_lane  # v1.2 A8 - was global_avg
```

> **v1.2 amendment A12 — backbone adaptation.** `unfreeze_epoch: 30` is retired. R4 predicts
> unfreezing will overfit on a dataset this size, so the plan scheduled an action it expected to
> fail; unfreezing is also incompatible with the ADR-005 feature cache. Backbone adaptation is now a
> **separate Week-15 experiment** using **LoRA (r=8, attention projections)** on the ViT branch,
> reported as a three-way comparison — frozen / LoRA / full fine-tune — which satisfies the
> comparison §20 L4 already promises. See
> [ADR-007](decisions/ADR-007-backbones-and-training-recipe.md).

### 8.6 Training Corpus Construction

> **Added in v1.1 (amendment A1).** Rationale and alternatives:
> [ADR-002](decisions/ADR-002-mfstnet-training-corpus.md).

MFSTNet consumes sequences of shape `[B, T=60, 3, 224, 224]` labelled with per-lane congestion at
t+60s. IndiaTrafficNet (§12) is a *detection* dataset of de-duplicated still frames and cannot supply
these. The corpus is instead constructed by auto-labelling real video with the fine-tuned detector.

> **v1.2 amendment A15 — window arithmetic corrected.** The original text placed the label at
> `t+60s`, which lies **inside** the 295-second observation window. That is not forecasting: the
> model would read a frame it had already observed, validation accuracy would look excellent, and the
> deployed model would fail. It also made the stated minimum clip length (5 min) shorter than one
> sample requires, so the HLD's "skip clips shorter than window + horizon" rule would have discarded
> the entire corpus. Both are corrected below.

**Timing, defined once and normatively:**

```
t0                     window start
t_end  = t0 + 295 s    last OBSERVED frame   (60 frames × 5 s spacing = 59 × 5 = 295 s)
t_label = t_end + 60 s = t0 + 355 s          prediction target — strictly AFTER t_end
minimum usable clip    = 355 s ≈ 6 min       (+ one frame margin)
```

```
Continuous recording session (own footage, retained offline only)
        │
        ├─ sample every 5s from t0 → 60 frames → resize 224×224 ──────→  X  [T=60, 3, 224, 224]
        │       covering  t0 … t0+295s
        │
        └─ fine-tuned YOLOv8 counts vehicles per lane per frame
                 │
                 └─ count at t0+355s → §14.1 thresholds ─────────────→  Y  ∈ {0,1,2}⁴
                     (60 s after the LAST observed frame)   LOW <5 | MED 5–15 | HIGH >15
```

| Parameter | Value | Rationale |
|---|---|---|
| **Minimum clip length** | **≥6 min (360 s) continuous** | One sample needs 355 s. **A 5-minute clip yields zero sequences.** Recording protocol must state ≥6 min; ≥30 min preferred |
| Sequence stride | 30 s | `(D − 355)/30 + 1` sequences from a clip of duration D. One continuous hour → ~109 |
| Label source | Fine-tuned YOLOv8 counts | Same detector as FR-D08; recorded per experiment |
| Label rule | §14.1 count thresholds | No new thresholds introduced |
| Split unit | **Source clip, never sequence** | Overlapping windows in both train and test would leak (§2.5.1) |
| Split ratio | 60/20/20 (§8.4) | Applied over clips, then sequences inherit their clip's split |
| Verification subset — *v1.2 A9, A18* | **Test split only: ~150 sequences stratified by density band, plus 25 double-counted.** Test-split density bands are re-derived from the **human** counts, not the detector's | Was "500 spread across the corpus" — 2,000 manual lane counts (~17 h) producing a number that changed no decision. Concentrating a smaller budget on the test split costs less and buys a **clean evaluation set**, which is what breaks the circularity in §14.5 A11. Train/val stay auto-labelled; the double-count yields inter-rater agreement |

**Label noise is a known property of this corpus, not a defect to be hidden.** Detection error
propagates into ground truth, most severely for under-represented classes (§20 L7). Per-class
detector recall is reported alongside MFSTNet per-class F1 so inherited error is separable from model
error.

**Contingency.** If the corpus is under ~2,000 sequences at Week 12, add SUMO-rendered pretraining
followed by real fine-tuning. This is a fallback, not a plan — it introduces a domain gap requiring
defence in the viva.

---

## 9. Functional Requirements

### 9.1 Dataset Collection

| ID | Requirement | Priority |
|---|---|---|
| FR-D01 | Team SHALL collect raw video from minimum 6 real Indian urban intersections | Must Have |
| FR-D02 | Footage SHALL cover peak hours (8-10am, 5-8pm) AND off-peak (2-4pm) | Must Have |
| FR-D03 | All footage SHALL be annotated on Roboflow with 8 vehicle classes | Must Have |
| FR-D04 | Annotated dataset SHALL contain minimum 12,000 frames | Must Have |
| FR-D05 | Dataset SHALL be split 70/15/15 with stratified class distribution | Must Have |
| FR-D06 | Dataset SHALL be published on Roboflow Universe AND Kaggle under CC BY 4.0 | Must Have |
| FR-D07 | Dataset SHALL include a datasheet documenting collection conditions and known biases | Must Have |
| FR-D08 | System SHALL train YOLOv8s on IndiaTrafficNet and report mAP@50 and mAP@50:95 per class | Must Have |
| FR-D09 | System SHALL compare IndiaTrafficNet FT vs. COCO-pretrained baseline on Indian test set | Must Have |

### 9.2 SUMO Simulation

| ID | Requirement | Priority |
|---|---|---|
| FR-S01 | A SUMO simulation environment SHALL be created for a 4-way Indian urban intersection | Must Have |
| FR-S02 | Traffic flow parameters SHALL be calibrated from IndiaTrafficNet count data | Must Have |
| FR-S03 | Simulation SHALL expose TraCI Python API for RL agent interaction | Must Have |
| FR-S04 | All four signal control methods SHALL run in the same SUMO environment | Must Have |

### 9.3 RL Signal Control Agent

| ID | Requirement | Priority |
|---|---|---|
| FR-R01 | System SHALL implement PPO agent using Stable-Baselines3 | Must Have |
| FR-R02 | State space SHALL be **16-dimensional** per §13.1: per-lane vehicle count, queue length, current phase, phase remaining, MFSTNet prediction per lane, emergency flag — *v1.2 A16* | Must Have |
| FR-R03 | Action space SHALL be discrete: next phase AND green duration (10/20/30/45/60/90 seconds) | Must Have |
| FR-R04 | Reward SHALL penalize avg wait, include emergency bonus, penalize starvation (>180s) | Must Have |
| FR-R05 | Agent SHALL be trained for minimum 500,000 timesteps | Must Have |
| FR-R06 | System SHALL run minimum 30 independent evaluation runs per method | Must Have |
| FR-R07 | Results SHALL report mean, std, 95% CI per method per metric | Must Have |
| FR-R08 | Statistical significance via paired t-test at alpha=0.05, with Cohen's d | Must Have |

### 9.4 MFSTNet Model

| ID | Requirement | Priority |
|---|---|---|
| FR-M01 | System SHALL implement CNN encoder (ResNet-50, pretrained ImageNet) | Must Have |
| FR-M02 | System SHALL implement ViT encoder (**DINOv2 ViT-S/14** via timm; supervised ViT-S/16 retained as ablation arm BB-1) — *v1.2 A12* | Must Have |
| FR-M03 | System SHALL implement bidirectional cross-attention fusion | Must Have |
| FR-M04 | System SHALL implement gating: g=sigmoid(Linear([Z_A;Z_B])); F=g*Z_A+(1-g)*Z_B | Must Have |
| FR-M05 | System SHALL implement BiLSTM temporal encoder (2 layers, hidden=128, bidir) | Must Have |
| FR-M06 | System SHALL implement Temporal Self-Attention on BiLSTM outputs (2L, 4H) | Should Have |
| FR-M07 | System SHALL implement temporal attention pooling over all T timesteps | Should Have |
| FR-M08 | System SHALL output congestion level per lane (LOW/MEDIUM/HIGH) 60s ahead | Must Have |
| FR-M09 | System SHALL benchmark MFSTNet vs. ALL baselines in Section 14.3 | Must Have |
| FR-M10 | System SHALL conduct ablation study across 7 configurations | Must Have |
| FR-M11 | Evaluation metrics: Accuracy, Macro F1, Per-class Precision/Recall, Latency | Must Have |
| FR-M12 | Trained model SHALL be exported in ONNX format | Must Have |
| FR-M13 | Runtime inference latency SHALL be <=150ms on server CPU | Must Have |
| FR-M14 | MFSTNet output SHALL be passed as auxiliary input to the PPO state vector (indices 11–14). During SUMO training a noise-calibrated surrogate stands in — [ADR-009](decisions/ADR-009-ppo-forecast-surrogate.md) — *v1.2 A16* | Must Have |

### 9.5 Perception Pipeline

| ID | Requirement | Priority |
|---|---|---|
| FR-P01 | System SHALL run YOLOv8s inference on Jetson Nano at >=10 fps | Must Have |
| FR-P02 | System SHALL detect and count vehicles per lane | Must Have |
| FR-P03 | System SHALL detect emergency vehicles and trigger preemption immediately | Must Have |
| FR-P04 | Emergency trigger SHALL require confidence >=0.75 AND >=2 consecutive detections | Must Have |

### 9.6 Signal Control and Actuation

| ID | Requirement | Priority |
|---|---|---|
| FR-A01 | PPO agent SHALL receive live counts + MFSTNet predictions and output signal commands | Must Have |
| FR-A02 | Signal commands SHALL travel server to Jetson Nano via MQTT | Must Have |
| FR-A03 | Min green: 10s; Max green: 90s | Must Have |
| FR-A04 | All-red clearance: minimum 3 seconds between transitions | Must Have |
| FR-A05 | Emergency preemption SHALL override PPO: clear emergency lane green within 3 seconds | Must Have |
| FR-A06 | MQTT dropout SHALL trigger automatic Webster fallback within 10 seconds | Must Have |

### 9.7 Dashboard and Analytics

| ID | Requirement | Priority |
|---|---|---|
| FR-UI01 | Dashboard SHALL display live signal state, vehicle count, MFSTNet prediction per lane | Must Have |
| FR-UI02 | Dashboard SHALL display emergency alert banner during active preemption | Must Have |
| FR-UI03 | Analytics page SHALL show historical vehicle counts (1hr/6hr/24hr) | Must Have |
| FR-UI04 | Analytics page SHALL show MFSTNet prediction accuracy tracker | Must Have |
| FR-UI05 | Analytics page SHALL show gate value tracker (CNN vs. ViT reliance over time) | Must Have |
| FR-UI06 | Benchmark page SHALL show SUMO statistical results table with CI for all methods | Must Have |
| FR-UI07 | Benchmark page SHALL show MFSTNet ablation study results table | Must Have |
| FR-UI08 | Event log SHALL show all signal events with timestamp and source | Must Have |
| FR-UI09 | Dashboard SHALL allow authenticated manual signal override | Should Have |
| FR-UI10 | Analytics data SHALL be exportable as CSV | Could Have |

---

## 10. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | YOLOv8 inference on Jetson Nano | >=10 fps at 640x640 |
| NFR-02 | MFSTNet inference on server CPU (ONNX) | <=150ms per prediction batch |
| NFR-03 | PPO agent action selection | <=50ms per decision |
| NFR-04 | MQTT end-to-end latency | <=200ms |
| NFR-05 | Dashboard WebSocket refresh | <=2 seconds |
| NFR-06 | Prototype uptime (4-hour evaluation) | >=95% |
| NFR-07 | All random seeds SHALL be fixed and documented (PyTorch, NumPy, SB3) | Critical |
| NFR-08 | Full experiment code SHALL be on GitHub with requirements.txt | Critical |
| NFR-09 | All 30-run raw benchmark results SHALL be committed as CSV files | Critical |
| NFR-10 | MFSTNet ablation raw results SHALL be committed as CSV files | Critical |
| NFR-11 | MQTT broker: username/password authentication | Security |
| NFR-12 | Dashboard: JWT-based login, 24h token expiry | Security |
| NFR-13 | Raw video frames: NOT transmitted over network or stored to disk **by the deployed runtime**. Only derived counts and predictions leave the edge device. Does not govern the offline training corpus (§8.6), which is retained locally, excluded from version control, and never published | Privacy |

---

## 11. Technology Stack

### 11.1 AI / ML Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Object Detection | YOLOv8 (Ultralytics) | v8.2+ | Vehicle detection on edge |
| CNN Encoder | ResNet-50 (torchvision) | — | Local spatial feature extraction |
| ViT Encoder | ViT-Small/16 (timm) | 0.9+ | Global spatial feature extraction |
| Cross-Attention | PyTorch nn.MultiheadAttention | 2.x | CNN-ViT bidirectional fusion |
| BiLSTM | PyTorch nn.LSTM (bidirectional=True) | 2.x | Short-range temporal modeling |
| Temporal Attention | PyTorch nn.TransformerEncoderLayer | 2.x | Long-range temporal modeling |
| ML Framework | PyTorch | 2.x | All model training |
| RL Library | Stable-Baselines3 | 2.x | PPO agent |
| RL Environment | SUMO + TraCI | 1.19+ | Traffic simulation |
| RL Monitoring | TensorBoard | 2.x | Training visualization |
| Model Export | ONNX Runtime | 1.16+ | Portable inference |
| Annotation | Roboflow | — | Dataset labeling |
| Experiment Tracking | MLflow | 2.x | Model versioning + metric logging |

### 11.2 Backend Stack

| Component | Technology | Purpose |
|---|---|---|
| Edge Runtime | Python 3.10+ | YOLOv8 inference pipeline |
| Image Processing | OpenCV 4.9+ | Frame capture and preprocessing |
| MQTT Client | Paho-MQTT | Edge-server messaging |
| MQTT Broker | Mosquitto 2.x | Message routing |
| API | FastAPI 0.11x | REST + WebSocket |
| Database | PostgreSQL 15 + TimescaleDB | Time-series storage |
| Containerization | Docker + Compose | Reproducible deployment |

### 11.3 Frontend Stack

| Component | Technology | Purpose |
|---|---|---|
| Framework | React + Vite (React 18) | Dashboard SPA |
| Charts | Recharts 2.x | Analytics visualization |
| Real-time | Native WebSocket | Push-based updates |
| State | Zustand 4.x | State management |
| Styling | CSS Modules + CSS Variables | Dark mode, scoped styles |

---

## 12. Novel Contribution 1 — IndiaTrafficNet Dataset

> ### ⚠ PROPOSED CHANGE — amendment A13, awaiting faculty guide sign-off
>
> [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) proposes replacing the 12,000-frame
> public-road campaign below with **curate-then-collect**: a harmonised benchmark assembled from
> licensed public sources, plus a 1,500–3,000 frame set collected on campus with written permission
> and automated face/plate blurring.
>
> Two reasons. **Effort:** ~20–60 objects per peak-hour frame means 12,000 frames is ≈360,000 boxes —
> roughly a third of the team's total capacity for the semester
> ([FEASIBILITY-AUDIT §3.1](FEASIBILITY-AUDIT.md)). **Exposure:** publishing frames of identifiable
> people under CC BY 4.0 raises unresolved DPDP Act 2023 questions, and seeking municipal permission
> has unbounded lead time.
>
> **This changes M1's acceptance criterion, so it is not adopted unilaterally.** Until signed off,
> §12.0 and §12.1 below remain in force.

### 12.0 Two-Track Strategy

> **Added in v1.1 (amendment A2).** Rationale and alternatives:
> [ADR-001](decisions/ADR-001-two-track-dataset-strategy.md).

The collection plan in §12.1 is unchanged in substance but no longer sits on the critical path.
Two tracks run concurrently:

| Track | Weeks | Purpose |
|---|---|---|
| **A — Bootstrap** | 2 onward | Fine-tune YOLOv8s on a public Indian traffic dataset (IDD, or a licence-verified Roboflow Universe set) so detection, SUMO calibration, and §8.6 corpus generation are unblocked immediately |
| **B — IndiaTrafficNet** | 2–8, per §12.1 | Collection, annotation, and public release. Weights swap in at Week 8 |

The swap yields a comparative experiment — public-pretrained vs. IndiaTrafficNet-fine-tuned mAP —
that strengthens FR-D09 beyond the ≥10% threshold M2 requires.

Two sets of detection weights exist between Weeks 2 and 8. Every experiment recorded in that window
**must** state which weights produced it (`detector_weights` field, experiment record template).
Class taxonomies will not match the eight target classes; the mapping table lives in Execution Manual
Part 2, and unmapped source classes train as background until the Week 8 swap.

### 12.1 Collection Plan

| Step | Activity | Target | Timeline |
|---|---|---|---|
| 1 | Identify 6 urban intersections | 6 locations | Week 2-3 |
| 2 | Record 2-3 hours video per intersection, peak + off-peak | ~15 hours raw footage | Week 3-5 |
| 3 | Extract frames at 2 fps | ~108,000 raw frames | Week 5 |
| 4 | Filter: blurred, overexposed, near-duplicate | ~15,000 clean frames | Week 5-6 |
| 5 | Annotate on Roboflow: bounding boxes, 8 classes | 12,000 annotated frames | Week 6-8 |
| 6 | Augmentation: flip, brightness, blur, mosaic | 3x expansion | Week 8 |
| 7 | Publish on Roboflow Universe + Kaggle | Public release | Week 8 |

### 12.2 Class Definitions

| Class | Description | Est. % |
|---|---|---|
| car | Passenger cars, taxis, SUVs | 35% |
| motorcycle | Bikes, scooters, mopeds | 30% |
| auto-rickshaw | Three-wheeled CNG/petrol autos | 15% |
| e-rickshaw | Electric three-wheelers | 5% |
| bus | City buses, mini-buses | 3% |
| truck | Heavy goods vehicles, tempos | 4% |
| pedestrian | Persons on foot | 7% |
| cattle | Cows, buffalo, stray animals | 1% |

---

## 13. Novel Contribution 2 — RL Signal Control via SUMO and PPO

### 13.1 RL Agent Formulation

**State Space (16 dimensions)** — *v1.2 amendment A16, [ADR-009](decisions/ADR-009-ppo-forecast-surrogate.md)*

```python
state = np.array([
    count_N / 50, count_S / 50, count_E / 50, count_W / 50,   #  0-3
    queue_N / 200, queue_S / 200, queue_E / 200, queue_W / 200,  #  4-7
    phase_NS, phase_EW,                                        #  8-9
    phase_remaining / 90,                                      # 10
    mfst_pred_N / 2, mfst_pred_S / 2, mfst_pred_E / 2, mfst_pred_W / 2,  # 11-14
    emergency_flag,                                            # 15
])
```

> **A16 — `mfst_gate_mean` removed; 17 → 16 dimensions.** The gate is a property of visual fusion and
> has **no analogue in SUMO**, so it would be constant throughout the 500K training steps — a dead
> input that consumes parameters and receives no gradient. Removing it is free now because no PPO
> checkpoint exists; it stops being free the moment one is written. The gate remains a research
> artifact (FR-M04), a logged output, and a dashboard feature (FR-UI05) — it is simply not policy
> input.
>
> **Contract rule (unchanged in spirit):** if MFSTNet is unavailable at inference, **zero indices
> 11–14**. Never shorten the vector.

> **A16 — where the forecast comes from during training.** The PRD previously specified these fields
> without saying what produces them while PPO trains inside SUMO, which has no camera. Per ADR-009
> they are produced by an **oracle corrupted by MFSTNet's measured confusion matrix** (from the
> human-verified test split), and three policies are trained and benchmarked:
>
> | Arm | Indices 11–14 | Answers |
> |---|---|---|
> | P-none | zeroed | Does forecast information help at all? (also the FR-A06 degraded-mode result) |
> | P-real | noise-calibrated surrogate | What is the realistic benefit? |
> | P-oracle | SUMO ground truth | The ceiling, and how steeply benefit depends on forecast quality |
>
> **Scheduling dependency:** P-real needs MFSTNet's confusion matrix, so M7's final runs now depend
> on M5. Develop against P-oracle for M6.

**Action Space:** 12 discrete actions (NS/EW x 6 green durations: 10/20/30/45/60/90s)

**Reward Function:**

```python
def compute_reward(traci, emergency_cleared):
    avg_wait  = mean([traci.lane.getWaitingTime(l) for l in lanes])
    avg_queue = mean([traci.lane.getLastStepHaltingNumber(l) for l in lanes])
    emergency_bonus    = 10.0 if emergency_cleared else 0.0
    starvation_penalty = sum(5.0 for l in lanes if traci.lane.getWaitingTime(l) > 180)
    return -avg_wait - 0.5 * avg_queue + emergency_bonus - starvation_penalty
```

**PPO Hyperparameters:**

```yaml
algorithm: PPO | policy: MlpPolicy | learning_rate: 3.0e-4
n_steps: 2048 | batch_size: 64 | n_epochs: 10
gamma: 0.99 | gae_lambda: 0.95 | clip_range: 0.2
ent_coef: 0.01 | total_timesteps: 500000 | seed: 42
```

### 13.2 Evaluation Protocol

```
For each method in [Fixed, Webster, Random, PPO]:
  For seed in range(1, 31):
    Run SUMO for 3600 simulated seconds
    Record: mean_wait_time, mean_queue_length, throughput,
            max_wait_time (95th pct), emergency_clearance_time

  Compute: mean, std, 95% CI (bootstrap, 10000 resamples)

Statistical tests:
  Paired t-test: PPO vs Fixed | PPO vs Webster
  alpha=0.05 | Effect size: Cohen's d
```

---

## 14. Novel Contribution 3 — MFSTNet Multimodal Fusion Model

### 14.1 Problem Formulation

```
Given:   Video frames F_1,...,F_T over last 5 minutes
         T = 60 timesteps at 5s intervals

Predict: Y in {0,1,2}^4   Congestion per lane, 60 seconds ahead
         0 = LOW   (< 5 vehicles)
         1 = MEDIUM (5-15 vehicles)
         2 = HIGH  (> 15 vehicles)
```

### 14.2 Why Gated Cross-Attention Generalizes Better

| Traffic Scenario | CNN vs ViT Importance | Gate Behavior |
|---|---|---|
| Dense, chaotic Indian peak-hour | CNN >> ViT | g --> 1.0 |
| Sparse, structured off-peak | ViT >> CNN | g --> 0.0 |
| Mixed, partially obstructed | Both matter | g --> 0.5 |
| Unseen intersection geometry | ViT adapts | g adjusts dynamically |

### 14.3 Baseline Comparison Models

> **v1.2 amendment A21 — this table is the single authoritative baseline list.** §3 previously listed
> a different set ("CNN-only LSTM, ViT-only LSTM, vanilla LSTM, GRU, CongestFormer") and §14.4's
> ablation configs A–G overlap both. Where they disagree, **this table governs**; §3 is prose and
> §14.4 is an ablation of *this work*, not a baseline list. The RTM pins the mapping.

| Model | Architecture | What it isolates |
|---|---|---|
| **MFSTNet (full)** | CNN+ViT+GatedCrossAttn+BiLSTM+TempAttn | This work |
| CNN + BiLSTM | ResNet-50 only | Value of adding ViT |
| ViT + BiLSTM | ViT-Small only | Value of adding CNN |
| Concat + BiLSTM | CNN+ViT concatenated (no attention) | Value of cross-attention |
| CrossAttn (1-dir) + BiLSTM | CNN->ViT only | Value of bidirectionality |
| CrossAttn (bidir, no gate) + BiLSTM | No gating | Value of gating |
| CongestFormer | Transformer-only on count sequences | Previous STMS baseline |
| LSTM | 2-layer LSTM on count sequences | Classic baseline |
| GRU | 2-layer GRU on count sequences | Classic baseline |
| Naive | Last-value prediction | Lower bound |

### 14.4 Ablation Study

| Config | CNN | ViT | CrossAttn | Gate | BiLSTM | TempAttn |
|---|---|---|---|---|---|---|
| A — CNN only | YES | NO | NO | NO | YES | NO |
| B — ViT only | NO | YES | NO | NO | YES | NO |
| C — Naive Fusion | YES | YES | Concat | NO | YES | NO |
| D — 1-dir CrossAttn | YES | YES | 1-dir | NO | YES | NO |
| E — Bidir (no gate) | YES | YES | Bidir | NO | YES | NO |
| F — + TempAttn (no gate) | YES | YES | Bidir | NO | YES | YES |
| **G — Full MFSTNet** | YES | YES | Bidir | YES | YES | YES |
| **H — Linear probe** *(v1.2 A22)* | YES | YES | NO | NO | **NO** | NO |

> **v1.2 amendment A22 — config H, the missing floor.** Configs A–G all contain a BiLSTM, so none of
> them answers the cheapest question a reviewer asks of a frozen-backbone model: *does the temporal
> machinery do anything at all?*
>
> Config H is frozen features → per-lane ROI pool → mean over the 60 timesteps → linear head. No
> fusion, no recurrence, no attention. It is the standard linear probe that every frozen-backbone
> paper is expected to report, and its absence here was an omission.
>
> **If H approaches G, the architecture is unjustified** and that is the finding — reported, not
> buried (BR-19). With cached features it costs minutes.

> **v1.2 amendment A23 — report MFSTNet over multiple seeds.** §8.4 fixes `seed: 42`, and the RL half
> runs 30 seeds with confidence intervals (FR-R07) while the model half reports a single run. A
> two-point macro-F1 gap between ablation configs is meaningless without knowing seed variance.
>
> Run every ablation config at **5 seeds** and report mean ± 95% CI. Feature caching makes this
> nearly free, and most comparable vision work does not do it — so it is another place the protocol
> sits above the field's standard rather than below it.

### 14.5 Evaluation Metrics

| Metric | Description |
|---|---|
| Accuracy | % of lanes correctly classified at t+60s |
| Macro F1-score | Average F1 across LOW/MEDIUM/HIGH |
| Per-class Precision/Recall | Critical for HIGH class |
| Inference Latency | ms per prediction batch on server CPU (ONNX), **with measurement host stated** |
| **Density-stratified macro F1** — *v1.2 A10* | Macro F1 reported separately per density band (low / medium / high), alongside the aggregate |
| **Transition-window recall** — *v1.2 A17* | **The headline metric.** Recall on windows where the label at t_label differs from the label at t_end |
| Persistence rate | % of windows where label(t_label) == label(t_end). Reported for every corpus |

> **v1.2 amendment A17 — persistence degeneracy.** Congestion over a 60 s horizon with three coarse
> classes is highly persistent: for most windows the answer at t+60 s is simply the answer now. If
> that rate is ~90%, the Naive last-value baseline (§14.3) sits near the ceiling, every model ties on
> aggregate accuracy, and the benchmark cannot rank anything. **All the signal lives in transition
> windows.**
>
> Therefore: measure the persistence rate on pilot footage **before building the corpus** (Execution
> Manual §1.2 measurement 4), report it for every corpus, and make **transition-window recall** the
> headline metric with aggregate macro F1 reported alongside. If the transition rate is below 5%,
> the task as specified is degenerate and the horizon or the class boundaries must be revisited
> **before** M4 — this is a corpus-design decision, not a results-interpretation one.
>
> Do **not** oversample transitions in the test split — that changes the operating distribution.
> Report stratified by transition/persistence instead.

> **v1.2 amendment A19 — the bootstrap resample unit.** Sequences drawn from one recording session
> overlap by up to 54 of their 60 frames and are strongly correlated. Resampling *sequences* treats
> them as independent and overstates precision, producing confidence intervals far too narrow.
>
> **Resample source clips, not sequences** (cluster bootstrap). Effective independent *n* is the
> number of source sessions in the split — likely 30–50, not thousands. Report *n* alongside every
> interval. FR-R07's bootstrap over 30 RL seeds is unaffected: those seeds are genuinely independent.

> **v1.2 amendment A20 — gate regularisation contaminates claim C2.** PRD §2.5.1 prescribes adding
> gate-entropy regularisation if the gate collapses. But C2 claims the gate is an *emergent*
> interpretable artifact. A gate regularised into non-collapse is not evidence of emergence, and a
> reviewer will say so.
>
> Report **both arms**: gate without regularisation (whatever it does, including collapse) and gate
> with regularisation. A collapsed gate is a publishable negative result about the mechanism
> (BR-19); a silently regularised one is a finding that does not survive scrutiny.

> **v1.2 amendment A10 — why stratify.** §14.2's hypothesis is that CNN and ViT complement each other
> *in dense chaotic traffic*. In sparse traffic counts are easy and every method should tie. A single
> aggregate metric averages a real density-concentrated effect into invisibility against a strong
> count baseline. `density_band` is recorded per sequence at corpus build time and costs nothing.

> **v1.2 amendment A11 — a caveat on the §14.3 baselines.** LSTM-on-counts, CongestFormer, and Naive
> last-value all consume detector counts, and §8.6 derives the labels from those same counts. Their
> input errors therefore correlate with the label errors and are scored as correct, while MFSTNet
> reads pixels and its independent errors are scored as wrong — biasing the comparison **against**
> MFSTNet. This is why the **test split is human-verified** (A9) while train/val remain
> auto-labelled. Any comparison against these baselines on auto-labelled data is invalid.

---

## 15. Hardware Requirements

### 15.1 Prototype Physical Setup

```
Table-top mock intersection (~60cm x 60cm base):

  [Camera N] on adjustable stand, top-down angle, 50cm height
       |
[LED W] -- [Intersection center] -- [LED E]
       |
  [Camera S]  (Camera E and Camera W on similar stands)

  Jetson Nano 4GB:
    - USB: 4x cameras via USB hub
    - GPIO/Relay: 4-channel relay --> 4x LED modules (R/Y/G each)
    - Wi-Fi: connected to local router

  Central Server (Laptop):
    - MQTT broker (Mosquitto, local)
    - FastAPI + PostgreSQL + TimescaleDB
    - PPO inference (CPU) | MFSTNet inference (CPU, ONNX)
    - React dashboard (localhost:3000)
```

### 15.2 Training Compute

> **Amended in v1.1 (amendment A7).** The table below was written before the team's hardware was
> known and assumes Colab-primary training. Training is now local-first on cached backbone features.
> Rationale: [ADR-005](decisions/ADR-005-local-first-training.md).

**Superseded estimates (Colab-primary):**

| Task | Recommended Hardware | Estimated Duration |
|---|---|---|
| YOLOv8s fine-tuning (100 epochs) | Google Colab Pro T4 GPU | 6-10 hours |
| PPO training (500K timesteps) | Laptop CPU (modern i5+) | 8-12 hours |
| MFSTNet training (100 epochs, ~4M params) | Google Colab T4 GPU | 10-16 hours |
| MFSTNet ablation (7 configs x 100 epochs) | Google Colab T4 GPU | 60-90 hours (parallelize) |

**Current plan.** Primary machine: Acer Predator Helios 16 — i5-13500HX (14C/20T), RTX 4050 Laptop
(6 GB). Colab is retained as overflow.

| Task | Where | Note |
|---|---|---|
| Backbone feature extraction (one-off) | Local GPU | ~350 KB/frame fp16; ~2.5 GB for 10 h of footage |
| MFSTNet training (100 epochs) | Local GPU, **cached features** | Backbones are frozen, so features are identical every epoch |
| MFSTNet ablation (7 configs) | Local GPU, cached features | Configs A–G differ only downstream of the backbones — **one cache serves all seven**. R6's 50-epoch mitigation is no longer required |
| YOLOv8s fine-tuning | Local GPU | Batch 8–16 at 640 fits in 6 GB |
| PPO (500K) + 30-run benchmark | Local CPU | SUMO is single-threaded; 14 cores run seeds in parallel |
| Overflow / parallel seeds | Colab free tier | Same configs, unchanged |

At `batch_size: 32` and `T: 60`, an uncached batch pushes 1,920 frames through both backbones. That
exceeds 6 GB and is tight even on a 16 GB T4 — a property of the architecture, not of the hardware.
Caching removes the constraint. Caches are invalidated by any change to the backbones, input resize,
or normalisation, and must record the git commit and preprocessing config that produced them.

Backbone unfreezing (§8.4 `unfreeze_epoch: 30`) is incompatible with caching and is reclassified as a
separate later experiment on the uncached pipeline, reported as the frozen vs. fine-tuned comparison
§20 L4 already commits to. See pending item P3.

### 15.3 Hardware Budget

> **Amended in v1.1 (amendment A3).** The configuration below is the **aspirational** target, costing
> ₹27,400–39,300 against a project budget of ₹0. It is retained as the documented deployment target.
> The **delivered** configuration is §15.4. Rationale:
> [ADR-003](decisions/ADR-003-laptop-as-edge.md).

| Item | Cost (INR) |
|---|---|
| NVIDIA Jetson Nano 4GB Developer Kit | Rs.12,000 - 15,000 |
| 4x USB Webcam (1080p) | Rs.8,000 - 12,000 |
| 4x LED Traffic Signal Kit (R/Y/G) | Rs.1,500 - 3,000 |
| USB 4-channel Relay Board | Rs.800 - 1,500 |
| MicroSD Card 64GB Class 10 | Rs.600 - 1,000 |
| USB Hub (powered, 4-port) | Rs.500 - 800 |
| Cables, power adapters, stands | Rs.1,000 - 2,000 |
| Google Colab Pro (3 months) | Rs.3,000 - 4,000 |
| **Total Estimated** | **Rs.27,400 - 39,300** |

### 15.4 Delivered Prototype Configuration (₹0 baseline)

> **Added in v1.1 (amendment A3).**

The edge node runs on a team laptop. The MQTT contract (§17), detection pipeline, Webster fallback
(FR-A06), and emergency preemption (FR-A05) are **unchanged** — only the host and the output device
differ.

| Component | Aspirational (§15.3) | Delivered | Effect on requirements |
|---|---|---|---|
| Edge compute | Jetson Nano 4GB | Team laptop (or lab-loaned Jetson/Pi) | NFR-01 measured on laptop, labelled as proxy |
| Cameras | 4× USB webcam | 1 webcam, 4 lanes simulated by region-of-interest split, or 4 looping video files | FR-P02 unchanged; documented in STP |
| Signal output | GPIO relay + LED modules | On-screen four-phase signal panel | FR-A01–FR-A05 logic unchanged; actuation is visual |
| Colab | Pro | Free tier | Mitigated by PRD R6 (50-epoch ablation) |
| **Total** | **Rs.27,400 – 39,300** | **Rs.0** | |

**Reporting rule.** Every latency table states its measurement host. Laptop figures are labelled
proxy measurements, and the absence of on-target validation is declared in the paper's limitations
(§20 L8). A clearly-labelled proxy measurement is acceptable to a reviewer; an unlabelled one is not.

**Upgrade path.** Check department lab inventory first — prior cohorts frequently leave Jetsons and
Pis behind. If one is obtained, LEDs and jumper wires cost under ₹200 and restore the physical
actuation demo.

---

## 16. UI/UX Requirements — Dashboard

### 16.1 Page 1 — Live Monitor

- Intersection schematic: top-down 4-way diagram with real-time R/Y/G signal state
- Per-lane cards (4): camera thumbnail, vehicle count by type, signal state, MFSTNet badge (LOW/MED/HIGH), gate value bar (CNN vs. ViT balance)
- RL Agent panel: current state vector, last action, reward estimate
- Emergency alert banner: full-width blinking during preemption
- System health row: MQTT, Jetson ping, DB, MFSTNet inference ms

### 16.2 Page 2 — Analytics

- Vehicle count over time per lane (1hr/6hr/24hr)
- MFSTNet accuracy tracker (predicted vs. actual, rolling 60s horizon)
- Gate value tracker (CNN vs. ViT reliance over time — unique visualization)
- Peak-hour heatmap (X=hour, Y=lane, color=avg count)
- Wait time comparison bar chart from SUMO results

### 16.3 Page 3 — Research Benchmarks

- SUMO results table (mean +/- 95% CI, all 4 methods, all metrics)
- PPO training curve (episode reward over timesteps)
- MFSTNet benchmark table (Accuracy/F1 for all 10 baselines)
- MFSTNet ablation table (all 7 configurations)
- YOLOv8 comparison table (mAP per class, COCO vs. IndiaTrafficNet FT)

### 16.4 Page 4 — Event Log

- Signal events (timestamp, phase, duration, source: PPO/fallback/manual)
- Emergency events (timestamp, lane, type, confidence, duration)
- CSV export

### 16.5 Design Specifications

| Attribute | Specification |
|---|---|
| Theme | Dark mode; background #0D1117 |
| Accent | Primary: #6366F1 (indigo); Alert: #FF6B35 (orange) |
| Signal colors | GREEN: #22C55E, YELLOW: #EAB308, RED: #EF4444 |
| MFSTNet badges | LOW: #22C55E, MEDIUM: #F59E0B, HIGH: #EF4444 |
| Typography | Inter (body), JetBrains Mono (numbers) via Google Fonts |
| Updates | WebSocket push (no polling) |
| Responsiveness | Desktop-first (1080p+) |

---

## 17. Integration and Communication Protocol

### 17.1 MQTT Topic Schema

```
stms/{intersection_id}/{lane_id}/vehicle_count
  QoS: 1 | Interval: every 5s
  Payload: { "count": 12, "types": {...}, "fps": 12.4, "ts": 1690000000 }

stms/{intersection_id}/{lane_id}/emergency/detect
  QoS: 2 | Trigger: on detection
  Payload: { "type": "ambulance", "confidence": 0.91, "frame_count": 3 }

stms/{intersection_id}/signal/command
  QoS: 1 | Trigger: on RL decision
  Payload: { "phase": "NS_GREEN", "duration": 45, "source": "ppo_agent" }

stms/{intersection_id}/congestion/prediction
  QoS: 0 | Interval: every 5s
  Payload: {
    "predictions": {"N":"HIGH","S":"MED","E":"LOW","W":"LOW"},
    "confidences": {"N":0.87,"S":0.72,"E":0.91,"W":0.88},
    "gate_value":  0.73,
    "model":       "mfstnet_v1",
    "horizon_sec": 60,
    "ts":          1690000000
  }

stms/{intersection_id}/system/heartbeat
  QoS: 0 | Interval: every 10s
  Payload: { "edge_status":"online","mfstnet_active":true,"ppo_active":true }
```

---

## 18. Project Timeline and Milestones

### 18.1 Phase Overview (20 Weeks)

| Phase | Weeks | Key Activities |
|---|---|---|
| Phase 0: Setup | 0-1 | GitHub repo, dev environments, SUMO install, Jetson Nano OS, team roles |
| Phase 1: Data Collection | 2-5 | Video at 6 intersections; frames extracted and filtered |
| Phase 2: Annotation | 5-8 | 12,000+ frames annotated on Roboflow; published publicly |
| Phase 3: YOLOv8 Training | 7-9 | Fine-tuning on Colab; mAP comparison vs. COCO documented |
| Phase 4: SUMO Environment | 6-10 | SUMO intersection built; traffic calibrated from dataset |
| Phase 5: MFSTNet Core | 9-12 | CNN+ViT+CrossAttn+BiLSTM implemented and converging |
| Phase 6: MFSTNet Full + Ablation | 12-14 | Gate + TempAttn added; all ablation configs evaluated |
| Phase 7: PPO Training | 10-13 | Agent trained 500K timesteps; convergence confirmed |
| Phase 8: RL Benchmarking | 13-14 | 30-run evaluation; statistical analysis complete |
| Phase 9: Hardware Prototype | 13-16 | Jetson pipeline live; emergency preemption 10/10 |
| Phase 10: Dashboard | 14-17 | All 4 pages live; WebSocket; benchmark + ablation populated |
| Phase 11: Integration | 17-19 | Full end-to-end test; performance validation; bug fixes |
| Phase 12: Paper and Report | 18-20 | Paper drafted; GitHub cleaned; final report submitted |

### 18.2 Milestones and Acceptance Criteria

| ID | Milestone | Acceptance Criteria | Due |
|---|---|---|---|
| M1 | IndiaTrafficNet Published | 12,000+ frames, 8 classes, live on Roboflow + Kaggle | Week 8 |
| M2 | YOLOv8 Validated | >=10% mAP improvement over COCO on Indian classes | Week 9 |
| M3 | SUMO Running | All 4 signal methods running; traffic calibrated | Week 10 |
| M4 | MFSTNet Core Working | CNN+ViT+CrossAttn+BiLSTM trains and converges | Week 12 |
| M5 | MFSTNet Benchmarked | Macro F1 >= 0.80; ablation table complete | Week 14 |
| M6 | PPO Converged | Reward curve plateaued; TensorBoard stable | Week 13 |
| M7 | RL Benchmark Complete | 30-run results; PPO statistically better (p<0.05) | Week 14 |
| M8 | Hardware Prototype Live | >=10fps; emergency preemption 10/10 <=3s | Week 16 |
| M9 | Dashboard Complete | All 4 pages live, WebSocket, all data fed | Week 17 |
| M10 | Full Integration | PPO + MFSTNet + edge + dashboard running 4 hours | Week 19 |
| M11 | Paper Submitted | Submission receipt from target venue | Week 20 |

---

## 19. Risk Analysis and Mitigation

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Dataset collection access issues | Medium | High | Start with campus intersections; dashcam footage supplement |
| R2 | 12,000-frame annotation bottleneck | High | Medium | Roboflow AI-assisted pre-labeling; weekly velocity tracking |
| R3 | MFSTNet does not converge | Medium | High | Start Phase 1 core only; freeze backbones; transfer learning |
| R4 | ViT overfits on limited data | Medium | Medium | Freeze ViT backbone; only train cross-attention and heads first |
| R5 | Gating mechanism collapses | Medium | Medium | Monitor gate histogram in TensorBoard; add gate entropy regularization |
| R6 | Ablation training too long | High | Medium | Run configs in parallel on Colab; reduce to 50 epochs for ablation |
| R7 | PPO does not outperform Webster | Medium | High | Tune reward shaping; curriculum learning; negative result is publishable |
| R8 | Jetson Nano too slow for YOLOv8s | Medium | High | Downgrade to YOLOv8n; reduce input to 416x416; TensorRT |
| R9 | MQTT instability during demo | Low | Medium | QoS 1/2; pre-test 48h before; pre-recorded video backup |
| R10 | Paper rejected from primary venue | Medium | Low | Submit to backup national conference simultaneously |

---

## 20. Open Issues and Known Limitations

| # | Limitation | Severity | Paper Action |
|---|---|---|---|
| L1 | MFSTNet congestion labels are derived from YOLOv8 detections (§8.6), not human annotation — detector error propagates into ground truth | High | Report the 500-sequence manual-verification label-noise estimate; report per-class detector recall beside per-class F1 so inherited error is separable |
| L1b | RL control results are SUMO-simulated; no live-road validation | High | State all control results are simulation-validated; call for field trials |
| L8 | Edge latency measured on a laptop proxy, not the Jetson deployment target (§15.4) | Medium | Label every latency table with its measurement host; declare absence of on-target validation |
| L2 | Single intersection only | Medium | Scope in abstract; multi-intersection as future work |
| L3 | Nighttime and weather excluded | High | Document in datasheet; quantify expected degradation direction |
| L4 | Frozen backbones limit representation quality | Medium | Report frozen vs. fine-tuned comparison in ablation |
| L5 | Gate interpretability is limited | Low | Report gate value histograms; qualitative analysis in paper |
| L6 | MFSTNet runs on server, not edge — adds MQTT latency | Low | Round-trip <=500ms; acceptable for 10-90s signal cycles |
| L7 | Cattle class imbalance (<200 samples) | Medium | Report per-class mAP with sample count; flag unreliability |

---

## 21. Success Metrics and KPIs

### 21.1 Research KPIs

| KPI | Target | Measurement |
|---|---|---|
| IndiaTrafficNet size | >=12,000 annotated frames | Roboflow dataset stats |
| YOLOv8 mAP improvement (auto-rickshaw) | >=+25% vs. COCO | Test set eval script |
| PPO vs. Fixed avg wait time reduction | >=20%, p<0.05 | Paired t-test, 30 runs |
| PPO vs. Webster avg wait time reduction | >=10%, p<0.05 | Paired t-test, 30 runs |
| MFSTNet macro F1 | >=0.80 | Test set evaluation |
| MFSTNet vs. CNN-only F1 delta | >=+5% | Comparison table |
| MFSTNet vs. ViT-only F1 delta | >=+3% | Comparison table |
| MFSTNet vs. CongestFormer F1 delta | >=+3% | Comparison table |
| Paper submitted | >=1 submission with receipt | Email confirmation |

### 21.2 System KPIs

| KPI | Target |
|---|---|
| Edge inference fps | >=10 fps on Jetson Nano |
| Emergency preemption success rate | 10/10 trials, <=3 seconds |
| Prototype uptime (4-hour session) | >=95% |
| MFSTNet inference latency | <=150ms on CPU (ONNX) |
| Dashboard WebSocket refresh | <=2 seconds |

---

## 22. Publication and Research Output Plan

### 22.1 Target Venues (Priority Order)

| Priority | Venue | Type | Window |
|---|---|---|---|
| 1 | IEEE ITSC 2027 | International Conference | ~Feb-Mar 2027 |
| 2 | CVIP 2026/2027 | National Conference India | ~Jul-Aug 2026 |
| 3 | Transportation Research Part C (Elsevier) | Q1 Journal | Rolling |
| 4 | ICIIT / ICCSIT or similar | National Backup | Rolling |

### 22.2 Suggested Paper Title

> "MFSTNet: Multimodal CNN-ViT Cross-Attention Fusion with Hybrid Temporal Modeling for Adaptive Traffic Signal Control at Indian Urban Intersections"

### 22.3 Open Source Repository Structure

```
github.com/[team]/mfstnet-traffic/
├── README.md | CITATION.cff | LICENSE (Apache 2.0)
├── indiatrafficnet/
│   ├── datasheet.md | download.py | statistics.ipynb
├── detection/
│   ├── train.py | evaluate.py | configs/yolov8s.yaml
├── mfstnet/
│   ├── model.py                <- Full MFSTNet architecture
│   ├── encoders/
│   │   ├── cnn_encoder.py      <- ResNet-50 + projection
│   │   └── vit_encoder.py      <- ViT-Small + projection
│   ├── fusion/
│   │   ├── cross_attention.py  <- Bidirectional cross-attention
│   │   └── gated_fusion.py     <- Gate mechanism
│   ├── temporal/
│   │   ├── bilstm.py           <- BiLSTM temporal encoder
│   │   └── temporal_attn.py    <- Transformer on BiLSTM outputs
│   ├── heads/
│   │   └── congestion_head.py
│   ├── train.py | evaluate.py | ablation.py | export_onnx.py
│   └── configs/mfstnet_config.yaml
├── simulation/
│   ├── intersection.net.xml | traffic_flows/
│   ├── train_ppo.py | evaluate_all.py
│   └── configs/ppo_config.yaml
├── server/
│   ├── main.py | mqtt_bridge.py | ppo_inference.py
│   ├── mfstnet_inference.py    <- ONNX MFSTNet runtime
│   └── db/
├── dashboard/                  <- React + Vite frontend
├── edge/
│   ├── inference.py | mqtt_publisher.py | fallback_webster.py
├── experiments/
│   ├── results/                <- Raw CSVs (30-run + ablation)
│   └── analysis.ipynb
├── models/                     <- Git LFS
├── docker-compose.yml | requirements.txt
```

---

## 23. Future Scope

### 23.1 v2.0 — Near Term (6-12 months post-graduation)

| Feature | Description |
|---|---|
| Multi-intersection MFSTNet | Train on graph of 4 intersections; cross-intersection attention |
| Nighttime dataset | IndiaTrafficNet-Night; low-light and IR augmentation |
| Weather robustness | Synthetic rain/fog via Albumentations; F1 degradation curve |
| Deformable cross-attention | Replace standard MultiheadAttention for spatial precision |
| TensorRT on edge | Deploy MFSTNet on Jetson Nano; target <50ms on edge |
| Field trial | Controlled 2-hour real intersection test with traffic police |

### 23.2 v3.0 — Long Term

| Feature | Description |
|---|---|
| GNN + MFSTNet | Intersection network as graph; GNN for multi-hop coordination |
| Video foundation model | Replace ViT backbone with VideoMAE or DINOv2 |
| V2X integration | 5G C-V2X: direct vehicle-to-intersection communication |
| Federated learning | Multiple agencies train without sharing raw video |

---

## 24. Appendix

### 24.1 Glossary

| Term | Definition |
|---|---|
| MFSTNet | Multimodal Fusion Spatio-Temporal Network — this project's core architecture |
| CNN | Convolutional Neural Network — captures local spatial features |
| ViT | Vision Transformer — captures global spatial context via patch-level attention |
| ResNet-50 | Deep residual CNN backbone, 50 layers (He et al., 2016) |
| ViT-Small/16 | ViT variant: ~22M params, 16x16 patches (Dosovitskiy et al., 2021) |
| timm | PyTorch Image Models library — provides pretrained ViT backbones |
| Cross-Attention | Attention where Q comes from one modality, K/V from another |
| Gated Fusion | Learned scalar gate adaptively weighting two representations |
| BiLSTM | Bidirectional LSTM — processes sequences forward and backward |
| Temporal Self-Attention | Transformer encoder on sequence of BiLSTM hidden states |
| Attention Pooling | Weighted sum over sequence using learned attention weights |
| CongestFormer | Previous Transformer-only congestion predictor (STMS v2.0 baseline) |
| IndiaTrafficNet | Annotated Indian intersection dataset (this project's contribution) |
| PPO | Proximal Policy Optimization — on-policy RL algorithm |
| SUMO | Simulation of Urban Mobility — open-source traffic simulator |
| TraCI | Traffic Control Interface — Python API to control SUMO |
| mAP | Mean Average Precision — standard object detection metric |
| Macro F1-score | Average F1 across classes (equal weight, handles imbalance) |

### 24.2 References

1. He, K. et al. (2016). Deep Residual Learning for Image Recognition. CVPR 2016.
2. Dosovitskiy, A. et al. (2021). An Image is Worth 16x16 Words. ICLR 2021.
3. Vaswani, A. et al. (2017). Attention Is All You Need. NeurIPS 2017.
4. Schulman, J. et al. (2017). Proximal Policy Optimization Algorithms. arXiv:1707.06347.
5. Jocher, G. et al. (2023). Ultralytics YOLOv8. https://github.com/ultralytics/ultralytics
6. Lopez, P.A. et al. (2018). Microscopic Traffic Simulation using SUMO. IEEE ITSC 2018.
7. Webster, F.V. (1958). Traffic Signal Settings. Road Research Technical Paper No.39.
8. Raffin, A. et al. (2021). Stable-Baselines3. JMLR 22(268):1-8.
9. MoRTH (2023). Road Accidents in India 2022. Government of India.
10. TERI (2022). Economic Cost of Traffic Congestion in Indian Cities.

### 24.3 Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| STMS v1.0 | 2026-07-28 | [Team] | Initial draft — rule-based system |
| STMS v2.0 | 2026-07-28 | [Team] | IndiaTrafficNet + PPO/SUMO + CongestFormer |
| MFSTNet v1.0 | 2026-07-31 | [Team] | CNN+ViT+Gated Cross-Attn+BiLSTM+TempAttn replaces CongestFormer |
| MFSTNet v1.1 | 2026-08-07 | [Team] | Amendments A1–A6 — see §24.4 and [PRD-CHANGELOG](PRD-CHANGELOG.md) |
| MFSTNet v1.2 | 2026-08-08 | [Team] | A7 local-first training · A8 per-lane ROI pooling · A9 verification concentrated on test split · A10 density-stratified metrics · A11 baseline-circularity caveat · A12 DINOv2 + LoRA. **A13 (§12 dataset) and A14 (prototype descoping) proposed, awaiting sign-off** |

### 24.4 Cost and Bill of Materials

> **Added in v1.1 (amendment A5).**

The project baseline is **₹0 cash**. Full budget in [SOW §8](SOW.md#8-budget); delivered hardware
configuration in §15.4.

| Category | Baseline | Notes |
|---|---|---|
| Compute (training) | ₹0 | Google Colab free tier; PPO on laptop CPU |
| Compute (edge) | ₹0 | Team laptop + webcam (§15.4) |
| Data platforms | ₹0 | Roboflow free tier, Kaggle, IDD (free registration) |
| Software | ₹0 | All open source — PyTorch, Ultralytics, SB3, SUMO, Mosquitto, FastAPI, React |
| Experiment tracking | ₹0 | MLflow + TensorBoard, self-hosted |
| Paper preparation | ₹0 | Overleaf free tier |
| Conference fee | Deferred | Payable only on acceptance; student rates apply. Not committed at submission |
| **Total committed** | **₹0** | |

Optional upgrades (Jetson, Colab Pro, LEDs) are listed in SOW §8 with their trigger conditions. None
is required to satisfy any Must-priority requirement.

---

*End of PRD — MFSTNet v1.2*
*Classification: Academic Research Project — B.Tech CSE (ML/AI Specialization), Year 4*
*This is a living document — update as implementation progresses and findings emerge.*
