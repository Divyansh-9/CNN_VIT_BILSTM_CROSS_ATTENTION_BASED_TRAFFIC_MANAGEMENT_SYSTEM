# Build Log

**The live journal. What we are doing, what broke, and how we fixed it.**

| | |
|---|---|
| **Started** | 2026-08-07 |
| **Last entry** | 2026-08-13 |
| **Current step** | S37 full PPO runs (long), or S18 dataset curation |

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
| S03c | Push to GitHub | ✅ | — | Live, CI green. **Repo is PUBLIC** |
| S03d | CI test workflow + README badges | ✅ | — | Tests now run under pytest in CI, not a local driver |
| S04 | Scope variation sign-off | ✅ | — | **Accepted 2026-08-13** by project owner. ~340 h recovered |
| S05 | Environment | ✅ | — | **The blocker was our own pin, not Python.** torch 2.13 runs on 3.14 |
| S06 | Week-2 pilots | ⛔ | R1 | Tooling ready and installed. **Needs ≥6 min of real traffic footage** |
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
| S13 | Source registry + polygon validation | ✅ | — | 31 assertions. Dev-corpus guard enforced |
| S14 | Frame store | ⬜ | R1 | S13 |
| S15 | Counting (centroid-in-polygon, provenance) | 🔵 | R1 | Geometry half **done**; detector half needs S11 |
| S16 | Validation gates (distribution, leakage, unassigned rate) | ✅ | — | 7 gates, 24 assertions. Two gates added beyond spec |
| S17 | End-to-end demo on synthetic data | ✅ | — | `scripts/demo_pipeline.py`. Found 2 defects on first run |

### Phase 3 — Dataset · Weeks 3–8 → **M1**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S18 | Curate Part A benchmark (harmonise taxonomies) | ⬜ | R1 | **unblocked** · S09 |
| S19 | Recording sessions (≥60 × ≥6 min) | ⬜ | R1 | **unblocked** |
| S20 | Annotation | ⬜ | All | S19, S06 |
| S21 | Face/plate blurring script | ⬜ | R1 | S19 |
| S22 | Publish → **M1** | ⬜ | R1 | S18, S20, S21 |

### Phase 4 — Model · Weeks 4–14 → **M4, M5**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S23 | Encoders + **grid alignment** (A24) | ✅ | — | A24 verified on real tensors. 16 tests |
| S24 | Cross-attention (standard — Phase 1 only) | ✅ | — | 4 fusion modes, gate behind a Phase 2 flag |
| S25 | BiLSTM + per-lane ROI head | ✅ | — | A8 verified: 4 different lane predictions |
| S26 | **Overfit 10 sequences to ~zero loss** | ✅ | — | All 8 configs reach <0.03. Found 2 real defects |
| S27 | Feature cache + manifest assertion | ✅ | — | Hash raises, never warns. 23 tests |
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
| S35 | Webster saturation-flow sweep (ADR-012) → **M3** | ✅ | — | 21 runs. **Broke ADR-012's selection rule** |
| S36 | Gym environment, `check_env` clean | ✅ | — | check_env clean. 16-dim contract read from spec |
| S37 | PPO training, three arms → **M6** | 🟨 | R3 | Harness + config done, smoke run trains. Full 500k pending |
| S38 | 30-seed benchmark + statistics → **M7** | 🟨 | R3 | Stats + harness done, baselines benchmarked. PPO arms pending |

### Phase 6 — System · Weeks 4–19 → **M8, M9, M10**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S39 | MQTT contract + cross-topic test | ✅ | — | 31 assertions. P7 and TRIAGE-001 closed |
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

> **WITHDRAWN — this problem did not exist.** `pip index versions torch` reports **2.13.0, which
> supports Python 3.14**. The ceiling came entirely from the `torch==2.3.1` pin *I* chose from memory
> and then propagated into the manual, `check_env.py` and `pyproject.toml` — and then asked for 30
> minutes of the user's time to install an interpreter nobody needed. It cost three days.
>
> The paragraph above is left standing because deleting it would erase the mistake. It is history,
> not guidance. **A pin is a decision, not a fact** — see the S05 correction entry.

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

### S03c · Push to GitHub

**Started** 2026-08-13 · **Status** 🔵 in progress
**Estimated** 15 min

