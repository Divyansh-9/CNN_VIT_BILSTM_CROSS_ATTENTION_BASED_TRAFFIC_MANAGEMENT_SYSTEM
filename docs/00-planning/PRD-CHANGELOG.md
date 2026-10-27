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

## P42 — every GPU run was aborting after it finished, and I called it a shell artifact (2026-08-20)

**Status:** CLOSED · Root cause found, fixed, and pinned by tests

`nn.LSTM(..., dropout=0.2)` on CUDA in **training mode** aborts the process at
teardown on this stack — torch 2.13.0+cu126, Python 3.14, Windows, sm_89 — with
`STATUS_STACK_BUFFER_OVERRUN` (`0xC0000409`). cuDNN allocates a dropout-state
descriptor that is not torn down cleanly.

`TemporalConfig` sets `dropout=0.2` with the BiLSTM on, so **every ablation
config except H** hit it, and so did every real training run:

```
train_mfstnet --device cuda   exit 127
train_mfstnet --device cpu    exit 0
```

### The part worth recording is how it was missed

**Everything succeeds first.** Training completes, the results CSV is written
and correct, the summary prints — then the process dies. What is left is a
non-zero exit code on a run whose output is perfectly good.

The first time it appeared in this session I wrote, in as many words, *"exit 127
is odd — probably a shell artifact after the run"*, and moved on. It was not an
artifact. Every GPU training run reported here as successful had been returning
failure, and the only reason the numbers are trustworthy is that the abort
happens after the write, which is luck rather than design.

It surfaced properly only because the **test suite** started returning non-zero
while printing nothing but passes — the same signature, in a place where a
non-zero exit is harder to shrug off.

### Narrowing it

| probe | result |
|---|---|
| bare CUDA tensor | clean |
| ResNet-50 on CUDA | clean |
| MFSTNet **construction** on CUDA | clean |
| MFSTNet **forward** on CUDA | abort |
| configs A–G | abort |
| **config H** (no BiLSTM) | clean |
| `TemporalEncoder` with BiLSTM | abort |
| `nn.LSTM(dropout=0.0)` | clean |
| `nn.LSTM(dropout=0.2)` | **abort** |
| same, `.eval()` | clean |

A single-layer LSTM aborts too, even though PyTorch ignores dropout there — so
it is the descriptor being allocated, not dropout being applied.

### The fix, and the two that were rejected

`TemporalEncoder` now stacks **single-layer LSTMs with an explicit `nn.Dropout`
between them**. That is precisely what PyTorch's built-in dropout does — output
of every layer except the last — so it is a workaround for a platform defect
rather than a modelling change, and a test holds it to that: given the same
weights with dropout inactive, the two forms agree **bitwise**, with an
identical parameter count.

| option | cost | verdict |
|---|---|---|
| disable cuDNN for the RNN | 66.1 ms/step against 5.9 — **11×** | rejected |
| set `dropout=0` on CUDA only | regularisation depends on the device | rejected outright — that is the [P39](#p39) defect class |
| **stacked LSTMs + explicit dropout** | 6.7 ms/step — **12%** of the LSTM step | adopted |

### Consequences

- `train_mfstnet --device cuda` exits 0. The full test suite exits 0.
- Parameter *names* changed (`rnn.weight_ih_l0` → `rnn_layers.0.weight_ih_l0`),
  so any MFSTNet checkpoint predating this will not load. None exists.
- Initialisation order changed, so seeded numbers move. `gate_capacity.csv` and
  `overfit_check.csv` were regenerated rather than left stale: the gate result
  holds across all three seeds — separation 0.243 / 0.235 / 0.188, same
  direction — and every ablation config still memorises the pilot sample with
  identical parameter counts.
- `gate_capacity.py` now runs all three seeds into one CSV, because the deck
  claimed a three-seed result while the committed file held one.

## P43 — the IDD baseline S17 was judged against does not reproduce (2026-08-20)

**Status:** OPEN · Found by trying to close [P41](#p41) rather than accept it ·
**Bears on a pending decision**

[P41](#p41) logged that three detector figures existed only as changelog prose.
One of them — IDD `0.7104` for `s15_yolov8s_joint_aug`, the detector of record —
could be re-measured here, because those weights are on disk. So it was.

| measure | value |
|---|---|
| mean over all 7 evaluated classes | **0.6130** |
| mean over the 5 vehicle classes | 0.6984 |
| Ultralytics' own `all` row | 0.6130 |
| **claimed in the changelog** | **0.7104** |

**It does not reproduce under any of them.** `experiments/results/s15_metrics_idd.csv`
is now committed: 1,170 images, 11,536 instances, per class.

For context, the previous detector `s14` scores **0.6174** on the same split —
so on this measurement s15 is very slightly *worse* on IDD than its predecessor,
not 0.09 better.

### Why this matters more than a wrong number

[S17](#s17-result) rejected the TrafficCAM-augmented detector on **criterion 4**:

> IDD fell **0.7104 → 0.6188**, a drop of 0.0916 against a 0.02 tolerance — 4.6×
> over.

The baseline in that sentence is the figure that does not reproduce. Against
the measured 0.6130, an S17 value of 0.6188 would be a **rise of 0.0058**, and
criterion 4 would have **passed** rather than failed by 4.6×.

That would flip the verdict on an arm that also took `e_rickshaw` from 0.000 to
0.4787 — the class the project exists to detect.

### What is and is not established

- **Established:** s15 scores 0.6130 on IDD test, committed, reproducible.
- **Established:** the 0.7104 baseline in the S17 entry is wrong or was measured
  some other way, and the entry does not say which.
- **Not established:** S17's own IDD figure of 0.6188. It is prose too, and its
  weights were never downloaded from Kaggle, so it cannot be re-measured here.
- **Therefore not established:** whether criterion 4 passed or failed.

### What follows

The S17 verdict is **suspended, not reversed**. Reversing it on one re-measured
half of a comparison would repeat the mistake that created this — deciding from
a number nobody can reproduce. Both sides have to be measured the same way,
which needs the S17 weights fetched from Kaggle or the arm re-run.

Until then the decision brief's IDD-scope item carries this, and no table
anywhere states the −0.0916 delta without saying it is unverified.

> **The habit that found it.** P41 was logged as "worth doing before the paper,
> not worth doing to finish a deck", and that was nearly the end of it. Closing
> a third of it took eleven minutes of evaluation on weights that were already
> on disk, and it turned up a result that changes a pending decision. Deferring
> a check is a decision too, and it should be re-examined whenever the cost
> estimate was a guess.

---

## P44 — an automatic lane centre sat above the horizon, counting sky (2026-08-21)

**Status:** CLOSED · Found by doing the lane review the pipeline was waiting on ·
**Justifies the review gate on stronger grounds than the one it was built for**

`data/lanes_reviewed/` did not exist, so `build_corpus.py` refused every build
and the whole model track — corpus, cache, S28, S29, **M5** — was stalled behind
it. The step is placing four points on twelve preview images.

Doing it found this. On `Pov_Thursday_Traffic__182ecf5e`, k-means had put
`lane_1` at **(0.43, 0.28)** — the horizon on that camera is near y=0.38, so the
centre was **in the sky**. Nearest-centre assignment is disjoint by
construction, so the lane was not empty: it was collecting far-field haze
detections from the vanishing point and reporting them as vehicles in a lane.

**Nothing downstream would have raised.** The lane has counts. The counts vary
over time. The labels derived from them look ordinary, and every validation gate
in `audit_corpus.py` passes on a distribution that is entirely artefact.

### Why this is a stronger argument than P23

[P23](#p23) established that automatic centres are **unstable** — they moved
0.164 of frame width when the detector changed — and that is why
`build_corpus.py` refuses `reviewed: false`. P23 is an argument about variance.

This is an argument about correctness: a centre that is not on the road at all.
Stability would not have caught it, because a centre in the sky is stable. Only
looking at the preview catches it, which is precisely what the gate demands and
what had not been done.

### What changed

- Centres placed on all twelve surveyed cameras; all four on this camera now sit
  below y=0.46, on road surface. Every camera clears the 0.05 separation check
  (tightest 0.221, widest 0.424).
- `import_lane_centres.py` gained `--reviewer`, recorded verbatim in every file.
  `reviewed: true` asserts *a human looked*; it did not say **who**, so a
  placement nobody on the team made could read as one somebody did.
- **The current twelve are recorded as placed by the assistant and NOT confirmed
  by a team member.** They unblock the pipeline; they are not a signed review.
  R1 opening the twelve previews closes this properly.

---

## P45 — triage admits footage on length, and length is anti-correlated with traffic (2026-08-21)

**Status:** CLOSED as a gate · **OPEN as a project risk** · Found by asking why
the corpus was small after it was finally buildable

`triage_footage.py` sets `mechanically_ok = long_enough and scene_moves and
steady`. None of those three says the road carries vehicles, and nothing between
triage and `build_corpus` checked. Measured over the surveyed footage:

| clip | seconds | det/frame | triage verdict |
|---|---:|---:|---|
| Highway sounds (US interstate) | 3602 | **7.1** | PASS |
| 4K road tracking (SE Asia) | 2093 | **2.8** | PASS |
| M6 Motorway (UK) | 2048 | 23.4 | PASS |
| Road traffic recognition | 2048 | 21.2 | PASS — duplicate of M6, [P22](#p22), r=0.981 |
| Dhaka Rampura | 1206 | 19.4 | PASS |
| Dhaka Rampura 🎧 | 1170 | 31.5 | PASS |
| Relaxing highway (Alpine) | 840 | 12.9 | PASS |
| Pov Thursday (Dhaka) | 497 | 29.8 | PASS |
| Mumbai Andheri | 349 | 29.7 | **reject: 349s<360** |
| 4K free download | 306 | 14.6 | **reject: 306s<360** |
| Delhi South Extension | 264 | **66.6** | **reject: 264s<360** |
| Dhaka roundabout (video1) | 183 | **64.4** | **reject: 183s<360** |

**The four densest cameras are all rejected on length, and three of the four
longest survivors are empty roads.** The 2093-second clip that passes averages
2.8 vehicles per frame. Triage was selecting against the target domain, and the
`MIN_USABLE_S = 360` threshold is not wrong — it is A15, and a shorter clip
genuinely yields fewer windows — it is simply insufficient on its own.

### The gate

`corpus_yield.py` gained `--min-density`, default **15.0 detections per sampled
frame**, which is PRD §14.1's MEDIUM→HIGH boundary. A camera whose *mean* frame
does not reach that boundary cannot show sustained HIGH congestion. Per-camera
percentile calibration does not rescue it — percentiles will manufacture a HIGH
class out of an empty road, and every label in it is noise.

Density and [P17](#p17)'s unassigned-rate gate are reported as **separate**
reasons: [P25](#p25) established that a camera can fail the second for having
the wrong lane *count*, which is a few clicks to fix, and collapsing the two
would hide that. Six tests in `tests/test_density_gate.py`.

The principle was already in the codebase and had never been generalised —
`build_corpus.py` excludes Bellevue by default at 0.73 det/frame against a 9.88
reference, noting *"a wrong count becomes a wrong LABEL, which is worse than no
data at all."*

### The risk this leaves open

Seven usable cameras of eleven distinct. At `step_s=2`: **152 overlapping
sequences, 28 independent segments, 5.4× inflation.** At the PRD's own
`step_s=5`: **12 independent segments from 4 cameras.**

Twelve of the 28 come from Dhaka Rampura — one junction, filmed twice. **No
available clip is both long enough and dense enough except that one junction.**
An A–H × 5-seed ablation over 28 segments split 60/20/20 by camera is
underpowered, and reporting it without saying so is the cherry-picking PRD
§2.5.5 forbids.

This is the honest answer to *"what is blocking the project"*: not an unstarted
step, but a corpus that no amount of pipeline work enlarges. The one input that
moves 28 upward is **two or three long fixed-camera recordings of dense
traffic** — a narrowed [S19](../../BUILD-LOG.md), not the 60 sessions ADR-006
cut.

---

## P47 — a 3,000-step smoke run and a 500,000-step training run wrote to the same filename (2026-08-21)

**Status: fixed.** `scripts/train_ppo.py`, `tests/test_checkpoint_guard.py`.

`train_ppo.py --smoke` exists so that a long run which fails at 80% has not cost
a day. It runs 3,000 timesteps instead of 500,000 — the same code path at 0.6%
of the length — and then saved its weights to

```
models/ppo/ppo_{arm}_{regime}{suffix}_seed{seed}.zip
```

which is byte-identical to the path the full run uses. A `.zip` records weights.
It does not record how long they were trained for, and nothing beside it did
either.

### Why this is not hypothetical

Earlier the same day a checkpoint dated **16 August** was nearly reported as the
output of a run started **21 August**, on nothing but a filename. The file was
not wrong; the question "which run produced this" simply had no answer on disk.
A smoke run overwriting a full one produces the same ambiguity with worse
consequences: the 30-seed benchmark (S38) evaluates whatever `.zip` it finds, so
an unnoticed overwrite means every PPO number in the paper was measured on a
model trained for 0.6% of its specified budget, and no artifact would say so.

### The fix, which the repository had already written once

`train_mfstnet.py` refuses to let a short verification run overwrite
`ablation.csv` when a longer run wrote it, and offers `--force` to whoever means
it. That rule was never applied to model weights. It is now:

* every checkpoint gets a `.zip.provenance.json` sidecar recording `timesteps`,
  `smoke`, arm, action space, regime, seed, episode length, **and the device**
  — [P38](#p38) pinned PPO to the CPU deliberately, and the sidecar is where a
  benchmark can verify two arms were measured on one device;
* a run whose `timesteps` is lower than the recorded run's **refuses**, naming
  both numbers, because "refused" without them sends the reader looking for
  which run they just protected;
* equal lengths proceed — re-running the same length is a reproducibility check
  (NFR-07), not a mistake;
* the check runs **before** the environment is built, not after training.
  Discovering at the end of an hour that the result cannot be written has
  already cost the hour.

### The case that will be hit most often

**A checkpoint with no sidecar at all.** Every one of the twelve checkpoints in
`models/ppo/` predates this and is in that state. Their length is unknown, so
they cannot be compared, and the guard refuses rather than guessing. That is
deliberately inconvenient: it is the same condition that produced the 16-August
confusion, and silently overwriting is what let it happen.

Eight tests. The last one pins a detail that would have been easy to get wrong —
`Path.with_suffix` turns `x.zip` into `x.provenance.json`, dropping `.zip` and
breaking the association between sidecar and checkpoint for anything sorting or
globbing them, so the sidecar keeps the full name.

---

## P46 — the gates that decide whether a corpus can carry a result ran only on synthetic data (2026-08-21)

**Status:** CLOSED as a wiring defect · **OPEN as the finding it exposed** ·
Found by building the first real multi-camera corpus, [P44](#p44)

`mfstnet/corpus/validation.py` holds `validate_corpus`, and with it the gates
that decide whether a corpus can carry a *result*: split balance, effective
sample size, transition rate, class distribution. **Its only caller was
`scripts/demo_pipeline.py`** — the end-to-end demo, which runs on synthetic
data.

The auditor that runs on a real corpus, `scripts/audit_corpus.py`, checks a
different and narrower question: internal consistency ([P40](#p40)) — is the
label where A15 says, does it re-derive from the counts, is any clip in two
splits. Every one of those is necessary and none of them asks whether the
corpus can support a claim.

**So the corpus that actually trains the model got the weaker of the two
checks, and the stronger set only ever ran on data nobody would publish.**

### What it was hiding

The first real corpus — 153 sequences, 7 cameras, built 2026-08-21 — passes
every consistency check. Running the corpus-level gates on it for the first
time:

```
[ warn ] split_balance: train 55 (36%) · val 35 (23%) · test 63 (41%)
         — 'train' is 24% off target
[ warn ] effective_sample_size: test split draws on 1 clip(s) — this is the
         effective n, not the sequence count
[  ok  ] transition_rate: 174 of 612 lane-windows change class (28.4%)
```

**The test split is one camera.** Splits are assigned by hashing the clip id,
which balances clip *count* and says nothing about clip *size*; with seven
cameras ranging from 1 to 63 sequences, the single largest landed alone in
test. Every confidence interval on M5 would have had an effective n of **1**,
and the bootstrap resamples clips, so no number of sequences rescues it.

Worse than the arithmetic: that one camera is **M6 Motorway, the only
non-South-Asian camera in the corpus.** The model would have trained on Dhaka,
Mumbai and Delhi and been tested exclusively on a UK free-flow motorway. The
transition rate of 28.4% — healthy, and consistent with the 31.0% [S06](../../BUILD-LOG.md)
measured — would have made the corpus look fine.

Dropping M6 does not fix it. Re-simulating the assignment over the remaining
six cameras gives **22 / 38 / 40**, with 20 training sequences. Hash assignment
is lumpy below ~60 clips and `check_split_balance`'s own docstring already says
the fix is more clips, not a different splitter.

### What changed

- `audit_corpus.py` now runs `check_split_balance`,
  `check_effective_sample_size` and `check_transition_rate` on every real
  corpus, as advisories. A skewed split does not make results wrong; it makes
  them unrepresentative, and blocking would stop work that should continue with
  the caveat attached.
- Four regression tests in `tests/test_audit_corpus.py` pin the wiring, so the
  gates cannot be silently unhooked again.

### The finding that stays open

Combined with [P45](#p45), this is the arithmetic that answers *"what is
blocking the project"*:

| | |
|---|---|
| independent segments, `step_s=2` | **28** |
| of which from one junction (Dhaka Rampura, filmed twice) | **12** |
| effective n of the test split | **1** |
| in-domain cameras after the density gate | **6** |

**No pipeline work changes any of these numbers.** The corpus is built, audited
and reproducible, and it cannot support an A–H × 5-seed ablation whose result
would survive review. The one input that moves them is two or three long
fixed-camera recordings of dense traffic.

---

## P52 — the `no-forecast` and `surrogate` PPO arms are the same environment (2026-08-21)

**Status: open. This is a design decision, not a patch.**

ADR-009 defines three arms and they are supposed to differ only by config:

> `no-forecast` — the 16-dim state with indices 11-14 zeroed. The honest floor.
> `surrogate` — a SUMO-derived congestion proxy in 11-14, standing in for the
> forecast so the RL half is not blocked on the vision half.

`simulation/configs/ppo_config.yaml` sets `use_mfstnet: false` for **both**, and
`traffic_env.py` branches on `use_mfstnet` exactly once — to raise
`NotImplementedError` because live MFSTNet is Phase 3. Nothing anywhere writes
a proxy into indices 11-14.

So the two arms produce **byte-identical observations**, and:

* the arms cannot be compared, because there is nothing to compare;
* a 30,000-step run trained today under the name
  `ppo_surrogate_saturated_keep_or_switch_seed42.zip` was a `no-forecast`
  policy. It has been deleted — a filename asserting something the contents do
  not support is the [P47](#p47) failure with a different field;
* the config's own note describes behaviour that does not exist, which is worse
  than a gap, because it reads as a specification of something already built.

### Why it went unnoticed

Both arms *train*. Both converge. Both write plausible checkpoints. The
difference between them is four numbers that are zero in both cases, and no
assertion anywhere compares one arm's observations with another's.

### What has to be decided, not just written

The proxy is not a formality. ADR-009's whole claim is that a *forecast-shaped*
input can stand in for MFSTNet while the vision half is unfinished, and that
claim only holds if the proxy has the same **failure profile** as the real
thing, not merely the same shape. A proxy read straight from SUMO's future
state is an oracle: PPO trained against it learns to trust a forecast that is
never wrong, and swapping in a model whose cross-camera macro F1 is what this
corpus supports would then be a *regression* the benchmark cannot anticipate.

A defensible proxy needs, at minimum, a stated accuracy target it is degraded
to, and that target has to come from a measured MFSTNet number. Which means
**the surrogate arm is blocked on S28/S29 after all** — the opposite of what
ADR-009 assumed when it introduced the arm to unblock the RL track.

That is the finding. The arm was created to decouple two halves of the project
and it cannot do so honestly, because calibrating the proxy requires the number
the other half has not produced yet.

## P53 — a zeroed forecast is indistinguishable from "every lane is clear" (2026-08-21)

**Status: partly fixed.** The contract digest is in; the encoding is not.

`spec.yaml` maps the three congestion classes through `mfst_pred_divisor: 2`,
so `{LOW, MEDIUM, HIGH}` becomes `{0.0, 0.5, 1.0}`. Indices 11-14 are zeroed
when the forecast is unavailable (FR-A06), and `traffic_env`'s docstring says
this "states 'no forecast'".

It does not. **`0.0` is LOW.** The declared fallback tells the policy that all
four approaches are predicted clear — the most optimistic forecast the encoding
can express — at precisely the moment the forecast has failed. A policy that
learned to shorten green on a LOW forecast will do exactly that when MFSTNet
dies.

Two things follow, and they are separable:

**The encoding is wrong and the fix is cheap.** Reserving `0.0` for "absent" and
mapping the classes to `{1,2,3}/3` costs one normaliser change, keeps the
dimension at 16, and needs no PRD amendment beyond the divisor. It removes the
ambiguity outright rather than adding a flag to compensate for it.

**The fallback is off-manifold and the fix is not cheap.** Even unambiguous,
a zero block the policy never saw during training is an input it has no learned
response to. Making the fallback in-distribution means training with forecast
dropout, which changes what every arm measures and so belongs in an ADR with
the arm definitions, not in a patch.

### What is fixed today

`simulation/contract.py` hashes the part of the spec that decides what a state
number *means* — index map, dimension, normalisers, fallback index list — and
`train_ppo.py` writes that digest into each checkpoint's provenance sidecar
beside the timesteps [P47](#p47) records.

The length of the state vector was already guarded: `traffic_env` refuses to
build if `spec.yaml`'s `dim` disagrees with its `STATE_DIM`. The change that
costs more keeps the length. Permute two entries in the index map, or halve a
divisor, and every shape still matches while the policy acts on a feature that
no longer means what it did while it learned to read it. Nothing raises.

An **absent** digest is refused rather than waved through, for the same reason
P47 refuses a checkpoint with no recorded length: every checkpoint written
before today is in that state, and that is exactly the condition that lets a
policy be scored against a state it never saw.

The action space is deliberately not hashed — ADR-015 is screening two against
each other, so a difference there is an intended comparison, and the filename
already carries which one ran. Twelve tests, pinning what the digest must
*notice* rather than its literal value: a test asserting a fixed digest would be
updated in the same commit as the mistake it exists to catch.

---

## P54 — the ablation was measuring the seed, not the architecture (2026-08-21)

**Status: fixed.** `scripts/run_loco.py` gained `--seeds`, and the summary
carries `macro_f1_seed_spread`.

Fold 0 of the first leave-one-camera-out ablation returned configs **B** and
**E** identical to four decimal places — same macro F1, same QWK, same accuracy,
and on inspection the same confusion matrix, cell for cell:

| | B (ViT-only) | E (bidir, no gate) |
|---|---|---|
| macro F1 | 0.4469 | 0.4469 |
| trainable params | 922,883 | 1,973,763 |
| epochs run | 25 | 21 |

Two architectures of different size, trained for different numbers of epochs, in
different wall-clock times, producing the same 140 predictions. That is either a
config defect — E silently falling back to the ViT branch — or a coincidence.

### It was a coincidence, and the check found something worse

Re-running both at seeds 1 and 7 separated them immediately, so there is no
config defect. But it exposed how little the seed-42 numbers were worth:

| config | seed 42 | seed 1 | seed 7 | spread |
|---|---|---|---|---|
| B | 0.4469 | 0.4860 | 0.4777 | **0.039** |
| E | 0.4469 | 0.2385 | 0.2046 | **0.242** |

**Config E's spread across seeds is six times config B's, and larger than the
distance between most pairs of configs in the table.** Its QWK is *exactly*
0.0 at seeds 1 and 7 — the signature of a model that has collapsed to a
constant predictor, which on a fold whose test camera contains no HIGH window
(ADR-019) is an easy local minimum to fall into.

A single-seed ablation over this corpus does not rank architectures. It ranks
initialisations. PRD §14.4 has always specified **A–H across five seeds**;
`run_loco.py` was written with `--seed 42` and would have produced a table that
looked like a result.

### Every number above was measured before P55, and none of them is safe

[P55](#p55) found that a cached window was a view into a memory map nothing kept
alive. It did not always crash — sometimes the pages were still intact when they
were read — so the runs that *completed* returned numbers computed on memory
that may or may not still have held the features.

That includes the table above. Re-running config A after the fix gave **0.3424**
where the pre-fix run gave 0.3408, and config C gave 0.2109 where it gave
0.2088; config B gave 0.4469 both times. Some reads were fine and some were not,
which is exactly what a use-after-free looks like when it does not fault.

**So the evidence for this entry is provisional.** The finding it rests on —
that seed-to-seed movement can exceed the distance between two configs — is not
in doubt as a *risk*, because the fix for it (report the spread, run five seeds)
is correct whether or not these particular numbers were. But the specific
figures are withdrawn, and the clean five-seed run now in flight either
reproduces them or does not. Whichever it does gets recorded here.

### The fix, and the part of it that matters

`--seeds` now takes a list, defaulting to `[42]` so a quick look stays quick,
with §14.4's five fixed as `42 1 7 13 21` — fixed rather than drawn, so a rerun
is a rerun (NFR-07). Fold views are trained once per seed and the per-run CSVs
are named `fold{k}_seed{s}.csv`.

The reported column is the one that stops this recurring:
**`macro_f1_seed_spread`** — how far a config moved on *one fold* when only the
seed changed, averaged over folds. Fold-to-fold movement is a different
quantity and is deliberately not folded into it. When the largest spread exceeds
the closest gap between two configs, `run_loco.py` prints that those two are not
separated by the table, rather than leaving a reader to rank rows that are noise
apart.

A single seed leaves the column **blank rather than 0.0**. One seed has not
measured a spread of zero; it has not measured one at all, and `0.0` would read
as "this config is stable".

### Also, a self-inflicted crash worth recording

The first four-fold run died after fold 0 with exit `3221225477`
(`0xC0000005`, access violation) — because the B-versus-E seed check above was
run on CUDA *while the ablation was running*, on a 6 GB card. Not
[P42](#p42)'s `0xC0000409` cuDNN teardown abort, and not a defect in either
script: two CUDA training processes on this GPU is one too many. Verification
runs go on the CPU or wait.

---

## P55 — every cached window was a dangling view into a released memory map (2026-08-21)

**Status: fixed.** `mfstnet/cache.py`, `tests/test_cache_aliasing.py`.

Training segfaulted. Exit `3221225477` on Windows, `139` under the shell — an
**access violation**, in several threads at once, with no Python frame in the
faulthandler dump. It happened on CPU and CUDA alike, on every ablation config,
at a point in the first epoch that moved between runs.

### The bug

[P29](#p29) made `read_window` memory-map the clip file so a 60-frame window
could be sliced without materialising a 1,000-frame clip. The window was then
returned as:

```python
cnn[window].to(dtype).unsqueeze(0)
```

`Tensor.to(dtype)` is a **no-op that returns `self`** when the tensor already
has that dtype. The cache stores fp16. So a caller asking for fp16 received a
**view into the memory map**, and `payload` — the only reference keeping that
mapping alive — went out of scope the moment `read_window` returned.

Every window handed to the trainer pointed at memory that had been released.
Whether it crashed depended on when the collector ran and when the pages were
reclaimed, which is why it moved around.

### Why it appeared only now

It was invisible for as long as callers asked for **fp32**, because widening
copies. [P35](#p35) then changed the training path to request fp16 — correctly,
to halve what `torch.stack` copies and what crosses the bus — and turned every
cached window into a dangling view. Two fixes, each right on its own, that
compose into a use-after-free.

The fix is `.to(dtype, copy=True)`, which materialises the window whatever the
dtypes are.

### Three wrong diagnoses, recorded because they cost the most time

1. **"Concurrent CUDA jobs."** The first crash happened while a verification
   run was on the GPU, so contention looked sufficient. It crashed again with
   the card idle.
2. **"Memory accumulated across the eight ablation configs."** Nothing released
   a model between configs, which was true and worth fixing, but a single
   config in a fresh process crashed too.
3. **"Peak host memory per batch."** Available RAM did fall to 2.4 GB while one
   batch was resident, which is genuinely tight. Gradient accumulation cut peak
   memory fourfold and it still crashed.

Each was plausible, each was consistent with the symptom, and each was wrong.
What settled it was that a repro reading all 153 windows straight from the cache
**passed** — and that repro called `read_window` without a `dtype`, taking the
fp32 default. The difference between the passing repro and the crashing trainer
was one keyword argument.

### What else this invalidates

The bug did not always fault. When the mapped pages happened to survive until
the read, the run completed and produced a number — computed on memory the
process no longer owned. So **every MFSTNet result measured between P35 and this
fix is provisional**, whether or not it crashed:

* the fold-0 ablation table quoted in [P54](#p54), and the three-seed B-versus-E
  comparison that entry is built on;
* the 2-epoch smoke figure recorded when the leave-one-camera-out pipeline was
  first exercised.

Re-running config A after the fix gave 0.3424 against 0.3408 before, and config
C 0.2109 against 0.2088, while config B gave 0.4469 both times. Some reads were
intact and some were not, which is the signature of a use-after-free that does
not fault.

Nothing outside MFSTNet is affected: the detector, the corpus counts, the SUMO
baselines and the PPO arms never read the feature cache.

### How much it actually moved, measured

Fold 0 seed 42 has now been re-run cleanly through all eight configs, against
the same fold and the same seed as the withdrawn table:

| config | pre-fix | post-fix | delta |
|---|---|---|---|
| A | 0.3408 | 0.3424 | +0.0016 |
| B | 0.4469 | 0.4469 | 0.0000 |
| C | 0.2088 | 0.2109 | +0.0021 |
| D | 0.2385 | 0.2385 | 0.0000 |
| E | 0.4469 | 0.4469 | 0.0000 |
| **F** | **0.4045** | **0.4992** | **+0.0947** |

One config moved by **0.095** — larger than the distance between most pairs of
configs in the table, and enough to reorder them.

**The right reading of this table is narrow.** It shows that the fault was
material. It does **not** show that the other five numbers were sound, and the
distinction is the whole point: a use-after-free is a property of a *run*, not
of a config. Those five re-ran close to their old values because their reads
happened to land on pages that were still intact — one scheduling accident away
from having been the exception, and nothing in the artifact distinguishes the
two cases.

So the admissibility rule is not "withdraw the ones that moved". It is:

> **No number measured between P35 and this fix is admissible, because the fault
> is silent and run-dependent.**

The deltas are evidence for that rule, not a shortlist of survivors. Stating it
the other way round — five stable, one bad — invites the obvious question of why
the five were not kept, and the answer would have to be that they cannot be
shown to be sound either.

### What the clean numbers show so far

On this one fold and seed — one camera, one initialisation, so not yet a
result — **H, the linear probe, reaches 0.4710 against the full model's
0.4977**. A22 added H precisely because a frozen-backbone paper is expected to
report the floor, and a 0.027 gap between "mean over time plus a classifier" and
the full gated architecture is the kind of finding §2.5.5 requires to be
reported rather than quietly dropped. Whether it survives four folds and five
seeds is what the run in flight decides.

### Kept from the wrong turns

Two changes came out of the false diagnoses and are kept on their own merits,
not because they fixed anything:

**Class weights no longer read the feature cache.** Computing the label
distribution went through `Windows.__getitem__`, pulling every training window's
features through the cache — for one fold, 108 windows of `[60, 2048, 7, 7]` —
materialised, counted, and discarded before epoch 1 began. The labels are
columns in `sequences.csv`.

**`--micro-batch`, default 8, with accumulation to the config's `batch_size`.**
`batch_size` is PRD §8.2 and is not negotiable; how many windows are resident at
once is not a hyperparameter. Seven tests hold it to that, and the weighting is
the part worth testing: each micro-batch's loss is a mean over its own windows,
so summing the means over-weights a short final group. `train_mfstnet` sums
`loss * windows` and divides the accumulated gradient by the windows actually
seen. One test demonstrates that the naive version **does** move the gradient,
so the weighting is not ceremony.

**Models are released between ablation configs**, and `run_loco.py` now runs one
config per process. The second is what removes the failure mode; the first only
makes it less likely.

---

## P56 — configs B and E agreed to four decimals, and it was not a dead flag (2026-08-22)

**Status: not a defect. Guard added.** `tests/test_configs_are_distinct.py`.

On fold 0 seed 42, config **B** (ViT only) and config **E** (bidirectional
cross-attention, no gate) returned identical macro F1 (0.4469) and identical QWK
(0.3429). Two architectures agreeing to four decimal places is not what "similar
performance" looks like — floating-point noise alone should separate them in the
third — so the obvious reading is a **dead flag**: `mode` or `use_gate` wired to
nothing, or to a module that is a no-op under the other settings.

That is the [P26](#p26) shape, where shapes agree, loss falls, and nothing
raises. It would silently delete a row from the ablation: eight configs on the
page, seven experiments behind it.

### Checked statically, in minutes, rather than with five seeds

The temptation was to run more seeds. Five seeds would have returned five
identical pairs and an invitation to report equality as a finding. The question
is about *computation*, and computation is checkable directly:

| | B | E |
|---|---|---|
| `fusion.mode` | `none` | `bidirectional` |
| `use_cnn` / `use_vit` | False / True | True / True |
| trainable parameters | 922,883 | 1,973,763 |
| logits on identical input | \multicolumn{2}{c}{**differ, max abs 0.055**} |

**The flag is wired.** What coincides is the `argmax` — and every metric in the
table is computed from the argmax. At initialisation both models are flat enough
for the predicted class to agree on all 140 lane-windows while the logits behind
them do not.

### Why this needed a test rather than a note

Comparing metrics cannot detect a dead flag, because metrics are exactly where a
dead flag hides. The guard therefore compares **logits across every pair of the
eight configs** on one input, and fails if any two are bitwise equal. Four tests,
one of which pins the counter-intuitive part: matching metrics do not imply
matching computation, so the metric-level coincidence stays legal and only the
computation-level identity is an error.

### What it leaves open

Two architectures converging on the same decision function is still worth
noticing. On fold 0 the test camera contributes no HIGH window (ADR-019), so the
effective problem is two-class over 140 predictions, and a corpus that easy is
one where architecture stops mattering. That is a statement about the corpus,
not the code, and it belongs with the other three pointing the same way —
see [ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md).

---

## P57 — the ablation cannot bear on control, because HIGH barely exists in it (2026-08-22)

**Status: open. This is a corpus and threshold finding, not a code defect.**

Fold 0's test camera has **62 LOW, 78 MEDIUM and 0 HIGH**. Checking the other
three folds before the suite finished — a five-minute query that decides whether
four hours of GPU time are worth waiting for:

| fold | test camera | lane-windows | LOW | MEDIUM | **HIGH** | HIGH share |
|---|---|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | 140 | 62 | 78 | **0** | 0.0% |
| 1 | M6 Motorway | 252 | 150 | 82 | **20** | 7.9% |
| 2 | Pov footover bridge | 44 | 27 | 8 | **9** | 20.5% |
| 3 | Dhaka Rampura (b) | 136 | 49 | 86 | **1** | 0.7% |

**Thirty HIGH lane-windows across all 572.** Two of the four folds are
effectively binary tasks with a dead output head, and a third has 44 windows in
total. Only fold 1 carries meaningful HIGH support — and its *training* split
holds 9 HIGH in 316 (2.8%) before being tested on 20.

### Why this is the finding rather than a caveat

A signal controller does not act on the LOW/MEDIUM boundary. **HIGH is the class
the entire downstream system exists to respond to.** An ablation that cannot
separate architectures on HIGH cannot bear on the project's actual claim,
however many configs and seeds it runs.

So the eight-config table measures LOW-versus-MEDIUM discrimination on most
folds. That is a real result about a real task, and it is **not** the task the
PRD's control chapter needs.

### The absent-class convention is now load-bearing on the numbers themselves

`macro_f1` divides by three classes and scores an absent one 0 by convention
([P31](#p31)). With HIGH absent it **caps mechanically at 0.667**. So fold 0's
0.4977 is roughly **three-quarters of what was reachable**, not half of 1.0, and
a reader who does not know the convention will misread it by a wide margin.

Two things follow, and both are fixed today:

* `run_loco.py` now derives and reports **`macro_f1_ceiling`**,
  **`macro_f1_present_mean`** (the mean over classes that actually occur) and
  **`test_high_share`** beside every config, and warns when the ceiling is
  below 1.0 or when HIGH falls under 5% of a fold's test split;
* both are **derived from the per-run CSVs**, which already carry `f1_*` and
  `support_*`. Adding columns to `metrics.py` mid-suite would have left half the
  fold files with one header and half with another.

[ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md)'s material threshold
of 0.05 was stated in the three-class-with-zeros convention and corresponds to
roughly **0.075** in a present-classes-only metric. A pre-registered threshold
whose meaning depends on an unfixed convention is not pre-registered in any
useful sense, so the convention is now stated explicitly in both documents.

### What is *not* being done about it

**The thresholds are not being recalibrated to produce more HIGH.** ADR-017 sets
them in Indo-HCM PCU and they are pre-registered and awaiting the guide.
Adjusting them until the class balance looks better is fitting the labels to the
desired outcome, and it is the exact failure [P45](#p45) already warned about:
per-camera percentile calibration will manufacture a HIGH class out of an empty
road.

**The running suite is not being stopped.** It still measures the seed spread
that [P54](#p54) needs re-measured on clean data — already at **0.1853** on the
clean runs in hand, against the withdrawn 0.242, so the same order of magnitude
and the same conclusion. It still measures LOW/MEDIUM discrimination, and it
still exercises the protocol. What it cannot do is support a claim about
congestion severity.

### Where this actually points

Not at the ablation, and not at the architecture. At the **corpus**: four of
eleven cameras were already excluded for averaging under 15 detections per frame
(P45), and of the seven that remain, the two densest contribute almost no HIGH
under the current thresholds. This is the same conclusion P45 reached from a
different direction, and it strengthens the case in the
[Part B memo](MEMO-2026-08-22-part-b.md) — a decision about which dataset to
build should be made knowing that the current one cannot express the class the
system acts on.

---

## P58 — the MFSTNet evaluation contains no Indian camera, and a UK motorway dominates it (2026-08-22)

**Status: open. This is the binding problem, and it outranks everything in
[P57](#p57).**

The four cameras eligible to be a leave-one-camera-out fold (ADR-019) were
inspected by looking at their footage, rather than by reading their filenames:

| fold | camera | country | viewpoint | lane-windows | HIGH |
|---|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | Bangladesh | footbridge over a junction, mixed traffic | 140 | 0 |
| 1 | **M6 Motorway** | **United Kingdom** | **bridge over a divided motorway** | **252** | **20** |
| 2 | Pov, footover bridge | Bangladesh | footbridge over a divided highway, mixed | 44 | 9 |
| 3 | Dhaka Rampura (b) | Bangladesh | footbridge over a boulevard, mixed | 136 | 1 |

Across the whole corpus:

| | fold-eligible cameras | sequences | lane-windows | HIGH |
|---|---|---|---|---|
| Bangladesh | 3 | 80 | 320 | 10 |
| **United Kingdom** | **1** | 63 | **252 (41%)** | **20 (53%)** |
| **India** | **0** | 9 | 36 (5.9%) | 7 |

### The three things this says

**There are no Indian cameras in the evaluation.** India's three clips — Mumbai
Andheri, South Extension Delhi, and one unlabelled — contribute **9 sequences of
153**, all below ADR-019's ten-window eligibility bar, so all three sit in
`always_train` and none is ever tested. The project's premise is unstructured
*Indian* traffic. The forecaster is evaluated on Bangladesh and Britain.

**The dominant fold is the premise's counterexample.** The M6 is a divided
motorway: enforced lane discipline, no junction, no auto-rickshaws, no mixed
traffic, no pedestrians. It is 41% of the evaluation corpus and **53% of every
HIGH label in the project**. A reader who reaches "M6 Motorway" in a table
captioned as Indian traffic stops reading there, and every refinement downstream
of it — the quantum, the aggregation order, McNemar, the ceiling column —
becomes irrelevant at that moment.

**It got in by a gate, not by a decision.** The M6 passed P45's density gate at
23.4 detections per frame and P17's unassigned-rate gate, and nothing in the
pipeline asks what country a camera is in or whether its traffic is structured.
Both gates are correct and neither is sufficient. **Long and clean is not the
same as representative**, which is the same lesson P45 learned about duration
and is now repeating about geography.

### The trade this creates, which the guide has to see

Dropping the M6 for domain coherence costs **53% of the HIGH windows** and
leaves exactly **three** eligible cameras — ADR-019's bare minimum, with no
margin.

**Domain coherence and HIGH support are in direct conflict, and the M6 is
simultaneously the cause of the first problem and the source of the second.**
That is not a trade an implementer should make quietly.

### What was checked, and what it ruled out

* **"Pov" is not a dashcam.** It is a *footover bridge* — a pedestrian
  overbridge — looking down a divided highway with auto-rickshaws,
  cycle-rickshaws, buses and trucks, with Bangladeshi signage. Elevated, mixed,
  and the correct viewpoint. The abbreviation misleads; the footage does not.
* **Dhaka-a and Dhaka-b are not the same camera.** Near-identical titles from
  one uploader, but the frames show different scenes — a junction with a police
  box, against a divided boulevard past South Point School. `group_cameras`
  separated them correctly at 0.2457 similarity. They remain *correlated*: one
  city, one road corridor, one uploader, and that is worth stating even though
  it is not leakage.

### Why this is not an implementation task

No amount of statistics fixes a corpus whose evaluation set excludes the country
in the project's title. The options — re-frame the claim as **South Asian
unstructured traffic**, drop the M6 and accept three folds, or re-select clips
for Indian footage — are all scope decisions, and the third changes what capture
would be commissioned. It is added to the
[Part B memo](MEMO-2026-08-22-part-b.md) **above** the HIGH finding, because it
changes the framing question before the density question is even reached.

### The distinction the memo must draw explicitly

Refusing to move ADR-017's thresholds stands. But **changing the sample is not
the same act as changing the ruler**:

* selecting footage for the presence of congestion, or for geography, is
  **sampling design**, declared in advance and reported;
* moving thresholds until the class balance improves is **fitting labels to a
  desired outcome**.

The guide will otherwise hear both as "you adjusted things until HIGH appeared",
and only one of them is that.

---

## P59 — the finest-grain artifact is now written unconditionally (2026-08-22)

**Status: fixed.** `scripts/train_mfstnet.py`, `scripts/discordance.py`,
`tests/test_discordance.py`.

[ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md)'s Q2 needs the
per-window decisions behind each metrics row, and they were never written. **A
metrics row is a view over those decisions and no aggregate can be
un-aggregated** — the only route back is to retrain, which is measured in GPU
hours against a file of a few hundred integers.

Every run now writes `<stem>_<config>.predictions.csv`: one row per test
lane-window carrying clip, start index, label index, lane, true, predicted and
correct. **Not behind a flag.** A flag is a decision made before the question is
known, and the question is never known in advance — Q2 was not a question when
this suite was designed.

The correspondence between the flat prediction list and the windows it names is
**asserted, not assumed**: `evaluate_split` iterates with `shuffle=False`, so
window `i` contributes `len(lanes)` consecutive entries in lane order, and a
count mismatch refuses rather than writing a file that looks right and describes
the wrong windows.

### The reproduction check, which cannot be skipped

Predictions may come from runs made after a metrics table was published. If
seeding or determinism has drifted even slightly, Q1 and Q2 would describe
**different models**, and a discordance count computed from them would not be
about the published table.

`discordance.py` therefore **re-scores every predictions file and compares it
against the committed row** for the same config, fold and seed before computing
anything. Any mismatch refuses the whole run and writes no output — a failed
check must not leave a result behind, because a discordance count from
unverified predictions is worse than none: it looks like evidence.

Twelve tests. Two worth naming: the CLI must write **nothing** when
verification fails, and a re-score differing by exactly one unit in the fourth
decimal is **allowed** — the committed CSVs round to four places, so a guard
that fired on that would fail on every honest reproduction.

McNemar's `p` is emitted under the column name
`mcnemar_p_INDEPENDENCE_VIOLATED`, tested as such. A `p`-value whose assumption
is broken must not be reachable under a name that reads as ordinary.

### What it changes about the plan

ADR-022 costed Q2 at 40 re-runs of G and H. With predictions written by every
run, **Q2 costs nothing extra** — it is computed from artifacts the suite
already produces, for every config pair rather than one.

## P60 — the suite died twice to the machine sleeping, and the second time was my fix being half a fix (2026-08-22)

**Status: fixed.** `powercfg`, and `run_loco.py --resume` behaviour.

The leave-one-camera-out suite has now been killed three times. Once by
[P55](#p55). Twice by the machine suspending: the wall clock jumped 10:48 →
18:06 the first time and 22:23 → 00:49 the second, and a suspend drops a local
CUDA context and a TraCI socket exactly the way both failures presented.

After the first, `powercfg /change standby-timeout-ac 0` was applied and
recorded as the fix. **It was half a fix.** `Win32_Battery.BatteryStatus`
reads 1 — discharging — so the laptop was on battery and `standby-timeout-dc`
still applied. All four of `standby-timeout` and `hibernate-timeout`, on AC and
DC, are now zero.

The wider lesson is not about power settings. **A four-hour unattended job that
starts from zero after any interruption will not finish on a laptop.** So
`run_loco.py` now skips a run whose artifacts already exist, and a run counts as
done only when **both** the metrics CSV and the predictions CSV are present — a
metrics row without its per-window decisions is precisely the state P59 exists
to prevent, so a half-written run is redone rather than kept.

The suite was restarted from scratch rather than resumed, because the thirteen
completed runs predate P59 and carry no predictions. Restarting at 8% complete
to gain a consistent artifact set across all 160 runs is a better trade than
carrying a split-format directory forward, and it removes ADR-022's 40 re-runs
entirely.

---

## P61 — the corpus now has to declare what it is, and the audit checks it against the claim (2026-08-22)

**Status: fixed.** `data/cameras.json`, `mfstnet/corpus/composition.py`,
`scripts/audit_corpus.py`, `tests/test_composition.py`.

[P58](#p58) found a British motorway supplying 41% of the evaluation corpus for
a project about unstructured Indian traffic. It was found by *looking at the
footage*, which is not a repeatable process and had already been skipped four
times.

The reason nothing caught it is structural: **P45's density gate and P17's
unassigned-rate gate select for usability, and usability is not
representativeness.** The M6 is long, clean and dense, so it passed both. Nobody
chose it.

### The check nothing else performs

> The paper claims a domain. Does the **evaluation set** contain that domain?

`audit_corpus.py` now **FAILS** — not warns — when no fold-eligible camera
matches the declared target. A model tested only on cameras outside its claimed
domain has not been evaluated on its claim, and no statistic computed downstream
repairs that. Run against the four folds today it fails all four, which is the
correct answer:

```
fold0  [ FAIL ] the test split contains the claimed domain (Bangladesh 1)
fold1  [ FAIL ] the test split contains the claimed domain (United Kingdom 1)
fold2  [ FAIL ] the test split contains the claimed domain (Bangladesh 1)
fold3  [ FAIL ] the test split contains the claimed domain (Bangladesh 1)
```

It also warns when one off-target camera supplies more than half the evaluation
**by window**, because counting cameras and counting windows answer different
questions — three Bangladeshi cameras against one British one is three-to-one by
camera and closer to even by window, and the second is what the model saw.

### Declared, never inferred

Nothing here can be read off a filename, so `data/cameras.json` declares country,
city, viewpoint and traffic type per camera — and records **how each was
determined**. `frame` means the footage was inspected; `filename` means it was
not, and those entries are marked provisional. `video1` is `unknown` throughout
rather than guessed: **an assumed attribution is worse than an absent one,
because it would silently satisfy this check.**

`is_on_target` returns a third answer, `None`, for exactly that case. An unknown
camera is not evidence for the claim and not evidence against it, and folding it
into either is the guess the module exists to prevent.

### The escape hatch is a diff, not a flag

There is no `--allow-domain-mismatch`, because a flag would be used. To make the
check pass, either change the corpus or **change the declared claim** — and both
are version-controlled and visible in review. If the guide re-frames the paper as
*South Asian unstructured traffic*, widening `target_domain.country` to include
Bangladesh makes three folds pass and **still fails the M6**, which is exactly
right. That behaviour is pinned by a test.

An **absent** registry is a different situation from a camera missing from one —
the project has not adopted the check rather than failed it — so it warns loudly
instead of passing quietly.

Thirteen tests, plus three in the audit suite. Two of the existing audit tests
broke on this and were fixed by giving their synthetic corpora a registry rather
than by disabling the check, so they exercise the real path.

---

## P62 — three questions answered before writing any more code (2026-08-22)

All three could have changed what code was worth writing, and all three were
hours rather than days. They are recorded together because the answers only mean
something jointly.

### 1. Are Dhaka-a and Dhaka-b the same junction? — **No.**

Near-identical titles from one uploader, and [P58](#p58) checked one mid-frame
each. Checked again at several timestamps: **Dhaka-a is a junction** — an open
crossing with a police box, a pink bus, buildings in red banners. **Dhaka-b is a
divided boulevard** with a raised central median and lamp posts, past South
Point School & College.

Different road *geometry*, not one junction from two angles: a junction viewed
from elsewhere is still a junction. They remain correlated — one city, one
corridor, one uploader — which is a caveat, not leakage.

**Why it was decisive.** If they were one camera, dropping the M6 would leave
**two** eligible cameras and leave-one-camera-out would stop meaning anything.
They are two, so option A below leaves three — ADR-019's bare minimum.

### 2. Does BMD-45 ship sequences? — **No, and the arithmetic is not close.**

BMD-45 is on-target in every respect that matters: Bengaluru CCTV, elevated,
mixed Indian traffic, CC BY 4.0, faces already blurred, and **already in this
project**. If it shipped continuous video the corpus problem would be solved
with no capture, no institutional permission, no blurring pipeline, no DPDP
exposure and no waiting on a decision. It was worth more than the remaining runs
to check.

It is **isolated still images**, and its authors sampled them for *"spatial and
temporal diversity"* — the deliberate opposite of a sequence. No timestamps, no
ordering, filenames are anonymised numeric IDs. Confirmed against the dataset
card rather than the abstract, which matches what
[ADR-016](decisions/ADR-016-two-phase-corpus.md) recorded from the Hub API.

The arithmetic settles it independently of any of that: **45,986 images over
3,679 cameras is about 12.5 frames per camera**, and A15 requires **90
consecutive observations** — T=60 at 2 s spacing plus a 30-step horizon — for a
single window. Even if every one of a camera's frames were consecutive, it is
seven times short.

**There is no free route to Indian sequences in data already held.**

### 3. Are the domain problem and the class problem separable? — **No.**

Fixing the domain means dropping the M6. Dropping the M6 removes 44% of the
windows and 20 of 30 HIGH labels, leaving about **10 HIGH corpus-wide** — the
three-class task then does not exist rather than being underpowered. Keeping
HIGH estimable keeps a British motorway as the majority of the evaluation.

And **dropping the M6 does not make the corpus Indian; it makes it
Bangladeshi**, which collapses the options rather than expanding them:

| option | folds | lane-windows | HIGH | domain |
|---|---|---|---|---|
| A — re-frame to South Asian, drop the M6 | 3 | 320 | 10 (3.1%) | coherent |
| B — re-frame to South Asian, keep the M6 | 4 | 572 | 30 | still incoherent |
| C — obtain Indian footage | — | — | — | the only route to the claim as written |

Option B is not a middle ground: it keeps A's domain problem to buy C's class
support. The memo now presents A and C together as one decision, because
approving the domain fix this week and discovering the class collapse next week
is the failure mode of presenting them in sequence.

## P63 — a reversal, recorded as one (2026-08-22)

[P59](#p59) argued against restarting the leave-one-camera-out suite: Q2 needed
only G and H, so it cost 40 re-runs rather than 160, and restarting would
discard runs already paid for.

**Two hours later the suite was restarted from scratch**, discarding thirteen
runs. Both statements are in the same day's history and the second contradicts
the first, so the reason is written here rather than left to be inferred:

* the suite had **died anyway** ([P60](#p60)), so there was no running job to
  protect — the choice was what to restart with, not whether to restart;
* per-run predictions had since been added, so a fresh run produces them for
  **all 160 runs** rather than 40, making Q2 free and complete;
* the thirteen completed runs predated that and carried none, so keeping them
  meant a directory in two formats.

The original argument was right when it was made and stopped being right when
the job died. **A decision that flips gets written down as a flip**, with what
changed — otherwise the record reads as drift, and the next reader cannot tell a
reconsideration from a lapse.

---

## P64 — every scope claim is now an assertion the paper cannot be built over (2026-08-22)

**Status: fixed, and two asserted claims currently fail.**
`docs/00-planning/CLAIMS.yaml`, `scripts/check_claims.py`,
`tests/test_claims.py`.

[P61](#p61) turned one question into a gate: *the paper claims a domain — does
the evaluation contain it?* The question is not specific to geography. Viewpoint,
traffic type, class coverage, camera count and licence releasability are each a
sentence a reviewer can check, each a place the project can be caught, and each
checkable against artifacts already on disk.

So each is written in `CLAIMS.yaml` **as the sentence it would appear as in the
paper**, with the assertion that decides whether it is true. What is being
claimed is legible without reading any code, which is the property that makes
the file worth keeping honest.

### What it says today

```
[ FAIL ] domain: We evaluate on unstructured Indian traffic.
         4 of 4 fold(s) have no on-target camera in test.
[  ok  ] viewpoint: All footage is from a fixed elevated viewpoint.
         no camera is known to be non-elevated, but 3 have an undetermined
         viewpoint — the claim rests on fewer cameras than it appears to
[ FAIL ] class_coverage: We report three-class congestion per lane.
         below 10 support in test: fold0:HIGH=0, fold2:MEDIUM=8,
         fold2:HIGH=9, fold3:HIGH=1
[  ok  ] camera_count: The evaluation covers at least four independent cameras.
[ note ] releasable: The corpus and everything derived from it can be released.
         7 of 7 camera(s) carry a licence that does not permit release
```

Three things in that output were not known before it ran.

**`fold2:MEDIUM=8`.** [P57](#p57) established that HIGH was thin. It is not only
HIGH — fold 2's *MEDIUM* class has eight windows. A generic check found what a
question aimed at one class did not.

**`camera_count` passes at exactly four**, so dropping the M6 for the domain
claim flips it to failing. The coupling [P62](#p62) describes in prose is now
mechanical: the two claims cannot both hold on this corpus, and the registry
says so without anyone remembering to.

**Every camera's licence is unresolved.** The corpus is built from third-party
YouTube uploads, and ITD v1.2 — which supplies the detector that counted them —
is CC BY-NC 4.0. Nothing derived is releasable until that is settled. It is
recorded as **aspirational** rather than asserted, which is the honest status
and keeps it visible without blocking work that does not depend on it.

### Asserted blocks, aspirational reports, and promotion is a diff

A claim cannot drift from intended to stated without someone editing the file,
and the edit is reviewable. That is the whole mechanism: there is no flag, and
the only way to make a failing assertion pass is to change the corpus or change
the claim.

**An unknown checker fails rather than being skipped.** A claim naming a
function that does not exist would otherwise pass by default, which is the
quietest way for an assertion to stop asserting.

### A defect found by its own tests

`check_claims.py` had a helper named `test_windows`. Importing it into a test
module made **pytest collect it as a test**, which then errored on a missing
fixture. A production function with a `test_` prefix hijacks the collector the
moment anything imports the module. Renamed to `windows_in_test_split`, with the
reason in its docstring so it is not renamed back.

---

## P65 — the fourth death was the battery, not the sleep timer (2026-08-22)

**Status: mitigated, and partly not fixable from here.**

The leave-one-camera-out suite has now been killed four times. [P55](#p55) once,
idle suspend twice ([P60](#p60)), and this:

```
22-08-2026 01:17:39   Id 109   The kernel power manager has initiated a shutdown transition
22-08-2026 06:00:45            Hypervisor successfully started
```

All four idle timeouts were already zero, on AC and DC, and `powercfg /lastwake`
reports no wake event. The machine did not idle-sleep — it **shut down at
01:17**, and `Win32_Battery.BatteryStatus` was 1 (discharging) at the time and
is 2 (on AC) now. **The battery ran out.** Nothing in P60's fix addressed that,
because P60's fix was about idleness and this was about power.

### What was changed, and what deliberately was not

Lid-close on AC is now *do nothing*, which removes one more way to lose a run
while plugged in.

**The critical-battery action is left alone.** Setting it to "do nothing" would
let the machine run to a hard power cut with a training process holding open
files, and losing an unattended run is a far cheaper failure than losing a
filesystem. It stays at hibernate.

So this one is not fixable from inside the repository: **an unattended
multi-hour run needs the laptop on mains.** That is an operating instruction,
not a code change, and it is written here because three of the four deaths were
diagnosed as something more interesting than they were.

### The change that did survive it

P60 added resume. This is the first death where that mattered: eleven completed
runs, both artifacts each, are skipped on restart rather than repeated. The
suite picks up where it stopped instead of returning to zero for the fourth
time.

That is the real lesson from the sequence, and it is not about power settings.
**On hardware that dies unpredictably, resumability is worth more than any
individual fix for any individual cause of death** — each cause was different,
each fix was correct, and none of them would have prevented the next one.

---

## P66 — the Q2 path verified on real artifacts, and what it says so far (2026-08-22)

**Status: tool verified. The numbers below are partial and are not a result.**

`discordance.py` had only ever run on synthetic fixtures. Run against the real
committed artifacts for configs G and H:

```
  reproduction check passed for G and H
  G vs H over 2 run pair(s), 280 lane-windows
  different predictions: 26 (9.29%)
  G right / H wrong: 15
  H right / G wrong: 4
  McNemar exact p = 0.01921   <- INDEPENDENCE VIOLATED
```

**The reproduction check passing is the part that matters here.** Every
predictions file re-scored to the macro F1, accuracy and QWK in its committed
metrics row, so the per-window decisions describe the same models the table
describes. That was the [P59](#p59) guard's whole purpose and it had never been
exercised on anything but fixtures.

### What the numbers are, and what they are not

**Fold 0 only, two of five seeds, one camera — the one with no HIGH window at
all.** They are recorded because a verification run produced them and hiding a
number a tool printed is the habit this changelog exists against, not because
they support anything.

What they do show is that **G and H are not decision-identical**: they disagree
on 26 of 280 lane-windows, and the disagreements are asymmetric — G right where
H is wrong 15 times against 4 the other way.

That is precisely the situation [ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md)
split Q1 from Q2 to detect. Q1 over four fold means is expected to return
"cannot distinguish"; Q2 already shows the two models decide differently. Had
they been named primary and fallback, the temptation would be to report Q2's
`p = 0.019` and stop. **They answer different questions, and Q2's `p` still
cannot support a generalisation claim** — 280 windows from one camera, sharing
54 of 60 frames with their neighbours, are nothing like 280 independent
observations.

The number that bears on the architecture is Q1, over four cameras, and it does
not exist yet.

---

## P67 — the ablation table is withheld, not captioned, while the corpus fails its claims (2026-08-22)

**Status: fixed.** `scripts/make_paper_tables.py`, `tests/test_paper_tables.py`.

The leave-one-camera-out ablation is running to completion and its numbers
**cannot enter the paper**, whatever they say: [P58](#p58) leaves no on-target
camera in any fold and [P57](#p57) leaves HIGH at 0/20/9/1. They are a real
measurement of something. They are not the measurement the paper claims to
report.

A caption saying so is not enough. **Eight numbers in a rendered table get
pasted into a draft three weeks later with the caveats stripped**, and the
caption is the first thing to go.

So `make_paper_tables.py` now declares which claims each table depends on and
**does not render** one whose claims fail:

```
  ablation   NOT RENDERED — the corpus fails 2 asserted claim(s):
             domain: 4 of 4 fold(s) have no on-target camera in test
             class_coverage: fold0:HIGH=0, fold2:MEDIUM=8, fold2:HIGH=9, fold3:HIGH=1
             A caption cannot stop these numbers being pasted into a draft.
```

The control table still renders. It is SUMO — no camera, no domain, no class
support — so gating it on the corpus would be a guard that cries wolf, and that
is pinned by a test.

Exit 1 when any table is withheld, so a paper build cannot step over it.

## P68 — a third coupling: the domain problem and the licence problem have one solution (2026-08-22)

**Status: open. It is the guide's decision and it changes the arithmetic.**

[P62](#p62) coupled two problems: fixing the domain drops the M6, which destroys
the HIGH class. There is a third, and it was recorded in
[P64](#p64)'s registry before its consequence was drawn.

**Every camera in the corpus carries an unresolved licence** — twelve
third-party uploads with nothing declared — and the detector that counted them
is ITD v1.2, **CC BY-NC 4.0**. Nothing derived from this corpus is releasable.
That was true before P58 and is independent of it.

**So the domain problem and the licence problem have the same solution and the
same cost: the corpus has to be re-sourced either way.** Re-sourcing was one
option among three. It is now the only one that fixes both, which changes what
capture is worth and therefore changes the recommendation in the
[Part B memo](MEMO-2026-08-22-part-b.md).

### A reversal, recorded as one

The memo previously recommended **cutting Part B** as the cheapest thing to
drop. That was right when the alternative was eleven usable cameras. With
**zero** on-domain fold-eligible cameras it is not, and the memo now says so in
its own text rather than leaving the guide to reconcile two recommendations.

The recommendation that survives is still the other branch — **change the claim,
not the corpus** — because with placements running, re-sourcing is weeks that do
not exist. What is defensible today is the benchmark, the protocol, and the
audit apparatus; those are not blocked on data nobody has.

## P69 — closed: Dhaka-a and Dhaka-b are not the same camera (2026-08-22)

Asked three times, answered twice, so it is recorded as **closed** with the
evidence rather than re-examined a fourth time.

Frames were inspected at 15% and 85% of each clip, not one mid-frame:

| | Dhaka-a | Dhaka-b |
|---|---|---|
| road form | open junction, vehicles crossing | divided boulevard, raised central median |
| landmarks | police-box sign, pink bus, red-bannered buildings | South Point School & College, WALTON signage |
| resolution | 1920×1080 | 3840×2160 |

Different road **geometry**, which is the part a viewing angle cannot change: a
junction seen from elsewhere is still a junction. `group_cameras` separated them
at 0.2457 similarity against a 0.80 threshold.

They remain correlated — one city, one corridor, one uploader — and that is
stated as a caveat, not called leakage.

**Consequence, which is why it kept being asked:** dropping the M6 leaves
**three** eligible cameras, not two, so leave-one-camera-out remains a protocol
at ADR-019's minimum rather than collapsing.

---

## P70 — dropping the M6 makes an already-powerless test resolve nothing (2026-08-22)

**Status: quantified and pre-registered.**
[ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md) amended.

[P62](#p62) said dropping the M6 costs the HIGH class. Two consequences were
stated as directions rather than figures, so they are computed here.

### The class is gone, not thinned

Dropping the M6 leaves three Bangladeshi cameras, ~320 lane-windows and **10
HIGH — nine of them inside Pov's 44-window fold.** HIGH would exist in **one
fold of three**. A class present in one fold is not estimable, so the collapse
to **binary (LOW vs MEDIUM+HIGH)** stops being an option and becomes forced.

The trigger is declared now, before the suite lands, on **support** grounds —
support is a property of the data, known before any metric — and it already
fires: *if any class has fewer than 10 test windows in more than one fold, the
reported task is binary.*

### The test loses what little power it had

| | n = 4 | n = 3 |
|---|---|---|
| `t_crit` two-sided 0.05 | 3.182 (df 3) | 4.303 (df 2) |
| minimum detectable difference | 1.591 × sd | **2.484 × sd** — 56% larger |
| at the measured seed spread 0.185 | 0.294 | **0.460** |

**0.460 is larger than the entire config table span**, which runs 0.211 to 0.499
on fold 0 — a range of 0.288. The test could not separate the best architecture
from the worst.

At n=4 it is already 0.294, which *is* the span. This is not a cliff at three
cameras; **the fold-level test resolves essentially nothing at four**, and
dropping the M6 makes it 56% weaker still.

### The honest description of the surviving branch

> Three cameras, one country, two classes, a test with no power, and a negative
> result reported as a negative result.

Defensible and publishable as a **benchmark-and-protocol** paper. **Not a
forecasting contribution.** The guide is shown it in those terms in the memo,
rather than as "we narrowed the scope", because those are different things and
only one of them is true.

## P71 — the control table renders, and its central comparison does not exist (2026-08-22)

**Status: fixed in the caption.**

[P67](#p67) correctly left the control table ungated: it is SUMO, so no corpus
claim bears on it. But **rendering is not meaning.** The table compares
`fixed`, `longest_queue` and `webster` — and contains **no learned controller at
all**, because [P52](#p52) leaves the surrogate arm unimplemented and
[ADR-021](decisions/ADR-021-forecast-quality-as-a-swept-variable.md)'s oracle run
has not gone.

A green table beside a withheld one reads as *"control is done, vision is not"*
to anyone who does not count the rows. The caption now says the opposite in the
table's own words, generated from its contents rather than remembered:

> No learned controller appears in this table: it compares the fixed-time
> baselines only. The PPO arms are unimplemented (P52) and the oracle bound of
> ADR-021 has not been run, so the comparison this table exists for is not yet
> answered.

The sentence disappears automatically once any learned arm appears in the CSV,
which is pinned by a test — a caveat that has to be removed by hand is a caveat
that outlives its reason.

## P72 — the outreach that should have been sent a week ago (2026-08-22)

**Status: drafted, not sent.** `docs/00-planning/OUTREACH-2026-08-22.md`.

[P62](#p62) established there is no route to an on-domain corpus from data
already held. It did not follow the obvious next step: **BMD-45's stills were
sampled from continuous recordings, and somebody has those recordings.**

BMD-45 is on-domain in every respect — Bengaluru Safe City CCTV, elevated fixed
viewpoint, mixed Indian traffic, CC BY 4.0, faces blurred, already cited here.
The *only* barrier is ~12.5 frames per camera against the 90 consecutive
observations a window needs. If even five or six cameras' worth of 15–20 minute
clips can be released, that closes **both** [P58](#p58)'s domain problem and
[P68](#p68)'s licence problem at once, with no capture, no permission chain, no
blurring pipeline and no DPDP exposure.

Two emails, batched with the TrafficCAM licence request that has been owed since
that dataset was assessed — and both asked the same third question: *any pointer
to continuous elevated Indian footage.*

**Timing is the whole point.** Replies take days. A mail sent today can inform
the guide's 29 August decision; a mail sent after it can only reopen a decision
already made. This is twenty minutes of work with a chance of removing the
project's binding constraint entirely, and it does not compete with placement
preparation.

Recorded as a defect rather than a task because the omission has a shape:
**every constraint in this project was treated as fixed until it was measured,
and this one was never even asked about.**

---

## P73 — the count baselines, measured across all four folds (2026-08-22)

**Status: measured.** `experiments/results/baselines_loco/`.

PRD §14.3's count-sequence baselines existed as a script and had never been run
against the leave-one-camera-out folds. They are the number MFSTNet has to beat,
and they are **not blocked by anything in [P57](#p57), [P58](#p58) or
[P68](#p68)** — counts are junction-invariant, which is the observation
[ADR-023](decisions/ADR-023-separate-the-two-claims.md) is built on.

Four folds, seed 42, macro F1:

| count model | mean | fold 0 | fold 1 | fold 2 | fold 3 |
|---|---|---|---|---|---|
| GRU | **0.5682** | 0.437 | 0.551 | 0.780 | 0.505 |
| **naive last-value** | **0.5571** | 0.449 | **0.692** | 0.673 | 0.414 |
| LSTM | 0.5385 | 0.405 | 0.579 | 0.780 | 0.390 |
| XGBoost | 0.4691 | 0.433 | 0.574 | 0.461 | 0.408 |

### The naive baseline is the story

**"The same as now" is the second-best model in the table and holds the best
single number in it** — 0.692 on the M6 fold. PRD §14.3 predicted this: over a
60-second horizon on a signal this autocorrelated, last-value is strong. It is
now measured rather than assumed, and **any claim about a learned forecaster has
to clear 0.557**, not zero.

A learned GRU beats it by 0.011 on the mean, which is inside the seed spread.

### What must not be read from this yet

On fold 0 seed 42, MFSTNet's config G scores **0.4977** against the best count
model's **0.449** — MFSTNet ahead. That is tempting and it is not evidence:

* one fold, one seed;
* it is the fold whose test camera has **no HIGH window**, so it is a two-class
  problem — precisely where the count models' structural advantage has least
  room to show. A32: on auto-labelled data a count model observes the exact
  variable the label is computed from, so it should win *by construction*, and a
  fold where it does not is a fold where that construction is weakest;
* the comparable numbers arrive when the suite finishes all four folds.

Recorded because a run produced it. Not reported as a finding.

### Why this was worth running today

It is **C1's evidence** under ADR-023, and C1 is the half of the project that is
not waiting on a corpus, a licence or a decision. Running it converted "the
controller half is fine" from an assumption into four folds of numbers, while
the vision half waits.

---

## P74 — twelve checkpoints of unknown length were sitting where the benchmark looks (2026-08-22)

**Status: fixed by archiving, not deleting.** `models/ppo/_pre_p47/`.

[P47](#p47) added provenance sidecars to PPO checkpoints. Twelve checkpoints
predate it, and **none records how many timesteps it trained for** — a `.zip`
stores weights, not training length.

They were still in `models/ppo/`, which is where `screen_action_space.py` and the
30-seed benchmark load from. A checkpoint of unknown length silently scoring a
benchmark is precisely the failure P47 exists to prevent, and the one that nearly
had a 16-August file reported as a 21-August result.

Moved to `models/ppo/_pre_p47/` with a README stating why. **Archived rather
than deleted** because they are the only artifacts of several days of runs;
**moved rather than left** because a guard that refuses them is worth less than
their not being in the path at all.

`assert_compatible` already refuses them on two counts — no recorded timesteps,
and no observation-contract digest — so this is defence in depth rather than the
only line. To use one, retrain it: cheaper than establishing what it is.

### And the run that should have happened days ago

With the archive clear, the **500,000-step `no-forecast` arm** is training. It
had died three times ([P60](#p60), [P65](#p65)) and its checkpoint on disk was
still dated 16 August.

It runs on the **CPU** by [P38](#p38)'s deliberate pinning, so it does not
contend with the ablation on the GPU — measured at 74% utilisation with both
running. That is the practical value of P38's decision, which was made for
comparability rather than for scheduling: **the RL half and the vision half can
progress at once.**

Under [ADR-023](decisions/ADR-023-separate-the-two-claims.md) this is C1's
evidence, and C1 is the half not waiting on a corpus, a licence or a decision.

---

## P75 — I ran the count baselines at one seed, one document after saying not to (2026-08-22)

**Status: fixed.** `experiments/results/baselines_loco/` now holds 4 folds × 5
seeds.

[P54](#p54) established that a one-seed table ranks initialisations rather than
architectures, and put `--seeds 42 1 7 13 21` in `run_loco.py`, in CLAUDE.md and
in PRD §14.4's own words. [P73](#p73) then reported the count baselines from
**one seed**, and quoted their means as if they were stable.

The mistake is not the numbers — they barely moved. It is that the standard was
written down and then not applied to the next thing measured, which is how a
standard becomes decoration.

### What five seeds say

| count model | mean | seed spread | fold 0 | fold 1 | fold 2 | fold 3 |
|---|---|---|---|---|---|---|
| GRU | **0.5663** | 0.034 | 0.428 | 0.557 | 0.780 | 0.500 |
| **naive last-value** | **0.5571** | **0.000** | 0.449 | **0.692** | 0.673 | 0.414 |
| LSTM | 0.5405 | 0.063 | 0.434 | 0.575 | 0.780 | 0.373 |
| XGBoost | 0.4691 | 0.000 | 0.433 | 0.574 | 0.461 | 0.408 |

**Naive and XGBoost show a spread of exactly 0.000.** Neither trains
stochastically, so that is the check that the seeding is real rather than
nominal — a five-seed table where *everything* moved would have meant the seed
was not reaching the model.

### The finding the extra seeds sharpen

**No learned count model reliably beats "the same as now."** The GRU leads naive
by **0.0092** against its own seed spread of **0.034** — the best learned
model's margin over doing nothing is **a third of the noise from re-running
it**.

At one seed that read as "GRU is best by 0.011". At five it reads as "nothing
here beats the naive baseline", which is a different sentence and the true one.

It is [ADR-023](decisions/ADR-023-separate-the-two-claims.md)'s C1 central
number, and it is a negative result that §2.5.5 requires be reported rather than
buried under a leaderboard ordering.

---

## P76 — an ADR declared it affects six requirements that do not exist (2026-08-22)

**Status: fixed, and made checkable.** `scripts/check_docs.py`,
`docs/00-planning/decisions/ADR-003-laptop-as-edge.md`, `CLAUDE.md`.

Checking whether the RTM had gone stale — it was last touched on 10 August while
fifteen ADRs landed — turned up two things, and **the one I expected was not
there.**

### What was not wrong

The RTM's coverage is **complete**: all 45 `FR-*`, all 13 PRD `NFR-*`, all 23
`BR-*`. The assumption that a 12-day-old join table must have holes in it was
wrong, and the measurement said so before any editing began.

### What was wrong

**CLAUDE.md's own rule did not match the repository.** It states that
`FR-*`/`NFR-*` are defined in PRD §9/§10. Three are not: `NFR-14`, `NFR-15` and
`NFR-16` are introduced by `docs/01-requirements/NFR.md`, which says so in as
many words — they are constraints the PRD implies without ever writing down as
verifiable requirements. NFR-15 and NFR-16 are cited as governing rules in
CLAUDE.md itself.

**A rule that does not match the repository is worse than no rule**: it invites
a defect report against documents that are correct, which is exactly what nearly
happened here.

**And ADR-003 cites a requirement range that no document defines.** Its
`Affects` row named six `FR-E` identifiers. The prototype requirements are
`FR-P01..FR-P04`. A reader tracing "what does the laptop-as-edge decision
change" hits nothing — the ADR has been unverifiable since 7 August.

### The check

`check_docs.py` now enforces traceability in **both** directions, and both have
already failed in this repository:

* **cited but undefined** — a document leans on an id and there is nowhere to
  look it up. This is how a requirement gets invented in prose and then treated
  as governing.
* **defined but absent from the RTM** — the RTM is the join table
  (BR → FR/NFR → DES → TC → M), so a requirement missing from it has no
  traceable test or milestone.

Stdlib only, so it runs in CI with the rest of `check_docs`.

### One deliberate strictness

The first correction to ADR-003 **still failed the check**, because the
correction note quoted the bad identifiers. The checker cannot distinguish a
citation from a historical mention — and neither can a reader copying from that
row. The note was rewritten to describe the range without spelling it, rather
than the check weakened to allow it.

### The bug in the checker itself

The pattern was written as `\b(...)\b` and reached the file as **two literal
backspace bytes** (`\x08`), so it silently matched nothing and reported "no
requirement ids found in any definition document". An `r"..."` prefix cannot
help once the byte is wrong. It is the same shell-escaping mangling that has
bitten this session repeatedly, and it is the reason the first run of a new
check must be read rather than trusted: **a checker that finds nothing looks
exactly like a repository with no problems.**

---

## P77 — two amendments were logged and never landed in the PRD (2026-08-22)

**Status: fixed, and made checkable.** `scripts/check_docs.py`, PRD §8.4 and
§13.1, `docs/01-requirements/SRS.md`.

CLAUDE.md's rule is:

> When implementation reveals the PRD is wrong, amend the PRD and log it in
> PRD-CHANGELOG — **never work around a PRD statement you believe is
> incorrect.**

The changelog half is easy to remember, because it is where the work happens.
**The PRD half was skipped twice in one day, by me.**

* [ADR-019](decisions/ADR-019-leave-one-camera-out-evaluation.md) declares it
  amends **PRD §8.4**. §8.4 still read `Split ratio | 60/20/20` with no note. A
  reader of the source of truth had no way to learn leave-one-camera-out exists.
* [ADR-020](decisions/ADR-020-forecast-staleness-channel.md) declares it amends
  **PRD §13.1**. §13.1 never mentioned it.
* `SRS.md` restated `MFSTNet uses 60/20/20 (PRD §8.4)` as current.

### What was written, and what deliberately was not

Both ADRs are **Proposed**. So the PRD now **points at** each proposal rather
than applying it: §8.4 marks the ratio superseded-pending and links ADR-019,
§13.1 says a 17-dimension change is proposed and *not* applied, and that the
section still describes the 16-dim contract `spec.yaml` implements.

Pre-applying a proposed amendment would be worse than not landing it: it would
put a decision in the source of truth that the guide has not made.

### The check

`check_docs.py` now fails when an ADR's header declares it amends a PRD section
and **the PRD never mentions that ADR**. Verified to fail by removing the
identifier from the PRD and watching it fire, then restoring — because
[P76](#p76) had just demonstrated that a new check which finds nothing looks
exactly like a repository with no problems.

It is deliberately **weak**: it asks only that the identifier appear somewhere
in the PRD, not that the surrounding prose be right. A stronger check would have
to understand the amendment, and a check nobody can satisfy is a check that gets
deleted.

### The same escaping bug, twice more

The pattern was first written with `\n` inside a character class and reached the
file as a real newline, breaking the string literal outright. Rewritten to match
**per line**, which needs no escape at all. Combined with P76's backspace bytes,
that is three regexes mangled by shell escaping in one session — the reliable
workaround is to build patterns without backslash escapes, using `chr()` where a
literal is unavoidable.

---

## P78 — the pre-registered test, written before the data (2026-08-22)

**Status: built and tested against synthetic folds. Not yet run for record.**
`scripts/gate_vs_probe.py`, `tests/test_gate_vs_probe.py`.

[ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md) fixed Q1's test, its
aggregation order, its power calculation and its material threshold before the
suite completed. **A pre-registration that leaves the analysis to be written
afterwards has left the analysis free**, so the code is now committed before the
data too — the commit that adds it precedes the commit that adds
`loco_summary.csv`, checkable in `git log`.

Eleven tests pin the three things that were fixed in advance:

* the **aggregation order** — seeds averaged within a fold, *then* differenced,
  *then* combined across folds. Differencing per seed and pooling gives the same
  mean and a different variance, which is the whole reason ADR-022 named an
  order;
* the **power calculation** — asserted against the figures ADR-022 quotes,
  1.591 × sd at n=4 and 2.484 × sd at n=3, so the document and the code cannot
  drift apart;
* the **verdicts**, including the one that exists to be refused: a null result
  prints `CANNOT DISTINGUISH` with the minimum detectable difference beside it,
  never "equivalent".

There is also a `SEPARATED BUT NOT MATERIAL` verdict, tested on a tiny but
consistent gap. At this n a significant result on a 0.02 difference is a
small-sample artifact before it is a finding, and the threshold exists so that
case has somewhere to go other than into the abstract.

### A dry run on the partial suite, which is not a result

Three of four folds, four of five seeds:

```
per fold             0:+0.0237  1:-0.2163  2:+0.0417
mean difference      -0.0503
min detectable diff   0.3579
VERDICT: CANNOT DISTINGUISH
```

**ADR-022's prediction holds so far**, which is the least surprising possible
outcome and was written down in advance for exactly that reason.

Two things worth noticing and not concluding from. The mean difference is
**negative** — the linear probe ahead of the full architecture across these
three folds — which is the opposite of the fold-0-only reading recorded in
[P73](#p73), and is why one fold was explicitly not treated as evidence there.
And **fold 1 alone swings −0.2163**: the M6, the fold that is 41% of the corpus
and a British motorway.

The suite is incomplete, so these are recorded as a tool check rather than a
finding. The number for record is produced once, on the finished suite.

---

## P79 — the ablation on fold 1 measures which model collapses hardest, not which generalises (2026-08-22)

**Status: open. This is a training-recipe defect, and it changes how the whole
ablation must be read.**

[P78](#p78)'s dry run showed fold 1 swinging **−0.2163** — the linear probe far
ahead of the full architecture. Rather than record the delta and move on, the
per-window predictions [P59](#p59) now writes were read.

**Config G predicts `HIGH` for all 252 windows of fold 1 at seed 1.**

```
fold1 seed1  G   predicted {HIGH: 252}
             H   predicted {HIGH: 138, LOW: 114}
true             {LOW: 150, MEDIUM: 82, HIGH: 20}
```

`20/252 = 0.0794`, which is exactly the accuracy recorded. At seed 42 G predicts
`{HIGH: 189, LOW: 63}`. **Neither model ever predicts MEDIUM on this fold at
all**, at any seed.

That is not an architecture comparison. It is a **collapse to a constant or
near-constant class**, and G collapses harder than H because it has the capacity
to fit the loss it is being given.

### The loss it is being given

PRD §8.4 specifies `CrossEntropyLoss` with **inverse-frequency class weights**.
Computed per fold from the training split:

| fold | train LOW/MED/HIGH | w_LOW | w_MED | w_HIGH | HIGH : MED |
|---|---|---|---|---|---|
| 0 | 84 / 118 / 18 | 0.87 | 0.62 | 4.07 | 6.6× |
| **1** | **119 / 188 / 9** | 0.89 | 0.56 | **11.70** | **20.9×** |
| 2 | 220 / 184 / 28 | 0.65 | 0.78 | 5.14 | 6.6× |
| 3 | 185 / 114 / 37 | 0.61 | 0.98 | 3.03 | 3.1× |

**On fold 1, nine HIGH windows carry 21× the per-sample weight of MEDIUM,
across a training split of 79 sequences.** The loss is dominated by nine
examples. Predicting HIGH everywhere is close to the weighted optimum, and the
model finds it.

The recipe is not wrong in general — inverse frequency is standard, and PRD §8.4
specified it before anyone knew the class balance this corpus would have. It is
pathological *at this balance and this training-set size*, which is a fact about
[P57](#p57)'s corpus meeting §8.4's recipe, not about either alone.

### What it means for the ablation

**The eight-config table on fold 1 ranks models by how completely they collapse.**
A model that collapses to a single class scores whatever that class's prevalence
is; a model that collapses partially scores a little better. Neither number is
about generalisation to an unseen camera.

It also explains [P54](#p54): the enormous seed spreads are models flipping
between *which* class they collapse to. Config E's 0.4469 / 0.2385 / 0.2046 is
that, not instability in any interesting sense.

**And it is the second time the same corpus fact has produced a fake result.**
[P57](#p57) found HIGH too sparse to estimate. This is the same sparsity coming
back through the loss function rather than through the metric.

### Not being fixed on the running suite

Changing the class weighting now would be changing the recipe after seeing which
results it produced. §8.4 is the specification, the run is in flight, and the
honest move is to **finish it and report what it measured** — including that on
at least one fold it measured collapse.

The fix belongs in an amendment with the arm definitions, alongside
[ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md)'s binary-collapse
trigger, which fires on the same underlying fact. Options a reviewer would
expect to see weighed: capping the weight ratio, square-root inverse frequency,
focal loss, or — most consistent with what this corpus can support — training
the binary task ADR-022 already pre-registered.

### The finding this validates

**P59 paid for itself here.** Without per-window predictions the record would
read "G scored 0.049 on fold 1", and the natural conclusion would have been that
the architecture generalises badly. The actual conclusion — that it emitted one
class 252 times — is a different problem with a different fix, and no metric in
the results CSV could have shown it.

---

## P80 — the benchmark promised PPO arms it could not run (2026-08-22)

**Status: fixed.** `simulation/ppo_controller.py`, `scripts/benchmark.py`,
`tests/test_ppo_controller.py`.

`benchmark.py` has said since it was written:

> PPO arms appear here automatically once checkpoints exist under `models/ppo/`.

They did not. `controllers()` returned `fixed`, `longest_queue` and `webster`
and nothing else. **This is the [P52](#p52) shape** — `ppo_config.yaml`
describing a surrogate arm that was never implemented — and it is worth naming
as a class: *a comment asserting a capability is indistinguishable from the
capability until someone runs it.*

Fixed now that a verifiable checkpoint exists: the first 500,000-step run with
a P47 sidecar (`timesteps: 500000`, `smoke: false`, contract digest
`24ad1c994e844238`, git commit recorded). Every prior checkpoint was unknowable
and is archived under P74.

### Two defects caught while writing the adapter, both silent

**The action decoding was wrong.** `keep_or_switch` is `Discrete(2)` — action 1
requests a switch, 0 keeps, and the green is the fixed `decision_interval_s`.
**The duration is not part of the action at all.** The first version here
decoded a green from `action // 2`, which on a two-action space is always 0, so
every green would have been the ladder's smallest while the environment used its
decision interval.

The policy would have been benchmarked under rules it never trained under, the
episodes would have run, the CSV would have filled, and **every number would
have been about a different experiment.** Nothing raises.

**A config value silently fell back to a literal.** The spec key is
`signal.green_durations_s`; the first version read `signal.green_durations` with
a default of `[10, 20, 30, 45, 60, 90]`. The default happened to match, so it
worked — and would have kept working, unchanged, after any edit to the real
value. That is exactly what NFR-16 prohibits. It now raises if the key is
absent, because a default here is a second copy of a config value.

### What is verified rather than trusted

`assert_compatible` refuses a checkpoint whose observation-contract digest does
not match the current `spec.yaml`, and one that records no digest. The 30-seed
benchmark is precisely where an unverified policy's numbers would end up being
reported from.

`discover_checkpoints` is **deliberately not recursive**, so P74's archive of
unknown-length checkpoints cannot be picked up. Recursing would undo that
archive in one line, and there is a test for it.

Safety clamping stays in the runner. A wrapper that clamped here would hide from
the results how often a learned policy asked for something out of range, which
is a thing worth knowing about a learned policy.

---

## P81 — the ablation finished, and it says what ADR-022 predicted (2026-08-22)

**Status: measured. 160 runs, 4 folds × 8 configs × 5 seeds, all with
per-window predictions.**

### The table

| config | | macro F1 | 95% CI | QWK | seed spread |
|---|---|---|---|---|---|
| C | concat fusion | **0.4405** | [0.372, 0.512] | 0.445 | 0.192 |
| **H** | **linear probe** | **0.4155** | [0.380, 0.449] | 0.477 | 0.165 |
| E | bidir, no gate | 0.4123 | [0.333, 0.487] | 0.393 | 0.209 |
| B | ViT only | 0.4059 | [0.361, 0.449] | 0.437 | 0.193 |
| **G** | **full, gated** | **0.3950** | [0.323, 0.464] | 0.343 | 0.198 |
| F | + temporal attn | 0.3900 | [0.308, 0.468] | 0.358 | 0.214 |
| A | CNN only | 0.3596 | [0.314, 0.405] | 0.307 | 0.160 |
| D | one-dir cross-attn | 0.2787 | [0.209, 0.348] | 0.190 | 0.125 |

**The full gated architecture ranks fifth of eight, below the linear probe.**
The ceiling is 0.9167, not 1.0 — one fold's test camera has no HIGH window
([P57](#p57)).

**Nothing in this table separates from anything else.** The largest seed spread
is 0.214 and the closest gap between two configs is 0.0032, a factor of 67. The
ordering is noise, and `run_loco.py` says so in its own output.

### Q1, the pre-registered test

```
per fold          0:+0.0237  1:-0.2163  2:+0.0796  3:+0.0313
mean difference   -0.0204
95% CI            [-0.1544, +0.0657]
min detectable     0.2115
VERDICT: CANNOT DISTINGUISH
```

Exactly the outcome [ADR-022](decisions/ADR-022-preregistered-gate-vs-probe.md)
wrote down in advance. The design could resolve 0.2115 and the observed
difference is 0.0204 — **the experiment has no power**, which is a statement
about the experiment.

### Q2, the diagnostic

```
reproduction check passed for G and H
20 run pairs, 2860 lane-windows
different predictions: 951 (33.25%)
G right / H wrong: 273
H right / G wrong: 597
```

G and H are **not** decision-identical — they disagree on a third of all
windows. And the disagreements are **asymmetric 2.19 : 1 in the probe's
favour**. McNemar's `p` is 0.00000 and is reported with its independence
assumption violated; it cannot support a generalisation claim.

Q1 says the fold-level test cannot separate them. Q2 says they decide very
differently and the probe is more often right. Those are the two different
situations ADR-022 split the questions to distinguish, and both are needed.

### The post-hoc analysis, labelled as post-hoc

Fold 1 is where [P79](#p79) found config G predicting `HIGH` for all 252 windows
— a collapse under inverse-frequency weighting on a 2.8% class, not an
architecture result. Excluding it:

| | folds | mean G − H | sd | MDD |
|---|---|---|---|---|
| pre-registered | 0, 1, 2, 3 | **−0.0204** | 0.133 | 0.212 |
| post-hoc, fold 1 removed | 0, 2, 3 | **+0.0449** | 0.030 | 0.075 |

**The sign flips.** On the three folds where neither model collapsed, G beats H
on every one.

**This is not the result, and it must never be reported as one.** ADR-022 fixed
the analysis in advance precisely so that a fold could not be dropped after
seeing which way it pushed the mean. The exclusion is *justifiable* — P79
diagnosed the collapse mechanically, from predictions, before Q1 was run — and
it is still a choice made with the numbers visible.

It is recorded as a **sensitivity analysis** with its own MDD, and the headline
stays `CANNOT DISTINGUISH` over four folds. What it earns is a pre-registered
hypothesis for a future corpus: *once the class weighting no longer drives
collapse, the fold-level comparison may separate.* That is a prediction, not a
finding.

### What this does not license

It does not license "the gate adds nothing", "MFSTNet fails", or "the linear
probe wins". At a minimum detectable difference of 0.212 over four camera-folds
with a 0.9167 ceiling and a class that exists in one fold, **this corpus cannot
rank these architectures**, and no amount of re-analysis changes that. It is
[ADR-023](decisions/ADR-023-separate-the-two-claims.md)'s C2, and it lands where
that ADR expected it to.

---

## P82 — the first real control result, and it beats the baseline that counts (2026-08-22)

**Status: measured.** `experiments/results/benchmark_ppo/`, 120 runs.

The 30-seed benchmark, saturated regime, now with a PPO arm that
[P80](#p80) made runnable. Mean per-vehicle wait, lower is better:

| method | n | mean wait | sd |
|---|---|---|---|
| **PPO, no-forecast, 500k** | 30 | **11.33 s** | 1.69 |
| Webster | 30 | 14.05 s | 1.86 |
| fixed | 30 | 26.18 s | 3.73 |
| longest queue | 30 | 26.92 s | 6.82 |

Paired over seeds:

| comparison | difference | 95% CI | p | Cohen's d |
|---|---|---|---|---|
| **PPO vs Webster** | **−2.72 s (19.4%)** | [−3.41, −1.98] | < 0.00001 | **−1.34** |
| PPO vs fixed | −14.85 s | [−16.04, −13.66] | < 0.00001 | −4.43 |
| PPO vs longest queue | −15.58 s | [−17.87, −12.72] | < 0.00001 | −2.12 |

### Why the Webster row is the one that matters

`benchmark.py` says it in its own docstring, written long before this number
existed:

> `fixed` is deliberately untuned... it stands for the status-quo signal this
> project claims to improve on. `webster` is the tuned-offline baseline — what a
> competent traffic engineer would deploy. **Beating `fixed` shows the problem
> is real; beating `webster` shows the method is worth having. Only the second
> is a result.**

**PPO beats Webster by 19.4%, paired over 30 seeds, at d = −1.34.** That is a
large effect against the baseline the project itself nominated as the real test,
and it is the first headline number this project has produced that is not
qualified into meaninglessness by its corpus.

### Where it sits, honestly

* **This is [ADR-023](decisions/ADR-023-separate-the-two-claims.md)'s C1**, and
  C1 is the half that needs no video corpus. The result stands whatever the
  guide decides about Part B, the domain, or the licence.
* **It is one arm.** `surrogate` does not exist ([P52](#p52)) and `mfstnet`
  needs a trained forecaster, so this measures *the controller*, not the
  forecast's contribution to it. The question "does a forecast help?" is
  untouched by this and remains ADR-021's.
* **One regime.** Saturated only. ADR-012's disqualification rules apply at the
  other two and none of these rows is marked disqualified.
* **One seed of training.** The policy is `seed 42`; PRD §14.4's five-seed rule
  is about *training* seeds, and this is thirty *evaluation* seeds against one
  trained policy. That is a real limitation and the next runs are seeds 1, 7, 13
  and 21.

### A mistake in the invocation, recorded because the output was misleading

`benchmark.py --out` is a **directory**, not a file. It was given
`experiments/results/benchmark_ppo_runs.csv`, so it created a *directory* of
that name containing `benchmark_runs.csv` and `benchmark_stats.csv`. The run was
correct and the path was nonsense — a directory called `something.csv` is the
kind of artifact that gets mistaken for a file by the next script that touches
it. Moved to `experiments/results/benchmark_ppo/`.

---

## P83 — the control server, and a default bound at import time (2026-08-22)

**Status: S41 done.** `server/safety.py`, `server/app.py`, 35 tests.

Phase 6 was 1 of 6 and needed nothing that is blocked — the detector exists, the
MQTT contract exists, and none of it touches the corpus, the guide or a licence.

### The shape, and why

**Every rule that matters is in `server/safety.py`, which has no HTTP in it.**
FR-A03 (10 s / 90 s green), FR-A04 (all-red ≥ 3 s), FR-A05 (emergency
preemption) and FR-A06 (Webster fallback within 10 s) are requirements about
*actuation*, and `simulation/controllers.py` already states the principle for
the simulator: safety clamping lives outside the controller so that **no
controller, learned or otherwise, can produce an unsafe program**. A PPO policy
is exactly the component that will one day request a 2-second green because a
reward surface said so.

The rule **order** is the requirement order and is tested as such: emergency
outranks minimum green — a minimum-green rule that delays an ambulance is a rule
applied to the wrong thing — and outranks the MQTT fallback. Webster's own
output is still clamped, because it is a formula and not a trusted oracle.

**NFR-13 is structural, not a rule to remember.** The request model has no field
that could carry a frame and no stored column could hold one, and both are
asserted. A privacy guarantee implemented as a check somewhere is a guarantee
that survives until someone adds an endpoint.

**FR-A06's clock is the server's.** The edge reports when it last spoke; the
server judges whether that is too long ago. **A device that has crashed cannot
report that it has crashed**, so a timeout measured on the sender would never
fire in the one case it exists for. There is a test named after that.

### The defect, which looked like something else

`def connect(path: Path = DATABASE)` binds the default **when the module is
imported**. The tests pointed `DATABASE` at a temporary file, every call ignored
them, and three tests shared one database — the real one, in `data/server/`.

It surfaced as `assert 9 == 3` on a history query, which reads as a query bug.
It was a scoping bug, and the give-away was that 9 is exactly 3 tests × 3 posts.
`connect` now resolves the default at call time.

Worth recording because **the test isolation was fake in a way the tests
passed through**: eleven of twelve assertions held anyway, and only the one that
counted rows noticed.

### Also

`requirements.txt` gained `fastapi`, `pydantic`, `uvicorn` and `httpx` — caught
by `test_every_imported_package_is_pinned`, which is the repo's own rule
enforcing itself in the same commit as the first import. `httpx` is not imported
by server code; `fastapi.testclient` requires it, and a test dependency whose
absence breaks the suite is still a dependency.

ADR-008's SQLite choice means there is no database driver in that list and no
container to run.

---

## P84 — the edge node, and both fallbacks now exist (2026-08-22)

**Status: S40 done, S43 half done.** `edge/node.py`, 14 tests.

**FR-A06 is decided on the edge, and that is the whole point of it.** When the
link to the server drops, the node stops waiting for commands and runs a locally
embedded cycle. It cannot ask the server whether the server is reachable.

That mirrors the server-side rule from [P83](#p83): the server measures the
timeout because *a device that has crashed cannot report that it has crashed*.
Both ends measure what they can observe, and neither trusts the other to tell
it. **Both fallbacks now exist and are tested**, which is most of S43.

### The transport is an interface, not a broker

`Transport` has two methods and `RecordingTransport` implements them into a
list, so the link is dropped by setting a flag. That is not a test double added
afterwards — it is the only reason the fallback is testable at all. **A fallback
that can only be exercised by unplugging something is a fallback nobody
exercises**, and this one has a test for the 10-second boundary in both
directions, for recovery, and for the case where nothing gets through and
`last_ack` correctly does not move.

### The contract is constructed, not described

The node builds `VehicleCount` and `Heartbeat` from `contracts/mqtt.py` rather
than assembling dictionaries, so a per-class breakdown that does not sum to the
total raises **at the edge** rather than reaching a consumer that cannot tell
which number to trust. Topics and QoS come from `Topic`, which binds them
together — the node cannot publish emergency at QoS 0 by choosing wrongly.

Three contract violations were caught while writing it, each in seconds because
the type refused: `Topic.format` does not exist (it is `render`), `Heartbeat`
takes `edge_status`/`mfstnet_active`/`ppo_active` rather than an uptime, and
`edge_status` accepts only `online` or `degraded` — not `ok`. **A contract that
refuses at construction is worth more than a schema nobody validates against.**

### NFR-13 stated as a test rather than a comment

The published topics are the node's entire outward surface, so the check is to
list them and assert every one ends in `vehicle_count` or `heartbeat`, and that
no payload body contains an image-shaped key. Frames are read, counted and
dropped.

### `Mode.LOCAL`, not a new name

The first version invented `Mode.FALLBACK`. The contract already defines
`LOCAL`, and a second name for one state is how a dashboard ends up with a
branch that never fires.

## P85 — M6 decides whether the full model beats the linear probe (2026-10-14)

**Believed.** That the leave-one-camera-out mean in `loco_summary.csv` was a
single quantity, and that ADR-022's `CANNOT DISTINGUISH` verdict was a property
of the models.

**Measured.** `scripts/camera_audit.py`, recomputed from the committed per-fold
scores with no training run. Fold 1 holds out **M6 Motorway Traffic** — the one
camera `data/cameras.json` declares `traffic_type: structured`, against a target
of `mixed`, and the entry that file already calls "the premise's
counterexample". It is **41.2% of all windows and 52.6% of every HIGH label**.

Macro-F1 over all four folds, against the three `mixed` folds alone:

| config | all folds | mixed only | delta |
|---|---|---|---|
| A — CNN only | 0.3596 | 0.3546 | −0.0050 |
| B | 0.4059 | 0.4257 | +0.0198 |
| C — best vision | 0.4405 | 0.4691 | +0.0286 |
| D | 0.2787 | 0.3553 | +0.0766 |
| E | 0.4123 | 0.4845 | +0.0722 |
| F | 0.3900 | 0.4663 | +0.0763 |
| **G — full model** | **0.3950** | **0.4693** | **+0.0743** |
| **H — linear probe** | **0.4154** | **0.4245** | **+0.0090** |

**The sign of ADR-022's comparison flips.** With all four folds the linear probe
beats the full model, G−H = **−0.0204**. Over the three in-regime folds the full
model beats the probe, G−H = **+0.0449**.

**Why, and why it is coherent rather than suspicious.** The configurations that
gain from excluding M6 are exactly the ones carrying fusion, recurrence and
attention — D through G all gain about 0.07 — while the linear probe gains
0.009 and the CNN-only arm *loses* 0.005. A model with more capacity to fit the
training regime transfers worse to a camera outside it. On fold 1, config D
scores 0.0490 on every seed, which is a degenerate constant predictor rather
than a weak one.

**Changed.** Nothing yet, and deliberately. PRD §2.5.5 forbids dropping an
inconvenient fold, and a mean chosen after seeing which one flatters a model is
cherry-picking. What is now required is that **no macro-F1 mean is quoted
without its fold composition**, because the two means answer different
questions: one is transfer to an out-of-regime camera, the other is
generalisation within the target regime.

**Rejected.** Dropping M6 from the corpus. It is the project's only structured
-traffic camera and therefore its only external-domain generalisation test; the
right move is to report it as a named arm, not to delete it.

**Owed.** A decision on how ADR-022's verdict is stated given that it is
conditional on fold composition, and a re-reading of `gate vs probe` in the
synopsis, which currently quotes the all-folds number alone.

## P86 — the `domain` claim cannot pass while M6 stays a fold (2026-10-15)

**Believed.** That adding licensed Indian cameras would turn the `domain` claim
green, and that this was compatible with keeping M6 as the project's
external-domain test (P85).

**Measured.** `evaluation_contains_target_domain` in `scripts/check_claims.py`
fails if **any** fold's test camera is off target. Every `real_external` camera
that stays a leave-one-camera-out fold is therefore a permanent failure of that
claim, however many Indian cameras are added beside it. The two decisions —
retain M6 as a fold, and assert the Indian domain — cannot both hold under the
claim's current protocol.

**Changed.** Nothing. `scripts/check_sources.py` now states the conflict every
time it runs, so it cannot be rediscovered after a collection effort has been
spent.

**Owed — the project owner's decision.** The coherent resolution is the
three-partition design: headline leave-one-camera-out folds over `real_india`
cameras only, and `real_external` cameras scored as a separately named
external-domain arm (train on the Indian folds, test on M6 and Dhaka). That is a
change to the claim's protocol and to ADR-019's fold set, so it needs an
amendment to both, not a code edit. Until then, `domain` stays red for two
reasons rather than one.

**Approved in principle — 2026-10-15, project owner.** The headline is scored
on eligible `real_india` cameras only; M6 and Dhaka are reported separately as
an external-domain evaluation; synthetic data is never an evaluation. The
approval covers the protocol, **not** a finding that the Indian-domain
requirement is met. Drafted as [ADR-025](decisions/ADR-025-headline-folds-are-real-india.md)
for explicit sign-off.

Implementing it found two traps, both now closed in `scripts/check_claims.py`.
First, a scoped `domain` check is **vacuously true over zero Indian folds**, and
zero is today's count; an empty scope now fails. Second, scoping only `domain`
would leave `camera_count` passing on three Bangladeshi cameras and a British
motorway, so all three evaluation claims are scoped together. Previewed with
`--protocol headline`: `domain`, `class_coverage` and `camera_count` all fail.
`CLAIMS.yaml` is unchanged until ADR-025 is signed.

## P87 — no trained MFSTNet was ever kept (2026-10-15)

**Believed.** That the A–H suite had produced trained models, and that the
exported ONNX graph was one of them.

**Measured.** `train_one` in `scripts/train_mfstnet.py` selected the best state
on validation macro-F1, evaluated it on test, and returned only the metrics.
**None of the 320 leave-one-camera-out runs saved its weights.**
`scripts/export_onnx.py` builds `MFSTNet(config, masks)` from scratch — correct
for the latency it measures, which does not depend on the weights, but it means
the control server and the dashboard have no trained forecaster to serve, and
there was nothing to fine-tune from.

**Changed.** `--save-checkpoint DIR` writes the selected model per config, with
a sidecar recording domain, test, validation and excluded cameras, mode,
preprocessing hash and the file's sha256. It refuses to overwrite without
`--force`, under P47's rule. `--init-from PT` fine-tunes from one: it loads
strictly, refuses a different config, and refuses a different feature space by
preprocessing hash (ADR-005: raise, never warn). The child's sidecar names its
parent by sha256, not by path. `resplit_corpus.py --domain foreign|india|mixed`
selects the cameras (ADR-025), and `mixed` reproduces all four committed fold
views byte for byte.

**Also tightened.** `CameraRegistry.partition` is now the one definition of a
camera's domain, shared by the fold builder and `check_sources.py`. It requires
every declared target field, viewpoint included, so Mumbai and South Extension
— Indian by filename, viewpoint never inspected — are `unknown` rather than
`real_india`. The corpus holds **zero** Indian cameras by that definition, which
is what the claims gate already said.

**Owed.** Re-export ONNX from a trained checkpoint, and point the server at it,
once the foreign baseline is chosen.

## P88 — the cache's hash certifies an interpolation it never used (2026-10-15)

**Believed.** That `PreprocessingSpec` describes how cached features were
computed, so a matching hash means matching inputs (ADR-005).

**Measured.** `PreprocessingSpec.resize_mode` is `"bilinear"`.
`scripts/build_cache.py` has always resized with `cv2.INTER_AREA`. The hash
covers the label, not the computation. The spec's own docstring names
interpolation as "exactly the kind of change that slips through a review
unnoticed", and it did — inside the record that exists to catch it. Found while
building the edge forecaster (ADR-026), which must reproduce the cache's input
exactly or serve the model an input space it never trained on, with nothing
raising.

**Changed.** The per-frame transform moved to `mfstnet/preprocess.py`, used by
both `build_cache.py` and `edge/forecaster.py`, and verified bit-identical to
the previous inline transform on a 1280×720 frame. The edge and the cache now
cannot diverge, whatever the label says.

**Rejected.** Correcting the label to `"area"`. It changes the hash, which
invalidates every cached feature and every checkpoint's `preprocessing_hash`,
to fix a word. The computation is right and is now single-sourced. The label
should be corrected at the next deliberate cache rebuild, with this entry
cited.

## P89 — the edge budget times inference, not decoding (2026-10-15)

**Believed.** That `verify_edge.py`'s step time is the edge's cost per step.

**Measured.** The step timer starts at a decoded frame. On S61's selected
checkpoint the step p95 was 170.8 ms against a 1000 ms budget. Cold start, which
does include decoding, was 147 s for the first 60-sample window. About 6 s of
that is model work (60 × 96 ms of features). The remaining ~141 s is decoding
the test camera's file: **3840×2160 at 29.97 fps**. Sampling every 2 s still
decodes every frame (P51), so that is about 3,600 4K frames, or roughly 39 ms a
frame, about 25 fps on the CPU. A live 4K stream arrives at 30 fps. **The decode
rate is derived from the cold start, not measured on its own.**

**Changed.** Nothing in the code. The ADR-026 evidence states the gap beside the
passing numbers rather than under them.

**Owed.** Time decoding alone at the deployment camera's resolution and codec,
with and without NVDEC. If a 4K camera cannot be decoded in real time, either
the stream is requested at 1080p — the model sees 224×224 regardless — or decode
moves to the GPU. Neither touches the model or its budget.

**Measured — 2026-10-15, `scripts/benchmark_decode.py`.** The derived 25 fps
above was **wrong**. Cold start also included OpenCV's forward-decode reader
and the model, so it was not a decode figure. Measured directly, and fixed
before the first run:

- **Test streams:** a 5-minute segment of the same footage in three encodings —
  the original AV1, and H.264 encoded the way a camera does (1 s GOP, constant
  bitrate).
- **Live run:** each stream played at real rate, one frame every 2 s through the
  full verified pipeline.
- **Pass needs all of:** decode at least 1.0× real time; lag growth under one
  step; interval p95 within 25% of 2 s; no lost sample.

| stream | decoder | decode only | lag, first to last | interval p95 | step p95 | verdict |
|---|---|---|---|---|---|---|
| AV1 4K (the YouTube file) | software | 41.3 fps, 1.38× | **3.2 → 39.4 s** | 3.00 s | 508 ms | **FAIL** |
| AV1 4K | NVDEC | 106.5 fps, 3.55× | 3.31 → 2.07 s | 2.17 s | 496 ms | pass |
| H.264 4K | software | 293.8 fps, 9.80× | 3.75 → 1.80 s | 2.12 s | 471 ms | pass |
| H.264 4K | NVDEC | 274.1 fps, 9.15× | 3.68 → 2.30 s | 2.22 s | 517 ms | pass |
| H.264 1080p | software | 824.4 fps, 27.5× | 3.28 → 1.72 s | 2.10 s | 413 ms | pass |

All five delivered 150 of 150 samples and 91 predictions.

**The AV1 software failure is real and reproducible**, and it is the one that
shows why decode-only throughput settles nothing. Decode alone ran at 1.38×
real time. Alongside the model, which shares the CPU, it fell 36 s behind in
five minutes. On a live stream that is dropped frames. It is not averaged into
the passing rows.

**Where a step's time goes**, each stage measured in isolation with no decoder
running:

| stage | 4K | 1080p |
|---|---|---|
| preprocessing, `INTER_AREA` on CPU | 50 ms | 11 ms |
| backbones, GPU, one frame | 52 ms | 52 ms |
| ONNX head, CPU, 60-step window | 167 ms | 167 ms |

The 4K resize costs about 40 ms more than 1080p. It is not the main cost. The
head is the largest stage and the least stable: it measured 57–115 ms in
earlier runs and 167 ms after 30 minutes of sustained load. That fits CPU
contention or laptop thermal throttling, and **which one is not isolated**. The
rest of the in-pipeline 410–520 ms is contention with a decoder running
continuously beside it. Every configuration stays inside the 1000 ms budget.

**Recommended deployment format: H.264, 1080p if the camera offers it.** It
passes in software with the largest margins, needs no GPU decoder, and halves
the preprocessing cost. The 224×224 model input does not need 4K. One caution
on that: the corpus cached this camera's features from its 4K source. A
1080p-to-224 downscale is close to a 4K-to-224 one, but not identical, so
switching a deployed camera's stream resolution is a small input shift worth
re-verifying with `verify_edge.py`.

**Still open, and why production readiness stays open.** These are re-encodes
of a YouTube file played from disk. They are not a real camera's stream over
RTSP: no network jitter, no camera-side encoder, no reconnects. The real
camera's codec, resolution, frame rate and stream protocol decide the final
answer. Two optimisations are worth measuring before then, and neither is
needed to pass: running the head on the GPU (onnxruntime's CUDA provider,
verified the same way as the CPU graph), and capping onnxruntime's threads so
it stops contending with decoding.

## P90 — the verified graph's weights were never hashed (2026-10-15)

**Believed.** That `VerifiedGraph` refuses any model that differs from the one
`export_checkpoint.py` verified, because it checks the graph's sha256 (ADR-026).

**Measured.** torch's exporter wrote the S61 model as two files: the graph,
`mfstnet_foreign_G_seed13_fold3.onnx` (0.57 MB), and its weights in
`….onnx.data` (12.6 MB). **55 of the graph's 89 initialisers live in the
`.data` file**, and only the graph file was hashed. A `.data` file swapped for
untrained weights would have loaded, passed the check and served. That is the
exact failure P87 exists to prevent, and it got past the check written for it.
Found while preparing the weights backup, which had to know every file a model
consists of.

**Changed.** `mfstnet/onnx_files.py` reads, from the graph itself, every
external file the graph references and hashes each one. `export_checkpoint.py`
records them as `files_sha256`. `VerifiedGraph` now:

- hashes the graph file before parsing it, so a replaced graph is reported as
  replaced and not as a parser crash;
- refuses a sidecar without per-file hashes;
- refuses a missing or extra file, and refuses any file whose hash differs.

Four tests build a real two-file ONNX model; one swaps only its weights.

**The S61 evidence stands.** Re-exporting the selected checkpoint produced both
files **byte-identical** to the deployed ones (`fe093966…`, `df2736a5…`).
Export is deterministic, so the graph verified 136/136 and measured on the edge
is the one now covered file by file. Its sidecar was replaced with the
re-export's, which adds `files_sha256` and changes nothing else.

**Related.** `scripts/backup_models.py` writes
`experiments/results/model_artifacts.sha256`: 83 files, 312 MB, the `.data`
files included. That manifest is committed, so any copy of the weights can be
verified against the repository. The laptop has one physical disk; C: and D:
are partitions of it, and `pack` refuses a destination on the repository's own
drive.

## P91 — A30's Bellevue finding does not reproduce with the current detector (2026-10-15)

**Believed.** [A30](#a30--measurement-withdrawn-the-detector-does-not-work-on-bellevue-2026-08-17),
2026-08-17: Bellevue is unusable as a corpus. On NE 8th, about 10 visible
vehicles drew 3 detections, one labelled `auto_rickshaw`, and the near-overhead
fisheye view was judged a third viewpoint class the detector cannot handle.
`build_corpus.py` has excluded paths containing "Bellevue" by default ever
since.

**Measured.** The project owner re-opened Bellevue for the foreign-data
pipeline (S63). The same camera (NE 8th, Monday 11 Sep 2017, 16:08–17:08) was
run through the detector the corpus is now built with: ITD-xl
(`best_xl_ITD_v1.2.pt`), confidence 0.45, **input 992**.

- Survey: **1,286 detections over 60 frames**, about 21 a frame; 1.6%
  unassigned to any lane.
- Three frames rendered and inspected (16:13, 16:38, 17:03): **24, 23 and 24
  detections**. At 16:38, every near- and mid-range vehicle is boxed. The north
  queue has about 10 boxes on about 15 visible cars, with the farthest missed;
  one small car at the right edge is missed. Roughly 75–85% of vehicles,
  against A30's 3 of 10.

`check_recording.py`, the tool A30's lesson produced, takes no `--imgsz` and
renders at the detector's default input size. The corpus counts at 992. Part of
A30's failure may have been the input size, and the tool cannot show it.

**What is still wrong, and why it is tolerable here.**

| error | effect | bound |
|---|---|---|
| the painted bicycle-lane symbol detected as `bicycle 0.74` in every frame, inside the west lane's reach | a constant +1 bicycle in that lane | 0.20 PCU, constant; per-camera thresholds absorb a constant offset |
| US cars sometimes labelled `autorickshaw` | 1.20 PCU instead of 1.00 | +0.20 PCU per misclassified car |
| the far end of the north queue under-counted | lower counts at the longest queues | compresses the top of the range, which the per-camera percentiles partly absorb |

None of these is A30's failure, where the counts were fiction. All three are
biases, and **Bellevue's labels are recorded as auto-labelled, proxy-derived
and foreign-domain**, never as Indian evidence and never as the headline.

**Changed.** A30 stands as what it measured. The default exclusion in
`build_corpus.py` is unchanged; this corpus was built with `--exclude` given
explicitly and empty, so the override is visible in the command and the
manifest. It is scoped to `data/corpus_bellevue` alone.

**Owed.** `check_recording.py` should take `--imgsz`, so the domain check runs
at the size the corpus counts at. A precise recall figure needs hand-counted
frames; the 75–85% here is from inspection, not annotation.

## P92 — on one Bellevue camera, MFSTNet does not beat persistence (2026-10-15)

**Measured.** S63, under a pre-registration written before any label existed.
Two hours of one camera, a chronological 60/20/20 split with full-window
buffers, G and H at five seeds each, selection on validation only. The selected
run is G, seed 21, at validation macro-F1 0.8704. On the held-out final period
it scored **0.5644**, while persistence — the label of the window's last
observed sample — scored **0.5875** on the same windows. G is better only on
QWK, 0.540 against 0.464. Full detail in
`experiments/results/bellevue_pilot/REPORT.md`.

**Why it matters more than one camera.** A32 said the labels are a
deterministic function of the count, so count baselines see the
label-generating variable. Persistence is the simplest such baseline, and
nothing here beats it. Until a model beats persistence on held-out data, it has
not shown it forecasts anything. That bar now belongs beside every result,
including S61, which was never compared with persistence.

**Also found.**

- The fixed thresholds give **no HIGH** in validation or test on this camera.
  The per-camera thresholds give HIGH only as "the busiest third", flat across
  the evening peak.
- The south lane is empty in 63% of samples and always LOW.
- `build_corpus.py` crashed after writing a temporal-mode corpus, because a
  print statement assumed clip-mode splits. The data was complete and the
  print is fixed.

**Owed, as a decision.** Whether the forecasting target needs redefining —
for example a longer horizon, or occupancy change rather than level —
**before** more Bellevue cameras are added. More cameras would measure
generalisation of a model that does not yet beat persistence on the camera it
was trained on.

**And S61 does not beat it either.** The same persistence baseline on S61's
four foreign folds, with that corpus's own labels (LOW ≤ 4, MEDIUM ≤ 15),
against G's mean over five seeds:

| fold | test camera | G | persistence |
|---|---|---|---|
| 0 | Dhaka Rampura | 0.4225 | **0.4492** |
| 1 | M6 | 0.4671 | **0.6924** |
| 2 | Dhaka footbridge | 0.4089 | **0.6726** |
| 3 | Dhaka Rampura (second camera) | 0.3297 | **0.4141** |

Persistence is ahead on every fold. That is consistent with
[ADR-023](decisions/ADR-023-separate-the-two-claims.md)'s measurement that
naive last-value scored 0.557 across four folds. It is now confirmed for the
model actually deployed on the edge. **The deployed model is verified,
integrated and fast. It is not yet better than predicting no change.**

**Horizon diagnostic, S63b.** At 180 s on the same camera the selected model
scores 0.6165 against persistence 0.5848, a difference of +0.032 with a paired
bootstrap 95% interval of [−0.061, +0.128]: not distinguishable. 300 s cannot
be split on two hours. At 60 s the interval is [−0.114, +0.079], so the
supported statement is "does not beat persistence", not "is beaten by it". By
the pre-registered stop rule the horizon is not changed again.

## P93 — the targets are predictable enough to leave room, and the signal cycle shows (2026-10-15)

**Measured** by `scripts/target_diagnostic.py` under
`experiments/results/bellevue_pilot/PREREGISTRATION_P93.md`, on validation
only: 19 windows, 76 lane decisions. The test period was not read.

| target | persistence F1 | naive trend F1 | trend − persistence [95% CI] |
|---|---|---|---|
| sustained level, mean count over the next 60 s | **0.6021** | 0.4780 | −0.124 [−0.208, −0.036] |
| direction, rise / stay / fall at ±1 vehicle | **0.2102** | 0.2589 | +0.049 [−0.010, +0.107] |
| instantaneous level (the current target, reference) | 0.6422 | — | — |

**Both targets clear the pre-registered bar for room** — persistence below 0.80,
and every class with at least 10 validation decisions.

**The finding behind the numbers is the signal cycle.** On the training period
the north lane's count autocorrelates at **−0.337 at 60 s and +0.354 at
120 s**, and the west lane at +0.206 at 120 s: a cycle of about two minutes.
That explains three things at once:

- **Persistence of the 60 s mean is right only 15.8% of the time on the north
  lane.** The last minute and the next minute sit in opposite halves of the
  cycle.
- **Naive trend loses to persistence** (the interval excludes zero), and on
  direction its QWK is **−0.64**: a recent rise is followed by a fall.
  Momentum is the wrong model; the traffic oscillates.
- **A model has a real way to win.** A 120 s input window covers a whole cycle,
  so the phase can be seen. Persistence cannot see phase.

**Pre-registered decision.** Sustained level has room, so it may be frozen and
a G/H training run pre-registered against it. Direction has room too, as a
separate task.

## P93a — ADR-017's PCU weighting was never applied to any label (2026-10-15)

`count_frame` adds one per detected vehicle (`per_lane[lane] += 1`), and
`pcu_total` in `mfstnet/corpus/pcu.py` is called nowhere in the corpus
pipeline. **Every label in the project, S61's included, is a raw vehicle count
against a threshold**, not the PCU-weighted occupancy ADR-017 specifies.

**Correction to P91 and to the S63 report, check 3.** A car misread as an
`autorickshaw` does not add 0.2 PCU; it adds nothing, because labels count
vehicles. The detection errors that do matter are the ones that change a
**count**:

- the painted bicycle symbol adds **one whole vehicle** to the west lane in 21%
  of samples — larger than the 0.2 PCU first stated;
- the 7% of `two wheeler` detections each count as one vehicle;
- the far end of the north queue is missed.

**Owed.** Implementing PCU needs pre-registered mappings for `LCV` and
`two wheeler`, which the PCU table lacks. It changes every label, so it is a
decision, not a fix.

## P94 — sustained targets: every model is ahead of its baseline, none distinguishably (2026-10-15)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P94.md`.
Selections were frozen and committed (`20bd1c1`) before the test was read.

| target | model | test F1 | previous-window mean | model − baseline [95% CI] |
|---|---|---|---|---|
| 60 s sustained | **G (selected)** | 0.7167 | 0.6470 | +0.070 [−0.017, +0.156] |
| 60 s sustained | H | 0.6829 | 0.6470 | +0.036 [−0.053, +0.126] |
| 120 s sustained | G | 0.8036 | 0.7139 | +0.090 [−0.001, +0.189] |
| 120 s sustained | **H (selected)** | 0.7718 | 0.7139 | +0.058 [−0.027, +0.147] |

**By the pre-registered definition, no model beats its baseline.** Every
interval contains zero.

**What did change, reported without over-reading it.**

- **All four point estimates are positive.** At the instantaneous 60 s target
  they were −0.023 and +0.032.
- **Absolute scores rose from about 0.56–0.62 to 0.68–0.80.** The sustained
  targets are far more learnable — and so is the baseline.

**Per-lane, where P93 said a model could gain.** At 60 s, on the north lane
(the strong signal-cycle lane), G is right on **16 of 29** windows against the
baseline's **11**, and on the east lane 18 against 12. It loses on the west
lane, 19 against 25. At 120 s, averaging over a whole cycle removes the phase,
and the north lane shows no gain: 11 against 12. That is consistent with the
P93 mechanism. It is one camera and a handful of windows, and is not
established by it.

**Selection, as fixed.** At 120 s, G and H tied exactly on validation (0.8914),
so the rule chose H. G later scored higher on test. The selection is **not**
revised after seeing the test.

**Why nothing resolves: power.** The intervals are about 0.17–0.19 wide on 25–29
test windows. Resolving an effect of +0.07 to +0.09 needs an interval roughly
half that width, or about **four times the test windows**. That is around 100,
which means several more hours of footage or more cameras.

**Decision, as pre-registered.** Neither model beats its baseline
convincingly, so the honest result stands and the labels are investigated
before the dataset is expanded. The power calculation above is the evidence
that expansion will eventually be needed to settle the question.

## P95 — the detector undercounts Bellevue by 15–45%, more as traffic grows (2026-10-15)

**Measured** by a blind hand count of 20 systematically chosen frames, under
`experiments/results/bellevue_pilot/AUDIT_PROTOCOL.md`, all fixed before
counting. The counts are in `audit_manual.json`, the comparison in
`audit_comparison.json`. This is a **pilot**: twenty correlated frames from one
camera.

| lane | hand mean | detector mean | MAE | bias (detector − hand) | relative | Pearson / Spearman | detected share, quiet half → busy half |
|---|---|---|---|---|---|---|---|
| west | 8.20 | 6.95 | 1.75 | −1.25 | −15% | 0.84 / 0.82 | 94% → 80% |
| north | 13.05 | 7.95 | 5.10 | −5.10 | **−39%** | 0.82 / 0.84 | 66% → 59% |
| south | 1.80 | 0.35 | 1.45 | −1.45 | −81% | **0.41 / 0.39** | 33% → 15% |
| east | 10.50 | 5.75 | 4.75 | −4.75 | **−45%** | 0.78 / 0.77 | 64% → 52% |

The painted bicycle symbol was reported as a bicycle in **6 of 20 frames**.

- **What it means for the labels.** On west, north and east the detector's count
  **orders** frames much as a person does (correlations 0.77–0.84), so relative
  labels carry real signal there. But the undercount **grows with traffic**:
  busy frames are compressed, which blurs exactly the HIGH class. The south
  lane is close to noise.
- **What it means for P92–P94.** Label noise of this size caps the accuracy any
  model *or* baseline can reach, and narrows the room between them. It is a
  plausible part of why nothing has been distinguishable.
- **What it revises.** The "roughly 75–85%" recall in P91 was an estimate by eye
  and was optimistic for north and east.

**Not changed, as pre-registered.** No threshold or label moves on a pilot.
The protocol's rule for material error is to expand the annotation sample
first. Whether to drop the south lane from the labels is a separate decision,
and changes the model's lane count.

## P96 — 60-frame audit: the undercount holds and grows with traffic; the south lane carries no signal (2026-10-15)

**Measured** on 60 blind hand-counted frames: the 20-frame pilot unchanged,
plus 40 more, two per six-minute bin with seed 2027. Selection was stratified
by time, never by detector count. Intervals are a frame-clustered bootstrap.
Detail in `experiments/results/bellevue_pilot/audit_comparison_60.json`.

| lane | undercount [95% CI] | quiet → busy undercount | Pearson [95% CI] | exact |
|---|---|---|---|---|
| west | 14% [9, 19] | 8% → 19% | 0.82 [0.72, 0.89] | 25% |
| north | 27% [20, 33] | 20% → 30% | 0.80 [0.68, 0.90] | 18% |
| east | 41% [34, 47] | 28% → 47% | 0.71 [0.56, 0.86] | 12% |
| south | 79% [66, 88] | 50% → 85% | **0.16 [−0.02, 0.50]** | 48% |

The painted bicycle symbol was reported as a bicycle in 13 of 60 frames (22%).

- **What the larger sample settles.** The pilot's north figure of −39% was high;
  60 frames put it at 27%. **The direction holds everywhere:** the detector
  undercounts on every lane, and on every lane it undercounts more when traffic
  is heavy. Busy periods are compressed, so the busy end of each lane's labels
  is squashed.
- **On west, north and east the ranking survives.** The lower bound of every
  correlation interval is at least 0.56, so relative labels track real traffic
  there, imperfectly but genuinely.
- **The south lane does not.** Its correlation interval includes zero.
  Exact-agreement of 48% looks good only because both counts are usually near
  zero.

**The south lane, assessed against the owner's two options.**

1. **Three lanes — west, north and east.** Supported by the evidence above.
   The contract already defines an absent approach: `to_state_values()` yields
   0.0 for a missing lane, the same value FR-A06 specifies when MFSTNet is
   unavailable, so PPO's 16-dimensional state stays intact.
2. **A corrected fourth region.** It needs an observable south approach queue.
   In this camera's frames the south approach runs **beneath the camera**: the
   bottom of the image is the near crosswalk and the dome housing, and vehicles
   waiting to enter northbound are out of view. **There is no observable queue
   to place a region on.** Option 2 is not available for this camera. It may be
   for another.

**Not changed.** No label, threshold, corpus or checkpoint. The lane decision is
the project owner's. The detector question — fine-tuning against a 14–41%
undercount that worsens with traffic — follows it, as agreed.

## P97 — on three lanes, G beats the previous-window mean at 60 s (2026-10-15)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P97.md`.
The three-lane Bellevue corpus (west, north, east) has P94's targets, windows,
splits, thresholds, seeds and rules; only the lanes changed. The selections
were committed (`20a4428`) before the test was read.

**A run was interrupted.** Six of the twenty runs finished before a session
ended. The remaining fourteen ran afterwards with an unchanged configuration,
and a run counted as done only when both its metrics and its predictions
existed. The evaluator then stopped once on a manifest key — the three-lane
corpus records its frozen 2/8 thresholds as `low_max`/`med_max` — before any
prediction file was opened. It was fixed to read either form, and the test was
read once.

| target | model | test F1 | previous-window mean | difference [95% CI] | verdict |
|---|---|---|---|---|---|
| **60 s** | **G (selected)** | 0.4508 | 0.3248 | **[+0.027, +0.225]** | **beats the baseline** |
| 60 s | H | 0.3620 | 0.3248 | [−0.050, +0.127] | not distinguishable |
| 120 s | **H (selected: exact validation tie)** | 0.3148 | 0.3806 | [−0.152, +0.027] | not distinguishable |
| 120 s | G | 0.4703 | 0.3806 | [−0.001, +0.189] | not distinguishable |

**The 60 s result does not come from the near-empty class.** The test period
has one LOW lane-decision in 87, and both G and the baseline get it wrong. G's
advantage is on the classes with support: MEDIUM F1 0.803 against 0.678 (59
instances) and HIGH 0.549 against 0.296 (27). Post-hoc sensitivity intervals,
**not pre-registered**, exclude zero:

| metric, G − baseline | difference [95% CI] |
|---|---|
| accuracy | +0.172 [+0.035, +0.299] |
| QWK | +0.401 [+0.129, +0.665] |
| F1 over MEDIUM and HIGH only | +0.189 [+0.040, +0.338] |

**Where the gain is.** Windows right out of 29, G against the baseline: north
20 against 11, east 18 against 12, west 25 against 25. The gain sits on the
signal-cycle lanes P93 identified and is absent on west.

**H is not a comparable simpler model here.** At 60 s it is not distinguishable
from the baseline and well below G (accuracy 0.552 against 0.724).

**What this supports, and what it does not.**

- **Supported:** on this camera, under these auto-derived labels, the full
  model forecasts the 60 s sustained level better than predicting the last
  minute again — the first pre-registered result in the project to clear that
  bar.
- **Qualified:**
  - There were **two** pre-registered primary comparisons, one per target, and
    one passed. No family-wise correction was pre-registered, and the primary
    interval's lower bound (+0.027) is close to zero; the sensitivity
    intervals are clearer.
  - It is one camera, one afternoon and 29 test windows.
  - The labels carry the P96 undercount: west 14%, north 27%, east 41%.
  - At 120 s the test has **no LOW at all**, so macro-F1 there is capped by an
    absent class.
- **Not established:** generalisation to an unseen camera; anything about
  Indian traffic.

**Two checks of consistency.**

- **At 120 s, G's interval is identical to P94's** (four lanes), to four
  decimals. That is expected rather than suspicious: the south lane was always
  LOW and always predicted LOW by both G and the baseline, so it changed
  neither side of the difference.
- **G and H tied exactly on validation at 120 s in both P94 and P97.** With 13
  validation windows, identical predictions are plausible. Validation
  predictions are not saved, so this is unverified.

**Not compared with P94** as if it were the same task, as the
pre-registration requires.


## P98 — the P97 result does not replicate on other hours of the same camera (2026-10-15)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P98.md`
(`3f5fd13`), which was written before any of the new footage was on disk. The
provenance and the eligibility counts were committed (`c252402`) before the
frozen model was run. Nothing was trained or reselected. The 60 s model is P97's
G seed 13 and the 120 s model is P97's H seed 42. Both match their sidecar
SHA-256, and both carry preprocessing hash `a4142d1ab333226b`, the same as the
new cache.

**Footage.** Eleven hourly NE 8th files, all continuous by the burnt-in clock,
with none excluded. Mon 13:08 is 53.5 minutes long in the source itself; it is
byte-identical to the project owner's copy and was kept at its actual length
(102 windows: five 10-minute blocks of 20 and one of 2). Mon 14:08 carries the
protocol's 149-sample buffer against P97's training. The camera is fixed across
all eleven files: the median lane-centre shift is at most 0.0063 of frame
width. Details are in `P98_PROVENANCE.md`.

| comparison | model − previous-window mean | 95% CI (10-min block bootstrap) | blocks / windows | verdict |
|---|---|---|---|---|
| **primary: Mon 07:08–15:08, 60 s, macro-F1** | **0.4268 − 0.4895 = −0.063** | **[−0.107, −0.009]** | 48 / 897 | **does not replicate; the model is worse** |

The secondaries, Holm-corrected as one family. None can rescue the primary.

| secondary | difference | 95% CI | p | Holm |
|---|---|---|---|---|
| west, 60 s | −0.084 | [−0.141, −0.000] | 0.049 | n.s. |
| north, 60 s | −0.090 | [−0.161, −0.006] | 0.036 | n.s. |
| east, 60 s | −0.018 | [−0.052, +0.010] | 0.29 | n.s. |
| dawn/dusk, 60 s | −0.254 | [−0.334, −0.130] | < 0.0001 | **significant, the model is worse** |
| Sunday daylight, 60 s | −0.015 | [−0.079, +0.062] | 0.78 | n.s. |
| 120 s, H | −0.294 | [−0.342, −0.231] | < 0.0001 | **significant, the model is worse** |
| accuracy, primary | **+0.094** | [+0.061, +0.128] | < 0.0001 | **significant, the model is better** |
| QWK, primary | −0.008 | [−0.127, +0.112] | 0.94 | n.s. |

The step-down stops at north: p 0.036 against a threshold of 0.010.

**Why: the model has never seen LOW.** On the primary stratum it predicts LOW
in **0 of 2,691** lane-decisions, against 129 true LOW. Its LOW F1 is 0, where
the baseline's is 0.288. The other two classes go the other way. MEDIUM F1 is
0.832 for the model against 0.744 for the baseline, and HIGH is 0.448 against
0.437. Accuracy rises because the model leans on MEDIUM, which is 69% of the
targets. Macro-F1 falls because it weights the missing class equally. P97's
training split held **1 LOW in 381** lane-decisions, and its validation split
held none, because the two training hours (Mon 15:08–17:08) were the afternoon
peak. P97's test held 1 LOW in 87. So P97's win was a win on MEDIUM and HIGH,
which its post-hoc MEDIUM/HIGH interval already said. This is the first test
with enough LOW to show that the model cannot produce the class.

**Exploratory, not pre-registered, and no rescue.** By hour, the model's
macro-F1 exceeds the baseline's at 10:08, 11:08, 13:08 and 14:08, the hours
closest to the training period. It falls below at 07:08, 08:08, 09:08 and
12:08, and the 07:08 and 08:08 files carry heavy low-sun glare. That pattern
fits drift in time of day, lighting or traffic away from two afternoon hours,
but eight hours cannot separate those three.

**What this establishes.**

- The P97 60 s result does **not** generalise across the day on the same
  camera, under the pre-registered metric.
- A model trained on two peak hours covers two of the three classes.
  Collecting more hours of the same peak would not fix this. Coverage of
  quieter periods would.
- Phase 2 (unseen cameras) with this checkpoint would test a model already
  known to be missing a class. That is a decision for the project owner, not
  a step to take by default.

**Unchanged:** the protocol, the model, the thresholds, the lanes and the P97
record. The licence remains unresolved (internal engineering only), and the
P96 undercount (14% / 27% / 41%) applies to every label here.

## P99a — a pretrained COCO YOLOv8m counts this camera better than ITD-xl in the afternoon (2026-10-15)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P99a.md`
(`d67ea67`), committed before any candidate ran on Bellevue footage. The 60
blind hand-counted frames of P95/P96 were scored under their own four regions.
**Harness check passed:** ITD-xl, run through the benchmark, reproduces
`data/corpus_bellevue/counts.csv` exactly on all 60 frames and all 4 lanes.

| candidate | 3-lane MAE (W/N/E) | − ITD-xl [95% CI, frame bootstrap] | verdict |
|---|---|---|---|
| ITD-xl, 992, conf 0.45 (reference) | 2.989 | — | — |
| YOLOv8s 640 | 4.644 | +1.656 [+1.367, +1.950] | worse |
| YOLOv8m 640 | 3.472 | +0.483 [+0.228, +0.733] | worse |
| YOLOv8x 640 | 3.067 | +0.078 [−0.200, +0.350] | not shown |
| YOLOv8s 1280 | 3.672 | +0.683 [+0.406, +0.956] | worse |
| **YOLOv8m 1280** | **2.400** | **−0.589 [−0.883, −0.306]** | **improves, selected** |
| YOLOv8x 1280 | 2.494 | −0.494 [−0.817, −0.172] | improves |

All COCO candidates ran at conf 0.25 and counted bicycle, car, motorcycle, bus
and truck.

**Where M1280 differs from ITD-xl:**

| lane | undercount, ITD-xl | undercount, M1280 | busy MAE, ITD-xl | busy MAE, M1280 |
|---|---|---|---|---|
| west | 14% | 14% | 2.1 | 2.5 |
| north | 27% | 15% | 5.1 | 4.6 |
| east | 41% | 15% | 7.1 | 3.6 |

- **The painted bicycle symbol** is reported as a bicycle in 13 of 60 frames
  by ITD-xl, and in 1 of 60 by M1280.
- **Costs, not only gains:**
  - Pearson correlation falls on west (0.82 → 0.76) and north (0.80 → 0.74).
  - On north in the quiet half, M1280 **overcounts by 15%**.
- **Still undercounts** on every lane.
- **Speed:** about 60 ms per frame on this laptop's RTX 4050, a proxy host
  (ADR-003).

**Not adopted.** The 60 frames are all from the busy afternoon. The protocol
selects, it does not adopt. Adoption waits on P99b, a blind count of 60
dawn, glare and dusk frames: that set also tests whether the morning LOW labels
are real. **87% of the corpus's LOW (297 of 343) comes from 06:08–08:08**, and
neither detector has been measured there. Nothing is rebuilt. P97 and P98
stand under ITD-xl.

## P99b — the morning LOW labels are real; YOLOv8m-1280 is not adopted (2026-10-15)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P99b.md`
(`81c3e89`). The 60 frames were chosen by seed before counting, from Mon
06:08, 07:08 and 08:08 and Sun 19:08. They were counted blind by hand
(`p99b_manual.json`; annotator unrecorded, all 60 counted in about 11 minutes
— these scenes average about 4 vehicles per lane). **Harness check passed:**
ITD-xl reproduces `data/corpus_p98/counts.csv` on all 60 frames.

| | ITD-xl (current) | YOLOv8m-1280 |
|---|---|---|
| 3-lane MAE | **0.911** | 1.267 |
| signed bias W / N / E | −0.08 / −0.05 / +0.17 | +0.53 / **+2.05** / +0.72 |
| Pearson W / N / E | 0.84 / 0.91 / 0.84 | 0.92 / 0.85 / 0.94 |
| LOW precision (frame count ≤ 2) | **0.845 [0.747, 0.931]**, 58 called | 0.950 [0.868, 1.000], 40 called |
| LOW recall | 0.817 [0.718, 0.910] | 0.633 [0.536, 0.730] |

**Decision 1, the morning LOW labels:** ITD-xl's LOW precision of 0.845 is
above the pre-registered 0.80 floor, so the labels are **usable**. The
interval's lower bound (0.747) is below 0.80. The labels are an honest
limitation, not a certainty. By hour, LOW precision is 1.00 at 06:08, 0.79 at
07:08 and 0.89 at Sun 19:08, but **0.44 at 08:08** (4 of 9), the hour with the
heaviest glare. That figure is reported, not a decision, at that sample size.

**Decision 2, M1280:** (M1280 − ITD-xl) MAE is **+0.356 [+0.161, +0.550]**.
The upper bound exceeds the +0.25 margin, so **M1280 is not adopted** and
ITD-xl stays. No corpus is rebuilt.

**What the two audits together say about the detector.** ITD-xl is accurate
when traffic is quiet (dawn, dusk, mornings: bias ≈ 0) and undercounts when it
is busy (P96: 14–41% in the afternoon). M1280 is the opposite: it is better
when busy (P99a) and **overcounts north by 47% when quiet**. Neither dominates.
The detector question is about the MEDIUM/HIGH boundary under heavy traffic.
LOW is not the problem. Fine-tuning, if it comes, targets busy-queue
occlusion. It stays deferred.

**For P99:** the existing ITD-xl counts are kept. P99 needs no detector rerun.

## P99 — coverage fixes the missing class and beats persistence, but Phase 2 is not passed (2026-10-16)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P99.md`
and its Amendment 1 (`4046cbc`, `8af7eb2`). All 20 runs trained on a corpus
holding **no test window** (`--no-test`). The selection was made on validation
only and committed (`21814b9`) before the test was read once. The two runs
finished before the overnight pause were kept, and the interrupted third was
retrained from the start under the same configuration.

**Selection:** G, **unweighted** loss, seed 7 (validation macro-F1 0.6196).
Pair means: G/none 0.6153, G/inverse 0.6074, H/inverse 0.6013, H/none 0.5721.
The G margin (0.008) is smaller than the seed spread within G/inverse.

**Primary, 26 test blocks, 390 windows:** macro-F1 **0.5875** against the
previous-window mean's 0.4852. The difference is **+0.102 [+0.041, +0.177]**,
so it **beats persistence**.

| recall | LOW (83) | MEDIUM (824) | HIGH (263) |
|---|---|---|---|
| model | **0.349** | 0.800 | 0.601 |
| previous-window mean | 0.361 | 0.729 | 0.369 |

**The Phase 2 conditions are conjunctive, and Phase 2 is NOT passed:**

| condition | result | |
|---|---|---|
| 1. LOW recall ≥ 0.50 (support ≥ 30) | 0.349, 29 of 83 | **FAIL** |
| 2. primary interval above zero | [+0.041, +0.177] | pass |
| 3. positive without any one lane or period | +0.080 to +0.111 across all 7 ablations | pass |
| 4. ONNX parity and test suite | argmax 1.0000, logit diff 2.6e-6, trained 1.0000 vs fresh 0.2256; pytest exit 0 | pass |

**Secondaries (Holm, 10 tests):**

- **Significant:**
  - east +0.096;
  - accuracy +0.101;
  - QWK +0.177;
  - MEDIUM recall +0.070;
  - HIGH recall **+0.232 [+0.108, +0.345]**.
- **Not significant:**
  - west +0.075;
  - north +0.094 (p 0.034, against a threshold of 0.0125);
  - LOW recall −0.012;
  - the objective, inverse − none on G: −0.034 [−0.058, −0.007], with p 0.015
    against a threshold of 0.010;
  - **the shortcut diagnostic.**

**The shortcut diagnostic is the finding that matters most.** The hour prior
knows only the time of day. It scores macro-F1 **0.6026**, +0.118 over
persistence, and the model − hour prior difference is −0.015 [−0.077, +0.119].
On this within-day split, the model's advantage over persistence is **not shown
to come from traffic beyond time of day**. The hour prior had every hour's
training blocks to draw on, which is exactly the limitation the protocol
stated in advance.

**Coverage did fix P98's failure.** The frozen P97 checkpoint, on the 330 test
windows from the P98 hours, still predicts **no LOW** (recall 0.000), with
macro-F1 0.414, −0.081 [−0.169, +0.026] against persistence. P99's selected
model scores 0.586 on the same windows and predicts LOW 69 times, 29 of them
correct.

**Reported, not substituted:** H with inverse weighting reaches test LOW recall
0.627 and macro-F1 0.596. It was not selected on validation, and swapping it in
after the test would void the protocol.

**What this establishes:**

- Training coverage was the blocker P98 exposed, and it is fixed.
- The model beats persistence on blocks of the hours it trained on.
- LOW is still under-recalled: 53 of 83 LOW were predicted MEDIUM, at a
  boundary of a 60 s mean ≤ 2 against ≥ 3 with a detector error of about 0.9
  per frame.
- An hour-of-day predictor does as well as the model.

The next blocker is whether the model uses the scene at all beyond time of day.
That needs a held-out-hour or held-out-day test, where an hour prior cannot be
learned. Phase 2 stays paused.

## P100 — on unseen hours the model uses the traffic, but beats neither the clock nor persistence (2026-10-16)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P100.md`
with Amendments 1–2 (`76a844f`, `3f18a5e`, `bc73d20`). P99's selected recipe
(G, unweighted) was retrained in two folds interleaved by hour, so every hour
was tested once by a model that never saw it. Each fold's model is the average
of three seeds (42, 1, 7), with no selection. The six runs were recorded
(`edd4481`) before the single test read.

**Part B, confirmatory:** 1,157 windows in 78 blocks across all 13 hours.
Support: LOW 275, MEDIUM 2,379, HIGH 817.

| | macro-F1 | LOW recall | MEDIUM recall | HIGH recall |
|---|---|---|---|---|
| model (seed average) | 0.4811 | **0.058** (16 of 275) | 0.859 | 0.504 |
| clock prior (nearest training hour) | 0.4522 | 0.000 | 0.879 | 0.507 |
| persistence | **0.5397** | 0.509 | 0.730 | 0.389 |
| model, input swapped (same hour, ≥ 24 min away) | 0.4266 | | | |

| question | difference [95% CI, block bootstrap] | Holm | answer |
|---|---|---|---|
| 1. unseen hours: model − clock prior | +0.029 [−0.005, +0.065], p 0.127 | threshold 0.025, n.s. | **does not beat the clock** |
| 2. model − persistence | −0.059 [−0.129, +0.031], p 0.191 | n.s. | **does not beat persistence** (point estimate below it) |
| 3. content: real − swapped | **+0.054 [+0.024, +0.087]**, p < 0.0001 | significant | **the model uses each window's traffic** |
| 4. LOW recall, against the 0.50 bar | 0.058; persistence − model +0.451 (significant) | — | **LOW collapses on unseen hours** (information only) |

**More secondaries:**

- **Fold A, model − clock:** +0.079 [+0.005, +0.118], p 0.027. This is **not
  significant** under Holm (threshold 0.0167).
- **Fold B, model − clock:** −0.008.
- **LOW recall, model − clock:** +0.058, not significant.

**Reported, not tested:**

- **Seeds:** individual seeds score 0.473 to 0.497, all above the clock prior
  and all below persistence.
- **By period, against the clock prior and against persistence:**

| period | − clock prior | − persistence |
|---|---|---|
| morning | +0.105 | −0.126 |
| midday | −0.005 | +0.112 |
| afternoon | +0.002 | +0.095 |
| Sunday evening | +0.077 | +0.010 |

**Reading, by the table fixed in advance:** *does not beat the clock, and real
input is better than swapped*. **It reads the traffic, but not enough to beat
the clock.**

- This revises Part A's exploratory hint. On unseen hours, swapping the input
  measurably hurts.
- It is not a demonstration of useful scene-specific forecasting: the model
  beats neither comparator.

**Why LOW collapses: coverage again.** LOW lives in 06:08–08:08 and Sun
19:08. Fold B holds out 06:08 and 08:08, which contain 213 of the 275 test
LOW, and trains on only **57** LOW decisions. Fold A trains on 191 and holds
out 62. With whole hours held out, too few quiet hours remain to learn the
class. The 13 hours hold **3 quiet hours**, and any hour-held-out design spends
some of them on test.

**Where each method is strong:**

- Persistence is strong on **LOW** (0.51 recall) and in the morning.
- The model is strong on **HIGH** (0.50 against 0.39) and at midday and in the
  afternoon, where it beats persistence by +0.10.
- Neither dominates.

**Part A, exploratory** (P99 checkpoint, already-read windows, reported
separately): real − swapped +0.047 [−0.007, +0.137].

**Unchanged:** P97, P98 and P99; the protocol; the thresholds. Phase 2 stays
paused.

## P101 — a count-only forecaster beats the vision model, the clock and persistence on unseen hours (2026-10-16, exploratory)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P101.md`
(`dcde584`), with the specification frozen before it ran. **Exploratory:** the
test windows are P100's, already read once. The comparison is paired on the
identical 1,157 windows (78 blocks), against P100's committed decisions. It
uses P100's folds, so every window was predicted by a model that never saw its
hour.

**The model.** Multinomial logistic regression with unweighted classes, one per
lane and fold, and nothing tuned or selected. Its 24 count features cover the
same 60 samples the vision model sees, with no clock feature. Scaling is fitted
on training windows only. It runs in seconds on a CPU.

| method | macro-F1 | LOW recall | MEDIUM recall | HIGH recall |
|---|---|---|---|---|
| **counts, logistic regression (primary)** | **0.6689** | 0.407 | 0.889 | 0.622 |
| counts, logistic regression, balanced (variant) | 0.6181 | **0.760** | 0.627 | 0.767 |
| counts, gradient boosting (variant) | 0.5810 | 0.204 | 0.874 | 0.595 |
| vision (P100, seed average) | 0.4811 | 0.058 | 0.859 | 0.504 |
| persistence | 0.5397 | 0.509 | 0.730 | 0.389 |
| clock prior | 0.4522 | 0.000 | 0.879 | 0.507 |

**Holm family, all three significant:**

| comparison | difference [95% CI, block bootstrap] |
|---|---|
| vision − counts | **−0.188 [−0.254, −0.099]** |
| counts − clock prior | **+0.217 [+0.143, +0.269]** |
| counts − persistence | **+0.129 [+0.097, +0.162]** |

All three count variants beat vision, the clock and persistence on point
estimates; the variants were not tested.

**Where the two disagree** (lane-decisions):

| true class | disagreements | counts right | vision right |
|---|---|---|---|
| LOW | 116 | 106 | 10 |
| MEDIUM | 402 | 236 | 165 |
| HIGH | 235 | 165 | 69 |

Vision is right on 244 decisions where the counts are wrong, so a combined
model has something to draw on. But counts lead in every class.

**Reading, by the table fixed in advance:** the interval is below zero, so
**the counts alone forecast better than the vision model here.** It is also
the **first model in this series to beat both persistence and the clock on
hours it never saw.**

**The limitation that bounds it (A32).** The labels are the same detector's
future counts. A count model inherits the detector's biases on both sides,
input and target. A vision model must infer counts the detector would produce,
including its undercount. So this result shows that **the images add nothing
beyond counts for forecasting these labels**. It does not show that images
carry no traffic information. P100's content control says they do. Only
human-verified future labels would make the comparison neutral.

**Not confirmatory.** These test windows were already read, and confirming
needs footage no model or analysis has touched. LOW recall for the primary is
0.407, below the Phase 2 reference of 0.50. The balanced variant reaches 0.760
but was not the pre-registered model. Phase 2 stays paused.

## P102 — C1 count forecaster v1 frozen; fresh confirmation can only come from other cameras (2026-10-16)

**Frozen** by the project owner's decision after P101.
`experiments/results/bellevue_pilot/c1_count_forecaster_v1.json`, SHA-256
`809d06eaf3152046f6178b1a75f9dc7a712142b3608c451ccd732fc0dc82ba46`, written by
`scripts/c1_freeze.py`.

- **The model:** P101's primary specification, unchanged (24 count features,
  no clock, unweighted logistic regression per lane), fitted once on all 1,157
  NE 8th daylight windows.
- **Checks:** a pure-Python reload reproduces scikit-learn on every window.
  CPU inference takes about 30 µs per window on this laptop, a proxy host,
  with features excluded.
- **Not promoted:** the balanced and boosted variants. **Not yet tested on
  footage it has not seen.**

**The source holds no other day of NE 8th.** Its 23 hourly files are one
continuous run, Sun 18:08 to Mon 16:08. The 13 daylight hours are spent, and
the 10 night hours have no measured detector validity. A fresh-footage
confirmation must therefore use **other cameras**, which makes it a
camera-transfer test.

Daylight hours already on disk:

| camera | hours |
|---|---|
| 150th Eastgate | Sun 18:08; Mon 06:08, 10:08, 14:08 |
| 150th Newport | Sun 18:08; Mon 10:08, 14:08 |
| 150th SE38th | Sun 18:08; Mon 09:08, 13:08 |
| 116th NE12th | only fragments |

**v1 is tied to NE 8th's layout.** Each lane's forecast reads all three lanes
in a fixed order (west, north, east), and another junction has no such
correspondence. A transfer test therefore needs a **lane-agnostic**
specification: one model shared across lanes, reading only the target lane's
own count history. It must be fixed before any other camera is counted.

## P103 — the count forecaster does not transfer to new cameras; persistence does (2026-10-16)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P103.md`
with Amendments 1–2 (`24997e7`, `fd60f3f`, `656233b`).

- **Before scoring:** the lanes were owner-placed and locked, all 10 files were
  continuous, and none was refused by the detector pass.
- **Thresholds and support** were committed (`6beb086`), calibrated from the
  Sunday 18:08 hours only.
- **Scoring:** one read, applying `c1L_v1.json` (sha `dbbd8df0…`) unchanged.

**Primary (calibrated per camera; pooled across Eastgate, Newport and SE38th;
Monday test hours, 788 windows, 41 blocks, 3,152 lane-decisions):**

| method | macro-F1 | LOW recall | MEDIUM recall | HIGH recall |
|---|---|---|---|---|
| C1-L (frozen, NE 8th) | 0.4834 | 0.287 | 0.168 | **0.981** |
| persistence | **0.7056** | 0.761 | 0.558 | 0.798 |
| calibration prior | 0.5605 | 0.726 | 0.393 | 0.680 |

| comparison (Holm) | difference [95% CI, block bootstrap stratified by camera] |
|---|---|
| C1-L − persistence | **−0.222 [−0.260, −0.183]** |
| C1-L − calibration prior | **−0.077 [−0.115, −0.035]** |

**Per camera, C1-L − persistence:**

| camera | difference | Holm |
|---|---|---|
| Eastgate | −0.284 [−0.325, −0.175] | significant |
| Newport | −0.344 [−0.369, −0.315] | significant |
| SE38th | −0.035 [−0.100, +0.018] | not significant |

The protocol's reading is **"no improvement over persistence"**: the NE 8th
gain does not transfer, and on new cameras the learned forecaster is worse
than the count it starts from. LOW recall, C1-L − persistence, is −0.473
(significant).

**Why** (an exploratory diagnostic, computed after scoring from the saved
windows):

- **C1-L forecasts too high on every camera:** +0.70 (Eastgate), +0.78
  (Newport) and +0.66 (SE38th) vehicles, above the actual future mean in 77–89%
  of windows.
- The OLS fit is centred on NE 8th's lane level (6.12 vehicles), and these
  lanes average 1.2–2.6.
- The calibrated boundaries span about one vehicle (Eastgate 0.13/0.97,
  Newport 0.53/1.53, SE38th 1.1/2.4), so a +0.7 bias moves most forecasts up a
  class. In the confusion matrix, 785 of 943 MEDIUM decisions are called HIGH.
- Persistence carries no learned level, so it transfers.
- **This also reframes P101.** Much of the count model's NE 8th advantage over
  persistence plausibly came from learning **that camera's** level, through
  regression toward its mean. That is real within one camera and does not move
  between cameras.

**Absolute 2/8 arm (secondary):**

- **HIGH is nearly absent here** (5 / 0 / 9 per camera, 14 pooled). It is
  flagged, and macro-F1 is effectively over LOW and MEDIUM.
- C1-L-cls − persistence is +0.017 [+0.010, +0.024] (Holm-significant), and
  C1-L − persistence is −0.036 [−0.046, −0.024].
- A small classifier edge on sparse lanes, with one class missing, does not
  change the primary reading.

**Limitation lanes (Amendment 2, reported, not tested).** C1-L − persistence:

| scored lanes | difference |
|---|---|
| without Newport lane_2 | −0.147 [−0.189, −0.106] |
| without Eastgate lane_1 | −0.221 [−0.258, −0.183] |
| without both | −0.143 [−0.184, −0.105] |

The conclusion does not depend on either lane.

**The lane profiles:**

- **Eastgate lane_1 is not a constant background.** Its standard deviation is
  0.70 and its modal share 0.72, in line with the camera's other lanes.
- **Newport lane_2 is nearly empty** (mean 0.37), as the occlusion predicted.
- **Unflagged and newly visible, SE38th lane_1 is nearly empty too** (mean
  0.19, modal share 0.99).
- C1-L − persistence per lane is negative or about zero on all 12 lanes. It is
  closest to zero on the busiest lanes (SE38th lanes 2 and 3, about 0.00), as
  the bias explanation predicts.

**Scope:** three cameras, one Sunday and Monday, with per-camera calibration.
The NE 8th models, P97–P102 and their records are unchanged.

**Disclosed defect in P103's support table.** The committed thresholds were
stored rounded to four decimals (Eastgate q33 0.1333 for 2/15). The
pre-scoring support count used the unrounded values. Future means are
multiples of 1/30, so **21 of 3,152 test decisions (0.7%)**, sitting exactly
on a boundary, fall one class higher under the committed thresholds: 18 at
Newport, 3 at Eastgate, 0 at SE38th. Scoring used the committed thresholds,
as the protocol requires, so the support behind the scores is LOW 543 /
MEDIUM 943 / HIGH 1,666, against the table's 555 / 940 / 1,657. Against a
−0.222 difference, this changes no conclusion. `p103_eval.py` now stores
thresholds at full precision for any future run. P103 is **not** rescored.

## P104 — persistence adopted as the prototype's transferable forecaster; contract amended additively (2026-10-16)

**Decision by the project owner, after P103.**

- **Persistence** becomes the prototype's transferable forecasting path. It was
  the best method measured on new cameras: macro-F1 0.706 against C1-L's 0.483.
- **C1-L's NE 8th result** (P101) stays documented as a within-camera result,
  not a claim of generalisation.
- **Change-based forecasting** (predicting a lane's change from its own recent
  level) is the next research experiment. It runs only under a new
  pre-registration on genuinely untouched footage.
- **Per-camera fitting** is deferred until such footage exists.
- **C2 (vision)** stays open until independently verified future labels
  exist.

**Implemented:**

- **`edge/persistence.py`**
  - **The method:** exactly as P94–P103 scored it. The class of the mean of
    each lane's last 30 counts (2 s apart) forecasts the next 60 s, with that
    camera's thresholds.
  - **Calibration:** `calibrate` applies ADR-017 (q33/q67) to a disjoint
    calibration period, at full precision. The P103 rounding defect cannot
    recur here.
  - **Confidence:** the class's **measured** P103 precision (LOW 0.762,
    MEDIUM 0.555, HIGH 0.800), not an invented probability. The gate is
    `None`.
- **`persistence_v1.json`**, frozen by `scripts/persistence_freeze.py`, SHA-256
  `2431c6641b9c6bd2f0ad823aa293ed8b13048b96825a0ff8c9ff87871c70e110`.
  - **Thresholds:** the three P103 cameras' calibration-hour values, which the
    script verifies are equal to P103's own; NE 8th's absolute 2/8, validated
    for LOW by P99b.
  - **Measured performance:** P103 0.7056 pooled on new cameras; P100 0.5397 on
    NE 8th's unseen hours.
  - **Model id:** `persistence@2431c6641b9c`.
- **Contract (`contracts/mqtt.py`), additive:** `MODEL_ID` now also accepts
  `persistence@<12 hex>`, the spec's hash. Every earlier id still matches, and
  anything else is still refused. `SCHEMA_VERSION` stays 2, because no
  existing payload changes meaning. A consumer pinned to an older copy of the
  module would refuse persistence ids; the server imports this module, so it
  does not.
- **Heartbeat truthfulness (`edge/node.py`):** `mfstnet_active` is now set only
  by an MFSTNet forecast. A persistence forecast is published like any other,
  but never reads as the vision model running.
- **Tests:** `tests/test_persistence_forecaster.py` pins the method, the
  window, the full-precision boundary, the spec-derived id against the
  contract, the measured confidence, the heartbeat flag and refusal of an
  uncalibrated camera. Locally, it also reproduces P103's persistence decisions,
  differing only on exact-boundary means where P103's rounded thresholds did.
  The full suite passes.

**Not done, deliberately:**

- **Persistence is not fed into the PPO state** (indices 11–14). Whether
  forecasts drive signal timing, and how absence is represented, is P97a and a
  separate decision. A good forecast is not evidence that a control policy is
  safe.
- **The near-empty lanes stay visible in every report** (Newport lane_2 and
  SE38th lane_1). No lane is excluded on its scores.

## P105 — a level-free change forecaster beats persistence on counts, not on classes, on untouched footage (2026-10-16)

**Measured** under `experiments/results/bellevue_pilot/PREREGISTRATION_P105.md`
with Amendments 1–4 (`0c59a54`, `6129ed9`, `9e225c0`, `17bd58d`, `9830964`).

- **Model:** ridge (`p105_ridge_v1.json`, sha `73532968…`), fitted only on
  already-used footage before any P105 file existed, applied unchanged.
- **Footage:** 16 files downloaded by rule. **116th NE12th was excluded whole**:
  it has no burnt-in clock, and its test files are truncated at the source. No
  substitute was chosen. No camera moved (overlay-verified).
- **Thresholds and support:** committed at full precision (`108ff8e`).
- **Scoring:** one read.

**Test:** Eastgate, Newport and SE38th, Monday 07:08, 12:08 and 16:08; 904
windows in 48 ten-minute blocks.

| camera | windows | blocks | footage |
|---|---|---|---|
| Eastgate | 342 | 18 | three full hours |
| Newport | 342 | 18 | three full hours |
| SE38th | 220 | 12 | 48.7 + 60 + 9.4 min |

Support: LOW 565, MEDIUM 670, HIGH 2,381.

| method | macro-F1 | count MAE | bias | LOW / MEDIUM / HIGH recall |
|---|---|---|---|---|
| persistence | 0.7162 | 0.972 | −0.008 | 0.782 / 0.491 / 0.877 |
| **ridge (level-free)** | **0.7324** | **0.748** | −0.017 | 0.782 / 0.506 / 0.902 |
| trend (continue the last change) | 0.5392 | 1.663 | +0.091 | 0.756 / 0.270 / 0.726 |

**Primary family (Holm):**

| comparison | difference [95% CI, block bootstrap stratified by camera] | verdict |
|---|---|---|
| persistence − ridge, count MAE | **+0.224 [+0.181, +0.271]** | **significant: ridge's counts are closer** |
| ridge − persistence, macro-F1 | +0.016 [−0.002, +0.036], p 0.079 | not significant |

**Reading, by the table fixed in advance:** *better counts, classes unchanged.*
Ridge forecasts the next minute's count 23% closer than persistence on
cameras and hours it never saw, and the improvement holds on every camera:

| camera | ridge MAE | persistence MAE |
|---|---|---|
| Eastgate | 0.718 | 0.968 |
| Newport | 0.570 | 0.694 |
| SE38th | 1.072 | 1.410 |

The gain is not large enough to change congestion classes significantly when
pooled.

**Secondaries (Holm):**

| comparison | difference | Holm |
|---|---|---|
| trend − persistence, macro-F1 | −0.177 | significant: worse |
| trend − persistence, MAE | worse by 0.691 | significant |
| ridge − persistence, LOW recall | 0.000 (identical) | — |
| per camera, ridge − persistence macro-F1: SE38th | **+0.049 [+0.012, +0.088]** | significant |
| per camera: Eastgate | +0.033 [−0.002, +0.073] | not significant |
| per camera: Newport | −0.008 | not significant |

Continuing the last change is clearly harmful, as expected at a signalised
junction (P93's two-minute cycle).

**What this establishes:**

- **The level-free design fixed P103's failure mode.** Ridge's bias is
  −0.017 vehicles, against C1-L's +0.66 to +0.78 in P103, because it cannot
  carry a camera's level.
- **This is the first learned forecaster in the project to beat persistence on
  a pre-registered primary, on untouched cameras and hours.** The metric is
  count error.
- Its coefficients forecast mostly the 2-minute mean. Averaging over a full
  signal cycle predicts the next minute better than the last half-cycle does.

**What it does not establish:**

- a congestion-class improvement (pooled macro-F1 is not significant);
- anything at 116th NE12th, which was excluded;
- independent confirmation of how the ridge specification was selected (stated
  in Amendment 1);
- anything about signal-control safety.

The near-empty lanes (Newport lane_2, SE38th lane_1) are kept and marked.

**No promotion follows automatically.** Persistence v1 remains the prototype's
forecaster until a separate decision.

## P106 — two forecasting roles implemented: persistence for the class, ridge for the count (2026-10-16)

**Decision by the project owner after P105, recorded as
[ADR-027](decisions/ADR-027-forecasting-roles.md)**, which amends ADR-026's
deployed forecaster and PRD §7.

- **Class:** persistence v1 stays the congestion-class forecaster.
- **Count:** the frozen ridge v1 becomes the **next-minute vehicle count**
  forecaster.
- **Not connected:** neither feeds signal timing.
- **Deferred:** the larger Option A study.

**Implemented:**

- **Contract** (`contracts/mqtt.py`, additive, schema still v2):
  - a `CountForecast` payload on its own topic `stms/{id}/count/forecast`, at
    QoS 0 like predictions;
  - model ids match `ridge@<12 hex>` only, and are disjoint from the class
    pattern;
  - counts must be finite and in [0, 200] per approach, and the horizon is
    60 s;
  - an approach the edge cannot forecast is absent, never 0.
- **`edge/samples.py`**, a buffer shared by both edge forecasters:
  - an exact lane set is required, because a missing lane is not a zero;
  - counts must be whole and plausible;
  - out-of-order samples are refused;
  - **a gap over 3 s resets the window**, so no forecast joins two stretches of
    traffic.
- **`edge/count_forecast.py`:**
  - serves only the spec with the frozen SHA-256 (`73532968…`), as model id
    `ridge@73532968dcf2`;
  - its features are identical to P105's, by test;
  - a non-finite or out-of-range forecast is refused, not published.
- **`edge/persistence.py`:** now uses the shared buffer, with the same
  checks. Its existing API is unchanged and its timestamp is optional.
- **`edge/node.py`:** `publish_count_forecast` publishes on the count topic,
  and never sets `mfstnet_active`.
- **Server:**
  - a separate `count_forecasts` table;
  - `POST /count_forecast/{id}` and `GET /count_forecast/{id}/latest`;
  - **both** latest-forecast responses now carry `role`, plus `age_s` and
    `stale` from the server's own clock (stale = older than the 60 s horizon).
    The count response also lists `missing_approaches` and states that it is a
    point estimate, not a class, and not used for signal timing;
  - MQTT ingest subscribes to both topics and routes each one to its own
    store.
- **Tests:** `tests/test_count_forecast.py` (22) covers:
  - the forecaster reproduces P105's method, and a tampered spec is refused;
  - the gap reset, the out-of-order refusal and the four kinds of bad sample;
  - the contract's refusals, including a class named `ridge@`;
  - topic and QoS;
  - the server keeping count and class apart, with real zeros kept and absent
    approaches listed;
  - the stale flag and ingest routing.

  The full suite passes.

**Not done:**

- **No dashboard is built** (ADR-008). The two `/latest` endpoints are what one
  would read, under ADR-014's two-panel rule.
- **The PPO state's 0.0-for-missing** (P97a) is unchanged, because the
  controller is not connected.

## P107 — a minimal read-only dashboard, to ADR-008's shape and ADR-014's two-panel rule (2026-10-16)

**Decision by the project owner after P106:** one small presentation and
observability task. No training, no Option A, no controller integration, no
push.

**Built** (`dashboard/`, React 18.3.1 + Vite 5.4.11 at exact pins; vitest):

- **Live region, two separate panels** (ADR-027 roles):
  - the **next-minute count** (ridge) as a point estimate;
  - the **congestion class** (persistence).

  Each shows model id, role, time received, age and staleness, all from the
  API, never hard-coded. A missing approach shows *no forecast*, never 0 and
  never LOW, and a real zero stays a zero. A stale forecast is labelled and
  dimmed. A response that fails validation is shown as *invalid*, with the
  reason, and never partly. The failures caught are a wrong role for the
  panel, an unknown model id, out-of-range or non-finite values, an unknown
  approach, or `missing_approaches` disagreeing with the values. API errors
  (404, 5xx, unreachable, non-JSON) each have their own state.
- **The P97a warning stays visible** in the live region: the controller's
  state contract encodes a missing approach as 0.0, the same as LOW. The page
  does not imply it fixes that.
- **No live accuracy** appears anywhere (ADR-014: it would be circular against
  detector-derived labels).
- **Results region,** separated from live: `GET /evidence` (new, read-only)
  builds the panel from the **committed** P105/P103 result files. Each study
  names its file, commit and date (from git), scope (windows, blocks, cameras,
  exclusions) and every difference **with its direction** ("persistence −
  ridge … positive favours ridge"). It is labelled *historical evaluation
  evidence, not a live performance guarantee*, with its limitations listed.
  Evidence is fetched until it first succeeds, then never again.
- **Read-only by construction:** the API client issues only `GET`, and only to
  `/count_forecast/{id}/latest`, `/prediction/{id}/latest` and `/evidence`.
  Tests pin the allow-list and scan the source for write calls. The server
  serves the build at `/dashboard` from the same origin.

**Tests:**

- dashboard, 12 (`npm test`): read-only API, error states, missing never
  zero/LOW, stale, invalid and mismatched roles, region separation and the
  P97a warning, evidence retry;
- `tests/test_dashboard_evidence.py`, 4: the numbers equal the committed files,
  the difference directions are correct, each study names its file and commit,
  and the endpoint refuses POST;
- the full Python suite passes.

**Checked end to end in a browser:**

- **The real edge forecasters** ran on real Newport counts, with the
  housing-occluded approach left unmapped, so S is missing. They posted
  through the server.
- **Fresh and stale intersections** both rendered correctly.
- **Desktop and 375 px phone width:** no horizontal scroll. Evidence rows stack
  into labelled cards, so the verdict is never off-screen. Two defects were
  found by looking and fixed before commit: an unlabelled difference
  direction, and a one-shot evidence fetch that could wait forever.

**Not done (scope):**

- WebSockets: it polls every 2 s, within the PRD's refresh budget;
- charts, ADR-014's deferred-agreement ribbon and the detection overlay;
- authentication: the page cannot reach a control endpoint;
- `dashboard` tests in CI: CI has no Node job, so `npm test` is run locally.

## P108 — P97a investigated: the missing-forecast zero is latent today, exposed in one place, and fixable before it costs anything (2026-10-16)

**Investigation only; no code changed.** The full trace, options and the
pre-registration outline are in
[INVESTIGATION-P97a-missing-forecasts.md](INVESTIGATION-P97a-missing-forecasts.md).

- **The defect:** indices 11–14 encode `{LOW, MEDIUM, HIGH} → {0, 0.5, 1}`,
  and a missing forecast is also 0.0. The spec mandates this
  (`zero_when_mfstnet_unavailable`), `to_state_values` implements it, and
  three tests pin it.
- **Latent:** no path feeds a forecast to any controller today.
  - The server's `propose()` reads counts only.
  - `Counts.forecast` and `forecast_age_s` are declared but read by nothing.
  - `PPOController` zeros 11–14.
  - The environment refuses live forecasts.
- **Exposed:** both server prediction responses publish `state_11_14` with 0.0
  for an absent approach.
- **Changed since ADR-020:**
  - **One full PPO checkpoint now exists** (no-forecast arm, 500,000 steps,
    contract `24ad1c99…`). ADR-020's age channel would invalidate it.
  - **Absence is now per approach** (ADR-027 cameras that cannot see an
    approach). ADR-020's reserved zero covers that; its shared age channel
    still covers staleness.
  - **Indices 11–14 now carry a role, not MFSTNet.**
  - **Any forecast-aware PPO is blocked by P52 anyway,** so the encoding can
    be fixed before anything depends on it.
- **Recommended:**
  - **Option A now:** the API reports absence as null, and `to_state_values`
    refuses to zero-fill implicitly. It invalidates nothing.
  - **Option D before any forecast-aware training:** ADR-020's encoding,
    amended for ADR-027, plus a fallback switch to the no-forecast policy when
    a forecast is absent or older than 10 s. This means retraining the one
    no-forecast checkpoint, under a pre-registered safety evaluation: never
    significantly worse than the no-forecast policy under injected dropout and
    staleness.
- **Awaiting the project owner's decision.** The controller stays disconnected.

## P109 — P97a Option A: a missing approach is refused or null, never 0.0 (2026-10-16)

**Decision by the project owner after P108:** approve Option A, accept Option
D as the plan, and amend ADR-020.

- **`CongestionPrediction.to_state_values`** now **refuses** a prediction with
  a missing approach (`ContractError`, naming it) instead of returning 0.0,
  which is also LOW. There is no implicit zero left in the contract.
- **New `to_state_values_or_none`** returns `None` for an absent approach. It
  is for display and APIs only.
- **Server:** `state_11_14` in both prediction responses carries **`null`**
  for an absent approach (Newport-style `[0.5, null, 0.5, 0.5]`), alongside
  `missing_approaches`.
- **Tests updated with the behaviour:**
  - the contract test now asserts the refusal, and that a real LOW stays 0.0
    beside a `None`;
  - the live server test now asserts `null`, where it previously pinned
    "indistinguishable from LOW".

**Unchanged on purpose:** the simulator, `PPOController` and the 16-dim
layout. The no-forecast arm's 11–14 are the arm's declared world, not a
substituted value. Option D, under amended ADR-020, changes that layout next.

## P110 — P97a Option D, step 3: the amended 17-dim state and the fail-safe gate (2026-10-16)

**Implements ADR-020 as amended** (`a1e09e0`). The controller stays
disconnected from signal timing.

- **`spec.yaml`:**
  - **Layout:** `dim: 17`. Indices 11–14 are the class forecast per approach,
    `forecast_class_value` LOW/MEDIUM/HIGH → 1/3, 2/3, 1, with **0.0 reserved
    for "no forecast"**. Index 16 is `forecast_age = min(age, 10) / 10`.
  - **Fallback:** `forecast_unavailable` is **one named operation**: class
    slots read absent and the age reads 1.0. It replaces
    `mfst_pred_divisor: 2` and `zero_when_mfstnet_unavailable`.
  - **Digest:** the observation contract digest changes (P53), and a test pins
    that it is no longer `24ad1c99…`.
- **`simulation/forecast_state.py`, the encoder:** `forecast_slots` is the
  only route to 11–14 and 16. An absent or unknown class reads absent, never a
  class. A message without a valid age is refused. A layout where a class
  equals the absent value is refused.
- **`simulation/forecast_state.py`, `ForecastGate`:** the owner's rule that the
  **validity of every required input** decides.
  - **Webster** if counts or queues are missing, non-finite or negative for
    any approach.
  - **The no-forecast policy** if the forecast message is absent, older than
    10 s (inclusive bound), invalid in age, or missing or invalid for **any**
    required approach. Partial coverage is not enough.
  - **The forecast-aware policy** only when everything is complete, fresh and
    valid.
  - **Recovery** needs a complete, fresh message. Every switch is logged with
    its reasons.
- **The environment and `PPOController`** build the forecast slots through the
  encoder. `PPOController.observe` **refuses** a missing or invalid count or
  queue, where it used to read it as 0 vehicles: the same P97a defect, in
  counts.
- **`CongestionClass.to_state_value`** is now 1/3, 2/3, 1, and a test checks it
  equals the spec. The server's `state_11_14` uses the same values, with
  `null` for absent.
- **The 500,000-step no-forecast checkpoint is archived** to
  `models/ppo/_pre_adr020/` with a README. Its contract no longer matches, so
  it is kept as evidence, out of `discover_checkpoints()`. **Step 4 retrains
  it** under the amended layout.
- **Tests:**
  - **New:** `tests/test_forecast_state.py`, 22 tests covering encoding,
    partial failure, the 10 s boundary, invalid classes, invalid counts to
    Webster, recovery and the switch log, and the policy input refusing a
    missing count.
  - **Rewritten:** the twelve tests that pinned the old layout now assert the
    amended one.
  - The full suite passes.

## P111 — documentation and CI audit after P110; nothing pushed, and why (2026-10-16)

The project owner asked whether documentation and GitHub were being
maintained.

**Documentation.** Four documents still described the pre-P110 world, and two
of them **instructed the defect**:

- **The Execution Manual §4.3** said "zero indices 11–14". It now shows the
  17-dim layout, the reserved 0.0, `forecast_age`, and "never write a value
  for a missing forecast or count yourself". It routes through
  `forecast_slots` and `ForecastGate`.
- **CLAUDE.md** had the same "zero indices 11–14" convention, a "16-dim
  contract" in three places, and "ADR-020 not implemented". All are
  corrected.
- **The README** described the state as 16-dim; corrected.
- **docs/README.md** now indexes the P97a investigation and the new
  [PUBLICATION-READINESS](PUBLICATION-READINESS.md). The build log gains rows
  for P108–P111.

**GitHub. Nothing is pushed, deliberately.** The repository is **PUBLIC**.
130+ unpushed commits contain **337 Bellevue-derived files** (licence
unresolved, internal only) and **19 third-party video preview frames**, and
**18 such frames are already public** on `main`. Pushing would publish them.
The options, with a recommendation (make the repository private, push, open a
draft PR; then the licence or a sanitised public branch), are in
PUBLICATION-READINESS. It is the owner's decision.

**CI would have failed on the first push, and is fixed.**

- **What was wrong:**
  - `origin/main` last ran CI on 2026-08-20, and 47 of the branch's 74 test
    files have never run there.
  - The `fast` job's exact command **failed at collection**:
    `test_checkpoint_guard.py` imports torch via `scripts/train_ppo.py`.
  - The new guards needed numpy and FastAPI that the job does not install.
- **The fix, which keeps the workflow's own rule (install what a guard needs
  rather than let it skip):**
  - the `fast` job installs pinned numpy, fastapi, pydantic and httpx;
  - the torch- and OpenCV-only files move to the `model` job, which gains
    `opencv-python-headless`;
  - a new `dashboard` job runs `npm ci`, `npm test` and `npm run build`.
- **Verification:** the `fast` command passes in a clean environment with
  exactly its install list, and the dashboard commands pass from a clean
  `npm ci`. The `model` job can only be confirmed on the runner.

## P112 — P97a step 5 pre-registered in two parts; the Part 1 harness frozen before it runs (2026-10-16)

**Approved by the project owner as a two-part protocol**
(`experiments/results/safety/PREREGISTRATION_P112.md`, `702566d`). **No part
has run.**

- **Part 1, fault-handling integrity,** runs after the retrain finishes.
  - **Setup:** five seeds; a fixed, seeded schedule of missing (bursts), stale,
    boundary (10.0 and 9.9 s), single and double approach dropout,
    invalid-class, and corrupt count and queue faults.
  - **Recovery is defined per message**, with no carry-forward of approaches.
  - **Six strict invariants:** any single violation fails, nothing is
    averaged.
  - **The forecast stream is labelled "ground-truth-now (not a forecast)",**
    because the invariants concern validity, not accuracy.
- **Part 2, non-inferiority,** is frozen now and **PENDING** until P52, ADR-021
  and a forecast-aware policy exist.
  - **Design:** 30 paired benchmark seeds, conditions C0, C1 and C2.
  - **Margins:** +5% `mean_wait_s` and +1 `starvation_event`.
  - **Statistics:** a one-sided bootstrap, with Holm over six tests.
  - **Labelling:** oracle inputs are labelled as such.

**Amendment 1, before any run.** Under corrupt counts the protocol said
"Webster", but the benchmark's Webster re-times from those very counts.
Following FR-A06's own `LocalWebster`, the deciding controller is the
**degraded-mode fixed 30 s cycle**. Holding the last valid counts was
rejected, because it trusts stale counts.

**Frozen before running:**

- **`simulation/gated_controller.py`:** `GatedController` gives the gate's
  verdict to exactly one of the fixed cycle, the no-forecast policy or the
  forecast-aware policy. A `Probe` stands in for the forecast-aware policy
  until P52.
- **`scripts/p112_part1.py`:** it checks every invariant against **its own
  record of what it injected**, never the gate's reasons, and refuses any
  checkpoint but the full retrain.
- **A harness check** (`--check`, one seed, 900 s, smoke checkpoint, scratch
  output, never the result) exercised every fault type and all three deciders,
  with 0 violations.
- **`tests/test_p112_harness.py`:** proves the checker can fail. A gate that
  ignores staleness, accepts partial coverage, ignores corrupt counts, or is
  too strict at the 10 s bound is each caught by the matching invariant.

## P113 — P97a step 5, Part 1 passed: the fail-safe gate handled every injected fault, with zero violations (2026-10-16)

**The retrain was verified before scoring** (`scripts/verify_ppo_checkpoint.py`,
`7230abd`). For `ppo_no-forecast_saturated_keep_or_switch_seed42.zip`,
SHA-256 `a7f06ba8c21085155bda998e23163846b7432762048b4ad9343a748339e20985`:

- **Training completed:** the model's own `num_timesteps` is **501,760**, 245
  whole 2,048-step rollouts, at or above 500,000. It is not a smoke run.
- **The layout matches:** the observation space is 17, contract
  `59579c2dd3be10ed` is the current digest, and `assert_compatible` passes.
- **The policy runs:** a legal decision is made.

The 16-dim predecessor stays archived in `models/ppo/_pre_adr020/`.

**Part 1, run once** under `PREREGISTRATION_P112.md` (`702566d`) with
Amendment 1 and the frozen harness (`fd637db`). Five seeds, saturated,
1800 s. **The stream is ground-truth-now, not a forecast.**

| seed | decisions | forecast (probe) | no-forecast | fixed cycle | logged changes | violations |
|---|---|---|---|---|---|---|
| 42 | 107 | 64 | 37 | 6 | 37 | **0** |
| 1 | 109 | 62 | 44 | 3 | 41 | **0** |
| 7 | 103 | 51 | 43 | 9 | 47 | **0** |
| 13 | 103 | 56 | 39 | 8 | 45 | **0** |
| 21 | 104 | 54 | 42 | 8 | 39 | **0** |
| **total** | **526** | **287** | **205** | **34** | **209** | **0** |

**Faults injected:**

| fault | count |
|---|---|
| F1 missing message (in bursts) | 148 |
| F2 stale | 25 |
| F2b boundary ages (10.0 and 9.9 s) | 20 |
| F3 approach dropout | 42 |
| F4 invalid class | 9 |
| F5 corrupt count | 28 |
| F6 corrupt queue | 7 |

**Every one of the six invariants held on every decision of every seed:**

| invariant | what held |
|---|---|
| I1 | no invalid input reached a forecast-aware decision; all 287 probe calls were on complete, fresh, valid messages |
| I2 | no missing approach was ever encoded as a class, and the age slot was exact |
| I3 | every one of the 209 changes of decider was logged with its reason |
| I4 | every corrupt count or queue (35 faults) went to the degraded-mode fixed cycle, whose action was applied |
| I5 | recovery happened only on a complete, fresh, valid message, and boundary ages were accepted |
| I6 | all five episodes completed |

**What this establishes:** the gate and the encoder handle every specified
fault exactly as ADR-020 (as amended) requires, in these SUMO conditions.

**What it does not establish:**

- **Not forecast accuracy:** the stream is ground truth, not a forecast.
- **Not non-inferiority:** that is Part 2, which stays **PENDING** until P52,
  ADR-021 and a forecast-aware policy exist.
- **Not safe real-world signal control.**

The episodes' delay figures are not a comparison and are not interpreted.
**The controller stays disconnected from signal timing.**

## P114 — P52 inspected before any training: a perfect forecast has little to say in the current simulation (2026-10-16)

**Nothing was trained.** The owner asked for P52 to be inspected before any
run. The full record is
[INVESTIGATION-P52-surrogate-arm.md](INVESTIGATION-P52-surrogate-arm.md).

**P52 stands as reported.**

- `surrogate` and `no-forecast` are still one config (`use_mfstnet: false`
  for both).
- No forecast producer exists in training.
- `train_ppo.py --arm surrogate` would still write a no-forecast policy
  under the surrogate name.
- No test compares the observations of two arms.

**The 17-dim layout (P110) and the gate (P113) need no change** to carry a
forecast. The forecast-aware policy is only consulted on complete, fresh
messages, so it trains on exactly that distribution. Its age channel must be
real: an older message carries an older forecast.

**New measurement** (`scripts/p52_headroom.py`, results in
`experiments/results/p52/`):

- **Setup:** seeds 100–104, disjoint from the evaluation seeds 0–29; §14.1
  thresholds.
- **Method:** each decision is paired with the class realised 60–75 s later,
  which is what ADR-021's oracle would supply.
- **At saturation, under the no-forecast policy:**
  - the oracle differs from the current class (persistence) on **6.9%** of
    2,160 approach-decisions, all LOW↔MEDIUM;
  - **HIGH occurs 0 times**.
- **The other regimes:** light 13.6%, oversaturated 5.2%.
- **The causes:**
  - the demand is constant-rate `vehsPerHour` flows, identical on all four
    approaches;
  - the §14.1 thresholds were set for camera counts, not for a 2-lane SUMO
    approach.
- **Disclosed:** an exploratory run on seeds 0–2 came first and is not cited.

**Consequences for ADR-021 (Proposed):**

- **The ceiling, as specified, tests a near-constant input.** A null result
  would not be the decisive result ADR-021 says it is.
- **Its macro-F1 grid has no meaning here:**
  - persistence already scores 0.569 (3-class), so 0.33, 0.50 and 0.65 are
    worse than what the policy can compute;
  - with HIGH absent, even the oracle scores 0.667, so 0.80 and 1.00 cannot
    be reached.

**Rejected: running the ceiling now** on the grounds that the checkpoint and
the gate are ready. The run would be uninformative, and that is exactly what
the inspection was asked to catch.

**Pending with the owner (D1–D4):**

- **D1:** add a time-varying scenario, gated by a pre-registered headroom
  test.
- **D2:** define the oracle as a SUMO lookahead under the frozen no-forecast
  policy.
- **D3:** sweep quality relative to persistence (an ADR-021 amendment).
- **D4:** three training seeds per arm.

ADR-021's go/no-go still needs the guide. **Part 1 stays passed (P113), Part 2
stays PENDING, and the controller stays disconnected from signal timing.**

## P115 — a scenario for ADR-021 pre-registered, and the state-lookahead oracle rejected on measurement (2026-10-16)

The owner approved D1–D4 of
[INVESTIGATION-P52](INVESTIGATION-P52-surrogate-arm.md):

- **D1:** a separate time-varying scenario;
- **D2:** an oracle simulated under the frozen no-forecast policy;
- **D3:** quality from persistence to oracle;
- **D4:** three training seeds per arm.

`PREREGISTRATION_P115.md` (`b952f20`) was committed before the scenario code
existed. It fixes four things:

- **the scenario family** (`pulsed`) and its parameter bounds;
- **a design budget** of 5 logged iterations on seeds 300–309;
- **a one-time qualification** on seeds 200–219;
- **six criteria:**
  - headroom;
  - class coverage;
  - not recoverable from the state;
  - determinism and demand alignment;
  - an attainable quality grid;
  - not breakdown.

**The oracle mechanism changed from what P114 proposed, within D2's
definition.** A SUMO `saveState`/`loadState` lookahead was spiked on the
constant `saturated` regime, with no scenario data, and rejected:

- **Too slow:** 1.4 s per lookahead, so an 1800 s episode took 522 s against
  6.3 s (about 83×).
- **Not reproducible:**
  - The default state precision is 2 decimals.
  - Even at 12 decimals with the RNG saved, two continuations from one loaded
    state agreed on 0.97 of classes and 0.67 of counts.
- **Crashes:** repeated backward loads crashed SUMO in three configurations.

**Adopted:** the **replay oracle**. Run the frozen policy on the seed once,
record every second, and read the count at *t* + 60 s. Its determinism is
verified, not assumed.

**Training-episode seeds moved clear of evaluation.** An episode's seed was
the training seed plus the episode index, so D4's training seeds 1 and 7
would have trained on evaluation seeds 1–29. On a scenario where the seed is
the demand, that is leakage. Scenario episodes now use seeds from 1,000,000
upward. Constant regimes keep the historical rule, so existing checkpoints
stay reproducible (tested).

## P116 — two harness facts that bound what existing and future SUMO numbers mean (2026-10-16)

**(a) The runner does not apply `keep_or_switch` the way the training
environment does. Open; it must be fixed before ADR-021 is evaluated.**

| | `TrafficSignalEnv` (training) | `run_episode` (evaluation) |
|---|---|---|
| a "keep" | lasts 5 s | is clamped up to a 10 s green (`min_green_s`) |
| the 90 s maximum | forces a switch after 90 s of keeps | is applied per request only, so a run of keeps is never forced |

How much this matters depends on the policy:

- **At `saturated`, the current no-forecast policy requests a switch on 96% of
  decisions** (217 of 227 on seed 100). It is effectively a minimum-green
  alternation, so the two harnesses behave alike.
- **At `light`, the same policy keeps on 80% of decisions,** and there they
  diverge.

A forecast-aware policy that anticipates traffic would hold phases, so
ADR-021 cannot be evaluated through the runner as it stands. **No committed
performance result is affected:**

- `benchmark_ppo` used the `phase_duration` checkpoint;
- P113 Part 1 tested gate integrity, not delay.

**(b) In the constant regimes, a seed does not vary the arrivals.**

- **What a seed does vary:** `build_sumo_demand.py` writes `vehsPerHour`
  flows, which SUMO inserts evenly spaced. Measured on `saturated`, seeds 1
  and 2 load **identical vehicles at identical seconds** but draw different
  vehicle types. A seed therefore varies vehicle mix, lateral placement and
  driver behaviour, never the demand.
- **What that means for existing intervals:** the 30-seed CIs on those
  regimes measure sensitivity to the vehicle mix, not to arrival variability.
- **What it does not change:** the existing numbers are correct for what was
  run. The script's docstring ("the 30-seed benchmark varies exactly this") is
  what is wrong.
- **How `pulsed` differs:** it uses `probability` flows, so its seeds vary
  both the schedule and the arrivals.

## P117 — the `pulsed` scenario qualified, on its one run (2026-10-16)

**Design** (`design_log.json`): iteration 1, the pre-registered starting point,
met all six criteria on seeds 300–309.

- **Parameters:** levels {300, 700, 1100} veh/h/approach, segments 120–300 s,
  hash `8267da50f659`.
- **Frozen and committed** (`5b306e4`) before qualification.
- **Iterations used:** 1 of 5.

**Qualification, run once on seeds 200–219** under the frozen policy
(sha256 `a7f06ba8…`), with the Q3 classifier fitted on the design seeds:

| | criterion | measured | threshold |
|---|---|---|---|
| Q1 | oracle ≠ persistence | **0.314** | ≥ 0.20 |
| Q2 | LOW / MEDIUM / HIGH share | **0.229 / 0.380 / 0.391** | ≥ 0.10 each |
| Q3 | state classifier disagrees with oracle | 0.482 | ≥ 0.10 |
| Q4 | deterministic / demand aligned | **20/20 and 20/20** | all |
| Q5 | delivered skill at q = 0, .25, .5, .75, 1 | 0.00, 0.25, 0.52, 0.71, 1.00 | within 0.05 |
| | 3-class macro-F1 along the grid | 0.676, 0.758, 0.844, 0.905, 1.000 | rising, range ≥ 0.15 |
| Q6 | arrived fraction | **0.938** (`Fixed(30)`: 0.955) | ≥ 0.85 |

**Passed.** For comparison, at the constant `saturated` regime under the same
policy P114 measured 6.9% for Q1, and HIGH at 0%.

**A weakness in Q3, stated rather than hidden.** The logistic regression
disagrees with the oracle more often (0.48) than plain persistence does
(0.31). A linear model on raw counts is a weak learner of thresholded
classes, so Q3 cleared an easy bar. Q1 is the stronger evidence that the
state does not already hold the future: persistence is the policy's free
baseline.

**The D2 cost** (`cost.json`, team laptop, CPU):

- an ordinary 1800 s episode is 1.9 s of environment stepping;
- the oracle pass is 3.9 s;
- that is about 3× the stepping, or about **+2.3 h per 500,000-step run**,
  with PPO's update time excluded;
- the oracle is cached per (seed, frozen policy), so arms sharing a training
  seed pay it once.

**Still required:** confirmation with the scenario-trained no-forecast policy
(seeds 240–259) before anything forecast-aware is trained.

## P118 — ADR-021 Amendment 1: scenario, oracle, quality axis, arms and outcome fixed before any run (2026-10-16)

[ADR-021 Amendment 1](decisions/ADR-021-forecast-quality-as-a-swept-variable.md)
records the owner's D1–D4 (not a guide signature; the status stays
*Proposed*).

- **Scenario:** `pulsed`, which replaces "saturated only".
- **The oracle:** the replay oracle, with the owner's limitation stated in the
  ADR. It is conditioned on the frozen policy's trajectory, so it is not a
  perfect forecast under a policy that changes traffic. Its realised agreement
  is reported in every evaluation, and every result is labelled oracle-input,
  an upper bound.
- **The quality axis:** persistence to oracle, q ∈ {0, .25, .5, .75, 1}, with
  measured skill reported per run.
- **Arms:**
  - no-forecast;
  - persistence (q = 0, the control);
  - the oracle (q = 1);
  - the sweep, only if the ceiling clears.
- **Replication and seeds:** three training seeds each (42, 1, 7), with
  evaluation on seeds 0–29.

**The outcome is named exactly, with the substitution documented.** ADR-021
said "mean total delay" and the runner had no such field.

- **`mean_total_delay_s`** is the mean over every vehicle loaded in the
  episode of tripinfo `timeLoss + departDelay`, including vehicles unfinished
  or not yet inserted.
- It is SUMO's decomposition of total delay, and it does not share
  `mean_wait_s`'s completed-trips-only bias.
- `run_episode(total_delay=True)` reports it, and a test shows the option
  moves no existing field.
- `mean_wait_s` is secondary here.
- **P112 Part 2 keeps `mean_wait_s` and is not amended.**

**The ceiling decision is fixed now.** The oracle must beat both no-forecast
and persistence, by paired t-test over seeds 0–29 (Holm across the two), each
with *d* ≥ 0.5. Beating no-forecast alone is reported as "an input channel
helps; foresight not shown".

**Open before any forecast-aware training (A1.7):**

1. confirmation;
2. P116(a);
3. the forecast producer in the environment, with the arms-differ-only-in-
   slots test, which closes P52 in code;
4. `train_ppo.py` refusing an arm without a producer;
5. Webster's sweep on `pulsed`.

**Nothing has been trained. P97a Part 1 stays passed, Part 2 stays PENDING,
and the controller stays disconnected from signal timing.**

## P119 — the training environment never ran the sublane model; every PPO policy trained on different traffic than it was evaluated on (2026-10-17)

**Found** while fixing P116(a): `TrafficSignalEnv` started SUMO without
`--lateral-resolution`, while `run_episode` applies 0.8 by default.

- **The consequence:** every PPO checkpoint trained on lane-disciplined
  traffic, which is ADR-010's (b) arm. Every evaluation, meanwhile, ran on the
  sublane model ADR-010 adopted as the model of Indian traffic.
- **How it showed up:** with identical decisions, the two harnesses' counts
  diverge within the first minute. On `pulsed` seed 999 they first differ at
  decision 11 (t = 67 s).

**Fixed.**
- **The environment:** it takes `lateral_resolution`, defaulting to 0.8, and
  `ppo_config.yaml` declares it (`env.lateral_resolution`).
- **The sidecar:** `train_ppo.py` records it in every new checkpoint's
  sidecar, and the surrogate arm refuses a frozen policy trained under a
  different value.

**What it affects:**
- **The existing checkpoints** stay as trained, and their sidecars say nothing
  about the sublane model, which means none was used.
- **The committed `benchmark_ppo` numbers** come from a `phase_duration`
  policy trained without the sublane model and evaluated with it. Those
  numbers are correct for what was run; they are not a matched comparison.
- **P115's qualification** ran in the environment without the sublane model.
  Its result stands for those dynamics, and the binding check is now the
  requalification (P115 Amendment 1).

## P120 — evaluation now reproduces training decision for decision, and the surrogate arm exists and fails closed (2026-10-17)

The owner approved four code items before any training. Items 1–3 are here,
and item 4 is P121.

**Item 1: the `keep_or_switch` mismatch (P116a), plus a fourth mismatch it
uncovered.**

- **The runner now applies the rules a `keep_or_switch` policy trained
  under,** for any controller declaring `decision_mode = "keep_or_switch"`:
  - it decides from t = 0;
  - a "keep" lasts 5 s, not a minimum green;
  - a switch is refused until 10 s of green;
  - 90 s of green forces the change, also across a run of keeps.

  Every other controller is unchanged.
- **`PPOController` never filled index 10 (`phase_remaining`).** Under
  `keep_or_switch` the environment sets it to the time left before max green
  (P11), so every evaluated policy saw a constant 0 there that it never saw in
  training.
  - The runner now passes `green_elapsed`, and the controller builds index 10
    exactly as the environment does, including the environment's reset value
    at t = 0.
  - A `keep_or_switch` observation without it is refused rather than read as
    0.
- **Verified:** `simulation/equivalence.py` traces a policy in both harnesses.
  - **With the real no-forecast checkpoint,** on full 1800 s episodes in
    `light`, `pulsed`, `saturated` and `oversaturated`, the traces are
    **identical in time, phase, counts and every element of the 17-dim
    observation, at every decision**.
  - **Before the fixes,** they differed at decision 0 (index 10).
  - **The guards can fail:** reverting the runner fix fails three of the
    regression tests, and removing the sublane model from the environment
    diverges at decision 11.
- **Regression tests** (`tests/test_harness_equivalence.py`) cover scripted
  reactive, always-keep and always-switch policies on two regimes, the 5 s
  keep, the 10 s refusal, the forced change at 90 s, and the real checkpoint
  on two regimes.

**Item 2: the forecast producer (P52 closed in code).**

- **`simulation/forecast_producer.py`:**
  - `NoForecast` sends nothing.
  - `Surrogate(q)` mixes the replay oracle with persistence (P115 §3) and is
    carried with its true age.
  - A message is refreshed when it would be older than 10 s. That gives ages
    0, 5 and 10 s, plus about 1% in between, at episode ends.
- **`simulation/oracle.py`:**
  - It holds the one per-second recorder, now shared by P115's qualification
    and the training-time oracle.
  - It replays the frozen policy per seed, caches the result under a key
    covering the scenario parameters, policy weights and dynamics, and writes
    no trip records.
- **Two problems the integration smoke caught before any real run:**
  - **An episode's last step can end past `episode_s`.** A switch runs its
    6 s interphase first, so the oracle could not answer the final decision.
    The producer raised instead of going quiet, and the replay now runs 15 s
    longer.
  - **The replay environment was still writing trip records.**
- **Tests** cover the two key properties:
  - the no-forecast and surrogate arms' observations, on the same seed and
    actions, are **identical everywhere except indices 11–14 and 16**;
  - the persistence arm reports the class of the counts it was made from.
- **The 17-dim contract is unchanged** (digest `59579c2dd3be10ed`).

**Item 3: `train_ppo.py` fails closed.** `build_producer` refuses, before any
environment or model exists, a surrogate run in any of these cases:

| refused when | detail |
|---|---|
| the quality is missing or off the grid | the grid is pre-registered |
| the regime or action space is wrong | a constant regime, or not `keep_or_switch` |
| the frozen policy is absent or unfit | the frozen policy fails if its sidecar is missing, it was a smoke run, it is short, it is the wrong arm or regime, it lacks the sublane model, or it has a stale contract |
| requalification is not established | the record is missing, it failed, or it names a different policy's SHA-256 |

It also refuses the `mfstnet` arm and unknown arms.

- **During training,** `forecast_audit` checks **every observation**:
  - no-forecast must read absent with age 1.0;
  - a surrogate must read a class with an age within the bound.

  The first violation stops training.
- **After training,** a surrogate run that sent no message is not saved.
- **Checkpoint naming:** surrogate checkpoints are named
  `ppo_surrogate-q{q}_...`.
- **The sidecar records:**
  - the producer;
  - its statistics;
  - the number of audited observations;
  - the sublane setting;
  - the episode-seed rule.
- **Tested:** 20 refusal and audit tests (`tests/test_train_ppo_guard.py`).

**Verified end to end:**
- **A no-forecast smoke run** on `pulsed` audited 4,191 observations, all
  absent, and recorded the sublane value and the P115 seed rule.
- **A surrogate smoke run** at q = 0.5, with a stand-in frozen policy, trained
  through PPO with 1,048 audited observations. 231 of 463 messages came from
  the oracle (0.50).

The four new suites join CI's `model` job.

## P121 — Webster's tuning on `pulsed` pre-registered before any run (2026-10-17)

`PREREGISTRATION_P121_webster.md` fixes the protocol:

- **Search space:** ADR-012's seven saturation flows × start-up lost time
  {0, 4} s, 14 configurations.
- **Seeds:** tuning seeds 400–419, disjoint from every other use.
- **Disqualifications:** ADR-012's, clamp rate > 0.50 or arrived fraction
  < 0.85.
- **Selection:** the lowest mean `mean_total_delay_s`. The baseline is tuned
  on the outcome it is compared on (ADR-021 A1.5), and the configuration the
  mean-wait rule would have picked is reported beside it.
- **Runs once.**

`select_best` gained a `metric` argument whose default keeps ADR-012's mean
wait, so every existing caller is unchanged.

**P115 Amendment 1, the requalification, is frozen in the same commit:**
- seeds 240–259;
- the full scenario-trained no-forecast policy at seed 42, under the
  corrected dynamics;
- unchanged criteria and thresholds;
- Q3 refitted on design seeds;
- on failure, pause and investigate, with no threshold changes.

`p115_qualify.py requalify` enforces it.

## P122 — Webster tuned on `pulsed`, once: s = 660 pcu/h/m with 4 s lost time (2026-10-17)

The run was made once under `PREREGISTRATION_P121_webster.md` (`78be804`):
- tuning seeds 400–419;
- 1800 s episodes with the sublane model at 0.8;
- `total_delay=True`.

The files are `webster_tuning.csv` (280 rows, with a provenance sidecar) and
`webster_selection.json`.

**Selected: saturation flow 660 pcu/h/m, start-up lost time 4 s.**

| measure | value |
|---|---|
| mean total delay | 39.42 s |
| mean wait | 23.48 s |
| clamp rate | 26% |
| arrived fraction | 0.950 |

**The mean-wait rule ADR-012 used would have selected the same
configuration,** so the choice of metric did not decide the baseline. This
configuration is now fixed for every ADR-021 evaluation on `pulsed`.

**Eight of the 14 configurations were disqualified.**
- **All seven with 0 s lost time clamp on 87–100% of decisions.** With no lost
  time the cycle formula asks for cycles shorter than the 32 s minimum, so
  these run as fixed short cycles under Webster's name.
- **s = 1283 with 4 s lost time clamps on 59%.**

**Recorded rather than hidden.** Those clamped configurations post a
**slightly lower** total delay than the selected Webster: 38.49–39.42 s, about
2% lower at best.

- **On `pulsed`,** a short fixed cycle is therefore competitive with genuine
  Webster.
- **ADR-012's rule** keeps them out of "Webster's best" because they are not
  Webster.
- **ADR-021's evaluation** should still report a fixed-cycle arm beside
  Webster, so that a PPO gain over Webster cannot be a gain that any short
  fixed cycle also delivers.

Evaluation seeds 0–29 were not used.

## P124 — the fixed-cycle comparator tuned once: 30 s green; and P122's reading corrected (2026-10-17)

The run was made once under `PREREGISTRATION_P123_fixed.md` (`e6aa330`), on
seeds 400–419 with the same harness as P122. The files are
`fixed_tuning.csv`, its sidecar, and `fixed_selection.json`.

| green | mean total delay | mean wait | arrived |
|---|---|---|---|
| 10 s | 58.10 s | 32.84 s | 0.935 |
| 15 s | 76.57 s | 27.33 s | 0.916 |
| 20 s | 46.37 s | 28.14 s | 0.942 |
| **30 s** | **44.88 s** | 28.08 s | 0.944 |
| 45 s | 46.11 s | 30.61 s | 0.943 |
| 60 s | 50.77 s | 34.25 s | 0.941 |

**Selected: a 30 s green.** It is now ADR-021's fixed-cycle comparator
(Amendment 2, A2.1). It is also the existing benchmark's fixed arm, and
FR-A06's degraded-mode cycle. The 15 s row is non-monotone, and is reported
as measured.

**P122's interpretation was wrong, and is corrected here.** P122 read the
disqualified zero-lost-time Webster configurations as "fixed short cycles",
and concluded that a short fixed cycle is competitive on `pulsed`. The data
here contradict that:

- **The best fixed cycle (44.88 s) is 13.8% worse than the selected Webster
  (39.42 s),** and about 16% worse than those clamped configurations
  (≈ 38.5 s).
- **What the clamp rule catches is fixed cycle *length*, not fixed splits.**
  - At a clamped cycle, `Webster.decide` still divides the green between the
    phases in proportion to each direction's measured flow ratio.
  - So those configurations are a fixed-length cycle with demand-responsive
    splits: adaptive, not fixed-time.
- **The supported reading** is that, on `pulsed`, **a short fixed-length cycle
  with demand-proportional splits is competitive with genuine Webster.** A
  fixed-time cycle is not.

**What stays as decided.**
- **ADR-012's disqualification rule** was applied as pre-registered, and the
  selected Webster stands.
- **The fixed-cycle arm** remains in ADR-021 as a floor, and is reported as
  one.

**Noted for the owner, and not acted on.** ADR-012 calls a fully clamped
configuration "a fixed cycle wearing Webster's name". On `pulsed` that
description is inaccurate, because the splits still adapt. Whether such
configurations deserve a reported "short-cycle proportional" arm in ADR-021 is
a scope question for the owner. Adding one now, after seeing these numbers,
would be selection after the fact. Any such arm would have to be
pre-registered before the ceiling runs.

## P125 — a clamped, demand-proportional Webster arm, pre-registered and selected from tuning data; ADR-021 Amendment 3 freezes the complete arm list (2026-10-17)

The owner approved reporting the controller P124 identified as a separate
ADR-021 arm. Its pre-registration (`PREREGISTRATION_P125_clamped.md`,
`ee429ef`) was committed before any selection, and fixes the controller
exactly:

| setting | value |
|---|---|
| base | `Webster` as committed, with 0 s start-up lost time |
| cycle | the cycle formula, clamped to [32, 192] s |
| green split | demand-proportional, `effective green × y_phase / Y` |
| green bounds | [10, 90] s, plus the runner's interphase |

The selection rule applies to the committed P122 tuning rows: among the
0 s lost-time configurations, the lowest mean total delay, subject to ADR-021's
survivorship floor. The clamp rule is deliberately not applied.

**Selected: s = 600 pcu/h/m, 0 s lost time.** Mean total delay 38.49 s, clamp
91%, arrived 0.951. The figures are computed by
`scripts/select_clamped_webster.py` into `clamped_selection.json`.

- **No episode was run, and evaluation seeds 0–29 were never used.**
- **The selection is among near-ties:** s = 525 gave 38.51 s and s = 900
  gave 38.60 s. The choice of s barely matters for this arm, which is itself
  informative: when the cycle length is clamped, the saturation flow
  contributes little.

**ADR-021 Amendment 3 freezes the complete arm list** before any ceiling
result:
- no-forecast PPO;
- persistence;
- forecast-quality PPO, up to the oracle;
- tuned Webster;
- fixed 30 s;
- Webster split with a clamped cycle.

**The primary question stays** forecast-aware against both no-forecast and
persistence. The baselines strengthen the operational comparison. X stays
defined against the tuned Webster.

## P126 — seed 1 lost to a SUMO port race and is rerun; the first retry fix was itself defective; the replicates are audited and locked before requalification (2026-10-17)

**What happened.** The three no-forecast replicates trained in parallel from
10:10. Seed 1 died part-way, at about 11:23, with no checkpoint saved.

- **The error:** its own SUMO reported `Unable to create listening socket:
  Address already in use`, and its TraCI handshake then failed with
  `struct.error`.
- **The cause:** TraCI picks a free port and hands it to SUMO, and another
  SUMO took the port first. My concurrent test runs were starting SUMOs at
  the time.
- **The crash log is kept** as `train_1_crashed_port_race.log`, separate from
  the rerun's.

**Seeds 42 and 7 were not affected.** Their logs contain no race, retry or
connection line. TraCI prints those when it retries, so every episode of both
runs ran on its own SUMO. Both completed:
- 500,000 steps;
- 503,820 and 503,791 audited observations;
- no traceback.

**The rerun.** Seed 1 was rerun from scratch at 11:50, with the same seed and
configuration. It is an infrastructure rerun, not a selection: no result of
the crashed run existed or was looked at.

**The first fix, `0644e26`, was defective.** It wrapped `traci.start` in a
retry, and passed a test that used a fake TraCI.

Reproduced against real SUMO, with a squatter taking the first port and
hanging up, it **hung**:
- the retry called `traci.close()`, which sends a close command over a dead
  socket and then waits forever on the SUMO it started;
- that SUMO also leaked, and an orphaned process was found and killed.

The rerun of seed 1 started under this code. A second race there would hang,
which is visible as stalled progress, rather than corrupt anything.

**Reading TraCI's code found a second, worse risk.** In a port race, the
client can connect to **another process's** SUMO. A handshake that succeeded
there would silently drive the wrong simulation, with the wrong seed's
demand.

**The fix, `1d1a799`.** `start_sumo` starts SUMO itself, so it always holds
the process. A failed attempt:
- closes the socket;
- kills only that process, without blocking;
- unregisters the connection;
- retries with a new port and the same command and seed.

A connection made while our own SUMO has exited belongs to someone else and
is refused. After five attempts the error is raised: an episode is never
skipped, re-seeded or reconfigured.

**Tested against a real race:** it recovers, and no SUMO is left running. A
mock covers the foreign-SUMO refusal. Parity is unchanged.

**The audit and the lock (`cc72fc3`, `5c5dd49`).** `scripts/p126_audit.py`
runs gate 1 and gate 2 on each replicate:
- the final full run;
- the sidecar;
- the architecture and hyperparameters against `ppo_config.yaml`;
- at least 500,000 audited observations;
- a clean log;
- seed-999 parity.

Only if all three pass does it write `no_forecast_lock.json`, atomically. The
lock holds:
- the checkpoint and sidecar SHA-256s;
- the config SHA-256s;
- the contract digest;
- the commit.

The lock binds what follows it:
- **requalification** refuses an unlocked policy, and records the lock's hash;
- **`train_ppo.py`** refuses the surrogate arm unless the frozen policy, the
  configs and the requalification all match the lock;
- **`--verify`** re-checks it, because a hash proves identity and only the
  audit's checks prove correctness.

**Early dry run (nothing written):** seeds 42 and 7 pass every check,
including seed-999 parity over a full 1800 s episode.

## P127 — the replicates are locked, and `pulsed` requalifies under the trained policy: all six criteria pass (2026-10-17)

**Gate 1 and gate 2: the three-seed audit (`p126_audit.py`).**

| seed | checks passed | steps learned | SHA-256 (prefix) |
|---|---|---|---|
| 42 | 18/18 | 501,760 | `8829979d7b293f19` |
| 1 (rerun) | 18/18 | 501,760 | `668cca36fe2668eb` |
| 7 | 18/18 | 501,760 | `76bfd71e9597d988` |

**The checks** covered:
- the final full run;
- the sidecar;
- the architecture and every hyperparameter against `ppo_config.yaml`;
- at least 500,000 audited observations (503,820, 503,698 and 503,791);
- a clean log;
- **seed-999 parity**: identical behaviour in training and evaluation over a
  full 1800 s episode, at every decision, on all 17 inputs.

**The first full attempt failed only when writing.** It passed all three
replicates, but a numpy `bool_` could not be serialised, so nothing was
written. That was fixed (`df6fac9`) and the audit re-run; its output is kept.

**The lock** (`no_forecast_lock.json`, `f84d9d7`) was written atomically.
`--verify` reports **every locked artifact, config and the commit match**.

**Provenance caveat.**
- **What the sidecar actually records:** `git_commit` is HEAD when the
  sidecar is written, at the end of training. Seeds 42 and 7 record
  `cc72fc3` but launched at `95a496e`; seed 1 records `94d1b9e` but launched
  at `0644e26`.
- **Why no result is affected:** no commit in between changed the
  no-forecast training path.
- **The fix:** new runs record `code_at_start`, the commit at launch and any
  dirty code (`7b8f5d6`).

**Gate 3: requalification, run once** (P115 Amendment 1). The run used:
- seeds 240–259;
- the locked seed-42 policy, trained on `pulsed` under the sublane model;
- Q3 refitted on design seeds;
- the lock's hash, recorded in `requalification.json`.

| | criterion | qualification (P117, without the sublane model, saturated-trained policy) | **requalification** | threshold |
|---|---|---|---|---|
| Q1 | oracle ≠ persistence | 0.314 | **0.362** | ≥ 0.20 |
| Q2 | LOW / MED / HIGH | 0.229 / 0.380 / 0.391 | **0.286 / 0.487 / 0.227** | ≥ 0.10 each |
| Q3 | state classifier disagrees | 0.482 | 0.455 | ≥ 0.10 |
| Q4 | deterministic / demand aligned | 20/20, 20/20 | **20/20, 20/20** | all |
| Q5 | delivered skill | 0, .25, .52, .71, 1 | **0, .24, .50, .77, 1** | within 0.05 |
| | macro-F1 along the grid | .676 → 1.000 | **.646 → 1.000**, rising | range ≥ 0.15 |
| Q6 | arrived fraction | 0.938 | **0.953** (fixed 30 s: 0.953) | ≥ 0.85 |

**Passed.** The scenario stays informative under the policy that will
generate the oracle. The future class now differs from the present slightly
**more** often (0.362).

**The frozen decision rule's next step is forecast-aware training,** under
the locked artifacts and the frozen arm list (ADR-021 Amendments 1–3).
- **Nothing forecast-aware has been trained.**
- **It is held for the owner's go.**
- **ADR-021's go/no-go remains a guide-level decision.**

## P128 — the ceiling pre-registered with its code, an ADR-021 decision record, and a real-policy smoke test that caught two defects (2026-10-17)

The owner approved the ceiling stage on three conditions:
1. the evaluation is pre-registered first;
2. a real-policy smoke test passes;
3. the ADR-021 decision record is committed before training.

**1. Pre-registration (`83f3af0`).**
- **The document:** `experiments/results/ceiling/PREREGISTRATION_P128_ceiling.md`
  is committed with `scripts/ceiling_eval.py`.
- **It fixes:**
  - the six frozen arms;
  - paired evaluation seeds 0–29;
  - mean total delay;
  - the two primary tests, oracle against no-forecast and oracle against
    persistence, using a paired t-test, Holm across the two, *d* ≤ −0.5, and
    a 10,000-resample bootstrap CI;
  - an operational gate: arrived ≥ 0.85, and starvation no more than
    no-forecast's plus 1;
  - the five readings and four qualifiers;
  - episode-failure handling: re-run once, then stop; nothing dropped;
  - the oracle-versus-realised report.
- **The rule as code:** `decide()` is tested on synthetic data for every
  reading and qualifier (`tests/test_ceiling_eval.py`, 11 tests).
- **The audit:** the six forecast checkpoints must each pass a forecast audit
  (gate 1 plus seed-999 parity with messages) before a lock is written.
- **The runner change:** an opt-in per-second hook, so that each message is
  scored against the class realised at its own target time.

**2. ADR-021 decision record (`974e10d`).** It records:
- what has passed, naming the lock and the requalification record by hash;
- what the owner's go authorises and what it does not.

It is not a guide signature, and the guide is to be informed before any
ceiling result is cited.

**3. The smoke test, run twice.**

**The first run found a naming defect (`4fd04a8`).** The label
`surrogate-q1.00` contains a dot:
- `Path.with_suffix` read `.00_pulsed...` as the suffix;
- the overwrite guard and the sidecar went to `ppo_surrogate-q1.zip`, **shared
  by q = 0 and q = 1 at the same seed**;
- SB3 saved the weights without `.zip`.

**The fix:** quality is now written in hundredths (`q100`, `q025`), paths are
explicit, and the evaluation finds checkpoints by the same function that names
them. The locked no-forecast names are unchanged.

**The second run passed every check:**
- the names are right;
- the producer replays the locked seed-42 policy (`8829979d…`);
- the delivered quality is exactly 1.0 and 0.0;
- the code was clean at launch;
- ages were 0, 5 and 10 s, with about 1% in between at episode ends;
- parity with messages is identical;
- **all 1,054 model and committed-result files are unchanged, and none were
  added.**

**An informative side result from the smoke test.** On an evaluation-style
episode (seed 999), a barely trained policy (3,000 steps) moves traffic far
from the frozen trajectory:
- the oracle's accuracy against what actually happened was **0.60**;
- persistence's was **0.92**.

That is the A1.2 limitation measured. The pre-registered "oracle transfer
weak" qualifier exists for this case. A trained policy should deviate less,
and the real runs will show it.

**One more race closed before the parallel runs.** The q = 0 and q = 1 arms at
a seed share oracle cache entries.
- Each process now writes its own temporary file.
- A rename that loses the race keeps the copy already there, after checking
  the two replays are identical.
- A difference raises an error.

Both behaviours are tested.

## P129 — episode 0 of every training run used the training seed as its demand seed; the ceiling's primary set becomes 28 seeds (2026-10-17, before any ceiling result)

**Found** while the six forecast replicates were training. The oracle cache
held replays for episode seeds **1, 7 and 42**, and the rule (P115 §4) cannot
produce those.

**The cause, read from SB3's source.**
- `PPO(seed = s)` calls `env.seed(s)`.
- `DummyVecEnv.reset` then passes `seed = s` to the first `reset`.
- `TrafficSignalEnv` uses an explicit seed as given, so episode 0 ran on SUMO
  seed *s*.
- Every later episode follows the rule (1,000,000 + 10,000 *s* + *e*).

**This was a deviation from P115 §4 in every training run so far:**
- the three locked no-forecast replicates;
- the six forecast replicates in progress.

**What it means for each training seed:**
- **seeds 1 and 7:** each trained **one of about 2,119 episodes** on the
  demand of evaluation seeds 1 and 7. That breaks A1.4's separation.
- **seed 42:** demand seed 42 belongs to no reserved set.

That covers the oracle policy too, and the requalification, which used seed
42's policy on seeds 240–259, is unaffected.

**The records are kept as they were.** The sidecars and the lock are
unchanged. Their `episode_seed_rule` states the rule, and this entry records
the exception.

**Decision (owner, option B): correct the evaluation population, and retrain
nothing.** P128 Amendment 1, committed before any ceiling episode, sets the
**primary evaluation set to {0, …, 29} \ {1, 7}**, 28 paired seeds. It is
frozen literally in `ceiling_eval.py`, which asserts that set shares no seed
with any training seed.

**All 30 seeds are still run.** The all-30 analysis is reported as a
**contaminated, secondary sensitivity analysis**:
- it is not independent validation;
- it can never override the primary decision;
- a test shows that a large gain confined to seeds 1 and 7 does not clear the
  ceiling.

**Unchanged:**
- the statistical procedure;
- the threshold *d* ≤ −0.5;
- Holm;
- the operational gate;
- the readings;
- the arms.

**Rejected: option A,** which would fix the seeding, retrain no-forecast seeds
1 and 7, re-lock, and restart the six forecast runs.
- **Its cost:** about three more hours of training, and the forecast runs
  already in progress.
- **What it would have bought:** literal compliance with P115 §4 for future
  runs only.
- **Why B is better:** B removes the contamination from the decision
  directly, and keeps every arm's training procedure identical, including any
  future sweep arm.

**Enforced in code.** `tests/test_seed_separation.py` builds the training stack
through `train_ppo.build_model`, the function `train()` now uses itself. It
resets the stack as SB3 does, and checks the **actual** SUMO seeds used,
including the seeded first reset, against every reserved set. A test of the
configured rule alone would have missed this.
- **Behaviour check:** a smoke run through the refactored `train()` audited
  4,191 observations, as before.
- **Record:** the environment now records every episode's SUMO seed
  (`run_seeds`).

## P130 — the ADR-021 ceiling, run once: no demonstrated control benefit from forecasts under the tested conditions (2026-10-17)

**The procedure.** P128 with Amendment 1 (`5f0ef86`, frozen before any ceiling
episode):
- **six forecast replicates,** persistence (q = 0) and oracle (q = 1) at seeds
  42, 1 and 7, audited at 30/30 checks each, including seed-999 parity with
  forecast messages;
- **locked** (`forecast_lock.json`, `b6b02f8`), with both locks re-verified;
- **evaluated once:** 12 arm-policy combinations × 30 seeds, all 360 rows
  kept (`ceiling_runs.csv` with its sidecar; `ceiling_stats.json`);
- **decided** on the 28 primary seeds, {0, …, 29} \ {1, 7}.

**Primary result.** The outcome is mean total delay; a negative difference
means the oracle arm has the lower delay.

| comparison | mean difference | bootstrap 95% CI | *d* | p | Holm |
|---|---|---|---|---|---|
| oracle − no-forecast | **+5.41 s** | [−0.91, +16.81] | +0.19 | 0.33 | n.s. |
| oracle − persistence | **+2.38 s** | [−6.35, +15.38] | +0.08 | 0.69 | n.s. |

**Reading (pre-registered): "no demonstrated control benefit from forecasts
under the tested conditions."** The ceiling does not clear.

The point estimates go the **wrong way**: the oracle arm has more delay than
both comparators. Neither difference is significant.

**Qualifiers attached:**
- **oracle transfer weak:** the oracle arm's realised accuracy was 0.774,
  under 0.80;
- **"oracle-input: an upper bound, not achievable; simulation evidence
  only".**

**The operational gate passed:**
- arrived fraction 0.946;
- 0 starvation events in every arm.

**Contaminated 30-seed sensitivity analysis (secondary, decides nothing):**
- **the same reading;**
- oracle − no-forecast: +5.08 s (*d* +0.18);
- oracle − persistence: −2.90 s (*d* −0.07).

**Per training seed** (oracle − comparator, mean over the 28 seeds):

| seed | vs no-forecast | vs persistence |
|---|---|---|
| 42 | +0.03 s | −2.57 s |
| 1 | **+17.29 s** | **+12.25 s** |
| 7 | −1.10 s | −2.55 s |

One replicate (seed 1) is far worse. The other two are close to zero, and
slightly favour the oracle against persistence. **The variance between
training seeds is as large as any effect,** which is why the intervals are
wide.

**The oracle against what actually happened (A1.2).** Accuracy is measured at
each message's own target time.

| arm | forecast sent | oracle | persistence | oracle agreement at decision times |
|---|---|---|---|---|
| oracle | 0.774 | 0.774 | 0.632 | 0.775 |
| persistence | 0.645 | 0.772 | 0.645 | 0.769 |

- **The oracle's information was genuinely better than persistence,** by
  about 13–14 points of accuracy against the realised future.
- **The policy did not convert it into lower delay.**
- **Under the trained forecast-aware policies, the oracle matched realised
  traffic about 77% of the time.** That is lower than under the frozen
  policy, which is exactly the limitation A1.2 named.

**The arms, mean total delay over the 28 primary seeds:**

| arm | delay (95% CI) | wait | arrived |
|---|---|---|---|
| Webster split, clamped cycle (s = 600, 0 s; clamp 94%) | **37.37 s** [34.10, 40.92] | 21.15 s | 0.957 |
| tuned Webster (660, 4 s; clamp 31%) | 39.81 s [36.06, 43.94] | 23.09 s | 0.957 |
| no-forecast PPO | 43.72 s [38.75, 49.40] | 24.37 s | 0.952 |
| fixed 30 s | 45.69 s [41.20, 50.98] | 28.11 s | 0.951 |
| persistence PPO | 46.75 s [40.47, 54.95] | 24.85 s | 0.944 |
| oracle PPO | 49.13 s [39.92, 62.22] | 24.03 s | 0.946 |

**Descriptive, unadjusted (P128 §7).** **Every PPO arm has more delay than
both Webster arms.**
- **No-forecast PPO against tuned Webster:** +3.91 s, *d* +0.61, p = 0.003.
- **No-forecast PPO against the clamped split:** +6.35 s, *d* +0.87.
- **No-forecast PPO against fixed 30 s:** a tie (−1.96 s, n.s.).

**What this establishes:**
- **Within this simulation, at 500,000 steps with this reward and state, an
  oracle 60-second congestion-class forecast did not improve PPO control**
  over no forecast, or over persistence.
- That is the decisive null §1 of ADR-021 intended, now on a scenario
  qualified to have headroom.
- **The X sweep is not run** (A1.4).

**What it does not establish, stated so the null is not over-read:**
- **The controller itself is the binding constraint.** The PPO policies do
  not beat a tuned Webster, or the clamped demand-proportional split, even
  with no forecast. A learner that cannot match simple adaptive timing is a
  weak instrument for detecting a forecast's value.
  - The null therefore reads "**not shown with this controller**". It does
    not read "forecasts cannot help control".
- **The replicate spread is large:** one oracle replicate is 17 s worse.
- **The oracle is the frozen policy's future,** and it matched realised
  traffic only 77% of the time under the forecast-aware policies.

**Consequences, all for the owner and the guide:**
- **The RL claim narrows, under ADR-021's go/no-go,** which is a guide-level
  decision. The supported statement is the measured null, with the
  qualifications above.
- **P97a Part 2's eligibility conditions are now formally met:** the
  surrogate arm exists, the ceiling has run, and a forecast-aware policy is
  trained. It still needs its pre-registered amendment (regime and forecast
  stream) before any run. Whether it is still worth running after a null
  ceiling is the owner's call.
- **The controller stays disconnected from signal timing.**

## P131 — the ceiling's conclusion adopted, the guide informed, Part 2 deferred, and a plan for what follows (2026-10-17)

**The conclusion.** The owner's wording is adopted verbatim as the ADR-021
record ("Conclusion", appended to the ADR):
- a **measured null for forecast benefit with the tested controller and
  experimental conditions**;
- not evidence that forecasts are inherently unhelpful.

The limits it names:
- weak oracle transfer (0.774);
- the spread between training seeds;
- PPO trailing both Webster arms.

**P130 stays frozen and authoritative:** no rerun, no reanalysis, and no new
exclusion or threshold.

**The guide is informed** in `MEMO-2026-10-17-adr021-ceiling.md`, with a reply
requested by 2026-10-24, **before any wider citation.** It asks for three
decisions:
1. **Narrow claim C1 (ADR-023).** Keep the count-forecaster half (P104–P106),
   and report the RL half as the measured null. **`CLAIMS.yaml` and ADR-023
   are not edited until the guide decides.**
2. **Whether P97a Part 2 should run at all.** Its preconditions are now met,
   but its motivating benefit was not shown.
3. **Whether to start one new study at its design stage.**

**The quality sweep is not run (A1.4).**

**P97a Part 2 is deferred, not run.** If the guide wants the narrower safety
question answered, a frozen amendment to P112 must first fix seven things:
- the scenario;
- the forecast source;
- the controller and baseline;
- the endpoints and margins;
- training-seed variability;
- fresh seeds;
- the interpretation if safety is non-inferior but delay does not improve.

**The plan:** `PLAN-2026-10-17-after-ceiling.md`. Its main proposal is a new
study, **forecast-assisted Webster split (FAW)**. It is designed so that each
of P130's three weaknesses is gone by construction:

| P130 weakness | how FAW removes it |
|---|---|
| training-seed variance | the controller is **deterministic**, so there is nothing to train and no replicate spread |
| an oracle taken from a different policy's trajectory | the oracle is a **replay under the baseline controller itself** |
| a 3-class label | a **next-minute count** forecast: the quantity Webster's flow ratios use, and ADR-027's ridge role |

**FAW's arms:** W-now (the P125 arm), W-oracle, and W-ridge (the frozen
deployable forecaster).

**Its gates:**
- **C1, feasibility on design seeds:** stop if the oracle changes fewer than
  10% of the green splits.
- **C2, pilot and power on pilot seeds:** stop if detecting a 2% minimum
  effect needs more than 200 seeds.
- **C3:** the pre-registration, committed before anything is evaluated.
- **C4:** one evaluation on fresh seeds (700 onward).

It is a new question on new seeds, and it is **not** a rescue of P130.

**The plan also parks two items:**
- a stronger RL controller, first milestone "match tuned Webster with no
  forecast";
- the rest of the roadmap, unchanged.

## P132 — forecast-assisted Webster split (FAW): design built, feasibility passed, power gate STOPPED the study (2026-10-17)

**Scope approved by the owner:** design, feasibility and power only.
`PREREGISTRATION_P132_faw.md` and its code (`d99cbee`) were committed before
any FAW episode.

**The question:** can a next-minute count forecast improve an already
competitive controller? It is a new question, **not a rescue of P130.**

**C0, the design:**
- **Arms,** all on the P125 Webster split (s = 600, 0 s lost time, clamped
  cycle). They differ only in the demand the rule reads:
  - **W-now:** the observed counts;
  - **W-oracle:** the realised next-minute mean, from W-now's own
    trajectory;
  - **W-ridge:** the frozen ADR-027 forecaster.
- **Webster** gained a pure `green_for` and an optional demand source. Its
  default is byte-identical, tested over 15,000 random decisions, and a
  committed P122 episode re-runs to exactly the same numbers.
- **The runner** now records interphase seconds for opt-in observers. A test
  shows this changes no outcome.

**C1, the feasibility gate, run once on design seeds 600–609: PASSED.**
- **The perfect forecast changes 637 of 765 W-now green splits (0.833)** by at
  least 1 s, against a 0.10 threshold.
- The mean change is 3.0 s, and half of the changes are at least 3 s.
- **The timing rule is sensitive to foresight.**

**Reported, not gating.** The frozen ridge forecaster is **worse than
persistence** on SUMO approach counts:
- ridge MAE against the realised next-minute mean: **4.17**;
- persistence MAE: **2.72**.

It was trained on Bellevue camera-lane counts.

**C2, the power gate, run once on pilot seeds 610–639: STOPPED.**

| quantity | value |
|---|---|
| paired SD of W-oracle − W-now total delay | **4.55 s** |
| minimum effect of interest (2% of W-now's 37.83 s) | **0.76 s** |
| pairs needed for power 0.80 at α = 0.025, two-sided | **347** |
| pre-registered maximum | 200 |

**Under the pre-registered rule, the study ends here:** *not adequately
powered within its budget.* The evaluation (C4) is not run, and no C3 is
written.

**Why a deterministic controller still varies.** There is no training spread
here. The paired SD comes from trajectories diverging: once W-oracle times a
single green differently, the rest of the episode's traffic differs.

**Pilot effects (labelled "not evidence", and used for n only):**

| comparison | pilot mean total delay |
|---|---|
| W-oracle − W-now | **+2.89 s** |
| W-ridge − W-now | **+2.80 s** |

Both pilot means are in the **unfavourable** direction:
- under W-oracle, the oracle's error against the traffic W-oracle actually
  produced was 2.48, against persistence's 2.67;
- every arm completed about 0.958 of its trips.

**Not done, and why.** The minimum effect, the seed budget and the arms were
not changed after seeing these numbers. Doing so would be the forking path
the protocol exists to prevent. Two further points:
- **The pilot points the wrong way,** so a larger study would most likely
  measure a null or a harm, not a benefit.
- **Any further FAW work would be a new decision made with knowledge of this
  pilot,** and would have to say so.

**What this establishes:**
- a perfect next-minute count forecast **does** change this controller's
  decisions;
- the delay effect of those changes is **below what 200 paired seeds can
  resolve** at a 2% minimum effect;
- the pilot did not suggest a benefit.

**What it does not establish:**
- that forecasts cannot help a signal controller;
- anything about a better-calibrated forecaster on SUMO, since ridge did not
  transfer here.

**Status:**
- the study is closed at its gate;
- the guide is informed by an addendum to MEMO-2026-10-17;
- P130 and P131 are unchanged;
- ADR-023 and `CLAIMS.yaml` are untouched;
- the controller stays disconnected from signal timing.

## P133 — the overall forecast-for-control conclusion; P132's wording corrected; the line is closed; plan for validation and publication (2026-10-17)

**A correction to P132, made here rather than by editing P132.**

P132 said the delay effect is "**below what 200 paired seeds can resolve** at
a 2% minimum effect". **That over-states it.** The power calculation says
only this: under the **pilot's estimated variability** (paired SD 4.55 s) and
the **pre-registered statistical assumptions** (two-sided, α = 0.025,
power 0.80), detecting the specified 2% improvement would need about **347
paired seeds**.

The pilot's effect estimates (+2.89 s and +2.80 s) are **exploratory**:
- they are not confirmatory evidence of harm;
- they are not evidence about the true effect size in general.

The defensible statements are:
- **the pre-registered power gate failed;**
- **no confirmatory evaluation was justified.**

**What P132 supports:**

| finding | defensible interpretation |
|---|---|
| 83.3% of green splits changed; average change 3.0 s | perfect count forecasts materially influence the controller's decisions |
| 347 paired seeds needed against a maximum of 200 | the pre-registered power gate failed; no confirmatory evaluation was justified |
| pilot +2.89 s (oracle), +2.80 s (ridge) | exploratory, not confirmatory evidence of harm |
| ridge MAE 4.17 against persistence's 2.72 | the Bellevue-trained forecaster does not transfer adequately to these simulated counts |
| completion about 0.958 in every arm | similar completion rates do not establish a delay benefit |

**The overall conclusion, adopted (owner's wording):**

> Across the tested simulation experiments, neither the learned PPO controller nor the classical Webster controller demonstrated a delay benefit from forecast inputs under the specified conditions. Forecasts changed controller decisions, but the proposed follow-up study failed its preregistered power gate. These findings do not establish that forecasts cannot improve traffic control under other controllers, scenarios, or better-calibrated forecasting systems.

**The forecast-for-control line is closed under the current protocol.**
Reopening it requires a genuinely new rationale and a new pre-registration.

**The governance state, explicit:**
- **P130 and P131:** frozen and unchanged.
- **P132:** its power-gate stop is recorded, and no confirmatory evaluation was
  run.
- **ADR-023 and `CLAIMS.yaml`:** unchanged until Ms Pokhriyal decides the
  claim wording.
- **Part 2:** deferred, and not started automatically.
- **The controller:** disconnected from signal timing.
- **Publication:** nothing is pushed, and the licence remains a gate.

**The next work is `PLAN-2026-10-17-validation-and-publication.md`,** three
workstreams:
- **V1, human-verified prediction quality.** It separates detector error from
  forecasting error, by comparing the forecaster fed detector counts, and fed
  human counts, against human next-minute targets.
  - The breakdowns are by camera, traffic level and horizon.
  - Its gates come first: a target-fidelity check on detector data, an
    inter-rater pilot, and a pre-registration before scoring.
- **V2, live-camera validation (S65).** It adds three criteria the current
  tooling lacks: timestamp correctness, end-to-end latency, and prediction
  freshness at the consumer. The 300 s recording is deleted after
  measurement, under NFR-13.
- **V3, publication.** Private first (an owner action), then the CI-checked
  draft PR, licence outreach, a sanitised public tree, and preview removal.

## P134 — validation and publication: the approved local work is done; four decisions surfaced (2026-10-17)

**Approved by the owner:**
- V1's fidelity check;
- V1's sampling and labelling code;
- V2's three criteria on a local stream;
- V3's public-copy builder.

**The boundaries held:**
- V1 used detector data only, and nothing was scored;
- V2 used a local stand-in, with no raw video on disk;
- V3 built locally, and nothing was pushed.

P130–P132 are frozen. ADR-023 and `CLAIMS.yaml` are untouched. The controller
stays disconnected.

### V1: human-verified prediction quality

**Target fidelity** (`v1_target_fidelity.json`), committed with its criteria
before it ran. The data were detector series only: P105's test hours, 56,240
lane-moments.

| frames per minute | MAE against the 30-sample mean | class agreement | result |
|---|---|---|---|
| 6 | 0.259 | 0.905 | fail |
| 10 | 0.158 | 0.935 | fail |
| **15** | **0.102** | **0.956** | **pass**: chosen |
| one frame at t + 60 s | 1.223 | 0.667 | reported only |

**Two design proposals for the V1 freeze (the owner's decision), both made
before any label:**

1. **Draw the sample from P105's test hours.**
   - No model was fitted or selected on them, so the hours are eligible.
   - P105's detector-label results exist for the same moments, so V1 becomes
     a **paired label-source comparison**: the same forecasts, scored against
     detector labels and against human ones.
   - No new footage is needed, which the standing rules forbid in any case.
2. **Replace "forecaster fed human counts" with "label-source effect".**
   - Ridge's input is 60 samples, two minutes. Feeding it human counts would
     mean **60 human-counted frames per lane per moment**, which is
     unaffordable.
   - The 15 future frames still yield:
     - detector-versus-human error on the same frames;
     - end-to-end forecast error against the human target;
     - how far the conclusion moves when the label source changes.

**The sample** (`v1_sample_manifest.json`): ids and sample indices only.
- **Eligible:** 608 lane-moments in 9 camera × class strata. Moments of one
  lane are non-overlapping on a 90-sample grid.
- **Drawn:** a 40-moment pilot, plus an ordered reserve.
- **Note:** Eastgate has only **8 LOW** moments, so that stratum falls under
  the plan's n < 30 rule. The main set's page refuses before the V1 freeze.

**The pilot page.** It is built, and lives only in the gitignored `data/v1/`.
- **Content:** 600 frames, 66.5 MB after downscaling to 960 px.
- **Verified:** it contains no clip name, moment id, time or count. The id key
  is kept from the labellers.
- **The draft counting instructions** are committed, and frozen after the
  inter-rater pilot.

### V2: the live-camera criteria

The owner decided that no raw camera video is written to disk. So:
- `capture` refuses unless explicitly authorised;
- **`decode-throughput`** measures criterion 1 from encoded packets **held in
  memory**. On the local stand-in (720p H.264) it ran at **60× real time,
  PASS, with 0 video files written**.

**Criteria 5–7 are implemented, each with a test that it can fail.** The run
was end to end: a 300 s local stand-in played at camera pace, the real ONNX
graph, and a real local server.

| criterion | result |
|---|---|
| 2–4 (lag, interval, no lost sample) | **PASS**: 150/150 samples, lag growth 0.0 s |
| 5 timestamps (stream PTS) | **PASS**: monotonic, 100% within tolerance |
| 6 latency | **FAIL**: processing p95 **434.5 ms** against 150 ms; transport p95 34 ms, passing |
| 7 freshness at the consumer | **PASS**: 176 polls, 100% at 10 s or less |

**Criterion 6 is reported as measured.** The threshold has not been
changed. But the mapping looks wrong, and the owner should decide it before
the real camera:
- the 150 ms budget is the PRD's figure for **MFSTNet inference on the server
  CPU**;
- "processing" measures the whole edge step, running **both backbones on a
  720p frame** plus the model.

**Proposal:**
- time the ONNX graph call alone, against 150 ms;
- separately require that the whole step keeps up in real time, for example
  p95 ≤ 50% of `step_s`.

### V3: the sanitised public tree

`scripts/build_public_tree.py` reads `git archive HEAD` only.

**Excluded, each with its reason in a manifest:**
- Bellevue-derived results;
- corpus per-frame data derived from third-party footage;
- third-party frames;
- **the submitted-document toolchain:** synopsis and progress-report
  builders, their content files, checkers and tests. They hold personal
  identity and are hands-off. They are excluded **unmodified**, and their
  publication is the owner's call.

**Verified:**
- 1,176 kept and 388 excluded;
- **0 leaks** on re-scan;
- **CI's fast suite passes inside the sanitised tree,** run as the single
  squashed commit a public branch would be.

**What running the suite there found and fixed:**
- **A test that would also have failed in GitHub CI:** it asserted that
  gitignored weights exist.
- **Bellevue-reading tests** now skip where their files are absent, and run
  everywhere else.

**Still the owner's:**
- **704 kept files mention Bellevue,** mostly code and documents quoting
  aggregates. They are listed for review, because whether aggregates may be
  published is part of the licence decision.
- **The public branch's workflow** must drop the synopsis steps. This is
  recorded as a to-do in the manifest.

**This builder does not resolve licensing or authorise publication.**

### Decisions now with the owner

1. **V1 design:** the paired P105-hours sample, and label-source effect
   replacing human-fed forecasts.
2. **V2 criterion 6:** split it into ONNX-call ≤ 150 ms and whole step ≤ 50% of
   `step_s`, before the real camera.
3. **V3:** review the 704 flagged files; confirm the toolchain exclusion; make
   the repository private.
4. **Labellers and the camera window**, both still to be named.

## P135 — the owner's V1/V2/V3 decisions implemented: V2 split frozen and re-run, the V1 gate built and validated, the V3 review classified (2026-10-17)

### V2: criterion 6 split, frozen before any real-camera run

**The owner decided** (`PREREGISTRATION_V2_S65.md`, `cc9a550`):

| part | what it times | passes if |
|---|---|---|
| **6a** | the model call alone, `session.run` on the CPU provider: the PRD's "MFSTNet ≤ 150 ms on server CPU via ONNX" | p95 ≤ 150 ms |
| **6b** | the whole edge step | p95 ≤ 1,000 ms **and** max ≤ 2,000 ms |
| **6c** | transport | p95 ≤ 200 ms |

p50, p90, p95, p99 and max are reported for each, and the pass statistic is
fixed in writing. The model call is timed by a pass-through wrapper, so the
forecaster is unmodified. Everything stays in memory.

**The stand-in re-run** (local footage at camera pace, real ONNX graph, real
local server). The host: Intel family 6 model 191 CPU, with the backbones on
an RTX 4050 Laptop GPU and ONNX on the CPU provider.

| part | p50 | p95 | max | result |
|---|---|---|---|---|
| **6a** model call | 259.8 ms | **325.9 ms** | 381.9 ms | **FAIL** (150 ms) |
| 6b edge step | 360.7 ms | 482.3 ms | 1,680 ms | PASS |
| 6c transport | — | 35.9 ms | — | PASS |

Criteria 2–5 and 7 pass again.

**The split revealed what the single number hid.** The earlier 434.5 ms
"processing" figure was mostly **the model itself**: MFSTNet's ONNX graph on
this laptop's CPU runs at about **2× the PRD budget**. The GPU backbones are
cheap.

This is a stand-in result. It does not close S65, and nothing was tuned
around it. **Any optimisation would be its own pre-registered change:** INT8
export (ADR-007), or a GPU execution provider.

### V1: the protocol and the gate, before any human label

- **Design approved:**
  - same-moment sampling from P105's test hours;
  - three distinct questions: detector error, deployed-system error, and
    label-source sensitivity. The third is explicitly **not** a measurement
    of a human-fed forecaster;
  - the 30-moment subgroup minimum. Eastgate LOW (n = 8) is descriptive only.
- **`PREREGISTRATION_V1_DRAFT.md`** is written. It becomes
  `PREREGISTRATION_V1.md`, which the main set's page requires, only after the
  inter-rater gate passes.
- **Q3's four alternatives are fixed now:**
  - the detector target;
  - a 6-frame aggregation;
  - a labeller swap;
  - imputing unusable frames.

  "Robust" means the sign holds under all four.
- **The inter-rater gate is code** (`scripts/v1_pilot_agreement.py`):
  - ICC(2,1), two-way random, absolute agreement, single rater, at least 0.80;
  - unusable frames excluded pairwise, and flagged above 5%;
  - κ on moment classes, reported;
  - one revision and re-pilot allowed, then it stops;
  - each attempt is scored once.
- **The ICC implementation is validated against the published Shrout and
  Fleiss (1979) example:** 0.2898 against the published 0.29.

  **Disclosed:** a first version of that test asserted a value I had guessed
  instead of computed. It failed, and was replaced by the published example
  before any commit.

### V3: the review classified, and the public frames listed

- **The 704 flagged files are given a first-pass category,** restrictive
  first (`experiments/results/publication/v3_review.csv`):

  | category | files |
  |---|---|
  | corpus-derived results (LOCO and baseline CSVs) | **645** |
  | dataset-specific material | **44** |
  | licence references | **4** |
  | aggregate results | **4** |
  | mention only | **7** |

  **A category is not a legal judgement.** The owner's review decides.
- **The 18 third-party frames already public on `origin/main` are listed**
  (`already_public_frames.txt`) for the outreach and for removal (V3-5).
- **The submitted-document toolchain stays excluded, unmodified.**
- **The repository still reads PUBLIC.** Making it private is the owner's
  first step, before any push.

### A tooling hazard found and closed

The Bash tool turned `\b` and `\n` inside heredocs into a real backspace and
a real newline. That silently broke a regex in `build_public_tree.py`, and
for a while broke a string. A test caught the regex, and the bytes were
repaired. **A scan of every tracked file found no other backspace bytes.**
Edits involving escape sequences now go through `chr()` codes or the edit
tool.

### Still with the owner

1. Name the two labellers.
2. Set the camera window.
3. Make the repository private.
4. Review the classified list, and send the licence outreach.

## P136 — the repository is private (verified); the owner's disposition is applied to the public copy (2026-10-18)

**V3-1 is done by the owner, and verified here** (`gh repo view`):
- **PRIVATE**;
- **0 forks**;
- no GitHub Pages site;
- no releases.

The repository was public until now. **The 18 third-party frames are still in
`main`'s history** (`already_public_frames.txt`), and deleting them from the
tip would not remove them from history. They stay tracked for the removal and
licensing work. **Nothing has been pushed.**

**The owner's preliminary disposition of the 704 flagged files** (not a legal
clearance):

| category | files | disposition |
|---|---|---|
| corpus-derived results | 645 | keep **excluded** until the dataset terms are reviewed |
| dataset-specific material | 44 | keep excluded pending a file-level rights review |
| licence references | 4 | review individually |
| aggregate results | 4 | review individually |
| mention only | 7 | likely retain if no restricted data or unsupported claim |

**How it is applied** (`build_public_tree.py`):
- **The corpus-derived results** (`loco/`, `baselines_loco/`, `loco_*.csv`)
  are excluded.
- **The Bellevue pipeline scripts** are excluded: the p9x/p10x builders and
  evaluators, the audit pages, the fetchers and the V1 scripts. So are the
  tests of those scripts.
- **A blanket exclusion of all 44 "dataset-specific" files would have removed
  `server/app.py` and `simulation/count_forecasts.py`** and broken the public
  build. These stay in, flagged, each with its disposition:
  - core code that only **names** a restricted path: kept, flagged for
    file-level review;
  - project records that quote aggregates (the build log, this changelog, the
    publication-readiness note): kept, flagged for redaction review before
    any release.

**The result:**
- **499 kept and 1,070 excluded;**
- **28 flagged,** each carrying its disposition in `v3_review.csv`;
- **0 leaks** on re-scan;
- **CI's fast suite passes inside the public copy.**

**A process slip, disclosed.** One commit (`2407ac1`, P136's first) landed with a
test failing, because piping pytest through `tail` hid its exit code. It was
corrected in `d43b93b`. **Commits now follow a check of pytest's own exit
status.**

**Still with the owner:**
- the labellers;
- the camera window;
- the file-level review of the 28;
- the licence outreach;
- **the go for V3-2:** push the feature branch only, open a draft PR, and read
  the CI. The repository is now private, so this is unblocked, but it is
  still a push.

## P137 — the first CI run on the private branch: an environment reproducibility finding, and the fix (2026-10-18)

**Context.** The owner authorised one private push of the feature branch, a
draft PR (#1) to `main` for CI only, and the CI review. Nothing was merged,
released or made public.

**The pre-push checks were limited, and are stated as such:**
- **The credential scan** found only the deliberate fake URL in the redaction
  test (`admin:hunter2`). That shows only what the scan's patterns checked;
  **it is not proof that no secret exists.**
- **No file is over 20 MB.** That says nothing about the rights to the 18
  third-party frames, or to the Bellevue-derived material in the branch's
  history. Both remain tracked blockers.

**Run 1, at `5c6566a`** (workflow runs 39098344382 and 39098349916): fast, dashboard, docs
and GitGuardian passed. **The model job failed one test:**
`tests/test_faw.py::test_a_committed_webster_tuning_row_reproduces_exactly`.
This re-runs P122's committed tuning episode: Webster at s = 660 pcu/h/m with
4 s lost time, on `pulsed`, seed 400, 1800 s, sublane 0.8, `total_delay=True`.

| metric | committed (Windows, SUMO 1.27.1) | CI run 1 (Linux, SUMO 1.28.0) | difference |
|---|---|---|---|
| `mean_total_delay_s` | 28.814 | 29.499 | +0.685 (+2.38%) |
| `mean_wait_s` | 16.263 | 16.698 | +0.435 (+2.67%) |
| `throughput` | 1,370 | 1,366 | −4 |
| `phase_switches` | 97 | 97 | 0 |

**The cause.** The model job installed `eclipse-sumo traci sumolib` unpinned,
and drew **1.28.0**. `requirements.txt` pins **1.27.1**, which produced every
committed SUMO result. `gymnasium` and `stable-baselines3` were unpinned in
the same job.

**The fix (`b7b891a`).** The job now installs `eclipse-sumo==1.27.1`,
`traci==1.27.1`, `sumolib==1.27.1`, `gymnasium==1.3.0` and
`stable-baselines3==2.9.0`. **The assertion was not changed.**

**Run 2, at `b7b891a`** (workflow runs 39098681046 and 39098683810): **every job passed.**
- **The versions installed, read from the run log:** exactly the five pins.
- **The reproduction test ran, and was not skipped.** Its only skip condition
  is a missing `traci`. The same test failed in run 1. The run-2 progress
  output shows no failure.

**What this establishes:**
- **Under SUMO 1.27.1, the committed Windows row reproduces exactly on the
  CI's Linux runner** (Python 3.12), in that tested environment.
- **The committed row does not reproduce under SUMO 1.28.0.** This is shown
  for **this one episode**.

**What it does not establish:**
- that every result changes between 1.27.1 and 1.28.0;
- that 1.28.0 is wrong;
- that other environment differences could never matter.

**It is now enforced.** `scripts/check_sim_versions.py` reads the five pins
from `requirements.txt` and compares them with what is installed. It exits 1
on any mismatch, naming each one. It runs in the model job before the
simulation suites, so drift becomes an explicit failure. A test checks that
it names every mismatch.

**Unchanged:**
- P130–P132 stay frozen;
- the forecasting claims and the baselines are untouched;
- the publication status is unchanged;
- PR #1 stays a draft, for CI only.

## P138 — the 19.4% (P82) is correct for what was run, and citable only as a qualified historical result; its qualifications in one place (2026-10-18)

**Status: applied 2026-10-21**, after the owner's review approved it. It
edits nothing in P82, does not reopen P130–P132, and changes no CSV, ADR-023
or `CLAIMS.yaml`.

**What P82 measured.** The figure "PPO beats Webster by 19.4%, d = −1.34" comes
from `experiments/results/benchmark_ppo/`, written at `30c82bb` under SUMO
1.27.1. It compares:
- **the policy:** one PPO policy, no-forecast, `phase_duration` action space,
  training seed 42, 500,000 steps;
- **the baseline:** best-tuned Webster;
- **the conditions:** 30 evaluation seeds in the constant `saturated` regime;
- **the outcome:** `mean_wait_s`, where the lower value is better.

**The numbers are correct for what was run.** P119 already said so. The
problem is that the qualifications were recorded in four separate places, while
the sentence travelled on its own: README.md line 37 and BUILD-LOG S38 quoted it
unqualified until this entry.

### The qualifications that apply, collected

1. **The comparison is not matched (P119).** The policy trained without the
   sublane model and was evaluated with it (`--lateral-resolution 0.8`). So the
   policy was scored on traffic dynamics it never trained on. We never measured
   how far this moves the 19.4%, in either direction.
2. **The arrival-time pattern is the same across all 30 seeds (P116 b).** In
   the constant regimes, `vehsPerHour` flows insert vehicles evenly spaced. Two
   seeds load identical vehicles at identical seconds and differ only in vehicle
   type, lateral placement and driver behaviour. So the bootstrap 95% CI of
   the paired difference in mean wait, [−3.41, −1.98] s, measures sensitivity
   to the vehicle mix. It does not
   measure demand variability.
3. **It is one policy, one regime and one arm (P82's own limits).** It has one
   training seed, so it ranks one initialisation against Webster, not the
   method (compare P54 on seed spread). It covers the saturated regime only, and
   the no-forecast arm only.
4. **The outcome is not ADR-021's.** `mean_wait_s` averages over completed
   trips only. ADR-021's protocol adopted `mean_total_delay_s`:
   `timeLoss + departDelay` over every vehicle, including unfinished and
   undeparted ones (ADR-021 Amendment 1).

### What does not apply, stated so the record is not over-corrected

- **The `keep_or_switch` actuation mismatch (P116 a) does not apply.** P82
  evaluated a `phase_duration` policy, and P116 already recorded that no
  committed performance result was affected.
- **The index-10 defect (P120) does not apply.** Under `phase_duration`,
  `phase_remaining` is structurally 0 in both harnesses (P11). Training and
  evaluation therefore agreed on it.

### P130: a different protocol, not a replication

P130 evaluated PPO and Webster with the training and evaluation sublane
configuration matched for its own protocol: `pulsed`, a `keep_or_switch`
action space, and 28 primary seeds. **It is evidence about that protocol, not
a direct replication of P82.** Under it, **every PPO arm had more delay than
both Webster arms.**
- **No-forecast PPO against tuned Webster:** +3.91 s of mean total delay,
  d +0.61, p = 0.003. This is descriptive and unadjusted (P128 §7).
- **On mean wait, the metric P82 used:** 24.37 s against 23.09 s. These are
  arm means only; no test was run on this metric.

P130 differs from P82 in traffic regime, action space, training seeds and
outcome metric. It therefore **neither replicates nor refutes P82**.

### What follows

- **The 19.4% figure may be cited only as a qualified historical result for
  the specific P82 experiment.** It must not be presented as evidence that PPO
  generally outperforms Webster. The citable form is:
  > Under constant saturated demand, a phase-duration PPO policy, trained
  > without the sublane model and evaluated with it, had 19.4% lower mean wait
  > than best-tuned Webster. This was over 30 evaluation seeds that varied the
  > vehicle mix but not the arrivals, with one training seed (P82). Under the
  > distinct `pulsed` protocol, with training and evaluation matched, no PPO
  > arm had lower delay than either Webster arm (P130).
- **C1 is not changed by this entry.** Narrowing C1 already waits on the guide
  (MEMO-2026-10-17, S63zm). This entry adds evidence to that decision and does
  not make it.
- **Where the sentence appears:**

  | Place | Action |
  |---|---|
  | `README.md` | Refreshed with this entry; the figure appears only in its qualified form |
  | `BUILD-LOG.md` S38 | Notes rewritten to the qualified form, citing this entry |
  | The submitted synopsis report | Untouched, because the synopsis is hands-off. The owner decides whether anything changes there |

  The synopsis report states the comparison through `synopsis_content.py` from
  `benchmark_ppo/benchmark_stats.csv`.

### Optional resolution: a new study, not a rerun

The way to replace the qualified number with a matched one is a
**pre-registered re-measurement**:
1. Retrain the `phase_duration` no-forecast policy with the sublane model, on
   training seeds 42, 1 and 7.
2. Evaluate it against the tuned Webster arm, with `mean_total_delay_s` as the
   primary outcome, on the regime or regimes named before any result.

It would be a new entry with its own lock, and P82's CSVs would stay as
committed. Whether to run it is the owner's call.

## P139 — the model backup would have saved under a quarter of the artifacts and then reported PASS (2026-10-18)

**Status: applied 2026-10-21**, after the owner's review approved it. The fix
is in `scripts/backup_models.py`, the test is `tests/test_backup_models.py`,
and the regenerated manifest is `experiments/results/model_artifacts.sha256`.
Before this entry, the repository's script was the unpatched one; the S66
archive was built by the patched copy, from outside the repository.

**What was found.** `backup_models.py pack` copies the files the committed
manifest lists, and `verify` re-hashes the copy against that same manifest.
The manifest was last written on 2026-10-15 (`5ac3722`), and it covers only
`models/mfstnet` and `models/onnx`.

A read-only comparison against `models/` today found **218 artifacts, 1,063
MB, outside the manifest**. The manifest covers 83 files and 312 MB. No listed
file was missing from disk, and no hash had changed.

| directory | files not covered | what they are |
|---|---|---|
| `models/ppo` | 36 | every PPO checkpoint and sidecar, **including the nine the ceiling locks fingerprint** (P126, P128) |
| `models/mfstnet` | 172 | the Bellevue, P99 and P100 checkpoints (P92–P106) |
| `models/onnx` | 3 | the P99 export |
| `models/detector` | 3 | the S11, S14 and S15 trained YOLOv8s weights |
| `models/external` | 4 | third-party weights, including `best_xl_ITD_v1.2.pt`, on which the corpus pipeline depends |

**Why it matters.** S66 described the backup as "83 files, 312 MB, against
the committed manifest". A pack run that day would have copied those 83 files
and printed `PASS`. A later disk failure would then have lost:
- the evidence that P130's locks point to;
- every model trained since 2026-10-15.

### The fix

| Safeguard | What it does |
|---|---|
| **Coverage** | `SOURCES` names all five model folders: `mfstnet`, `onnx`, `ppo`, `detector`, `external` |
| **No packing from a stale manifest** | `check` compares the manifest with the disk and names three kinds of disagreement: a file not in the manifest, a file gone from disk, and a changed hash. `pack` runs `check` first and copies nothing if it fails |
| **No silent drops** | Regenerating the manifest refuses to drop an artifact the previous manifest recorded. A vanished file must be named with `--allow-removed`, or nothing is written |
| **The copy matches the inventory exactly** | `verify` fails on each of the following: a missing file, a corrupt file, a file in the copy's model folders that the manifest does not list, and a copy whose own manifest is not the committed one |

Together, `pack` = `check` (manifest = disk) + copy + `verify` (copy =
manifest). A backup that passes is therefore the complete current inventory,
with no file added and none left out.

### Tests

`tests/test_backup_models.py` has 12 cases: **all 12 fail against the current
script, and all 12 pass against the patched one.** They cover:
- every source folder is covered;
- a fresh manifest passes;
- each kind of staleness is named;
- `pack` refuses a stale manifest and copies nothing;
- `pack` + `verify` succeed on a current manifest;
- a regenerated manifest refuses to drop a recorded artifact unless it is
  named;
- `verify` fails on a missing file, a corrupt file, an unexpected file, and a
  foreign manifest.

### The real inventory, checked read-only (2026-10-18)

| | committed manifest | fresh manifest |
|---|---|---|
| entries | 83 | **301** (252 mfstnet, 6 onnx, 36 ppo, 3 detector, 4 external) |
| size | 312 MB | 1,375 MB |
| `check` against the five folders | **FAIL**: 218 not in the manifest | **PASS** |
| committed entries kept, with identical hash | — | 83 of 83 |
| locked hashes matching the disk (9 checkpoints, 9 sidecars) | 0 of 18 listed | **18 of 18** |

Regeneration started from the committed manifest, so any dropped entry would
have been refused. None was dropped.

**Where the inventory comes from.** Every fresh inventory was hashed directly
from the five source folders under `models/`, never from the archive.
- **The packer** (`make_trained_weight.py`, step 1):
  1. hashes `artifacts()` on disk;
  2. refuses if any committed entry is gone or has changed;
  3. builds the archive from that validated inventory.
- **An independent re-hash of the source folders** afterwards produced 301
  files, **identical to the archive's record**, with all 83 committed entries
  present at the same hash.

The chain is therefore:

| Link | What holds |
|---|---|
| source folders → fresh manifest | removals need explicit authorisation |
| manifest → archive | the build used the validated inventory |
| archive → manifest | `verify` passed |
| cloud copy → archive | the owner's download check |

### It has already been used once, from outside the repository (S66)

The patched script ran from a scratch copy against the real `models/` folders.
It produced `trained_weight.zip`:
- **contents:** 301 artifacts, 1,375 MB;
- **sha256:** `0745587bf7b0348acec518f1c35b6d54eb46b25d39d11bfcdc3cf4562ea519d3`;
- **checks before upload:** `check` passed, `pack` verified its own copy, and
  a separate standalone verifier extracted and re-hashed all 301 files.

The archive was uploaded to the owner's private Google Drive. **The owner
reports** downloading and checking it. That check is owner-reported: its
output was not retained, and it was not independently audited.

### Applied (2026-10-21)

| Step | Result |
|---|---|
| `check` against the committed 83-entry manifest, before regenerating | **FAIL**, 218 disagreements, as found on 2026-10-18 |
| `backup_models.py manifest` | 301 entries, 1,375 MB, **identical** to the inventory the S66 archive recorded on 2026-10-18 |
| The 83 prior entries | **83 of 83** kept, every one at its identical hash |
| `check` against the regenerated manifest | **PASS** |
| Locked hashes (9 PPO checkpoints, 9 sidecars) against the manifest | **18 of 18** |
| `p126_audit.py --verify`; `ceiling_eval.verify_lock` on both locks | OK; OK, OK |
| `tests/test_backup_models.py` | 12 of 12 |

Future backups go through `pack`, which runs `check` first, and an
independent `verify`.

**What this does not do:**
- **It publishes nothing.** The destination is the owner's own storage.
- **It does not settle any licence.** The Bellevue-derived checkpoints and the
  third-party weights are backed up for recovery only, and their licence
  status is unchanged.

## P140 — a malformed payload crashed the server path instead of being refused (2026-10-18, revised 2026-10-21)

**Status: applied 2026-10-21** in the integration batch, after the owner's review approved it. Test: `tests/test_contract_malformed.py`. The review evidence (patch, run
outputs, mutation script) is held outside the repository.

**Found** while checking the SAD's forecast-validation wording against the
code.

**Revision 3** (finding D): the refusal message no longer includes the
underlying exception's text, which could quote the offending value. The tests
now assert that a planted marker is absent from the `ContractError` message
and from the HTTP response. Two related problems that P140 does **not**
change are recorded as P141 candidates (see the end).

**Revision 2** adds:
- top-level non-object JSON and invalid UTF-8 (review finding A);
- a separate record for processing failures (finding B);
- the test coverage finding C asked for.

### The defect

`contracts.mqtt.decode` refused a wrong schema version cleanly. Several other
malformed payloads escaped as bare Python exceptions instead of
`ContractError`:

| Payload | Escaped as | Why |
|---|---|---|
| unknown class, mode or source | `ValueError` | the enum conversion ran outside the `try` |
| missing `predictions` | `KeyError` | the field was read outside the `try` |
| `predictions` not a mapping | `AttributeError` | `.items()` ran outside the `try` |
| top-level `[]` or `null` | `AttributeError` | `data.pop("v")` assumed a JSON object |
| invalid UTF-8 bytes | `UnicodeDecodeError` | only `JSONDecodeError` was caught |

### Consequences

| Path | What happened | Evidence |
|---|---|---|
| `POST /prediction/{id}` | **HTTP 500, not 422** | Reproduced on the current code: unknown class, missing `predictions`, `[]` and `null` |
| `server/mqtt_ingest.py` | `_on_message` caught only `ContractError`. With paho-mqtt 2.1.0, `suppress_exceptions` defaults to `False`, and paho re-raises a callback's exception in the network thread that `loop_start()` runs. **Expected effect: one malformed message stops all forecast ingest, silently** | Read from paho's source and the installed default. **Not reproduced against a live broker** |

No stored data was affected: decoding fails before anything is written.

### The fix

1. **Decoding.**
   - `UnicodeDecodeError` is caught next to `JSONDecodeError`.
   - A parsed value that is not a JSON object is refused before `.pop`.
   - The enum conversions and field reads move inside the refusal. There,
     `TypeError`, `ValueError`, `KeyError` and `AttributeError` become
     `ContractError`.
   - **The new refusal messages name only the exception type,** never its
     text, which can quote the offending value; this applies to both the JSON
     and the schema refusal. `from exc` keeps the detail for in-process
     debugging. The messages reach HTTP 422 responses.
   - A `ContractError` raised by a payload's own validation passes through
     unchanged.
   - `ContractError` is itself a `ValueError`, so existing callers that catch
     `ValueError` keep working.
2. **The ingest: refusals and failures are kept apart.**
   - **`refused`** holds `ContractError` only. That is a malformed message,
     the producer's fault.
   - **`failed`** is new. It holds any other exception, such as a locked
     database. That is the server's own processing failure, and the message
     may well have been valid.
   - Each failure is recorded as `(topic, "ExceptionType, N bytes")` and
     logged at ERROR level through the `server.mqtt_ingest` logger, with the
     topic, the exception type and the size only.
   - Neither list nor the log ever holds payload content (NFR-13). The
     exception message is not recorded either, because it can quote the
     payload.
   - Nothing escapes the callback, so the network thread keeps running.
   - **Retrying a failed store is a separate design decision, not made
     here.** A failed message is observable but dropped.

The wire format, the schema version and every valid payload are unchanged.

### Tests

`tests/test_contract_malformed.py` has 18 cases.
- **Against the current code:** 17 fail. The one that passes is the
  valid-payload control, which is expected.
- **With the patch:** all 18 pass.

| Group | Cases |
|---|---|
| `decode` raises `ContractError` | 8: unknown class, missing `predictions`, `predictions` not a mapping, top-level array, top-level `null`, invalid UTF-8, unknown heartbeat mode, unknown command source |
| A valid payload still decodes | 1 (the control) |
| HTTP answers 422 | 4: unknown class, **missing `predictions`**, top-level array, top-level `null` |
| Ingest: a malformed message, then a valid one | 4: unknown class, array, `null`, invalid UTF-8. Each asserts 1 refused, **1 stored** (ingest still works) and 0 failed |
| Ingest: a storage failure, then a valid message | 1. Asserts 1 failed, 0 refused and 1 stored, and that the failure is logged |

**Planted-marker checks.** These cases put a marker string where it could
leak, and assert it is absent:

| Case | Marker placed in | Asserted absent from |
|---|---|---|
| unknown class, unknown mode, unknown source, invalid UTF-8 | the payload | the `ContractError` message |
| unknown class over HTTP | the payload | the HTTP 422 body |
| unknown class and invalid UTF-8 through the ingest | the payload | the ingest records and the captured log |
| storage failure | the exception text | the `failed` record and the captured log |

Some cases carry no marker, because there is no content to leak: missing
`predictions`, `predictions` not a mapping, top-level array and `null`. The
tests use a temporary SQLite file, never the server's own database.

**The marker checks are a real guard.** Putting `{exc}` back into the refusal
message makes 4 tests fail: the unknown class, mode and source `decode` cases,
and the HTTP unknown-class case. `mutate_exc.py` is the mutation script.

**Regression check.** It ran in a `git archive HEAD` snapshot with the patch
applied. Eight related suites passed (142 passed, 3 skipped):
- contract, server and safety;
- edge node, persistence forecaster, count forecaster and edge forecaster;
- live MQTT, which skips without a broker.

One suite was left out: `test_dashboard_evidence.py` fails in the snapshot
**with and without** the patch. It reads commit metadata, and an archive has
no `.git`. It passes in the repository, in the local full run on 2026-10-18
(1,206 passed, 3 skipped).

### To apply, once approved

1. Apply the patch and add the test.
2. Run the full suite in the repository.
3. Commit them together: the contract fix, the ingest handling and the test,
   nothing else.

### Not changed by P140: two P141 candidates

These were found while checking finding D. Both are pre-existing, and both are
outside P140's narrow scope. They are recorded so P140's wording does not
imply them away. They were probed over HTTP in the snapshot, with a temporary
database.

1. **Some existing validation messages echo payload values into the HTTP
   422 body.** These include:
   - the schema version (`v{version}`);
   - the `model` field (`got {model!r}`);
   - the prediction keys.

   A marker placed in each was echoed back to the sender. The message goes
   only to the client that sent the payload; the ingest records and logs
   never hold it.
2. **Three fields are not type-checked:** `confidences`, `horizon_sec` and
   `ts`. A string in any of them was accepted (HTTP 200) and stored in SQLite
   (3 of 3 rows). The 4,096-byte payload cap bounds this, but free text up to
   that size can cross the edge boundary. The SAD's statement that schema v2
   admits no free text is therefore too strong. The SAD draft has been
   corrected.

## P141 — the two network-facing payloads are typed to the field, and a refusal no longer repeats what the sender wrote (2026-10-21)

**Status: applied 2026-10-21** in the integration batch, after the owner's review approved it. It is applied on top of P140.
Test: `tests/test_contract_fields.py`.

### Scope

The server decodes only two payload types, through
`POST /prediction/{id}`, `POST /count_forecast/{id}` and the MQTT ingest:
- `CongestionPrediction`;
- `CountForecast`.

They are therefore where schema v2's aim, "no free text across the edge
boundary", has to hold. P141 changes **only the validation and the refusal
messages of these two types**, plus `decode`'s version message and its
exception net. The wire format, the schema version and every other payload
type are unchanged.

### What changes

| Field or message | Before (P140 base) | After |
|---|---|---|
| `confidences` values | any value accepted and stored | a finite number in [0, 1]; `bool` refused |
| `horizon_sec` (prediction) | unchecked | the integer 60 (PRD §8.2) |
| `horizon_sec` (count forecast) | `!= 60`, so `60.0` passed | the integer 60; `60.0`, `"60"` and `True` refused |
| `ts` (both) | unchecked | a finite number, `0 < ts < 4,102,444,800` (2100-01-01) |
| `gate_value` | `true` passed, since `bool` is an `int` | a finite number in [0, 1], or null |
| count values | `true` passed | a finite number in [0, 200] |
| model id (both) | `re.match` with `$`, so a trailing `\n` passed | `fullmatch` |
| a JSON integer beyond float range, e.g. `10**400` | `OverflowError`: HTTP 500, filed by the ingest as the server's own failure | refused as `ContractError`: HTTP 422, filed as `refused` |
| refusal messages | quoted the submitted version, model, approach keys, lane names and values | name the field and the rule only |

**Kept stable,** because existing tests match on them: "never MED",
"Version mismatch", "gate_value", "same lanes", "config@12-hex" and
"approaches".

### Why each bound is what it is

- **`confidences` in [0, 1].** Every producer emits a probability: MFSTNet's
  softmax maximum, or persistence's measured precision. So does the PRD §17
  example.
- **`horizon_sec = 60`.** This is PRD §8.2's horizon. `CountForecast` already
  required it, and no producer overrides the default.
- **`ts < 2100-01-01`.**
  - **Why an upper bound:** without one, a JSON integer of ~300 digits passed,
    and `encode` stored every digit. That was about 128 chosen bytes per
    message.
  - **Why no lower epoch bound:** existing fixtures use `ts=1.0`
    (`test_mqtt_contract.py`, lines 236 and 246).
  - **What is left:** `ts` and every other float field still carry about 8
    bytes of chosen precision each. That is inherent in a numeric field, and
    it is stated here rather than claimed away.

### Tests

`tests/test_contract_fields.py` has 115 cases.

| Run | Result |
|---|---|
| With P141 | **115 pass** |
| On the P140 base | **83 fail, 32 pass** |

The 32 that pass on the base are expected:
- **9 compatibility controls** must pass on both: the valid payloads, the
  three real producers' shapes, and a valid store over HTTP.
- **23 are regression pins** for refusals the old code already made: the
  count horizon, the gate range, the count range, and the "same lanes" and
  missing-`v` messages.

| Group | What it proves |
|---|---|
| Bounds | Bad `confidences` (10 values), `horizon_sec` (9 × 2 topics), `ts` (12 × 2 topics), `gate_value` (7) and count values (7) are each refused with a message naming the field |
| Model id | A trailing newline is refused on both topics |
| No echo, `decode` | 16 cases, each with a planted marker. They cover every rewritten message, plus "same lanes", missing version and overflow, pinned so a later edit cannot start quoting. The marker is absent from the `ContractError` |
| No echo, HTTP | The same 16 cases: 422, the marker absent from the body, and **zero rows stored**. The old check could not fail, because the database is created only after a successful decode; it now counts rows |
| Overflow | `10**400` in a confidence, the gate, the ts, a count, or a count's ts: HTTP 422, and the ingest gives refused 1, failed 0, stored 0 |
| Compatibility | Valid payloads, integer bounds (0, 1), an integer epoch `ts` (PRD §17), a null gate, and the three real producers' shapes round-trip. A valid store over HTTP gives exactly 1 row per table |

**Mutation check** (`mutate_p141.py`). Each of the 7 behaviours was reverted
one at a time, and **all 7 were caught**:
- the gate accepting `bool`;
- a count accepting `bool`;
- the count horizon accepting `60.0`;
- no upper bound on `ts`;
- `match` restored for each model pattern (two mutants);
- overflow escaping.

The two `bool` mutants are caught by the `True` and `False` cases themselves,
not only by the overflow case.

**Regression check** in a `git archive HEAD` snapshot with P140 and P141
applied: 10 suites, **275 passed, 3 skipped**. The suites:
- P141's and P140's new tests;
- contract and server;
- edge node, persistence, count forecast and edge forecaster;
- live MQTT, which skips without a broker;
- safety.

`test_dashboard_evidence.py` was left out as before: it needs `.git`, and it
passes in the repository.

### Compatibility, checked

| Area | Finding |
|---|---|
| **Producers** | No in-repo producer or consumer breaks: `edge/persistence.py`, `edge/forecaster.py`, `edge/count_forecast.py`, `edge/node.py`, the scripts and the dashboard. An independent review read all of them, and both real forecasters round-trip under P141 |
| **Intended tightenings on the wire** | A payload with `horizon_sec` sent as `60.0`, or with `ts` 0, was accepted before and is now refused with 422. No in-repo producer sends either |
| **numpy scalars** | `np.float64` is accepted, because it subclasses `float`. `np.float32`, `np.int64` and `np.int32` are now refused at construction. **Before P141 they failed anyway**, at `encode()` ("not JSON serializable"), so none could reach the wire. Producers convert with `float(...)` and `round(...)` |
| **Stored rows** | `GET /…/latest` re-decodes the stored payload. A row stored before P141 that P141 refuses (a string `ts`, say) would make that endpoint return 500. **No server database exists on this machine** (`data/server/` is gitignored and absent), so no real row is affected. Any database carried over from an earlier deployment should be checked before P141 is applied |

### Not changed by P141: a P142 candidate, found by the same review

These are outside the two payload types, so they are left for P142. They are
listed so that no document claims the boundary is closed while they remain.

| Issue | Severity | Detail |
|---|---|---|
| **The intersection id is unvalidated free text** | must-fix | It comes from the URL path, or from the MQTT topic level. It is stored in SQLite and echoed in responses, and the 4,096-byte cap does not apply to it. A 12,000-character path id and a 48,000-character topic id were both accepted and stored. The ingest also logs the full topic, which therefore carries this text. **This is the largest remaining free-text channel.** The fix is a closed id pattern, checked in `route()` and in every handler that takes an id |
| **Framework-level echoes on the same endpoints** | should-fix | With `Content-Type: application/json`, FastAPI's own 422 quotes the whole submitted body. `/history?limit=` quotes its input. The 404 replies from `/…/latest`, and `/history`, quote the id |
| **`/observation`** | adjacent | `emergency_approach` is free text, stored in the `reason` column and echoed. An unknown approach key is quoted in its 422 |

## P142 — the intersection id is a closed pattern wherever it enters, and no framework path repeats what the sender wrote (2026-10-21)

**Status: applied 2026-10-21** in the integration batch, on top of P140 and
P141, after the owner's review approved revision 2. Test:
`tests/test_intersection_boundary.py`.

**Integration fix (2026-10-21), found by the full suite before the commit.**
- **The failure.** Revision 2 imported `Mount` from `starlette.routing`, in
  `server/app.py` and in the test. Starlette is only a transitive dependency
  of FastAPI and is not pinned, so `test_requirements_complete.py` failed
  (NFR-08, clean-machine reproduction).
- **Why the review runs missed it.** Those runs covered the related suites,
  not this test.
- **The fix.** Both imports now use `fastapi.routing.Mount`, the identical
  class, through the pinned `fastapi`. There is no new dependency and no
  change in behaviour.

**Revision 2 (2026-10-21)** closes the access-log gap the P142 review found.
- **The gap.** The filter logged any path made of plain tokens that matched a
  route. But a route can match an id the contract refuses:
  `/history/SECRETMARKER.x`, where `.` is allowed in a segment but not in an
  id. And a static mount matches any sub-path: `/dashboard/SECRETMARKER`.
- **The fix.** An API route's path is now logged only when every path
  parameter is an `intersection_id` that passes `INTERSECTION_ID`. A mount is
  logged as `<mount>/<static>`, never with its sub-path.

- **The patch** is `P142-boundary.patch`: 472 lines, 8 files, diffed against
  the P141-patched tree.
- **The test** is `tests/test_intersection_boundary.py`.

Both are held outside the repository.

**Applying it.** The stack P140 → P141 → P142 applies cleanly to `HEAD`
(`1967e55`). The result is identical to the tested tree, apart from line
endings: the checkout uses CRLF.

### Why

The intersection id travels **outside** every payload:
- in the URL path of five endpoints;
- in the MQTT topic level;
- in the `/observation` body.

So the 4,096-byte payload cap never applied to it. P141's review stored a
48,000-character id through the MQTT topic. P142's own review then found
three more echo channels outside the application code, plus three unbounded
fields on `/observation`, one of which was a safety bypass.

### What changes

| Area | Before | After |
|---|---|---|
| **The id** | Any text of any length, stored, echoed and logged | `INTERSECTION_ID = [A-Za-z0-9_-]{1,32}`, matched in full and defined once in `contracts/mqtt.py`. It is checked in both store functions (shared by HTTP and MQTT), in both `GET …/latest` handlers, in `/history`, in the `/observation` body (pydantic pattern) and in `route()` |
| **Edge** | A node with a bad id published, and the server dropped every message silently | `EdgeNode` refuses a bad id at start-up |
| **Trailing-slash redirect** | Starlette answered `/history/<anything>/` with a 307. Its `Location` header repeated the raw path (48 KB in a test), the query string and the `Host` header, before any check ran | `redirect_slashes=False`: a plain 404 with no `Location` |
| **FastAPI's 422** | It quoted the submitted value (`input`), and named sender-chosen keys in `loc` | One handler keeps `type`, `loc[:2]` and `msg`. It drops `input` and `ctx` |
| **uvicorn access log** | It logged every refused id and every query string verbatim; one line was 6,057 characters | A filter rewrites the logged target. **An API route's path is logged only if every path parameter is an `intersection_id` passing the contract's rule**; otherwise it is `<refused path>`. **A static mount is logged as `/dashboard/<static>`**, never with its sender-chosen sub-path. No route matched: `<unmatched path>`. A query becomes `?<query>`. The filter is installed when the module is imported, and is verified under real uvicorn |
| **404 replies** | Quoted the id | Fixed text |
| **`/history?limit=`** | `-1` returned every row, because SQLite reads `LIMIT -1` as no limit | `limit ≥ 1`; still clamped at 500 |
| **`/observation`, counts and queues** | Any signed 64-bit integer was stored and returned by `/history`; `10**30` gave a 500 | Integers in 0 to 10,000 (`MAX_OBSERVED`) |
| **`/observation`, heartbeat age** | Unbounded: `1e300` produced a 381-character stored `reason`. **`NaN` compared false against the timeout, so it skipped the FR-A06 fallback** | Finite and in 0 to 1,000,000 s |
| **`/observation`, emergency approach** | Free text, stored in `reason` and echoed | `N`, `S`, `E` or `W`. Lower case is normalised, as `SignalGuard` always has done |
| **`/observation`, `forecast` and `forecast_age_s`** | Unbounded, and unused by the server | Closed and bounded the same way; still unused |
| **Ingest** | Records and logs held the raw topic; a refusal was not logged at all | Topics are labelled `<unrouted topic>` until the id checks out. Refusals are logged as a warning with the label, type and size |
| **Dashboard** | Accepted an id of any length; a 33-character id showed an error | Same 32-character limit as the server |

### One existing test changed — please review

`tests/test_server_app.py::test_an_unknown_approach_is_refused` asserted that
the bad key ("NORTH") **was** echoed in the 422. That echo is what P142
removes.
- **What still holds:** the test's purpose, that a typo'd key is refused
  rather than read as zero traffic. It still asserts the 422.
- **What it now also checks:** that the error names the `counts` field and
  lists the allowed approaches.
- **What is reversed:** only the echo assertion. It now requires "NORTH" to be
  absent.

### Tests

`tests/test_intersection_boundary.py` has 118 cases.

| Run | Result |
|---|---|
| With P142 | **118 pass** |
| On the P141 base | **94 fail, 24 pass** |
| **The 9 cases added in revision 2, against revision 1's filter** | **7 fail**: the 3 dotted-id paths and the 4 static-mount paths. The other 2 are a 33-character id, which revision 1 already refused, and a 32-character id, which must still be logged |

The 24 that pass on the base are all compatibility controls: valid ids,
valid observations, uppercase and lowercase emergency approaches, the stale
heartbeat fallback, the clamp, valid ingest and a valid edge node. They must
pass both before and after.

The cases cover:
- **Ids:** seven invalid kinds, plus a trailing-newline case:
  - too long;
  - 12,000 characters;
  - a dot, a space, non-ASCII, `+` or `%`.

  Each is checked across all five HTTP endpoints, `/observation`, the MQTT
  ingest (records **and** log), `route()`, `intersection_of()` and
  `EdgeNode`.
- **Framework echoes:** a JSON-typed body, unknown keys, broken JSON, a bad
  `limit`, trailing-slash redirects (including a reflected `Host` header), and
  **the formatted access-log line** for 13 targets.
- **Static mount:** 4 targets under a real static mount, which the fixture
  adds the way `server.app` does when `dist` exists.
- **`/observation` bounds:** 13 out-of-bound cases, `NaN`/`Infinity`
  heartbeats, and 5 in-bound cases.

**"Stores nothing" is checked by counting rows.** The clamp test inserts 600
rows and asserts that exactly 500 come back.

**Probes the HTTP tests rely on:**
- **Ids reach the handler.** A spy on `check_intersection_id` shows that
  percent-encoded ids arrive decoded (`'SECRETMARKER\n'`), so the refusal is
  the server's, not the client's.
- **The log filter works under real uvicorn**, with a built `dist`, so the
  static mount exists. `probe_access_log.py` starts the server with uvicorn's
  default logging and sends 10 hostile requests and 1 valid one, including
  `/history/SECRETMARKER.x`, `/prediction/SECRETMARKER.x/latest`,
  `/dashboard/SECRETMARKER` and `/dashboard/SECRETMARKER/x.js?q=…`.
  - **What was logged:** `<refused path>`, `/dashboard/<static>` and
    `/dashboard/<static>?<query>`.
  - **No `Location` header came back**, and **no marker appeared in any log
    line**.
  - **Output:** `probe-access-log-stacked.txt`.

**Mutation check** (`mutate_p142.py`; output in `p142-mutation.txt`). Each of
the **29 protections** was reverted one at a time, and **all 29 were caught**.
That includes:
- **the two gaps the review found, put back:** trusting a route match, and
  logging a mount's sub-path;
- the redirect;
- each part of the access-log filter;
- each `/observation` bound;
- the lowercase normalisation;
- the edge check;
- the refusal log;
- the `match`-with-`$` mistake.

All files are restored byte for byte after the run.

**Regression check** in the patched snapshot: 11 Python suites give **384
passed, 3 skipped**. The dashboard's vitest gives **13 of 13**, including the
new length case. `test_dashboard_evidence.py` was left out as before: it needs
`.git`, and it passes in the repository.

### Compatibility

| Area | Finding |
|---|---|
| **Ids in use** | Every id in the repo fits the pattern: `j1`, `j3`, `j7`, `j9`, `live`, `verify`, `bench`, `int01`, `a`, `b`, `x`, `nowhere`, and the dashboard's default `j1`. The `+` subscriptions still render |
| **Clients** | Nothing in the repo parses a 422 or 404 body. The dashboard maps 404 to "unavailable" by status alone |
| **Stored data** | Rows stored before P142 under an id outside the pattern can no longer be read: `GET …/latest` now returns 422 for them. No server database exists on this machine, so no real row is affected; a carried-over database should be checked first, as for P141 |
| **Wire tightenings** | A lowercase emergency approach keeps working. Counts above 10,000, negative counts, and non-finite or negative ages are now refused. No in-repo producer sends any of them |

### What remains, stated rather than claimed away

1. **A valid id is still a small channel.** A matching id is stored and
   echoed: about 24 chosen bytes per message. Only a configured registry of
   known intersections closes that, and it is not proposed here. One
   `SignalGuard` per distinct valid id is also kept in memory, without bound.
2. **Numeric fields still carry a few bytes each** through their digits (as
   recorded in P141).
3. **Two 422 shapes.** A bad path id gives a string `detail`; framework
   validation gives a list. Nothing parses either.
4. **Kept on purpose:**
   - The unknown-count-key check in `/observation` is now unreachable, but is
     kept as a second line and no longer quotes the key.
   - Dropping `ctx` currently removes nothing sensitive; it is a precaution.
5. **The static `/dashboard` mount**, which exists only when `dashboard/dist`
   is built, was probed with a throwaway `dist` (removed afterwards).
   - **No redirect and no echo.** `/dashboard?q=<marker>` with a hostile
     `Host`, `/dashboard/assets?q=<marker>` and `/dashboard/<marker>` all
     returned a plain 404, with no `Location` and no marker.
   - **One usability change.** `/dashboard` without the slash is now a 404
     where it used to redirect, so the dashboard URL is `/dashboard/`.
     - The only place the URL is written without the slash is P107's
       changelog entry. That entry is historical and is left as it is.
     - The TIM, when it is written, should give `/dashboard/`.
6. **The vitest run went through a junction** to the repo's
   `dashboard/node_modules`, so it may have refreshed its gitignored `.vite`
   cache. No tracked file changed.

## D1–D2 — the two Phase C integration findings, fixed narrowly (2026-10-21)

**Status: applied 2026-10-21** in the integration batch, on top of P142, after
the owner's review approved it. Tests: `tests/test_edge_classes.py`, and the
banner assertions in `dashboard/src/dashboard.test.jsx`.

By the owner's direction, these Phase C findings carry no P-number.

### D1 — the edge could not publish counts from the deployed detector

**The defect.** The ITD detector says 'two wheeler', 'autorickshaw', 'LCV',
'bicycle' and 'pedestrain'. `VehicleCount` accepts PRD §12.2's eight classes
only. So `EdgeNode.tick` raised an uncaught `ContractError` on the first
two-wheeler. That ended the edge loop, and with it FR-A06's local cycle.

**No new taxonomy decision.** The mapping the project already uses is applied:

| Detector class | Contract class | Where it was already decided |
|---|---|---|
| two wheeler | motorcycle | `scripts/pseudo_label.py` `ITD_TO_OURS` |
| autorickshaw | auto-rickshaw | the same; the wire spelling uses a hyphen |
| car, bus, truck | unchanged | the same |
| LCV | **truck** | the same, and DATASETS §6: "`Truck`+`LCV` to `truck`" is a merge of like things. PRD §12.2's truck includes "tempos" |
| pedestrain | pedestrian | the same (ITD's spelling) |
| bicycle | **dropped, never merged** | `class_mapping.yaml` and `ITD_TO_OURS`: a bicycle's PCE is not a motorcycle's |

**No PCU weighting is introduced.** A kept vehicle counts one.

#### What changed

- **The mapping lives once**, in `indiatrafficnet/class_mapping.yaml` under
  `itd_mapping` (the project's "versioned, not remembered" authority). Every
  ITD class has an explicit entry. A test keeps the yaml equal to
  `pseudo_label.ITD_TO_OURS`, so the two cannot drift.
- **`edge/classes.py`** is new. `load_itd_mapping()` reads the mapping and
  converts it to wire spelling, and refuses a target the contract lacks.
  `normalise()` is **total**: every name ends up kept, dropped by decision, or
  unknown. It never raises.
- **`EdgeNode`** gains two fields:
  - `detector_classes`, the mapping. The default is `None`, meaning the
    caller already speaks contract names, so existing callers are unchanged.
  - `excluded`, a tally of dropped or unknown classes. It is diagnostic only
    and never goes on the wire.
- **`EdgeNode.publish_counts` never raises:**
  - **A dropped class** (bicycle) is left out, and the rest is published.
  - **A class with no decision at all** withholds that lane's count, with a
    warning. Publishing the rest would report fewer vehicles than were seen,
    which is the missing-as-zero error P97a forbids.
  - **Any remaining `ContractError`** is logged and returns `False`.
  - **A withheld publish is not an acknowledgement.** So a node whose counts
    can never be delivered **still falls back after 10 s** (FR-A06), rather
    than dying or appearing healthy.
- **The forecasters' input is unchanged.** Persistence and ridge still read
  the detector's lane totals, which include bicycles: the corpus counted them,
  and the frozen specs were calibrated on them. Only the `vehicle_count`
  per-class breakdown follows the contract's taxonomy, and that topic is not
  ingested by the server.
- **The two counts are documented as separate, deliberately.** This is the
  review point.
  - **Where:** `edge/classes.py`'s docstring, and the SAD's new §4.3, which
    has a table of both counts.
  - **The rule:** never feed the forecasters the filtered count, and never
    publish the raw totals as a contract count.

#### Evidence

| Check | Result |
|---|---|
| `tests/test_edge_classes.py` | 10 cases: **10 pass with D1, 0 pass without it** |
| Related suites (P140–P142 tests, contract, server, edge node, forecasters, safety, vehicle ids, IDD mapping) | **421 passed, 1 skipped** |
| Live-broker test (`test_mqtt_live.py`) | 4 of 4 |
| **Phase C re-run on the full stack, with no harness adapter** (the node maps classes itself) | 300 samples. **0 of 900 lane count publishes undelivered.** 224 bicycle detections excluded (see the note below). 271 + 241 forecasts stored byte-identical. Dashboard matches the API. F1 to F4 all pass. **The forecast values are identical to the `HEAD` run.** Report: `phaseC/out-stacked/` |

**About those 224 bicycles.** At NE8th they are mostly the painted
bicycle-lane symbol that P95 documented: detected as a bicycle in nearly every
frame, inside the west lane. Dropping bicycles from `vehicle_count` removes
that artefact from the wire. **The forecasters still see it, as they did in
calibration.**

### D2 — the dashboard's safety banner was out of date

| | Text |
|---|---|
| **Before** | "Open safety issue P97a: the controller's state contract encodes a missing approach as 0.0, the same value as LOW." That stopped being true at P110 |
| **After** | "In the controller's state, 0.0 means an approach has no forecast and LOW is encoded as 1/3 (ADR-020 as amended, P110). Still open: P97a Part 2, the controller's behaviour under forecast faults, which is deferred." |

**Also updated:** `dashboard/README.md`, which repeated the old sentence.

**Left as written:** P107's changelog entry, which is historical.

**Tested:** a dashboard test now asserts the new wording and the absence of
the old. It passes 13 of 13 with D2, and fails on the old banner. The banner
is visible in `phaseC/out-stacked/dashboard_after_run.png`.

### Not changed by D1–D2

`CLAUDE.md`, the project instruction file, still says: "The P97a
missing-approach representation issue remains unresolved by this dashboard."
That was stale in the same way the banner was. The same batch corrects it,
with the owner's approval (CLAUDE-md-P97a).

## D3 — the deployed edge path is a committed program, `python -m edge.run` (2026-10-21)

**Status: implemented 2026-10-21**, after the owner's go-ahead. As with D1–D2,
it carries no P-number. It resolves HLD §9-C1 and meets
[PLAN-D3](../plans/PLAN-D3-edge-entry-point.md).

### What was missing

The deployed edge path (detector → counting → persistence + ridge → publish →
fallback) had only run inside the Phase C harness, outside the repository.
`edge/node.py`'s docstring advertised `python -m edge.node`, which never
existed. The TIM and SOP could not describe starting it.

### What changed

- **`edge/run.py`**, new. It adds no logic of its own: counting is
  `mfstnet.corpus.counting`, the forecasters are `edge.persistence` and
  `edge.count_forecast` (ADR-027), and publishing, the class mapping (D1) and
  FR-A06 are `EdgeNode`'s. `EdgeLoop` takes detections, never a frame, so it
  cannot keep one.
- **Refused at start-up:** an intersection id outside the P142 pattern, an
  invalid broker port, a missing file, a lane file that is neither reviewed nor
  a corpus manifest (P23), an approach mapping that does not cover every lane
  exactly once, a camera with no thresholds or with thresholds calibrated on a
  different number of lanes, and `--source camera` without `STMS_CAMERA_URL`.
- **Not refused:** a broker unreachable at start-up. FR-A06 exists for a node
  that cannot reach the server, so the program starts, warns, and runs the
  local cycle after the timeout.
- **A camera outage still runs FR-A06.** While the stream reconnects, the node
  is ticked once a step with no counts, so the timeout is still measured from
  `last_ack`. The missing step is a gap, so the forecast windows restart.
- **The camera URL** is read only from `STMS_CAMERA_URL` and never logged.
  OpenCV's own messages, which can quote the URL, are silenced in camera mode.
- **`edge/node.py`**: the docstring now points to `edge.run`.

### Evidence

| Check | Result |
|---|---|
| `tests/test_edge_run.py` | 43 of 43, one or more per PLAN-D3 criterion |
| Mutation check | 12 protections reverted one at a time; all 12 caught |
| Live run 1: 300 samples of the Phase C footage, real amqtt broker, server and ingest | exit 0. **271 class and 241 count forecasts stored, identical payload for payload to the stacked Phase C run** (timestamps aside). 224 bicycle detections kept from the wire, the same as Phase C. No new file in the snapshot besides the server's store |
| Live run 2: real-time pacing, broker killed and restarted | `FR-A06: no successful publish for 12.0s` logged; `link restored` 1.0 s after the restart; exit 0 |

The live runs used a `git archive` of `7484de8` plus `edge/run.py`. The footage
is Bellevue NE8th, for internal engineering use only; its licence is
unresolved. The run's harness and outputs are held outside the repository with
the other review evidence.

### One test expectation corrected

A sample refused for a missing lane does not itself reset the window. The test
first expected the next sample to forecast; it does not, because the refused
step leaves a 4 s hole and `SampleBuffer` resets on any gap over 3 s. That is
the intended behaviour: a window is never bridged over a missing step. The test
was corrected, not the code.

### Not changed

No model specification, frozen evidence or signal-control architecture. No
forecast feeds signal timing (ADR-027, P97a), and the program drives no signal
hardware.

### Still open

- **A clean-environment check of the start-up**, before the TIM and SOP.
- **The counting settings are module constants** (`DEFAULT_WEIGHTS`, conf 0.45,
  imgsz 992), each overridable on the command line. They are the settings the
  persistence thresholds and ridge coefficients were calibrated under, not
  hyperparameters, but by this repository's own convention they belong in
  configuration. Recorded, not moved.
- **Live-camera behaviour** is S65's measurement. D3 tests the reconnect path
  with stand-ins only.

## D4 — the clean-environment check, and the setup corrections it called for (2026-10-21)

**Status: applied 2026-10-21**, after the owner's go-ahead for the corrections
the clean-environment report specified. As with D1–D3, it carries no P-number.

### The check

Could a teammate follow the documented setup from a clean checkout and start
`python -m edge.run` without undeclared local files? It ran on two fresh clones
at `3e6f63c`, on Python 3.12.10 (primary; CI's version) and 3.14.4, outside
the repository.

**Answer: not from the repository alone.**
- **What reproduced:** the code, its dependencies, its start-up checks, and
  the full suite: 1,501 passed, 24 skipped, 0 failed.
- **What did not:** four prerequisites are not in the repository (below), and
  the setup documents were wrong in five places.

### Corrections

| Correction | Where |
|---|---|
| **`sumo-data==1.27.1` pinned.** `eclipse-sumo 1.27.1` requires `sumo-data` with no version, so a clean install drew 1.28.0 beside SUMO 1.27.1, and the preflight did not notice. `sumo-data` ships binaries, not only data. This is the P137 class of drift. **No reproduction failure was shown:** the committed P137 episode passed under 1.28.0 as well | `requirements.txt`; `check_sim_versions.py` now checks it; its test covers the drift; the CI model job, which installs the SUMO packages one by one, pins it too |
| **Python 3.12 everywhere.** The manual said 3.11, with a warning about torch 2.3.1 that no longer applies | Execution Manual §0.3 and its Week 0 checklist; `CLAUDE.md` |
| **The edge start-up is documented:** the prerequisites and their status, the command and its arguments, and how starting differs from delivering | Execution Manual §0.7 (new) |
| **The broker:** `requirements.txt` installs none, and NFR-11 is unmet by the current code (below) | Execution Manual §0.7 |
| **Docker Compose is not committed.** Two documents said it was; no compose file has existed on any branch. PRD §22.3's tree is a target layout and is unchanged | `docs/01-requirements/NFR.md`; `CLAUDE.md` |
| **The fallback procedure:** (a) no longer stops a nonexistent `mfstnet_service` and points to `ForecastGate`'s tests; (b) no longer uses Linux `systemctl`, and times the switch from the last acknowledged publish | Execution Manual §5.3 |
| **Disk and Shapely:** pip's cache needs more than 3 GB (3.1 GB measured), or a redirect; Shapely is not imported anywhere, so its warning can be ignored | Execution Manual §0.3 |

### NFR-11 is unmet by the current code

Neither MQTT client sends credentials. `edge/mqtt_transport.py` and
`server/mqtt_ingest.py` have no username or password option, and no file in
`edge/`, `server/`, `contracts/` or `scripts/` calls `username_pw_set` or
`tls_set`. An authenticated broker would refuse both. **Configuring an
authenticated broker does not fix this**; credential support is a code change,
not made here and not yet authorised.

### Re-check after the corrections

A fresh clone at `3e6f63c` with only this batch applied, installed by the
corrected manual on Python 3.12.10:

| Check | Result |
|---|---|
| Install (§0.3 commands, unchanged) | torch and `requirements.txt` exit 0; `pip check` clean; **`sumo-data` resolves to 1.27.1**; otherwise the same 117 packages as the first clean install |
| `check_env.py` / `check_sim_versions.py` | exit 0 / exit 0, now listing `sumo-data` |
| P137 reproduction, preflight test, `ForecastGate` tests (`tests/test_forecast_state.py`) | 24 passed |
| §0.7 start-up | `--help` exit 0; a missing `--source` refused with exit 2; with no broker, it starts, warns, and exits 0 with nothing delivered and no file written |
| §0.7 delivery | the first class forecast returned 200 from `GET /prediction/{id}/latest` |
| §5.3 (b) | broker stopped: `FR-A06: no successful publish for 12.0s` (10.6 s after the stop); `link restored` 4.5 s after the broker restarted; exit 0; only the server's database written |
| Full suite in the clone | **1,501 passed, 24 skipped, 0 failed**, exit 0 |

With no broker at all, the switch read 19.8 s. Nothing was ever acknowledged,
so it ran from node creation and included the 5 s connection wait and the
detector's warm-up before the first step.

**The 24 skips** are all environmental. 21 are gitignored or untracked
material: PPO checkpoints, local corpora and local footage. The other three
are the pretrained download and two live-broker tests that need
`AMQTT_PYTHON`. So the live-broker test did not run from the clean clone.

### What these checks do not show

- **The broker** was an anonymous amqtt stand-in. This shows the data path,
  not Mosquitto compatibility or NFR-11.
- **The input** was synthetic, with the committed 4-lane manifest as a
  start-up fixture. Every forecast was LOW or 0.0. That is start-up evidence
  only, not detector accuracy, forecast quality or camera suitability.

### Still open

- **Teammate access to the detector weights.** The only copy is the owner's
  private backup (S66). Its identity is verified against the committed
  manifest (`06006ecb5fe5…6b00`). Its licence is unresolved, and it is not to
  be redistributed.
- **A camera-matched lane file**, and thresholds for that camera (ADR-017).
- **Broker credentials in the code (NFR-11)**, and a committed broker
  configuration.
- **The environment:**
  - `py -3.12` needs a Python 3.12 install, and the check used python.org's
    NuGet package;
  - the disk redirect was needed on this machine, which has only 2–4 GB free
    on C:, and the documented commands were not tried without it.
- **Out of scope here:** moving the detector settings into configuration, and
  S65.

## D5 — the edge's counting settings are configuration, not script defaults (2026-10-21)

**Status: applied 2026-10-21**, after the owner's go-ahead to start the
remaining work. As with D1–D4, it carries no P-number. It closes the open item
D3 recorded: "The counting settings are module constants".

### What changed

- **`indiatrafficnet/class_mapping.yaml`.** The `counting` block already held
  `confidence_threshold: 0.45`, the declared operating point ADR-002 derives
  every label from. It now also holds `detector_weights` and `imgsz`.
  - **No value is new.** All three are what the committed corpus manifest
    records (`data/corpus/manifest.json`: `best_xl_ITD_v1.2.pt`, conf 0.45,
    imgsz 992), and so what the persistence thresholds and the ridge
    coefficients were calibrated under.
  - **No target-camera calibration is introduced.** The block's
    `PROVISIONAL` status and its re-sweep note are unchanged.
- **`edge/run.py`** reads all three from that block (`load_counting`), and no
  longer carries `DEFAULT_WEIGHTS`, `DEFAULT_CONF` or `DEFAULT_IMGSZ`.
  - A block missing a setting is refused at start-up, never filled in.
  - `--weights`, `--conf` and `--imgsz` still override it on the command line.
  - `EdgeLoop` no longer has a default threshold: the caller passes one.
- **Execution Manual §0.7** says where the defaults come from.

### Evidence

| Check | Result |
|---|---|
| `tests/test_edge_run.py` | 46 of 46, of which three are new: the defaults follow the config file it is pointed at, and the command line still overrides; the committed block equals the corpus manifest's detector, conf and imgsz; a block missing `detector_weights` is refused |
| Related suites (`test_idd_mapping.py`, `test_edge_classes.py`) | pass, including the existing pin of `confidence_threshold: 0.45` |
| Mutation check | the three literals restored as defaults, and the missing-key refusal removed, one at a time: 4 of 4 caught |

### Not changed

- The values themselves, the forecasters, the class mapping and the contract.
- Anything about the four open deployment prerequisites (D4).

## D6 — both MQTT clients can authenticate to the broker (NFR-11) (2026-10-21)

**Status: applied 2026-10-21**, after the owner's go-ahead for MQTT
credential support as its own change. As with D1–D5, it carries no P-number.

### What was wrong

NFR-11 requires an authenticated broker: `allow_anonymous false`, verified by
an unauthenticated connect attempt being refused. Neither client could meet
it. `edge/mqtt_transport.py` and `server/mqtt_ingest.py` had no username or
password option, so a broker configured as NFR-11 requires would have refused
both (D4).

### What changed

- **`contracts/broker.py`**, new. `Credentials` holds the username and
  password and leaves the password out of its repr.
  `credentials_from_env()` reads `STMS_MQTT_USERNAME` and
  `STMS_MQTT_PASSWORD`:
  - both set: credentials;
  - neither set: `None`, an anonymous connection;
  - one without the other: refused with `CredentialError`. The message names
    the missing variable and never quotes a value.
- **`MqttTransport` and `PredictionIngest`** take `credentials=` and send them
  on connect.
  - A refused connection is recorded in `connect_refused` as the broker's
    reason code only, so a refusal can be told apart from a broker that is not
    there.
- **`edge/run.py`** reads the credentials at start-up.
  - Half a credential exits with code 2.
  - With neither set, it warns that it is connecting anonymously.
  - A refusal is logged with its reason code, and the FR-A06 local cycle runs
    as for any broker the node cannot reach.
- **`python -m server.mqtt_ingest`** does the same, and exits naming the
  broker's reason when refused.
- **The existing no-credentials behaviour is kept** for development and tests.
- **Execution Manual §0.7** documents the two variables and what has and has
  not been verified. The README and PLAN-D3 now describe the third deployment
  prerequisite as an authenticated deployment broker, not missing code.

### Evidence

| Check | Result |
|---|---|
| `tests/test_broker_credentials.py`, new, no broker | 11 of 11. Neither variable or both; the password is kept out of the repr; four partial configurations refused, each naming the variable and not the value; each client calls `username_pw_set` only when given credentials; a refusal is recorded by reason code without the password; the ingest refuses half a credential at start-up |
| `tests/test_edge_run.py` | 49 of 49, of which three are new: credentials read from the environment and kept out of the settings' repr, and half a credential refused (exit 2) without echoing either value |
| `tests/test_mqtt_live.py`, `AMQTT_PYTHON` set, on an **amqtt broker that enforces authentication**: `allow_anonymous: false` plus `FileAuthPlugin` with an Argon2 password file, and a random password for each run that is in no committed file | 7 of 7. Three are new: both clients refused without credentials; a wrong password refused and absent from every log and output; authenticated clients carry a prediction from the edge to the server's store |
| Reason codes, edge and ingest each | anonymous, wrong password, unknown user: refused with `Not authorized`. Correct credentials: accepted |
| Mutation check, with the live broker | each protection reverted once: each client dropping its credentials; half a credential connecting anonymously; the password shown in the repr; an error naming a value; `edge.run` ignoring the environment; each client not recording a refusal. **8 of 8 caught** |

### What this does and does not establish

- **It establishes that NFR-11's verification passes against an amqtt broker
  configured to enforce authentication.** An unauthenticated connect attempt
  is refused, for both clients, and authenticated clients work end to end.
- **It does not establish NFR-11 for the deployment broker.** Mosquitto, the
  broker the PRD names, was not tested, and no broker configuration is
  committed, Mosquitto's or any other. Setting it up with `allow_anonymous
  false` and a password file is part of the third open deployment
  prerequisite.
- **It does not add TLS.** Credentials cross the network in clear text to the
  broker, as MQTT over plain TCP does. NFR-11 asks for username and password
  authentication; encrypting the link is a separate decision.

### Still open (D4, updated)

1. Teammate access to the detector weights; the licence is unresolved.
2. A camera-matched lane file, and thresholds for that camera.
3. An authenticated deployment broker. The code is ready; the broker's
   configuration and a test against Mosquitto are not.
4. The disk and Python-install constraints.

## D7 — the edge's recovery log and the ingest's start-up line say what is true (2026-10-22)

**Status: applied 2026-10-22**, after the owner's decisions on the TIM and SOP
discrepancies (items 4 and 6). As with D1–D6, it carries no P-number.

### What was wrong

- **The recovery log implied signal control.** When publishes were
  acknowledged again, `edge/run.py` logged `link restored; the server is
  driving again`, and `EdgeNode.tick` gave its reason as `link healthy; the
  server is driving`. No server drives a signal (ADR-027, P97a).
- **The ingest's start-up line named one topic of two.** It printed
  `subscribed to stms/+/congestion/prediction on …`, although the ingest also
  subscribes to `stms/+/count/forecast` (ADR-027).
- **The line was buffered.** Run with its output redirected to a file, it did
  not appear until the ingest exited (the TIM validation, 2026-10-22).

### What changed

- **`edge/run.py`** logs `link restored: publishes are acknowledged again`.
- **`edge/node.py`'s** `tick` reason reads `link healthy: publishes are
  acknowledged`.
- **`server/mqtt_ingest.py`** has a new `subscription_summary()`. It renders
  every topic in `INGESTED`, so the start-up line is `subscribed to
  stms/+/congestion/prediction and stms/+/count/forecast on HOST:PORT`, and
  it is printed with `flush=True`.
- **Execution Manual §5.3** quotes the new log line.

### Evidence

| Check | Result |
|---|---|
| `tests/test_edge_run.py`, one new test | A LOCAL → NORMAL transition logs exactly the new line, and neither it nor the `tick` reason mentions a server or driving |
| `tests/test_broker_credentials.py`, one new test | The start-up line names both ingested topics |
| Focused suites (`test_edge_run`, `test_broker_credentials`, `test_edge_node`) | 76 passed |
| Mutation check | Each old wording, and the one-topic line, restored one at a time: 3 of 3 caught |

### Not changed

- **The ingest's Ctrl+C shutdown**, deferred by the owner (item 5). It still
  ends with a `KeyboardInterrupt` traceback and does not disconnect first.
- Behaviour: only the text of two messages and one `tick` reason changes.

## D8 — the SAD describes the MQTT subscriptions that exist (2026-10-22)

**Status: applied 2026-10-22**, after the owner's decision on the TIM and SOP
discrepancies (item 3). It is documentation only. As with D1–D7, it carries no
P-number.

### What was wrong

SAD §4.2's topic table gave `edge → server` as the consumer of three topics no
server component subscribes to. The ingest subscribes to the two forecast
topics only (`server/mqtt_ingest.py`, `INGESTED`):
- **`system/heartbeat`** and **`vehicle_count`** are published by the edge and
  received by nothing. HLD §9-C4 had already recorded `vehicle_count`.
- **`emergency/detect`** is defined, but nothing outside the tests publishes or
  subscribes to it.

§6.2 called the server's trigger "the reported heartbeat", which read as the
MQTT heartbeat. It is the age that the caller of `POST /observation`
reports.

### What changed

- **SAD §4.2** names the actual consumer of each of those three topics, and
  says what follows from it: the edge's `LOCAL` mode is visible only in the
  edge's log, not on the server or the dashboard.
- **SAD §6.2** says the server's 10 s trigger is `seconds_since_heartbeat` in
  `POST /observation`, not the MQTT heartbeat. This keeps the edge's local
  fallback and the server's safety behaviour distinct.
- **The SAD's status line** records the correction.

### Not changed

No code, and no other SAD section. Whether the server should ingest the
heartbeat is a design question, not decided here.

## A37 — NFR-12 is aligned with ADR-008: a bearer token on HTTP writes, reads open (2026-10-22)

**Raised** 2026-10-22 · **Affects** PRD §10 NFR-12, NFR.md, RTM, SRS §3.3 ·
**Status** ADOPTED by the owner

**The conflict.** NFR-12 said "Dashboard: JWT-based login, 24h token expiry".
ADR-008, accepted by the owner, replaced it with "a single shared password over
local network", whose stated intent is that unauthenticated users cannot
control signals. NFR.md's verification text was never changed, and neither
mechanism was ever implemented.

The requirement also named the wrong surface. The dashboard only reads, and
the risk lies in the server's `POST` endpoints, which accepted any caller.

**The amendment.** NFR-12 becomes:
- **writes:** every HTTP `POST` needs a shared-secret bearer token;
- **reads:** stay open.

It is verified by:
- a `POST` without the token, or with a wrong one, returns 401;
- with no token configured, every `POST` returns 401;
- `GET` endpoints answer without a token.

JWT stays superseded by ADR-008. The owner chose this option (A) over HTTP
Basic on every endpoint (B) and JWT (C).

**What it is not.** It is not a secured deployment. The token crosses plain
HTTP, and reads are open, so the server stays on 127.0.0.1. The MQTT broker's
authentication is NFR-11 (D6).

## D9 — every HTTP write needs a bearer token; reads stay open (2026-10-22)

**Status: applied 2026-10-22**, after the owner's decision (option A, A37). As
with D1–D8, it carries no P-number.

### What changed

- **`server/app.py`.** A new `require_write_token` guards all three `POST`
  routes (`/observation`, `/prediction/{id}`, `/count_forecast/{id}`):
  - it needs `Authorization: Bearer <token>`, with the scheme matched
    case-insensitively;
  - the token is compared with `STMS_API_TOKEN` by `hmac.compare_digest`;
  - with the variable unset or empty, every write is refused, and no setting
    turns this off;
  - every refusal is one fixed 401, `a valid bearer token is required to
    write`, with `WWW-Authenticate: Bearer`. It never says what was wrong and
    never repeats what was sent;
  - an unauthenticated request is refused before its body is validated;
  - a lifespan hook warns at start-up when the variable is unset;
  - `write_auth_header()` is what an HTTP client sends.
- **The clients.** `scripts/benchmark_live.py` (`HttpTransport`) and
  `scripts/verify_edge.py` send the header, from the same variable.
- **The MQTT ingest is unaffected.** It calls the store functions directly.
- **`GET` endpoints are unchanged**, and the dashboard needs no token.
- **Tests.** `tests/conftest.py` configures a synthetic token for every test,
  and gives a `write_headers` fixture to the six existing test clients that
  write.
- **Documents.** The PRD's NFR-12 row, NFR.md, RTM and SRS (A37); an
  implementation note on ADR-008; the dashboard README; TIM §8, §12 (check 4a)
  and §13; SOP §1, §9.3 and §11.

### Evidence

| Check | Result |
|---|---|
| `tests/test_api_auth.py`, new | 36 of 36. A missing token is refused on every route. Wrong and malformed tokens are refused without echo: a wrong value, the `Basic` scheme, `Bearer` with nothing after it, a bare token, and a missing space. The right token writes as before on every route. The scheme is case-insensitive. An unauthenticated invalid body gets 401, not 422. A token unset, empty or blank refuses everything. Reads stay open. The start-up warning names the variable only. No token appears in logs, output or responses. The comparison is constant-time. Both clients send the header from the environment |
| Existing server-facing suites, with the token | 296 passed: the behaviour with a valid token, `/observation` and validation errors included, is unchanged |
| Mutation check | 10 protections removed one at a time: each route's guard, fail-closed, the constant-time comparison, no-echo, the scheme check, the start-up warning, and each client's header. **10 of 10 caught** |

### What this does not establish

- **Read protection.** `GET` endpoints are open by decision.
- **Transport security.** The token crosses plain HTTP. Mosquitto and TLS are
  the next, separate change.
- **A secured deployment.** The other deployment prerequisites are unchanged.

## D10 — MQTT over TLS with mandatory verification; Mosquitto verified in a test configuration (2026-10-23)

**Status: applied 2026-10-23**, after the owner's approval of the TLS design
and of Mosquitto option A. As with D1–D9, it carries no P-number.

### What changed

- **`contracts/broker.py`.** `STMS_MQTT_CA_FILE` turns MQTT TLS on.
  - `client_tls_context()` trusts that CA only. It requires the broker's
    certificate, checks the host name, and refuses anything below TLS 1.2.
  - `ca_file_from_env()` refuses a CA file that is missing, unreadable or not
    a certificate. It never falls back to plain TCP, and its message names the
    variable, not the path.
  - There is no setting that turns verification off.
- **`edge/mqtt_transport.py` and `server/mqtt_ingest.py`** take `ca_file=` and
  use that context. `tls` records it, because a failed verification looks like
  an unreachable broker to paho.
- **`edge/run.py` and `python -m server.mqtt_ingest`** read the variable at
  start-up:
  - an unusable file means exit code 2 (edge) or exit code 1 (ingest);
  - with it unset, they warn that the link is plain TCP;
  - a failure says "over TLS".
- **`scripts/tls_material.py`** makes throwaway CA material with the `openssl`
  command, so `cryptography` is not a new dependency. It lives in `scripts/`
  because a local helper under `tests/` cannot be imported by name here:
  `tests` is taken by an installed package.
- **Documents.** TIM §1, §7.3, §7.4, §13 and §15; SOP's opening, §6 and §9.3;
  Execution Manual §0.7; the README and PLAN-D3 prerequisite text; and the
  `CLAUDE.md` command list.

### Mosquitto

- **Version:** 2.1.2, the official Windows installer.
- **Source:** `mosquitto.org` and `download.eclipse.org` were unavailable
  during an Eclipse outage. The installer came from the Internet Archive's
  capture of `mosquitto.org`.
- **Integrity:** its SHA-1 equals the archive's record, and its SHA-256 equals
  the `microsoft/winget-pkgs` record for the official URL.
- **Not Authenticode-signed:** the project signs none of its Windows
  installers. The owner accepted this as a documented exception (option A).
  The hashes establish integrity, not the publisher.
- **Service:** the owner ran the installer to `D:`, which also registered a
  Windows service. The service was then removed, and the tests run Mosquitto
  in the foreground only.

The full record is in the setup notes, held outside the repository.

### Evidence

| Check | Result |
|---|---|
| `tests/test_broker_tls.py`, new, no broker | 12 passed: an unset or empty variable means plain TCP; a missing, directory, non-certificate or empty CA file is refused without its path; a real CA is accepted; the context always verifies; each client uses TLS only when given a CA, and never calls `tls_insecure_set`; no source file contains a verification bypass; the ingest refuses an unusable CA at start-up |
| `tests/test_mosquitto_live.py`, new, Mosquitto 2.1.2 | 18 passed: the right credentials are accepted and anonymous, wrong-password and unknown-user connections are refused (both clients); the edge reconnects after a broker restart; with the trusted CA, a prediction goes edge → broker → ingest → store over TLS; a wrong CA, an untrusted self-signed certificate and a hostname mismatch each fail (both clients); plain TCP to the TLS listener fails; no password, key path or key content in any log, and no password in the broker's log |
| `tests/test_edge_run.py` | Two new tests: an unusable CA file stops the program (exit 2) without echoing the path, and a usable one is read from the environment |
| Mutation check, Mosquitto live | 8 protections removed: 7 caught. **Not caught: removing the explicit TLS 1.2 floor.** Python's default is already TLS 1.2, so no test can tell the two apart. The line stays, as a floor that holds if the default changes |

### What this does not establish

- **A deployment broker.** No configuration, certificates, key storage or
  rotation for a real deployment are committed. The broker configuration in
  TIM §7.3 is a **test configuration**.
- **Mutual TLS.** Clients authenticate by password, not by certificate.
- **HTTP TLS.** The server stays on `127.0.0.1`.
- **CI coverage.** The live tests need `MOSQUITTO_EXE`, which CI does not set.

## D11 — CPU-only operation of the edge path, measured (2026-10-23)

**Status: recorded 2026-10-23**, after the owner approved the documentation
update. It is a measurement and changes no code. As with D1–D10, it carries no
P-number.

### Setup

| Item | Value |
|---|---|
| Path | The committed edge components at `5542e29`: `YoloDetector`, `EdgeLoop` and `file_frames` from `edge/run.py`. The counting settings came from `class_mapping.yaml` (D5): `best_xl_ITD_v1.2.pt`, conf 0.45, imgsz 992. Persistence and ridge forecasters |
| Footage | The NE8th recording (Bellevue, internal engineering use), 60 samples at the 2 s step after one warm-up sample. Frames stayed in memory |
| Publishing | An in-memory stand-in (`RecordingTransport`), so neither the broker nor a live camera was involved |
| Host (ADR-003) | The team laptop: Intel Family 6 Model 191 with 20 logical CPUs, RTX 4050 Laptop 6 GB, Windows 11. A proxy, not deployment hardware |
| CPU-only | `CUDA_VISIBLE_DEVICES=-1`, so `torch.cuda.is_available()` was False and the model ran on `cpu` |

### Results (ms per 2 s sample)

| | CPU-only | GPU |
|---|---|---|
| Decode + whole step, p50 / p95 / max | 1,077 / **1,119** / **1,145** | 74 / **84** / 108 |
| Detection alone, p50 | 1,052 | 48 |
| First sample, cold | 2,773 | 2,148 |
| Forecasts published, 60 samples | 34 | 34 |

A second run of each gave the same picture.

### Reading

- **CPU-only operation is demonstrated for this path and this recording.** It
  publishes the same forecasts as on the GPU, and its slowest sample, 1,145 ms,
  leaves about 855 ms before the next 2 s sample.
- **The detector is almost all of the cost.** Counting, the forecasters and
  publishing add under 1 ms, and decoding about 25 ms.
- **It does not meet the pre-registered p95 ≤ 1,000 ms step target** (V2,
  criterion 6b): the CPU p95 is 1,119 ms. That target applies to the MFSTNet
  path, and is quoted only for comparison.

### Not established

- Multi-hour thermal stability.
- CPU contention with other processes.
- Other hardware.
- Live-camera performance at deployment resolution (S65).
- MFSTNet on CPU, which P135 already measured: its model call is p95 325.9 ms
  and fails 6a.

The harness and its raw output are held with the review evidence, outside the
repository. TIM §3 and §15 are updated.

## D12 — the ingest stops cleanly (2026-10-23)

**Status: applied 2026-10-23**, after the owner's go-ahead. It closes the
limitation the TIM/SOP review deferred: on Ctrl+C, the ingest ended in a
`KeyboardInterrupt` traceback and did not disconnect from the broker. As with
D1–D11, it carries no P-number.

### What changed

- **`server/mqtt_ingest.py`.** `main` no longer waits on an untimed
  `threading.Event().wait()`. An untimed wait is not interrupted by Ctrl+C on
  Windows.
  - **`serve_until_stopped()`** polls a stop event every 0.5 s. On Ctrl+C
    (`KeyboardInterrupt`), or when the event is set, it calls `ingest.stop()`
    to disconnect, then returns a one-line summary: `stopped; N stored, M
    refused, K failed`. `main` prints it and exits 0.
  - **`stop_on_signals()`** sets the event on SIGTERM, and on SIGBREAK
    (Ctrl+Break) on Windows.
- **SOP §2.** The ingest's shutdown row now describes this behaviour, and
  says which of the signals were tested.

### Evidence

| Check | Result |
|---|---|
| `tests/test_ingest_shutdown.py`, new | 4 of 4: Ctrl+C disconnects and returns the summary, with no exception; a stop request disconnects; the wait is always timed, never untimed; SIGTERM and SIGBREAK set the stop event |
| `tests/test_mqtt_live.py::test_a_running_ingest_stops_cleanly`, new, real amqtt broker | **Run on Windows:** a real `python -m server.mqtt_ingest` process, once subscribed, gets Ctrl+Break. It exits 0, prints the summary, and writes no traceback. The test's SIGINT and SIGTERM variants exist for Linux and have **not been run** yet |
| Mutation check | 4 protections removed one at a time (untimed wait, no disconnect, Ctrl+C not caught, signals not installed): **4 of 4 caught** |

### Not established

**Ctrl+C itself on Windows** was not sent in a test. The console delivers it
to every process attached to the console, including the test runner. It goes
through the same `KeyboardInterrupt` path that the unit test covers.
Only Ctrl+Break, on Windows, was sent to a real process. The SIGINT and
SIGTERM variants run on Linux only, for example in CI, and have not been run.

### Not changed

The edge program's shutdown (already clean), the server's (uvicorn), and any
forecasting or contract behaviour.

## P143 — engineering proceeds on the foreign corpus; Indian-data acquisition on hold; the deployed edge counts exactly what the forecasters were trained on (2026-10-25)

**Decision (project owner, not the guide).** Engineering, integration and
system validation proceed on the footage the project has: Bellevue (US), Dhaka
and the M6. Indian-data acquisition is **put on hold** as active work:
- the six-viewpoint campus set (S19);
- licence-first collection, with the BMD-45 outreach (S54).

On hold means not done and not cancelled. Neither outreach email is recorded as
sent, and no Indian footage has been secured. Reopening S19 needs the guide's
decision on [MEMO-2026-08-22](MEMO-2026-08-22-part-b.md).

**What does not change.**
- **The two claims stay red.** `domain` (0 of 4 test cameras Indian) and
  `class_coverage` (HIGH 0/20/9/1, P57) still fail.
- **No change to `CLAIMS.yaml`, the checker, or the registered thresholds.**
- **Nothing measured on foreign footage is Indian-domain evidence**, and no
  document may present it as such.

**Why.** Completing the working system (Objective A) and showing that it holds
on Indian traffic (Objective B) are separate milestones. The second must not
block the first. The corpus pipeline is already dataset-portable:
- `cameras.json`, `sources.json` and `check_sources.py` gate a new source;
- triage → build → relabel → audit → cache → resplit processes it.

So onboarding Indian footage later is a data task, not an architectural one.
Portability is not equivalence. A new dataset brings its own geometry, vehicle
mix and congestion distribution, and is evaluated on its own.

### The evidence that came with the decision: train/serve count parity

Every earlier end-to-end test fed a **synthetic** video through lane centres
that matched no real scene. That covers the TIM validation at `d2db1c3` and the
clean-machine self-check v1–v3. `--camera` only selects the persistence
thresholds. Those runs established transport, not counting.

[`scripts/count_parity.py`](../../scripts/count_parity.py) closes that gap. It
runs the **deployed edge's own code** on the real footage:
- `edge.run.file_frames`;
- `edge.run.YoloDetector`;
- `count_frame`, at the settings the edge reads from `class_mapping.yaml`.

It compares the result with `data/corpus_p103/<camera>/counts.csv`, the counts
the persistence and ridge forecasters were calibrated and trained on (P103,
P105). A clip passes only if every lane value, every timestamp and the sample
count are identical.

| Scope | Clips | Samples | Lane values exact |
|---|---|---|---|
| All three P103 cameras: 150th/Eastgate (4 clips), 150th/Newport (3), 150th/SE38th (3) | **10 of 10 at parity** | 17,785 (one per 2 s, about 9.9 hours of footage) | **71,140 of 71,140** |

**The check detects skew.** Counting at confidence 0.60 instead of 0.45, on
the first 150 samples of each Eastgate clip, fails all four clips: 540, 528,
409 and 417 of 600 lane values exact. `--mutate-conf` exists for exactly this
and refuses to write over the real results.

**Scope of the claim.** For the full P103 corpus, at the committed counting
configuration, the deployed edge counting path reproduces the offline corpus
lane counts exactly. There is no train/serve skew in counting there.

What this does not establish:
- **forecast quality** (S67);
- **behaviour on the live camera stream** (S65);
- **any camera outside P103.**

**Provenance.**
- Per-sample results and `summary.csv` are in
  `experiments/results/bellevue_pilot/count_parity/`, with a sidecar: RTX 4050,
  torch 2.13.0+cu126, ultralytics 8.4.118.
- The run was made from the working tree at `bac812f` before this script was
  committed. That is why the sidecar names `bac812f`.
- The footage path is an argument and is never recorded.
- Frames are counted and dropped in memory (NFR-13).

### Board

- **S19 and S54:** ⬜ with an "on hold" note, following S50's precedent for
  owner deferrals. The board has no on-hold status, and its checker accepts
  only the existing symbols. Their history is kept.
- **S42 → 🔵,** reviewed against ADR-008 and FR-UI01–08:
  - **built:** the Live and Results regions;
  - **not built:** FR-UI01 signal state, FR-UI02, FR-UI03, FR-UI05, FR-UI08.

## D13 — the dashboard shows system status and forecast history (2026-10-25)

S42's approved scope after P143. Both additions are in the **live** region,
separate from Results (ADR-014). Both are read-only, so there is no video, no
source selection, no controls, no map, and no accuracy.

### What the server could and could not supply

- **Forecast history needed two read endpoints.** Forecasts were stored in
  SQLite, but nothing read them back: `/history` returns signal observations.
  Added:
  - `GET /prediction/{id}/history`;
  - `GET /count_forecast/{id}/history`.

  Both are newest first, check the id, take `limit ≥ 1` (default 30), and clamp
  at 500, as `/history` does (P142). An absent approach is listed, never
  filled; a real 0.0 count is kept. Reads stay open (D9).
- **No live latency exists to show.** The server dates everything by its own
  clock, because edge clocks drift, and records no edge-to-server delay. The
  panel therefore shows the **browser's measured round trip to `/health`**,
  labelled as such, and flags it above the 2 s refresh budget. Benchmark
  latency stays in the committed results, not in a live panel.
- **Service health is partial, and the panel says so.** `/health` reports only
  the server. The broker, the ingest and the edge do not report their own
  health, so a forecast stream going stale is how a stopped one shows.

### What the panels show

- **System status:**
  - the server: reachable, or the reason it is not;
  - each forecast stream: fresh, stale or missing, with its age, judged by the
    same validation as its own panel;
  - the measured round trip.
- **Forecast history:**
  - class and count tables, each validated whole. One bad row refuses the
    table rather than showing part of it;
  - "no forecast" for an absent approach, never 0 and never LOW;
  - the producing model on every row. Nothing is attributed to MFSTNet while
    ADR-027 assigns the live roles to persistence and ridge.

### Verification

| Check | Result |
|---|---|
| Server tests, `tests/test_forecast_history.py` | 7 new: order, absences, real zero, no mixing of the two stores, empty, `limit` bounds, a bad id refused unquoted, open reads |
| Dashboard tests, `npm test` | 22, of which 9 are new |
| Mutations: each new protection removed once | **9 of 9 caught.** The first run missed one: the allow-list test probed only the class pattern. It now probes both |
| Production build | compiles; 158 KB JS, 51 KB gzipped |
| Real server and real SQLite, in a browser | 3 class and 3 count forecasts posted through the API with a throwaway token. At 1280 px: newest first, absences shown, the 0.0 kept, round trip 10 ms. **Stale at 78 s** with no new forecast. **Unreachable within 5 s** of stopping the server. At 390 px: no page-level horizontal scroll; the class table scrolls inside its own box |

Not changed by this entry: the server's `EVIDENCE_LIMITS` text still says "P97a
(missing encoded as 0.0 = LOW in the controller's state) is open". That is out
of date since P110, where 0.0 means "no forecast". It is visible in the Results
region and is a separate correction.

## D14 — the evidence footnote states the encoding as it is since P110 (2026-10-26)

D13 recorded that the server's `EVIDENCE_LIMITS`, shown in the dashboard's
Results region, still said "P97a (missing encoded as 0.0 = LOW in the
controller's state) is open". That has been wrong since P110, checked against
P110's text: 0.0 at indices 11–14 is reserved for "no forecast", and LOW,
MEDIUM and HIGH are 1/3, 2/3 and 1.

The sentence now says what the live banner says (D2):
- neither forecast is connected to signal timing;
- 0.0 means an approach has no forecast, and LOW is 1/3 (ADR-020 as amended,
  P110);
- P97a Part 2, the controller's behaviour under forecast faults, is deferred.

`tests/test_dashboard_evidence.py` pins the new wording. It reads the constant
directly, so the test does not skip when the Bellevue results are absent.
Putting the old sentence back fails it.

## D15 — Docker Compose for the server stack (2026-10-26)

**Closes the D4 gap.** NFR.md specified Compose for the server stack and no
compose file existed. Docker B1 was approved by the owner, CI-only: Docker
Desktop is not installed on the development laptop, which has about 1 GB free
on C:.

### What is committed

| File | What it does |
|---|---|
| `docker-compose.yml` | `broker-init`, `mosquitto`, `server` and `ingest`; SQLite in a named volume both use; the broker's files in another |
| `deploy/server.Dockerfile` | one image for `server` and `ingest`, in three stages (below). It runs as a non-root user and has a health check on `/health` |
| `deploy/mosquitto.conf` | login and TLS on 8883 only, as D6 and D10 |
| `deploy/make_local_secrets.py` | a throwaway test CA, broker certificate, random passwords and API token, into gitignored `deploy/secrets/`. Refuses to overwrite. Local and CI only |
| `deploy/evidence_commits.py` | the commit behind every committed result file, read from the real history at build time |
| `deploy/smoke_test.py` | the real path, and the refusals (below) |
| `.dockerignore` | keeps secrets, data, models, frames and weights out of the build context |
| `.github/workflows/tests.yml` | job `compose`: build, start, smoke test, restart, smoke test again, then a scan for secrets in logs and image layers |

The image's three stages:
- **The dashboard,** built on Node 22, as CI builds it.
- **The evidence map,** made with git from the history.
- **The runtime,** Python 3.12.10. It installs only the four pins the server
  imports, taken from `requirements.txt`, which stays the authority.

The smoke test publishes over MQTT with TLS and the edge's login, then checks:
- the ingest stores both forecasts, and the server returns them, latest and
  history;
- W is listed as missing, and the real 0.0 is kept;
- the built dashboard is served;
- an anonymous client is refused, and a write without the token gets 401;
- the evidence names real commits.

With `--after-restart` it checks that the store persisted.

### Design decisions, each following the existing architecture

- **The dashboard is not its own container.** The server already serves the
  built dashboard at `/dashboard/`, same origin, and the image builds it in.
- **The edge is not in the stack.** It runs on its own device (ADR-003), with
  the detector weights and the forecaster specs, which no image may carry.
- **Passwords are hashed inside the broker's init container.** Nothing is
  hashed on the host, and the key and password file belong to the broker with
  mode 0600.
- **The broker's health check reads the listening socket from
  `/proc/net/tcp`.** It needs no login, so no credential is written into a
  health check.
- **No `docker compose up --wait`.** Some Compose versions count the one-shot
  `broker-init` exiting as a failure. The smoke test waits for real readiness
  instead.

### One code change it needed

`/evidence` names each result's commit by running `git log`. A container has
no history, so every study would have read "uncommitted", which is wrong
provenance under ADR-014.

`committed_at` now falls back to the build-time map named by
`STMS_EVIDENCE_COMMITS`. Neither available still reads "uncommitted", never a
guess. A test covers four cases: the map's answer, a file the map does not
name, an unreadable map, and no map at all.

### Verification, and what it does not cover

| Check | Result |
|---|---|
| Image tags | `eclipse-mosquitto:2.1.2-alpine` (the Mosquitto verified in D10), `python:3.12.10-slim-bookworm` and `node:22.23.2-alpine`, each confirmed on Docker Hub |
| `make_local_secrets.py` | writes 7 files; refuses a second run without `--force` |
| `evidence_commits.py` | 1,056 files mapped; p103 and p105 match `git log` exactly |
| The same services run natively: Mosquitto 2.1.2 with this config, the server and the ingest | smoke test 9 of 9; after a restart 6 of 6, so the store persisted. No secret in any log |
| The smoke test detects failure | **caught:** a broker allowing anonymous clients, and a store lost before the after-restart check |

**Not yet verified:**
- the Dockerfile and the compose file themselves;
- the image build;
- the container wiring: volumes, ownership, the broker-init hashing, the
  health checks;
- the secret scan of image layers.

All of these run only in CI's `compose` job, which runs once the branch is
pushed. A push needs the owner's authorization. Until that job passes, the
Docker deliverable is implemented, not verified.

## D16 — D15's Compose stack is verified in CI (2026-10-26)

D15 shipped the Compose stack as implemented but not verified, because Docker
is not installed on the development laptop. The owner authorized the push of
`1967e55..0530650` after a reviewed range report. The first CI run of the new
`compose` job supplies the missing verification.

**The run.** `tests`, run `40274825271`, on commit `0530650`, triggered by the
push on 2026-10-26. **All four jobs passed:**

| Job | Result | Duration |
|---|---|---|
| fast suites | success | 1 m 19 s |
| model suites (CPU torch) | success | 5 m 12 s |
| dashboard (vitest + build) | success | 17 s |
| compose stack | success | 57 s |

The `docs` workflow and the `tests` run that PR #1 triggered on the same
commit also passed.

**What the `compose` log shows, step by step.** A green job alone would not
show that its steps ran.

**The image is built from the committed Dockerfile.**
- The runtime installed exactly the four server pins from `requirements.txt`,
  plus their dependencies.
- The evidence stage mapped 1,056 result files to their commits.

**The stack starts in order.**
- `broker-init` ran and exited.
- `mosquitto` and `server` reported healthy.
- `ingest` started after both.

**The smoke test passed 9 of 9:**
- the broker refused an anonymous client over TLS ("Not authorized");
- the edge's login was accepted over verified TLS;
- the ingest stored both forecasts, and the server returned them;
- the class forecast read back exactly, with W listed as missing;
- the count history kept the real 0.0, with W missing;
- the built dashboard is served at `/dashboard/`;
- an HTTP write without the token was refused (401);
- the server answered `/health`;
- the evidence named real commits (`0c97ccb`, `252c3e0`).

  That shows the commit map works for the two result files the evidence panel
  reads. The other 1,054 mappings were produced by the same git query, but no
  check looked at them individually.

**After restarting `server` and `ingest`, 6 of 6 passed.** The stored
forecasts persisted.

**The secret and content scan reported "clean", for exactly what it checks:**
- the stack's service logs contain neither the API token nor either broker
  password;
- `docker history` shows the API token in no image layer. The passwords are
  never given to the build, so the scan does not look for them there;
- the image holds none of four named paths: `/app/deploy`, `/app/.git`,
  `/app/data/corpus` and `/app/models`.

It is not a scan of every file in the image.

**Scope.**
- **What this establishes:** on a clean Linux runner, the image builds and the
  tested stack works on the paths the smoke test exercises.
- **Not run on the development laptop:** Docker is not installed there.
- **Not a production deployment:** the secrets are throwaway test material,
  and its broker, CA and certificates are not a deployment's (TIM §7.4).
- **No edge:** it is not in the stack (ADR-003). This run establishes neither
  edge deployment nor real-camera integration (S65).

**Seen, and not changed here.** GitHub annotated the run with two warnings:
- `actions/checkout@v4` and `actions/setup-python@v5` target the deprecated
  Node 20 runtime, and GitHub forces them onto Node 24;
- `ubuntu-latest` is migrating to Ubuntu 26.

Neither failed anything. The action update is held by the owner, to be made
separately after compatible versions are checked.

## D17 — the deployed path runs end to end on real footage (2026-10-26)

**The question.** Does the system work as one product? That means real
footage, through the deployed edge, over MQTT with login and TLS, into the
ingest and SQLite, out through the API, onto the dashboard. Every earlier
delivery test fed a synthetic video. P143 proved counting only.

**`scripts/demo_e2e.py`.** It runs the services natively:
- Mosquitto with `deploy/mosquitto.conf`;
- the server and the ingest;
- `python -m edge.run` on one Bellevue clip, with that camera's lane geometry
  from `data/corpus_p103`.

It has two modes:
- **Verify** (the default) runs nine checks and exits 1 if any fails.
- **`--live MINUTES`** runs the stack for watching at `/dashboard/?id=live`.

The secrets are throwaway (`deploy/make_local_secrets.py`), live in a temporary
folder, and are deleted at the end. `scripts/demo_pipeline.py` remains the
other demonstration: it covers the corpus chain on synthetic data.

### The nine checks

| # | Check | Pass condition |
|---|---|---|
| E1 | The stack starts | broker, server and ingest up with no manual step |
| E2 | The edge runs | `edge.run` finishes its samples at real-time pace and exits 0 |
| E3 | Forecasts arrive | a class forecast and a count forecast are both stored |
| E4 | **Forecasts are correct end to end** | every stored class and count forecast **equals** an independent replay: the offline corpus counts through the same forecasters, skipping what the edge skips |
| E5 | The dashboard is served | `/dashboard/` returns the built page |
| E6 | A stopped edge shows | the class stream reads stale after its 60 s horizon, and the server stays up |
| E7 | The store persists | server and ingest stopped, **confirmed down**, restarted; the history row count is unchanged |
| E8 | Recovery | a fresh class forecast after the edge restarts |
| E9 | No leak | no secret in any service log; no new file in the repository, so no frame or video was written (NFR-13) |

### Results

All runs used Bellevue 150th/Eastgate, 2017-09-11 10:08, with the RTX 4050
laptop as the host.

| Run | Samples | Result |
|---|---|---|
| Prototype run, before the script was committed | 180 (6 min) | E1–E4 and E6–E9 pass. **E4: 151 of 151 class, 121 of 121 count forecasts equal.** E5 was checked in a real browser: streams fresh, history matching, no MFSTNet, then stale at 72 s |
| `scripts/demo_e2e.py`, verify | 180 | **9 of 9.** E4 151 of 151 and 121 of 121; first class forecast after 69 s, first count after 128 s; recovery after 67 s |
| The same, after E7 was strengthened to require the server to be confirmed down | 70 | **9 of 9.** E4 41 of 41 and 11 of 11; the server was down after its stop |
| `--live 20` | 600 (20 min) | ran to the end and stopped itself; the temporary secrets were removed |

**Why E7 was strengthened.** The first E7 restart took 1.1 s. That raised the
question whether `terminate()` on the venv launcher left the real server
running, in which case E7 would pass over a server that never restarted.

A direct test showed the launcher's job object stops the child: `/health`
answered 0 immediately after the stop, and no server process remained. The
fast restart was real. E7 now **asserts** that the server went down, so a
surviving server can no longer pass it.

### What this establishes, and what it does not

**Established, for the clip and configuration tested:**
- the deployed system runs as one product, with no manual step;
- the live pipeline's outputs **matched the independent replay for the
  tested footage**: every stored forecast equals what the evaluated
  forecasters produce from the offline corpus counts. P143 gives frames to
  counts; E4 gives counts to forecasts to MQTT to storage to the API;
- the stack recovers from a stopped edge and a restarted server.

**Repeatability, not universality.** The two complete verify runs, of 180
and 70 samples, show that the result repeats on this setup: this laptop, this
camera, this clip. They do not establish reliability across machines, camera
feeds or conditions.

**Not established:**
- **forecast accuracy:** exact replay shows the pipeline reproduces the
  forecasters, not that their forecasts came true. That is P103, P105 and
  S67's human labels;
- **a live camera stream** (S65);
- **Indian traffic;**
- **a fresh machine;**
- **any camera other than this one,** although P143's counting parity covers
  all three P103 cameras.

The live forecasts come from persistence and ridge (ADR-027), and MFSTNet
does not serve them.

## D18 — the dashboard palette, its measured rules, and a readable stale state (2026-10-27)

**The palette.** The dashboard was specified as dark-mode-only in `#0D1117`
and `#6366F1` (CLAUDE.md, stack line). It now uses the owner's brand palette
(#080808, #EC7C22, #A4510E, #FFFDFB) under two rules.
- **Orange is interface chrome only**, never on traffic data: its hue sits
  14° from an amber and 24° from a red, so near data it reads as a
  congestion level.
- **Every class and state colour is measured**, not chosen by eye.

All colours live in `dashboard/src/theme.css`.

**What `tokens.test.js` holds them to:**
- text contrast;
- class colours at 3:1 on the panel, with 4.5:1 chip text;
- state text at 4.5:1;
- the focus ring at 3:1 on every surface (WCAG 1.4.11);
- hue gaps from the brand orange;
- that LOW, MEDIUM and HIGH stay at least 20 CIELAB apart, and the three
  states at least 12, under simulated protanopia, deuteranopia and tritanopia
  (Machado 2009).

That last criterion is the project's own, not a WCAG requirement. WCAG asks
only that colour is never the sole signal, which the labels and shapes already
satisfy. The floor keeps label-free marks distinguishable.

**The step-1 colours failed three of those checks.** Six colours moved by
CIELAB ΔE 0.3 to 6.1 (old → new):
- low `#36D681` → `#36D982`;
- medium `#EDED3E` → `#EEEE3F`;
- high `#E63973` → `#E43A73`;
- ok `#3BC9D6` → `#3ACCD9`;
- stale `#4E7BF5` → `#427FFF`;
- bad `#BB3DF5` → `#CE3BF7`.

The three checks that failed:
- the unreachable text on its banner measured 4.49:1;
- the classes were 19.4 apart under deuteranopia;
- fresh and stale were 4.1 apart under deuteranopia.

All three pass now. The reviewer approved this revision after a prototype
validation against six checks.

**The stale state.** The stale warning was rendered inside the panel it warns
about, which was dimmed with `opacity: 0.55`, so the warning measured 2.27:1.
The dimming also took the stale values below 4.5:1. Now:
- **The warning sits above the data,** with its age, on its own background:
  4.54:1 for the heading and 16.44:1 for the text, measured on the running
  stack.
- **The values stay readable,** muted at 7.36:1, and class chips become
  outlines, so nothing old looks current and nothing is hidden.
- **No opacity is used anywhere.** A test fails if it returns.

**Shapes as well as colours.** In the status panel, fresh is a dot, stale a
diamond, unreachable or invalid a square, and nothing yet a dashed outline.

**One honesty fix found on the running stack.** With the server down, the page
still read "Server round trip 10 ms". That was how long the failed request
took, not a round trip. A round trip is now reported only for a health check
that succeeded.

**Tests.** `tokens.test.js` went from 7 tests to 12, and `dashboard.test.jsx`
from 22 to 26. A mutation check broke each protection once and the suite
caught 15 of 15. The fresh, stale and unreachable states were captured at
1280 and 390 px from a real run of `scripts/demo_e2e.py --live 2` on the
Bellevue 150th/Eastgate clip, with no horizontal scroll at 390 px. The
screenshots are kept outside the repository.

**Decisions recorded here, not yet built:**
- **Four theme modes (D-5).** Dark is the default. Light, Dark high contrast
  and Light high contrast are approved as accessible alternatives for daylight,
  low vision, and projectors or glare. They have been designed and measured,
  with the same rules at stricter limits for the high-contrast pair: 57 rules
  each, all passing. They become a dashboard change of their own, which must
  show that every theme renders the same text.
- **Icons (D-6).** Ten Phosphor icons (MIT) are approved, vendored in one
  local file with the licence notice, and always beside a text label. The
  dashboard uses no icons yet.

Not established by this entry:
- full WCAG conformance;
- usability with real operators;
- the redesigned layout (later UX steps).
