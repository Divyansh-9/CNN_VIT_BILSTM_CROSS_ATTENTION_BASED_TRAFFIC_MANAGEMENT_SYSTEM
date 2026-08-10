# Non-Functional Requirements Specification (NFR)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | NFR v1.0 |
| **Date** | 2026-08-07 |
| **Related** | [PRD §10](../00-planning/PRD.md) (requirement source) · [SRS](SRS.md) · [FRD](FRD.md) · [RTM](RTM.md) |

---

## 1. Purpose

PRD §10 states each non-functional target as a number. A number without a measurement procedure is
not verifiable — "≤150 ms" means different things depending on whether it is a mean or a median,
measured cold or warm, including or excluding preprocessing. This document fixes the procedure for
each, so that the figure reported in the paper is the figure the requirement asked for.

Requirement text is not restated; PRD §10 is authoritative.

---

## 2. Performance

| ID | Target | Measurement procedure | Method | TC | Owner |
|---|---|---|---|---|---|
| NFR-01 | YOLOv8 ≥10 fps @ 640×640 | Sustained over 60 s of continuous inference after a 10 s warm-up. Report **median and 5th percentile** fps, not mean — a mean hides periodic stalls. Record the measurement host | T | TC-N01 | R4 |
| NFR-02 | MFSTNet ≤150 ms, server CPU, ONNX | Median of 100 inferences after 10 warm-up runs. **Includes** preprocessing and postprocessing; excludes model load. Batch size as deployed | T | TC-N02 | R2 |
| NFR-03 | PPO decision ≤50 ms | Median of 1,000 `predict()` calls, `deterministic=True`, excluding environment step time | T | TC-N03 | R3 |
| NFR-04 | MQTT end-to-end ≤200 ms | Publish timestamp in payload; subscriber records receipt. **Requires clock sync** — run publisher and subscriber on one host for the baseline, and report cross-host separately using NTP-synced clocks | T | TC-N04 | R4 |
| NFR-05 | Dashboard refresh ≤2 s | Time from server publish to rendered DOM update, sampled 50 times over a 10-minute session | T | TC-N05 | R4 |
| NFR-06 | Uptime ≥95% over 4 h | Continuous run; downtime is any interval where the heartbeat topic is silent >30 s. Report total downtime and longest single outage | D | TC-N06 | R4 |

### 2.1 Composed latency budget

The end-to-end sensing-to-actuation path must be measured as a whole, not inferred by summing parts —
queueing between stages is not captured by per-stage medians.

```
frame captured
  → detection            (NFR-01: ≤100 ms/frame at 10 fps)
  → MQTT publish         (NFR-04: ≤200 ms)
  → MFSTNet inference    (NFR-02: ≤150 ms)
  → PPO decision         (NFR-03: ≤50 ms)
  → MQTT command         (NFR-04: ≤200 ms)
  → actuation
                          ─────────────────
             worst case ≈ 700 ms
```

PRD §20 L6 accepts up to 500 ms as immaterial against 10–90 s signal cycles. The composed worst case
exceeds that, so the **measured** round trip is reported in the STR, and L6's figure is amended if
measurement disagrees with it. Do not report the estimate as if it were a measurement.

### 2.2 Measurement host disclosure

Per PRD §15.4 and ADR-003, the edge node is a laptop rather than the Jetson deployment target.

**Every latency and throughput figure in every document, table, and paper states the host it was
measured on.** PRD §20 L8 declares the absence of on-target validation.

**The proxy is optimistic, not representative — say so.** The edge laptop carries an RTX 4050, which
vastly outperforms a Jetson Nano. Clearing ≥10 fps on it says nothing about Jetson feasibility.
Therefore report **two** figures for NFR-01:

| Figure | Label | What it evidences |
|---|---|---|
| RTX 4050, GPU inference | *Optimistic proxy* | That the pipeline runs in real time |
| Same laptop, **CPU-only** | *Conservative proxy* | A far better indicator for constrained edge hardware |

The second costs one extra run and is the number a reviewer will actually find persuasive. An
unlabelled GPU figure presented as evidence of edge viability does not survive one question.

### 2.3 Quantised models must be reported as quantised

If INT8 quantisation is used to meet NFR-02 (see
[ADR-007 §5](../00-planning/decisions/ADR-007-backbones-and-training-recipe.md)), the reported
**accuracy must come from the same quantised model that produced the reported latency.** Quoting fp32
accuracy alongside INT8 latency is a misreporting error, not a presentational shortcut.

---

## 3. Reproducibility

PRD §10 marks NFR-07 to NFR-10 **Critical**. They are graded deliverables (SOW §5.1) and the
evidential basis for BR-17, BR-18, and BR-19.

