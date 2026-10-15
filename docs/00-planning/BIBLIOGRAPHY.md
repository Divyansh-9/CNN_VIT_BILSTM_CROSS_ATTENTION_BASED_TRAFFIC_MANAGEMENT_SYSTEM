# Bibliography

Every external work this project cites, in one place, with what it is cited **for**.

| | |
|---|---|
| **Date** | 2026-08-10 |
| **Owner** | R2 (paper lead) |
| **Purpose** | Feed the paper's reference list; prevent citing work nobody read |

## How to use this

**The `Verified` column is the important one.**

| Mark | Meaning |
|---|---|
| ✅ | URL retrieved **and content checked** during this project. Safe to cite, and safe to quote a number from |
| 🔗 | **Bibliographic record retrieved** from an index (OpenAlex, or arXiv for preprints it does not hold at their publication year): title, authors, year, venue and DOI are confirmed. The full text has **not** necessarily been read |
| ⚠️ | Named from general knowledge, **not retrieved**. Author, year or venue may be wrong. **Verify before it enters the paper** |

An entry marked ⚠️ is a lead, not a citation. Getting an author or venue wrong in a submitted paper
is the kind of error a reviewer notices immediately and reads as carelessness about everything else.

**Rule:** nothing enters a reference list while still marked ⚠️. Verify it, retrieve the real
record, flip the mark, and record the DOI.

**🔗 is now mechanical, and it is a weaker claim than ✅ on purpose.**
`scripts/verify_references.py` queries each work by title, and **refuses to record a result whose
title or year does not match what was expected** — so a 🔗 mark means an index agrees that the work
exists with those authors at that venue in that year. The records live in `data/references.json`,
and the Phase-I Progress Report's reference list is generated from them rather than typed, which is
what makes a thirty-row comparative table of citations safe to submit.

It does **not** mean anyone read the paper. A number quoted from a work needs ✅, and §2's B2 is the
only entry in that state whose figures this project repeats. The reading list in
[RELATED-WORK §6](RELATED-WORK.md) is still owed.

The matcher is tested in `tests/test_progress_report.py`, including the case that made the
threshold strict: the expected DCRNN title shares six of its nine significant words with a
different 2018 traffic-forecasting paper, and an earlier, looser rule recorded that paper's authors
as DCRNN's.

---

## 1. Saturation flow and signal timing — heterogeneous traffic

Underpins [ADR-012](decisions/ADR-012-webster-saturation-flow.md) and the Webster baseline.

