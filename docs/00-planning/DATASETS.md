# Dataset Sources and Selection

| | |
|---|---|
| **Document** | DATASETS v1.0 |
| **Date** | 2026-08-07 |
| **Purpose** | Which public datasets we use, which we deliberately do not, and why |
| **Related** | [ADR-001](decisions/ADR-001-two-track-dataset-strategy.md) (two-track strategy) · [PRD §12](PRD.md) · [Execution Manual Part 2](../90-manual/EXECUTION_MANUAL.md#part-2--the-dataset) |

---

## 1. Decision

Revised 2026-08-08 by [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md), which replaced the
12,000-frame field campaign with a curate-then-collect strategy. Rationale:
[FEASIBILITY-AUDIT §3.1 and §4-H1](FEASIBILITY-AUDIT.md).

| Role | Source | Size | Use |
|---|---|---|---|
| **Detector bootstrap** | **IDD Detection** | 22.8 GB | Track A YOLOv8 fine-tuning from Week 2 |
| **Class supplement** | **FGVD** | 2.6 GB | Fine-grained vehicle labels for rare classes |
| **Fixed-camera views** | **UA-DETRAC** or CityFlow | ~10 h video | Correct viewpoint; also the dev corpus source |
| **Benchmark (Part A)** | Curated from the above | — | IndiaTrafficNet-Bench: harmonised 8-class taxonomy, splits, datasheet |
| **Deployment data (Part B)** | **Campus collection, ours** | 1,500–3,000 frames | Fixed elevated Indian intersection views — the genuine gap |

Everything else on the IDD portal is out of scope. Reasons in §4 — read them before downloading,
because several entries look relevant and are not.

---

## 1.5 Should we build our own dataset at all?

Short answer: **a small one, on your own campus, with permission — not a 12,000-frame public-road
campaign.**

### The effort problem

A peak-hour Indian intersection frame holds roughly 20–60 annotatable objects. FR-D04's 12,000 frames
is on the order of **360,000 bounding boxes** — about 300 hours drawn from scratch, or 120–150 with
model-assisted review. Team capacity for the entire project is ~715 person-hours. One deliverable
would consume a fifth to a third of everything you have.

> Measure this yourself in Week 2 rather than trusting the estimate: annotate **50 frames** (25 peak,
> 25 off-peak), time it, and commit the measurement. One hour of work replaces the largest guess in
> the project.

### The legal and ethical problem

Recording public roads in India is not prohibited. **Publishing** frames of identifiable people is a
different question:

- Faces and licence plates are personal data. India's **DPDP Act 2023** governs processing of
  personal data of identifiable individuals. Releasing them under CC BY 4.0 without a clear lawful
  basis is, at minimum, unresolved.
- Venues increasingly require an ethics statement. "We filmed strangers and released it" is a weak
  answer to a reviewer.
- Restricted areas — defence installations, airports, some government buildings — are genuine
  constraints, and being questioned mid-session costs you the session.
- Seeking municipal permission is possible but has **unbounded lead time**, which is the one risk
  category a 20-week schedule cannot absorb.

> This is a risk assessment, not legal advice. Route any publication decision through your
> institution's ethics or research committee.

### What to do instead

**Part A — curate.** Build IndiaTrafficNet-Bench from permissively-licensed public sources: one
harmonised taxonomy, de-duplication, standard splits, a full datasheet, evaluation scripts. Where a
licence permits redistribution, ship images; where it does not, **ship conversion scripts plus a
manifest** so users rebuild it from their own copies. This is lawful, standard practice, and a
citable contribution — the field genuinely lacks a harmonised Indian multi-class benchmark, because
every existing set uses a different taxonomy.

**Part B — collect small, on campus.** 1,500–3,000 frames from a fixed elevated position on your own
institution's grounds:

| Step | Detail |
|---|---|
| Permission | One email to administration explaining the academic purpose. Days, not months |
| Signage | Post a notice at the recording location where practical |
| Anonymisation | **Blur faces and licence plates before any release.** Automate it; commit the script |
| Documentation | Datasheet section covering consent basis, blurring method, residual risk |
| Retention | Raw unblurred video stays local, never published (NFR-13) |

Part B is small enough to annotate *well* — consistent conventions, checked edge cases — instead of
12,000 frames rushed by four people under deadline. For the fixed-camera subset that carries the
novelty, quality beats quantity.

**Net effect:** the contribution survives and arguably strengthens, legal exposure drops to near
zero, ~200 person-hours return to the experiments, and annotation leaves the critical path.

> **M1's acceptance criterion changes**, so ADR-006 needs faculty guide sign-off. Take it with the
> feasibility audit in Week 1–2.

---

## 2. The viewpoint problem — read this first

**IDD is ego-vehicle dashcam footage.** It is recorded from a camera mounted on a moving car, at road
level, looking forward. Our system uses a **fixed, elevated camera looking down at an intersection.**

That is a real domain gap, and it changes what IDD is good for:

| | IDD (ego view) | Our deployment (fixed elevated view) |
|---|---|---|
| Camera | Moving, road level, forward-facing | Static, elevated, downward |
| Vehicle appearance | Rear and three-quarter views, large and close | Top-down and oblique, small and distant |
| Occlusion pattern | Vehicles occlude each other front-to-back | Vehicles occlude less; elevation is the whole point |
| Scene | Continuously changing | One fixed scene |
| Density in frame | A few large objects | Many small objects |

**What IDD is therefore good for:** teaching the detector what Indian vehicle *classes look like* —
what distinguishes an auto-rickshaw from a car, what an e-rickshaw is, that cattle appear on roads.
Those class semantics transfer across viewpoint. This is exactly what
[ADR-001](decisions/ADR-001-two-track-dataset-strategy.md) needs a bootstrap for: unblocking the
pipeline, not producing final results.

**What IDD is not good for:** final detection accuracy at your deployment viewpoint. Expect the
bootstrap model to under-perform on your own footage, particularly on small distant vehicles. That is
not a failure — it is the reason IndiaTrafficNet exists.

### 2.1 This strengthens your paper

The gap is an argument, not an embarrassment. Written honestly it becomes a motivation paragraph:

> *Public Indian traffic datasets are predominantly ego-vehicle in perspective (IDD, IDD-X, I2WDD),
> reflecting an autonomous-driving research agenda. Fixed-camera intersection surveillance — the
> viewpoint required for signal control — remains under-served. IndiaTrafficNet addresses this gap.*

That is a stronger justification for Novel Contribution 1 than "we collected our own data," and it is
checkable by any reviewer. Quantify it in Week 9: report bootstrap-weights mAP on your own test set
alongside IndiaTrafficNet-fine-tuned mAP. The difference **is** the viewpoint gap, measured.

---

## 3. Selected datasets

### 3.1 IDD Detection — primary bootstrap

| | |
|---|---|
| **Source** | India Driving Dataset, IIIT Hyderabad — `idd.insaan.iiit.ac.in` |
| **Size** | 22.8 GB · 40,000 images with bounding-box annotations |
| **Released** | 2018 |
| **Licence** | Research use, via registered account. **Cite the IDD paper in any publication** |
| **Format** | Pascal VOC-style XML (needs conversion to YOLO) |
| **Serves** | FR-D08 bootstrap; ADR-001 Track A |

**Why this one over IDD 117k.** IDD 117k-Detection has 117,099 images but ships as five 15 GB parts —
about 72 GB. For a bootstrap whose entire purpose is to exist by Week 2, 40,000 images is already far
more than enough; you will subsample it anyway (§5). The extra 50 GB buys nothing that matters here.
If detection quality turns out to be the binding constraint later, 117k is the upgrade path.

**Citation** (required — put it in the paper now, not in Week 20):

> Varma, G., Subramanian, A., Namboodiri, A., Chandraker, M., & Jawahar, C.V. (2019). *IDD: A Dataset
> for Exploring Problems of Autonomous Navigation in Unconstrained Environments.* WACV 2019.

### 3.2 FGVD — secondary

| | |
|---|---|
| **Size** | 2.6 GB · 5,502 images · 210 fine-grained labels in a 3-level hierarchy |
| **Capture** | Moving car-mounted camera (same viewpoint caveat as §2) |
| **Serves** | Class supplement, especially for vehicle types IDD labels coarsely |

Small and cheap to download. Its three-level hierarchy means you can collapse fine labels up to our
eight classes. Useful if IDD's rare-class coverage proves thin. **Optional** — do not let it delay
Week 2.

---

## 4. Deliberately not used

Several portal entries look relevant. They are not, and knowing why saves a wasted download.

| Dataset | Size | Why not |
|---|---|---|
| **IDD Temporal** (Train I–IV, Val, Test) | ~99 GB | **The trap.** "Temporal" suggests it supplies MFSTNet's sequences. It does not: it provides ±15 frames around each annotated frame — about 1–2 seconds. MFSTNet needs **60 frames spanning 5 minutes** (PRD §8.6). Two orders of magnitude short, and ego-view besides |
| **IDD 117k - Detection** (5 parts) | ~72 GB | Same task as IDD Detection at 3× the images and 3× the download. Upgrade path only (§3.1) |
| **IDD Segmentation** (20k Parts I & II) | 24 GB | Semantic segmentation. We need bounding boxes for counting (FR-P02). Wrong annotation type |
| **IDD Lite** | 26.9 MB | Subsampled segmentation for architecture search. Wrong annotation type |
| **IDD-3D** | 236 GB | LiDAR-based 3D detection. No LiDAR in our stack, and out of scope |
| **IDD Multimodal** (Primary/Secondary/Supplement) | 16 GB | Stereo + GPS + LiDAR + OBD. Ego-vehicle sensing; nothing we consume |
| **IDD-X** | 160 GB | Driving-behaviour explanation, dual-view. Different problem |
| **I2WDD** | 19.4 GB | Two-wheeler driving behaviour. Different problem |
| **IDD-AW** | 19 GB | Adverse weather (rain, fog, low light, snow) with NIR. **Explicitly out of scope** — PRD §20 L3 and SOW §2.2 exclude night and adverse weather. Note as future work |
| **MTSVD / MissingTSMini** | 138 GB / 2.5 GB | Traffic-sign detection. Not our task |

**IDD-AW deserves a sentence in the paper's future-work section.** It is the obvious next step for
anyone extending this work past the daytime-only limitation, and citing it shows you know the
limitation is addressable rather than merely acknowledged.

---

## 5. Practical handling — the storage problem

22.8 GB does not fit in a free 15 GB Google Drive. Do not try.

**Workflow:** download to Colab's local disk (ephemeral, ~80–100 GB), convert and subsample there,
and persist only the small result to Drive.

```python
# In Colab — /content is ephemeral local disk, NOT Drive
!mkdir -p /content/idd && cd /content/idd
# download using the token generated from the IDD portal, then:
!tar -xf IDD_Detection.tar.gz -C /content/idd
```

Then:

1. **Convert** VOC XML → YOLO txt.
2. **Map classes** to our eight (§6). Drop everything unmapped.
3. **Drop empty images** — frames with no target-class object contribute nothing to a bootstrap.
4. **Subsample to ~15–20k images.** Diminishing returns beyond that for 50 epochs of fine-tuning, and
   it keeps training within a single Colab session.
5. **Persist** the converted subset (~2–4 GB) to Drive. Delete the raw archive.

Record the subsample seed and count in `indiatrafficnet/public_subset.yaml` so the bootstrap is
reproducible (NFR-07). A bootstrap you cannot reproduce means a Week-9 comparison you cannot defend.

---

## 6. Class mapping

Our eight target classes are fixed by PRD §12.2 and FR-D03. IDD's taxonomy is Cityscapes-derived with
India-specific additions.

> **Verify the exact label set before mapping.** Do not trust this table or any second-hand list —
> enumerate the labels in the download itself:
>
> ```bash
> grep -rhoP '(?<=<name>)[^<]+' /content/idd/**/Annotations/*.xml | sort | uniq -c | sort -rn
> ```
>
> Commit the output. It is evidence for your datasheet (FR-D07) and it settles arguments.

Expected mapping, to be confirmed against that output:

| Our class (PRD §12.2) | Expected IDD label | If absent |
|---|---|---|
| car | `car` | — |
| motorcycle | `motorcycle` | — |
| auto-rickshaw | `autorickshaw` | The class that matters most — verify it exists |
| e-rickshaw | *(likely absent)* | Train as background until Week 8 |
| bus | `bus` | — |
| truck | `truck` | — |
| pedestrian | `person` | Decide whether `rider` maps here or to motorcycle — **document the choice** |
| cattle | `animal` | If coarse, expect weak transfer. IndiaTrafficNet carries this class |

Labels present in IDD but absent from our taxonomy (`traffic sign`, `traffic light`, `bicycle`,
`train`, `caravan`, `trailer`, `vehicle fallback`, …) are dropped, not merged. Merging unlike classes
teaches the detector a category that does not exist in our label space.

Keep the mapping in `indiatrafficnet/class_mapping.yaml` — versioned, not remembered.

### 6.1 The `rider` question

IDD annotates `person` and `rider` separately; a motorcyclist is a `rider` on a `motorcycle`. Our
taxonomy has no `rider`. Pick one convention, write it in the datasheet, and apply it to
IndiaTrafficNet annotation too:

**Recommended:** map `rider` → drop, count only the `motorcycle`. Our task is counting *vehicles* for
congestion; counting a motorcycle and its rider as two objects inflates counts by roughly the
two-wheeler share, which PRD §12.2 estimates at 30%. That would systematically bias every congestion
label built by the §8.6 pipeline.

This is a small decision with a large downstream effect. Make it once, in Week 2, and make
IndiaTrafficNet annotation follow it.

---

## 7. Datasheet obligations

Every public dataset used must appear in the IndiaTrafficNet datasheet (FR-D07) with its name,
version, licence, and how it was used. Two reasons: FR-D09's comparison is meaningless without
knowing what the baseline was trained on, and a reviewer who cannot tell which data produced which
number will discount both.

Record for each: dataset name and version, licence and access date, image count used after
subsampling, class mapping applied, and which experiments used it.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial. IDD Detection selected as primary bootstrap; viewpoint gap documented |
