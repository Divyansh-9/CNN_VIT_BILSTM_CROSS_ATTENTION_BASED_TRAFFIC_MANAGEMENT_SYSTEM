# ADR-002 — MFSTNet Training Corpus by YOLO-Derived Auto-Labeling

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-07 |
| **Deciders** | Project team + faculty guide |
| **Affects** | PRD §8 (new §8.6), §14.1, §20 L1, NFR-13, M4, M5 |
| **Related** | ADR-001 (supplies the detector), ADR-004 |

## Context

MFSTNet consumes sequences of shape `[B, T=60, 3, 224, 224]` — sixty frames at 5-second intervals,
five minutes of video — and predicts per-lane congestion in {LOW, MEDIUM, HIGH} sixty seconds ahead
(PRD §8.1, §14.1). Training requires many such sequences, each carrying four labels.

The PRD never says where they come from. Two candidate sources are implied and neither works as
written:

- **IndiaTrafficNet** (§12) produces bounding-box-annotated *still frames* selected for diversity,
  with near-duplicates deliberately filtered out (§12.1 step 4). It is a detection dataset. It
  contains no temporal continuity and no congestion labels.
- **§20 L1** states MFSTNet is "trained on SUMO sequences." SUMO renders schematic top-down
  geometry — coloured rectangles on grey polylines. ResNet-50 and ViT-Small are ImageNet-pretrained
  and frozen (PRD §8.2), so their features on such renders would carry little usable signal. Worse,
  the entire research claim is that CNN local texture and ViT global context are complementary in
  *dense, chaotic Indian traffic* (§14.2). Synthetic renders contain neither texture nor chaos, so
  the gate would have nothing to arbitrate and the ablation would measure noise.

Left unresolved, this surfaces around Week 10 as "the model won't converge," which PRD §2.5.1
misattributes to normalization or sequence-ordering bugs. The team would debug the wrong thing.

## Decision

Build the corpus from real video, and derive labels mechanically using the count thresholds the PRD
has already defined.

```
Continuous 5-minute clips (own footage, retained offline)
        │
        ├─ sample every 5s → 60 frames per sequence, resized to 224×224   → model input X
        │
        └─ fine-tuned YOLOv8 (ADR-001) counts vehicles per lane per frame
                 │
                 └─ count at t+60s → PRD §14.1 thresholds → label Y ∈ {0,1,2}⁴
                        LOW    < 5 vehicles
                        MEDIUM 5–15 vehicles
                        HIGH   > 15 vehicles
```

Sequences are generated with a stride (e.g. 30s) over each clip, so one hour of footage yields
roughly 110 overlapping sequences. Splits are cut **by source clip, never by sequence** — overlapping
windows from one clip landing in both train and test would leak, and PRD §2.5.1 already flags
"sequence ordering (no data leakage)" as a thing that goes wrong in Week 11–12.

The label rule is the PRD's own (§14.1). No new thresholds are invented.

## Consequences

**Positive.** Real imagery, matched to what the frozen ImageNet backbones actually encode. Zero
manual sequence labeling — labels are free once the detector exists. The pipeline becomes coherent
end to end: IndiaTrafficNet → YOLOv8 → auto-labeled sequences → MFSTNet, which means Novel
Contribution 1 now feeds Novel Contribution 3 rather than sitting beside it. This is a stronger
story in the paper than the PRD currently tells.

**Negative — and this must be stated in the paper, not buried.** Labels are model-derived, so
YOLOv8 detection error propagates into MFSTNet's ground truth. A model trained on another model's
output inherits its blind spots, particularly for the under-represented classes (cattle, <200
samples, PRD §20 L7). Mitigation: a **500-sequence subset is manually verified against human
counts** and reported as a label-noise estimate; per-class detector recall is reported alongside
MFSTNet's per-class F1 so a reader can see which errors are inherited.

**Consequence for NFR-13.** Raw video must be retained offline to build the corpus. NFR-13 governs
the *deployed runtime* — no frames leave the edge device over the network or are written to disk in
production. It does not govern the offline training corpus. NFR-13's wording is amended (PRD
amendment A6) to state this boundary explicitly, and the training corpus is excluded from the
repository by `.gitignore`.

**Consequence for §20 L1.** The limitation is rewritten. MFSTNet is no longer simulation-trained;
the honest limitation is now model-derived label noise plus single-city, daytime-only coverage.

## Alternatives considered

**SUMO-rendered sequences only.** Unlimited labeled data with no collection dependency, and exact
ground truth. Rejected for the reasons in Context: frozen ImageNet backbones on schematic renders,
and a fusion claim that becomes untestable.

**SUMO pretraining then real fine-tuning.** Adds data volume and a defensible sim-to-real angle.
Rejected as scope: it introduces a domain-gap problem the team would have to defend in the viva,
for a benefit that only matters if real sequences turn out to be scarce. Reconsider at Week 12 if
the corpus is under ~2,000 sequences; recorded in the manual as a contingency, not a plan.

**Manual congestion labeling of sequences.** Highest label quality. Rejected on arithmetic: at ~2
minutes per sequence for a human to count four lanes across sixty frames, 2,000 sequences is
roughly 67 hours of work on top of the 12,000-frame annotation already committed in M1.
