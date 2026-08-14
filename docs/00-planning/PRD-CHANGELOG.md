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
| ~~P7~~ **CLOSED** | MQTT payload schema defects | Closed 2026-08-13 | All six closed by amendment A26 and `contracts/mqtt.py`, with a 31-assertion cross-topic contract test. TRIAGE-001 closed |
| ~~P8~~ **CLOSED** | Webster parameterisation | Closed 2026-08-10 | [ADR-011](decisions/ADR-011-webster-definition.md) settled cycle clamping, splits and the two roles. [ADR-012](decisions/ADR-012-webster-saturation-flow.md) settles saturation flow and lost time: the published range spans 525W–1283W PCU/h per metre of approach width, so **sweep it and report Webster's best** rather than picking a value. PCE motorcycle 0.24, auto-rickshaw 0.78. Lost time 4–5 s start, ~3 s clearance |
