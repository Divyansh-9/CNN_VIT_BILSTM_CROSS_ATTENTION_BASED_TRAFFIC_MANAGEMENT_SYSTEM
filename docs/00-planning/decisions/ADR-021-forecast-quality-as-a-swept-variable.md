# ADR-021 — Sweep forecast quality; run the ceiling first

**Status:** Proposed · **Date:** 2026-08-21 · **Amends [ADR-009](ADR-009-ppo-forecast-surrogate.md); fixes [P52](../PRD-CHANGELOG.md)**

## Context

[P52](../PRD-CHANGELOG.md) found that `no-forecast` and `surrogate` are the same
environment: both set `use_mfstnet: false`, and nothing writes a proxy into
indices 11-14. ADR-009's central comparison has never been runnable.

The first reading of that finding was: **a proxy must be calibrated to a
measured MFSTNet accuracy, therefore the surrogate arm is blocked on S29, and
ADR-009's decoupling fails.**

**That conclusion was wrong**, and wrong in an expensive direction. It treats
forecast quality as a constant to be set. It is a variable to be swept.

## Decision

### 1. Run the ceiling before anything else

Train PPO against a **perfect** forecast — SUMO's own future congestion class at
t+60 s, uncorrupted — and benchmark it against Webster at saturation.

This is one training run, and it is the highest-value run in the whole RL track,
because it can falsify the track outright:

> **If PPO with a perfect forecast does not beat PPO with no forecast, the
> forecast contributes nothing to control and no achievable MFSTNet can change
> that.**

Nothing downstream needs to be built to learn this. It is labelled an oracle
everywhere it appears and is never reported as an achievable result — it is the
upper bound, which is exactly what makes a null result there decisive.

This step is not in the reviewer's proposal or in the first draft of ours. It
costs one run and it gates the other twenty.

### 2. Forecast quality is the independent variable

If the ceiling clears, run the surrogate arm across a **grid of degradation
levels** and report controller performance as a function of forecast quality.

The dependency inverts: S29 no longer unblocks the experiment, it **selects a
point on a curve already measured**. And the result is stronger than the point
estimate ADR-009 was going to produce — a falsifiable threshold:

> PPO beats Webster at saturation only where forecast macro-F1 exceeds **X**.

If S29 returns below X, the RL claim is cut in **Week 8 with a measured
justification** rather than discovered in Week 18 with nothing to show. Given
the cross-camera detector figure of **0.3500** and a corpus of 28 independent
segments, there is a real chance X sits above what this project can reach. That
is worth knowing early, and it is worth reporting either way (§2.5.5).

### 3. The decision rule is pre-registered, before the sweep runs

X is chosen post-hoc unless it is fixed in advance, and a threshold chosen after
seeing the curve is the cherry-picking PRD §2.5.5 forbids. So, written here
before any sweep run exists:

**X is the lowest swept forecast macro-F1 at which PPO's mean total delay beats
Webster's over 30 evaluation seeds by a paired t-test at α=0.05 with Cohen's
d ≥ 0.5.** Points that clear significance but not the effect size are reported
as "significant, not material" and do not set X.

**Go/no-go:** if the S29 fold mean lands below X, the RL contribution is
reported as *not supported at achievable forecast quality*, and the paper's
claim narrows to the vision half plus the measured threshold. That is a result,
not a failure.

### 4. Corruption is structured, not magnitude-only

A proxy read from SUMO's future state is an oracle only if it is degraded by
magnitude alone. An i.i.d. per-step class flip is simultaneously **too benign** —
independent errors average out across a decision window — and **too harsh**, in
that it manufactures jitter no real model produces.

The proxy is parameterised by three things instead:

| parameter | why |
|---|---|
| **adjacent-class-biased confusion** — MED↔HIGH dominant, LOW↔HIGH rare | congestion is ordinal; real confusions are between neighbours. §14.3 already reports `off_by_two_rate` separately for this reason |
| **lane-correlated errors** across the four approaches | all four predictions come from one frame through one camera, so their errors are not independent |
| **temporal persistence** — errors decay over a horizon rather than resampling per step | a model that is wrong about a scene stays wrong while the scene lasts |

The parameterisation is chosen so that **S29 hands back exactly this object**: a
confusion matrix, plus a lane-correlation and a persistence term measurable from
the per-fold predictions. The sweep's parameter space is directly indexable by
the eventual measurement, with no re-parameterisation step in between.

The corruption seed is recorded in the run's provenance sidecar. A degraded
forecast that cannot be reproduced is not a controlled variable.

### 5. Bounded compute

The sweep multiplies runs, so it is bounded up front:

- **saturated only** — the measured capacity knee (ADR-012). Light and
  oversaturated are run at the selected point, not across the grid.
- coarse grid first at macro-F1 ≈ **{0.33 (chance), 0.50, 0.65, 0.80, 1.00
  (oracle)}**, one training seed each, to locate the crossing;
- **30 evaluation seeds** only at the two grid points bracketing the crossing,
  and at the selected point. NFR-10's interval is spent where it decides
  something.

## Consequences

- ADR-009's three arms become four: `no-forecast`, `surrogate(q)` for swept `q`,
  `oracle`, and `mfstnet`. `oracle` is a bound and is labelled as one.
- The RL track stops being blocked on the vision track, in both directions.
- `use_mfstnet: false` on the surrogate arm is a defect to fix, not a setting.
  See [P52](../PRD-CHANGELOG.md).
- The go/no-go above is a **project-scope decision** and needs the guide, not
  only the project owner — it can narrow what the paper claims.

## Alternatives rejected

**Calibrate one proxy to the eventual MFSTNet number.** ADR-009's original
shape. It produces one point, it cannot say whether that point is near a
threshold, and it makes the RL track wait for the vision track — which is the
opposite of why the arm exists.

**Skip the surrogate and wait for `mfstnet`.** Defensible on honesty grounds and
fatal on schedule: it puts the entire RL result after S29 and after live
integration, in Weeks 17-19, with no fallback if it fails.

**Report the oracle as the result.** It is an upper bound on a quantity nothing
achieves. Reported as a bound, it is informative; reported as a result, it is
false.
