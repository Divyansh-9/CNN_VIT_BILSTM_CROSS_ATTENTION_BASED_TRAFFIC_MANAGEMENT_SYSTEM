# ADR-015 — Success Criteria, Action Space, and What to Work On Next

| | |
|---|---|
| **Status** | Proposed — **needs guide sign-off before any of it is locked in** |
| **Date** | 2026-08-14 |
| **Affects** | FR-R08, FR-R07, PRD §13.1 action space, FR-M14; pending items P10, P11 |
| **Related** | [ADR-009](ADR-009-ppo-forecast-surrogate.md) · [ADR-012](ADR-012-webster-saturation-flow.md) rev 2 · [ADR-013](ADR-013-artifact-hosting-and-publication.md) rev 2 · [ADR-014](ADR-014-dashboard-metrics-separation.md) |

## Context

The S38 benchmark produced a result that invalidates a graded success criterion,
and reviewing the project's priorities surfaced three more decisions that should
be made before compute is spent rather than after. They are recorded together
because they interact.

---

## Decision 1 — FR-R08 compares against the strongest baseline, not the weakest

### The evidence

30 paired seeds, saturated regime, mean wait with 95% CI
(`experiments/results/benchmark_stats.csv`):

| Method | Mean wait | 95% CI |
|---|---|---|
| fixed-time | 31.09 s | [29.83, 32.38] |
| Webster (s=750, the qualifying configuration) | 29.32 s | [26.94, 31.66] |
| **longest-queue** | **18.51 s** | [17.71, 19.31] |

| Comparison | Difference | p | Cohen's d |
|---|---|---|---|
| fixed vs Webster | +1.77 s, CI **[−1.00, 4.50]** | **0.225** | 0.226 |
| longest-queue vs Webster | −10.81 s | <0.00001 | −1.572 |

**Webster is not significantly better than fixed-time.** FR-R08's "PPO beats
Webster by ≥10%" was written assuming Webster is a strong classical baseline.
Measured, it is statistically indistinguishable from doing nothing adaptive — so
the requirement as written can be satisfied by a method that is not adaptive
either, and any reviewer who has read one RL-signal-control paper will say so.

### The decision

| Comparison | Status |
|---|---|
| vs fixed-time | Reported. **No claim** |
| vs Webster (swept, qualifying configuration) | Reported. **No claim** |
| **vs longest-queue** | **Primary claim: ≥10% reduction in mean wait, significant at α=0.05, with Cohen's d and 95% CI** |

**Keep the 10%, change the baseline — one change, not two.** A ≥15% target was
considered and rejected: nothing justifies 15 over 10 or 20, and setting a
numeric bar chosen after seeing the baselines re-introduces exactly the incentive
this project has spent effort removing. 10% against longest-queue means
**≤16.66 s**, which is already a materially harder bar than 10% against Webster
(≤26.39 s) ever was — the requirement gets stricter while its number stays put,
which is the easiest version to defend at sign-off.

**The statistical criterion is primary and the percentage is secondary.** If PPO
achieves a significant 7% improvement, that is a result and it gets reported as
one (PRD §2.5.5, BR-19). A percentage threshold must never become a reason to
re-run seeds until the number cooperates.

---

## Decision 2 — build both action spaces, measure, then choose (P11)

`phase_remaining`, state index 10, is **structurally zero at every decision
point**: the agent acts only at phase end, so the green it requested has fully
elapsed by the time it observes. One of sixteen dimensions carries no
information.

The literature-standard fix is a **fixed decision interval with keep-or-switch
actions** (MPLight, PressLight, RESCO), which makes the feature meaningful and
makes the action space match what reviewers expect.

**But that replaces PRD §13.1's 12 discrete (phase, duration) actions, which is a
graded requirement** — the same class of change as Decision 1, and not one to
make unilaterally because it is inconvenient to leave.

### The decision

Implement **both** behind a config flag. Screen them at 5 seeds each. Present the
comparison and let the guide choose.

**With a decision deadline and a stated default: 2026-08-18. If no response by
then, keep-or-switch is adopted.** Deferring to an approver with no timeout turns
one blocker into two — P10 and P11 would stack, and a guide who is simply busy for
a week makes the S06 deadline irrelevant because progress is stalled elsewhere.
A default that fires on silence is not a way around sign-off; it is what stops
silence from becoming a decision nobody made. The same deadline and a default of
option 1 (annotations only, no frames) applies to P10.

* §13.1's action space stays implemented as specified, so nothing graded is lost.
* The literature-standard alternative exists with evidence rather than assertion.
* **No compute is wasted either way** — this is the decisive point. Training
  500k × 3 arms × 30 seeds and *then* changing the action space invalidates every
  checkpoint. Screening first costs a fraction of one arm.

---

## Decision 3 — compute is screened cheap and reported expensive (FR-R07)

500k timesteps × 3 arms × 30 seeds is a serious ask against a free Kaggle
allocation of roughly 30 GPU-hours per week.

**Staged protocol:**

1. All three ADR-009 arms at **5 seeds** — screening.
2. The full **30 seeds** on the winning arm only — the reported numbers.

This is standard practice in RL papers, and it protects a weekly quota from being
spent on an arm that underperforms.

**One refinement worth stating:** the screening seeds are **0–4, a subset of the
final 0–29**. The screen is therefore not thrown away — those five runs become
part of the reported thirty. `compare()` pairs by seed, so this composes for free
and costs five episodes less than the naive version.

**What must not happen:** screening at 5 seeds, seeing a favourable gap, and
reporting it. `compare()` already attaches a note when n < 30, and that note must
survive into any table it reaches.

---

## Decision 4 — publish no frames (P10)

