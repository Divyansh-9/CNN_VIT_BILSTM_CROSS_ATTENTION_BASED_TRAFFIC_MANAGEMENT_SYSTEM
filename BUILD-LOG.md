# Build Log

**The live journal. What we are doing, what broke, and how we fixed it.**

| | |
|---|---|
| **Started** | 2026-08-07 |
| **Last entry** | 2026-08-13 |
| **Current step** | S07 — waiting on S04, S05, S06 |

---

## Why this file exists

Three jobs, and the third is the one people forget.

1. **Know what to do next.** One ordered list, one status per step.
2. **Know what is blocked and on whom.** Blockers age badly when nobody names them.
3. **Record what went wrong and how it was fixed.** Every B.Tech final report needs a *challenges
   faced* section, and every viva asks *what went wrong?* Writing that in Week 20 from memory
   produces vague answers. Writing it the day it happens produces specific ones.

> **The rule:** an entry goes in **the day the step starts** and is completed **the day it ends**.
> Not later. A log written at the end of the project is a work of fiction.

## How we use it together

| Moment | What happens |
|---|---|
| A step begins | The assistant says **"Starting S## — <name>"** and adds an entry with status `in progress` |
| Something breaks | The problem and the fix go into that step's entry immediately, while the detail is fresh |
| A step ends | The assistant says **"S## done"**, sets status `done`, and fills in evidence + actual time |
| A step is blocked | Status `blocked`, with **who** it is blocked on and **what** would unblock it |

Estimated versus actual time is recorded on every step. That is not bureaucracy — after ten steps you
will know your team's real estimation error, and the
[feasibility audit](docs/00-planning/FEASIBILITY-AUDIT.md) can be corrected with evidence instead of
guesses.

---

## Status board

**Legend:** ✅ done · 🔵 in progress · ⛔ blocked · ⬜ not started

### Phase 0 — Setup · Weeks 0–2

| # | Step | Status | Owner | Note |
|---|---|---|---|---|
| S01 | Repository, Git LFS, tooling scripts | ✅ | — | `check_env`, `check_docs`, `seed` |
| S02 | Documentation suite | ✅ | — | 43 docs, 12 ADRs. **Now stop** |
| S03 | Corpus logic + tests | ✅ | — | 44 tests passing |
| S03b | Metrics module + tests | ✅ | — | 62 tests. Confusion matrix now a required artifact |
| S04 | **Scope variation sign-off** | ⛔ | Team lead | Blocked on faculty guide. Gates ~340 h |
| S05 | **Python 3.11 environment** | ⛔ | Everyone | Nothing runs until this is done |
| S06 | **Week-2 pilots** (annotation, counts, cache, persistence) | ⛔ | R1 | Needs S05 + any traffic video |
| S07 | Doc walkthrough — each owner presents their part | ⬜ | All | 90 min. Fixes "nobody has read it" |

### Phase 1 — Detection · Weeks 2–3

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S08 | Acquire IDD, enumerate real label set, convert to YOLO | ⬜ | R1 | S05 |
| S09 | Class mapping + `rider` convention | ⬜ | R1 | S08 |
| S10 | Subsample and persist with recorded seed | ⬜ | R1 | S09 |
| S11 | Fine-tune YOLOv8s → `bootstrap_v0` | ⬜ | R1 | S10 |
| S12 | mAP evaluation harness (FR-D08/D09) | ⬜ | R1 | S11 |

### Phase 2 — Corpus pipeline · Week 3

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S13 | Source registry + polygon validation | ⬜ | R1 | S05 |
| S14 | Frame store | ⬜ | R1 | S13 |
| S15 | Counting (centroid-in-polygon, provenance) | ⬜ | R1 | S11, S14 |
| S16 | Validation gates (distribution, leakage, unassigned rate) | ⬜ | R1 | S15 |
| S17 | Golden test + end-to-end integration | ⬜ | R1 | S16 |

### Phase 3 — Dataset · Weeks 3–8 → **M1**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S18 | Curate Part A benchmark (harmonise taxonomies) | ⬜ | R1 | S04, S09 |
| S19 | Campus permission + recording sessions | ⬜ | R1 | S04 |
| S20 | Annotation | ⬜ | All | S19, S06 |
| S21 | Face/plate blurring script | ⬜ | R1 | S19 |
| S22 | Publish → **M1** | ⬜ | R1 | S18, S20, S21 |

