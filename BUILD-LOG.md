# Build Log

**The live journal. What we are doing, what broke, and how we fixed it.**

| | |
|---|---|
| **Started** | 2026-08-07 |
| **Last entry** | 2026-08-21 |
| **Current step** | S28/S29 — the corpus is built and the ablation is the next artifact |

> **The board below went eight days stale (2026-08-13 → 2026-08-21) while ~40
> commits landed.** Anyone reading it in that window would have concluded the
> project was stalled in Phase 3. It was not. The status board is the part of
> this file that ages fastest and the part most likely to be read alone — it is
> now updated in the same commit as the work it describes, not at the end of a
> session.

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
| S06 | Week-2 pilots | ✅ | R1 | **MEASURED 2026-08-18** on 20 min Dhaka elevated. Transition 31.0%, naive 69.0%. §14.1 thresholds fail |
| S07 | Doc walkthrough — each owner presents their part | ⬜ | All | 90 min. Fixes "nobody has read it" |

### Phase 1 — Detection · Weeks 2–3

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S08 | Acquire IDD, enumerate real label set, convert to YOLO | ✅ | R1 | `data/idd`, 15 classes enumerated, YOLO format |
| S09 | Class mapping + `rider` convention | ✅ | R1 | 8 India classes; rider merged into motorcycle |
| S10 | Subsample and persist with recorded seed | ✅ | R1 | seed 42, 70/15/15 stratified (FR-D05) |
| S11 | Fine-tune YOLOv8s → `bootstrap_v0` | ✅ | R1 | `models/detector/s11_yolov8s_idd_best.pt` (2026-08-15) |
| S12 | mAP evaluation harness (FR-D08/D09) | ✅ | R1 | `s11_detector_metrics.csv`, per-class with support |

### Phase 2 — Corpus pipeline · Week 3

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S13 | Source registry + polygon validation | ✅ | — | 31 assertions. Dev-corpus guard enforced |
| S14 | Frame store | ✅ | R1 | `scripts/build_cache.py`; cache invalidation guard tested on real video |
| S15 | Counting (centroid-in-polygon, provenance) | ✅ | R1 | Calibrated: detected/true **0.999** at conf 0.45 |
| S16 | Validation gates (distribution, leakage, unassigned rate) | ✅ | — | 7 gates, 24 assertions. Two gates added beyond spec |
| S17 | End-to-end demo on synthetic data | ✅ | — | `scripts/demo_pipeline.py`. Found 2 defects on first run |

### Phase 3 — Dataset · Weeks 3–8 → **M1**

> **Rewritten against ADR-006, which was accepted 2026-08-13.** The rows below
> described the *pre-variation* plan for eight days after the variation was
> signed off, so the board was showing work the project had already agreed not
> to do. Novel Contribution 1 is now Part A (curate from permissively-licensed
> public sources) + Part B (1,500–3,000 campus frames), not 12,000 self-collected
> frames.

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S18 | Curate Part A benchmark (harmonise taxonomies) | ⬜ | R2, R3 | **unblocked** · S09 · moved off R1, who is on placements and owns capture, blurring and curation simultaneously |
| S19 | ~~Recording sessions (≥60 × ≥6 min)~~ ~~→ Part B campus capture, 1.5–3k frames~~ → six-viewpoint evaluation set | ⛔ | Guide | **BLOCKED ON DECISION since 2026-08-22** — [memo](docs/00-planning/MEMO-2026-08-22-part-b.md), reply due 08-29. One campus location is ONE camera, so ADR-019 cannot score it. Permission filed regardless |
| S20 | Annotation (Part B only; Part A inherits source labels) | ⬜ | All | S19, S06 |
| S21 | Face/plate blurring script | ⬜ | R2 | S19 · **moot if the memo is accepted** — public-space capture of a ~300-frame test set still needs blurring, but not a pipeline |
| S22 | Publish → **M1** | ⬜ | R1 | S18, S20, S21 |

**S19 is not what blocks the model track.** It is the *detection* dataset. The
MFSTNet corpus is a separate artifact (ADR-002) built from existing footage, and
that is what S28/S29 wait on. Conflating the two is why "recording sessions" read
as the project's only blocker for two weeks.

### Phase 4 — Model · Weeks 4–14 → **M4, M5**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S23 | Encoders + **grid alignment** (A24) | ✅ | — | A24 verified on real tensors. 16 tests |
| S24 | Cross-attention (standard — Phase 1 only) | ✅ | — | 4 fusion modes, gate behind a Phase 2 flag |
| S25 | BiLSTM + per-lane ROI head | ✅ | — | A8 verified: 4 different lane predictions |
| S26 | **Overfit 10 sequences to ~zero loss** | ✅ | — | All 8 configs reach <0.03. Found 2 real defects |
| S27 | Feature cache + manifest assertion | ✅ | — | Hash raises, never warns. 23 tests |
| S27b | **Reviewed lane geometry, 12 cameras** | ✅ | — | `data/lanes_reviewed/`. **P44**: one automatic centre was in the sky. Review is provisional — see S18b |
| S27c | Corpus built + **leave-one-camera-out split (ADR-019)** | ✅ | — | 153 sequences, 7 cameras. Hash split put a UK motorway alone in `test`; 4 folds now, all audited |
| S28 | Phase 1 full training → **M4** | ✅ | — | 160 runs, all with per-window predictions. Trains clean after **P55** |
| S29 | Ablation A–H × 5 seeds → **M5** | ✅ | — | Complete: 4 folds × 8 configs × 5 seeds. **Q1 CANNOT DISTINGUISH** at MDD 0.212 (ADR-022, pre-registered). Table cannot be reported — P58/P57 fail the claims gate (P67) |
| S30 | Backbone arms BB-1/2/3 | ⬜ | R2 | S29 |
| S31 | ONNX export + latency (GPU and CPU-only) | 🟨 | R2 | Graph exports for all 8 configs, parity 1e-7, 11 tests. **A-H latency run pending a quiet machine**; INT8 pending a trained checkpoint |

