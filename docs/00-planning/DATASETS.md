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

### 2.05 Published evidence that off-the-shelf detection fails here

Rashmi & Shantala (2020) ran YOLO over a week of Karnataka, India footage
([B10](BIBLIOGRAPHY.md)). Accuracy reached **92–99% for buses, cars and motorcycles** — and dropped
**below any useful level** on the vehicle modes specific to the study zone.

Two consequences, and both are load-bearing:

**It justifies the dataset.** This is independent, published evidence that a general-purpose detector
fails on exactly the classes IndiaTrafficNet exists to add. That is a far stronger motivation than
"we wanted our own data," and it belongs in the paper's introduction.

**It is a live risk to M2.** FR-D09 requires ≥25% mAP improvement on auto-rickshaw. If fine-tuning
does not lift the zone-specific classes, that milestone fails. Recorded as SOW R25. Report per-class
mAP **with sample count** either way — a detector that cannot learn auto-rickshaw from 12,000 frames
is itself a reportable finding about transfer, not a failure to conceal.

> ⚠️ B10 is currently the weakest-sourced important claim in the project. It is priority 1 in the
> [bibliography verification queue](BIBLIOGRAPHY.md#verification-queue). Verify it before it carries
> weight in the paper.

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

## 4.4 IDD Detection — acquired and verified (2026-08-15)

`D:/traffic dataset/downloads/idd-detection/IDD_Detection`, standard VOC layout
(`Annotations/`, `JPEGImages/`, `train.txt`, `val.txt`, `test.txt`).

| Split | Images |
|---|---|
| train | **31,569** |
| val | **10,225** |
| test | **4,794** |

**Verified rather than assumed.** 400 randomly sampled training annotations
(seed 42) were parsed: **400 of 400 succeeded, none missing or malformed.**
13 distinct classes, with the counts in that sample:

| IDD class | count | maps to IndiaTrafficNet |
|---|---|---|
| motorcycle | 998 | motorcycle |
| person | 942 | pedestrian |
| rider | 924 | see §6.1 — the `rider` question |
| car | 827 | car |
| **autorickshaw** | **272** | **auto-rickshaw** |
| truck | 247 | truck |
| vehicle fallback | 179 | IDD's catch-all; see §6 |
| bus | 149 | bus |
| traffic sign | 129 | not used |
| **animal** | **121** | **cattle** |
| bicycle | 37 | bicycle |
| traffic light | 30 | not used |
| train | 1 | not used |

**This is a materially better fit than any alternative assessed.** IDD carries
**auto-rickshaw and animal natively** — two of the three India-specific classes
that the DataCluster sample (§4.5) lacks, and the two that no foreign dataset can
supply at all. Only **e-rickshaw** is absent, and it remains a reason
self-collection is still required for the detector, not only for the corpus.

### Full label census — 507,576 boxes (FR-D07 datasheet evidence)

§6 requires enumerating the labels in the download rather than trusting any
second-hand list. Done over every annotation:
`experiments/results/idd_label_census.csv`.

| | boxes | | boxes |
|---|---|---|---|
| motorcycle | 103,608 | bus | 18,745 |
| **rider** | **97,626** | traffic sign | 14,203 |
| car | 90,520 | **animal** | **6,224** |
| person | 88,397 | traffic light | 3,699 |
| **autorickshaw** | **32,280** | bicycle | 3,142 |
| truck | 27,837 | caravan | 136 |
| vehicle fallback | 21,081 | train / trailer | 60 / 18 |

**Two findings.**

**1. The test split has no labels.** `test.txt` lists 4,794 ids and **zero** have
annotation files — labels are withheld, as is normal for a benchmark. Usable
data is train + val = **41,794 images / 507,576 boxes**. `prepare_idd.py` draws
from `train.txt` and re-splits 70/15/15 (FR-D05), so nothing depends on the
withheld set, but any figure quoting "46,588 images" is wrong.

**2. `rider` is the second-largest class at 97,626 boxes.** That is the §6.1
decision measured: dropping it removes **19% of all boxes**, and *not* dropping
it would have added a phantom object to nearly every motorcycle. The convention
was right and its magnitude is now documented rather than estimated.

**S08–S12 are unblocked.** The detector track needs no further data acquisition.

## 4.5 Two data needs, and why no public dataset solves the second

Added 2026-08-14, after a candidate dataset was proposed as a way to unblock S06.
It is written down because the same confusion has now cost time twice.

**The project needs two different things and they have been treated as one.**

| Need | Shape required | Public sources |
|---|---|---|
| **Detector** — S08–S12, YOLOv8 fine-tuning | still images + bounding boxes | plentiful (IDD, FGVD, and the candidate below) |
| **MFSTNet corpus** — S06, S28–S31 | **continuous fixed-camera video, ≥360 s**, one signalised intersection | **essentially none** |

The second row is the blocker, and it is the one no public dataset has solved.
Published vehicle datasets are almost universally either image collections or
dashcam clips. MFSTNet forecasts congestion **60 s ahead**, which requires
T=60 frames at 5 s spacing plus a label 60 s past the window end — amendment A15
puts the minimum clip at **360 s from a stationary camera**. A photo collection
has no temporal structure at all, and a dashcam has no fixed frame, so lane
polygons cannot be defined.

**State it once so it is not rediscovered a third time: the corpus need has no
public substitute.** Filming, or a live municipal camera feed, are the only two
shapes that fit — which is what PRD §22 and [ADR-001](decisions/ADR-001-two-track-dataset-strategy.md)
specified from the start when they called IndiaTrafficNet self-collected.

### Candidate assessed — DataCluster Labs "Indian Vehicle Dataset"

- Kaggle: <https://www.kaggle.com/datasets/dataclusterlabs/indian-vehicle-dataset>
- GitHub: <https://github.com/datacluster-labs/Indian-Vehicle-Dataset>
- Roboflow mirror: <https://universe.roboflow.com/datacluster-labs-agryi/indian-vehicle-auto>

| | |
|---|---|
| Size | ~40,000 images, **15,000 annotated**, ~53,000 boxes |
| Classes | Indian Auto, Indian Truck, Bus, Truck, Tempo Traveller, Tractor, Car, Two Wheelers |
| Formats | COCO, YOLO, PASCAL-VOC, TFRecord |
| Media | **Still images** |

**Verdict: useful for the detector, useless for the corpus.** Its class list
overlaps ours better than any foreign footage does — *Indian Auto* is our
auto-rickshaw, the single most important India-specific class — and 15,000
pre-annotated images directly attacks the annotation burden the
[FEASIBILITY-AUDIT](FEASIBILITY-AUDIT.md) found underestimated by roughly 3×.
It contains **no e-rickshaw and no cattle**, so it cannot replace self-collection
even for detection.

> **Licence must be checked before any use.** The images are stated to be
> *"exclusively owned by Data Cluster Labs"*, with a licence *"purchased"* for
> research and commercial use, and the GitHub repository states **no licence terms
> at all**. [ADR-013](decisions/ADR-013-artifact-hosting-and-publication.md)
> Decision 4 commits this project to properly-licensed sources. Read the licence
> field on the Kaggle page itself — that is the only authoritative statement — and
> prefer **IDD (§3.1)**, which is the academic standard, citable, and unambiguously
> licensed for research. An unclear commercial sample is a poor trade when a
> citable academic alternative already exists.

### DataCluster re-assessed after the viewpoint gap was measured — REJECTED

Re-examined once P5 rev 2 showed the real problem is viewpoint, not classes.
Two independent reasons, either sufficient.

**1. The licence is `copyright-authors`.** That is Kaggle's all-rights-reserved
marker, confirmed from the dataset's own metadata rather than its description.
[ADR-013](decisions/ADR-013-artifact-hosting-and-publication.md) Decision 4
commits this project to properly-licensed sources for anything that reaches a
publication. This disqualifies it before any technical question is asked.

**2. The imagery is street-level phone stills, which is the wrong geometry.**
Filenames encode 4160×3120, 3264×2448, 2592×1944 — 4:3 phone-camera stills, and
the dataset describes itself as crowdsourced. Two samples inspected directly:

| | |
|---|---|
| Sample A | a parked Tempo Traveller filling most of a portrait frame, shot from a few metres at eye level |
| Sample B | a signalised junction from the kerb — sparse traffic, distant vehicles, ~60% of the frame bare tarmac |

Sample B is closer to useful than Sample A, but neither is an elevated fixed
camera looking down at dense traffic. **It would add more of what IDD already
over-supplies — large, near, eye-level vehicles — and none of what the measured
gap needs.**

### The gap points at aerial data, and that is worth knowing before acting on it

The geometry that resembles an elevated junction camera — small objects, oblique
downward view, dense scenes — is what **drone datasets** contain.
[VisDrone2019-DET](https://docs.ultralytics.com/datasets/detect/visdrone) is the
obvious candidate: 8,629 aerial images across 14 cities, and its class list
includes **`tricycle` and `awning-tricycle`**, the closest public analogue to an
auto-rickshaw that any non-Indian dataset offers.

**It is not being adopted yet, deliberately.** Drone altitude is tens of metres
where a footbridge is five to ten, so it is *closer* than dashcam without being
the same thing, and the cities are Chinese. Adding it now would be augmenting on
a hunch, which is the pattern this project has spent its effort correcting.

**Run S12 first.** The cross-camera experiment measures what viewpoint transfer
actually costs, using IDD alone and no new data. If the drop is large, VisDrone
becomes a justified augmentation with a number behind it. If it is small, the
whole line of reasoning was wrong and no third dataset is needed.

### Foreign and highway footage — evaluate on it, never train the corpus on it

Non-Indian footage was proposed for generalisation. Three separate uses, and
mixing them is the risk:

1. **Detector** — genuinely helps robustness to lighting and camera height, but
   adds **zero** examples of auto-rickshaw, e-rickshaw or cattle, and skews class
   balance toward cars.
2. **MFSTNet labels** — actively harmful. The §14.1 thresholds are calibrated for
   Indian lane occupancy *with lateral filtering*; the same count means a
   different congestion state elsewhere.
3. **Highway versus signalised intersection** — the decisive one. See §4.6.

**Better use: a domain-shift evaluation.** Train on Indian data, evaluate
zero-shot on foreign footage, report the drop. That is a stronger contribution
than a silently mixed training set — reviewers reward an honest generalisation
section and penalise unclear provenance. The A9 human-verified **test split stays
Indian-intersection only**.

## 4.6 "Do auto-rickshaws and cattle appear on highways?" — the signal answers it

A reasonable objection: highways have traffic lights too, so is the India-specific
class list really tied to local roads?

**The distinction is not highway versus city. It is access-controlled versus not** —
and the presence of a traffic signal settles it.

NHAI prohibits, on access-controlled expressways and highways: motorcycles and
scooters, **three-wheelers including e-carts and e-rickshaws**, non-motorised
vehicles, tractors, and quadricycles. The stated reason is the speed differential
between fast and slow traffic. Access-controlled corridors are also
**grade-separated** — they use interchanges, not signalised crossings.

So the two facts compose:

> **If a road has a traffic signal, it is not access-controlled. If it is not
> access-controlled, three-wheelers and slow traffic are permitted — and present.**

This *inverts* the concern rather than confirming it. Every location this project
can legitimately study is a signalised intersection, and every signalised
intersection in India is one where auto-rickshaws, e-rickshaws and stray cattle
are legal and common. A National Highway running through a town — extremely common
in India — becomes a mixed-traffic arterial with signals, and is an **excellent**
filming site: high volume, genuinely heterogeneous, real signal cycle.

Conversely, an expressway with no signal is **out of scope entirely**, not because
of its vehicle mix but because there is no signal to control. The PPO half of this
project has nothing to act on there.

### The practical consequence

**Stop filtering candidate footage by "highway versus urban". Filter by:**

1. a **signalised** intersection in frame,
2. **mixed traffic** — three-wheelers visible,
3. a **stationary** camera,
4. **≥360 s** continuous (A15).

That is a cleaner inclusion criterion than any road-class label, and criterion 1
makes criterion 2 nearly automatic. `scripts/capture_stream.py --check` already
enforces 3 and 4 mechanically; 1 and 2 are a human glance at the first frame.

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

- **2026-08-14** — added §4.5 (two data needs; DataCluster Labs assessed; foreign footage
  becomes a domain-shift evaluation rather than training data) and §4.6 (the signal, not the
  road class, decides whether the India-specific classes are present).


| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial. IDD Detection selected as primary bootstrap; viewpoint gap documented |