India's DPDP Rules were notified 13 November 2025 with full enforcement from
13 May 2027, inside this project's publication window. Street footage contains
identifiable faces and number plates.

**Decided:**

1. A curated benchmark from **properly-licensed public sources**.
2. The campus subset under **explicit institutional permission**, CC BY 4.0, with
   faces and plates blurred — or replaced by the **derived lane overlay** ADR-014
   already defines for the dashboard. Reusing that decision is better than
   inventing a second one, and the overlay makes the privacy claim visible rather
   than asserted.
3. Model weights, annotations and metrics. **Never raw frames.**

This is sufficient to reproduce every number in the paper, because the corpus is
auto-labelled from detector counts (ADR-002).

> **Correction to a common assumption.** [ADR-006](ADR-006-curate-then-collect-dataset.md)
> is **proposed, not accepted**. It is frequently referred to as an
> already-approved fallback and it is not — invoking it needs the same guide
> sign-off as everything else here. Believing an escape hatch is open when it is
> not is worse than not having one.

---

## Decision 5 — S06 gets a hard deadline, and the RL track pauses at good enough

**Accepted criticism.** The RL and simulation track is now the strongest part of
the project — mutation-tested statistics, paired bootstrap, an honest baseline
comparison that disproved a graded requirement. The vision track, which is the
half the repository is *named* after, has been blocked on footage for over a
week. Continuing to polish the strong half while the load-bearing half stalls is
optimisation theatre: it closes tickets without de-risking anything.

### The decision

**A hard deadline on S06 footage: 2026-08-21, with an automatic trigger.**

> **Pre-committed now, so it cannot be re-litigated later.** If no clip of ≥360 s
> from a fixed camera on heterogeneous traffic is in hand on **2026-08-21**,
> ADR-006's curate-then-collect path is taken to the guide **that same day**. Not
> "considered". Not after one more week of trying. A deadline whose only
> consequence is trying harder is not a deadline, and "let us try once more" is
> exactly how a week became three.

Progress made toward it today: `scripts/capture_stream.py` now captures a public
stream to disk with a bundled ffmpeg, filters candidates by duration *before*
downloading, and verifies that a capture actually moves. **The tooling half of
the blocker is gone.** A real Indian junction was captured and inspected — 640×360,
78.8 s, 40 of 40 sampled frames distinct, genuinely usable footage that is still
**too short**, because A15 needs ≥360 s and 78.8 s yields exactly zero sequences.

**What the search found, and the defect it exposed.** The first version of
`search()` filtered on `duration >= 360`. A live stream reports `duration: None`,
so **every continuous stream was silently excluded** — the search could not find
the only kind of source that solves the problem, and it returned short recorded
clips while appearing to work. Fixed; live entries now sort first.

With that fixed, YouTube search surfaces plenty of continuous fixed-camera
intersection streams — Abbey Road, Kingston, Jackson Hole — and **no Indian one**
across six queries. The likely reason is that India's Smart City traffic feeds
live on municipal web portals rather than YouTube, which is a different capture
problem (HLS/MJPEG endpoints) rather than a harder one.

**A non-Indian junction is not a substitute**, and the temptation should be named
before someone acts on it. The §14.1 thresholds are calibrated for Indian
heterogeneous traffic, and the entire premise is auto-rickshaws and lateral
filtering. Abbey Road would answer the A17 transition-rate question weakly and the
threshold question *wrongly*.

### Three sourcing tracks, all running from today — not on 2026-08-21

The automatic trigger is a **fallback, not a plan**. If the first alternative is
looked for on deadline day, the deadline has already failed. All three start now.

**P0 — self-capture. Starting tonight.** A phone on a tripod, 15 minutes, one
intersection, fixed position.

> **This is not a fallback; it is the original plan.** PRD §22 and
> [ADR-001](ADR-001-two-track-dataset-strategy.md) specify IndiaTrafficNet as
> **self-collected and self-annotated**. S06 was always going to require someone
> standing at an intersection. The week spent hunting public footage was, in
> honest terms, a way of avoiding the thing the specification already committed
> to — and it produced a good capture tool and no usable source.
>
> It is also the only option entirely within the team's control, the only one
> whose legal footing is unambiguous (institutional permission, and nothing
> published — Decision 4), and it answers both Week-2 questions this week rather
> than next. 15 minutes of phone video clears the ≥360 s bar four times over.

**P1 — Indian Smart City camera feeds** (Pune, Surat, Bengaluru B.TRAC, Chennai
and others), typically served as MJPEG/HLS/RTSP on municipal portals rather than
YouTube. `capture_stream.py` already runs on ffmpeg, which pulls HLS and RTSP the
same way, so this is **source discovery, not new tooling**.

> **With a caveat this ADR has to name, having just spent Decision 4 on it.**
> Pulling frames from a government camera feed the team does not own, to build a
> dataset, deserves the same scrutiny as publishing them. It is plausibly fine
> for a dev-source pilot and it is *not* automatically fine — check the portal's
> terms before pointing a script at it. Being careful about DPDP in one section
> and casual about scraping in the next would be incoherent.

**P2 — ADR-006 curate-then-collect.** The automatic trigger above.

**Concatenating short clips remains forbidden.** It fabricates precisely the
temporal structure the pilot exists to measure.

---

## Consequences

**Good.** The headline claim is made against a baseline worth beating. No compute
is spent before the action space is settled. The dataset question has an answer
that survives a strict examiner, a strict guide, and a future audit. The stalled
half of the project has a date attached.

**Bad.** Three graded requirements now await sign-off (FR-R08, §13.1's action
space, and the dataset plan) instead of one. That is the honest cost of having
measured them rather than assumed them.

**Blocked on.** Guide sign-off for Decisions 1, 2 and 4. Decisions 3 and 5 are
process and take effect immediately.