### Phase 4 — Model · Weeks 4–14 → **M4, M5**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S23 | Encoders + **grid alignment** (A24) | ⬜ | R2 | S05 |
| S24 | Cross-attention (standard — Phase 1 only) | ⬜ | R2 | S23 |
| S25 | BiLSTM + per-lane ROI head | ⬜ | R2 | S24 |
| S26 | **Overfit 10 sequences to ~zero loss** | ⬜ | R2 | S25, S17 |
| S27 | Feature cache + manifest assertion | ⬜ | R2 | S26 |
| S28 | Phase 1 full training → **M4** | ⬜ | R2 | S27 |
| S29 | Ablation A–H × 5 seeds → **M5** | ⬜ | R2 | S28 |
| S30 | Backbone arms BB-1/2/3 | ⬜ | R2 | S29 |
| S31 | ONNX export + latency (GPU and CPU-only) | ⬜ | R2 | S29 |

### Phase 5 — Simulation and RL · Weeks 3–14 → **M3, M6, M7**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S32 | SUMO 4-way network | ⬜ | R3 | S05 |
| S33 | Sublane model + heterogeneous vTypes (ADR-010) | ⬜ | R3 | S32 |
| S34 | Fixed / Random / Webster baselines | ⬜ | R3 | S33 |
| S35 | Webster saturation-flow sweep (ADR-012) → **M3** | ⬜ | R3 | S34 |
| S36 | Gym environment, `check_env` clean | ⬜ | R3 | S35 |
| S37 | PPO training, three arms → **M6** | ⬜ | R3 | S36 |
| S38 | 30-seed benchmark + statistics → **M7** | ⬜ | R3 | S37, S29 |

### Phase 6 — System · Weeks 4–19 → **M8, M9, M10**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S39 | MQTT contract + cross-topic test (fix TRIAGE-001 first) | ⬜ | R4 | S05 |
| S40 | Edge node: capture → count → publish | ⬜ | R4 | S11, S39 |
| S41 | FastAPI + store | ⬜ | R4 | S39 |
| S42 | Dashboard (2 pages if ADR-008 approved) | ⬜ | R4 | S41 |
| S43 | Both fallbacks + fault injection — **pull to W17** | ⬜ | R4 | S40, S41 |
| S44 | Integration → **M8, M9, M10** | ⬜ | All | S42, S43 |

### Phase 7 — Research output · Weeks 15–20 → **M11**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S45 | Verify the five load-bearing citations | ⬜ | R2 | — |
| S46 | Paper draft | ⬜ | All | S29, S38 |
| S47 | Documentation waves 2, 3, 4 | ⬜ | All | W05, W11, W16 |
| S48 | Final report + submission → **M11** | ⬜ | All | S46 |

---

## The log

Newest last. Each entry is written when the step starts and closed when it ends.

---

### S01 · Repository, Git LFS, tooling scripts

**Started** 2026-08-07 · **Closed** 2026-08-10 · **Status** ✅ done
**Estimated** 2 h · **Actual** ~3 h

**What we did.** `git init`, Git LFS for model weights, `.gitignore` excluding raw video while
*keeping* result CSVs tracked, directory skeleton per PRD §22.3, pinned `requirements.txt`,
`.env.example`, and three scripts: `seed.py`, `check_env.py`, `check_docs.py`.

**Problem — the environment could not have worked.** The Execution Manual instructed
`pip install -r requirements.txt` against a file that did not exist, and told the team to write
`seed.py` without providing it. Part 0 failed at step one as written.

**Fix.** Created both. Manual updated to reference the committed files rather than describe them.

**Problem — Python 3.14 is installed and PyTorch does not support it.** Writing `check_env.py`
surfaced it: torch 2.3.1 publishes no wheels above Python 3.12. `pip install` fails with
`No matching distribution found for torch==2.3.1`, which reads like a network fault and is not.

**Fix.** `check_env.py` checks the interpreter version first and explains the cause in plain language.
Manual now requires Python 3.11 explicitly. **Still open as S05** — the interpreter is not installed.

**Problem — documentation drifted silently.** ADRs 005–008 changed the plan while five documents
still described the superseded approach.