| # | Work | Cited for | Verified |
|---|---|---|---|
| B1 | *Saturation Flow Rate Measurement on a Four Arm Signalized Intersection of Ahmedabad City*, IJERT — [link](https://www.ijert.org/saturation-flow-rate-measurement-on-a-four-arm-signalized-intersection-of-ahmedabad-city) | Saturation flow 933W–1283W (IRC PCU) and 636W–821W (Justo & Tuladhar PCU) for the same intersection. **The evidence that PCU convention alone moves the answer 2×** | ✅ |
| B2 | *Base saturation flow rate (BSFR) and its effect on performance of pretimed signalized intersection with non-lane based urban heterogeneous traffic* — [PMC11226031](https://pmc.ncbi.nlm.nih.gov/articles/PMC11226031/) | `S₀ = 622·Wₑ` (R²=0.99, widths 5–8 m); narrow-width form `1020 + 459·Wₑ`; **PCE motorcycle 0.24, auto-rickshaw 0.78**; lost time 4–5 s start, ~3 s end. Banda Aceh, non-lane-based | 🔗 record retrieved (openalex), doi: 10.1371/journal.pone.0306112 |
| B3 | *Study on Geometric Factors Influencing Saturation Flow Rate at Signalized Intersections under Heterogeneous Traffic Conditions*, JTTs — [PDF](https://www.scirp.org/pdf/JTTs_2017012216394202.pdf) | 610–660 PCU/h per metre for approach widths 3.5–14 m; saturation flow rises with width | ✅ |
| B4 | *Empirical assessment of saturation flow rate with dynamic PCUs at signalized intersections under mixed traffic conditions*, Innov. Infrastruct. Solut. (2025) — [link](https://link.springer.com/article/10.1007/s41062-025-02188-3) | Dynamic PCU as a refinement over fixed PCU values. Future work, not adopted | ✅ |
| B5 | IRC:SP-41-1994 | `S = 525 × W` PCU/h, stated valid above 5.5 m approach width. **The Indian standard, and the low end of the sweep** | ⚠️ Obtain the actual IRC document |
| B6 | Webster, F.V. (1958). *Traffic Signal Settings*. Road Research Technical Paper No. 39 | The optimum cycle formula `C₀ = (1.5L + 5)/(1 − Y)` | ⚠️ |

## 2. Vision-based congestion prediction — the task-level prior art

Underpins [RELATED-WORK §2.6](RELATED-WORK.md) and the narrowing of claim C1. **This is the section
the first novelty survey missed.**

| # | Work | Cited for | Verified |
|---|---|---|---|
| B7 | *Applications of deep learning in traffic congestion detection, prediction and alleviation: A survey* — [arXiv 2102.09759](https://arxiv.org/pdf/2102.09759) | That an entire survey of this space exists. **Cite it to show the field was surveyed, not to borrow from it** | 🔗 record retrieved (openalex), doi: 10.1016/j.trc.2021.103432 |
| B8 | *Predicting spatio-temporal traffic flow: a comprehensive end-to-end approach from surveillance cameras*, Transportmetrica B (2024) — [link](https://www.tandfonline.com/doi/full/10.1080/21680566.2024.2380915) | Detection, tracking and prediction in one pipeline from fixed low-resolution cameras. Nearest task-level neighbour | 🔗 record retrieved (openalex), doi: 10.1080/21680566.2024.2380915 |
| B9 | Chakraborty, Adu-Gyamfi, Poddar, Ahsani, Sharma, Sarkar (2018). *Traffic Congestion Detection from Camera Images using Deep Convolution Neural Networks*, Transportation Research Record — [link](https://journals.sagepub.com/doi/abs/10.1177/0361198118777631) | Camera-image congestion detection with deep CNNs | 🔗 record retrieved (openalex), doi: 10.1177/0361198118777631 |
| B10 | Rashmi & Shantala (2020), Karnataka, India | **YOLO 92–99% on bus/car/motorcycle; below usable accuracy on zone-specific modes.** The strongest external justification for IndiaTrafficNet, and the basis of risk R25 | ⚠️ **Priority verify** — this is load-bearing for the dataset contribution |

## 3. Hybrid CNN–Transformer architectures

Underpins [RELATED-WORK §2.1–2.3](RELATED-WORK.md). Originally all ⚠️ — named from general
knowledge during the architecture survey, none retrieved. The 🔗 pass retrieved the records for the
entries this project actually cites; B14 and B20 are still leads, because nothing cites them.

| # | Work | Cited for | Verified |
|---|---|---|---|
| B11 | Peng et al. (2021). *Conformer*, ICCV | **Nearest architectural neighbour.** Parallel CNN + transformer branches with feature coupling | 🔗 record retrieved (openalex), doi: 10.1109/iccv48922.2021.00042 |
| B12 | Chen, Fan, Panda (2021). *CrossViT*, ICCV | Dual-branch fusion by cross-attention | 🔗 record retrieved (openalex), doi: 10.1109/iccv48922.2021.00041 |
| B13 | Dai et al. (2021). *CoAtNet*, NeurIPS | Convolution + attention complementarity | 🔗 record retrieved (openalex), doi: 10.48550/arxiv.2106.04803 |
| B14 | Mehta & Rastegari (2022). *MobileViT*, ICLR · Guo et al. (2022). *CMT*, CVPR | The efficient hybrid family | ⚠️ |
| B15 | Liu et al. (2022). *ConvNeXt*, CVPR | Adversarial citation — argues the ViT branch must earn its place. **Ablation config A must answer it** | 🔗 record retrieved (openalex), doi: 10.1109/cvpr52688.2022.01167 |
| B16 | Lu et al. (2019). *ViLBERT*, NeurIPS | **Co-attention — your bidirectional cross-attention, published 2019** | 🔗 record retrieved (openalex) |
| B17 | Tan & Bansal (2019). *LXMERT*, EMNLP | Cross-modality bidirectional attention | 🔗 record retrieved (openalex), doi: 10.18653/v1/d19-1514 |
| B18 | Alayrac et al. (2022). *Flamingo*, NeurIPS | **Gated cross-attention — your gate mechanism, published 2022** | 🔗 record retrieved (openalex), doi: 10.48550/arxiv.2204.14198 |
| B19 | Oquab et al. *DINOv2* | Self-supervised features; the default ViT branch per ADR-007 | 🔗 record retrieved (openalex), doi: 10.48550/arxiv.2304.07193 |
| B20 | Hu et al. (2021). *LoRA* | Parameter-efficient adaptation, replacing `unfreeze_epoch` | ⚠️ |

## 4. Traffic forecasting — the graph/sensor paradigm

Underpins [RELATED-WORK §2.4](RELATED-WORK.md). Cited to establish what the mainstream **assumes**,
not what it does.

| # | Work | Cited for | Verified |
|---|---|---|---|
| B21 | Yu, Yin, Zhu (2018). *STGCN*, IJCAI | Graph-based forecasting on sensor networks | 🔗 record retrieved (openalex), doi: 10.24963/ijcai.2018/505 |
| B22 | Li et al. (2018). *DCRNN*, ICLR | Diffusion-convolutional recurrent forecasting | 🔗 record retrieved (arxiv), doi: 10.48550/arXiv.1707.01926 |
| B23 | Wu et al. (2019). *Graph WaveNet*, IJCAI | Adaptive adjacency | 🔗 record retrieved (openalex), doi: 10.24963/ijcai.2019/264 |
| B24 | Guo et al. (2019). *ASTGCN*, AAAI | Attention-based spatio-temporal GCN | 🔗 record retrieved (openalex), doi: 10.1609/aaai.v33i01.3301922 |

## 5. RL traffic signal control

Underpins [RELATED-WORK §2.5](RELATED-WORK.md), claim C4, and the baseline argument in ADR-012.

| # | Work | Cited for | Verified |
|---|---|---|---|
| B25 | Wei et al. (2018). *IntelliLight*, KDD | Deep RL on real signal data | 🔗 record retrieved (openalex), doi: 10.1145/3219819.3220096 |
| B26 | Wei et al. (2019). *PressLight*, KDD | Max-pressure-informed reward | 🔗 record retrieved (openalex), doi: 10.1145/3292500.3330949 |
| B27 | Wei et al. (2019). *CoLight*, CIKM | Multi-intersection coordination | 🔗 record retrieved (openalex), doi: 10.1145/3357384.3357902 |
| B28 | Zheng et al. (2019). *FRAP*, CIKM | Phase-competition invariance | 🔗 record retrieved (openalex), doi: 10.1145/3357384.3357900 |
| B29 | Chen et al. (2020). *MPLight*, AAAI | **Cite this when disclaiming RL novelty** | 🔗 record retrieved (openalex), doi: 10.1609/aaai.v34i04.5744 |
| B30 | Ault & Sharon (2021). *RESCO*, NeurIPS D&B | Standard benchmark and evaluation protocol | ⚠️ **Priority verify** |
| B31 | *Reinforcement Learning for Traffic Signal Control: Comparison with Commercial Systems* — [arXiv 2104.10455](https://arxiv.org/pdf/2104.10455) | Fixed-time 552–924 s vs RL 100–120 s; baselines reported without variability. **Evidence that your 30-seed + CI protocol is above field standard** | ✅ URL; ⚠️ figures need checking against the actual paper |

## 6. Datasets

Underpins [DATASETS.md](DATASETS.md) and [RELATED-WORK §2.7](RELATED-WORK.md).

| # | Work | Cited for | Verified |
|---|---|---|---|
| B32 | Varma, Subramanian, Namboodiri, Chandraker, Jawahar (2019). *IDD*, WACV | The bootstrap dataset. **Ego-vehicle viewpoint** — the gap that motivates Part B | 🔗 record retrieved (openalex), doi: 10.1109/wacv.2019.00190 |
| B33 | Wen et al. (2020). *UA-DETRAC*, CVIU | Fixed elevated camera, Chinese traffic. Dev-corpus source | 🔗 record retrieved (openalex), doi: 10.1016/j.cviu.2020.102907 |
| B34 | Tang et al. (2019). *CityFlow*, CVPR | Fixed multi-camera, US traffic | 🔗 record retrieved (openalex), doi: 10.1109/cvpr.2019.00900 |
| B35 | FGVD — fine-grained vehicle detection | Class supplement for rare vehicle types | ⚠️ |

---

## Verification queue

Ordered by consequence if wrong. The 🔗 pass cleared the four that were about *identity* — B16
ViLBERT, B18 Flamingo, B29 MPLight and B11 Conformer are now recorded with their DOIs, so the
citations that disclaim novelty point at the right papers. What is left is a different kind of
owing: entries no index holds, and entries whose *content* this project repeats without having read
it.

| Priority | Entry | What is still owed |
|---|---|---|
| 1 | **B10** Rashmi & Shantala | **No index holds it.** The YOLO 92–99% / below-usable figures are load-bearing for the dataset contribution and risk R25, and they are still recalled rather than retrieved. Either retrieve the paper or stop quoting the numbers — the Phase-I Progress Report does the latter: it makes the same argument from viewpoint and class coverage (B32, B33, B34), which are recorded |
| 2 | **B30** RESCO | Not in `data/references.json`: the OpenAlex query for it did not return a record matching the expected title and year, and nothing was recorded rather than something approximate |
| 3 | **B5** IRC:SP-41-1994, **B6** Webster 1958 | Standards and a 1958 technical paper, neither indexed. Listed in `EXTRA_REFERENCES` in `scripts/phase1_progress_content.py` and cited as standards, which is honest; obtaining the documents is still owed before a number is quoted from either |
| 4 | **B8** Transportmetrica B | 🔗 only — the record is confirmed and the full text is paywalled. Read before any claim about *how* it forecasts |
| 5 | **B31** arXiv 2104.10455 | The fixed-time 552–924 s versus RL 100–120 s figures need checking against the paper, not the abstract |

**What the 🔗 pass does not excuse.** Every work in
[RELATED-WORK §6](RELATED-WORK.md)'s reading list is still to be read by a team member and presented
to the group. A confirmed DOI tells a reviewer the citation is real; it does not survive a viva
question about what the paper actually did.

## Rules

- **Read before citing.** A reference list containing work nobody opened is detectable and damaging.
- **Record the DOI** when verifying, not just the URL — URLs rot.
- **Cite what a work *assumes*, not only what it does.** §4's value is that those methods assume
  sensor infrastructure; that framing is the citation's purpose.
- **Update this file when a new source is used**, in the same commit. A bibliography assembled in
  Week 19 from memory will contain errors.