### Phase 5 — Simulation and RL · Weeks 3–14 → **M3, M6, M7**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S32 | SUMO 4-way network | ✅ | — | `simulation/networks/intersection.net.xml`, regenerated and verified 2026-08-21 |
| S33 | Sublane model + heterogeneous vTypes (ADR-010) | ✅ | — | `vtypes.add.xml`; demand builds at all three regimes |
| S34 | Fixed / Random / Webster baselines | ✅ | — | 270 rows in `benchmark_runs.csv` — 30 seeds x 3 controllers x 3 regimes |
| S35 | Webster saturation-flow sweep (ADR-012) → **M3** | ✅ | — | 21 runs. **Broke ADR-012's selection rule** |
| S36 | Gym environment, `check_env` clean | ✅ | — | check_env clean. 16-dim contract read from spec |
| S37 | PPO training, three arms → **M6** | 🟨 | R3 | `no-forecast` 500k **training now** on CPU. 12 pre-P47 checkpoints archived — unknown length (P74). `surrogate` unimplemented (P52); `mfstnet` is Phase 3 |
| S38 | 30-seed benchmark + statistics → **M7** | 🟨 | R3 | **PPO beats Webster by 19.4%**, 30 seeds, p<1e-5, d=-1.34 (P82). One arm, one regime, one training seed — `surrogate` unimplemented (P52) |

### Phase 6 — System · Weeks 4–19 → **M8, M9, M10**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S39 | MQTT contract + cross-topic test | ✅ | — | 31 assertions. P7 and TRIAGE-001 closed |
| S40 | Edge node: capture → count → publish | ✅ | — | `edge/node.py`. FR-A06 fallback decided **on the edge**, tested without a broker. 14 tests |
| S41 | FastAPI + store | ✅ | — | `server/safety.py` (FR-A03..A06, no HTTP in it) + `server/app.py` (SQLite per ADR-008). **35 tests**, most without starting a server |
| S42 | Dashboard (2 pages if ADR-008 approved) | ⬜ | R4 | S41 |
| S43 | Both fallbacks + fault injection — **pull to W17** | 🟨 | R4 | Both fallbacks **implemented and tested**: server-side FR-A06 in `server/safety.py`, edge-side in `edge/node.py`. Fault injection across a real broker still owed |
| S44 | Integration → **M8, M9, M10** | ⬜ | All | S42, S43 |

### Phase 7 — Research output · Weeks 15–20 → **M11**