**Fix.** `check_docs.py` enforces three things mechanically: every relative link resolves, no
withdrawn claim reappears in a live document, every ADR is registered. Runs in CI on any markdown
change. The withdrawn-claim check distinguishes *asserting* a stale claim from *quoting it while
correcting it*, so ADRs are not exempted wholesale — and it found a true positive immediately, a
stale config example in the manual that would have been copy-pasted.

**Evidence.** Commits `f3e1e22`, `47688a8`.

---

### S02 · Documentation suite

**Started** 2026-08-07 · **Closed** 2026-08-13 · **Status** ✅ done — **and deliberately stopped**
**Estimated** unknown · **Actual** ~6 days of sessions

**What we did.** 43 documents: SOW, BRD, PRD (amended to v1.2), SRS, FRD, NFR, RTM, 12 ADRs,
feasibility audit, related work, bibliography, datasets, execution manual, training guide, two
triage reports, process review, and a plain-English explainer.

**Problem — the plan was 1.6× over capacity and nobody had counted.** ~1,200 person-hours specified
against ~715 realistic. The parts that earn marks were scheduled behind parts that earn almost none.

**Fix.** Feasibility audit with the arithmetic shown. ADR-006 and ADR-008 propose ~340 h of cuts.
**Both still unsigned — S04.**

**Problem — novelty was overclaimed, twice.** First survey searched by *architecture* and missed that
CNN+ViT fusion is Conformer (2021), bidirectional attention is ViLBERT (2019), gated cross-attention
is Flamingo (2022). Second pass then found an entire vision-based congestion-prediction literature
that had never been searched, because nobody searched by *task*.

**Fix.** RELATED-WORK narrows every claim to what survives. Risk R26 records the lesson: **search by
task, not only by architecture.** Assume a third overclaim exists.

**Problem — one of our own findings was wrong.** The spec-invariant test "found" a contradiction
between the 180 s starvation limit and a 186 s cycle. It conflated *cycle length* with *lane wait* —
a lane waits for the other phase's green plus two all-reds, 96 s, not a full cycle. No contradiction.

**Fix.** Withdrawn and recorded in the register. The test was rewritten to assert the correct model.
**Lesson worth keeping: a test encodes an assumption, and a precisely-stated assumption can still be
precisely wrong.**

**Problem — documentation became its own risk.** 43 documents nobody on the team had read, written in
one voice across six days. Ratio peaked at 17:1 documentation to code.

**Fix.** Process review, and `EXPLAIN.md` — the whole project in plain English with worked examples,
written to be finished rather than referenced. Documentation is now **closed** until the Week 5 wave
gate.

**Evidence.** Commits `ce3a09b` through `f20ce57`.

---

### S03 · Corpus logic and tests

**Started** 2026-08-10 · **Closed** 2026-08-10 · **Status** ✅ done
**Estimated** 3 h · **Actual** ~4 h

**What we did.** `mfstnet/corpus/` — the label rule, window timing, and clip-level split assignment.
Pure standard library: no torch, no video, no GPU, so it could be written *and executed* before the
environment exists.

**Why out of order.** PLAN-01 puts the pilots first. They are blocked on S05 and S06, both human
tasks with lead time. The pipeline's *structure* does not depend on those measurements — only its
config values do, and those live in `spec.yaml`. Recorded in the plan so the reordering is visible.

**Problem — the window arithmetic was wrong, and fatally.** The label sat at `t+60s`, which is
**inside** the 295-second observation window. The model would read a frame it had already seen:
excellent validation, useless deployment. Separately, 355 s are needed per sample, so the stated
5-minute minimum clip would have produced a corpus of **size zero**.

**Fix.** Amendment A15. Timing stated once, in frame indices rather than seconds, because "60 frames
at 5 s spacing" covers 59 intervals and that is exactly where the error lived. `Sequence.__post_init__`
now refuses to construct a sample whose label falls inside its window, so the defective shape cannot
be built at all.

**Problem — could not run pytest.** No pyyaml, no pytest, no virtual environment.

**Fix.** Wrote a standard-library driver exercising every assertion, so the logic was genuinely
verified rather than assumed. The pytest files are committed for when S05 completes.

