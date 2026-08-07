# Experiment Record — EXP-NNN

> **Write this when the run starts, not after it finishes.** A record reconstructed afterwards is
> missing exactly the fields that turn a surprising result into a finding.

## Identity

| Field | Value |
|---|---|
| Run ID | EXP-NNN |
| Date started | YYYY-MM-DD HH:MM |
| Owner | |
| Purpose | One sentence: what question does this run answer? |

## Configuration — reproducibility (NFR-07, NFR-08)

| Field | Value |
|---|---|
| Config file | `mfstnet/configs/____.yaml` |
| Git commit | `____` (the code that ran, not the current HEAD) |
| Seed | 42 |
| **Detector weights** | `bootstrap_v0` / `indiatrafficnet_v1` — **mandatory** (ADR-001; two sets exist W2–W8) |
| Dataset / corpus version | |
| Hardware | Colab T4 / laptop CPU / ____ — **required for any latency figure** (NFR §2.2) |
| Environment | `requirements.txt` at the commit above |

## Hypothesis

**Expected:** what you think will happen, and why.

**Would falsify it:** what result would show the expectation was wrong.

## Results

| Metric | Value |
|---|---|
| | |

| Artifact | Path |
|---|---|
| Raw results CSV | `experiments/results/____.csv` |
| Checkpoint | |
| TensorBoard / MLflow run | |

## Analysis

**What happened:**

**Versus expectation:** matched / partially / contradicted —

**Why (evidence, not speculation):**

**Follow-up:**

## Status

- [ ] Raw CSV committed (NFR-09 / NFR-10)
- [ ] Config and commit recorded above
- [ ] Result reported honestly, including if negative (BR-19)
- [ ] Relevant RTM row updated

> A run whose result you dislike is still a result. PRD §2.5.5: a covered-up negative result is a
> failed project.
