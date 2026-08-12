# Related Work and Novelty Positioning

| | |
|---|---|
| **Date** | 2026-08-08 |
| **Purpose** | Establish what already exists, so the contribution is claimed accurately |
| **Read before** | Writing the paper's method section, and before the viva |
| **Related** | [FEASIBILITY-AUDIT §4-H2](FEASIBILITY-AUDIT.md) |

---

## 1. Why this document exists

A reviewer's first question is *what is new here?* A claim that overreaches gets the paper rejected;
a claim that is precise and defended gets it accepted even when the delta is modest.

The uncomfortable finding of this review: **almost every mechanism in MFSTNet already exists in the
literature.** Dual CNN-ViT branches, bidirectional cross-attention, and gated fusion are each
published, some of them years ago. This does not mean the project is not novel. It means the novelty
must be stated at the right level of abstraction, and the paper must cite the precedents rather than
appear unaware of them.

Being the team that cites Conformer and ViLBERT is respectable. Being the team that a reviewer has to
inform about them is not.

---

## 2. What already exists

### 2.1 Hybrid CNN–Transformer architectures

This is the closest prior art to Stages 1–2, and the most dangerous to ignore.

| Work | What it does | Relation to MFSTNet |
|---|---|---|
| **Conformer** (Peng et al., ICCV 2021) | Parallel CNN and transformer branches with a Feature Coupling Unit exchanging information at every stage | **Nearest neighbour.** Dual-path local+global with bidirectional coupling. Differences: couples at every stage rather than once; no learned gate; no temporal component |
| **CrossViT** (Chen et al., ICCV 2021) | Dual-branch ViT at two token scales, fused by cross-attention on CLS tokens | Establishes cross-attention as a dual-branch fusion mechanism |
| **CoAtNet** (Dai et al., NeurIPS 2021) | Convolution and attention stacked in one network | Shows the local/global complementarity premise |
| **MobileViT** (Mehta & Rastegari, ICLR 2022), **CMT** (Guo et al., CVPR 2022) | Efficient hybrids interleaving conv and attention | Same premise, efficiency-oriented |
| **ConvNeXt** (Liu et al., CVPR 2022) | Modernised pure CNN matching ViT performance | A useful adversarial citation — argues the ViT branch must earn its place. Your ablation config A must answer it |

**Implication.** "We combine CNN and ViT with cross-attention" is not a contribution in 2026. The
ablation is what converts the architecture into evidence — specifically config C (naive concat) vs. E
(bidirectional cross-attention), which isolates whether the attention mechanism does anything at all.

### 2.2 Bidirectional cross-attention is co-attention

| Work | What it does |
|---|---|
| **ViLBERT** (Lu et al., NeurIPS 2019) | Co-attentional transformer layers: each modality's queries attend to the other's keys/values, **in both directions** |
| **LXMERT** (Tan & Bansal, EMNLP 2019) | Cross-modality encoder with bidirectional attention |

Your `Z_A = CrossAttn(Q=CNN, KV=ViT)` and `Z_B = CrossAttn(Q=ViT, KV=CNN)` is co-attention, published
in 2019 for vision-language. Applying it across two *visual* encoders is a different application, not
a new mechanism. Say so.

### 2.3 Gated cross-attention exists too

| Work | What it does |
|---|---|
| **Flamingo** (Alayrac et al., NeurIPS 2022) | Gated cross-attention layers with a learned `tanh` gate controlling how much cross-modal information flows |
| Highway Networks, GRU/LSTM gating | The general principle: learned scalar or vector gates arbitrating between information paths |

Your gate `g = σ(W[Z_A; Z_B])`, `F = g·Z_A + (1−g)·Z_B` is a convex-combination gate. The mechanism
is standard. **What is not standard is treating the gate value as a reported, analysed research
artifact** — FR-UI05, BR-07, and PRD §14.2's density-dependent hypothesis. Flamingo's gates are an
optimisation device; yours is an interpretability claim. That framing is defensible and is the part
worth emphasising.

### 2.4 Traffic forecasting

| Work | Input | Relation |
|---|---|---|
| **STGCN** (Yu et al., IJCAI 2018), **DCRNN** (Li et al., ICLR 2018), **Graph WaveNet** (Wu et al., IJCAI 2019), **ASTGCN** (Guo et al., AAAI 2019) | Loop-detector / probe sensor time series on a road graph | The dominant paradigm. **They do not use vision at all** — they assume instrumented infrastructure |

**This is your strongest genuine gap.** The mainstream traffic-forecasting literature presumes sensor
infrastructure that most Indian intersections do not have. A camera-only forecaster targets a
deployment context those methods cannot serve. Lead with this framing, not with the architecture.

### 2.5 RL traffic signal control