**Why this before more code.** Twenty-one commits exist on **one laptop and nowhere else**. ADR-003
and ADR-005 both concentrate training, the edge node and the demo on that same machine, and the
feasibility audit already lists it as hazard H3. Right now the mitigation named there — "push
continuously" — is not actually happening.

Three further reasons it cannot wait:

- **NFR-08 is a graded requirement**: code on GitHub with a pinned `requirements.txt`. Currently unmet.
- **S07 (doc walkthrough) is impossible** while 44 documents live on one machine.
- **`.github/workflows/docs.yml` has never run.** A CI job that has never executed is a guess.

**Pre-push safety check — done, clean.** No secret-shaped filenames tracked, no `.env`, no raw video,
no large binaries. Largest tracked file is `PRD.md` at 85 KB. Git LFS configured but holds nothing
yet, which is correct — no weights exist.

**Added.** `LICENSE` (MIT), which README promised and the repo did not have. It scopes the licence to
**source code only** and states separately that datasets carry their own terms — the curated benchmark
is per-source, the campus subset is CC BY 4.0 anonymised, and third-party sets keep their own licences.
A single blanket MIT over a repository that will contain other people's data would be wrong.

**Closed 2026-08-13.** Remote added, `main` pushed, 22 commits live. Description and 10 topics set.
**`docs.yml` ran for the first time and passed in 8 s** — a CI job that had never executed is a
guess, and it is now evidence.

**Repo is PUBLIC.** Private was recommended and not taken; recorded rather than re-argued. The one
concrete concern: `SCOPE-VARIATION-REQUEST.md` is addressed to the faculty guide, names them, and
they have not seen it. Reversible any time with
`gh repo edit --visibility private --accept-visibility-change-consequences`.

---

### S03d · CI test workflow and README badges

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 30 min · **Actual** ~45 min

**What we did.** `tests.yml` runs the corpus, metrics, geometry and spec-invariant suites on Python
3.11, installing **pytest and pyyaml only** — none of them import torch, so CI finishes in seconds
instead of pulling two gigabytes. Then a README badge block reporting status, stack, model, RL and
project metadata.

**Decision — the workflow came before the badges.** A badge asserting a test count nobody re-checks
is decoration. The tests had only ever run through a hand-written stdlib driver; now they run under
pytest on a clean machine, and the badge is a live workflow result.

**Decision — the badges say what is true.** Status reads **PRE-IMPLEMENTATION**, not "live". No model
has trained and no frame has been detected. Badges that overstate are the same failure as overclaimed
novelty wearing a different costume.

**Problem — the first CI run failed immediately: `ModuleNotFoundError: No module named 'mfstnet'`.**

Every local check had passed. The cause is that the stdlib driver began with `sys.path.insert(0, ".")`,
which put the repository root on the path and hid the fact that nothing else does. Under pytest on a
clean checkout, `tests/` is collected and `mfstnet/` is never on the path.

**Fix.** `pyproject.toml` with `pythonpath = ["."]`, plus `mfstnet/__init__.py` to make the package
explicit rather than implicit.

**Problem — second CI failure, exit 4.** `pyproject.toml` carried both `[tool.pytest.ini_options]`
and an empty `[tool.pytest]`. Pytest refuses both: *"Cannot use both [tool.pytest] (native TOML
types) and [tool.pytest.ini_options] (string-based INI format) simultaneously."* My error. Removed the
empty table and left a comment saying why it must not return.

**Problem — the third push triggered no workflow at all.** `tests.yml` had a `paths:` filter listing
`**.py` and the workflow file. The fix commit touched only `pyproject.toml`, so nothing matched and
nothing ran.

**This is worse than a failing build.** A workflow that does not run leaves the badge showing the
*previous* result — so a green badge can mean "never executed against this code". The filter was
saving nine seconds and could produce a badge that lies.

**Fix.** Path filter removed from `tests.yml`. It runs on every push.

**Problem — fourth run: 105 of 106 passed, and the one failure was a bad test rather than bad code.**
`test_leakage_message_names_the_offending_clips` asserted `"b" not in <message>`. The letter **b**
occurs inside the word *overlap* in the error's explanatory sentence.

