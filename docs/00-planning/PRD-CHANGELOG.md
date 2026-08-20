# PRD Change Log

Amendments to [PRD.md](PRD.md). The PRD declares itself a living document (§24.3), so changes are
recorded here rather than made silently. Every amendment names the section touched, the reason, and
the requirements affected.

**Rule:** when implementation reveals the PRD is wrong, amend the PRD and log it here. Do not work
around a PRD statement you believe is incorrect — a diverging PRD is worse than a wrong one, because
the team stops trusting it.

---

## v1.1 — 2026-08-07

Six amendments arising from the SDLC planning review. All are additive or clarifying; no
architecture, hyperparameter, or milestone was changed. Decision records:
[ADR-001](decisions/ADR-001-two-track-dataset-strategy.md) ·
[ADR-002](decisions/ADR-002-mfstnet-training-corpus.md) ·
[ADR-003](decisions/ADR-003-laptop-as-edge.md) ·
[ADR-004](decisions/ADR-004-phased-document-delivery.md)

### A1 — New §8.6, MFSTNet Training Corpus Construction

**Defect.** The PRD specified MFSTNet's input shape (`[B, 60, 3, 224, 224]`), its labels, and its
training hyperparameters, but never said where labelled sequences come from. IndiaTrafficNet is a
detection dataset of de-duplicated still frames with no temporal continuity. §20 L1 asserted training
on "SUMO sequences," which is incompatible with frozen ImageNet-pretrained backbones and would make
the fusion claim untestable.

**Change.** Added §8.6 specifying corpus construction: real video clips, YOLOv8-derived per-lane
counts, congestion labels from the §14.1 count thresholds, splits cut by source clip.

**Affects.** FR-M08, FR-M09, FR-M10, FR-M11, M4, M5. No requirement text changed; §8.6 supplies what
was missing.

**If this had not been caught,** it would have surfaced around Week 10 as non-convergence, which
§2.5.1 misattributes to normalisation or sequence-ordering bugs — sending the team to debug the wrong
thing during the tightest part of the schedule.

### A2 — §12.0, Two-Track Dataset Strategy

**Problem.** §12 sequenced all training behind Week 8 annotation completion. R2 (annotation
bottleneck) is rated High likelihood, and §2.5.1 independently predicts the overrun. M4, M5, and M7
all inherited that single unbuffered dependency.

**Change.** Added §12.0. Track A bootstraps YOLOv8 on a public Indian dataset from Week 2; Track B is
§12.1 unchanged, swapping in at Week 8.

**Affects.** FR-D08, FR-D09 (strengthened — the swap adds a comparative experiment), M1, M2, R2.
§12.1 substance unchanged.

**New obligation.** Experiments run between Weeks 2 and 8 must record which detector weights produced
them.

### A3 — §15.3 reframed, new §15.4 Delivered Prototype Configuration

**Problem.** §15.3's bill of materials totals ₹27,400–39,300 against a ₹0 budget. M8 depended on
hardware nobody had committed to buying, and Jetson Nano supply is now constrained.

**Change.** §15.3 relabelled as the aspirational deployment target. §15.4 added: laptop-as-edge,
on-screen signal panel, ₹0 total. MQTT contract, detection pipeline, Webster fallback, and emergency
preemption logic are unchanged.

**Affects.** FR-P01, NFR-01 (now measured on a laptop proxy and labelled as such), M8, R8. FR-A01
through FR-A06 unchanged — control logic is host-independent.

**New obligation.** Every latency table states its measurement host.

### A4 — §20 L1 rewritten; L1b and L8 added

**Problem.** L1 stated MFSTNet is trained on SUMO sequences. After A1 this is false, and it named the
wrong limitation.

**Change.** L1 now names the real limitation: labels are model-derived, so detector error propagates
into ground truth. L1b preserves the accurate part of the original — RL control results are
simulation-validated. L8 added for laptop-proxy latency measurement.

**Affects.** Paper limitations section; STR reporting obligations.

### A5 — New §24.4, Cost and Bill of Materials

**Change.** Added an explicit ₹0 baseline with optional upgrades and their trigger conditions.

**Why.** The budget constraint was implicit and therefore repeatedly re-litigated. Naming it once, as
a documented constraint (SOW C2), settles it.

### A7 — §15.2 Training Compute superseded

**Problem.** §15.2 assumed Colab-primary training, written before the team's hardware was known. It
also carried an ablation estimate of 60–90 h that R6 rated High-likelihood to overrun, mitigated by
cutting to 50 epochs.

**Change.** Training is local-first on an RTX 4050 / i5-13500HX laptop, using **cached backbone
features**. Because the backbones are frozen, their outputs are identical every epoch and can be
computed once; because ablation configs A–G differ only downstream of the backbones, one cache serves
all seven.

**Affects.** §15.2, R6 (mitigation no longer required — ablation runs at full 100 epochs), §8.4
`unfreeze_epoch` (see P3), NFR-01 (see below), M4, M5, M6, M7. No hyperparameter changed.

**New obligation.** Cache manifests record the git commit and preprocessing config; a mismatch at
load time is an error, not a warning. A stale cache produces results that look normal and are wrong.

**Note on NFR-01.** Under ADR-003 the edge node is this same laptop, whose RTX 4050 vastly
outperforms a Jetson Nano. The ≥10 fps figure will be met easily and is an **optimistic** proxy, not
a representative one. Report the measurement host, and additionally report a CPU-only figure as the
better proxy for constrained edge hardware.

### A6 — NFR-13 clarified

**Problem.** NFR-13 read "Raw video frames: NOT transmitted over network or stored to disk." Read
literally, A1's training corpus violates it, since building sequences requires retaining video.

**Change.** NFR-13 now states that it governs the **deployed runtime** — no frames leave the edge
device over the network or to disk in production — and explicitly does not govern the offline
training corpus, which is retained locally, excluded from version control, and never published.

**Affects.** NFR-13, §8.6. The privacy guarantee is unweakened; its scope is now stated rather than
inferred.

---

## v1.2 — 2026-08-08

Arising from the [feasibility audit](FEASIBILITY-AUDIT.md) and the
[corpus HLD](../02-design/HLD-detection-corpus-pipeline.md).

**A8–A12 applied as engineering amendments. A13 and A14 accepted by the project owner on
2026-08-13** and now in force. They change M1's acceptance criterion and several Must-Have
FR-UI/NFR targets, so the approval is recorded explicitly: **approved by the project owner, not
by a faculty guide.** If a guide later reviews scope, this line is the record of who decided.

| # | Section | Change | Source | Blocked? |
|---|---|---|---|---|
| A8 ✅applied | §8.1, §8.4 | Per-lane ROI pooling replaces global average pooling before the congestion head. As written, §8.1 pools away all spatial information then applies one shared head four times, yielding four identical predictions | Corpus spec §6 | No |
| A9 ✅applied | §8.6 | Verification budget concentrated on the test split (~150 sequences + 25 double-counted) rather than 500 spread across the corpus. Breaks circular evaluation and costs less | Corpus spec §5.2 | No |
| A10 ✅applied | §14.5 | Add density-stratified reporting alongside aggregate metrics | Corpus spec §5.3 | No |
| A11 ✅applied | §14.5 | Note that count-consuming baselines share error structure with auto-derived labels; verified test labels are what make the comparison valid | Corpus spec §5.1 | No |
| A12 ✅applied | §8.1, §8.2, §8.4, §9.4 | DINOv2 ViT-S/14 as the default ViT branch, supervised ViT-S/16 retained as ablation arm BB-1; add a 3-arm backbone ablation. Replace `unfreeze_epoch: 30` with a late LoRA experiment | [ADR-007](decisions/ADR-007-backbones-and-training-recipe.md) | No |
| A13 ✅**applied 2026-08-13** | §12, FR-D01..D07, M1 | Redefine Novel Contribution 1 as curate-then-collect: a harmonised benchmark plus a 1,500–3,000 frame campus set, replacing the 12,000-frame public-road campaign | [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) | **Yes** |
| A14 ✅**applied 2026-08-13** | §11, §16, FR-UI*, NFR-06, NFR-12 | Prototype descoping — SQLite+Parquet, 2 dashboard pages, shared password, 1-hour uptime test | [ADR-008](decisions/ADR-008-prototype-descoping.md) | **Yes** |

---

## v1.2 continued — 2026-08-10

Arising from an external technical review that found a **fatal mechanical bug** and two threats to
headline claims. All applied.

| # | Section | Change | Severity |
|---|---|---|---|
| A15 ✅ | §8.6 | **Window arithmetic corrected.** The label was placed at `t+60s`, which is *inside* the 295 s observation window — the model would read a frame it had already seen. Correct target is `t_end + 60 = t0 + 355 s`. Consequently the minimum clip is **6 min, not 5**; at 5 min the HLD's skip rule discards the entire corpus | **Fatal** |
| A16 ✅ | §13.1 | PPO state **17 → 16 dims**; `mfst_gate_mean` removed (no SUMO analogue — a dead input). Forecast fields sourced from a noise-calibrated surrogate; three policy arms. [ADR-009](decisions/ADR-009-ppo-forecast-surrogate.md) | High |
| A17 ✅ | §14.5 | **Transition-window recall becomes the headline metric**; persistence rate reported for every corpus. A 60 s horizon over 3 coarse classes is highly persistent, so Naive last-value may sit near the ceiling and no model could be ranked | High |
| A18 ✅ | §8.6 | Human verification **stratified by density**; test-split density bands re-derived from **human** counts, not the detector's. Closes the residual circularity in claim C5 | Medium |
| A19 ✅ | §14.5 | **Cluster bootstrap** — resample source clips, not sequences. Sequences from one clip share up to 54 of 60 frames; resampling them overstates precision. Report effective *n* | Medium |
| A20 ✅ | §14.5 | Gate-entropy regularisation contaminates claim C2. **Report both arms** — regularised and not | Medium |
| A26 ✅ | §17.1 | **Six MQTT payload defects closed** (TRIAGE-001 D1–D6) and QoS made a read-only property of the topic rather than a publish argument. Source of truth moves to `contracts/mqtt.py`. The contract test proved the old design failed open: assigning `Topic.EMERGENCY.qos` succeeded and downgraded emergency delivery process-wide | High |
| A25 ✅ | §14.5, FR-M11 | **Confusion matrix is now a required artifact.** ADR-009's PPO surrogate is defined as an oracle corrupted by MFSTNet's *measured* confusion matrix, per density band — but FR-M11 never required producing one, so claim C4 depended on an artifact nothing mandated. Also adds ordinal-aware metrics, because LOW/MEDIUM/HIGH are **ordered** and plain F1 scores a two-step error identically to a one-step error. Support reported beside every per-class figure | High |
| A24 ✅ | §8.1 Stage 1–2 | **The two fusion branches did not have the same token count, so the gate could not execute.** Cross-attention returns one output per query: `Z_A` carries the CNN's 49 tokens, `Z_B` carries the ViT's 197 (original) or 257 (DINOv2). `g·Z_A + (1−g)·Z_B` is elementwise and needs identical shapes. **Present since v1.0 — not caused by the DINOv2 switch.** Fixed by aligning both branches onto a shared G×G grid before Stage 2, which also gives ROI pooling (A8) the spatial map it requires. G=7 default; cost scales as (G²)² and cross-attention is not cached | **Fatal** |
| A22 ✅ | §14.4 | **Ablation config H — linear probe.** A–G all contain a BiLSTM, so none answers whether the temporal machinery earns its place. H is the standard frozen-backbone floor and its absence was an omission. If H approaches G, the architecture is unjustified — report it | High |
| A23 ✅ | §8.4, §14.4 | **Report MFSTNet over 5 seeds with 95% CI.** The RL half runs 30 seeds; the model half reported one. A two-point F1 gap between configs is meaningless without seed variance. Cached features make it nearly free | Medium |
| A21 ✅ | §14.3 | §14.3 declared the **single authoritative baseline list**; §3's prose list and §14.4's ablation configs are subordinate | Low |

Also: [ADR-010](decisions/ADR-010-sumo-heterogeneous-traffic.md) adds the SUMO sublane model and
heterogeneous vTypes, because the default lane-following model does not represent the unstructured
traffic the paper is about. No PRD section changed; FR-S01/S02 acceptance gains configuration detail.

### Why A15 was missed

The window arithmetic was never done end to end. Each document repeated `T=60 @ 5s` and
`horizon 60s` correctly in isolation; nobody added 295 + 60 and compared it against "5-minute clips."
The HLD's golden test was designed to catch horizon **off-by-one** errors — it would not have caught
a corpus of size zero, because with no sequences there is nothing to test.

**Lesson recorded:** any spec containing two independently-stated durations needs one worked example
with real numbers. Added to the wave-gate reconciliation checklist.

## Pending — items to revisit

Not defects, but places where the PRD will need amendment once implementation produces evidence.
Reviewed at each wave gate (W05, W11, W16).