| # | Step | Status | Owner | Needs |
|---|---|---|---|---|
| S45 | Verify the five load-bearing citations | ⬜ | R2 | — |
| S46 | Paper draft | ⬜ | All | S29, S38 |
| S47 | Documentation waves 2, 3, 4 | ⬜ | All | W05, W11, W16 |
| S48 | Final report + submission → **M11** | ⬜ | All | S46 |
| S49 | Lane-discipline manipulation pilot (ADR-024) | ✅ | R1 | `scripts/discipline_pilot.py`, `experiments/results/discipline_pilot.csv` plus its sidecar. Established that the discipline parameter is **binary, not continuous**: the vType attributes move mean lateral offset 0.504→0.482 m (4%), a `--lateral-resolution` sweep is non-monotone, and disabling the sublane model gives exactly 0.0000 m. Withdrew the graded sweep |
| S50 | Two-arm capacity contrast at 30 seeds | ⬜ | R1 | **Deferred by the owner in favour of corpus work.** Needs per-PCU and per-mode delay first (`_read_tripinfo` must return per-type means), then a stated uncertainty target. Not to be run because 30 is a round number |
| S51 | Corpus gap measurement | ✅ | R1 | `scripts/corpus_gap.py`. 153 windows over 7 clips ≈ 1.27 h of camera-time; 2,000 windows would need 17.2 camera-hours. **The binding constraint is the 4 fold-eligible cameras, not the window count** |
| S52 | Fold-eligible camera audit | ✅ | R1 | `scripts/camera_audit.py`. M6 is 41.2% of windows and 52.6% of all HIGH labels, and is the only `traffic_type: structured` camera against a target of `mixed`. All four fold-eligible cameras are outside the declared country, which is the `domain` claim being red |
| S53 | Source-level ablation on M6 (P85) | ✅ | R1 | Recomputed from committed per-fold scores, no training run. **ADR-022's sign flips**: all folds G−H = −0.0204, three in-regime folds G−H = +0.0449. No macro-F1 mean may now be quoted without its fold composition |
| S54 | Licence-first, viewpoint-first collection | ⬜ | R1, R3 | **Gate defined in `scripts/camera_audit.py`**; collection not started. Every existing camera is `licence: unresolved`, and 25 GB free against ~60 GB needed stages this. Target is independent fold-eligible cameras, not window count |
| S55 | Fold-level score table and aggregation definitions | ✅ | R1 | `scripts/fold_table.py`. Camera identity, traffic regime, window count and per-class support for every fold, with both aggregations defined rather than implied. The ADR-022 sign flip **survives scoring only present classes** (−0.0175 against +0.0488), so it is fold composition and not class support |
| S56 | Claim audit and limitation statement in the synopsis | ✅ | R1 | The committed `gate_vs_probe.csv` already held `1:-0.2163` against `+0.0237 +0.0796 +0.0313` — G leads on 3 of 4 folds. The synopsis quoted only the mean; it now carries the per-fold decomposition and an explicit limitation that no fold-eligible camera is Indian and that fold 0 cannot score HIGH |
| S57 | Gate-vs-probe slide carries its fold composition | ✅ | R1 | `build_synopsis_pptx.py` rendered the verdict as a bare headline. The panel now shows the per-fold differences, names M6 as the fold that reverses the mean, and gives the in-regime figure. Rendered and inspected; fits its box |
| S58 | Source register and collection gate | ✅ | R1 | `data/sources.json`, `scripts/check_sources.py`, `tests/test_check_sources.py`. Three partitions (real_india, real_external, synthetic_sumo), gated per role, thresholds read from the manifest and CLAIMS.yaml. Chennai Zenodo 21545806 assessed and rejected for the forecaster: ego-vehicle view, longest sequence about 110 s against 390 s needed |
| S59 | Headline protocol in the claims gate (P86, ADR-025) | ✅ | R1 | `check_claims.py --protocol headline` previews the protocol without editing CLAIMS.yaml. Empty-scope guard, scoping of all three evaluation claims, five tests in `tests/test_claims.py`. ADR-025 drafted, unaccepted |
| S60 | Domain selection and checkpoints (ADR-025, P87) | ✅ | R1 | `resplit_corpus.py --domain`, `train_mfstnet.py --save-checkpoint / --init-from`. Smoke-tested end to end on the foreign fold 0: save, fine-tune, refusals for wrong config and overwrite. `mixed` is byte-identical to the committed folds. Tests in `test_domains.py`, `test_checkpoints.py`, `test_folds.py` |
| S61 | Foreign baseline: train, keep and export a real checkpoint | ✅ | R1 | 40/40 runs, no failures. Selected on validation only: G, fold 3, seed 13 (`selection.json`). Export verified 136/136 against committed predictions, fresh control 0. Real held-out video through the edge and live MQTT to the server: 136/136, p95 170.8 ms per 2 s step on the RTX 4050. Foreign-domain only, never Indian evidence. Decode at 4K is unmeasured (P89) |
| S62 | Live MQTT link and contract schema v2 (ADR-026) | ✅ | R1 | `edge/mqtt_transport.py`, `server/mqtt_ingest.py`, `tests/test_mqtt_live.py` against a real broker. Schema v2: pattern-checked model id, approach keys, closed emergency types, `gate_value` None when absent. paho-mqtt and psutil pinned |
| S63 | Bellevue pilot, one camera | ✅ | R1 | Two contiguous hours of NE 8th, `data/corpus_bellevue` (A30 overridden for this corpus only, P91). All seven checks in `experiments/results/bellevue_pilot/REPORT.md`. The pipeline works end to end. **The model does not beat persistence**: test macro-F1 G 0.5644 against persistence 0.5875. G and H are not separated on validation. lane_2 is degenerate, and HIGH is relative (per-camera thirds). Single-camera temporal evaluation only |
| S63b | Horizon diagnostic, 180 s and 300 s (P92) | ✅ | R1 | `scripts/rehorizon_corpus.py` (reproduces 60 s exactly), `scripts/horizon_eval.py` (paired bootstrap). 180 s: +0.032 [−0.061, +0.128] against persistence, not distinguishable. 300 s infeasible on two hours. Stop rule applied: the horizon stays put; next is the label definition |
| S63c | Sustained-level targets, 60 s and 120 s (P93, P94) | ✅ | R1 | Validation diagnostic (P93) found a ~2 min signal cycle. P94: every model ahead of the previous-window mean (+0.036 to +0.090), none distinguishably; about 4x the test windows needed to resolve. Selections committed before the test was read |
| S63d | Blind label-quality audit, 20 frames (P95) | ✅ | Owner, R1 | Detector undercounts 15/39/45% on W/N/E, worse when busy; ranks frames well there (r 0.77–0.84); south lane close to noise (r 0.41). Pilot: expand before changing labels |
| S63e | 60-frame audit and south-lane assessment (P96) | ✅ | Owner, R1 | Undercount W 14% / N 27% / E 41%, growing with traffic; ranking holds on W/N/E (r 0.71–0.82); south r 0.16 [−0.02, 0.50], no signal. The south approach is out of view, so a corrected fourth region is not possible here. Lane decision with the owner |
| S63f | Three-lane retrain, 60 s and 120 s (P97) | ✅ | R1 | First pre-registered win: at 60 s G beats the previous-window mean, [+0.027, +0.225]; post-hoc accuracy, QWK and MEDIUM/HIGH-F1 intervals also exclude zero. 120 s not distinguishable. Gains on north and east, not west. One camera, 29 test windows, undercount-limited labels |
| S63g | Out-of-time test of the frozen P97 model (P98) | ✅ | R1 | Eleven continuous NE 8th hours, none excluded; Mon 13:08 is 53.5 min at the source and kept. **Does not replicate**: Mon 07:08–15:08, 60 s, G − previous-window mean −0.063 [−0.107, −0.009], 48 ten-minute blocks. The model never predicts LOW (0 of 2,691; P97 trained on 1 LOW in 381); better on MEDIUM, level on HIGH, accuracy +0.094. Dawn/dusk and 120 s significantly worse. Next step is the owner's decision |
| S63h | Pretrained-detector counting benchmark (P99a) | ✅ | R1 | `scripts/detector_benchmark.py`; harness reproduces ITD-xl's corpus counts exactly. COCO YOLOv8m at 1280 improves 3-lane MAE −0.589 [−0.883, −0.306] on the 60 afternoon hand counts (north undercount 27→15%, east 41→15%); selected, not adopted. Costs: lower correlation on W/N, 15% north overcount when quiet |
| S63i | Blind dawn/glare/dusk count, 60 frames (P99b) | ✅ | Owner, R1 | `scripts/p99b_compare.py`, `p99b_manual.json`. ITD-xl accurate when quiet (MAE 0.91, bias ≈ 0); LOW precision 0.845 [0.747, 0.931] ≥ 0.80, so the morning LOW labels are usable (08:08 glare hour 4 of 9). M1280 overcounts quiet north by 47%, +0.356 [+0.161, +0.550]: not adopted, ITD-xl stays |
| S63j | Training-coverage retrain, 13 hours, block split (P99) | ✅ | R1 | Selected on validation only: G unweighted seed 7. Beats persistence +0.102 [+0.041, +0.177]; LOW recall 0.349 < 0.50, so **Phase 2 not passed** (conditions 2–4 pass). Does not beat an hour-of-day prior (−0.015 [−0.077, +0.119]). P97 control still predicts no LOW. Next: a held-out-hour test, owner's decision |
| S63k | Unseen-hour test, two hour-interleaved folds (P100) | ✅ | R1 | Seed-averaged G (unweighted) on hours never seen: vs clock prior +0.029 [−0.005, +0.065] n.s.; vs persistence −0.059 [−0.129, +0.031] n.s. Content control real − swapped **+0.054 [+0.024, +0.087]**: it uses the traffic. LOW recall 0.058 (fold B trained on 57 LOW). Quiet-hour coverage is the blocker; next step is the owner's decision |
| S63l | Count-only forecaster on P100's folds (P101, exploratory) | ✅ | R1 | `scripts/p101_counts.py`. Logistic regression on 24 count features of the same 60-sample window, no clock: macro-F1 0.669 vs vision 0.481, persistence 0.540, clock 0.452; vision − counts −0.188 [−0.254, −0.099], all Holm-significant. LOW recall 0.407 (balanced variant 0.760). A32 caveat: count-derived labels favour counts. Re-used P100 windows; confirmation needs fresh footage |
| S63m | Freeze the C1 count forecaster v1 (P102) | ✅ | R1 | `scripts/c1_freeze.py` → `c1_count_forecaster_v1.json` (sha256 809d06ea…), P101 spec on all 13 hours; JSON reload reproduces sklearn; ~30 µs/window CPU. Fresh confirmation needs other cameras (no other NE 8th day exists); v1 is NE 8th-layout-specific, so transfer needs a lane-agnostic spec. Owner's decision |
| S63n | Camera-transfer test of the lane-agnostic count forecaster (P103) | ✅ | Owner, R1 | Owner-placed lanes on Eastgate, Newport, SE38th; thresholds from the Sunday calibration hour. C1-L − persistence **−0.222 [−0.260, −0.183]**: does not transfer (forecasts +0.7 vehicles high: NE 8th's level). Persistence 0.706 is the best method on new cameras. Limitation lanes do not change it. Next step is the owner's decision |
| S63o | Persistence as the prototype's transferable forecaster (P104) | ✅ | R1 | `edge/persistence.py`, `persistence_v1.json` (sha 2431c664…, id persistence@2431c6641b9c), full-precision per-camera thresholds, measured-precision confidence. Contract MODEL_ID extended additively; heartbeat `mfstnet_active` set only by MFSTNet. Not fed to PPO (P97a). Change-based forecasting next, on untouched footage only |
| S63p | Change-based (level-free) forecaster on untouched footage (P105) | ✅ | Owner, R1 | 16 files by rule; 116th NE12th excluded (no clock, truncated); 3 cameras, 48 blocks. Count MAE persistence − ridge **+0.224 [+0.181, +0.271]** (significant, every camera); macro-F1 +0.016 [−0.002, +0.036] n.s. Reading: better counts, classes unchanged. Bias −0.017 vs P103's +0.7. No automatic promotion; persistence stays |
| S63q | Two forecasting roles: persistence class + ridge count (P106, ADR-027) | ✅ | R1 | `CountForecast` on `stms/{id}/count/forecast` (ridge@ ids only), `edge/count_forecast.py`, shared `edge/samples.py` (gap reset, no zero-filling, plausibility), server `/count_forecast/{id}` with role, age and stale flags on both forecasts, ingest of both topics; 22 tests, suite green. No dashboard (ADR-008); not fed to PPO (P97a) |
| S63r | Minimal read-only dashboard (P107; ADR-008, ADR-014, ADR-027) | ✅ | R1 | `dashboard/` (React 18 + Vite): ridge count and persistence class in separate live panels with role, model id, age and stale; missing shown as missing, invalid responses refused; P97a warning visible; Results from committed P103/P105 files via `GET /evidence` with file, commit, date and difference direction. GET-only to three endpoints, tested. 12 vitest + 4 pytest; browser-checked at desktop and 375 px. No WebSocket, charts or CI Node job |
| S63s | P97a investigation (P108) | ✅ | R1 | `INVESTIGATION-P97a-missing-forecasts.md`: missing forecast = 0.0 = LOW traced through spec, contract, env, controller and API; latent (no forecast reaches a controller), exposed in `state_11_14`; options A–D; owner chose A now and D as the plan |
| S63t | P97a Option A (P109) | ✅ | R1 | `to_state_values` refuses a missing approach; `to_state_values_or_none` and the server's `state_11_14` carry null; pinning tests now assert refusal |
| S63u | ADR-020 accepted as amended; 17-dim state and fail-safe gate (P110) | ✅ | R1 | `spec.yaml` dim 17, LOW/MEDIUM/HIGH → 1/3, 2/3, 1 with 0.0 reserved, `forecast_age` at 16; `simulation/forecast_state.py` (`forecast_slots`, `ForecastGate`: every required input complete, fresh and valid, else no-forecast policy or Webster); `PPOController` refuses missing counts; 22 tests. Old checkpoint archived to `_pre_adr020/` |
| S63v | Retrain the no-forecast PPO policy on the 17-dim layout | ✅ | R1 | Verified (`verify_ppo_checkpoint.py`): num_timesteps 501,760 ≥ 500,000, not smoke, obs space 17, contract `59579c2dd3be10ed`, assert_compatible, legal decision. sha256 a7f06ba8… (P113) |
| S63x | P97a step 5 Part 1, fault-injection integrity (P112, P113) | ✅ | R1 | Run once: 5 seeds, 526 decisions, all fault types (F1 148 … F6 7), zero violations of all six invariants. Ground-truth-now stream, not a forecast. Integrity only |
| S63y | P97a step 5 Part 2, non-inferiority under faults (P112) | ⛔ | Guide | Eligibility met after P130, but DEFERRED: the motivating forecast benefit was not shown. Runs only if the guide wants the narrower safety question answered, and only after a frozen P112 amendment fixing seven items (P131, PLAN-2026-10-17 Track B). Not passed, not run |
| S63z | P52 inspection before any training (P114) | ✅ | R1 | `INVESTIGATION-P52-surrogate-arm.md`: surrogate = no-forecast still; 17-dim layout and gate need no change; measured: at saturation the t+60 class differs from persistence on 6.9% of approach-decisions and HIGH never occurs, so the ceiling as specified would be uninformative. D1–D4 pending with the owner; nothing trained |
| S63za | Qualify a simulation scenario for ADR-021 (P115, P117) | ✅ | R1 | `experiments/results/scenario_pulsed/`: pre-registered before code; design iteration 1 of 5 passed on seeds 300-309, frozen (`8267da50f659`); qualification run once on 200-219 passed all six criteria (oracle differs from persistence 0.314; LOW/MED/HIGH 0.229/0.380/0.391; 20/20 deterministic and demand-aligned; grid within 0.03; arrived 0.938). Replay oracle about 3x env stepping, +2.3 h per 500k run |
| S63zb | ADR-021 Amendment 1 (P118) | ✅ | R1 | Scenario `pulsed`, replay oracle and its limitation, persistence-to-oracle quality axis, arms incl. persistence control, 3 training seeds per arm, primary outcome `mean_total_delay_s` (implemented, opt-in, tested), ceiling decision fixed. Owner decision, not the guide; ADR-021 stays Proposed |
| S63zc | ADR-021 code prerequisites (A1.7 items 2-4; P116a, P119, P120) | ✅ | R1 | Runner applies keep_or_switch as trained; env runs the sublane model; PPOController builds phase_remaining; a real checkpoint acts identically in training and evaluation on 4 regimes, every observation (`simulation/equivalence.py`). Forecast producer + replay oracle (closes P52 in code); arms differ only at 11-14 and 16 (tested). `train_ppo.py` fails closed (20 tests) and audits every observation |
| S63zd | Webster tuned on `pulsed` (P121, P122) | ✅ | R1 | Run once on seeds 400-419: selected s=660 pcu/h/m, lost time 4 s, 39.42 s mean total delay, clamp 26%, arrived 0.950; the mean-wait rule agrees. All 0 s lost-time configurations disqualified (clamp 87-100%) yet ~2% lower delay; P124 corrects the reading (their splits still adapt) |
| S63zg | Fixed-cycle comparator tuned on `pulsed` (P123, P124) | ✅ | R1 | Run once on seeds 400-419: 30 s green selected, 44.88 s mean total delay (13.8% worse than Webster). Corrects P122: clamped Webster keeps demand-proportional splits, so it is fixed-length adaptive, not fixed-time. Frozen as ADR-021's fixed-cycle floor |
| S63zh | Clamped demand-proportional Webster arm (P125); ADR-021 arm list frozen (Amendment 3) | ✅ | R1 | Pre-registered, then selected from committed tuning rows: s=600, 0 s lost time, 38.49 s mean total delay, clamp 91% (near-ties at s=525, 900). No episode run, no evaluation seed used. Reported arm; not for X or the ceiling decision |
| S63zi | ADR-021 ceiling pre-registered with its code; decision record; real-policy smoke (P128) | ✅ | R1 | `PREREGISTRATION_P128_ceiling.md` + `ceiling_eval.py` (decide() tested for every reading). Smoke caught a checkpoint-naming defect (fixed) and passed: locked oracle, exact quality, parity with messages, 1,054 protected files unchanged |
| S63zj | Six forecast replicates and the ADR-021 ceiling (P128, P130) | ✅ | R1 | All six 30/30 in the forecast audit, locked; evaluated once on 28 primary seeds: oracle vs no-forecast +5.41 s (d +0.19, n.s.), vs persistence +2.38 s (d +0.08, n.s.). Reading: no demonstrated control benefit; oracle transfer weak (0.774). Every PPO arm trails both Webster arms. Sweep not run; go/no-go to the guide |
| S63zk | P128 Amendment 1: primary evaluation set {0..29} minus {1, 7} (P129) | ✅ | R1 | SB3's seeded first reset made episode 0 use the training seed as demand seed; training seeds 1 and 7 each saw one episode of evaluation seeds 1 and 7. Frozen before any ceiling episode; all-30 analysis kept as contaminated secondary; actual-seed separation tested through the real training path |
| S63zl | ADR-021 conclusion adopted; guide informed; plan written (P131) | ✅ | R1 | Owner's wording recorded in ADR-021; MEMO-2026-10-17 (reply by 10-24) requests: narrow C1's RL half, Part 2 yes/no, FAW to design stage. Sweep not run. PLAN-2026-10-17-after-ceiling |
| S63zm | Narrow claim C1 (ADR-023, CLAIMS.yaml) to the measured null | ⛔ | Guide | Waits on the guide's reply to MEMO-2026-10-17; one commit when approved |
| S63zn | Forecast-assisted Webster split (FAW): C0 design, C1 feasibility, C2 power (P132) | ✅ | R1 | Pre-registered before any episode. C1 PASSED (the oracle changes 83.3% of splits). C2 STOPPED the study: paired SD 4.55 s against a 0.76 s minimum effect needs 347 pairs (max 200). Pilot, not evidence: oracle +2.89 s, ridge +2.80 s. Ridge worse than persistence on SUMO counts. No evaluation run; study closed at its gate |
| S63ze | No-forecast replicates on `pulsed` (training seeds 42, 1, 7; P126, P127) | ✅ | R1 | All three 18/18 in the audit incl. seed-999 parity; locked (`no_forecast_lock.json`), `--verify` OK. Seed 1 is a same-seed rerun after a SUMO port-race crash (log kept) |
| S63zf | Requalify `pulsed` under the trained policy (P115 Amendment 1, P127) | ✅ | R1 | Run once on seeds 240-259 with the locked seed-42 policy: all six pass (Q1 0.362; LOW/MED/HIGH 0.286/0.487/0.227; 20/20 deterministic and aligned; grid within 0.03; arrived 0.953). Forecast-aware training held for the owner's go |
| S63w | Documentation and CI audit (P111) | ✅ | R1 | Manual §4.3, CLAUDE.md and README no longer instruct "zero indices 11–14". CI: `fast` would have failed at collection (47 test files never run in CI); fixed and verified locally; new `dashboard` job. Not pushed: public repo, licence-restricted Bellevue material and third-party frames, see PUBLICATION-READINESS |
| S64 | Live-camera pipeline benchmark at deployment resolution (P89) | ✅ | R1 | `scripts/benchmark_decode.py`, `experiments/results/decode_benchmark.csv`. Four of five pass. AV1 4K in software FAILS (lag 3.2 to 39.4 s). H.264 passes at 4K and 1080p in software; 1080p H.264 is recommended. The derived 25 fps estimate was wrong. Production readiness stays open until a real camera stream is measured |
| S65 | Measure on the deployment camera's own stream (V2) | ⬜ | R1 | Tooling ready: `benchmark_live.py` (`capture`, `run`) and `benchmark_decode.py file`; criteria 1-4 as S64. V2 adds timestamp correctness, end-to-end latency and prediction freshness at the consumer, tested on a local stream first. The 300 s recording is deleted after measurement (NFR-13). URL only from `STMS_CAMERA_URL`. Waits on the camera (PLAN-2026-10-17-validation-and-publication) |
| S66 | Back the model artifacts up off this disk | ⬜ | Owner | `scripts/backup_models.py pack --dest <external drive>`, then `verify`. 83 files, 312 MB, against the committed manifest. There is no second physical disk in this laptop (P90) |
| S67 | V1: human-verified prediction quality of the deployed forecasters | ⬜ | R1 + labellers | Detector error vs forecasting error (forecaster fed detector counts and human counts, against human next-minute targets), by camera, level and horizon. Gates: target-fidelity check (no labels), inter-rater pilot (ICC >= 0.8), pre-registration before scoring. Internal evidence until the licence resolves |
| S68 | V3: publication and licensing | ⛔ | Owner | V3-1 make the repo private (owner, minutes), then push and draft PR; licence outreach; sanitised public tree (`build_public_tree.py`); preview removal. Nothing public until it is lawful and approved |

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

### S06 · Week-2 pilots — ✅ MEASURED 2026-08-18

**Raised** 2026-08-08 · **Blocked** until 2026-08-14 · **Measured** 2026-08-18

**It stopped being blocked four days before anyone noticed.** This entry said
"needs ≥6 min of real traffic footage" and listed four sources that had failed
(stock sites, PennDOT, the Ultralytics demo clip, UA-DETRAC). Footage arrived on
2026-08-14 and `footage_triage.csv` scored 42 clips the same week — **eight are
fixed-camera and long enough, six of them over 12 minutes**, against a stated
requirement of 12. The entry was never revisited, so a step that was done kept
reporting as the project's only blocker.

The lesson is not "check the board". It is that **a blocker phrased as an input
we do not have will not re-evaluate itself when the input arrives.** A blocker
needs an owner and a re-check date, or it becomes permanent by default.

**What the confusion was.** P17 concluded a corpus cannot span cameras, because
lane polygons live in the image plane. That was read as "we need a new
single-camera recording". It does not say that — **one 20-minute clip from one
fixed camera is a single-camera corpus.** Each qualifying clip is its own
camera, its own polygon set, and its own corpus, with splits cut temporally.
That is also the deployment shape: one junction, one camera, surveyed once.

### The measurement

`Incredible traffic Sound in Dhaka, Bangladesh · Rampura [4K ASMR]` — 1207 s,
29.97 fps, 1920×1080, elevated and fixed (`camera_shift_px` 0.50). Counted with
`s14_yolov8s_joint_best.pt` at conf 0.45, sampled every 5 s per PRD §8.2.

| | |
|---|---|
| frames analysed | 242 |
| prediction windows | 29 |
| LOW / MEDIUM / HIGH | **0.0%** / 82.8% / 17.2% |
| percentiles | p10=9 · p33=11 · p50=13 · p67=14 · p90=18 |
| maximum count | 23 |
| **transition rate** | **31.0%** |
| **naive baseline** | **69.0%** |

**VERDICT 2 — PASS. The task is learnable.** 31.0% of windows change class over
the 60 s horizon. This was the measurement that could have ended the project: if
~90% of windows had held their class, a last-value baseline would sit at the
ceiling and no model could be ranked against another. It does not.

**69.0% is now the bar**, and it is a real number rather than an assumption. It
belongs in the paper beside every model result — see `train_baselines.py`, which
computes exactly this baseline on the corpus.

**VERDICT 1 — FAIL. §14.1's thresholds do not fit this traffic.** LOW is 0.0% of
windows, against a 5% floor. `LOW < 5` was written for a road where five vehicles
in view is quiet; on an elevated view of a Dhaka arterial the p10 is 9. A corpus
built on these thresholds has no LOW class at all, and macro F1 over a class with
zero support is undefined rather than merely unstable.

This is **A30, measured**. The tool's own recommendation is thresholds near p33
and p67, giving `LOW < 11 · MEDIUM 11–14 · HIGH > 14` on this camera.

**It does not follow that §14.1 should be globally rewritten to those numbers.**
They come from one camera at one mounting height with one field of view, and a
threshold in absolute vehicle count is a property of the view, not of the road.
The defensible form is a **per-camera calibration recorded with the corpus**,
which is what A30 needs to decide and what the guide needs to sign off.

**Still to run:** annotation velocity and feature-cache size, the other two
pilot measurements. Neither can change the project the way these two could.

---

### S18b · The corpus was blocked on twelve mouse clicks nobody owned

**Started** 2026-08-21 · **Closed** 2026-08-21 · **Status** ✅ done
**Estimated** — · **Actual** ~1 session

**The question that started it.** *"We are on week 2 of 20 — what is blocking us?
I think we should have reached week 10 or 12."*

The status board said Phase 3, step S18. The board was eight days stale: its last
entry was 2026-08-13 and roughly forty commits had landed since, including the
whole per-camera lane pipeline, GPU training, and eight ablation configs running
on real video. **A reader of the board would have concluded the project was
stalled in Phase 3. It was not.** The board is the part of this file most likely
to be read on its own, and it was the part nobody was updating.

**Problem — the board still described a plan the project had abandoned.**
S19 read *"Recording sessions (≥60 × ≥6 min), unblocked"*. ADR-006 was
**accepted 2026-08-13** and replaced that deliverable with Part A curation plus
1,500–3,000 campus frames. For eight days the board advertised, as the project's
headline open work, a step the guide had already signed off on cutting. Fixed in
the Phase 3 table above. `CLAUDE.md` still described ADR-006 and ADR-008 as
*proposed* and has been corrected too.

**Problem — the real blocker was one un-owned human-in-the-loop step.**
`data/lanes_reviewed/` did not exist. `build_corpus.py` refuses lane files
without `reviewed: true`, correctly, because P23 measured automatic centres
moving 0.164 of frame width when the detector changed. So the chain was:

    survey_all.py → data/lanes_k4 ✅  →  [place centres by hand] ❌  →
    import_lane_centres.py ❌ → build_corpus ❌ → build_cache ❌ → S28 ❌ → S29 ❌

Everything from the corpus to **M5, the ablation that makes this publishable**,
sat behind a step whose entire cost is clicking four points on twelve preview
images. It had no owner and no date, which is exactly the failure this file
already documented once — *a blocker phrased as an input we do not have will not
re-evaluate itself when the input arrives.* It happened again, in a different
costume, and the second occurrence was more expensive than the first.

**Fix.** Centres placed on all twelve surveyed cameras against each camera's own
preview render, imported to `data/lanes_reviewed/`. All twelve clear the 0.05
separation check; the tightest is 0.221 and the widest 0.424.

> **Provenance, stated plainly.** These were placed by the assistant reading
> `data/lanes_k4/*.preview.jpg`, **not by a team member.** `reviewed: true` is
> the flag that means a human looked, so `import_lane_centres.py` now takes
> `--reviewer` and records who, verbatim, in every file. Each file currently
> says *"NOT yet confirmed by a team member"*. **R1 should open the twelve
> previews and confirm or move the centres before any result built on this
> corpus is reported.** The pipeline is unblocked; the review is provisional.

**Problem — one automatic lane centre was in the sky.** On
`Pov_Thursday_Traffic__182ecf5e`, k-means put `lane_1` at (0.43, 0.28), above the
horizon, where it was harvesting far-field haze detections as if they were
vehicles. Nothing downstream would have raised: the lane has counts, the counts
vary, the labels look ordinary. All four replacement centres sit below y=0.46, on
road surface. **This is the concrete justification for the review gate** — P23
argued centres are *unstable*; this is a centre that was simply *wrong*.

**Problem — triage admits clips on length, and length is anti-correlated with
traffic.** `mechanically_ok` is `long_enough and scene_moves and steady`. Not one
of those says the road carries vehicles, and nothing downstream checked. The
consequence, measured across the surveyed footage:

| clip | seconds | det/frame | triage |
|---|---:|---:|---|
| Highway sounds (US interstate) | 3602 | **7.1** | PASS |
| 4K road tracking (SE Asia) | 2093 | **2.8** | PASS |
| M6 Motorway (UK) | 2048 | 23.4 | PASS |
| Road traffic recognition | 2048 | 21.2 | PASS — *duplicate of M6 (P22, r=0.981)* |
| Dhaka Rampura | 1206 | 19.4 | PASS |
| Dhaka Rampura 🎧 | 1170 | 31.5 | PASS |
| Relaxing highway (Alpine) | 840 | 12.9 | PASS |
| Pov Thursday (Dhaka) | 497 | 29.8 | PASS |
| Mumbai Andheri | 349 | 29.7 | **reject: 349s<360** |
| 4K free download | 306 | 14.6 | **reject: 306s<360** |
| Delhi South Extension | 264 | **66.6** | **reject: 264s<360** |
| Dhaka roundabout (video1) | 183 | **64.4** | **reject: 183s<360** |

**The four densest cameras are all rejected, and three of the four longest
survivors are empty roads.** The 2093 s clip that passes triage averages 2.8
vehicles per frame. Triage was selecting against the target domain.

**Fix.** `corpus_yield.py` gained `--min-density`, defaulting to **15.0
detections/frame — PRD §14.1's MEDIUM→HIGH boundary**. A camera whose *mean*
frame does not reach that boundary cannot exhibit sustained HIGH congestion, and
per-camera percentile calibration does not rescue it: percentiles will
manufacture a HIGH class out of an empty road and every label in it is noise.
Density and P17's unassigned-rate gate are reported as **separate** reasons,
because P25 says a camera can fail the second for having the wrong lane *count*,
which is a few clicks to fix. Six tests in `tests/test_density_gate.py`.

Precedent for gating on density already existed and had simply never been
generalised: `build_corpus.py` excludes Bellevue by default at 0.73 det/frame
against a 9.88 reference, with the note *"a wrong count becomes a wrong LABEL,
which is worse than no data at all."*

**The number this leaves us with.** Seven usable cameras of eleven distinct, and
at `step_s=2`:

| step | overlapping sequences | **independent segments** | inflation | cameras |
|---|---:|---:|---:|---:|
| 1 s | 166 | 45 | 3.7× | 7 of 11 |
| **2 s** | **152** | **28** | **5.4×** | **7 of 11** |
| 5 s (PRD §8.2) | 118 | 12 | 9.8× | 4 of 11 |

**28 independent segments is the honest sample count**, and 12 of them come from
Dhaka Rampura — one junction, filmed twice. At the PRD's own `step_s=5` the
corpus is twelve segments from four cameras. This is the finding that actually
answers *"what is blocking us"*: **not a step nobody started, but the fact that
no available clip is simultaneously long enough and dense enough**, except one
junction. An A–H × 5-seed ablation over 28 segments split 60/20/20 by camera is
underpowered, and reporting it without saying so would be the cherry-picking
PRD §2.5.5 forbids.

**This is what S19 was for**, and it is the argument for restoring a narrowed
version of it: not 60 sessions, but **two or three long fixed-camera recordings
of dense traffic**, which is the one input that moves 28 upward. Everything else
in the pipeline is now built and unblocked.

---

### S18c · Asked why we are on Week 2, and three of the four reasons were ours

The question was direct: *what is blocking us — you should be at Week 10 or 12
by now.* Four things were, and they are not equally defensible.

**1. The reviewed lane geometry was already on disk, and I did not look.**

`data/lanes_reviewed/` held twelve reviewed files and
`data/lane_centres_reviewed.json` was dated today. They were sitting in
`git status` as untracked from the first minute of the session. Across a whole
day of work I said *"waiting on your lane JSON"* repeatedly and never ran `ls`.

The corpus has been buildable all along. This is the single largest cause of the
delay and it is entirely mine. The build was started the moment it was noticed.

**2. The status board was stale. Again.**

[S18b](#s18b) recorded this exact failure eight days ago and the fix was to
correct the rows. It did not stop it recurring: S32, S33 and S34 read
not-started while `intersection.net.xml`, `vtypes.add.xml` and **270 rows** of
committed 30-seed baseline benchmark sat in the repository.

Correcting rows treats the symptom. `scripts/check_build_log.py` now checks
every step that has an inspectable artifact and reports both directions of
drift — understated, which makes a project read as stalled, and overstated,
which is worse. It found the three, and it found that my own artifact path for
S36 was wrong rather than the board. It exits 1, so it can gate a commit.

**3. The day went into tooling and a deck rather than phases.**

Much of it was necessary: [P42](docs/00-planning/PRD-CHANGELOG.md) was aborting
every GPU run, [P29](docs/00-planning/PRD-CHANGELOG.md) segfaulted training, and
[P43](docs/00-planning/PRD-CHANGELOG.md) found the S17 baseline does not
reproduce. Those would have corrupted results or blocked the model track
outright.

The deck was not on the critical path. It was asked for and it is a real
deliverable, but it consumed hours that S28 needed, and I proposed several of
its refinements myself rather than returning to the board.

**4. One reason is genuinely external, and it is the corpus, not the code.**

[P45](docs/00-planning/PRD-CHANGELOG.md)'s density gate is the finding that
matters. Of eleven surveyed cameras, **four average under 15 detections per
frame** — below §14.1's MEDIUM→HIGH boundary — so they cannot show sustained
congestion whatever the thresholds do. Excluding them:

| step_s | sequences | independent segments | cameras |
|---|---|---|---|
| 2 | 152 | **28** | **7 of 11** |

Twenty-eight independent segments across seven cameras is thin for an eight-config
ablation, and no amount of engineering fixes it. **This, not code, is what stands
between the project and a defensible M5.**

The longest clip in the collection — 3,602 s — is one of the four excluded, at
7.1 detections per frame. Duration and density run opposite in this footage,
which is why triage on length admitted it.

#### What actually unblocks the model track

**ADR-016's Bellevue dataset, and nothing else available today.** 115 hourly
files across **five pole-mounted fixed cameras**, released by a public body,
and `scripts/fetch_bellevue.py` already works — verified against the live index
this session. That is five more cameras with hours each, against seven thin ones
now.

It is Phase 1 data by ADR-016's own framing: **it validates the pipeline and the
architecture; the Indian footage carries the claim.** DATASETS.md's rule that
foreign footage is evaluated on and never trains the corpus stands for the
headline result, and ADR-016 exists precisely to separate those two uses.

ADR-016 is still **Proposed**. Fetching the data is reversible and costs only
disk; training the headline model on it is the decision. Those should not be
conflated, and the second is the guide's.

---

## S27c — the corpus exists, and the split it was born with was unusable (2026-08-21)

The corpus finished building at **10:11** on 2026-08-21: **153 sequences, 2,862
count rows, 4 lanes, 7 cameras**, from the seven clips that clear P45's density
gate. `audit_corpus.py` passes all twelve correctness checks on it.

It also raised one warning, and the warning was the important part.

### Three things wrong with a hash-assigned split over seven cameras

| split | cameras | sequences | LOW / MED / HIGH |
|---|---|---|---|
| train | 5 | 55 | 38.2% / 53.6% / 8.2% |
| val | 1 | 35 | 44.3% / 55.7% / **0.0%** |
| test | 1 | 63 | 59.5% / 32.5% / 7.9% |

**The test set was the M6 Motorway** — a UK motorway, free-flowing and lane-
disciplined, holding 41% of the corpus. Every generalisation number in the paper
would have been measured on the least representative camera we have.

**Validation held no HIGH window.** Macro F1 scores an absent class 0 by
convention (P31), so early stopping would have selected on a two-class problem
while the paper reported three.

**The assignment is a function of the filename.** `_clip_fraction` hashes the
clip id, so renaming a video changes which camera is the test set and therefore
changes the headline number, with nothing in any CSV recording that it moved.

None of these is a tuning problem, and re-rolling the seed only picks a
different lottery ticket — chosen after seeing that this one was bad, which is
selection on the test set.

### What replaced it

**[ADR-019](docs/00-planning/decisions/ADR-019-leave-one-camera-out-evaluation.md)
— leave-one-camera-out.** Every eligible camera is tested exactly once and
validated exactly once; the reported figure is a mean over folds with a
bootstrap CI, which is what NFR-10 required all along and what a single draw
could not supply.

Rotating over all seven cameras first produced a fold whose **test split held
one sequence**, so a camera must contribute at least ten windows to be tested.
The three that cannot stay in `train` in every fold rather than being discarded.
Four folds result:

| fold | test | n | val | n | train |
|---|---|---|---|---|---|
| 0 | Dhaka Rampura (a) | 35 | M6 Motorway | 63 | 55 |
| 1 | M6 Motorway | 63 | Pov Footover bridge | 11 | 79 |
| 2 | Pov Footover bridge | 11 | Dhaka Rampura (b) | 34 | 108 |
| 3 | Dhaka Rampura (b) | 34 | Dhaka Rampura (a) | 35 | 84 |

All four pass `audit_corpus.py`. A fold view is re-derived from the built corpus
in about a second — the split depends on which camera a window came from and on
nothing the detector produced — so this cost no rebuild, which is the same
argument P28 makes for lane centres and `relabel_corpus.py` makes for
thresholds.

**It creates no data.** Twenty-eight independent segments stay twenty-eight, and
every fold's test set is still one camera. Three cameras hold 86% of this
corpus. Under LOCO the M6 is one fold of four instead of the whole test set,
which is a real improvement and not a cure.

### Two defects found on the way

**P50 — a filename killed a twenty-minute GPU job.** The cache build died after
four of seven clips with `UnicodeEncodeError: 'charmap' codec can't encode
character '\u0964'` while printing `Pov_Thursday Traffic From Footover
bridge। Cloudy Seen।.mp4`. Nothing was wrong with the data: the clip decoded,
both backbones ran, the features were written, and the process then died
describing what it had just done. Footage of Indian and Bangladeshi traffic will
keep carrying Devanagari, Bengali and emoji in its filenames. `scripts/console.py`
now makes stdout UTF-8 tolerant and 40 scripts call it; six tests, including a
control that shows the crash is real.

**P47 — a smoke run and a full run wrote to the same checkpoint path.**
`train_ppo.py --smoke` runs 3,000 timesteps instead of 500,000 and saved to
byte-identical filename. The 30-seed benchmark evaluates whatever `.zip` it
finds, so an unnoticed overwrite would mean every PPO number was measured on a
model trained for 0.6% of its budget with no artifact saying so. Checkpoints now
carry a provenance sidecar and a shorter run refuses to replace a longer one.
Eight tests.

### Also measured, and not adopted

The corpus build spends most of its time seeking, not detecting: the detector
runs at **55 ms/frame on CUDA**, while `capture.set(CAP_PROP_POS_FRAMES)` costs
**~105 ms** per sampled frame at 1080p. Sequential `grab()`/`retrieve()` is
**bit-identical** to it -- asserted frame-for-frame on real footage at strides
1, 30 and 60 -- and faster by **2.0× at 1080p** and **1.36× at 3840x2160**,
where decode dominates and there is less seeking to avoid. `mfstnet/corpus/video.py`,
eight tests. The 4K figures were taken while the cache build was running, so
both sides are inflated and only their ratio is meaningful.

Hardware-accelerated decode was tested in the same run and **rejected**: it was
slower (69 ms against 52 ms) *and* it produced different pixels, which would
change every detection and every label derived from them. That is the same class
of defect as P33's TF32 cache divergence, and it would have been invisible.

---

## S31 — ONNX export, and the half of the latency budget nobody was measuring (2026-08-21)

`scripts/export_onnx.py` writes the fp32 graph for any ablation config, checks
it against PyTorch on the same input, and times it under ONNX Runtime on CPU.
Eleven tests. One of them exports **all eight configs**: a config that cannot
leave the training harness is not deployable, and an ablation table comparing
one deployable model against seven undeployable ones is comparing things of
different kinds.

### The budget was being measured against a third of the work

PRD §16 sets **150 ms on server CPU**. `MFSTNet` deliberately does not own the
backbones (ADR-005) — they are frozen, they run once into the feature cache, and
keeping them out is what lets the ablation build eight configs without loading
45 M parameters eight times. So the exported graph takes **cached features**,
and 150 ms measured against it is a budget for the head alone.

A deployed server has no cache. Handed a 60-frame window it must run ResNet-50
and DINOv2 over all sixty frames before this graph can start, and that cost is
neither optional nor amortised. The CSV therefore carries `head_ms` **and**
`backbone_ms`, because reporting only the first satisfies the budget by leaving
out most of the work. ADR-003 already requires a latency figure to name its
measurement host; this requires it to name its **scope**.

The full A–H run with backbone timing is deliberately **not** recorded yet: the
machine has a cache build on it, and a latency number taken under contention is
not a latency number.

### The gate is asserted, not assumed

A graph that dropped the gate would still serve predictions, still hit the
budget, and quietly remove the thing the architecture chapter is about. So
`exposes_gate` is a column, and a test pins it per config: G has one, H — the
linear probe — must not.

### Not done here

**INT8.** ADR-007 puts quantisation at export time, and that is right, but an
INT8 graph has to be calibrated on real feature windows and validated against
the fp32 one on the test split. Spot-checking it on random tensors would produce
a number and no evidence. This writes the fp32 graph that calibration starts
from.

### Also: three jobs did not crash

A cache build and two 500,000-step PPO runs all died at once, one of them with
`FatalTraCIError: Connection closed by SUMO`, and two with no traceback at all.
The wall clock moved from 10:48 to 18:06 across the gap. **The machine slept.**
A suspend drops a local TraCI socket exactly that way, and the missing
tracebacks are processes that never got to raise.

Worth recording because the first reading was a defect hunt — SUMO instability,
memory pressure, a bug that only appears after 38 minutes — and all of it would
have been chasing nothing. A 30,000-step surrogate run afterwards completed
cleanly and wrote its P47 sidecar. Long unattended runs on this machine need
sleep disabled, not code changes.