**Fix.** Assert on the structured part of the message — `"a in ["` present, `"b in ["` absent — not on
prose. A test that greps a sentence for a single character tests the wording, and breaks the next
time anyone improves the sentence.

**Worth keeping.** Three failures in a row, all found by *running* rather than reading, and none of
them findable any other way. This is exactly the class the process review predicted: *"the next class
of defect only appears when something runs."*

The first one is the instructive one. Local verification was not wrong, it was **more permissive than
reality** — the stdlib driver put the repo root on `sys.path`, so it never tested whether anything
else would. **A check easier than the real environment passes things the real environment will not.**

---

### S13 · Source registry and lane geometry

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 2 h · **Actual** ~2 h

**What we did.** `geometry.py` (lane polygons, point-in-polygon, disjointness) and `sources.py`
(registry, clip validation, dev-corpus guard). Pure standard library — ray casting rather than
Shapely, so it runs before the environment exists.

**Decision — coordinates are normalised, not pixels, and it is enforced.** A polygon in pixels means
something different after any resize or re-encode, and nothing downstream would raise. Any vertex
outside [0, 1] is rejected at construction with an error that says why.

**Decision — a point on the boundary counts as inside.** This is not arbitrary: Shapely's `contains`
**excludes** the boundary while `intersects` **includes** it. A vehicle centroid landing exactly on a
shared edge would be assigned by one and dropped by the other. The convention is pinned and tested,
so swapping in Shapely later cannot silently change counts.

**Decision — overlapping lanes are rejected at registration, not per frame.** If two polygons can
both claim a centroid, every count downstream depends on iteration order. That is a bug producing
plausible numbers that never raises. Checked once, at load. Catches crossing edges, shared edges, and
full nesting.

**Decision — the dev-corpus guard is enforced, not conventional.** `assert_usable_for_reporting`
raises on a `dev` source. The override exists for smoke tests but must be passed explicitly and
recorded in the experiment record. HLD WI-17 said "convention would not survive Week 13"; this is
what not relying on convention looks like.

**Decision — `kind` has no default.** A source whose status nobody stated is exactly the one that
reaches a reported result by accident, so omitting it is an error rather than an assumption.

**Problem — an all-short source would have produced an empty corpus silently.** PRD A15 fixed the
arithmetic, but a source whose every clip is under 355 s would still have loaded fine and yielded
nothing, surfacing days later as a mysteriously empty dataset.

**Fix.** Registration distinguishes the two cases. *Some* clips short is a warning naming them.
*Every* clip short is a hard error saying the recording protocol is wrong, not the data.

**Evidence.** 31 assertions pass. Commit `TBD`.

---

### S16 · Corpus validation gates

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 1.5 h · **Actual** ~2 h

**What we did.** `validation.py` — seven gates run after the corpus is built and before anything
trains on it, returning one report rather than a series of asserts.

**Decision — severity is two-valued, and the distinction is the design.** BLOCKING stops the run;
ADVISORY is reported and does not. Only conditions that make a result **invalid** block; conditions
that make a result **weak** advise. A gate that fires on everything gets switched off, and the checks
that mattered go with it.

| Blocking | Advisory |
|---|---|
| degenerate class · clip leakage · unverified test split · degenerate task | thin test split · high unassigned rate · split balance |

**Two gates added beyond WI-14's list**, because the listed ones would pass a corpus that cannot
support the experiment:

**Transition rate (PRD A17)** — the most valuable check in the file. If the class at t+60s almost
always equals the class now, a last-value baseline sits near the ceiling and **no model can be ranked
against another**. A test demonstrates the failure directly: a corpus with *perfect* class balance
that still blocks, because nothing ever changes.

**Effective sample size (PRD A19)** — the bootstrap resamples clips, so effective *n* is the clip
count. Five hundred sequences drawn from three clips give intervals that look tight and are not.
Advisory, not blocking: it does not make results wrong, it makes them look more certain than they are.

**Decision — `labels_now` joins the manifest.** The transition gate needs the class at the last
observed frame. S4 already has the counts, so storing it costs nothing — and it hands us the Naive
last-value baseline of §14.3 for free.

**Decision — `raise_if_blocking()` reports every failure at once**, not the first found. A test
enforces it. Fixing gate failures one round-trip at a time is how a morning disappears.