| # | Item | Revisit at | Why |
|---|---|---|---|
| P1 | §14.1 count thresholds (LOW <5, MED 5–15, HIGH >15) are per-lane absolute counts | W9, after first corpus build | If the class distribution proves severely skewed on real footage, thresholds may need recalibration. Any change invalidates every prior label and must be logged |
| P2 | §13.1 state normalisation divisors (`count/50`, `queue/200`) | W10, after SUMO calibration | Chosen before real count data existed. If real counts exceed them, states saturate at 1.0 and the agent goes blind to the busiest conditions |
| P3 | §8.4 `unfreeze_epoch: 30` | W12 | R4 anticipates ViT overfitting. Amendment A7 additionally makes unfreezing incompatible with feature caching, so it is now a separate later experiment rather than a mid-run transition. Decide explicitly and log it |
| P4 | Ablation epoch count (100 → 50) | W13 | R6 mitigation, **likely unnecessary after A7** — cached features make the full 7-config ablation cheap. If invoked anyway, log it; the paper must state ablation used fewer epochs than the headline model |
| P5 | §20 L1 label-noise estimate | W12 | The verification subset produces a number that belongs in the PRD |
| ~~P6~~ **CLOSED — mis-analysis, withdrawn** | FR-R04 starvation vs FR-A03/FR-A04 | Closed 2026-08-10 | **The finding was wrong.** It conflated *cycle length* with *lane wait*. A lane is served in one phase, so it waits for the **other** phase's green plus two all-reds — `90 + 2×3 = 96 s`, well under the 180 s limit. No contradiction; no PRD value changes. The threshold is correctly calibrated for what it actually governs: two consecutive 90 s greens give 189 s (penalised), two consecutive 60 s greens give 129 s (tolerated). See [ADR-011](decisions/ADR-011-webster-definition.md) §Decision 2 |
| **P9** | **Is phase repetition legal?** | **Before M6 (W13)** | Exposed by correcting P6. The action space is (phase, duration) with nothing forbidding NS→NS. If repetition is forbidden, starvation is structurally impossible and FR-R04 is dead code; if permitted, the penalty is load-bearing. `spec.yaml` sets `phase_repetition_allowed: true` as a working default so the two readings cannot diverge silently — confirm it against comparable published action-space definitions |
| **A27** | **Yellow interval was missing from the signal specification entirely** — added, and every derived signal figure corrected with it | §9.6, FR-A04, FR-R04, ADR-011 | `spec.yaml` fixed min green, max green and all-red but never a yellow interval, so every derived number was computed as if amber did not exist. Building the real SUMO network in S32 made it visible: netconvert emits a yellow phase whether or not the specification mentions one. Corrections: worst red per approach **96 -> 99 s** (an approach is red for the other phase's green *and* its yellow, plus both all-reds; its own yellow is not wait time, because traffic still discharges then). Webster clamp bounds **[26, 186] -> [32, 192] s** — the old ceiling was *below* the cycle the network can actually produce, so Webster would have clamped on every cycle and ADR-012's reported clamp rate would have been meaningless. Starvation margin narrows from 84 s to 81 s and still holds |
| **P10** | **What may be published from IndiaTrafficNet?** | **Before S18 collection** | India's DPDP Rules were notified 13 Nov 2025, with full enforcement from 13 May 2027 — inside this project's publication window. Street footage contains identifiable faces and number plates. NFR-13 governs runtime *transmission*; publishing a dataset is a different act and carries the exposure. [ADR-013](decisions/ADR-013-artifact-hosting-and-publication.md) ranks three options — annotations-only, blurred frames, or derived statistics — and raw unblurred frames are excluded under all of them. **The guide picks the option before frames are collected**, because that is the last point at which the cheap answer is still available |
| **P11** | **State index 10 (`phase_remaining`) carries no information** | **Before M6 (W13)** | Found in S36 by measuring the observation rather than trusting the spec. The §13.1 action space is 12 discrete (phase, duration) pairs, so the agent acts only at phase end — by which time the requested green has fully elapsed and `phase_remaining` is 0 at **every** decision point. §13.1 lists the feature assuming a controller that can observe mid-phase; its own action space is one that cannot. One of sixteen dimensions is dead. Two resolutions: (a) change the action space to a fixed decision interval with keep-or-switch actions, the standard RL traffic-control formulation, which makes the feature meaningful — a **PRD amendment**, not a code edit; or (b) accept the dead index, document it, and keep it zeroed for contract compatibility (FR-M14 forbids shortening the vector). Asserted by `test_phase_remaining_is_structurally_zero_at_decision_points` so it cannot be forgotten |
| **P13** | **No learned baseline exists — §14.3's baselines are all rule-based thresholds** | **Before the ablation table is written** | Raised from Saxena et al., IEEE TITS 26(6) 2025, which reaches 92.5% on a three-class congestion task using gradient-boosted trees on tabular features. A learned tabular baseline is therefore both standard and cheap. Add XGBoost, plus a logistic-regression floor, over the same per-lane count windows MFSTNet consumes — same splits, same seeds — as a **row in the §14.4 ablation table**, not a footnote. **If ResNet-50 + DINOv2 + bidirectional cross-attention + BiLSTM cannot beat trees on raw counts, that is the single most important finding this project could produce**, and it costs minutes of CPU. Far better discovered on our own schedule than in review. See [RELATED-WORK](RELATED-WORK.md) |
| **P14** | **BMD-45 changes the detector plan: Indian elevated CCTV data exists under CC BY 4.0** | **Before any further detector training** | 45,986 images / 481,947 boxes from 3,679 Safe City CCTV cameras in Bengaluru, incl. **65,899 three-wheeler boxes** at the deployment viewpoint, against 1,001 dashcam auto-rickshaw boxes in the whole IDD test split. Directly addresses the gap P5 rev 2 measured. **Does not replace IDD** — it has no `pedestrian` and no `cattle`, so the two are complementary and must be trained **jointly, not sequentially** (a sequential IDD stage ends on 100% dashcam data and un-teaches the geometry). Needs a taxonomy merge (4 car subtypes → `car`, `Bus`+`Mini-bus` → `bus`, `Truck`+`LCV` → `truck`) and a check whether `Three-wheeler` conflates auto- with e-rickshaw, which bears on P12 but does not change its pre-registered 1% rule. 153.2 GB, so subsample inside Kaggle rather than downloading locally. See [DATASETS](DATASETS.md) |
| ~~P7~~ **CLOSED** | MQTT payload schema defects | Closed 2026-08-13 | All six closed by amendment A26 and `contracts/mqtt.py`, with a 31-assertion cross-topic contract test. TRIAGE-001 closed |
| ~~P8~~ **CLOSED** | Webster parameterisation | Closed 2026-08-10 | [ADR-011](decisions/ADR-011-webster-definition.md) settled cycle clamping, splits and the two roles. [ADR-012](decisions/ADR-012-webster-saturation-flow.md) settles saturation flow and lost time: the published range spans 525W–1283W PCU/h per metre of approach width, so **sweep it and report Webster's best** rather than picking a value. PCE motorcycle 0.24, auto-rickshaw 0.78. Lost time 4–5 s start, ~3 s clearance |

---

## A28 (proposed) — `step_s` is a pilot-determined parameter, not a fixed 5 s

**Raised** 2026-08-15 · **Affects** PRD §8.2, §8.6, A15, `spec.yaml sequence.step_s`
**Status** PROPOSED — needs guide sign-off

### The problem

A15 fixed the minimum clip length at **355 s**, derived as `(T−1)·step_s + horizon_s`
= 59×5 + 60. Forty-two candidate clips were then rejected against it, several of them
excellent Indian intersection footage with verified-stationary cameras.

**But `step_s = 5` is not derived anywhere.** T=60 and the 60 s horizon both trace to
stated requirements; the 5 s spacing appears in §8.2 as a bare number. The minimum
clip length — the single constraint that has blocked S06 for two weeks — rests
entirely on it.

### What changes if it moves

Measured against the 42 triaged clips (`experiments/results/footage_triage.csv`),
counting only those whose camera already passes the stationarity check:

| `step_s` | history span | min clip | clips that qualify |
|---|---|---|---|
| 5 (current) | 295 s | 355 s | **8** — all Western motorways |
| 4 | 236 s | 296 s | 10 |
| 3 | 177 s | 237 s | 11 |
| **2** | **118 s** | **178 s** | **12** |
| 1 | 59 s | 119 s | 13 |

At `step_s = 2` three Indian and Delhi clips become usable that are currently rejected
**purely on this arithmetic**:

| Clip | Duration | Camera |
|---|---|---|
| Mumbai Traffic Chaos — Near Andheri Station | 349 s | jitter 0.74 px, drift 32.7 px (1.7%) — **passes** |
| South Extension, multi-coloured buses and autos | 264 s | jitter 1.12 px — **passes** |
| `video1.mp4` | 183 s | jitter 0.47 px, drift 1.7 px (0.1%) — **passes** |

The Andheri clip is the best-composed Indian intersection scene in the entire
collection: elevated, stationary, black-and-yellow auto-rickshaws throughout, BEST
bus, handcarts, pedestrians.

### Is 118 s of history enough?

Not obviously, and that is the point — **neither is 295 s obviously necessary.** Both
are assertions. What can be said:

- The signal cycle in this project is clamped to **32–192 s** (A27). 118 s covers most
  of a cycle; 295 s covers one and a half to nine.
- Sampling every 2 s captures queue build-up and discharge at a resolution 5 s misses,
  which is the dynamic the forecast depends on.
- Traffic autocorrelation decays. 60 samples at 5 s spacing may be largely redundant.

### Decision requested

**`step_s` becomes an output of the Week-2 pilot rather than an input to it.** The A17
transition-rate analysis measures the timescale on which the congestion class actually
changes; the sampling interval should be set from that measurement, with **2 s as the
working default** because it unlocks the footage already in hand.

Rejecting real footage to protect a number nobody derived is the wrong trade. If the
pilot shows the class changes on a 300 s timescale, `step_s = 5` is vindicated and the
clips are correctly rejected — but that will be a finding rather than an assumption.

**Nothing is relaxed by this.** T=60, the 60 s horizon, clip-level splits, the
stationary-camera requirement and the human-verified test split are all untouched. One
undocumented constant becomes measured.

### The circularity in the version above, and how it is removed

**As first written, this amendment committed the error it was meant to avoid.** The
table lists five candidate values; `step_s = 2` is the *smallest one that unlocks
exactly the three clips already in hand*. That is a parameter chosen after seeing which
value makes the available data pass — structurally identical to the 15% success
threshold rejected in [ADR-015](decisions/ADR-015-success-criteria-and-priorities.md)
Decision 1, and no more defensible for being a preprocessing constant rather than a
success metric.

A pre-committed decision rule does not fix it, because the pilot as scoped would have
run on **the three clips that need the answer to come out a particular way**.

**The fix is to decouple the measurement from the selection**, which is possible because
they have different data requirements:

| | needs | available |
|---|---|---|
| **Measuring** the transition timescale | a clip long enough to observe several class changes — roughly 120 s | **20+ clips** |
| **Training** on a clip | ≥ `(T−1)·step_s + horizon` | 8 to 13 clips, depending on the value being chosen |

The timescale can therefore be measured at **1 s resolution on every clip over ~120 s**,
including every clip this amendment would *not* rescue. The measurement does not depend
on the threshold, so it cannot be bent by it.

**Pre-registered before the pilot runs:**

1. Sample the congestion class at **1 s** on every clip ≥ 120 s, whatever its verdict.
2. Report the transition timescale for **South Asian junction footage and Western
   motorway footage separately.** They are different processes — a motorway has no
   signal, no cycle and often no congestion — so pooling them would average two
   distributions and call the result stability. A large difference between them is
   *expected* and is not evidence of instability.
3. **The exact statistic, fixed now.** `step_s = ceil(P75 / (T−1))`, where P75 is the
   **75th-percentile inter-transition interval** in seconds across qualifying South
   Asian clips, and T=60. Nothing is chosen after the numbers are seen.

   A high percentile and a ceiling are both deliberate: **each pushes toward a LARGER
   `step_s`**, which is the direction *against* the outcome this amendment would prefer.
   A 25th percentile with rounding-down was considered and rejected for exactly that
   reason — it biases toward the small values that rescue the clips in hand, which is
   the flexibility this pre-registration exists to remove. When a statistic must be
   picked in advance, pick the one that makes your preferred answer harder.
4. **If that rule selects 5 s, the three clips stay rejected** and this amendment is
   withdrawn.
5. Any timescale estimated from fewer than 5 **independent** clips is reported as
   **preliminary**, never as the basis for a final value. **Independent means a distinct
   physical camera and location** — not a distinct file. Two recordings of the same
   junction at different times are correlated observations of one process, and counting
   them separately would inflate confidence in a result resting on fewer vantage points
   than it appears to.

### The census, stated plainly rather than implied

"20+ clips" is true and misleading. The honest breakdown of the 33 clips over 120 s:

| | count |
|---|---|
| Measurable (≥120 s) | 33 |
| South Asian / Indian | 20 |
| Western motorway / other | 13 |
| **South Asian AND camera passes stationarity** | **6** |
| **South Asian, stationary, distinct location** | **~4** |

The six are Dhaka Rampura (×2, evidently the same vantage point), Mumbai Andheri,
South Extension (×2, same location), and `video1`. That is roughly **four independent
South Asian vantage points**, against a rule requiring five.

**So rule 5 will almost certainly trigger on the exact population the PRD's core claim
depends on.** The pilot runs on 33 clips and will still be *preliminary for Indian
signalised junctions*. This must be said to the guide in those words — "20 clips" would
imply coverage that does not exist.

It also settles the standing of self-filming. It is not merely the good path running in
parallel: **it is the only route by which this measurement stops being preliminary on
the side that matters.** One additional independent vantage point takes the count from
four to five.

### The cost, in hours — and a correction

The "2.5×" figure was quoted without absolute numbers, which was the right thing to
object to. Measured over the 33 clips:

| | frames | at 25 fps | at 40 fps |
|---|---|---|---|
| `step_s = 5` | 4,142 | 0.05 h | 0.03 h |
| `step_s = 2` | 10,382 | **0.12 h** | 0.07 h |
| difference | +6,240 | **+0.07 h (~4 minutes)** | +0.04 h |

**The correction runs opposite to the way it was framed.** Presented as a multiplier,
2.5× sounded like a genuine trade-off worth weighing. In absolute terms it is roughly
**four minutes of GPU time**. The compute objection to this amendment does not survive
contact with the arithmetic, and it should not be offered at sign-off as though it did.

What remains a real cost is neither compute nor annotation: it is **one more PRD
amendment awaiting a decision** at a point where three already are.

### The cost this amendment did not price

`step_s = 2` samples **2.5× more densely**, so building the corpus needs 2.5× the
detector inference passes — 175 frames rather than 70 for a 349 s clip.

One clarification on the comparison, because the two costs are in different currencies.
The [FEASIBILITY-AUDIT](FEASIBILITY-AUDIT.md)'s 3× underestimate concerns **human
annotation hours** for IndiaTrafficNet, which trains the detector. The corpus is
**auto-labelled** (ADR-002), so this is GPU time, not person-time, and it does not
compound with that finding. It is still a real cost and it is still 2.5×.

**Weighed against the alternative it is not obviously worth it.** One clean 15-minute
recording satisfies `step_s = 5` with four times the margin, needs no amendment, no
sign-off and no extra compute. This amendment exists to make already-collected footage
usable **in parallel with** filming, never instead of it — ADR-015 Decision 5's P0 track
is unchanged.

---

## P5 — label noise, measured (2026-08-15)

Pending item P5 asked for an estimate of label noise in the auto-labelled corpus
(ADR-002). It has been carried as a worry since the corpus spec was written. Here
is a number.

Measured on the Mumbai Andheri clip, 365 samples at 1 Hz, stock COCO YOLOv8n,
whole-frame counts:

| | |
|---|---|
| Count range | 6 – 23, median 13 |
| Adjacent-second \|difference\| | mean 2.00, median 2, max 7 |
| **Implied detector noise (sd)** | **~1.13 vehicles** |
| Smoothed signal (sd) | ~3.30 vehicles |
| **Signal-to-noise** | **2.92** |
| **Samples within one noise-sd of a §14.1 threshold** | **26%** |
| Label changes | 0.071 / s — one every ~14 s |

**Real traffic barely changes in one second, so most of the adjacent-sample
difference is the detector disagreeing with itself.** That gives a direct noise
estimate without needing ground truth.

### The finding

**About a quarter of frames carry a label that detector noise alone can flip.**
Counts near 4 or 15 sit inside the noise band, so their LOW/MEDIUM or MEDIUM/HIGH
assignment is close to a coin toss. A corpus auto-labelled from these counts
inherits that directly.

It also explains the A17 pilot: the transitions being counted were largely
threshold-crossing noise rather than congestion changing.

### Replicated across four independent vantage points

The single-clip figure above was extended to every stationary South Asian clip
at a **distinct camera and location** (`experiments/results/p5_label_noise.csv`):

| Vantage point | n | median count | noise sd | signal sd | SNR | near threshold |
|---|---|---|---|---|---|---|
| Mumbai Andheri | 365 | 13 | 1.13 | 3.30 | 2.92 | **26%** |
| Dhaka Rampura | 400 | 8 | 1.46 | 3.01 | 2.06 | **19%** |
| Delhi South Extension | 265 | 21 | 2.08 | 6.77 | 3.25 | **23%** |
| `video1` | 187 | 5 | 0.83 | 1.86 | 2.24 | **11%** |

**The consistency is the result.** Four unrelated locations, three cities, two
countries, day and night, counts from 5 to 21 — and signal-to-noise lands
between **2.06 and 3.25** every time, with **11–26%** of labels inside the noise
band. This is not a quirk of one clip.

**Noise scales with density**, and that has a design consequence. `video1` at a
median of 5 vehicles shows noise of 0.83; South Extension at 21 shows 2.08. So
the **HIGH threshold at 15 sits in a noisier regime than the LOW threshold at 4**,
and uniformly spaced thresholds are not uniformly reliable. §14.1's boundaries
should be checked against the noise at their own density, not chosen on the count
scale alone.

### Caveats — an upper bound, and one vantage point short

* **Stock COCO YOLOv8n**, not the fine-tuned detector S08–S12 will produce. A
  detector trained on Indian classes should be markedly quieter, so these are
  ceilings rather than expected values.
* **Whole-frame counts**, not per-lane. Per-lane counts are smaller, so a fixed
  threshold sits differently against the noise.
* **Four independent vantage points against A28's bar of five.** By this project's
  own rule this remains **preliminary** — consistent, replicated, and one location
  short of the standard it set for itself.

### What follows

1. **Run this again after S08–S12.** The comparison stock-vs-fine-tuned is itself
   a reportable result, and it quantifies what the detection work buys the corpus.
2. **Thresholds should be checked against the noise band, not only against
   traffic.** A threshold sitting where 26% of the mass is unstable is badly
   placed regardless of whether the class balance looks reasonable.
3. **Report this in the paper.** A corpus paper that states its label-noise
   estimate is more credible than one that does not mention it, and reviewers of
   auto-labelled datasets ask.

---

## P5 rev 2 — the fine-tuned detector did NOT reduce label noise (2026-08-15)

The S11 detector was trained precisely so this could be measured: the earlier P5
figures came from stock COCO YOLOv8n, a model with no auto-rickshaw class at all,
so they were declared an upper bound that fine-tuning should improve.

**It did not.** `experiments/results/p5_label_noise_comparison.csv`, same four
independent vantage points, same 1 Hz sampling, same smoothing:

| | stock COCO | S11 fine-tuned |
|---|---|---|
| median detector noise (sd) | **1.29** | 1.34 |
| median signal-to-noise | **2.58** | 2.01 |
| median labels within a noise-sd of a threshold | **21%** | 28% |

Every headline moved the wrong way. And the reason is visible in the counts:

| Vantage point | stock | tuned | change |
|---|---|---|---|
| Mumbai Andheri | 13 | 6 | **−54%** |
| Dhaka Rampura | 8 | 4 | **−50%** |
| Delhi South Extension | 21 | 24 | +14% |
| `video1` | 5 | **0** | **−100%** |

**The fine-tuned detector sees roughly half the vehicles, and on one clip none at
all.** Its SNR on `video1` is 1.04 — indistinguishable from noise.

### This is not a broken model, it is the viewpoint gap — measured

The same weights score **mAP50 0.6201** on IDD's own test split, with
`auto_rickshaw` at 0.703. The detector works. It works *on dashcam imagery*,
because that is all IDD contains — a car-mounted rig at roughly 1.5 m, where
vehicles are large and near.

These clips are elevated fixed cameras looking down at a junction, where vehicles
are small and distant. That is precisely the gap [DATASETS §2](../00-planning/DATASETS.md)
opens with and the reason `class_mapping.yaml` weights side views. **It has now
been measured rather than asserted, and it is severe.**

### Consequences, and they are not small

1. **The S11 detector cannot auto-label the corpus as it stands.** ADR-002 derives
   every congestion label from detector counts. A detector that misses half the
   vehicles produces labels that are wrong in a systematic, direction-consistent
   way — far worse than the random noise P5 was originally measuring.
2. **ADR-001's bootstrap strategy is insufficient by itself.** "Fine-tune on a
   public Indian dataset, swap in IndiaTrafficNet at Week 8" assumed the public
   dataset transfers. For classes it does; for *viewpoint* it does not.
3. **The one fix that works is the one already blocked.** Elevated fixed-camera
   footage is needed as *training* data, not only as evaluation data — which
   raises S06 from important to load-bearing for the detector track too.
4. **S12's cross-camera experiment is now the priority**, because it measures how
   far viewpoint transfer degrades *within* IDD and therefore how much elevated
   data the fine-tune will need.

### What must not be done

Reporting the S11 mAP of 0.62 as the detector's performance without this result
beside it. The number is true on IDD and misleading about deployment, which is
the exact shape of claim this project has spent its effort removing.

**This is a negative result and it is reported, not buried** (PRD §2.5.5, BR-19).
It is also the most useful thing the detector track has produced: it converts a
documented worry into a measured constraint, before 12,000 frames were annotated
against a detector that cannot see them.

---

## A29 (proposed) — FR-A05's 3-second preemption bound contradicts FR-A03 and FR-A04

**Raised** 2026-08-16 · **Affects** PRD §9.6 FR-A05 · **Status** PROPOSED — needs guide sign-off

Found while implementing emergency preemption, which the PRD has required all
along and which nothing had implemented.

FR-A05: *"Emergency preemption SHALL override PPO: clear emergency lane green
**within 3 seconds**."*

That is unreachable whenever the emergency approach is red, because two other
Must-Have requirements stand in the way:

* **FR-A04** — all-red clearance, minimum 3 s between transitions.
* The program also runs 3 s of yellow, so **a phase change costs 6 s** before the
  emergency approach can legally see green.
* **FR-A03** — minimum green 10 s. Preemption arriving just after a green starts
  waits out the rest of it.

Measured on the real runner (`Fixed(green_s=30)`, saturated, seed 42):

| emergency | latency | |
|---|---|---|
| N at t=5 s | **0 s** | already green — the only case the bound is met |
| N at t=41 s | **15 s** | |
| E at t=5 s | **11 s** | |
| E at t=40 s | **6 s** | the floor: yellow + all-red |

**Worst observed 15 s against a specified 3 s.** The floor is 6 s and cannot be
lowered without deleting clearance.

### The implementation does not resolve this by cheating

Preemption overrides the controller — a controller that permanently demands the
wrong phase still loses, asserted by
`test_preemption_overrides_a_controller_that_refuses_to_yield`. But it does not
override safety. Reaching green sooner by dropping the interphase would release
one approach into an intersection another is still crossing.
`test_preemption_never_skips_yellow_and_all_red` fails if a future edit
"optimises" the latency that way.

`test_fr_a05_three_second_bound_is_unreachable_when_the_approach_is_red`
asserts the defect itself, so it cannot quietly stop being true.

### Proposed amendment

> FR-A05 — Emergency preemption SHALL override the controller within **1 signal
> decision step**, and SHALL clear the emergency approach to green at the
> earliest time permitted by FR-A03 and FR-A04. Clearance intervals SHALL NOT be
> shortened for preemption. The measured latency SHALL be reported per episode.

This keeps the intent — nothing outranks an ambulance except physics — while
stating a bound that can be met and verified. The published figure becomes a
**measured latency distribution**, not an unmet assertion.

**Do not implement against this until the guide signs off.** The code above is
the safe behaviour under the *existing* requirements; only the numeric claim in
FR-A05 is in question.

---

## S13 — the viewpoint gap measured as mAP, and FR-P02 measured for the first time (2026-08-16)

P5 rev 2 showed detector counts halving on elevated footage and attributed it to
viewpoint. That was an inference from counts, on unlabelled clips. BMD-45 provides
**labelled** elevated Indian CCTV, so the same claim can now be tested directly.

498 BMD-45 images, 5,273 vehicle boxes, evaluated with the unchanged S11 weights
(`experiments/results/s11_on_bmd45_elevated.csv`).

### The gap is not subtle

| class | IDD test (dashcam) | BMD-45 (elevated) | change |
|---|---|---|---|
| car | 0.717 | 0.525 | −27% |
| motorcycle | 0.662 | 0.381 | −42% |
| **auto_rickshaw** | **0.703** | **0.349** | **−50%** |
| bus | 0.729 | 0.109 | **−85%** |
| truck | 0.689 | 0.248 | −64% |
| **overall mAP50** | **0.6201** | **0.3223** | **−48%** |

**mAP50 halves.** `auto_rickshaw` — the class the entire India-specific argument
rests on — loses half its performance. `bus` very nearly disappears.

**Precision holds while recall collapses.** `auto_rickshaw` precision falls only
0.847 → 0.719, but recall falls 0.626 → 0.293. The detector is not confused about
what it sees; it does not see. That is the signature of a scale and geometry
mismatch, not a class-confusion problem, and it is why more Indian *dashcam* data
would not have fixed it.

This independently corroborates BMD-45's own reported figure — UA-DETRAC-tuned
models reach 33.6% mAP@0.50:0.95 on this data against 83.8% in-domain — from a
different starting point, which is worth more than either number alone.

### FR-P02 has never been measured. It has now, and it fails

"System SHALL detect and count vehicles per lane" is Must Have and is the
backbone of everything downstream. `experiments/results/counting_accuracy.csv`:

| | |
|---|---|
| true vehicles | 5,273 |
| detected | **2,061** |
| detected / true | **0.391** |
| mean signed error | **−6.45 vehicles/frame** |

**The detector finds 39% of the vehicles.** mAP would never have said this
plainly: mAP is a per-class ranking measure over IoU thresholds, a count is one
integer per frame, and a detector can hold a respectable mAP while losing the
same fraction of vehicles in every frame.

### The finding that changes the plan

| | mean true count | detected / true |
|---|---|---|
| sparsest third | 3.8 | **0.480** |
| densest third | 18.7 | **0.368** |

**The shortfall is not a constant — it grows with density.** That distinction
decides whether this is fixable by recalibration:

* A *constant* fraction would be correctable. The §14.1 count thresholds could be
  divided through and the congestion labels would survive.
* A fraction that **falls as density rises** compresses the top of the range. The
  gap between a MED scene and a HIGH scene shrinks precisely where the label
  needs it to be widest.

So the §14.1 thresholds **cannot be recalibrated around this**, and ADR-002's
auto-labelling would not merely be noisy on elevated footage — it would be
**biased toward "less congested"**, which is the worst available direction for a
congestion predictor. A model trained on those labels would learn to under-call
exactly the congestion it exists to predict.

### Consequences

1. **The S11 detector must not auto-label any elevated corpus.** Not as a caution
   — as a measured prohibition.
2. **Joint BMD-45 + IDD training is now the critical path**, not an improvement.
3. **This is a publishable result on its own.** A quantified cross-viewpoint
   generalisation gap for Indian traffic detection, with the recall/precision
   decomposition that identifies the cause, is a contribution independent of
   whether MFSTNet beats its baselines.
4. **FR-P02 needs an acceptance threshold.** It currently states a capability with
   no number attached, which is how it went unmeasured for the whole project.
   Proposed with A30, once the joint model gives a figure worth setting it against.

Credit where it belongs: this was found because the question "shouldn't we
measure vehicle count?" was asked. It was already required, already relied upon,
and nobody had checked it.

---

## S14 — joint BMD-45 + IDD training closes the viewpoint gap (2026-08-16)

The run S13 made the case for. `yolov8s`, 60 epochs, seed 42, identical recipe to
S11 so the comparison is about **data, not hyperparameters**. Trained on the
mapped union; evaluated on the two test splits **separately**, which is the whole
reason they were kept apart.

### Elevated CCTV — the gap is closed

`experiments/results/s14_metrics_bmd45.csv`, 1,200 frames / 12,357 vehicles:

| class | P | R | mAP50 | mAP50-95 | boxes |
|---|---|---|---|---|---|
| car | 0.860 | 0.900 | **0.920** | 0.813 | 2,770 |
| motorcycle | 0.870 | 0.828 | **0.906** | 0.698 | 5,910 |
| **auto_rickshaw** | 0.883 | 0.867 | **0.914** | 0.784 | 2,132 |
| bus | 0.852 | 0.805 | 0.876 | 0.749 | 606 |
| truck | 0.797 | 0.774 | 0.841 | 0.698 | 939 |
| e_rickshaw · pedestrian · cattle | — | — | — | — | 0, NOT EVALUATED |

**Overall mAP50 0.8915** (S11: 0.3223) · **mAP50-95 0.7485**

`auto_rickshaw` **0.349 → 0.914**, recall **0.293 → 0.867**. The class the entire
India-specific argument rests on went from missing seven vehicles in ten to
finding nine in ten, at the deployment viewpoint.

### Dashcam — no trade

`experiments/results/s14_metrics_idd.csv`, 1,170 frames / 8,287 vehicles.
**Overall mAP50 0.6174** against S11's **0.6201** — a 0.4% difference.

| class | S11 | S14 | |
|---|---|---|---|
| car | 0.717 | 0.713 | −0.004 |
| motorcycle | 0.662 | 0.678 | **+0.016** |
| auto_rickshaw | 0.703 | 0.711 | **+0.008** |
| bus | 0.729 | 0.714 | −0.015 |
| truck | 0.689 | 0.696 | **+0.007** |
| pedestrian | 0.478 | 0.458 | −0.020 |
| cattle | 0.362 | 0.352 | −0.010 |

Three up, four down, net −0.4%. **Elevated performance nearly tripled at no
measurable dashcam cost**, and this is a claim rather than a hope only because
the test splits were never merged.

**The two that fell are the two only IDD supplies.** `pedestrian` and `cattle`
have no elevated source, so joint training dilutes them without giving anything
back. −0.020 and −0.010 are small, but the direction is systematic and predicted,
and it is recorded rather than averaged away.

### Counting — much better, not yet enough

| | S11 elevated | **S14 elevated** | S14 dashcam |
|---|---|---|---|
| detected / true | 0.391 | **1.178** | 0.813 |
| sparsest third | 0.480 | 1.285 | 1.033 |
| densest third | 0.368 | 1.149 | 0.775 |

It now **over-counts by 18%** instead of missing 61%, and the density dependence
more than halved in relative terms (−23% across the range → −11%).

**ADR-002's auto-labelling stays blocked on elevated footage, for two reasons.**

1. **The density slope is reduced, not removed.** A single recalibration constant
   still leaves MED and HIGH compressed against each other, which is exactly the
   distinction the label turns on.
2. **The over-count is unexplained, and an unexplained error is not a corrected
   one.** 1.285 in the *sparsest* frames — where annotation is easiest and
   crowding cannot excuse it — points at false positives rather than at
   annotators missing vehicles. That is a hypothesis, and it is checkable by
   rendering predictions against ground truth. Until it is checked, the
   convenient reading is not the one to adopt.

### What is now established

**A camera-only detector that works at the deployment viewpoint**, with the
India-specific class at mAP50 0.914 — and a measured cross-viewpoint gap, its
cause (recall collapse, not class confusion), and its closure. That sequence is
publishable independently of whether MFSTNet beats its baselines.

Weights are gitignored per ADR-013 rev 2. The four CSVs are committed as written
by the scripts, never transcribed (NFR-09), and the per-frame counting files were
independently re-aggregated locally to confirm the run's summary figures.

---

## S14b — the over-count was the operating point, not the model (2026-08-16)

S14 left one thing unexplained, and auto-labelling stayed blocked on it: the
joint detector over-counted elevated frames by 18% (ratio 1.178), with the ratio
still varying across density. The convenient reading was "BMD-45's annotators
missed small vehicles". That reading was not adopted; it was tested.

### Matching predictions to ground truth named the excess

498 elevated frames, 5,273 ground-truth vehicles, IoU ≥ 0.5:

| | |
|---|---|
| matched | **5,010** (95% of ground truth found) |
| unmatched predictions | **1,172** — 19% of all detections |
| missed ground truth | 263 |

The unmatched detections are not like the matched ones:

| | matched | unmatched |
|---|---|---|
| median confidence | **0.863** | **0.415** |
| median box area | 4,330 px | **1,494 px** |

**64% of them sit below confidence 0.5**, and they are roughly a third the area of
a real vehicle box. That is a threshold signature, not a modelling failure.

### The reason this was missed for two steps

**mAP is threshold-independent; a count is not.** mAP integrates over the whole
precision-recall curve, so the operating point never enters it. A count is one
integer per frame produced at exactly one threshold — and that threshold was
Ultralytics' default of 0.25, which nobody had ever chosen for counting.

### Sweeping it settles the question

`experiments/results/s14_counting_threshold_sweep.csv`:

| conf | detected/true | sparsest third | densest third | MAE |
|---|---|---|---|---|
| 0.25 (default) | 1.172 | 1.215 | 1.169 | 2.00 |
| 0.35 | 1.079 | 1.121 | 1.075 | 1.35 |
| 0.40 | 1.037 | 1.061 | 1.036 | 1.15 |
| **0.45** | **0.999** | **1.025** | **0.997** | **1.07** |
| 0.50 | 0.964 | 0.989 | 0.958 | 1.10 |
| 0.60 | 0.901 | 0.944 | 0.892 | 1.36 |

At conf 0.45 the ratio is **0.999** and the density spread collapses to **0.028**:

| | ratio | sparse → dense spread |
|---|---|---|
| S11, dashcam-only | 0.391 | 0.112 |
| S14 at conf 0.25 | 1.172 | 0.046 |
| **S14 at conf 0.45** | **0.999** | **0.028** |

The density dependence that blocked auto-labelling is **not merely reduced, it is
gone to within 3%**. No recalibration constant is needed, which is the outcome
that could not be reached by moving the §14.1 thresholds.

### Two things that must be said with it

**The threshold is fitted, and fitted parameters need held-out confirmation.**
0.45 was chosen by looking at these 498 frames. That is the same move A28 was
corrected for, and it is acceptable here only because it is declared: **conf 0.45
is fitted on BMD-45 elevated imagery and must be re-confirmed on S06 deployment
footage before it is trusted at the site.** If the site's geometry or camera
differs enough, the operating point moves with it.

**An unbiased ratio is not a small per-frame error.** MAE at the optimum is still
**1.07 vehicles per frame**. Against a sparse-third mean of 3.8 vehicles that is
roughly 28% relative error on individual frames, and a congestion label is
assigned per frame, not in aggregate. The errors cancel in the ratio; they do not
cancel in a label. Density-stratified reporting (A10) is what keeps this visible.

### Consequence

**ADR-002's auto-labelling is unblocked for elevated footage**, conditional on the
operating point being pinned at conf 0.45, recorded in the corpus spec rather
than left to a library default, and re-confirmed on S06 footage.

The prohibition recorded in S13 is lifted on evidence, not on the passage of
time — and it was correct to hold it until the excess had a cause.

---

## A30 (proposed) — §14.1's congestion thresholds are camera-dependent and must be calibrated per corpus

**Raised** 2026-08-17 · **Affects** PRD §14.1, §8.6, ADR-002, ADR-016 · **Status** PROPOSED

Found by measuring Bellevue footage before committing the project to it, rather
than after.

### The measurement

§14.1 fixes absolute counts: `LOW < 5`, `MEDIUM 5–15`, `HIGH > 15`. Applied to
Bellevue with the calibrated detector (conf 0.45), sampled at the A15 5 s step:

| clip | duration | samples | max count | LOW | MEDIUM | **HIGH** |
|---|---|---|---|---|---|---|
| 116th/NE12th, 17:08 evening peak | 427 s | 81 | 11 | 34.6% | 65.4% | **0.0%** |
| Bellevue/NE8th, 08:08 morning peak | 3,600 s | 720 | 11 | 87.6% | 12.4% | **0.0%** |

**Two cameras, both rush hours, 68 minutes: the count never exceeds 11 and HIGH
never occurs.** A corpus built this way would contain zero examples of the class
the model most needs to predict.

### The deeper problem, which is not about Bellevue

An absolute count threshold is **a property of the camera, not of the traffic**.
A wider field of view sees more vehicles at identical congestion; a camera aimed
further down the approach sees more again. §14.1's numbers encode one particular
framing that was never specified, so they were never portable — Bellevue merely
made that visible by being different enough to fail loudly.

This would have surfaced eventually as an unexplained distribution shift when the
deployment camera was mounted at a slightly different angle from the pilot.

### Proposed amendment

Thresholds become **per-camera percentiles of that camera's own count
distribution**, pre-registered before any labelling:

> LOW below the 50th percentile · MEDIUM 50th–85th · HIGH above the 85th,
> computed per camera over at least one full daily cycle.

* The label becomes "congested **for this junction**", which is what a signal
  controller actually acts on.
* It transfers across countries and cameras without re-deriving anything by hand.
* §14.1's absolute numbers are retained as the **expected instance** of this rule
  for an Indian junction — if the deployment camera's percentiles land near
  5 and 15, the PRD was right and nothing changes.
* The percentile cut points are fixed **before** seeing any corpus, for the same
  reason A28's statistic was.

**Cost of not doing it:** a Bellevue-trained model that has never seen HIGH, and
an Indian model whose labels silently depend on where the camera was pointed.

### What this does NOT license

Tuning percentiles per corpus until the classes balance. The cut points are one
pre-registered rule applied everywhere; a corpus that comes out imbalanced is
reported imbalanced, with inverse-frequency weighting (PRD §8.4) and
density-stratified metrics (A10) doing the work they already exist for.

---

## A30 — measurement WITHDRAWN; the detector does not work on Bellevue (2026-08-17)

A30 was raised yesterday on the finding that Bellevue never reaches HIGH under
§14.1's thresholds. **That measurement is withdrawn.** It was computed from
detector counts, and the detector does not recognise Bellevue's cameras.

### What rendering one frame showed

Four automated checks had passed. One glance did not:

| | |
|---|---|
| 116th/NE12th | ~30 vehicles visible, **3 detected**. A bus labelled `car 0.54`, a sedan labelled `motorcycle 0.52` |
| Bellevue/NE8th | ~10 vehicles visible, **3 detected**, all distant. One labelled **`auto_rickshaw 0.57`** — in Washington State |

Bellevue's cameras are **near-overhead fisheye**. That is a *third* viewpoint
class, distinct both from IDD's dashcam and from BMD-45's oblique elevated CCTV.
The detector has seen neither near-overhead framing nor barrel distortion, and it
fails on both.

### Everything downstream of those counts is void

* **"HIGH never occurs, max count 11"** — measuring a detector that finds one
  vehicle in ten. Withdrawn.
* **"traffic present: median 6 vehicles/frame"** — same.
* **"viewpoint 0.46× the BMD-45 reference"** — worse than wrong, it was
  **self-confirming**: it measured the size of *detections*, so a detector firing
  only on small distant objects always produces a "correct" median. It graded the
  detector's failures and called them a camera property.

**The claim that §14.1's thresholds are camera-dependent still stands on its own
reasoning** — a wider field of view sees more vehicles at identical congestion,
which is true regardless of Bellevue. But it now has **no measurement behind it**,
and A30 is demoted from a finding to an argument until one exists.

### The check that no statistic replaces

Two automated substitutes were tried and both were circular:

1. **Mean detection confidence** — the mean of boxes above 0.45 is always above
   0.45. Passes by construction.
2. **Detections at conf 0.10 ÷ detections at 0.45.** Genuinely discriminating
   (BMD-45 1.36, Bellevue 2.56 and 4.17) but it **confounds domain shift with
   density**: a good dense Indian clip scores 2.80, worse than Bellevue. Shipping
   it as a gate would have rejected exactly the footage we want.

So `check_recording.py` now **renders one annotated frame and tells the operator
to look at it**, keeping the ratio as advisory. Automated domain-shift detection
is a research problem; looking at one frame is five seconds and it is what caught
this.

### Consequence for ADR-016

**Bellevue is not usable as a corpus** without detector work we cannot afford —
it ships no annotations, so adapting to near-overhead fisheye would mean
annotating from zero, which is the cost the whole bootstrap strategy exists to
avoid.

ADR-016's *structure* survives: two phases, pipeline first, claim second. Its
*source* does not.

**And the failure is informative.** "Elevated fixed camera" is not one viewpoint —
it is at least three: dashcam, **oblique elevated** (BMD-45, a footbridge, a first-floor
window), and near-overhead fisheye (much municipal CCTV). Our detector handles
the middle one, which is precisely what a phone on a footbridge produces.

**That makes self-recorded footage a better match than Bellevue ever was**, not a
worse one — and it is the strongest argument yet for S06.

---

## P15 — the signal controller was never controlling the signal (2026-08-17)

**Status:** OPEN · **Severity:** every SUMO result to date is suspect

Found while diagnosing why the two PPO action spaces produced *byte-identical*
evaluation numbers.

### The symptom that gave it away

| arm | phase switches | completed trips | mean wait |
|---|---|---|---|
| `phase_duration` | **0** | 706 | **10.013 s** |
| `keep_or_switch` | **56** | 706 | **10.013 s** |

One controller never switched the light. The other switched it 56 times. Both
produced the same 706 trips and the same mean wait to three decimals. That is
only possible if the controller has no effect on the simulation.

### The cause

`traci.trafficlight.setPhase()` sets the current phase **but does not hold it**.
SUMO's built-in program keeps advancing on its own schedule. Measured directly —
we set phase 0 and read it back every ten seconds:

    t=10s  phase 0     t=40s  phase 0     t=70s  phase 0
    t=20s  phase 3     t=50s  phase 3     t=80s  phase 2
    t=30s  phase 5     t=60s  phase 4     t=90s  phase 3

The light was running its default fixed program throughout. **Every controller
this project has benchmarked was decorative**; the differences between them came
from where the interphase blocked the loop, not from signal policy.

### The fix, and that it works

`setPhaseDuration(tls, 100_000)` after every `setPhase` pins the phase until the
controller changes it. With it, the phase holds at 0 for the full sixty seconds,
and controllers separate as they should — over 600 s at seed 42:

| | mean wait | switches |
|---|---|---|
| fixed | 21.55 s | 16 |
| longest-queue | **16.53 s** | 18 |

Applied to both `runner.run_episode` and `TrafficSignalEnv`, which had the same
call and therefore the same defect.

### What is now void

Every committed SUMO result predates the fix and must be regenerated:

* `baselines.csv`, `benchmark_runs.csv`, `benchmark_stats.csv` — including the
  headline **"fixed 31.09 s vs Webster 29.32 s, p = 0.225"**. That comparison was
  between two labels attached to the same underlying program.
* `webster_sweep.csv` — the s=750 selection.
* `action_space_screen.csv` — void twice over, since both arms were also the
  same program.

**The `p = 0.225` result is not merely unconfirmed, it is explained.** Two
methods that were secretly identical *should* fail to differ significantly. The
statistic was correct; the thing it was computed on was not.

### Why it survived

The runner's tests assert bounds, clamping and interphase behaviour — all of
which were genuinely correct. Nothing asserted that **the controller's decision
reaches the simulation**, because that seemed too basic to check. The regression
test to add is exactly the diagnostic above: a controller that never switches and
one that switches constantly must produce *different* numbers.

### Also fixed

A `NamedTemporaryFile` created per `reset()` and never deleted. **9,931 leaked
files** had accumulated and eventually broke SUMO startup outright, which is what
killed the screening run.

---

## A31 (proposed) — viewpoint robustness is a detector requirement, not a dataset criterion (2026-08-17)

Raised by the project owner, and they are right. I had been treating the
detector's viewpoint limitation as a **filter on data** — "Bellevue is
near-overhead, so Bellevue is the wrong dataset". The correct reading is that
**the deployment camera is an elevated fixed camera whose exact geometry we do
not control**, so a detector that handles only one pitch is carrying a defect,
and selecting datasets around that defect hides it instead of fixing it.

### I also misattributed the cause

I said Bellevue failed because of **fisheye distortion**. Measured on BMD-45 by
applying increasing barrel distortion, using the out-of-domain ratio
(detections at conf 0.10 ÷ detections at 0.45) that needs no labels:

| barrel k | ratio | detections/frame |
|---|---|---|
| 0.0 | 1.37 | 9.5 |
| −0.4 | 1.41 | 8.8 |
| −0.8 | 1.38 | **7.9** |

**Distortion is not the problem.** The ratio never moves and detections fall
17% across the entire range.

Repeating it with a perspective warp that simulates raising the camera toward
vertical:

| pitch | ratio | detections/frame |
|---|---|---|
| 0.00 | 1.37 | 9.5 |
| 0.50 | 1.40 | 7.7 |
| 0.75 | 1.44 | 6.3 |
| **1.00** | **1.72** | **4.2** |

**Viewing angle costs 56% of detections against distortion's 17%.** A vehicle
from directly above shows roof only — no side, no front — and that is a
different object to a detector that has only seen it obliquely.

### Why it is fragile, and it is not inherent

The S14 run used Ultralytics' defaults:

    perspective  0.0
    degrees      0.0
    shear        0.0

**Every geometric augmentation that would teach viewpoint invariance was off.**
The detector is not fragile because oblique data is all that exists — it is
fragile because we never asked it to generalise across pitch.

### Proposed amendment

Retrain the joint detector with geometric augmentation enabled:

    perspective  0.0006      # Ultralytics range is 0 to 0.001
    degrees      8.0
    shear        4.0

**Pre-registered success criterion, fixed before the run:** detections per frame
at pitch 1.0 must reach **at least 70% of** the pitch-0.0 figure, against today's
44% (4.2 of 9.5) — while elevated mAP50 on BMD-45 stays within 2 points of
0.8915. Robustness bought by making the model worse everywhere is not robustness.

The pitch sweep is the measurement, it needs no new labels, and it runs in
minutes on the existing eval split.

### Consequence

If it works, Bellevue becomes usable after all, and more importantly **the
deployment stops depending on mounting the camera at the one angle the detector
happens to like.** That is the real argument: we will not always control where a
municipal camera points.

---

## S34 rev 2 — the baselines re-run with a working controller, and the ordering inverts (2026-08-17)

First measurement taken after the P15 fix. 30 paired seeds, saturated regime,
1200 s episodes — same harness, same seeds, same statistics. The only change is
that the traffic light now obeys the controller.

| method | mean wait | 95% CI | | before P15 |
|---|---|---|---|---|
| **Webster** | **14.05 s** | [13.41, 14.71] | | 29.32 s |
| fixed | 26.18 s | [24.87, 27.53] | | 31.09 s |
| longest-queue | 27.94 s | [26.35, 29.57] | | 18.51 s |

| comparison | difference | p | Cohen's d | |
|---|---|---|---|---|
| fixed vs Webster | +12.13 s | **< 0.00001** | **2.94** | significant |
| longest-queue vs Webster | +13.89 s | **< 0.00001** | **2.92** | significant |
| fixed vs longest-queue | −1.76 s | 0.097 | −0.31 | not significant |

### Every conclusion from the old table is reversed

* **Webster was reported as no better than fixed-time (p = 0.225).** It is better
  by **86%** with an effect size near 3. It was never a weak method; it was a
  method that could not reach the actuator.
* **Longest-queue was reported best at 18.51 s.** It is now the *worst* arm and
  statistically indistinguishable from fixed-time.
* The one honest thing about the old table — that two of the arms did not
  differ — was true for the wrong reason.

Webster's result is what theory predicts once it can act: a principled cycle-time
allocation should beat both a fixed cycle and a greedy queue rule.

### What this means for the project

**The bar for PPO just moved a long way up, and that is correct.** Beating a
broken 29.32 s would have been meaningless; beating a properly-actuated Webster
at 14.05 s with a CI of [13.41, 14.71] is a real claim, and it may well not be
achievable. If PPO cannot beat Webster, that is the result and it gets reported
(PRD §2.5.5, BR-19).

It also makes the RL contribution honest rather than decorative. A paper whose
learned controller beats a crippled baseline is worse than no paper.

### Superseded

`experiments/results/VOID-PRE-P15.md` still lists the pre-fix files. `baselines.csv`
and `webster_sweep.csv` remain to be regenerated; `benchmark_runs.csv` and
`benchmark_stats.csv` are now post-fix and current.

---

## A31 — NOT MET. Reported as measured (2026-08-18)

Both pre-registered criteria were checked against D2 (`perspective=0.0006`,
`degrees=8.0`, `shear=4.0`, 60 epochs, seed 42).

| criterion | target | D1 | **D2** | |
|---|---|---|---|---|
| pitch retention at 1.0 | ≥ 70% | 46% | **51%** | **FAILS** |
| BMD-45 mAP50 | ≥ 0.8715 | 0.8915 | **0.8941** | MEETS |

**The in-domain guard held** — mAP50 went *up* by 0.0026, and `auto_rickshaw`
improved 0.914 → 0.919. The risk that robustness would be bought by making the
model worse everywhere did not materialise.

**The robustness target was missed by a wide margin.** A 5-point gain against a
26-point shortfall. `perspective=0.0006` sits at the low end of Ultralytics'
0–0.001 range, and the evidence is that it barely perturbs the geometry.

Per A31's own pre-registration, the response is to **report the number and keep
D1 as the working detector**, not to relax the threshold — which would be
choosing the criterion to fit the result (PRD §2.5.5, BR-19).

### The proxy was flattering the problem

The pitch sweep is a synthetic perspective warp of oblique imagery. Bellevue is
genuine pole-mounted near-overhead municipal CCTV — the actual condition the
requirement is about. Four clips, 12 frames each:

| model | detections/frame | out-of-domain ratio |
|---|---|---|
| D1 | 0.73 | 4.62 |
| **D2** | **1.55** | **3.15** |
| *(BMD-45 oblique reference)* | *9.88* | *1.37* |

**D2 more than doubles D1 on real near-overhead footage** — a bigger relative
gain than the synthetic sweep showed. The augmentation did more than the proxy
credited it with.

But it still finds **1.55 vehicles per frame where the oblique reference is
9.88**, and the out-of-domain ratio stays at 3.15 against 1.37. Bellevue remains
unusable as a corpus. The direction is right and the magnitude is nowhere near
enough.

### What this changes

1. **A31 is not met and D1 remains the working detector.** D2 is retained as an
   ablation arm; its in-domain numbers are marginally better, so the choice
   between them is not obvious and belongs in the table rather than in a
   decision made here.
2. **The synthetic pitch sweep is retired as the acceptance measure.** It
   under-reported the real effect by half. Bellevue replaces it — a proxy that
   disagrees with the thing it proxies is worse than no proxy.
3. **A34 is proposed, not run:** retrain with augmentation an order of magnitude
   stronger (`perspective=0.001`, `degrees=20`, `shear=10`), with the criterion
   restated **on Bellevue** — detections/frame ≥ 50% of the oblique reference —
   and the same in-domain floor. That is tuning the intervention while holding
   the criterion fixed, which is legitimate; moving the threshold would not be.
4. **A35 is worth raising against A34:** if geometric augmentation of oblique
   data cannot reach near-overhead performance, the honest conclusion may be
   that **near-overhead is a genuinely different domain requiring labelled data
   from it**, and no amount of warping oblique imagery substitutes. Two failed
   attempts would be evidence for that rather than for trying a third.

> **Renumbered 2026-08-18 (was A32/A33).** These two were written as forward
> proposals before A32 was allocated, and A32 then went to the human-verified
> reporting rule below — which is now cited from five source files. Two live
> meanings for one amendment ID is the kind of defect that surfaces in a viva,
> so the doc-only pair moved. **Amendment IDs are allocated once and never
> reused**, exactly as CLAUDE.md already requires of `BR-*`/`FR-*`/`NFR-*`.

---

## ADR-012 rev 3 — Webster sweep re-run post-P15; s=750 re-selected on valid evidence (2026-08-18)

The original sweep ran before P15, so no configuration was controlling anything
and every row described the same default SUMO cycle under a different label. It
mattered more than the other voided results, because post-P15 Webster is the
strongest baseline and its parameterisation sets the bar PPO must clear.

`experiments/results/webster_sweep.csv`, 5 seeds, saturated, 1200 s:

| s (pcu/h/m) | mean wait | clamp rate | arrived | |
|---|---|---|---|---|
| 525 | 20.60 s | 3.5% | 93.9% | |
| 660 | 16.11 s | 12.3% | 94.5% | |
| **750** | **14.22 s** | **37.8%** | **94.8%** | **SELECTED** |
| 900 | 14.41 s | 80.5% | 95.0% | rejected — clamp |
| 1050 | **14.03 s** | 99.2% | 94.9% | rejected — clamp |
| 1283 | **14.03 s** | 100.0% | 94.9% | rejected — clamp |

**The disqualification rule earned its place again.** s=1050 and s=1283 post the
*lowest* waits in the sweep and clamp on essentially every decision — the cycle
formula decides nothing and they are fixed cycles wearing Webster's name.
Reporting either as "Webster's best" would put a fixed-time controller in the
results table under the adaptive baseline's label.

### The selection is unchanged, and that is worth stating precisely

The pre-P15 sweep also chose s=750, and `benchmark.py` already used it. So the
30-seed headline of **14.05 s** was computed at the right saturation flow, and
the sweep's 14.22 s at 5 seeds agrees with it.

**The old sweep's numbers were meaningless and its conclusion happened to
survive.** That is luck, not vindication, and it is recorded as luck — had it
selected differently, the entire benchmark would have needed re-running rather
than merely re-justifying.

### The headline also passes its own survivorship check

ADR-012's second disqualification applies to the benchmark itself, not just the
sweep. Checked directly:

| method | mean wait | arrived | throughput |
|---|---|---|---|
| fixed | 26.18 s | 92.6% | 930 |
| longest-queue | 27.94 s | 92.1% | 925 |
| **Webster** | **14.05 s** | **92.0%** | **922** |

All three sit well above the 85% floor with throughput within 1% of each other,
so Webster's 86% improvement is genuine and not achieved by dropping the
vehicles that waited longest.

---

## P16 — the gate has never been shown to do anything (2026-08-18)

**Status:** OPEN · **Severity:** the project's headline novelty currently has no evidence

Found by hunting for the next P15 — an assumption relied on everywhere and
asserted nowhere.

CLAUDE.md states the position plainly: *"The gate value is a research artifact,
not an internal detail — it is logged, tracked on the dashboard (FR-UI05), and
analyzed in the paper."* [RELATED-WORK](RELATED-WORK.md) narrows the defensible
novelty to the **gate-as-artifact**, because the fusion mechanisms themselves are
all published.

So the gate is not a component. It is the contribution.

### It sits at its initialisation value

`experiments/results/overfit_check.csv`, config G, the only arm with
`use_gate: True`:

    gate_mean  0.4999      accuracy 1.0

Sigmoid of approximately zero is 0.5. **The model memorised ten sequences
perfectly and the gate never moved.**

Probed directly at initialisation (588 gate values, seed 42):

| | |
|---|---|
| mean | 0.49617 |
| std | **0.00227** |
| range (max − min) | **0.0098** |
| gradient, `fusion.gate.weight` | **5.3 × 10⁻⁶** |
| gradient, `fusion.gate.bias` | 2.6 × 10⁻⁶ |
| mean shift on a different input batch | **0.00056** |

The gate spans **under 1% of [0, 1]** and barely responds to the input. The
gradient reaching it is roughly six orders of magnitude smaller than the values
it would need to move, so at `lr = 1e-4` the per-step update is ~5 × 10⁻¹⁰.

`F_fused = g·Z_A + (1−g)·Z_B` with g ≈ 0.5 everywhere is **an unweighted
average**. Gated bidirectional cross-attention is, on this evidence,
indistinguishable from taking the mean of the two branches.

### What is and is not established

**Not established:** that the gate is broken. Gradient is non-zero, the
mechanism is wired, and a 10-sequence memorisation task gives it no reason to
move — the model can win without it.

**Established, and this is the problem:** there is **no evidence whatsoever**
that the gate does anything, and the paper's central claim assumes it does. That
is precisely the gap P15 occupied — relied on everywhere, asserted nowhere.

This is also the failure PRD §2.5.1 predicts by name ("Gate collapses — all
predictions identical class") with a Week 12–13 mitigation attached. It is
Week 2, and the condition is already visible.

### The experiment that settles it, pre-registered

A gate can only earn its place if the two branches carry **different**
information. On random features they do not, and on a memorisation task nothing
forces specialisation.

> Train config G against config E (bidirectional, no gate) on the real corpus.
> The gate is doing work if **(a)** its per-lane standard deviation across the
> test split exceeds **0.05**, and **(b)** G beats E on macro-F1 by more than the
> seed-to-seed spread of E.
>
> If the gate stays inside ±0.02 of 0.5, the honest conclusion is that
> **gating contributes nothing on this task**, the claim is withdrawn, and E
> becomes the reported architecture.

Both thresholds are fixed now, before the corpus exists, for the same reason
A28's statistic and A31's criterion were.

### Why this was missed

`test_model.py` asserts the gate is *present in the output* and *shaped
correctly* — both true, both insufficient. Nothing asserted it **varies**. A
constant 0.5 passes every existing test while making the contribution vacuous.

The new test does not assert the gate is healthy, because it currently is not.
It asserts the gate's variation is **measured and recorded**, so the number
cannot silently stay at 0.5 through to the paper.

---

## A32 (proposed) — the headline comparison must be on human-verified labels (2026-08-18)

**Raised** 2026-08-18 · **Affects** PRD §14.3, §14.5, §8.6, ADR-002 · **Status** PROPOSED

From [CRITICAL-REVIEW](CRITICAL-REVIEW.md). This is a **reporting rule**, and it
costs nothing to adopt — but without it the project can run a correct experiment
and draw the wrong conclusion from it.

### The problem

Congestion labels are derived from detector counts through §14.1's thresholds, so
the label is a deterministic function of the count. §14.3's baselines include
LSTM, GRU and CongestFormer **on count sequences**.

Those baselines therefore observe **the exact variable the label is computed
from**. MFSTNet observes pixels and must recover the count before it can
extrapolate. On auto-labelled data the count models should win by construction,
and MFSTNet can at best match them minus detector error.

"Camera-only congestion prediction" is not merely disadvantaged there — it is
**set up to lose**, and the loss would say nothing about vision.

### The amendment

> **§14.5.** The headline MFSTNet-versus-baselines comparison SHALL be reported
> on the **human-verified test split** (A9). Auto-labelled results MAY be
> reported alongside and SHALL be labelled as auto-labelled wherever they appear.

A human judging congestion is not applying `count > 15`. They see queue length,
whether traffic is stopped or moving, spatial bunching, blocked turns — properties
that are present in pixels and **absent from a count**. That is where a vision
model can win, and it is the only place it can.

### Why a rule rather than a note

A11 already observes that count-consuming baselines share error structure with
auto-derived labels, and treats it as a bias against MFSTNet. It is stronger than
a bias; it is a structural guarantee.

Left as an observation, the predictable thing happens: the auto-labelled table is
the biggest and cleanest one available, the count baselines top it, and the
project concludes its own approach failed — when what failed was the label
definition. A reporting rule is what stops that, and it has to be written before
the numbers exist.

### Related

Also raised in the same review, and recorded so they are not lost:

* **Frozen backbones cap the vision advantage.** The properties that separate
  congestion from vehicle count are exactly the task-specific ones a frozen
  generic encoder is least likely to expose. ADR-007's late LoRA experiment is
  the only mechanism in the plan that lets the encoder learn anything
  task-specific, and it should be **promoted from optional to planned**.
* **Run P13 and the Naive baseline early.** If last-value or XGBoost-on-counts
  already scores well on human-verified labels, that number reframes the
  contribution — and Week 3 is a far better time to learn it than Week 14.

---

## ADR-015 — action-space screen complete; keep-or-switch wins decisively (2026-08-18)

The measurement ADR-015 committed to, and the first one that could mean anything:
the pre-P15 screen produced byte-identical numbers for both arms because neither
was controlling the light.

`experiments/results/action_space_screen.csv`, 5 seeds each, 50k timesteps,
900 s episodes, evaluated on 3 held-out episodes per seed:

| action space | mean wait | sd | best seed |
|---|---|---|---|
| `phase_duration` (PRD §13.1) | 25.95 s | 9.47 | 14.93 s |
| **`keep_or_switch`** | **12.78 s** | **2.03** | **10.60 s** |

**Keep-or-switch is 50.8% better and less than a quarter as variable.**

The spread matters as much as the mean. `phase_duration` ranges from 14.93 s to
36.62 s across seeds — an agent that picks a phase *and* a duration at every
decision has a much larger space to get wrong, and on some seeds it never finds
a good region. Keep-or-switch, deciding one bit every 5 s, lands between 10.60 s
and 15.17 s on all five.

### This also vindicates P11's reasoning

P11 observed that state index 10 `phase_remaining` is structurally zero under
(phase, duration), because the agent only acts at phase end. The fix was not
cosmetic: restoring that dimension came with a formulation that is both better
and steadier.

### What this does NOT establish

**It is not a comparison with Webster.** Keep-or-switch's 12.78 s and Webster's
14.05 s were measured on **different episode lengths** — 900 s here against
1200 s in the benchmark — so putting them side by side would be comparing two
different experiments. The honest comparison requires PPO in the 30-seed
benchmark at 1200 s, which is the next RL step.

**It is a screen, not a result.** Five seeds, 50k timesteps against the
specified 500k, no significance test. It exists to rank two options so the
choice is informed, and `benchmark_stats.csv` remains the reported comparison.

### Consequence

**DECISION-BRIEF item 1 now has evidence rather than a default.** The stated
default was to adopt keep-or-switch on P11's reasoning alone; it is now adopted
on a measured 50.8% margin with lower variance. The guide is being asked to
confirm a number, not to arbitrate an argument.

§13.1's action space stays implemented behind the flag, so nothing graded is
lost and the comparison is reproducible.

---

## P17 — a corpus cannot span cameras, because lane polygons are per-camera (2026-08-18)

**Status:** OPEN · Found by building the first real corpus and reading its output

399 sequences from 13 clips. The label distribution is unusable:

| split | LOW | MEDIUM | HIGH |
|---|---|---|---|
| train | 193 | 84 | **0** |
| val | 43 | 13 | 2 |
| test | **8** | **56** | **0** |

Zero HIGH in train and test, and the test split is nearly the inverse of train.
The first reading was A30's — that §14.1's absolute thresholds do not fit this
footage. **That reading was wrong, and the real cause is worse.**

### The lane assignment is meaningless across cameras

`corpus.counting` returns an unassigned rate alongside the counts, and its
docstring says that is "not optional". It earned that:

| clip | assigned to a lane |
|---|---|
| 4K Road traffic | **13.5%** |
| Highway sounds | 38.8% |
| Pov_Thursday | 39.1% |
| Relaxing highway | 51.3% |
| M6 Motorway | 63.6% |
| Dhaka Science Lab | 65.4% |
| Incredible traffic jam | 90.1% |
| Incredible traffic Sound | **94.0%** |

One `motorway` polygon set was applied to thirteen different cameras. On some it
happens to line up; on most it does not. **A polygon is defined in the image
plane, so it is a property of the camera, not of the road.** Counts derived
through a mismatched polygon are not low counts — they are counts of the wrong
region, and every label built on them is arbitrary.

The class imbalance is a *symptom*. Fixing thresholds would have produced a
balanced distribution over meaningless counts, which is worse than an obviously
broken one.

### What this means structurally

**A corpus can only be assembled from clips that share a camera.** ADR-002 says
splits are cut by clip to prevent leakage; it silently assumes those clips come
from one installation. Thirteen YouTube clips of thirteen different roads cannot
form one corpus at any threshold.

This is not a limitation of the approach — it is the deployment reality. The
system watches **one fixed camera** at one junction. Lane polygons are surveyed
once for that camera and never change.

### Consequences

1. **The 13-clip corpus is discarded.** It is retained as the evidence for this
   finding and must not be trained on.
2. **`build_corpus.py` must take per-clip polygons**, and must refuse a clip
   whose unassigned rate exceeds a threshold — a polygon that catches 13% of
   detections is a misconfiguration, not data.
3. **A30's measurement stays withdrawn.** Its Bellevue evidence was void because
   the detector was out of domain; this corpus cannot restore it because the
   polygons were wrong. The threshold question is still open and still
   unmeasured.
4. **This raises the value of S06 sharply.** Multiple recordings from one
   junction, with polygons surveyed once, is the only corpus shape that works —
   and it is exactly what a single recording trip produces.

---

## P18 — requirements.txt was wrong in both directions, and the graded statistics were never checked against anything (2026-08-18)

**Status:** CLOSED · Found by a baseline that silently reported `SKIPPED`

`train_baselines.py` printed `xgboost_counts  SKIPPED - pip install xgboost`
while `import xgboost` succeeded standalone. The `except ImportError` was
catching an import that fired one level down: `XGBClassifier` is xgboost's
scikit-learn wrapper and constructs scikit-learn at call time, so on a machine
without sklearn the failure surfaced as "xgboost is missing".

Switching to the native `xgboost.train` API removed the coupling. But the near
miss is the point — **a baseline can disappear from the results table and print
a plausible reason for it.** §14.3's baselines are what MFSTNet is measured
against; one silently absent is a result that overstates the contribution.

### What the audit found

Walking the AST of every source file and comparing imports against
`requirements.txt` in **both** directions:

| direction | count | consequence |
|---|---|---|
| imported, not pinned | 6 | clean-machine reproduction fails (NFR-08) |
| pinned, imported nowhere | 16 | the file overstates what is needed |

The six unpinned — `yt-dlp`, `imageio-ffmpeg`, `gdown`, `huggingface-hub`,
`nbformat`, `nbclient` — are all lazily imported inside data-acquisition
scripts. Lazy imports are why the gap survived: nothing fails at startup, it
fails on the day someone reproduces the corpus. They now have their own section,
because a machine that trains from an existing corpus genuinely does not need
them and the file should say which is which.

Most of the sixteen unused pins are legitimate: FastAPI, MQTT, ONNX, MLflow and
TensorBoard belong to the Weeks 17–19 prototype (ADR-004 wave 3). They are
annotated as pinned-ahead-of-use so the next audit does not re-flag them.

### The part that actually mattered

`scipy` and `scikit-learn` were pinned with the comments
"paired t-test, bootstrap CI (FR-R07, FR-R08)" and "macro F1, per-class P/R
(FR-M11)" — and **imported nowhere.** Both were hand-rolled:
`mfstnet/metrics.py` and `experiments/statistics.py` are pure standard library.

That choice is defensible and is retained; the arithmetic stays auditable line
by line and runs before the environment exists. What was not defensible is that
**nothing checked it.** Macro F1, quadratic weighted kappa, the paired t-test
and Cohen's d are graded reported numbers. `_t_sf`'s own docstring said
"an approximation nobody verifies is worse than none" — and nobody had verified
it. A continued-fraction expansion that loses precision in the tail is invisible
until a p-value near α=0.05 falls the wrong side.

`tests/test_metrics_reference.py` now cross-checks both modules against
scikit-learn and SciPy: 52 assertions over randomised inputs plus the degenerate
shapes — a class that never appears, perfect agreement, fully inverted
agreement, and the t-distribution tails at df ∈ {1, 2, 5, 29, 100}.

**Result: everything agrees.** Confusion matrix exact; macro/weighted F1,
per-class precision/recall, accuracy and QWK to 1e-9; the paired t-test
statistic to 1e-9 and its p-value to 1e-6; `_t_sf` to 1e-8 across the tails.

No number changes. The hand-rolled implementations were correct. But they were
correct *unverified*, which is the same position P15 and P16 occupied — relied
on everywhere, asserted nowhere — and this one sat directly under the results
section.

### Consequences

1. **`requirements.txt` reconciles with the code** and carries the audit method
   at the top, so NFR-08 can be re-checked rather than re-asserted.
2. **The reference cross-check runs in CI.** It skips when SciPy/scikit-learn
   are absent, so the production path never acquires the dependency.
3. **`xgboost>=2.1` is pinned** (P13), and the baseline uses the native API so
   it runs wherever xgboost imports.
4. **Catching `ImportError` around more than the import itself is a defect.**
   It converts any nested import failure into a plausible-looking skip.

---

## A36 — the LoRA arm is promoted from optional to planned (2026-08-18)

**Raised** 2026-08-18 · **Affects** ADR-007 §3, requirements.txt · **Status** ADOPTED

From [CRITICAL-REVIEW](CRITICAL-REVIEW.md) Risk 2. This does not change the
schedule, the design, or any hyperparameter. It changes what a null result is
allowed to mean.

ADR-005 caches frozen backbone outputs, which only works because the backbones
are frozen. The consequence, which the ADR states but does not weigh: **the
model cannot learn features for this task.** It recombines ImageNet and DINOv2
features and nothing more.

The properties that separate congestion from vehicle count — queue length,
stopped-versus-moving, spatial bunching — are exactly the task-specific
properties a frozen generic encoder is least likely to expose, and they are the
properties the camera-only claim rests on.

**This compounds A32.** A32 establishes that the comparison is only winnable on
human-verified labels. Risk 2 adds that even there, the advantage may not
materialise if it lives in properties the frozen features do not encode. Two
independent reasons for the same null result, and neither would be visible in
the number itself.

LoRA is the only mechanism in the plan that lets the encoder learn anything
task-specific. Leaving it optional means a null result on the frozen arms is
uninterpretable: "camera-only prediction does not work" and "frozen ImageNet
features do not encode queue dynamics" produce the same table.

### Consequences

1. **`peft` moves out of requirements.txt's optional block.** It is a planned
   dependency, pinned like any other.
2. **A frozen-only null result is not reportable on its own.** It needs the LoRA
   arm beside it to say which of the two explanations holds.
3. **Cutting it for time stays legitimate** — Week 15 sits behind the main
   results, and the cache invalidation makes it the most expensive arm in the
   study. But it must then be **recorded as a cut**, because the frozen-feature
   ceiling becomes an untested confound on the headline claim rather than a
   question the project answered.

---

## Result — the controller ranking is not stable across demand regimes (2026-08-18)

**Status:** MEASURED, **PARTIALLY VOIDED BY P19 — read that entry first** ·
3 controllers × 3 regimes × 30 paired seeds, all post-P15 ·
`benchmark_runs.csv`, `benchmark_stats.csv`

> **P19 correction.** The Webster arm at `light` clamps on 100% of decisions and
> is disqualified by ADR-012 — every comparison against it below is void. Every
> `oversaturated` comparison is void for survivorship (all three controllers
> completed under 85% of trips). **The `saturated` rows stand unchanged**, as
> does `fixed vs longest_queue` at `light`. The headline finding — that the
> ranking is regime-dependent — survives, but its light-regime half is now
> "Webster is undefined here" rather than "longest_queue beats Webster".

The post-P15 benchmark ran at `saturated` only, because that is the regime the
voided `baselines.csv` screen had picked with one seed. Extending it to the other
two regimes was expected to be bookkeeping. It is not.

Mean wait per vehicle, seconds (lower is better, `*` = best in row):

| regime | fixed | longest_queue | webster |
|---|---|---|---|
| light | 11.92 | **6.28*** | 6.59 |
| saturated | 26.18 | 27.94 | **14.05*** |
| oversaturated | 71.89 | 70.46 | **66.61*** |

Paired comparisons, 30 seeds each:

| regime | comparison | Δ (s) | p | Cohen's d | significant |
|---|---|---|---|---|---|
| light | fixed vs longest_queue | 5.64 | <0.00001 | 18.92 | yes |
| light | longest_queue vs webster | −0.31 | <0.00001 | −1.08 | yes |
| saturated | fixed vs longest_queue | −1.76 | 0.09682 | −0.31 | **no** |
| saturated | fixed vs webster | 12.13 | <0.00001 | 2.94 | yes |
| saturated | longest_queue vs webster | 13.89 | <0.00001 | 2.92 | yes |
| oversaturated | fixed vs longest_queue | 1.43 | 0.62392 | 0.09 | **no** |
| oversaturated | fixed vs webster | 5.28 | 0.09993 | 0.31 | **no** |
| oversaturated | longest_queue vs webster | 3.85 | 0.01203 | 0.49 | yes |

### Three things that were not visible from one regime

**1. The winner changes.** `longest_queue` is the best controller under light
demand and beats Webster there significantly. Under saturation it is the
**worst** of the three — worse than a fixed 30 s cycle, though not significantly
so. A queue-greedy rule works while there is slack to exploit and stops working
when there is none.

**2. Webster's advantage is a saturated-regime phenomenon.** It is 86% at
saturation with d = 2.94. At oversaturation it cannot significantly beat a fixed
cycle at all (p = 0.09993, d = 0.31). When every approach is over capacity there
is little left for signal timing to allocate, and all three controllers converge
towards the same 66–72 s.

**3. Effect sizes collapse in the direction the paper cares about.** d falls
from 2.94 to 0.31 between saturated and oversaturated. A method separation
demonstrated at one demand level says little about the next one up.

### What this changes

1. **"Webster wins by 86%" is a saturated-regime claim** and must be reported
   with the regime attached. It is not wrong; it was stated without the
   qualifier it needs, and the qualifier is the interesting part.
2. **ADR-012's selection of Webster `s=750` was made at `saturated`.** The
   selection rule is unaffected — it was applied correctly to the regime it was
   applied to — but the parameter is regime-specific and is not established for
   light or oversaturated demand.
3. **The bar PPO must clear is regime-dependent, and PPO trains at `saturated`
   only** (`ppo_config.yaml`, `train_ppo.py --regime`). Beating Webster at
   saturation is the hardest of the three (86% margin to erase); beating it at
   oversaturation is nearly free, because nothing separates the controllers
   there. **A PPO result must state its training and evaluation regime, and
   generalisation across regimes is an open question, not an assumption.** The
   checkpoint filename already encodes the regime, so the provenance exists.
4. **`baselines.csv` is retired** as superseded rather than regenerated — see
   `experiments/results/VOID-PRE-P15.md`. This closes the last artifact P15
   voided.

### Honest limits of this measurement

The three regimes come from `build_sumo_demand.py` and are **synthetic demand on
a synthetic 4-way intersection**. Nothing here is evidence about a real junction,
and the absolute numbers are not comparable to field measurements. What the
experiment supports is the *relative* claim: on identical demand streams, which
controller wins depends on the regime. That is the claim being made.

---

## P19 — the three-regime result was reported before its own disqualification rules were applied (2026-08-18)

**Status:** CLOSED · Found by asking whether `WEBSTER_SATURATION = 750.0` was
defensible outside the regime it was selected in

The three-regime result above was committed with a hardcoded Webster saturation
flow. ADR-012 selected `s=750` **at saturated demand**, and `benchmark.py` used
it at all three. So the obvious question was whether a different `s` wins
elsewhere. The answer is worse than "yes".

### At light demand, Webster is not Webster

The sweep at `light`, 5 seeds per configuration:

| s (pcu/h/m) | mean wait | clamp rate | arrived |
|---|---|---|---|
| 525 | 6.55 | **100%** | 96.0% |
| 660 | 6.55 | **100%** | 96.0% |
| 750 | 6.55 | **100%** | 96.0% |
| 900 | 6.55 | **100%** | 96.0% |
| 1050 | 6.55 | **100%** | 96.0% |
| 1283 | 6.50 | **100%** | 95.7% |

Six configurations, one number. That is the P15 signature — methods that are
secretly the same program cannot differ — and the mechanism is exact:
`optimum_cycle` returns roughly `23/(1-y)`, which is below `min_cycle_s = 32`
for any `y < 0.28`. At light demand it clamps to the floor every decision, and
`s` stops mattering because it only enters through `y = q/s`.

**`ADR-012` already covers this**: a configuration clamping on more than half its
decisions "is a fixed cycle wearing Webster's name". Nothing qualifies at light,
so no Webster claim may be made there.

**This voids a claim made in the entry above.** "longest_queue beats Webster at
light demand (6.28 vs 6.59)" is not a comparison with Webster. It is a
comparison with a 32 s minimum cycle. The correct statement is that
`longest_queue` beats a fixed 30 s cycle at light demand by 47%, which is still
true and still significant, and that **Webster is undefined in this regime**.

### At oversaturation, no controller's mean wait is citable

The sweep rejected all six configurations for completion, not clamping — 78% to
83% of trips finished against the 85% floor. Checking the benchmark's own rows
against the same rule:

| regime | method | mean wait | arrived | verdict |
|---|---|---|---|---|
| oversaturated | fixed | 71.89 | 79.7% | survivorship |
| oversaturated | longest_queue | 70.46 | 82.3% | survivorship |
| oversaturated | webster | 66.61 | 82.6% | survivorship |

**All three**, not just Webster. When a fifth of vehicles never complete, a mean
wait is an average over a subset selected by the very thing being measured. The
ordering happens to be directionally safe here — the controller with the lower
wait also completed *more* trips, so the bias runs against it rather than for it
— but the magnitudes are not reportable and the metric is the wrong one.
Oversaturated demand needs throughput or completion rate as the headline, not
mean wait.

### The structural defect

ADR-012's two disqualifications were defined, correct, and **applied only in
`webster_sweep.py`.** The script that produces the reported comparison never
ran them. The rule existed; the place it mattered never called it.

That is the same shape as P15 (the controller that was never controlling) and
P16 (the gate asserted nowhere): a thing relied on everywhere and checked in one
place that is not the place it is relied on.

### Consequences

1. **`disqualification()` moves into `simulation/webster.py`** beside
   `select_best`, which now calls it, and `benchmark.py` applies it per method
   over seeds. Ten tests pin it, including both threshold boundaries.
2. **`benchmark_stats.csv` gains `a_disqualified`, `b_disqualified`, `citable`.**
   A reader of the committed file sees the verdict without re-deriving it, and a
   paper table generated from the CSV can filter on it.
3. **4 of 9 comparisons are citable**: all three at `saturated`, plus
   `fixed vs longest_queue` at `light`. Everything else is printed and marked
   uncitable.
4. **`benchmark.py --restat` recomputes statistics from the committed runs CSV**
   without re-simulating. NFR-09/10 requires paper tables to come from committed
   CSVs by a committed script; that only holds if changing the analysis does not
   cost 270 episodes, or the CSV and the analysis drift apart.
5. **The original choice of `saturated` is vindicated, for a reason nobody had
   established.** It is the only regime in which all three controllers produce
   citable measurements. That was luck when it was picked by a single-seed
   screen; it is now a checked property, and it is the regime PPO trains in.

### What was right

The rules that caught this were **pre-registered in ADR-012 and written against
our own preferred result** — they were created because the sweep's naive best
was a 100%-clamped fixed cycle, and adopting them cost us the headline number at
the time. They caught two more failures here, one of them in a result committed
forty minutes earlier. Thresholds fixed before the data are worth what they cost.

---

## P20 — the pilot's learnability gate admitted the failure it was written to catch (2026-08-18)

**Status:** CLOSED · Found by running the S06 pilot twice with different detectors

S06 was measured on 2026-08-18, four days after it stopped being blocked. Two
defects surfaced in the running of it.

### The instrument decided the verdict

The pilot hardcoded COCO `yolov8n`, justified in its own docstring: "this pilot
measures the *traffic*, not our detector, so a general model is the right
instrument". Run both ways on the same 20 minutes of elevated Dhaka footage:

| | COCO `yolov8n` | `s14_yolov8s_joint_best` |
|---|---|---|
| median count | 9 | 13 |
| maximum count | 16 | 23 |
| HIGH share | **0.0%** | 17.2% |
| transition rate | **6.9%** | **31.0%** |
| naive baseline | **93.1%** | **69.0%** |

COCO has no auto-rickshaw class. On South Asian traffic it is not a neutral
instrument — it is blind to a large share of the vehicles, and the count
distribution is exactly what §14.1's thresholds get judged against.

Taken at face value, the COCO arm says the junction barely changes state and a
last-value baseline scores 93.1%: the task is not worth modelling. That
conclusion would have been an artifact of the measuring device. **The detector
is now a parameter (`--weights`, `--conf`) and both arms are recorded.**

### The gate passed a 93.1% naive baseline

`PilotResult.task_is_learnable` was `transition_rate >= 0.05`. The rule it
implements, stated in BUILD-LOG S06, is: "if ~90% of windows do not change class
within 60 seconds, a last-value baseline sits near the ceiling and no model can
be ranked against another."

90% unchanged is a **10%** transition rate. The gate was written at half that,
so it printed `VERDICT 2 PASS` for a 6.9% transition rate and a 93.1% naive
baseline — the precise condition it exists to reject. No test pinned the
threshold, which is how the two came apart.

`MIN_TRANSITION_RATE = 0.10` now, with tests pinning it and both measured arms.

**This tightening is adverse to us and was made knowing that.** It flips a
result already recorded as passing. The reported arm passes either way (31.0%),
so nothing moved to rescue a number.

### Consequences

1. **The task is learnable and that is now measured, not assumed.** 31.0% of
   windows change class over the horizon. This was the measurement that could
   have ended the project.
2. **69.0% is the floor for every model**, and belongs beside every reported
   result. A model scoring under it is worse than assuming nothing changes.
3. **A30 has its evidence.** §14.1's `LOW < 5` never fires on this camera — the
   p10 count is 9. Thresholds in absolute vehicle count describe the *view*, not
   the road. The defensible form is per-camera calibration recorded with the
   corpus; on this camera the measured split is `LOW < 11 · MEDIUM 11–14 ·
   HIGH > 14`. **Still requires sign-off** — it changes a graded specification.
4. **A pilot's detector must be reported with its numbers.** A count
   distribution without the instrument that produced it is not interpretable.

---

## P21 — the detector's headline number does not generalise, and one class was never trained (2026-08-19)

**Status:** OPEN · Found by evaluating our best detector on TrafficCAM before
training on it

`s15_yolov8s_joint_aug` scores **mAP50 0.8941 on BMD-45 elevated**, and that
figure has been the project's detection headline since A31 closed. Evaluated
unchanged on [TrafficCAM](../00-planning/research/TRAFFICCAM-ASSESSMENT.md) —
human-annotated Indian elevated CCTV from different cities — it scores
**0.3500**.

| class | AP50 on TrafficCAM | boxes |
|---|---|---|
| auto_rickshaw | 0.587 | 1,234 |
| motorcycle | 0.571 | 6,038 |
| car | 0.463 | 5,267 |
| bus | 0.422 | 372 |
| truck | 0.407 | 617 |
| **pedestrian** | **0.001** | 1,593 |
| **e_rickshaw** | **0.000** | 365 |

### `e_rickshaw` was never trained, not merely never evaluated

The morning's finding was that `e_rickshaw` has zero test boxes in IDD and zero
in BMD-45. The cause is worse than the symptom:

    IDD train  e_rickshaw=0
    IDD val    e_rickshaw=0
    IDD test   e_rickshaw=0

**Zero instances in the entire dataset.** The detector carries an `e_rickshaw`
output head that has never seen one training example. Its 0.000 AP is not a
generalisation failure — the class does not exist in anything we trained on.

PRD §5 lists e-rickshaw among the India-specific classes that justify building
our own detector at all. **One of the classes in the novelty claim has been
decorative since S11.** Nothing caught it because the class was equally absent
from the test split, so no metric ever had the chance to be zero.

TrafficCAM supplies 687 train / 786 val / 227 test e_rickshaw boxes. It is the
first data in the project that can train or measure the class.

### The 0.8941 is measured on unusually easy objects

Median box area as a fraction of the frame, square-rooted to a linear size:

| dataset | car | motorcycle | pedestrian |
|---|---|---|---|
| **BMD-45 eval** | **0.1055** | **0.0741** | — |
| IDD test | 0.0564 | 0.0453 | 0.0314 |
| TrafficCAM test | 0.0556 | 0.0407 | 0.0569 |

BMD-45's objects are **about twice the linear size** of both other sets — four
times the pixel area. IDD and TrafficCAM agree closely with each other and
disagree with BMD-45.

So the ordering 0.894 (BMD-45) > 0.710 (IDD) > 0.350 (TrafficCAM) is not three
measurements of one capability. It is substantially a measurement of how large
the objects are in each set, and **the number we have been quoting comes from
the easiest of the three.**

A scale explanation does *not* cover `pedestrian`: TrafficCAM's pedestrians are
**larger** than IDD's (0.0569 against 0.0314), and AP falls from 0.458 to 0.001.
That remains unexplained and is recorded as open — one candidate is the S09
`rider`-into-`motorcycle` convention colliding with TrafficCAM annotating riders
separately.

### Consequences

1. **The headline must be reported per dataset, with object scale stated.** A
   single "mAP50 0.8941" is not defensible when the same weights score 0.35 on
   comparable footage from other Indian cameras.
2. **TrafficCAM training moves from optional to necessary.** It is the only
   source that can train `e_rickshaw` at all, and the only cross-camera test of
   whether the detector generalises within India.
3. **ADR-018's criterion 1 is not wrong but is now insufficient.** Holding
   BMD-45 at 0.8941 says nothing about the 0.35. A TrafficCAM criterion belongs
   beside it.
4. **This was found before training on TrafficCAM, not after.** Had the arm been
   trained first, 0.35 → some higher number would have looked like the new data
   helping, when a large part of it is the old number never having been
   trustworthy.

### What was right

Measuring the existing model on new data **before** training on it. That is a
free experiment, it takes fifty seconds, and it is the only ordering that can
tell a generalisation failure apart from a training improvement.

### P21 addendum — e-rickshaws are found and mislabelled, not missed

Matching our detector's predictions against 168 ground-truth e-rickshaws by
IoU ≥ 0.4:

| our detector calls it | share |
|---|---|
| **motorcycle** | **47.6%** |
| auto_rickshaw | 25.6% |
| missed entirely | 23.8% |
| car | 3.0% |

**76% are localised correctly and given the wrong label.** With no `e_rickshaw`
concept the head assigns the nearest class it was trained on, and for a small
three-wheeler that is usually `motorcycle`. `auto_rickshaw` is over-predicted
**1.77×** against its own ground truth, which is the same effect seen from the
other side.

This is better news than a 0.000 AP suggests: the features and localisation are
already there, so the class needs examples rather than a new capability.

**It interacts with [ADR-017](decisions/ADR-017-pcu-thresholds.md), and against
us.** A raw vehicle *count* barely notices this error — 76% of e-rickshaws are
still counted as some vehicle. PCU weighting does notice: an e-rickshaw scored
as a motorcycle carries **0.30 PCU instead of 1.20**, a four-fold under-weight,
and as a car 1.00 instead of 1.20.

So PCU-weighted occupancy is *more* sensitive to class confusion than raw
counting is. ADR-017 argued for PCU on resolution grounds and that argument
stands, but this is a cost on the other side of the ledger and it was not in the
ADR. **PCU should not be adopted on a detector that cannot tell an e-rickshaw
from a motorcycle**, which makes fixing the class a precondition for ADR-017
rather than an unrelated task.

---

## P22 — the corpus blocker is size, not thresholds, and it is off by an order of magnitude (2026-08-19)

**Status:** OPEN · Found by building the corpus instead of reasoning about it

The project status recorded earlier today said MFSTNet was "blocked on one
decision rather than on compute" — the ADR-017 threshold sign-off. **That was
wrong, and building the corpus proved it in ten minutes.**

### The threshold decision never blocked anything

The expensive pass — running the detector over every frame — produces
`counts.csv`, which contains **no thresholds at all**. Labels are a cheap
arithmetic derivation written into `sequences.csv`, and `label_from_count`
already took `low_max`/`med_max` as parameters, with a docstring saying so:
"a recalibration is a config change, not a code change."

Only the plumbing was missing. `build_corpus.py` now exposes both thresholds and
records them in the manifest, and `relabel_corpus.py` regenerates labels under
any threshold set in seconds without touching the detector. **A threshold
decision selects which labelling is the headline; it cannot gate the work.**

### What actually blocks it

The 20-minute Dhaka clip yields **242 samples and 29 windows**. One prediction
window spans 360 s (A15: T=60 × 5 s + 60 s horizon), so at a 30 s stride a clip
of duration D gives `(D − 360) / 30` windows.

Worse, `assign_splits` refuses a single clip — correctly, since hash-assigning
one clip empties two splits. The honest alternative for one continuous recording
is a temporal split, and it must discard windows within one window-length of
each boundary, because neighbouring windows share 11 of their 12 half-minutes.

Applied to the real numbers:

    29 windows -> 1 survives the buffers -> 'val' is empty -> REFUSED

**One clip does not produce a corpus. It produces one window.**

| source | windows @ 30 s stride |
|---|---|
| Dhaka (1,206 s) | 28 |
| M6 Motorway (2,048 s) | 56 |
| 4K road traffic (2,093 s) | 57 |
| Highway sounds (3,602 s) | 108 |
| **all 8 fixed-camera clips** | **351** |

Shrinking the stride inflates the count without adding information — at 5 s the
Dhaka clip reports 169 windows that overlap almost completely.

### The resolution, and it makes the science better

**P17 said a corpus cannot span cameras.** Re-read precisely, it said a corpus
cannot span cameras *through one shared polygon set*, because a polygon lives in
the image plane. With **polygons surveyed per camera** — which
`survey_lanes.py` already does — and **thresholds calibrated per camera** —
which is exactly what ADR-017 proposes — a multi-camera corpus is coherent.

That takes the corpus from 28 windows to ~351, and it changes the experimental
design for the better: **split by camera, so the test split is a held-out
camera.** P21 measured the detector losing 0.8941 → 0.3500 across camera sets;
a corpus whose test split is a different camera measures precisely the
generalisation that matters, instead of assuming it.

**So ADR-017 is not a labelling tidy-up. It is the precondition for having a
corpus at all**, and its priority should be read that way.

### Consequences

1. **The status page's "blocked on one decision" was wrong** and is corrected.
   The blocker is footage volume, and it is an order of magnitude, not a margin.
2. **`assign_splits_temporal` exists** for the single-camera case and refuses
   loudly rather than silently producing an unusable split.
3. **Per-camera polygons must be surveyed for the remaining seven clips.** That
   is human work — each needs looking at, per `survey_lanes.py`'s own warning.
4. **351 windows is still small** for a model with attention layers. It is
   enough to train Phase 1 honestly and report it with its size stated; it is
   not enough to claim a large-scale result.
5. **S06's recording trip becomes the highest-value input again**, for a reason
   sharper than before: hours from one junction beats minutes from many.

### P22 addendum — A28 is the decision that unlocks the corpus, not ADR-017

Two more measurements, and together they change which sign-off to chase first.

**Independent segments, not windows, is the honest sample size.** Sliding-window
augmentation is standard practice and legitimate *within* the training split —
the rule it must never break is overlap between train and test. So the corpus
can use an **asymmetric stride**: dense for train, sparse and buffered for
val/test.

That inflates the window count without adding information, and both numbers must
be reported:

| | |
|---|---|
| train windows at a 5 s stride | 1,053 |
| **independent 360 s segments** | **12** |

Twelve. Across all eight fixed-camera clips. A model with attention layers
trained on twelve independent temporal segments is a pilot, not a result, and
saying otherwise would be the kind of claim this log exists to prevent.

**A28 is the lever, and it is already written and pre-registered.** `step_s = 5`
is a bare number in §8.2 that is derived nowhere; the whole 355 s minimum rests
on it. Recomputing the segment count across the triaged footage:

| `step_s` | window span | independent segments | cameras usable |
|---|---|---|---|
| 5 (current) | 355 s | 19 | 8 |
| 4 | 296 s | 25 | 9 |
| 3 | 237 s | 32 | 10 |
| **2** | **178 s** | **42** | **11** |
| 1 | 119 s | 67 | 11 |

**A28 at `step_s = 2` more than doubles the corpus from footage already on
disk**, and admits three clips currently rejected on arithmetic alone — one of
them the Andheri intersection, which A28's own entry calls the best-composed
Indian intersection scene in the collection.

### The corrected priority

Earlier today this log said to take **ADR-017** to the guide first. That was
right about ADR-017 mattering and wrong about the order:

1. **A28 first.** It is what determines whether a corpus exists at all, and it
   doubles it from data already downloaded. It is also *cheaper to accept* — the
   PRD's own §8.2 never derived the number being changed.
2. **ADR-017 second.** It decides which labelling is the headline, and
   `relabel_corpus.py` makes that switchable in seconds after the fact.

**A28 was written to unblock S06** — to stop rejecting good footage on
undefended arithmetic. Its larger value was not measured until now: it is the
single decision that most increases the corpus, and it needs no new data.

### On TrafficCAM's official splits

TrafficCAM ships `splits/benchmark/` — 2,263 supervised train, 209 val, 1,529
test, plus semi-supervised subsets with **~60,000 unlabelled frames**.

**These are detection splits and they help the detector, not the corpus.** Using
them replaces our ad-hoc camera-session split with the published benchmark, which
makes our detector numbers directly comparable to the TrafficCAM paper — a real
gain, and it should be adopted for that reason.

They do nothing for MFSTNet. A TrafficCAM sequence is 30 frames at stride 2,
about **two seconds**, against a window span of 178–355 s. No split of a
two-second clip produces a forecasting window. The corpus constraint is
unchanged by anything in that folder.

---

## A28 — resolved by measurement. `step_s = 2`, and §14.1's 5 s is contradicted (2026-08-19)

**Status:** MEASURED · the pre-registered statistic now has data · **still needs
sign-off, but the question it asked is answered**

A28 asked for `step_s` to become "an output of the Week-2 pilot rather than an
input to it", and pre-registered the rule **`step_s = ceil(P75 / 59)`**, where
P75 is the 75th percentile of the dwell time — how long a congestion class
persists before it changes. It also said plainly what would vindicate the status
quo:

> If the pilot shows the class changes on a 300 s timescale, `step_s = 5` is
> vindicated and the clips are correctly rejected.

**It does not.** Measured on the S06 pilot, 242 samples of elevated Dhaka
footage, across three independently trained detectors and two threshold sets:

| detector | thresholds | runs | P75 dwell | `ceil(P75/59)` |
|---|---|---|---|---|
| ours `s14_joint` | §14.1 | 28 | 45 s | **1** |
| ours `s14_joint` | calibrated | 60 | 30 s | **1** |
| COCO `yolov8n` | §14.1 | 15 | 60 s | **2** |
| COCO `yolov8n` | calibrated | 69 | 20 s | **1** |
| ITD v1.2 | §14.1 | 15 | 70 s | **2** |
| ITD v1.2 | calibrated | 62 | 25 s | **1** |

**Every combination gives 1 or 2. None gives 5.** The congestion class changes
on a 20–70 s timescale, not a 300 s one, and the result does not depend on which
detector produced the counts or which thresholds labelled them.

### The measurement is conservative in our disfavour

The pilot sampled every 5 s, so dwell times are quantised to 5 s multiples and
the measured P75 is an **upper bound** on the true dwell. A finer sampling could
only shorten it, which would push `step_s` down rather than up. The conclusion
is therefore robust to the one methodological weakness it has.

### Recommendation: `step_s = 2`

The conservative end of the measured range — it satisfies the rule for every
row in the table, keeps 118 s of history rather than 59 s, and is the value
A28 already nominated as its working default.

| | `step_s = 5` (today) | `step_s = 2` |
|---|---|---|
| window span | 355 s | **178 s** |
| cameras usable | 8 | **11** |
| independent segments | 19 | **42** |

> **Superseded by [P27](#p27).** The segment counts here no longer reproduce —
> they predate the duplicate-camera finding and two detector fixes. Measured
> today: 29 segments over 7 cameras at `step_s = 5`, 64 over 11 at `step_s = 2`.
> The window spans are arithmetic and stand.

**This is the decision that determines whether a corpus exists**, and it needs no
new footage. Three currently-rejected clips become usable, one of them the
Andheri intersection that A28's own entry calls the best-composed Indian
intersection scene in the collection.

### What is NOT being asked for

T=60, the 60 s horizon, clip-level splitting, the stationary-camera requirement
and the human-verified test split are all untouched — as A28 originally stated.
The only change is that a number which was never derived is now derived, from
the statistic that was fixed in advance for exactly this purpose.

### Honest limit

42 independent segments is a **pilot-scale corpus**. Sliding-window augmentation
can produce ~1,000 training windows from it, and both numbers must be reported
together: the window count without the segment count overstates the evidence by
roughly ninety-fold. Hours of footage from one junction remains the only thing
that changes that — but this change moves the project from *cannot train* to
*can train honestly*, today, on data already downloaded.

> **Superseded by [P27](#p27).** The `~1,000 windows` and `ninety-fold` figures
> were estimates, and both are wrong once measured. At the committed geometry —
> `stride_s = 30`, not one window per frame — the corpus is **355 windows over
> 62 independent segments, an inflation of 5.7×**. The direction of the warning
> was right and its magnitude was invented; the paired-reporting rule it
> introduced stands and is now stated with measured numbers.

---

## S16 result — ITD distillation NOT ADOPTED, and one of my criteria was vacuous (2026-08-19)

**Status:** MEASURED · 4.2 h on Kaggle T4 x2 · ADR-018 gate applied unchanged

| # | criterion | measured | verdict |
|---|---|---|---|
| 1 | BMD-45 elevated mAP50 ≥ 0.8941 | **0.8884** (−0.0057) | **FAIL** |
| 2a | `cattle` AP50 drop ≤ 0.02 | **0.4794** (was 0.3516, **+0.1278**) | PASS |
| 2b | `e_rickshaw` predictions fall ≤ 50% | **0 vs 0** on 200 frames | PASS |
| 3 | ≥ 10 fps on the stated host | 84.2 fps, Tesla T4 | PASS |
| 4 | IDD mAP50 not down > 0.02 | 0.6963 (−0.0141) | PASS |

**The arm is not adopted.** Criterion 1 failed by 0.0057 — a hair, and precisely
the kind of margin a pre-registered threshold exists to decide without
negotiation. ADR-012's discipline applies: the number is recorded, the criterion
is not retuned.

### What the distillation actually bought and cost

Training a YOLOv8s student on 1,200 frames pseudo-labelled by ITD-x produced a
model that is **slightly worse on both established test sets** — BMD-45 −0.0057,
IDD −0.0141 — while gaining nothing on the class the merge existed to protect.

That is consistent with what the pilot measured before the run: ITD's advantage
is concentrated in small classes, and **65% of its bus detections and 43% of its
trucks on this footage were oversized enough to be rejected**. A teacher that
noisy hands a student noise along with signal.

### Criterion 2b passed vacuously, and that is my error

`e_rickshaw` predictions were **0 before and 0 after**. The criterion asked
whether the count fell by more than half; zero does not fall. It passed while
proving nothing, because the class was already dead — which
[P21](#p21) established the same day for a reason the criterion could not see:
IDD contains **zero** e_rickshaw instances, so the head was never trained.

A criterion that cannot distinguish "the class was preserved" from "the class
was already absent" is not a criterion. It was written when no labelled
e-rickshaws existed anywhere in the project, and it was honest about that limit
at the time — but it should have been marked unfalsifiable rather than counted
as a pass. **S17 replaces it with a real AP50 measurement** on TrafficCAM's 227
labelled e-rickshaw test boxes.

### The genuinely surprising result

**`cattle` improved by +0.1278**, from 0.3516 to 0.4794 — a 36% relative gain on
a class that appears **nowhere in ITD** and nowhere in the pseudo-labels. It came
from the label merge preserving our own detections plus, most likely, the extra
elevated-domain frames helping a class that is only ever seen from above.

That is worth keeping even though the arm is rejected: it is evidence that
elevated-domain training data helps classes the new data does not contain, which
is an argument **for** S17 rather than against it.

### Consequences

1. **The S16 weights are not adopted.** `s15_yolov8s_joint_aug` remains the
   detector of record at 0.8941.
2. **Pseudo-labelling from ITD is not a dead end, but it is not free.** A teacher
   whose large-vehicle boxes are majority-spurious needs stricter filtering than
   an area threshold before it is worth a second attempt.
3. **S17 is the better-posed experiment** and it is running: human annotations
   rather than a noisy teacher, and a criterion on `e_rickshaw` that can fail.
4. **A negative result, reported.** PRD §2.5.5 requires this and it is the third
   time today the pre-registered discipline has cost us a preferred answer.

### A28 addendum — measured on a real build, and it settles the split strategy

`step_s = 2` was applied to the Dhaka clip end to end. It works, and it fails,
and both halves are informative:

| | `step_s = 5` | `step_s = 2` |
|---|---|---|
| samples from 1,206 s | 242 | **603** |
| sequences | 86 | **103** |
| survive leak-free buffers | **1** | **20** |
| 3-way temporal split | refused | **still refused** |

**Twenty times more usable windows, and still not a corpus.** The reason is
arithmetic rather than luck. A three-way temporal split needs every band wider
than one window plus a buffer either side; the narrowest band is `val` at 20% of
the span, so `0.20 × span ≥ 3 × window`, i.e. **the recording must be at least
fifteen windows long**.

| clip | seconds | span/window @ `step_s=2` | 3-way? |
|---|---|---|---|
| Dhaka Rampura | 1,206 | 6.8 | no |
| M6 Motorway | 2,048 | 11.5 | no |
| 4K road traffic | 2,093 | 11.8 | no |
| **Highway sounds** | **3,602** | **20.2** | **yes** |

**One camera needs ~44 minutes at `step_s = 2` to support a temporal split.**
Exactly one clip in the collection clears it, and it is a Western motorway.

### So the split strategy is settled: by camera, not by time

Splitting **by camera** needs no temporal buffers at all — two cameras share no
frames, so there is nothing to leak. It also makes the test split a **held-out
camera**, which measures the generalisation P21 showed the detector lacks
instead of assuming it.

That requires `step_s = 2` to reach eleven cameras, and per-camera lane polygons
for each. **A28 and the multi-camera corpus are one decision, not two.**

The temporal split stays implemented and tested: it is the correct mode once S06
delivers 44+ minutes from a single junction, which is now a precisely-stated
requirement rather than a vague preference for "more footage".

---

## S17 result — TrafficCAM +0.2234, `e_rickshaw` alive for the first time, and a real trade-off (2026-08-19)

**Status:** MEASURED · 2.8 h on Kaggle T4 x2 · gate applied unchanged ·
**NOT ADOPTED** under the pre-registered criteria

| # | criterion | measured | verdict |
|---|---|---|---|
| 1 | TrafficCAM mAP50 > 0.3500 | **0.5734** (+0.2234) | **PASS** |
| 2 | `e_rickshaw` AP50 > 0.30 | **0.4787** (was 0.000) | **PASS** |
| 3 | BMD-45 not down > 0.02 | 0.8916 (−0.0025) | PASS |
| 4 | IDD not down > 0.02 | **0.6188** (−0.0916) | **FAIL** |
| 5 | `cattle` not down > 0.02 | 0.3508 (−0.0008) | PASS |
| 6 | ≥ 10 fps | 79.4 fps, Tesla T4 | PASS |

### The class that was never trained now works

`e_rickshaw` went from **0.000 to 0.4787**. [P21](#p21) established that IDD
contains zero e_rickshaw instances, so the detector shipped an output head that
had never seen one example — decorative since S11, in a class PRD §5 lists among
the India-specific ones that justify building our own detector at all.

1,254 human-annotated training boxes fixed it. That is the single most valuable
outcome of the day, and it came from data, not from architecture.

### Cross-camera generalisation improved by 64% relative

TrafficCAM **0.3500 → 0.5734**. P21 measured the detector losing two-thirds of
its accuracy when moved to Indian cameras it had not seen; roughly half of that
loss is now recovered, and BMD-45 held at 0.8916 while it happened.

`cattle` also held at 0.3508 despite being **absent from TrafficCAM entirely** —
the second time today that elevated-domain data has protected or improved a class
the new data does not contain.

### The cost, and it is a real trade rather than a defect

IDD fell **0.7104 → 0.6188**, a drop of 0.0916 against a 0.02 tolerance — 4.6×
over. The model has specialised toward elevated fixed cameras and away from
dashcam.

**The arm is not adopted.** Criterion 4 was fixed before the run and it failed;
ADR-012's discipline is that the number is recorded and the criterion is not
retuned to fit it. That rule has now cost a preferred answer four times today,
which is the only reason it is worth anything.

### What the criterion did not encode, stated as a question rather than an excuse

Criterion 4 assumed dashcam accuracy matters. **The deployment is an elevated
fixed camera** (ADR-003, PRD §7), and IDD is the only dashcam surface in the
project. So the trade may well be one the project *wants*.

That is a **scope decision for the guide, made forward**, not a retroactive
reinterpretation of a failed criterion. The honest options:

1. **Keep criterion 4.** IDD stays a reported set and the arm is rejected.
2. **Retire IDD as an acceptance surface**, keeping it as a reported number, on
   the grounds that no deployment sees a dashcam. Then re-run and judge against
   criteria fixed in advance of *that* run.

Option 2 must not be applied to this run's numbers. It changes what a future
experiment is judged on, which is legitimate; changing what this one is judged
on after seeing 0.6188 would not be.

### Consequences

1. **`s15_yolov8s_joint_aug` remains the detector of record**, unchanged, at
   0.8941 BMD-45 / 0.7104 IDD / 0.3500 TrafficCAM.
2. **The multi-camera direction is vindicated.** Elevated Indian data bought
   +0.2234 cross-camera and revived a dead class, which is the strongest
   available argument for the multi-camera corpus and for A28 that unlocks it.
3. **P21's reporting rule is now mandatory in practice, not just in principle.**
   No single mAP number describes this model: 0.8916 / 0.6188 / 0.5734 with
   object scale stated is the only honest summary.
4. **Two arms run, two rejected, both informative.** S16 showed a noisy teacher
   costs more than it gives; S17 shows human annotation in the target domain
   gives a great deal and costs something specific and namable.

---

## P23 — the lane survey inherits the detector's blind spots (2026-08-19)

**Status:** OPEN · Found by drawing detection boxes instead of centroids, after
the reviewer asked why the preview used dots

The lane review sheet drew each detection as a **coloured dot** — the centroid,
accumulated over 60 sampled frames and coloured by lane assignment. That is what
a lane survey needs, and it is the wrong thing to show, because it makes the
detection underneath **impossible to judge**. Object detection is read as boxes;
a dot hides both the box extent and whether the box was right.

Drawn properly, on the mid-frame of each clip at conf 0.45:

| camera | detections | quality |
|---|---|---|
| **M6 Motorway** | 19 | **near perfect** — every visible vehicle boxed, tight, correctly classed |
| **Mumbai Andheri** | 16 | **poor** — 25+ vehicles visible |

On the Mumbai frame, specifically:

* **at least four auto-rickshaws in the lower-left are missed entirely**,
  including a large one in the foreground;
* `truck 0.84` is a **market stall**, not a truck;
* several boxes are grossly oversized — the bus box overshoots, and a `car` box
  spans a largely empty region;
* roughly ten pedestrians are visible and **none** is detected.

This is [P21](#p21) rendered as a picture rather than a number: 0.8941 on BMD-45,
0.3500 on other Indian cameras. The measurement said it; the frame shows it.

### The consequence that matters, and it was not obvious

**Lane centres are computed from detection centroids.** Where the detector is
blind, no centroid appears, so the cluster centre moves toward the region the
detector happens to handle. On Mumbai the missed lower-left auto-rickshaws are
exactly the traffic a lane there would count.

**A biased detector produces biased lanes**, and every count drawn through them
inherits the bias. The unassigned rate — P17's diagnostic — cannot see this: a
vehicle that was never detected is not unassigned, it is absent.

### Two corrections

1. **Previews must show boxes.** The lane assignment is still the point, so the
   preview now draws detection boxes for the displayed frame *and* the lane
   centres, rather than substituting centroids for both.
2. **The survey should use the best detector for the domain, not the adopted
   one.** S17 scores **0.5734** on this kind of camera against s15's **0.3500**,
   and was rejected only for regressing IDD dashcam accuracy — which has nothing
   to do with surveying a lane on an Indian arterial.

**Point 2 is a distinction worth stating explicitly.** A model rejected for
*reporting* can be the right *tool*: surveying lanes is not a reported result,
and using a weaker detector there to stay consistent with an adoption decision
would be cargo-culting the rule rather than applying it. The adopted detector
remains s15 for every number the project reports.

### What this does not change

The nearest-centre method is unaffected — it was adopted because polygons
overlapped on 11 of 12 cameras, and that finding stands. This is about the
*input* to the clustering, not the clustering.

### P23 addendum — measured, and it is worse than the argument suggested

P23 argued that lane centres inherit the detector's blind spots. Surveying all
twelve cameras a second time with **ITD-x at its trained resolution** made that
measurable.

**Lane centres move by a median of 0.1639 of frame width** — roughly **315
pixels on a 1920-wide frame** — when the detector changes.

| camera | s15 dets | ITD dets | centre shift | unassigned |
|---|---|---|---|---|
| Dhaka Rampura (b) | 1,264 | 535 | **0.286** | 16.1% → 12.9% |
| Relaxing highway | 325 | 621 | **0.339** | 11.1% → 7.6% |
| M6 Motorway | 950 | 1,364 | 0.262 | 7.5% → 9.2% |
| South Extension | 2,759 | 2,043 | 0.221 | 36.9% → **28.4%** |
| Mumbai Andheri | 1,587 | 426 | 0.107 | 13.7% → 4.9% |
| Highway sounds | 199 | 264 | 0.051 | 3.5% → 5.3% |

**All twelve cameras now clear the 35% unassigned gate**, against ten before —
so the better detector helps by that measure. But the centres it produces are
somewhere else entirely.

### The confound I introduced, and the clean test

The re-survey changed **three variables at once** — detector, `imgsz`, and a new
box-area filter — which is precisely the discipline this project applies to
every other comparison and which I did not apply here.

Isolating the area filter alone, s15 at `imgsz 640`, 40 frames:

| camera | centres shift from the filter alone |
|---|---|
| Mumbai | 0.0108 |
| Dhaka | 0.0160 |
| M6 | 0.0036 |

**An order of magnitude smaller than 0.164.** The filter is not the cause; the
detector is. P23's mechanism is confirmed rather than merely argued.

Pairing was also checked: matching centres optimally instead of by index changed
the median not at all, and found only **one** label flip in twelve — so the
movement is real and not an artifact of arbitrary cluster labels.

### What this means for the method

**A lane whose position moves 16% of the frame when the tooling changes is not a
property of the road.** It is substantially an artifact of which vehicles the
detector happened to see, and every count drawn through it inherits that.

`survey_lanes.py` has always said its output is "a starting point to check by
eye, not an authority". This puts a number on how far from an authority it is.

**So automatic lane inference should not be used unreviewed, and the tooling
should stop implying otherwise.** The productive shape is a human placing lane
centres once per camera — with the detection density rendered underneath as a
visual aid — rather than a clustering that must then be audited.

Nearest-centre assignment is unaffected and remains right: it is disjoint by
construction and reproduces whatever centres it is given. The defect is in how
the centres are *chosen*, not in how they are *used*.

---

## Milestone — the ablation harness runs on real video (2026-08-19)

**Status:** SMOKE TEST · not a result, and reported as one nowhere

All eight ablation configs (A–H) ran through one code path on real cached
frozen-backbone features, and wrote a 32-column CSV. This is the first time
video has reached the model in this project.

    clips -> detector -> per-camera counts -> labels -> windows
          -> camera splits -> frozen-backbone cache -> MFSTNet -> CSV

The harness behaves as specified:

* **Every config executes.** CNN-only, ViT-only, concat, unidirectional,
  bidirectional, +temporal attention, full gated, and the A22 linear probe.
* **`use_gate` is honoured.** `gate_mean`, `gate_std` and `gate_range` are
  populated for **G alone**, which is the only config with gating on. H is the
  linear probe and correctly reports none.
* **NFR-15 holds in practice:** the eight configs differ only by config, with no
  code edit between them.

### The P16 instrument works, and says what it said before

Config G reported **`gate_mean 0.52477`, `gate_std 0.004806`** — the gate sitting
essentially at its initialisation, which is what P16 measured on synthetic data
(0.4999 / 0.00227).

**That is not evidence about the gate.** Two epochs on sixty sequences with two
windows in test cannot move a gate or refute anything. What it establishes is
that the falsification test P16 pre-registered — gate std > 0.05 **and** G beats
E — is now *runnable* rather than merely written down. It needs a real corpus.

### Why the accuracy numbers are absent from this entry

Macro-F1 across the eight configs was 0.0 or 0.3333, on **two test windows**.
Reporting a comparison from that would be worse than reporting nothing, and the
configs that scored 0.3333 (D, F, H) have no claim over those that scored 0.0.

### What this milestone is

Proof that the pipeline runs, not that the model works. The lanes were automatic
centres marked reviewed to exercise the path, and the corpus is four clips.

**Five integration defects were found by running it**, none of which the ~500
unit tests caught, because all five lived between components:

1. labelling iterated polygons after counting had moved to centres
2. hash-based splits left val and test empty at four cameras
3. lanes surveyed with one detector, counted with another (44% unassigned)
4. ROI pooling had no region — a centre is not one
5. lane geometry did not travel with the corpus manifest

---

## P24 — `vehicle_ids` counted three of ITD's seven vehicle classes, and it voided a conclusion I had just published (2026-08-19)

**Status:** CLOSED · Found by a contradiction between two of my own measurements

Comparing detectors on one Mumbai clip, s15 reported **842** vehicles and ITD-x
**286**. [P21](#p21) had measured ITD finding **11–27% more** than s15 on
comparable footage. Both could not be right.

### The cause

`scripts/pilot_a17.vehicle_ids` resolved vehicle classes from a fixed
**inclusion** list:

    VEHICLE_NAMES = {"car", "motorcycle", "bus", "truck",
                     "auto_rickshaw", "e_rickshaw"}

An inclusion list only recognises the taxonomy it was written against. Against
ITD's names it matched **`bus`, `car`, `truck`** and silently ignored
**`two wheeler`, `autorickshaw`, `LCV`** — on Indian footage, most of the
traffic. Every ITD count in the corpus builder and the lane survey was over a
crippled detection set.

**The same defect was found and fixed in `pilot_counts.py` earlier the same
day**, with a comment explaining exactly this failure — and it was not fixed in
`pilot_a17.py`, which is what `build_corpus.py` and `survey_all.py` import. One
fix, one file, and the identical bug three imports away.

Resolution is now by **exclusion**: everything is a vehicle except people,
cattle, riders and street furniture. That is taxonomy-agnostic by construction.

### What it voids, including a recommendation made minutes earlier

I had reported that counting with the same detector the lanes were surveyed with
cuts the unassigned rate, citing 30.1% → 21.2% across four clips and
18.3% → 9.5% on Mumbai. **Both numbers were the bug.** ITD looked cleaner
because it was counting a third of the vehicles.

Re-measured on identical frames and lanes after the fix:

| detector | assigned | unassigned | rate |
|---|---|---|---|
| s15 @640 | 842 | 189 | **18.3%** |
| ITD @992 | **1,038** | 243 | **19.0%** |

ITD finds **23% more vehicles**, which restores agreement with P21. But the
unassigned rate is **the same**, not lower.

**So the operational claim is withdrawn: matching the survey detector to the
counting detector does not reduce the unassigned rate on this evidence.**

The underlying principle survives on different grounds — P23 measured lane
centres moving 0.164 of frame width between detectors, so lanes and counts
should still share one detector because they otherwise describe different
geometry. That argument was never the unassigned rate.

### Consequences

1. **`data/corpus_smoke_itd` is void** and its label distribution (LOW 46.7%
   against the s15 build's 16.7%) was an artifact of missing two-wheelers and
   auto-rickshaws, not a threshold effect.
2. **`--imgsz` was still worth adding.** ITD at 992 against 640 is a real
   difference and the corpus manifest now records the resolution alongside the
   detector, because a count from a model run outside its trained size is a
   different measurement.
3. **The lane survey used the same broken resolution.** The ITD centres in
   `data/lanes_itd` were clustered from car/bus/truck centroids only. They must
   be re-surveyed before use — which matters, because the placement heatmaps
   were rendered from them.

### P24 addendum — blast radius, audited rather than assumed

A defect that silently drops two thirds of the traffic deserves its reach
established, not estimated. Every consumer of `vehicle_ids`, checked:

| script | model it runs | affected? |
|---|---|---|
| `survey_all.py` | ITD-x | **YES** — `data/lanes_itd` re-surveyed |
| `build_corpus.py` | ITD-x | **YES** — `corpus_smoke_itd` deleted |
| `build_demo.py`, `check_recording.py`, `survey_lanes.py` | ours | no |
| `evaluate_detector_arms.py`, `measure_viewpoint_robustness.py`, `verify_counting.py` | ours | no |
| `pseudo_label.py` | ITD-x | **no** — see below |

Against our own taxonomy the inclusion list happened to match all six vehicle
classes exactly, so every our-detector number in the project is unaffected.

**`pseudo_label.py` imported `vehicle_ids` and never used it**, behind a
`# noqa: F401 (parity of imports)`. Filtering went through `ITD_TO_OURS`
explicitly, which is why S16's pseudo-labels carried 12,930 motorcycles and
11,050 auto-rickshaws rather than none. **S16 and S17 are unaffected.**

That dead import made this audit harder than it needed to be — grep reported a
consumer that was not one. It is removed, with a comment saying why the absence
is deliberate.

### A28 is unaffected, checked two ways

A28 is the decision heading to the guide, so its independence from P24 was
verified rather than assumed:

1. **`pilot_counts.py` does not call `vehicle_ids`.** It carries its own
   exclusion set, added when this same defect was found there earlier the same
   day.
2. **The numbers themselves rule it out.** ITD's pilot reported p50 **21**
   against s15's **13**. A three-class ITD would have reported *fewer* vehicles,
   not more.

### The regression is now pinned

`tests/test_vehicle_ids.py` resolves our taxonomy, ITD's, and COCO's — including
a taxonomy no rule was ever written for — and asserts that pedestrians, cattle
and riders are never counted under either spelling of "pedestrian". The third
occurrence of this defect will be a red test rather than a wrong number.

## P25 — the unassigned gate was rejecting cameras for having the wrong lane count (2026-08-19)

**Status:** CLOSED · Found by re-surveying after the [P24](#p24) fix

With all seven of ITD's vehicle classes counted rather than three, detections
roughly tripled — Mumbai 426 to 1,781, Dhaka 312 to 1,165 — and **unassigned
rates rose** on most cameras. Two then failed P17's 35% gate:

| camera | before P24 fix | after |
|---|---|---|
| South Extension | 28.4% | **35.1%** |
| video1 | 13.1% | **44.4%** |

The earlier low rates were the artifact: cars, buses and trucks cluster on the
carriageway, while two-wheelers spread across it and its edges. Counting only
the former made every lane look tighter than it was.

### They were not bad cameras

Every camera had been surveyed with a flat `--lanes 2`. Varying it:

| camera | k=2 r0.25 | k=3 r0.25 | k=4 r0.25 | k=2 r0.40 |
|---|---|---|---|---|
| South Extension | **36.5%** | 19.3% | **11.2%** | 9.1% |
| video1 | **44.2%** | 15.4% | **3.3%** | 4.6% |
| Dhaka Rampura | 21.6% | 9.6% | 8.0% | 3.7% |

Both "failures" clear the gate comfortably at k=4. **The gate was conflating an
unusable camera with a wrong lane count**, and a flat k across twelve different
scenes was never defensible — a junction with four approaches is not a motorway
with two.

### Which lever, and why it matters

Raising `max_radius` fixes the number too (South Extension 36.5% to 9.1%), and it
is the wrong fix. The radius is a tuning knob that widens acceptance until the
complaint stops; **`k` corresponds to something real — how many approaches the
scene has.** Choosing k is a statement about the road; choosing radius is a
statement about wanting the gate to pass.

### This vindicates placing lanes by hand

`docs/demo/place_lanes.html` already lets a person place as many centres as the
scene has approaches. P25 shows that is not a convenience — **the lane count is
per-camera information a clustering cannot supply**, because k is an input to
k-means rather than an output of it.

So the automatic survey's role narrows further: it renders where the traffic is,
and every judgement — how many approaches, and where their centres sit — is the
reviewer's. The seeded crosses are a starting point at the survey's k, and
adding or removing them is expected rather than exceptional.

## P26 — a corpus spanning cameras pooled every camera through one camera's lanes (2026-08-20)

**Status:** CLOSED · Found while checking whether [P25](#p25)'s variable lane
counts could reach the model

P25 established that different cameras need different lane counts. Checking
whether `build_corpus.py` could carry that turned up something worse in the
path that already existed.

### What was wrong

`docs/demo/place_lanes.html` produces one set of lane centres **per camera** —
P17 requires it, because a lane lives in one camera's image plane. Three places
then collapsed that back to one set:

1. **`build_corpus.py` counted the rejection rate and wrote labels using the
   seed camera's lane NAMES** (`lane_names(lanes)`, where `lanes` was
   `next(iter(per_clip_lanes.values()))`). With matching counts the names
   coincide and it works by luck; with differing counts it is a `KeyError` or a
   silent undercount that inflates the unassigned rate and rejects a good
   camera.

2. **The manifest recorded ONE camera's `lane_centres` for the whole corpus.**

3. **`train_mfstnet.py` built one `[L, G, G]` mask tensor from that entry and
   passed it to `MFSTNet` at construction**, so `LanePool` pooled every window
   from every camera through the same masks.

Defect 3 is the one that matters. Nothing raises: the shapes agree, the loss
falls, the confusion matrix fills in. **Every camera but one was pooled through
somebody else's lanes**, and the run looks entirely ordinary.

### Nothing published is invalidated

The only run on a multi-camera corpus was the overfit check
(`experiments/results/overfit_check.csv`) — 10 sequences, accuracy 1.0, final
loss 0.0003. That is a memorisation sanity test of the plumbing, and it is not
a result. No ablation table, no reported metric, and no claim rests on the
broken path. The defect was found **before** the real corpus was built, which
is the only reason this entry is short.

### The fix: geometry is an input, not a constructor constant

`LanePool.forward` and `MFSTNet.forward` now accept optional per-sample masks
`[B, L, G, G]`; the einsum becomes `btdhw,blhw->btld`. The dataset carries each
window's own masks and the collate stacks them. Omitting them keeps the old
single-camera behaviour exactly, which is what lets a corpus built before this
still train.

This is the right formulation independently of the bug. **A model meant to
generalise across cameras cannot hold one camera's geometry as a parameter** —
the masks say *where this camera's lanes are*, which is per-input information
by definition.

### The lane count, unlike the positions, must agree

The congestion head is built once with one output per lane, so a corpus cannot
mix a two-lane camera with a four-lane one. Three layers now say so, earliest
first: the placement page marks a camera done only at exactly four and flags
disagreeing counts; `import_lane_centres.py` reports the split by count;
`load_reviewed_lanes` refuses, naming the cameras.

**Four is the count**, from P25's measurements rather than from the PRD: at two
centres South Extension leaves 36.5% of vehicles unassigned and video1 44.2%;
at four, 11.2% and 3.3%.

> **Correction to an earlier reading in this session.** The four lanes at PPO
> state indices 11–14 (§13.1) do *not* fix MFSTNet's lane count. ADR-009 has
> PPO training against a surrogate inside SUMO, whose N/S/E/W approaches are
> SUMO's, and ADR-016 states plainly that the lane count is a config rather
> than an architectural constant. The two only meet at live integration, which
> is Phase 3 and optional. The constraint is narrower than "four by contract":
> **one corpus, one count.**

## P27 — the A28 segment counts are superseded, and the argument for them was the weaker one (2026-08-20)

**Status:** CLOSED · Found while computing corpus yield before the real build

The P22 addendum and [DECISION-BRIEF](DECISION-BRIEF.md) §5 both quote **19
independent segments at `step_s = 5` rising to 42 at `step_s = 2`**, across 8
cameras rising to 11. Recomputing over today's footage reproduces neither
number, from either the triage list or the survey.

`scripts/corpus_yield.py` now computes it, and `experiments/results/corpus_yield.csv`
is the source. Over 12 clips collapsing to 11 distinct cameras, counting only
those clearing P17's 35% unassigned gate:

| `step_s` | window span | sequences | independent segments | inflation | cameras |
|---|---|---|---|---|---|
| 1 | 119 s | 381 | 101 | 3.8× | 11 of 11 |
| **2** | **178 s** | **359** | **64** | **5.6×** | **11 of 11** |
| 5 | 355 s | 302 | 29 | 10.4× | 7 of 11 |

*Computed against the four-lane survey. An earlier run of this table, made
before P25's lane counts were placed, excluded South Extension and video1 for
exceeding the 35% unassigned gate and read 62 segments over 9 cameras. At four
lanes both clear it comfortably — 10.5% and 3.2% — so all eleven contribute.*

The old figures were computed on a footage set from an earlier date and are
withdrawn rather than reconciled — the footage has changed, the duplicate
camera has since been found (P22), and the detector has been fixed twice
(P20, P24). Quoting a number that no longer reproduces is worse than quoting a
smaller one that does.

### The argument was the weaker one either way

Both documents lead with the corpus roughly doubling. **Sequence count is a
poor argument and doubling it is a poorer one**: consecutive windows overlap
heavily — at `step_s = 2` a window spans 178 s against a 30 s stride — so the
count rises with the stride while the information does not. The measured
inflation is 5.7× at `step_s = 2` and 10.4× at 5.

The argument that survives is different and stronger. **`step_s = 5` requires
355 s per clip and so deletes four cameras outright.** Sequences drawn from one
camera are correlated; cameras are the unit the model has to generalise over,
and no amount of sliding-window augmentation manufactures a viewpoint. Going
from 7 contributing cameras to 9 — 11 once P25's lane counts are placed — is
the change that matters.

### The honest limit is unchanged and slightly worse

64 independent segments is a pilot-scale corpus, and 20 of them come from a
single motorway clip. Both numbers travel together in the paper: **359 windows
over 64 independent segments over 11 cameras.** The window count alone
overstates the evidence by 5.6×, and the segment count alone hides that
**31% of it is one camera** — the 3,602-second highway clip. That concentration
is the corpus's real weakness, and no choice of `step_s` fixes it.

## P28 — moving a lane centre cost a full detector pass, so it would not have been moved (2026-08-20)

**Status:** CLOSED · Found while checking what the [P26](#p26) manifest change
implied for the cache

The corpus manifest already carries a `threshold_note` making a point it is
proud of: `counts.csv` is threshold-independent, so `relabel_corpus.py`
re-derives labels in seconds and **a threshold decision is a config change,
never a reason to delay building the corpus.**

The same principle was only half applied. `counts.csv` holds *per-lane* counts,
so it is lane-*dependent*: changing a lane centre meant running the detector
over every clip again. Eleven cameras at ITD-XL and `imgsz=992` is hours.

### Why that is worse than it sounds

Lane centres are placed by hand over a detection heatmap, by eye, on twelve
cameras at four centres each. **That is not going to be right first time**, and
the honest test of a placement is not how it looks but the unassigned rate it
produces — which is only visible after counting.

A feedback loop costing hours per iteration is a feedback loop that gets used
once. The placement would have been judged on appearance and kept.

### The fix

`build_corpus.py` now also writes **`detections.csv`** — every detection in
normalised coordinates, with class and confidence. It is the expensive output
of the pass and **it does not depend on the lanes at all**.
`scripts/relane_corpus.py` rebuilds counts, labels and the manifest from it.

Measured on a two-camera corpus: **0.36 seconds.** The two placements it was
given differ exactly as they should — 2.0% of detections unassigned under
sensible centres, 87.8% under deliberately bad ones.

| changing | costs |
|---|---|
| label thresholds | `relabel_corpus.py` — seconds |
| **lane centres** | **`relane_corpus.py` — seconds** |
| detector, confidence, `step_s`, `imgsz` | `build_corpus.py` — hours |

Splits are carried over verbatim rather than recomputed, so a lane change is
the *only* difference between two corpora and they stay comparable. The feature
cache is untouched: ROI pooling applies geometry at train time (P26), so
`build_cache.py` never needs re-running for a lane change.

NFR-13 is unaffected — normalised boxes and class names, never pixels.

> **Note for the paper.** This makes lane placement a *revisable* parameter,
> which means the placement finally used has to be recorded and justified like
> any other. `relaned_from` in the manifest keeps the chain.

## P25 addendum — four lanes, measured on all twelve cameras (2026-08-20)

P25 measured the four-lane hypothesis on three cameras. Re-surveying all twelve
at `--lanes 4` settles it:

| camera | at 2 lanes | at 4 lanes |
|---|---|---|
| South Extension | **35.1%** | 10.5% |
| video1 | **44.4%** | 3.2% |
| Dhaka Rampura (b) | 22.2% | 2.6% |
| Dhaka Rampura | 23.9% | 1.3% |
| Relaxing highway | 18.5% | 1.7% |
| Mumbai Andheri | 11.6% | 2.2% |
| Pov_Thursday | 9.8% | 1.7% |
| 4K Road traffic (1) | 7.2% | 2.5% |
| Road traffic recognition | 6.8% | 0.8% |
| M6 Motorway | 6.6% | 1.0% |
| Highway sounds | 3.5% | 0.2% |
| 4K Road traffic (2) | 3.0% | 0.0% |

**Every camera improved. None got worse. All twelve clear the 35% gate**, the
worst now being 10.5%. The two "failures" were a wrong lane count throughout,
exactly as P25 argued from three cameras.

### What it changes downstream

All **11 distinct cameras** now contribute, where the k=2 survey excluded two.
The corrected yield is **64 independent segments over 11 of 11 cameras** at
`step_s = 2`, against 29 over 7 at `step_s = 5` — which strengthens A28 rather
than changing its direction.

The placement page is reseeded from this survey, so the reviewer's job is to
**move crosses that sit wrong rather than place four from nothing**. The
heatmaps did not need regenerating: detection density does not depend on the
lanes.

> **The automatic centres are still not trusted.** They sit at the centre of
> mass of a cluster, which on a junction can land between two approaches — a
> low unassigned rate only proves the crosses are *near the traffic*, not that
> they mark the approaches a signal controller would act on. That distinction
> is the whole reason for the review step (P23), and 10.5% versus 0.2% does not
> excuse it.

## P29 — training segfaulted on the second batch, because a window read its whole clip (2026-08-20)

**Status:** CLOSED · Found by running the corpus pipeline end to end on real
multi-camera footage for the first time

The [P26](#p26) fixes were unit-tested but the assembled path had never run on
video. Five cameras, four lanes each, `--step-s 2`, `--imgsz 992`: the corpus
built (85 sequences), the cache built (0.66 GB), and training **segfaulted**,
exit 139, with no Python traceback.

### What it was

`FeatureCache.read_window` called `read_clip`, which loads **every frame of the
clip** and widens fp16 storage to fp32 — then sliced 60 frames out and threw
the rest away. Per window.

A batch of 32 windows from one clip therefore read that clip 32 times. On the
1,035-frame camera that is **26 GB of allocation churn to produce 1.5 GB of
batch**. Measured: collating one batch took free memory from 8.4 GB to 0.0 GB,
and the second batch died.

It had never shown up because every previous run used `corpus_smoke` — four
short clips, tens of frames each, where reading the whole clip costs nothing.

### The fix

`read_window` now memory-maps the file and **slices before widening**, so only
the frames it needs are ever materialised. Measured on the 411 MB clip: **0.01
GB against 0.43 GB, and 29× faster.** The preprocessing-hash check still runs
first; a stale file is still refused.

`read_clip` keeps its eager behaviour for callers that genuinely want a whole
clip.

> **Why the segfault had no traceback.** It was not a Python-level
> `MemoryError` — the allocator failed inside a native `torch.load`, so the
> process died before anything could be raised. A silent exit 139 after a clean
> start is the shape this defect takes, and it is worth recognising: nothing in
> the log said "memory".

### What the end-to-end run also confirmed

- `build_corpus --lanes-dir` produces per-camera geometry for five distinct
  cameras, and training reports `per-camera ROI geometry for 5 camera(s)`.
- `detections.csv` holds 30,292 rows and `relane_corpus.py` re-derives the
  whole corpus from it in **0.66 s**, against roughly 56 minutes for the
  detector pass that produced it.
- `build_cache` caches exactly up to each clip's last needed label frame rather
  than the whole clip, which is why its frame counts sit below the corpus
  sample counts.

### Also fixed: empty frames were dropped on re-derivation

A frame the detector found nothing in writes no rows to `detections.csv`, so
`relane_corpus.py` skipped it — and an empty frame is not missing data, it is
**zero traffic, a LOW label**. Worse, compacting the series breaks the index
arithmetic: window position *i* stops meaning sample *i*, so every label is
read from the wrong moment.

Measured on the real corpus: **119 of 1,046 samples** on one camera, 3 on
another. `build_corpus` now records `samples_per_clip` and `relane_corpus`
rebuilds the full range, counting a missing sample as zero. Corpora built
before this fall back to the highest index seen and say so — interior gaps are
recovered, trailing ones cannot be.

## P30 — requirements.txt contradicted its own first paragraph, and matched nothing installed (2026-08-20)

**Status:** CLOSED · Found while investigating why training ran on CPU

`requirements.txt` opens with:

> Versions are PINNED, not ranged. A range that resolves differently in
> November than it did in August breaks reproducibility silently.

Below that paragraph, **21 of its 35 requirement lines were ranges.** `xgboost`
was listed twice, identically, on consecutive lines.

### The worse half

The 14 lines that *were* pinned did not match the environment. Every single one
that is installed here disagreed with its pin:

| package | declared | installed |
|---|---|---|
| stable-baselines3 | `==2.3.2` | 2.9.0 |
| gymnasium | `==0.29.1` | 1.3.0 |
| eclipse-sumo / traci / sumolib | `==1.19.0` | 1.27.1 |
| tqdm | `==4.66.4` | 4.70.0 |
| python-dotenv | `==1.0.1` | 1.2.2 |

**Seven of seven wrong.** `pip install -r requirements.txt` on a clean machine
would have built a materially different stack from the one every measurement in
this project was taken on — a different SUMO minor version, a different SB3
major. NFR-08 is graded *Critical* and was fiction.

### Why the existing test passed throughout

[P18](#p18) added `test_every_imported_package_is_pinned`, which walks the AST
and checks **imports ⊆ requirements**. That is one direction. Nothing checked
**requirements against reality**, and its own docstring explains the reasoning:

> It reads the source rather than the installed environment on purpose. A test
> that checked `pip list` would pass on the developer's machine — the one place
> the answer is already known — and say nothing about a clean checkout.

That argument is right about a *missing* dependency and wrong about a *lying*
one. A pin nobody has ever run is a guess, and the only machine that can catch
it is the one with the package installed.

### The fix

Every active line is now `==` at the version this environment actually runs,
read from the installed distributions rather than chosen. Three tests enforce
it: no ranges, no duplicates, and **pins match installed versions** where the
package is present (skipping what is absent, so CI and partial checkouts still
mean something). All three fail against the old file.

`pyarrow` and `shapely` are dropped — neither is imported anywhere. Counts are
written as CSV rather than Parquet, and lane assignment has been nearest-centre
arithmetic since [P23](#p23) rather than polygon containment. `kaggle` is added:
`scripts/kaggle_push.py` imports it behind a guard, so it never failed loudly.

Dependencies for subsystems that do not exist — server, dashboard, edge, ONNX
export, MLflow — move to a clearly-marked block that is deliberately **not
pinned and not installed**, since pinning a version nobody has run is the
defect being corrected. ADR-008 may delete them outright.

### The CPU finding that started this

`torch 2.13.0+cpu` is installed while an RTX 4050 (6 GB, driver 610.62) sits
idle. `scripts/check_env.py` reports it correctly and has all along —
`[ WARN ] CUDA -- unavailable -- CPU-only torch wheel?` — with the exact
reinstall command. It was simply never acted on.

**It is not blocking.** Measured on this machine, one config over 73 real
sequences runs at 25.1 s/epoch, which puts the full 8-config ablation at
**~23.6 h on CPU** for the real corpus — against the 60–90 h the PRD budgets
for an *uncached* run on a Colab T4. ADR-005's feature cache is what makes CPU
viable, and it is doing exactly what it was adopted for.

A CUDA reinstall would cut that further and is a ~2.5 GB download that replaces
a working environment mid-project. Recorded as an option, not taken unilaterally.

## P31 — the ablation table read as a comparison when it was an artifact of the split (2026-08-20)

**Status:** CLOSED · Found by running the full A–G ablation on real footage

The first ablation over real multi-camera data returned this:

| config | macro-F1 | QWK |
|---|---|---|
| A (CNN-only) | 0.4889 | 0.5 |
| B (ViT-only) | 0.0 | 0.0 |
| C … G | **0.2222** | 0.0 |

Five configs identical to four decimal places. That is not five models
agreeing — the test split held **no LOW labels at all**, so LOW scores 0 by
convention and drags macro F1 down by a third whatever the model does. 0.2222
is 2/9: one class recovered out of three.

### The warning already existed and was thrown away

`mfstnet/metrics.py` had produced exactly the right message all along:

> LOW has NO samples — its precision/recall/F1 are 0 by convention, and macro
> F1 is being dragged down by a class that does not occur. Check the corpus
> distribution gate (PRD A17).

`train_mfstnet.py` never read `report.warnings`. It printed the number and
wrote the CSV without it, so **the caveat existed and the number travelled
alone** — into `experiments/results/ablation.csv`, a graded deliverable
(NFR-09/10) that a reader would take at face value.

Warnings are now printed per config and carried in a `warnings` column. The
column is present and empty on a healthy split, because a CSV whose columns
change between runs cannot be concatenated across the ablation.

> **Note on duplication.** `train_mfstnet` builds its result row by hand rather
> than calling `EvaluationReport.as_row`, which already existed and is used by
> `overfit_check.py`. The two had silently diverged, and that is how the field
> went missing in the first place. Both now carry it; the duplication itself is
> left in place because changing the column set of a graded CSV is not a
> refactor to make casually.

### Macro F1 averages over every declared class, deliberately

Averaging over only the classes *present* would have reported 0.3333 here.
sklearn's default does that; `labels=[0,1,2]` does not, and neither do we — now
pinned by a test against sklearn so the stricter convention cannot drift.

### The distribution behind it

The five-camera pilot corpus labels **83.5% LOW, 12.9% MEDIUM, 3.5% HIGH** at
the default thresholds. Projected onto the full corpus that is roughly 1,199 /
186 / 51 labels. HIGH is thin, and the thresholds are the lever — which is
[ADR-017](decisions/ADR-017-pcu-thresholds.md), still awaiting guide sign-off.
`relabel_corpus.py` retunes them in seconds, so this is a decision to take with
evidence rather than a cost to pay up front.

## P32 — the GPU was idle for two reasons, and the wheel was the smaller one (2026-08-20)

**Status:** CLOSED · Raised by the project owner, who was right to push back on
"a known, accepted state"

[P30](#p30) recorded `torch 2.13.0+cpu` on a machine with an RTX 4050 as
accepted, on the grounds that CPU training was fast enough. That understated
the problem twice over.

### The documented install command could not have worked

`requirements.txt`, `check_env.py` and the Execution Manual all said:

```
--index-url https://download.pytorch.org/whl/cu121
```

**That index no longer carries torch at any version.** `pip index versions
torch --index-url .../cu121` answers "No matching distribution found", and so
does cu124. Following the documented instruction resolved to the CPU wheel
without reporting anything wrong — which is exactly how the environment ended
up where it did.

What exists today:

| index | newest torch | verdict |
|---|---|---|
| cu121, cu124 | *none* | dead |
| **cu126** | **2.13.0** | matches the installed version exactly |
| cu128 | 2.11.0 | would be a downgrade |

`torch==2.13.0+cu126` and `torchvision==0.28.0+cu126` are the same versions
already installed, so the upgrade changes the compute backend and nothing else.
The GPU is compute capability 8.9 (Ada) on driver 610.62; CUDA 12.6 covers it.

### The wheel alone would have changed nothing

**`train_mfstnet.py` had no device handling whatsoever** — no `.to()`, no
`.cuda()`, no autocast. `build_cache.py` had had a `--device` flag all along;
the trainer never did. Installing a CUDA build would have left the model and
every batch on the CPU, with the GPU still idle and nothing looking wrong.

This is the failure mode worth remembering: **it does not error, and the
numbers are correct.** It is only slow, on a machine that appears healthy.

`--device auto|cpu|cuda` now defaults to `auto`, the model and every batch move
together, and the run prints which device it chose.

### Measured, on the five-camera pilot

| | CPU | CUDA |
|---|---|---|
| config G, 8 epochs | 200.9 s | **24.5 s** (8.2×) |
| full A–H, 8 epochs | 734 s (A–G) | **256 s** |
| peak VRAM at batch 32 × T=60 | — | **4.17 GB of 6.4 GB (65%)** |

Extrapolated to 359 sequences at 100 epochs, the **full A–H ablation is ~3.8 h
on CUDA against ~12.3 h on CPU.**

Two caveats on those numbers, because the headline flatters:

* **8.2× is config G alone**, the heaviest. Across all eight the aggregate is
  ~3.3×, because with GPU compute fast the **cache read becomes the
  bottleneck** — configs A and B gain almost nothing (1.0× and 1.6×). Further
  speedup is now an I/O problem, not a compute one.
* Batch 32 fits with 2.27 GB spare, so ADR-007's bf16 AMP is not needed to make
  it run. It remains available.

### Reproducibility

Two seeded CUDA runs of config G agree on all 31 recorded fields, so NFR-07
holds on the new device. They do **not** agree with CPU — the same config and
seed gives `gate_mean` 0.53895 on CPU and 0.54268 on CUDA, which is ordinary
kernel difference and not fixable by seeding.

ADR-003 already requires every latency figure to state its measurement host.
The same now applies to trained metrics: **the results CSV records `device`**,
because a row that does not say which produced it cannot be compared with one
that does.

### Corrections this forced

* **The ablation is A–H, eight configs, not seven.** An earlier message in this
  session "corrected" 8 to 7; the original was right. **H is the linear probe**
  added by A22 — no fusion, no recurrence, no attention — and it is the floor a
  frozen-backbone paper is expected to report. CLAUDE.md said "configs A-G",
  which A22 made stale.
* PRD §21's "ablation 60–90 h on Colab T4" describes an **uncached** run.
  Cached and local it is under four hours, which is ADR-005 doing exactly what
  it was adopted for.

## P33 — the feature cache was not device-independent, and nothing said so (2026-08-20)

**Status:** CLOSED · Found immediately after [P32](#p32) put the GPU to work

ADR-005 invalidates a cache on any change to "backbone, resize, or
normalization", and `read_clip` raises on a `preprocessing_hash` mismatch
rather than warning. **The hash does not include the device**, so a CPU-built
and a GPU-built cache carry the same hash and can be mixed clip by clip.

That is only safe if the two agree. By default they do not.

### `cudnn.allow_tf32` defaults to True

TF32 gives convolutions a 10-bit significand. Measured on real frames from the
pilot footage, against a CPU fp32 reference:

| | worst difference | as a fraction of tensor scale |
|---|---|---|
| cuDNN TF32 **on** (default) | 1.07e-1 | **3.6e-3** |
| cuDNN TF32 **off** | 9.3e-5 | **3.1e-6** |
| *fp16 storage resolution* | | *4.9e-4* |

With TF32 on, the error is **seven times coarser than the fp16 the cache is
stored in — so it survives storage.** With it off it is 158× finer and
disappears into rounding.

Since splits are cut by clip ([ADR-002](decisions/ADR-002-mfstnet-training-corpus.md)),
a mixed cache means a device artifact that varies clip by clip, and therefore
one that can correlate with the split. That is the shape of defect ADR-005's
hash check exists to prevent, arriving through the one door it does not cover.

### The fix

`build_cache.py` sets `cudnn.allow_tf32 = False` and `matmul.allow_tf32 = False`
on CUDA. The cache becomes device-independent as ADR-005 already assumed, so no
hash change and no forced rebuild. It costs **4% on a one-time build** — 163 ms
to 170 ms per 32-frame batch.

Training is left free to use TF32: the cache is written once and read many
times, and this is only the writing half.

### Getting the measurement right took three attempts

Worth recording, because each wrong metric looked convincing:

* **Absolute difference** (`1.6e-2`) reads as a failure until you notice the
  activations reach 60.
* **Per-element relative error** peaks at 1.0 and 1.99 — but those are
  near-zero values crossing a ReLU boundary or a sign, where the absolute
  difference is negligible.
* **Distance in fp16 representable steps** shows a worst gap of 32,888, which
  again is denormals far apart in bit space and adjacent in value.

The metric that means something is **worst absolute difference as a fraction of
the tensor's own scale**, compared against fp16's 4.9e-4 resolution. The two
built caches sit at 2.6e-4 of scale — inside storage precision, consistent with
fp16 rounding boundaries and not with TF32.

### Also in this change

`--device` now defaults to `auto` in `build_cache.py` and `overfit_check.py`
too. `build_cache` defaulted to `cpu`, so the backbones ran on the CPU unless
somebody remembered the flag; `overfit_check` had a `device` parameter with no
way to set it at all. `resolve_device` and `move` live in `scripts/device.py`
so all three scripts decide the same way.

Rebuilding the pilot cache on the GPU takes **3m48s**.

## P34 — ADR-017's calibration rule made LOW unreachable on real footage (2026-08-20)

**Status:** CLOSED · Found by running `relabel_corpus --calibrate` on the pilot
corpus · **Bears directly on the pending ADR-017 sign-off**

[ADR-017](decisions/ADR-017-pcu-thresholds.md) sets the class boundaries at the
p33 and p67 of the observed count distribution, implemented as:

```python
low_max = percentile(observed, 33) - 1
```

The `- 1` is deliberate: it puts p33 itself in MEDIUM. It also assumes p33 is
greater than zero, and on real footage it is not.

**41.2% of per-lane counts in the pilot corpus are zero.** With four lanes on a
camera, most lanes are empty at any given instant. So p33 = 0, `low_max` = −1,
and **no count satisfies `count <= -1`** — the calibrated corpus came out 0%
LOW in every split, which is precisely the degeneracy calibration exists to
prevent.

| labelling | train LOW / MEDIUM / HIGH |
|---|---|
| §14.1 defaults (4 / 15) | 83.5 / 12.9 / 3.5 |
| CLAUDE.md's example (8 / 20) | 94.5 / 4.5 / 1.0 |
| `--calibrate`, as written | **0.0** / 76.4 / 23.6 |
| `--calibrate`, clamped | **57.2 / 19.2 / 23.6** |

### The fix, and what it means for the ADR

`low_max = max(0, p33 - 1)`. When p33 is zero, **LOW means "an empty lane"** —
which is what the class should mean anyway, and which the unclamped rule
expressed as an impossibility instead. A second guard widens MEDIUM by one if
p33 and p67 collide, so a concentrated distribution cannot leave the middle
class empty either.

**ADR-017 should be amended before sign-off**, not worked around: its rule as
written is correct only for a distribution with no mass at zero, and a
per-lane vehicle count is exactly the kind that has a lot. The guide is being
asked to approve a rule; it should be the one that works.

### Reading the result honestly

57.2 / 19.2 / 23.6 on train is usable. The **test split is still degenerate**,
but for an unrelated reason: the pilot corpus has one test clip yielding one
sequence, so four labels in total. That is a property of a five-camera pilot,
not of the thresholds, and the eleven-camera corpus will not have it.

### The rest of the pipeline, verified on real footage

Every documented step now has a real run behind it rather than a `--help`
check: `build_corpus` → `relane_corpus` → `relabel_corpus` → `build_cache` →
`overfit_check` → `train_mfstnet --config` → `train_mfstnet --ablation` →
`train_baselines`. All four count-sequence baselines train, xgboost included,
so [P18](#p18)'s native-API fix holds on real data.

## P35 — half of every epoch was spent widening fp16 to fp32 on the wrong side of the bus (2026-08-20)

**Status:** CLOSED · Found by profiling an epoch after [P32](#p32) made the GPU
the compute device

[P32](#p32) noted that once the GPU was doing the arithmetic, the aggregate
ablation speedup was only ~3.3× while config G alone gained 8.2×: configs A and
B barely moved, because reading cached features had become the limit. Profiling
one epoch of 73 windows said where it actually went:

| stage | time |
|---|---|
| cache read, per item | 0.69 s |
| read **+ collate** | 3.91 s |
| host → device transfer | 2.12 s |
| forward + backward | 6.01 s |

**The data path was 50% of the epoch, and the read was not the expensive part
of it.** `torch.stack` was, at 3.2 s.

### Why

`FeatureCache.read_window` widened fp16 storage to fp32 before returning, so
everything downstream carried twice the bytes it needed to: `torch.stack`
allocated and copied 770 MB per batch instead of 385 MB, and the PCIe transfer
shipped 1.5 GB instead of 0.77 GB.

Nothing needed fp32 until the model did the arithmetic, on the far side of the
bus.

### The fix, and why it is free rather than a trade

The dataset now reads fp16, the collate stacks fp16, the transfer ships fp16,
and `move(..., cast=torch.float32)` widens on the device.

**Widening fp16 to fp32 is exact** — every fp16 value is representable in fp32
— so where it happens cannot change a number. Verified rather than asserted:
all eight ablation configs agree on **every one of 32 recorded fields**, gate
statistics included.

### Measured, on the pilot corpus

| config | CPU | GPU fp32 path | GPU fp16 path | total |
|---|---|---|---|---|
| A (CNN only) | 33.2 s | 20.5 s | **12.7 s** | 2.6× |
| B (ViT only) | 20.1 s | 19.8 s | **9.4 s** | 2.1× |
| G (full) | 208.4 s | 40.0 s | **16.6 s** | **12.6×** |
| **A–H total** | — | 256 s | **103 s** | **2.48×** on top of the GPU |

Extrapolated to 359 sequences at 100 epochs, the **full A–H ablation is ~1.5 h**,
against 3.8 h on the fp32 GPU path and 12.3 h on CPU.

The configs that gained least from the GPU gained most from this, which is the
expected shape: A and B were never compute-bound.

> **Where the remaining time goes.** The transfer is still pageable rather than
> pinned, and the collate is still single-threaded. Both are worth revisiting
> only if the ablation stops fitting comfortably in an evening — at 1.5 h it
> does.

## P36 — the gate has the capacity to gate; the flat gate is a fact about the data (2026-08-20)

**Status:** CLOSED · P16 asked whether a constant gate could pass unnoticed.
It cannot, and now it has been explained rather than only detected.

Every run on the pilot corpus reported the gate at `mean ~0.54, std ~0.005` —
one value for every spatial location and every timestep, which is a learned
scalar blend rather than a gate. FR-M04 makes the gate a research artifact, so
"why" is a question the paper has to answer.

### The mechanism, measured

`g = sigmoid(Linear([z_a; z_b]))`. Instrumenting the gate's input at
initialisation:

| quantity | value |
|---|---|
| `z_a` std | 0.035 |
| `z_b` std | 0.035 |
| cosine(`z_a`, `z_b`) | −0.004 |
| gate pre-activation std | 0.023 |
| sigmoid slope at 0 | 0.25 |
| **predicted gate std** | **0.006** |
| observed gate std | 0.006 |

The two directions are nearly orthogonal, so they genuinely carry different
information. They are simply **small**: a 512-input Linear over inputs of std
0.035 produces a pre-activation that keeps the sigmoid in its linear region
around 0.5. Reaching saturation needs the Linear's weights to grow by about two
orders of magnitude, and `weight_decay=1e-4` pulls the other way.

### It is a bound on ease, not on capacity

`experiments/gate_capacity.py` builds a task the gate should want to solve:
half the samples carry the label in the CNN branch and half in the ViT branch,
so no single fixed blend serves both. Across three seeds:

| seed | gate std | g when CNN carries | g when ViT carries | separation |
|---|---|---|---|---|
| 1 | 0.320 | 0.404 | 0.670 | 0.266 |
| 7 | 0.263 | 0.451 | 0.672 | 0.221 |
| 42 | 0.444 | 0.481 | 0.654 | 0.172 |

**The gate moves, by 50–90× its pilot spread, and it moves in a consistent and
interpretable direction.** `g` weights `z_a`, which is CNN-queries-ViT, and it
rises when the *ViT* branch holds the signal — the gate routes attention toward
whichever branch is worth reading. That is exactly the behaviour the mechanism
was chosen for, and it is the paper's story if it reproduces on real data.

So a flat gate on the pilot corpus is **a finding about the corpus**, not a
defect: five cameras, 85 sequences, and a label the CNN branch can serve on its
own. It should be re-measured on the eleven-camera corpus and reported either
way — a gate that stays flat there is a result, not an embarrassment.

### The caveat that limits the claim

**Config F reaches accuracy 1.000 on the same task**, so gating was not
*necessary* to solve it. The reason is in the fusion's return:

```python
return self.norm(fused + 0.5 * (f_cnn + f_vit)), gate
```

The residual adds **both branches back, ungated**. Whatever `g` does, neither
branch can be suppressed, so the gate arbitrates only the cross-attention half
of the representation. That bounds how much of the ablation's F→G difference
gating can ever account for, and it is worth stating plainly in the paper
rather than discovering in review.

Recording it, not changing it: the residual is PRD §8.1's architecture, and
altering what the gate can do would change what the ablation measures. That is
a decision for the guide, with this evidence attached.

## P37 — calibration pooled every camera, which ADR-017 explicitly rejects (2026-08-20)

**Status:** CLOSED · Found while drafting the [P34](#p34) amendment to ADR-017

ADR-017 decision 2 reads: *"Thresholds are calibrated per camera at the p33/p67
of a calibration period, and recorded in the corpus manifest. A threshold in
absolute units describes the view, not the road."*

`relabel_corpus.py --calibrate` pooled every clip into **one** threshold pair,
and its help text called that "ADR-017's rule". The script had implemented half
the decision, and the half it implemented contradicted the half it had not.

### What pooling costs, measured

| camera | p33 | p67 | zero share |
|---|---|---|---|
| 4K Road traffic | 0 | 1 | 64% |
| Mumbai Andheri | 4 | 9 | 0% |
| Pov_Thursday | 4 | 9 | 8% |
| South Extension | 8 | 18 | 9% |
| video1 | 13 | 19 | 0% |
| **pooled** | **0** | **3** | 41% |

The pooled p67 is 3; video1's **p33 alone is 13**. Under pooled thresholds the
busy cameras never see LOW and the quiet one never sees HIGH — each camera gets
a truncated label alphabet, decided by where it sits relative to the others.

| labelling | train | test |
|---|---|---|
| §14.1 defaults | 83.5 / 12.9 / 3.5 | degenerate |
| pooled | 57.2 / 19.2 / 23.6 | degenerate |
| **per camera** | **59.2 / 26.0 / 14.7** | **25 / 50 / 25** |

Per-camera calibration is the first labelling that leaves **all three classes
present in every split**, including the one-sequence test split.

### The fix

`--calibrate` now calibrates per camera, labels each clip with its own
boundaries, and records `thresholds_by_clip` plus `threshold_scope` in the
manifest — a corpus that does not say which scope produced it cannot be
compared with one that does. `--calibrate-global` is kept only as the
comparison arm for the sign-off.

### The cost, which belongs in the paper

Per-camera thresholds make HIGH **relative to the camera's own range**. A lane
that only ever holds zero or one vehicle has no congested state, and
calibration must not invent one — two vehicles on a free-flowing motorway is
not congestion however rare it is there.

So a quiet camera contributes **no HIGH examples**. That is the right
behaviour and still a cost: HIGH is then carried by a subset of viewpoints, and
its cross-camera generalisation is tested on fewer cameras than LOW's or
MEDIUM's. Report it beside the per-class results rather than leaving it to be
inferred.

A test pins this deliberately — `test_per_camera_calibration_cannot_invent_a_class_that_never_occurs`
asserts that a quiet lane yields **zero** HIGH, so a future change that
"fixes" the imbalance by manufacturing congestion fails loudly.

## P38 — installing CUDA made PPO twice as slow (2026-08-20)

**Status:** CLOSED · A regression introduced by [P32](#p32), caught by running
the simulation half after changing the training half

[P32](#p32) replaced the CPU-only torch wheel with a CUDA build, which was
right for MFSTNet. It also changed something nobody asked it to.

Stable-Baselines3 selects CUDA whenever torch can see a GPU. `train_ppo.py`
never named a device, so the day the wheel changed, PPO moved to the GPU — and
SB3 warns, in its own words, that this is the wrong call:

> You are trying to run PPO on the GPU, but it is primarily intended to run on
> the CPU when not using a CNN policy … the GPU utilization will be poor and
> the training might take longer than on CPU.

Measured on this machine over 8,192 timesteps with the real state shape
(16-dim, 12 discrete actions):

| device | time |
|---|---|
| **cpu** | **8.0 s** |
| cuda | 16.2 s |

**Twice as slow.** Nothing in the policy is convolutional: the observation is a
16-dim vector (PRD §13.1) and the network is two small dense layers, so
per-step kernel launch and host transfer cost more than the arithmetic saves.
At 500K timesteps across three arms that is roughly 25 minutes given away per
sweep.

### The part that matters more than the minutes

CLAUDE.md already said "PPO trains on laptop CPU" — and it did, **by accident**,
because the installed wheel could not do otherwise. The moment that accident
ended, the statement quietly became false and no result said so.

A benchmark run before the wheel change and one run after would have been
measured on different devices, and neither CSV recorded which. That is the same
class of defect as [P33](#p33)'s cache and [P32](#p32)'s training metrics: a
number whose meaning depends on a fact the number does not carry.

`device="cpu"` is now explicit, with the reason written beside it, and a test
asserts both — a bare pin invites a later reader to "fix" it. A companion test
asserts `train_mfstnet` still defaults to `auto`, since MFSTNet is the opposite
case and a hardcoded `cpu` there would silently give back the 12.6×.

### The simulation half still runs

Checked end to end after this session's changes, on SUMO 1.27.1 rather than the
1.19.0 the pins claimed before [P30](#p30): network build, demand generation at
all three regimes, PPO smoke training, and `benchmark.py --restat` re-deriving
the statistics from the committed CSV.

## P39 — three defects, one shape: a number that does not carry what it depends on (2026-08-20)

**Status:** CLOSED · A pattern, closed once, after fixing three instances of it

Three defects found today looked unrelated and were not:

| | the number | the fact it depended on and did not record |
|---|---|---|
| [P32](#p32) | `gate_mean` 0.53895 vs 0.54268, same config and seed | which device ran it |
| [P33](#p33) | cached features, same `preprocessing_hash` | whether TF32 was on |
| [P38](#p38) | benchmark mean wait | which device PPO trained on |

Each was fixed where it happened. None of those fixes stops the fourth
instance, and the fourth is the one nobody catches — the environment moved, the
result changed, and the result file cannot say so.

### What changed

`experiments/provenance.py` writes a sidecar beside a result file naming the
environment that produced it: git commit, Python, torch **version and build**
(`2.13.0+cpu` and `2.13.0+cu126` are the same version and cannot give the same
numbers), CUDA availability and device, **both TF32 flags**, and the versions of
every package a result depends on. Callers add what only they know — the device
actually used, the corpus read, the regime run.

Wired into every writer of a graded deliverable: `train_mfstnet.py`,
`train_baselines.py`, `benchmark.py`, `webster_sweep.py`. A parametrised test
asserts each still does, so a fifth result writer added later fails until it
joins them.

### Why a sidecar rather than columns

Existing result CSVs are committed graded deliverables (NFR-09/10). Adding
columns to them means rewriting files whose contents were produced by a run —
which is transcription, the exact thing NFR-09 forbids. A file beside them costs
nothing and rewrites nothing.

### Two things deliberately absent

No timestamp and no username. The question a sidecar is asked is *"are these two
results comparable?"*, and a field that always differs between two runs makes
the diff useless for answering it. A test asserts two records written moments
apart are **identical**.

### What this does not fix

The 27 result CSVs already committed have no sidecar and will not get one
retroactively — inventing an environment record for a run nobody observed would
be worse than having none. They are dated and the changelog says what the
environment was on those dates; that is the audit trail for anything before
today.

## P40 — nothing checked that a built corpus was internally consistent (2026-08-20)

**Status:** CLOSED · No defect found; the check that would have found one did
not exist

The unit tests cover each corpus component in isolation — window arithmetic,
labelling, splitting, lane assignment. Nothing checked **the artifact they
combined to produce**. Once a corpus is on disk, that is a different question,
and it is the one every downstream number rests on.

`scripts/audit_corpus.py` re-derives a corpus from its own more primitive files
and checks it against itself. It trusts nothing the builder recorded about its
own output.

### The check that matters most

**The label must sit where A15 says it does.** `label_index` has to equal
`start_index + (T−1) + horizon_s/step_s`, and the observed-to-label gap has to
come to `horizon_s` in wall-clock seconds.

An off-by-one there makes **every label in the corpus wrong** — the model would
train on a target 2 s ahead while the paper claims 60 s — and nothing else would
look unusual. A test in this change proves the point: shifting one label leaves
the row count, the split sizes and the class balance identical. There is nothing
else to notice it by.

### The real corpus passes

```
[  ok  ] label_index == start_index + 59 + 30
[  ok  ] the label frame is strictly after the last observed frame (A15)
[  ok  ] the observed-to-label gap is 60s in wall clock
[  ok  ] every label re-derives from counts.csv through the recorded thresholds
[  ok  ] no clip appears in more than one split (ADR-002)
[  ok  ] every window's label frame exists in counts.csv
[  ok  ] every clip has its own lane geometry (P26)
[  ok  ] every camera declares the same lane count
[  ok  ] counts.csv indices are contiguous from 0 for every clip
```

The one warning is [P31](#p31)'s known test-split degeneracy, which is a
property of a five-camera pilot rather than of the corpus builder.

### An auditor that only passes proves nothing

Each check was exercised against a corpus mutated to break exactly that
invariant. **All seven mutations were caught**, and the mutation suite is
committed so the auditor cannot decay into something that always passes:

| mutation | caught by |
|---|---|
| label shifted by one | the A15 arithmetic |
| one label flipped | re-derivation from counts |
| clip in two splits | the leakage check |
| label past the end | the A15 arithmetic |
| a clip loses its geometry | the P26 check |
| cameras disagree on lane count | the width check |
| a count row deleted | the contiguity check |

The audit is now a step in the documented pipeline, between `build_corpus` and
`build_cache`, and exits 1 so it can gate a run.

## P41 — three reported detector figures have no committed CSV behind them (2026-08-20)

**Status:** OPEN · Found while checking every number destined for the review deck

NFR-09 requires raw results as committed CSVs rather than summary tables. Three
figures the project quotes freely do not have one:

| figure | where it appears | actual source |
|---|---|---|
| IDD `0.7104` — the detector of record | [S17](#s17-result), DECISION-BRIEF, the review deck | changelog prose |
| TrafficCAM `0.5734` after distillation | S17 | changelog prose |
| `e_rickshaw` `0.4787` | S17, and quoted as a headline outcome | changelog prose |

The S17 run happened on Kaggle T4×2 and its per-class metrics were written into
the changelog by hand instead of into `experiments/results/`. The numbers are
almost certainly right — they were read off a real run — but "almost certainly
right" is the state NFR-09 exists to rule out, and it is the same standard this
log has applied to everything else.

### Two things this immediately broke

The HTML review deck closed with *"Every figure in this deck comes from a
committed CSV."* That was **false for three of its figures**, which is worse
than not making the claim. The claim is now accurate and those figures carry a
dagger naming the run log.

Separately, the deck's generalisation slide put BMD-45 and TrafficCAM — both
from the s15 detector — in one comparison row beside an IDD figure, and the only
CSV-backed IDD number belongs to **s14, a different detector**. A row that mixes
two models is exactly the failure the slide is about. The PowerPoint version
shows the two same-model numbers and moves IDD into the speaker notes with its
detector named.

### What closing it costs

Re-running the S17 evaluation to emit per-class CSVs is roughly three hours of
GPU time. That is worth doing before the paper quotes any of these numbers, and
it is not worth doing to finish a deck. Logged rather than done.

**Until then:** any of the three may be stated with its source named, and none
of them may be described as measured-and-committed.
