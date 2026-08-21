# ADR-020 — One age channel, because a stale forecast is worse than an absent one

**Status:** Proposed · **Date:** 2026-08-21 · **Amends [PRD](../PRD.md) §13.1 state layout (A16); fixes [P53](../PRD-CHANGELOG.md)**

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
