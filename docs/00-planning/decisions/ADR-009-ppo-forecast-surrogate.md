# ADR-009 — Forecast Surrogate for PPO Training, and a 16-Dimensional State Vector

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-10 |
| **Affects** | PRD §13.1, FR-M14, FR-R02, FR-R05, M6, M7; RELATED-WORK claim C4 |
| **Related** | [ADR-002](ADR-002-mfstnet-training-corpus.md) (same class of gap) |

## Context

PRD §13.1 defines a 17-dimensional PPO state containing four MFSTNet lane predictions (indices 11–14)
and `mfst_gate_mean` (index 15). PPO trains for 500,000 timesteps inside SUMO (FR-R05).

**Nothing in the PRD says where those five numbers come from during training.** MFSTNet consumes real
camera frames. SUMO produces no camera frames. A grep across the suite finds the fields defined in
§13.1, contract-tested in FR-M14, and discussed in the RTM — and nowhere sourced.

This is the same defect class as the missing training corpus that ADR-002 fixed: a specified
interface with no specified producer. Left open, it surfaces around Week 11 when someone tries to
instantiate the environment and has to invent something under deadline — and whatever they invent
silently becomes the experiment.

It also puts claim **C4** ("anticipatory state for RL signal control", RELATED-WORK §3) at risk,
because C4 is currently untestable as written.

### Options that do not work

**Render SUMO's GUI and run MFSTNet on it.** Frozen ImageNet/DINOv2 backbones on schematic
top-down renders produce near-meaningless features — the identical argument by which ADR-002 rejected
SUMO renders for MFSTNet training. Rejected for the same reason.

**Train the policy with the fields zeroed.** This is the FR-A06 degraded mode, and it is a useful
*ablation arm*, but as the only arm it abandons C4 entirely.

**Oracle: compute true congestion at t+60 from SUMO ground truth.** Honest and easy, but a policy
trained on a perfect forecaster and deployed against a ~0.8-F1 one meets a distribution shift at
inference. The PRD's own warning about the state vector being a contract applies to itself here.

## Decision

### 1. A noise-calibrated forecast surrogate

During SUMO training the forecast fields are produced by an **oracle corrupted to match MFSTNet's
measured error**:

```
true_class(lane, t+60)          from SUMO ground-truth counts via §14.1 thresholds
        │
        └─ sample from row `true_class` of MFSTNet's per-class confusion matrix,
           measured on the human-verified test split (PRD §8.6, A9)
                │
                └─ surrogate_pred(lane)  →  state indices 11–14
```

The confusion matrix is per-density-band where sample size allows, so the surrogate degrades in dense
conditions exactly as the real model does.

### 2. Three policies, not one — C4 becomes a sensitivity curve

| Arm | Forecast fields | Answers |
|---|---|---|
| **P-none** | Zeroed (FR-A06 degraded mode) | Does forecast information help at all? |
| **P-real** | Noise-calibrated surrogate | What is the realistic benefit? |
| **P-oracle** | Ground truth | What is the ceiling, and how steeply does benefit depend on forecast quality? |

All three run the full 30-seed protocol (FR-R06). Reported together, this is a **stronger** result
than the original single comparison: it answers not just "does it help" but "how good does the
forecaster need to be before it helps" — which is the question a deployment reader actually has, and
one the signal-control literature (§2.5) largely does not address.

C4's wording changes from *"MFSTNet predictions improve PPO control"* to *"anticipatory state
improves PPO control, and the benefit scales with forecast quality as follows."* Narrower, testable,
and defensible.

### 3. The state vector becomes 16-dimensional — `mfst_gate_mean` is removed

The gate is a property of visual fusion. SUMO has no scene, so the gate has **no analogue at all**
during training. Holding it constant makes index 15 a dead input: it consumes parameters, receives no
gradient signal, and teaches the policy nothing.

Removing it is free **today** and expensive later, because no PPO checkpoint exists yet. The RTM
previously argued for retaining the dimension so that checkpoints stay valid — that reasoning applies
only once checkpoints exist. This is the last moment the change is free.

```
state = [ count_N/50 … count_W/50,        #  0-3
          queue_N/200 … queue_W/200,      #  4-7
          phase_NS, phase_EW,             #  8-9
          phase_remaining/90,             # 10
          mfst_pred_N/2 … mfst_pred_W/2,  # 11-14
          emergency_flag ]                # 15   (was 16)
```

The gate remains a research artifact (claim C2), a logged output (FR-M04), and a dashboard feature
(FR-UI05). It is simply not policy input. **If MFSTNet is unavailable at inference, zero indices
11–14** — the contract rule is otherwise unchanged.

### 4. Scheduling consequence

P-real needs MFSTNet's confusion matrix, which needs M5 (Week 14). Therefore:

- Weeks 11–13: develop and converge PPO using **P-oracle**. Satisfies M6.
- After M5: run the final three-arm 30-seed benchmark for M7.

M6 and M7 keep their dates. What changes is that M7's final runs depend on M5 — record this
dependency in the schedule, because it was not previously there.

## Consequences

**Positive.** C4 becomes testable, and as a sensitivity curve rather than a point estimate. The
distribution-shift objection is answered directly: the training-time forecaster has the deployed
forecaster's error profile by construction. P-none doubles as the FR-A06 degraded-mode evaluation,
so a required behaviour gains a quantitative result for free.

**Negative.** Three policies means 3 × 500K training steps and 90 additional evaluation episodes.
On 14 CPU cores running seeds in parallel this is hours, not days — but it is real, and the
feasibility audit's 60-hour PPO line should absorb roughly +15 h.

**Negative.** PRD §13.1's dimensionality changes, and FR-M14/FR-R02/TC-R02 all assert 17. All must
be updated together, in one commit, or the contract test becomes the thing that is wrong.

**Negative.** The surrogate inherits whatever bias the confusion matrix carries. Since that matrix is
measured on the human-verified test split, it is the best estimate available — but it is an estimate
from ~150 sequences, so the per-density-band matrices will be small-sample. Report the matrix
alongside the RL results so a reader can judge.

## Alternatives considered

**Keep 17 dims, fix `mfst_gate_mean` at 0.5.** Preserves the PRD as written. Rejected: a constant
input is a dead dimension, and preserving a spec that describes nothing is not a virtue. Amend the
spec instead.

**Train only P-real.** Fewer runs. Rejected — without P-none there is no evidence that forecasting
helps at all, and without P-oracle no evidence about how much forecast quality matters. The three-arm
design is what converts C4 from an assertion into a finding.

**Defer the decision until Week 11.** Rejected: whatever is improvised then becomes the experiment,
and the state-vector change stops being free the moment the first checkpoint is written.
