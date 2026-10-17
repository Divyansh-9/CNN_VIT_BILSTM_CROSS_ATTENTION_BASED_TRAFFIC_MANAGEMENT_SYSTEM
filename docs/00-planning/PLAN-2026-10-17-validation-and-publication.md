# Implementation plan — validation and publication

**Date:** 2026-10-17 · **Owner:** project owner · **Supersedes:** Track E of
[PLAN-2026-10-17-after-ceiling](PLAN-2026-10-17-after-ceiling.md).

**Why these three.** The forecast-for-control line is **closed** under the
current protocol (P130–P133). Reopening it would need a new rationale and a
new pre-registration. The project's defensible contribution now depends on
three pieces of work that strengthen it whatever control ultimately shows:

| # | workstream | the question it answers | gate |
|---|---|---|---|
| **V1** | human-verified prediction quality | are the deployed forecasters genuinely predictive, on labels a detector did not make? | protocol frozen before any label is read for scoring |
| **V2** | live-camera validation (S65) | does the edge pipeline meet its technical criteria on the real stream? | the owner provides the stream |
| **V3** | publication and licensing | what can lawfully be made public, and how? | the owner's decisions; licence replies |

**Order.** V3's first step comes first because it is minutes of owner action:
making the repo private, which unblocks CI. V1 is the main engineering
effort. V2 waits on the camera.

## Standing rules (unchanged)

- **Frozen:** P130, P131 and P132, unchanged.
- **Untouched until Ms Pokhriyal decides:** ADR-023 and `CLAIMS.yaml`.
- **Part 2:** deferred.
- **The controller:** disconnected from signal timing.
- **No push** while the repository is public.
- **The synopsis documents:** hands-off.
- **Pre-registration before data** for any scored evaluation. Every gate's
  stop is recorded as a finding.
- **The Bellevue licence is unresolved,** so everything scored on Bellevue
  footage is **internal engineering evidence**. It is not publishable until V3
  resolves it.

---

## V1 — human-verified prediction quality

### V1.1 What is evaluated, and why it is not already known

**ADR-027 deploys two forecasters:**
- persistence for the congestion class (`persistence@2431c6641b9c`);
- the level-free ridge for the next-minute count (`ridge@73532968dcf2`).

**Their evidence (P103–P105) used detector-derived targets.** A32 requires the
headline comparison on **human-verified** labels. Detector-derived targets
mix two errors:
- **detector error:** the counts are wrong now;
- **forecasting error:** the future is mispredicted.

They also make persistence look better than it is when the detector's errors
are correlated in time.

**V1 separates the two errors.** For each sampled lane-moment, a blind human
count is taken **now** and **across the next minute**. Three comparisons
follow from it:

| comparison | input | target | isolates |
|---|---|---|---|
| detector error | detector count at t | human count at t | the detector alone |
| end-to-end forecast error | the forecaster fed **detector** counts | human next-minute target | what the deployed system delivers |
| forecaster-only error | the forecaster fed **human** counts | human next-minute target | the forecasting model alone |

All three are reported **by camera, by traffic level (LOW / MEDIUM / HIGH),
and by horizon (30, 60 and 120 s)**. The 60 s horizon is primary.

### V1.2 Stages and gates

| stage | what | output | stop rule | estimate |
|---|---|---|---|---|
| **V1-0 Design** | sampling frame, target definition, labelling tool, effort model | design note | — | 0.5 day |
| **V1-1 Target-fidelity check** *(detector data only; no labels)* | does a mean of *K* human-countable frames per minute (*K* = 6, every 10 s) approximate the 30-sample next-minute mean? Measured on detector series | `v1_target_fidelity.json` | if *K* = 6 misses its tolerance, try *K* = 12. If neither fits the labour budget, the target becomes the count at t + 60 s, decided **before** labelling | 0.25 day |
| **V1-2 Inter-rater pilot** | 2 labellers, 40 lane-moments, blind | ICC of counts; κ of classes | if ICC < 0.8, revise the counting instructions **once**, re-pilot, then freeze | 0.5 day |
| **V1-3 Pre-registration** | protocol + scoring code + `decide()` + tests, committed **before scoring** | `PREREGISTRATION_V1.md` | — | 0.5 day |
| **V1-4 Labelling** | blind counts on the frozen sample | `v1_labels.json` | — | ~1 person-day per 150 lane-moments (V1-2 replaces this with its measured rate) |
| **V1-5 Scoring, once** | the three comparisons and their breakdowns | `v1_results.json` and a report | — | 0.25 day |