**Evidence.** 24 assertions pass. Every threshold is a parameter, because P1 expects recalibration.

---

### S17 · End-to-end pipeline demonstration

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 1 h · **Actual** ~1.5 h

**Why, stated bluntly.** Three thousand lines existed, every module unit-tested, and **not one of
those tests exercised two modules together**. A pile of individually-correct parts is not a pipeline,
and the defects that matter live at the seams. That is the documentation failure one layer down.

**What we did.** `counting.py` (the geometry half of S3 — the detector is blocked, assigning boxes to
lanes is not) and `scripts/demo_pipeline.py`, which runs detections → counts → smoothing → labels →
windows → clip-level splits → seven gates → metrics. Synthetic input, standard library, ten seconds.

**It found two defects on the first run.**

**Defect 1 — my own gate could not fail.** `check_split_balance` returned `passed=True`
unconditionally. It printed the numbers and flagged nothing. The demo produced a **58/4/38** split
and the gate said `PASS`. A 4% validation split is noise; early stopping on it is meaningless. Fixed
to flag deviation above 10 points, advisory rather than blocking — skew makes results weak, not
invalid.

**Defect 2 — a collection requirement nobody had stated.** Chasing why the split skewed produced
this, measured against the actual splitter:

| Source clips | train / val / test |
|---|---|
| 24 | 11 / 5 / 8 |
| 40 | 21 / 8 / 11 |
| **60** | **32 / 13 / 15** |
| 120 | 71 / 24 / 25 |

Splits are cut by clip, so under PRD A19 **the clip count *is* the statistical sample size**. Below
~60 clips, validation and test each hold fewer than ten and no interval separates a two-point F1
difference — however many sequences those clips contain.

ADR-006 specified Part B in **frames** (1,500–3,000) and said nothing about how many sessions they
come from. Now amended: **≥60 continuous sessions of ≥6 minutes.** The Execution Manual's recording
table carries it too. Same order of footage as before; the *unit* is sessions, not hours, and that
distinction was missing.

**Limitation added to ADR-006.** Sixty clips from one campus position are not sixty independent
scenes. Clip-level splitting prevents *frame* leakage; it does nothing about overfitting to one
intersection's geometry and lighting. The test split measures temporal generalisation, not spatial.

**What the demo does not prove**, and says so in its own output: nothing about whether the detector
works, whether real traffic transitions often enough to be learnable, or whether any model helps.
It proves the plumbing carries water.

**Evidence.** `python scripts/demo_pipeline.py` — 24 clips, 312 sequences, 0 blocking failures, 2
advisories, Naive baseline 65.2%.

---

### S39 · MQTT contract and cross-topic test

**Started** 2026-08-13 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 1.5 h · **Actual** ~2 h

**What we did.** `contracts/mqtt.py` — topics, QoS, payload schemas, encode/decode — plus a
31-assertion cross-topic test. Closes all six TRIAGE-001 defects and pending item P7.

**Why now rather than Week 17.** Three owners build against this schema in three different weeks and
the pieces only meet during integration, which §2.5.1 already flags as where trouble appears. Each
defect is fifteen minutes now and half a day then, with no slack left.

**Decision — QoS is a property of the topic, not an argument to a publish call.** A helper taking a
QoS parameter lets three people pass three different values for the same topic. Attaching it to the
topic removes the choice.

**Problem — the design did not actually do that, and my own test caught it.**
`Topic` is an Enum, and Enum members accept attribute assignment. `Topic.EMERGENCY.qos = QoS.AT_MOST_ONCE`
**succeeded**. The override test set it, and a later assertion then read **QoS 0 for emergency** —
exactly-once silently downgraded to at-most-once, process-wide, for every publish including ones
written by someone who never touched that line.

Emergency is QoS 2 because a duplicate fires a spurious preemption and a loss risks a life. It is the
one topic where the level is not a preference.

**Fix.** `qos` and `template` are read-only properties over private attributes. Assignment raises.

**Worth keeping.** The contract was correct as *written* and unenforceable as *built*. Writing a rule
down and making it impossible to break are different jobs, and only the second survives three owners
and fifteen weeks.

**Also guarded.** A test asserts `gate_value` survives the round trip, because A16 removed the gate
from the **PPO state vector** and a reader of that amendment might reasonably delete it from this
payload too — where FR-UI05 and BR-07 still need it.

