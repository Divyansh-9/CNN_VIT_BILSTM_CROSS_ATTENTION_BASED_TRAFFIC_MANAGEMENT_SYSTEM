# ADR-020 — One age channel, because a stale forecast is worse than an absent one

**Status:** Accepted **as amended** by the project owner 2026-10-16 (Amendment 1 below), **not a faculty-guide signature** · originally Proposed 2026-08-21 · **Date:** 2026-08-21 · **Amends [PRD](../PRD.md) §13.1 state layout (A16); fixes [P53](../PRD-CHANGELOG.md)**

## Context

`spec.yaml` maps the three congestion classes through `mfst_pred_divisor: 2`,
so `{LOW, MEDIUM, HIGH}` becomes `{0.0, 0.5, 1.0}`. FR-A06 zeroes indices 11-14
when MFSTNet is unavailable, and `traffic_env`'s docstring claims this "states
'no forecast'".

**It states that all four approaches are predicted clear.** Zero is LOW. The
declared fallback hands the policy the most optimistic forecast the encoding
can express, at the moment the forecast has failed.

### Absent is the easy half

Reserving `0.0` and mapping the classes to `{1,2,3}/3` removes that ambiguity
outright, and costs one normaliser.

It does nothing for **stale**, which is the worse failure. An eight-second-old
forecast is numerically identical to a fresh one, fully in-distribution, and
confidently wrong exactly when traffic is changing fast enough for the age to
matter. PRD §7.2 already names a 10 s MQTT threshold, so staleness is not a
hypothetical the design invented — it is a specified operating condition with
no representation in the state.

## Decision

**Reserve zero, and add one shared age channel.** The state becomes 17-dim:

```
11-14  MFSTNet class N S E W   (LOW, MEDIUM, HIGH) -> {1, 2, 3} / 3
16     forecast_age            min(age_s, 10) / 10,  1.0 when absent
```

Index 15 stays `emergency_flag`; the new channel is appended, not inserted.

**Why one scalar and not a flag.** Absent, stale and fresh collapse onto a
single monotone channel, so the policy can learn a *discount* rather than a
branch, and the three cases are ordered the way their risk is ordered. A binary
`available` bit cannot express the middle case at all.

**Why one channel and not four.** All four lane predictions come from one
MFSTNet forward pass over one frame. They share a timestamp by construction,
and four copies of one number is four chances to disagree.

**Why both halves now.** The reserved zero alone would be a PRD amendment; the
age channel alone would be another. Doing them separately means two amendments
and two generations of invalidated checkpoints for one problem. **Zero final PPO
checkpoints exist today** — the reason this is cheap is precisely that nothing
has been spent yet, and that stops being true the moment the arms are run.

The two are also not redundant. With an age channel the policy *can* learn to
ignore 11-14 when index 16 reads 1.0; reserving zero means it does not have to,
and a single misread index cannot produce a confident wrong forecast on its own.

## Consequences

- `dim: 16` becomes `dim: 17`, and the observation contract digest
  ([P53](../PRD-CHANGELOG.md), `simulation/contract.py`) changes. Every
  checkpoint predating the change refuses to load, which is the mechanism
  working rather than an inconvenience.
- **This is not a revert of A16.** A16 removed `mfst_gate_mean` because SUMO has
  no camera and so no gate to read. `forecast_age` has a SUMO analogue in every
  arm — it is a property of the message, not of the image — and the surrogate
  can produce it honestly.
- `zero_when_mfstnet_unavailable` becomes a statement about indices 11-14 *plus*
  setting index 16 to 1.0, so the fallback is one named operation rather than a
  list of indices and a convention.
- Training must exercise the channel or it is decoration. That is
  [ADR-021](ADR-021-forecast-quality-as-a-swept-variable.md)'s dropout schedule,
  not this decision.

## Alternatives rejected

**`spaces.Dict` with `MultiInputPolicy`.** Proposed as the general fix. SB3's
default `CombinedExtractor` applies `nn.Flatten` to Box subspaces and
concatenates them, so a Dict space is the flat vector with extra steps unless a
`BaseFeaturesExtractor` is hand-written per key. The warm-start argument for it
is real but is an argument for the *extractor*, not for the space, and it can be
adopted later without changing what any index means.