### V1.3 Design decisions to freeze at V1-3

**The sample:**
- **source:** footage **no model was fitted or selected on**. Only P105's
  untouched cameras and hours qualify, and only the hours P105 did not score;
- **stratification:** by camera × traffic level, from detector classes;
- **day only:** night stays excluded;
- **size:** from V1-2's measured labelling rate and SD, at a pre-set
  precision. The primary target is a 95% CI half-width of **0.15 vehicles**
  on the ridge-minus-persistence MAE.

**Blinding:**
- the labeller sees footage only, with no detector output and no forecast;
- frame order is randomised across lanes and moments;
- the "now" and "future" frames of one moment are never shown adjacently.

**Primary endpoints:**

| forecaster | endpoint | baseline |
|---|---|---|
| ridge (count) | MAE against the human next-minute target | persistence |
| persistence (class) | macro-F1 against the human next-minute class | the hour prior |

The statistics follow house conventions: a paired bootstrap stratified by
camera with 10-minute blocks, and Holm across the primary tests.

**The named readings:**
- the forecaster beats its baseline on human labels;
- no demonstrated difference;
- the baseline is better.

The detector-error share is reported with each.

### V1.4 Implementation tasks

1. **`scripts/v1_target_fidelity.py`** (V1-1). Detector series only.
2. **`scripts/v1_sample.py`.** Stratified, seeded draw of lane-moments from
   the eligible hours. It writes the sample manifest, which is committed: ids
   and timestamps, not frames.
3. **`scripts/v1_label_page.py`.** Extends `count_audit_page.py`:
   - blind, randomised order, lane tinting;
   - export to JSON;
   - the page is written under `data/` (gitignored, never published), because
     it holds footage.
4. **`scripts/v1_score.py`.**
   - It refuses unless the pre-registration is committed unchanged, and runs
     once.
   - It has a `restat` mode.
   - It uses the deployed forecasters unchanged, with their SHA-256 checked.
5. **Tests:**
   - sampling is reproducible;
   - the forecasters are applied unchanged (hashes);
   - the scorer refuses without a committed pre-registration;
   - `decide()` is correct for every reading;
   - the label page never embeds detector output.

### V1.5 Risks

| risk | mitigation |
|---|---|
| labelling cost | V1-1 picks the cheapest target that is faithful enough; V1-2 measures the real rate before sizing |
| label noise | the inter-rater pilot, ICC reported, one instruction revision allowed **before** freezing |
| HIGH is rare, so the per-class breakdown is thin | stratify by detector class; report each stratum's *n*; no claim on a stratum with *n* < 30 |
| footage licence | internal evaluation only; frames never leave `data/`; results are publishable only after V3 |

---

## V2 — live-camera validation (S65)

**Status:** the tooling exists (`benchmark_live.py capture/run`,
`benchmark_decode.py file`). It **waits on the camera**: `STMS_CAMERA_URL` is
read from the environment and is never printed or recorded.

**This is a technical validation,** not a claim that the controller is
production-ready. The controller stays disconnected.

### V2.1 Criteria

**Criteria 1–4 are frozen from S64 and P89.**

