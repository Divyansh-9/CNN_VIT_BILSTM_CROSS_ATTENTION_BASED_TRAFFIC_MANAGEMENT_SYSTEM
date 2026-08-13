# ADR-013 — Artifact Hosting: GitHub for Code, Hugging Face for Use, Zenodo for Citation

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-08-13 |
| **Affects** | NFR-08 (reproducibility), NFR-13 (privacy), BR-18, M8; `.gitattributes` LFS configuration |
| **Related** | [ADR-001](ADR-001-two-track-dataset-strategy.md) (dataset) · [ADR-008](ADR-008-prototype-descoping.md) (proposed) · [ADR-014](ADR-014-dashboard-metrics-separation.md) |

## Context

Four artifacts need somewhere to live, and they have genuinely different requirements:

| Artifact | Size | Needs |
|---|---|---|
| Code | small | version control, CI — **already on GitHub** |
| Model weights | ~100–400 MB per checkpoint | versioned, fetchable by a training script, mirrorable |
| IndiaTrafficNet | 12,000+ frames | discoverable, citable, **and legally publishable** |
| A live demo | — | a URL that works during a viva and during review |

The repository already has Git LFS configured for weights. That configuration is worth
re-examining rather than inheriting.

### Finding 1 — the Git LFS objection is weaker than it used to be, but the bandwidth one is not

GitHub raised the included Git LFS allowance for Free and Pro accounts to **10 GB storage and 10 GB
bandwidth**, moving from pre-paid data packs to metered billing at roughly $0.07/GiB-month storage
and $0.0875/GiB bandwidth beyond that.

*This corrects a figure that was almost stated here from memory as 1 GB.* The distinction matters:
at 1 GB, LFS would have been unusable for this project; at 10 GB it is merely a poor fit.

The reason it remains a poor fit is **bandwidth, not storage**. LFS bandwidth is consumed on every
clone and every CI checkout that fetches objects. A four-person team, a laptop reinstall, and a CI
job that pulls weights will spend the monthly allowance far faster than the storage will fill — and
when bandwidth is exhausted the repository stops serving LFS objects, which reads to a teammate as a
broken clone rather than as a quota.

### Finding 2 — Hugging Face fits weights better than any general file host

No per-repository size limit for models and datasets, repositories up to ~300 GB supported without
asking, free public hosting, git-based versioning, and a model card that is a genuine research
artifact rather than a README. `from_pretrained`-style fetching means the training script names a
revision instead of a path.

For a paper, a model card and dataset card are also what a reviewer expects to find.

### Finding 3 — Hugging Face is not an archive, and a conference submission needs one

Zenodo accepts **up to 50 GB per record with a maximum of 100 files** (a one-time increase to 200 GB
is available on request), and mints a DOI. A DOI is what a paper cites and what survives an account
being deleted or renamed. Hugging Face offers neither guarantee.

These are not competitors. HF is where the artifact is *used*; Zenodo is where the artifact is
*cited*.

### Finding 4 — the full prototype will not run on any free tier, and should not be made to

Hugging Face Spaces' free CPU tier is 2 vCPU / 16 GB RAM and **sleeps after 48 hours of inactivity**.
The PRD §22 prototype is an edge node, an MQTT broker, FastAPI, PostgreSQL with TimescaleDB, and a
React dashboard. Fitting that onto a sleeping 2-vCPU container is weeks of work for zero assessed
marks, and the [FEASIBILITY-AUDIT](../FEASIBILITY-AUDIT.md) already finds the production stack
consumes a quarter of the project for almost no assessed value.

### Finding 5 — publishing the dataset is a legal question, not only a hosting one

India's DPDP Rules were **notified on 13 November 2025**, with full enforcement and Schedule 1
penalties effective **13 May 2027** — inside this project's publication window.

Street footage of an Indian intersection contains identifiable faces and number plates. NFR-13
already forbids transmitting raw frames *at runtime*; it says nothing about **publishing a dataset**,
which is a different act and the one that carries the exposure.

This ADR does not attempt a legal conclusion — nobody here is qualified to give one. It records the
engineering response that removes the question.

## Decision

**Code stays on GitHub. Weights go to Hugging Face. Citation goes to Zenodo. The public demo is
deliberately smaller than the prototype.**

| Artifact | Primary | Mirror / archive | Rationale |
|---|---|---|---|
| Code | GitHub | Zenodo at submission (via the GitHub–Zenodo hook) | CI lives here; the DOI snapshots the exact commit |
| Model weights | **Hugging Face model repo** | GitHub **Release asset**, not LFS | no size ceiling in practice, versioned, model card |
| IndiaTrafficNet | **Hugging Face dataset repo** | **Zenodo record** with DOI | HF for use, Zenodo for the citation and permanence |
| Public demo | **HF Space**, ONNX MFSTNet only | — | free, always-on URL, survives a sleeping container |
| Full prototype | **laptop + tunnel**, live during the viva | recorded walkthrough video | see Finding 4 |
| Result CSVs, figures | committed to git | — | small, and NFR-09 requires them reviewable in-repo |

### Git LFS is retired for weights

`.gitattributes` keeps LFS only for anything small and genuinely binary that must be versioned with
the code. Checkpoints are fetched from Hugging Face by name and revision. **A weights file must never
be the reason a clone fails.**

### What may be published from IndiaTrafficNet

Ordered by preference. The first that is achievable wins:

1. **Annotations plus a retrieval script.** YOLO-format labels, lane polygons, per-frame counts and
   the source manifest are published; frames are not. This is the standard practice several traffic
   datasets already follow, it removes the personal-data question entirely, and it is *sufficient for
   reproducing every number in the paper* because the corpus is auto-labelled from counts.
2. **Frames with faces and number plates blurred**, blurring applied before publication and the
   blurring script committed so the transformation is auditable.
3. **Nothing beyond derived statistics**, if the guide judges even blurred publication unwise.

**Raw unblurred frames are not published under any option.** The test split is human-verified (A9),
which means a person looked at those frames — that is a review step, not a licence to distribute.

The guide signs off on which option applies before any upload. Recorded as pending item **P10**.

## Consequences

**Good.** Cloning the repository never depends on a bandwidth quota. Weights are versioned where the
tooling expects them. The paper cites a DOI that will resolve in ten years. The demo has a URL that
does not require the laptop to be awake. The dataset publication question is answered before frames
are collected rather than after — which is the only time the cheap answer is still available.

**Bad.** Three hosting locations instead of one, and the training script gains a network dependency
on Hugging Face. Mitigated by pinning a revision hash, and by the GitHub Release mirror.

**Accepted risk.** Option 1 publishes no frames, which makes IndiaTrafficNet less useful to others
than a full image dataset would be. That is the correct trade: a narrower contribution that can be
published beats a broader one that cannot.

**Blocked on.** Faculty guide sign-off for the publication option (P10). Everything else in this ADR
can proceed immediately, since none of it requires collected data.

## Sources

- [Git LFS billing — GitHub Docs](https://docs.github.com/billing/managing-billing-for-git-large-file-storage/about-billing-for-git-large-file-storage)
- [LFS metered billing FAQ — GitHub community discussion](https://github.com/orgs/community/discussions/61362)
- [Storage limits — Hugging Face Hub](https://huggingface.co/docs/hub/en/storage-limits)
- [Spaces overview — Hugging Face](https://huggingface.co/docs/hub/en/spaces-overview)
- [Size limitations — Zenodo support](https://support.zenodo.org/help/en-gb/1-upload-deposit/80-what-are-the-size-limitations-of-zenodo)
- [DPDP Rules 2025 notified — PIB](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf)