**Problem found by running it — hash-based splits are lumpy at small N.** 40 clips at 60/20/20 gave a
test split of **five clips**. Under amendment A19 the bootstrap resamples *clips*, so effective sample
size for every confidence interval **is** the clip count. Five cannot separate a two-point F1
difference however many sequences they contain.

**Fix.** Added `ratio_deviation()` and documented the reporting threshold. Converges by 120 clips
(test deviation −0.008).

**Evidence.** 44 tests passing. Commit `2403a20`.

---

### S03b · Metrics module and tests

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 1 h · **Actual** ~1.5 h

**What we did.** `mfstnet/metrics.py` — confusion matrix, per-class precision/recall/F1 with support,
macro and weighted F1, and three ordinal-aware measures. Pure standard library, so it runs before the
environment exists.

**Problem — a required artifact was required by nothing.** ADR-009 defines the PPO training surrogate
as an oracle corrupted by **MFSTNet's measured confusion matrix**, per density band. FR-M11 listed
accuracy, macro F1, per-class precision/recall and latency. **No confusion matrix.** Claim C4 depended
on an artifact no requirement mandated producing.

**Fix.** Amendment A25 makes it required, per density band and per lane, and the CSV row carries all
nine cells rather than a summary.

**Problem — the metrics ignored that the classes are ordered.** LOW < MEDIUM < HIGH, but standard
multiclass F1 scores "predicted HIGH, truth LOW" identically to "predicted MEDIUM, truth LOW". One is
a wrong nudge; the other holds a signal green on an empty approach while a queue builds elsewhere.

**Fix.** Added ordinal MAE, off-by-two rate, and quadratic weighted kappa. A test demonstrates the
gap directly: two cases with **identical accuracy**, ordinal MAE 0.5 against 1.0.

**Problem — a rare class produces a flattering number.** With HIGH at 1% of samples, a model that
always predicts LOW scores 0.95 accuracy.

**Fix.** Support is reported beside every per-class figure (as FR-D08 already requires for detection),
and the module **warns** when any class falls below the 5% distribution gate. In the test case
accuracy reads 0.95 while macro F1 reads 0.33 — that gap is the signal.

**Evidence.** 18 metric assertions pass, every expected value hand-computed and written into the test
rather than produced by the code under test. A metric suite that checks itself against its own output
checks nothing.

---

### S04 · Scope variation sign-off — ⛔ BLOCKED

**Raised** 2026-08-08 · **Status** ⛔ blocked, **6 days**

**Blocked on.** Faculty guide signature.
**Unblocked by.** A twenty-minute conversation, using
[SCOPE-VARIATION-REQUEST.md](docs/00-planning/SCOPE-VARIATION-REQUEST.md).

**Why it matters.** ADR-006 and ADR-008 gate ~340 person-hours. Until signed, every document carries
a conditional branch and the project plans against two incompatible futures.

**Ageing note.** This has been "submit this week" for three sessions. It is now the oldest open
blocker in the project and the cheapest to clear.

---

### S05 · Python 3.11 environment — ⛔ BLOCKED

**Raised** 2026-08-10 · **Status** ⛔ blocked

**Blocked on.** Installing Python 3.11 alongside the existing 3.14.
**Unblocked by.** ~30 minutes: install, `py -3.11 -m venv .venv`, torch from the CUDA index, then
`pip install -r requirements.txt`.

**Why it matters.** Nothing executes until this is done — no detector, no model, no simulation, and
`pytest` cannot verify the 44 tests that currently pass only through a hand-written driver.

**Known trap, already handled.** `python scripts/check_env.py` reports the exact cause in plain
language rather than letting pip's misleading error waste an afternoon.

---

### S06 · Week-2 pilots — ⛔ BLOCKED

**Raised** 2026-08-08 · **Status** ⛔ blocked

**Blocked on.** S05, plus any fixed-camera traffic video.
**Unblocked by.** ~3 hours once those exist.

**The four measurements.** Annotation velocity · count distribution · feature-cache size ·
**persistence rate**.

**Why the third and fourth matter most.** If counts above 15 never occur, the HIGH class is
degenerate and macro F1 ≥ 0.80 is unreachable. If ~90% of windows do not change class within 60
seconds, a last-value baseline sits near the ceiling and **no model can be ranked against another**.

Either discovery costs a threshold edit now. In Week 12 it costs the ablation.

---