| # | criterion | measured by | state |
|---|---|---|---|
| 1 | decode ≥ 1.0× real time on the camera's own codec, resolution and bitrate | `capture` then `benchmark_decode.py file` | exists |
| 2 | lag growth < one step (arrival drift) | `run` | exists |
| 3 | prediction interval p95 within 25% of `step_s` | `run` | exists |
| 4 | no lost samples | `run` | exists |
| 5 | **timestamp correctness:** sample timestamps monotonic, and inter-sample spacing within tolerance of `step_s`, by the wall clock **and** the stream's own clock | `run` | **add** |
| 6 | **end-to-end latency:** frame arrival → prediction published → server receipt, p50 / p95 / max, against PRD budgets (MQTT ≤ 200 ms; MFSTNet ≤ 150 ms on the server CPU as a proxy, with the host stated per ADR-003) | `run` + server log | **add** |
| 7 | **prediction freshness at the consumer:** the age of the latest prediction when the API is read; the share of reads that are stale (> 10 s, the gate's bound) | `run` + polling `GET /count_forecast/...` and `/prediction/...` | **add** |
| — | reconnects, windows lost and jitter | `run` | exists; reported, not gating |

### V2.2 Stages

| stage | what | gate | estimate |
|---|---|---|---|
| V2-0 | add criteria 5–7 to `benchmark_live.py`, tested against a **local test stream** (ffmpeg serving a file over RTSP); pre-register the thresholds | tests pass | 0.5 day |
| V2-1 | pre-flight: the URL is set in the environment, the network is reachable, the clocks are synchronised | checklist | 0.1 day |
| V2-2 | `capture` 300 s, then criterion 1 on the recording. **Privacy (NFR-13):** the recording stays in a gitignored scratch directory and is **deleted after measurement**; only measurements are kept. This is the owner's call before the run | — | 0.25 day |
| V2-3 | `run` 600 s, end to end: edge → MQTT → server → API | criteria 2–7 | 0.25 day |
| V2-4 | report: results with the host, network and codec stated; S65 closed or reopened with reasons | — | 0.25 day |

**Risk:** the camera's network, not the pipeline, fails the criteria.
**Mitigation:** jitter and reconnects are reported beside the criteria, so a
network failure is distinguishable from a pipeline failure.

---

## V3 — publication and licensing

| step | action | owner | blocks | evidence it is done |
|---|---|---|---|---|
| V3-1 | **make the repository private** (Option A) | project owner (a GitHub setting) | CI on this branch | `gh repo view` shows PRIVATE |
| V3-2 | push the feature branch only; draft PR to `main`; read all four CI jobs | Claude, after V3-1 | — | CI results recorded |
| V3-3 | **licence outreach** (Option B): send the drafts in `OUTREACH-2026-10-15.md` and record the replies per source | project owner | anything public that uses Bellevue | replies filed; `data/cameras.json` licences updated, which then moves the `releasable` claim |
| V3-4 | **sanitised public tree** (Option C): `scripts/build_public_tree.py` | Claude | a public release | see below |
| V3-5 | **remove the already-public previews** (Option D): a deletion commit; a history rewrite only if the owner decides | project owner decides | — | the files are absent from `main`'s tip |
| V3-6 | the model weights on Hugging Face (ADR-013), only for models whose **training data** permit it | project owner | after V3-3 | a model card states the data and its licence |

**What V3-4 does.** It builds a fresh public tree:
- **excluded:**
  - every Bellevue-derived path;
  - third-party frames;
  - any file `scripts/check_sources.py` marks unreleasable.
- **guarded:** a test fails if any excluded pattern appears in the output, and
  the tests that need Bellevue files skip cleanly when those files are
  absent.
- **recorded:** a manifest lists every exclusion, with its reason.
- **published as:** one squashed commit on a fresh public branch.
- **checked first:** CI runs on the sanitised tree before anything is pushed.

**Publication gate.** Nothing becomes public until all three hold:
- V3-3 or V3-4 makes it lawful;
- the owner approves the specific push;
- the claims checker's `releasable` item is satisfied for what is published.

---

## Sequence and owners

| when | V1 | V2 | V3 |
|---|---|---|---|
| now | V1-0, V1-1 (no labels needed) | V2-0 (local test stream) | **V3-1** (owner, minutes) → V3-2 |
| next | V1-2 pilot (two labellers) | V2-1 to V2-3 once the stream is available | V3-3 outreach (owner); V3-4 build |
| then | V1-3 freeze → V1-4 labelling → V1-5 scoring | V2-4 report | V3-5 / V3-6 on the owner's decisions |

**What Claude can do without new approvals:**
- V1-0 and V1-1;
- V1.4 tasks 1–3, all code with no scoring;
- V2-0;
- V3-4 code, built locally and never pushed.

**What needs the owner:**
- labellers (V1-2, V1-4);
- the camera (V2-1);
- the privacy decision on the 300 s capture (V2-2);
- V3-1, V3-3, V3-5 and every push.

**What needs the guide:**
- the claim wording (ADR-023 / `CLAIMS.yaml`);
- Part 2;
- MEMO-2026-08-22 (the six-viewpoint set), which overlaps V1 and would give
  V1 Indian footage.