| Work | Contribution |
|---|---|
| **IntelliLight** (Wei et al., KDD 2018) | Deep RL on real-world signal data |
| **PressLight** (Wei et al., KDD 2019) | Max-pressure-informed reward |
| **CoLight** (Wei et al., CIKM 2019) | Multi-intersection coordination via graph attention |
| **FRAP** (Zheng et al., CIKM 2019) | Phase-competition invariance |
| **MPLight** (Chen et al., AAAI 2020) | Scalable pressure-based control at city scale |
| **RESCO** (Ault & Sharon, NeurIPS 2021 D&B) | Standard benchmark for RL signal control |

**Be honest with yourself:** single-intersection PPO on SUMO is a well-solved, heavily benchmarked
problem. Your PPO agent is not a contribution on its own, and claiming it as one invites a reviewer
to point at MPLight.

What *is* new: the state vector includes a **learned visual congestion forecast** (PRD §13.1, indices 11–14) rather than only instantaneous measurements. Whether anticipation helps is a real question the
above works largely do not test, because they consume sensor readings of the present.

### 2.6 Vision-based congestion prediction — the literature this review originally missed

**Correction, 2026-08-10.** The first version of this document surveyed graph-based forecasting
(§2.4) and hybrid CNN-transformer architectures (§2.1) and concluded that C1 — a camera-only
forecaster — was the project's strongest claim, because the forecasting literature assumes sensor
infrastructure. **That conclusion was wrong.** A separate and active literature predicts congestion
directly from camera imagery, and it was not surveyed.

| Work | What it does |
|---|---|
| Chakraborty et al. (2018), *Transportation Research Record* | Congestion detection from camera images using deep CNNs |
| Deep learning for congestion detection, prediction and alleviation — survey (arXiv 2102.09759, 2021) | An entire survey of this space. Its existence is the point |
| End-to-end spatio-temporal flow prediction from surveillance cameras (*Transportmetrica B*, 2024) | Detection, tracking and prediction in one pipeline from fixed low-resolution cameras |
| Rashmi & Shantala (2020) | YOLO on one week of Karnataka, India footage |

**What this costs the project.** "Camera-only congestion forecasting" is not novel. C1 must be
narrowed, and §3 below is rewritten accordingly. Being the second overclaim this review has caught,
it is also a reminder that a novelty search is only as good as the search terms — the graph
forecasting literature was surveyed because the architecture suggested it, and the vision literature
was missed because nobody searched for the *task*.

**What it gives back.** Rashmi & Shantala's result is directly useful and belongs in the paper's
motivation: YOLO reaches 92–99% accuracy on buses, cars and motorcycles in Indian footage, but drops
**below any useful level** on the vehicle modes specific to the study zone. That is independent
published evidence that off-the-shelf detection fails on exactly the classes IndiaTrafficNet exists
to add — the strongest external justification for the dataset contribution the project has, and a
live risk to FR-D09's ≥25% auto-rickshaw criterion (SOW R25).

### 2.7 Indian and fixed-camera traffic datasets

| Dataset | Viewpoint | Note |
|---|---|---|
| **IDD** (Varma et al., WACV 2019) | Ego-vehicle dashcam | The reference Indian set. Includes `autorickshaw`, `animal` |
| **FGVD** | Ego-vehicle | Fine-grained vehicle taxonomy, three-level hierarchy |
| **UA-DETRAC** (Wen et al., CVIU 2020) | **Fixed elevated camera** | Right viewpoint, Chinese traffic |
| **CityFlow** (Tang et al., CVPR 2019) / AI City Challenge | Fixed multi-camera | Right viewpoint, US traffic |

**The gap is real and it is specific:** Indian traffic data is predominantly ego-view (an autonomous
driving agenda); fixed-camera surveillance data is predominantly non-Indian. The intersection of
*heterogeneous Indian traffic* and *fixed elevated viewpoint* is genuinely under-served. That is what
[ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) Part B addresses, and it is a cleaner
claim than raw frame count.

---

## 3. What this project can honestly claim

Ordered by defensibility. Claim the top ones loudly; mention the rest as engineering.

**C1 — Per-lane congestion forecasting from a single fixed camera in non-lane-disciplined
heterogeneous traffic, coupled to a controller.** *(Narrowed 2026-08-10 — see §2.6.)*

The original wording — "camera-only forecasting where the literature assumes sensors" — was
overstated. Vision-based congestion prediction is an active field (§2.6). What survives is the
conjunction, and each element is load-bearing:

| Element | Why it narrows the claim |
|---|---|
| **Non-lane-disciplined heterogeneous traffic** | The vision literature is predominantly lane-disciplined. Published evidence says detection degrades badly on India-specific vehicle modes (§2.6) |
| **Per-lane output, not scene-level** | Existing work typically classifies a whole scene or predicts link flow. Per-lane is what a signal controller can act on |
| **Coupled to a controller** | The forecast is a policy input (C4), not a dashboard number |

Claim the conjunction. Claiming any single element invites a citation you did not survey.

**C2 — The fusion gate as an interpretable, analysed artifact.**
Not "we used a gate" but "we report what the gate learns, and it tracks scene density as §14.2
predicts." If the gate correlates with density, that is a genuine interpretability finding. **If it
does not, report that too** — a gate that collapses or learns nothing is an informative negative
result (BR-19).

**C3 — A harmonised Indian multi-class benchmark with a fixed-camera subset.**
Per ADR-006. The taxonomy-mismatch problem across existing sets is real and documented.

**C4 — Anticipatory state for RL signal control, with a forecast-quality sensitivity curve.**
Three policies — no forecast, noise-calibrated forecast, oracle forecast — answering not only *does
anticipation help* but *how good must the forecaster be before it helps*
([ADR-009](decisions/ADR-009-ppo-forecast-surrogate.md)). Narrow, testable, and stronger than the
single comparison originally planned. Note the SUMO fidelity caveat in
[ADR-010](decisions/ADR-010-sumo-heterogeneous-traffic.md): control results come from a simulator
configured for heterogeneous traffic, with the baseline sensitivity to that configuration reported.

**C5 — A density-stratified evaluation.**
Per the corpus spec §5.3. Reporting where the fusion helps rather than only whether it helps on
average is methodologically better than most comparable work.

### What must not be claimed

- "Novel CNN-ViT fusion architecture" — §2.1
- "Novel bidirectional cross-attention" — §2.2, this is co-attention from 2019
- "Novel gating mechanism" — §2.3
- "First RL traffic controller" — §2.5
- Any real-world wait-time reduction — everything is SUMO-simulated (PRD §20 L1b)

---

## 4. The comparison that decides the paper

Not MFSTNet vs. CNN-only. **MFSTNet vs. the count-based baselines** — LSTM on count sequences,
CongestFormer, and Naive last-value (PRD §14.3).

Those are the cheap alternatives. If a two-layer LSTM reading YOLO counts matches a dual-backbone
transformer reading pixels, a reviewer will reasonably ask why the complexity is justified. This is
the question the paper must answer head-on rather than bury.

Three things make the answer defensible:

1. **Verified test labels** (corpus spec §5.2) — without them the count baselines are scored on
   labels derived from their own inputs, which biases the comparison in their favour.
2. **Density stratification** (§5.3) — if fusion helps where detection saturates, that is the
   finding, and an aggregate metric hides it.
3. **A deployment argument** — count baselines require a working detector at inference. MFSTNet does
   not, so it degrades differently when detection fails. Under FR-A06 that is operationally relevant,
   not just rhetorical.

If MFSTNet still ties, say so and analyse why (PRD §2.5.5). "Visual fusion does not beat count-based
forecasting in this regime, and here is our evidence for why" is a publishable finding at CVIP and a
far better outcome than a cherry-picked win.

---

## 5. Venue positioning

| Venue | Fit | Emphasise |
|---|---|---|
| **IEEE ITSC** | Good | C1 and C4 — deployment context, infrastructure-free sensing, control integration |
| **CVIP** | Good | C2 and C3 — the gate analysis and the benchmark; a vision audience |
| National conference | Backup | Any of the above |

For ITSC, the RL half leads and MFSTNet is the enabling component. For CVIP, the fusion and gate
analysis lead and the RL half is the application. **Write the results once, frame the introduction
twice.**

---

## 5.5 Citations

Every work named here is listed in [BIBLIOGRAPHY.md](BIBLIOGRAPHY.md) with its URL, what it is cited
for, and — critically — whether it has actually been **verified**.

Most architecture and RL citations in this document are currently marked ⚠️: named from general
knowledge during the survey, never retrieved. **Nothing enters the paper's reference list while still
marked ⚠️.** The citations that disclaim novelty (ViLBERT, Flamingo, MPLight, RESCO) are the ones
most damaging to get wrong, and they head the verification queue.

## 6. Reading order for the team

Week 3–4, one paper each, presented to the group in fifteen minutes:

1. **Conformer** — your nearest architectural neighbour. Know exactly how you differ.
2. **ViLBERT** (co-attention sections) — the origin of your bidirectional fusion.
3. **PressLight** or **MPLight** — what good RL signal control looks like.
4. **DCRNN** or **STGCN** — what mainstream traffic forecasting assumes, and why you differ.
5. **IDD** — your data foundation and its stated limitations.

Not reading these is the most common way a strong project gets a weak viva.