**An `available` bit.** Cannot express stale, which is the failure this is
mostly about.

**Per-lane confidence, entropy, or class probabilities.** Better signal, and a
larger change: the surrogate would have to emit calibrated three-class
probabilities rather than a class, which is [ADR-021](ADR-021-forecast-quality-as-a-swept-variable.md)'s
territory. Deferred deliberately so this amendment stays one that can be
verified by inspection.

---

## Amendment 1 — 2026-10-16, after the P97a investigation (P108)

**Accepted by the project owner, not a faculty-guide signature.** Everything
above is the original decision, kept unedited, because the reasoning still
holds. This amendment records what has changed since 2026-08-21, and adds the
one rule the original did not have, the fallback. Evidence:
[INVESTIGATION-P97a-missing-forecasts.md](../INVESTIGATION-P97a-missing-forecasts.md),
P108 and P109.

### Why an amendment was needed: three assumptions that no longer hold

1. **"Zero final PPO checkpoints exist today."** One now does:
   `ppo_no-forecast_saturated_keep_or_switch_seed42.zip`, 500,000 steps,
   observation contract `24ad1c994e844238`. The age channel changes `dim`, so
   it will refuse to load (P53 working). **It is retrained under the amended
   layout**, because it is the fallback policy below and must share the
   layout. No other model is affected: forecasters and MFSTNet do not read
   this state.
2. **"All four lane predictions come from one MFSTNet forward pass."** Under
   ADR-027 an approach can be absent **on its own**, permanently (a camera
   that cannot see it: NE 8th south, P96; Newport lane_2, P103) or
   transiently. The reserved zero is therefore **per approach**. The age
   channel stays **one per forecast message**, because one message has one
   timestamp.
3. **"MFSTNet class" at 11–14.** Under ADR-027 the class forecast comes from
   whichever forecaster holds that role (today persistence v1). The index
   names `mfst_pred_*` are kept, to avoid churning every consumer for a name,
   and they now mean **"the class forecast for that approach"**, whatever its
   source.

### The layout, as amended (`dim: 17`)

```
11-14  class forecast N S E W   LOW, MEDIUM, HIGH -> 1/3, 2/3, 1;  0.0 = no forecast for that approach
15     emergency_flag           unchanged
16     forecast_age             min(age_s, 10) / 10;  1.0 when there is no forecast message at all
```

**A missing approach is never encoded as a class.** The state builder writes
0.0 only for an approach with no forecast, and refuses any other route to it.
That carries P109's rule (no implicit zero) into the controller.

### The fallback: a rule about every required input, not one age

A **forecast-aware** policy may decide only when **all** of these hold:

- every approach the policy requires has a class forecast in the current
  message (partial coverage is not enough);
- that message is at most **10 s** old (PRD §7.2's bound), by the server's
  clock;
- the counts and queues it reads are present for every approach, and finite
  and non-negative.

**If any condition fails, the controller uses the no-forecast policy:** the
retrained checkpoint, on the same layout, with 11–14 = 0.0 and index 16 = 1.0.
If the counts themselves are invalid, the existing FR-A06 Webster fallback
applies.

**Recovery:** the forecast-aware policy resumes only on a **complete, fresh,
valid** message, never on partial or recovering data. **Every switch is
logged with its reason.** A missing approach therefore never becomes LOW: not
in steady state, not during partial camera failure, and not during recovery.

### Acceptance and evidence required

- **Contract tests:**
  - an absent approach can never encode as a class;
  - the age is monotone, with 1.0 for absent;
  - the P53 digest changes and old checkpoints refuse to load.
- **Fallback tests:** each failing condition above selects the no-forecast
  policy, and recovery requires a complete fresh message.
- **A pre-registered simulation safety evaluation,** with missing and stale
  forecasts injected at fixed rates:
  - the controller with this fallback must be **not meaningfully worse** than
    the no-forecast baseline;
  - the comparison is paired, with the margin and statistics fixed before
    running.
  - Passing it is **safety evidence only.** Whether forecasts *improve*
    control is ADR-021's question, asked afterwards.
- **The controller stays disconnected from signal timing** until that
  evaluation passes (ADR-027 rule 4).