| ID | Target | Measurement procedure | Method | TC | Owner |
|---|---|---|---|---|---|
| NFR-07 | Seeds fixed and documented | A single `set_seed(42)` utility seeds Python `random`, NumPy, PyTorch (CPU and CUDA), and SB3, and sets `torch.backends.cudnn.deterministic`. Verification: two runs of the same config produce identical epoch-1 loss to 1e-6 | T | TC-N07 | R2 |
| NFR-08 | Code on GitHub with `requirements.txt` | Clean-machine reproduction: fresh clone, fresh environment, `pip install -r requirements.txt`, run one training config for 2 epochs without manual intervention. **Pinned versions, not ranges** | D | TC-N08 | All |
| NFR-09 | All 30-run RL raw results as CSV | `experiments/results/rl_runs.csv` tracked in git (explicitly un-ignored), ≥120 rows, one per seed per method. Every aggregate table in the paper recomputable from it by a committed script | I | TC-N09 | R3 |
| NFR-10 | Ablation raw results as CSV | `experiments/results/ablation.csv` tracked in git, all 7 configs present including those that did not help (BR-19) | I | TC-N10 | R2 |

### 3.1 Reproducibility as a working practice

These are not end-of-project chores. Retrofitting reproducibility in Week 19 fails, because the seeds
and configs of earlier runs no longer exist.

- The seeding utility is written **before** the first training run, not after.
- Every run writes an experiment record (template in `docs/templates/`) at the moment it starts.
- Result CSVs are appended by the training script itself, never transcribed by hand.
- Summary tables in the paper are generated from the CSVs by a committed script. A table typed by
  hand cannot be recomputed, and a table that cannot be recomputed is not evidence.

Docker Compose is committed for the server stack (broker, API, database, dashboard). It is not
required for training, which runs on Colab.

---

## 4. Security

| ID | Target | Measurement procedure | Method | TC | Owner |
|---|---|---|---|---|---|
| NFR-11 | MQTT username/password auth | Broker configured with `allow_anonymous false`. Verification: an unauthenticated connect attempt is **refused** | T | TC-N11 | R4 |
| NFR-12 | JWT login, 24 h expiry | Protected endpoint returns 401 without a token and after a token older than 24 h | T | TC-N12 | R4 |

Credentials come from environment variables, never from committed files. `.gitignore` excludes
`.env` and `secrets.yaml`. This is a demo system on a local network — the requirement is that
authentication exists and works, not that it withstands a determined attacker.

---

## 5. Privacy

| ID | Target | Measurement procedure | Method | TC | Owner |
|---|---|---|---|---|---|
| NFR-13 | Raw frames never transmitted or written to disk **by the deployed runtime** | Inspect every MQTT payload schema for image or image-encoded fields (none permitted). Inspect the edge runtime for any file write of frame data. Confirm only counts, class distributions, fps, and predictions cross the boundary | I | TC-N13 | R4 |

### 5.1 Scope boundary

Clarified by PRD amendment A6, because the original wording conflicted with the training corpus
introduced in §8.6.

| | Governed by NFR-13? | Handling |
|---|---|---|
| Deployed runtime frames | **Yes** | Never transmitted, never written. Derived counts only |
| Offline training corpus (PRD §8.6) | No | Retained locally, excluded by `.gitignore`, never published |
| IndiaTrafficNet published frames | No | Published deliberately under CC BY 4.0 (FR-D06) |

The published dataset warrants explicit care that PRD §12 does not currently require: faces and
licence plates are visible in street-level footage. Before public release, review a sample for
identifiable individuals, and state the collection and consent basis in the datasheet (FR-D07).
This is a reviewer question at any venue with an ethics statement, and it is easier to answer with a
documented review than with an assurance.

---

## 6. Constraints treated as non-functional

| ID | Constraint | Verification |
|---|---|---|
| NFR-14 | Total cash cost ₹0 for all Must-priority requirements | Inspection against PRD §24.4 BOM |
| NFR-15 | Every MFSTNet module disableable by config flag (ablation-ability) | All 7 configs A–G runnable from config alone, with no code edit between them |
| NFR-16 | Hyperparameters live in YAML, not in training scripts | Inspection: no numeric literal in a training script that also appears in a config file |

NFR-14 to NFR-16 are introduced by this document — they are real constraints the PRD implies but
never states as verifiable requirements. NFR-15 in particular is an architectural constraint that
governs how the model is written from the first commit; discovering in Week 13 that a module is
wired in unconditionally means rewriting it under deadline.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial NFR. Measurement procedures fixed for NFR-01..NFR-13; NFR-14..NFR-16 added |