**Evidence.** 31 assertions. Emergency QoS 2, counts and commands QoS 1, predictions and heartbeat
QoS 0, matching PRD §17.1.

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

### S05 · Environment — RESOLVED, and the blocker was self-inflicted

**Raised** 2026-08-10 · **Closed** 2026-08-13 · **Status** ✅ done
**Estimated** 30 min of the team's time · **Actual** 20 min, none of it theirs

**What was claimed.** That Python 3.11 had to be installed because PyTorch publishes no wheels above
3.12, and that nothing in the project could run until someone did it. This was repeated across the
Execution Manual, `check_env.py`, `pyproject.toml`, several status summaries, and a detailed
step-by-step for the team.

**What is actually true.** `pip index versions torch` returns **2.13.0** for Python 3.14. The cap was
never Python's; it was `torch==2.3.1` in our own `requirements.txt` — a version picked from memory
early on and then treated as a fact about the world.

The environment now runs on the interpreter that was already installed:

    torch 2.13.0+cpu · ultralytics 8.4.118 · numpy 2.5.2 · opencv 5.0.0 · Python 3.14.4
    173 tests pass under real pytest, locally

**Why it took three days to notice.** Nobody ran `pip index versions torch`. The pin was written
once, the constraint was inferred from it, and every later document repeated the inference rather
than the check. It was corrected only because the project owner pushed back on being told to wait.

**Lesson, and it generalises.** *A pin is a decision, not a fact.* Version constraints written from
memory become project constraints the moment they are documented, and they are then defended rather
than tested. The same failure mode produced the "400 frames/day" estimate and the P6 mis-analysis:
a plausible number stated confidently, propagated, and never checked against the thing it described.

**Fixed.** `requirements.txt` no longer pins torch at all — it is installed from a platform index and
the file says why the old pin was removed. `pyproject.toml` drops the `<3.13` cap.
`check_env.py` no longer asserts a torch-derived ceiling it cannot verify.

**Consequence for the team.** S05 required nothing from them. The three-item blocker list was two
items, and one of those was a documentation defect.

---

### S06 · Week-2 pilots — ⛔ BLOCKED on footage only

**Raised** 2026-08-08 · **Status** ⛔ blocked · tooling ready

**Blocked on.** Real traffic footage of ≥6 minutes. Nothing else.

**Tooling is built, installed and verified.** `mfstnet/corpus/pilot.py` (the arithmetic, tested on
three synthetic scenarios), `scripts/pilot_counts.py` (video + YOLO), and
`scripts/collect_camera.py` (poll a still-image camera). torch, ultralytics and OpenCV are installed
and a YOLO forward pass runs on real pixels.

**Sources tried, and why each failed — recorded so nobody repeats them:**

| Source | Outcome |
|---|---|
| Stock video sites (Pexels, Pixabay, Videezy) | Clips are 10–30 s. One window needs 355 s |
| PennDOT public traffic cameras | Serve JPEG without auth, but **1 distinct frame in 100 s**. Far too slow |
| Ultralytics demo video | 2.1 s, and contains no vehicles |
| UA-DETRAC | Registration required; not completed |

**The duplicate check earned its place immediately.** `collect_camera.py --probe` hashes frames, and
the PennDOT camera returned the *same image* on every poll. Collecting it naively would have produced
a transition rate of zero and "proved" the task degenerate — when the only degenerate thing was the
sampling.

**Concatenating a short clip to reach 6 minutes was considered and rejected.** It would fabricate the
temporal structure the pilot exists to measure.

**What unblocks it.** ≥12 continuous minutes of any road, fixed camera, no panning. A phone on a
windowsill is sufficient — the footage is `kind: dev`, never published and never trained on.

**The four measurements.** Annotation velocity · count distribution · feature-cache size ·
**persistence rate**.

**Why the third and fourth matter most.** If counts above 15 never occur, the HIGH class is
degenerate and macro F1 ≥ 0.80 is unreachable. If ~90% of windows do not change class within 60
seconds, a last-value baseline sits near the ceiling and **no model can be ranked against another**.

Either discovery costs a threshold edit now. In Week 12 it costs the ablation.

---
