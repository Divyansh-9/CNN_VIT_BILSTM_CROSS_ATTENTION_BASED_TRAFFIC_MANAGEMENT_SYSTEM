# ADR-013 — Artifact Hosting: GitHub for Code, Hugging Face for Use, Zenodo for Citation

| | |
|---|---|
| **Status** | Proposed · **rev 2** (free-tier survey widened; Finding 4 reversed) |
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

### Finding 4 — the full prototype *can* be hosted free, but not on a PaaS free tier

**Revised.** This section first concluded the prototype could not be hosted free at all. That was
wrong: it surveyed managed platforms and stopped. A permanently-free VM exists.

Hugging Face Spaces' free CPU tier is 2 vCPU / 16 GB RAM and **sleeps after 48 hours of inactivity**
— fine for a single-model demo, wrong for a five-service stack.

The wider survey, with the ₹0 constraint treated as binding rather than aspirational:

| Option | Genuinely free? | Verdict for this project |
|---|---|---|
| **Oracle Cloud Always Free** | Yes, no expiry, no card charge | **Best fit.** A real VM the whole stack fits on. See the caveats below |
| **GitHub Student Developer Pack** | Yes, with student verification | Bundles DigitalOcean and Azure credit — *time-limited*, so a fallback rather than the base |
| Hugging Face Spaces | Yes | Right for the reduced ONNX demo, wrong for the stack |
| Cloudflare Pages / Workers | Yes, generous, no sleep | **Right for the React dashboard.** Static build, free forever |
| Render / Railway / Fly | Partly | Services spin down; managed Postgres free tiers **expire**. See the trap below |
| Supabase / Neon (Postgres) | Yes | Free projects **pause when idle**. Same trap |
| Cloudflare Tunnel | Yes | Public URL onto the laptop. The viva fallback that cannot fail |

**Oracle's Always Free tier was silently halved.** The widely-cited 4 OCPU / 24 GB Ampere A1
allocation dropped to **2 OCPU / 12 GB on 15 June 2026**, with no blog post and no customer
notification. 2 OCPU / 12 GB still comfortably runs Mosquitto, FastAPI, Postgres and a static React
build. Two caveats that decide whether to rely on it: ARM capacity is frequently **"Out of Capacity"**
in popular regions, and idle Always Free accounts can be reclaimed. So it is provisioned **early**,
kept warm, and is never the only plan.

**The free-tier trap that actually costs marks.** Platforms whose free databases *expire* or *pause
when idle* fail in a specific, predictable way: the demo works while you build it in October,
nobody touches it for three weeks, and it is dead the week of the submission. A tier that sleeps is
not free — it is deferred breakage timed for the worst possible moment. This rules out managed free
Postgres as the prototype's database of record.

The [FEASIBILITY-AUDIT](../FEASIBILITY-AUDIT.md) finding still stands independently: the production
stack consumes a quarter of the project for almost no assessed value. Hosting being free does not
make it worth the hours. **Free removes the cost objection, not the effort objection.**

### Finding 5 — publishing the dataset is a legal question, not only a hosting one

India's DPDP Rules were **notified on 13 November 2025**, with full enforcement and Schedule 1
penalties effective **13 May 2027** — inside this project's publication window.

Street footage of an Indian intersection contains identifiable faces and number plates. NFR-13
already forbids transmitting raw frames *at runtime*; it says nothing about **publishing a dataset**,
which is a different act and the one that carries the exposure.

This ADR does not attempt a legal conclusion — nobody here is qualified to give one. It records the
engineering response that removes the question.

### Finding 6 — the training platform default is wrong, and the better one is also free

Not hosting, but the same question and it was settled from the same untested assumption. The manual
names Google Colab T4 as the training platform.

| | Kaggle Notebooks | Colab free |
|---|---|---|
| Weekly GPU quota | **~30 h, published** | 15–30 h, **not published**, shifts with demand |
| Hardware | P100, or **2× T4** | T4 when available; can drop to CPU at peak |
| Session length | up to 12 h | up to 12 h, disconnects after ~90 min idle |
| Credit card | not required | not required |

For a **60–90 hour ablation**, a published quota and two T4s beat an undisclosed allocation that can
silently degrade to CPU mid-run. Kaggle becomes the primary; Colab stays as overflow. Both are free,
so this costs nothing but a changed default.

This matters less than it looks, because ADR-005's feature cache already collapses the ablation from
60–90 hours to hours — but the arithmetic should be right before it is relied on.

## Decision

**Code stays on GitHub. Weights go to Hugging Face. Citation goes to Zenodo. The public demo is
deliberately smaller than the prototype.**

| Artifact | Primary | Mirror / archive | Rationale |
|---|---|---|---|
| Code | GitHub | Zenodo at submission (via the GitHub–Zenodo hook) | CI lives here; the DOI snapshots the exact commit |
| Model weights | **Hugging Face model repo** | GitHub **Release asset**, not LFS | no size ceiling in practice, versioned, model card |
| IndiaTrafficNet | **Hugging Face dataset repo** | **Zenodo record** with DOI | HF for use, Zenodo for the citation and permanence |
| Public demo | **HF Space**, ONNX MFSTNet only | — | free, always-on URL, no card |
| Dashboard (static) | **Cloudflare Pages** | — | free forever, no sleep |
| Full prototype | **Oracle Always Free VM** | **laptop + Cloudflare Tunnel** | free with no expiry; the tunnel is the fallback that cannot fail |
| Training compute | **Kaggle** (30 h/week, published) | Colab free | see Finding 6 |
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

**Everything here is ₹0.** No option in this ADR requires a card charge, and none has an expiry
date. Time-limited student credit (DigitalOcean, Azure, via the GitHub Student Developer Pack) is
deliberately *not* load-bearing — it is a fallback, because a credit that runs out in month nine of a
twenty-week project is a scheduled outage.

**Provision early, not at integration.** The Oracle VM is claimed in Week 5, not Week 17, for two
reasons: ARM capacity is often unavailable and may take several attempts, and an idle Always Free
account can be reclaimed. A VM that exists and is kept warm costs nothing; one that must be obtained
during integration week is a risk with a deadline attached.

**Blocked on.** Faculty guide sign-off for the publication option (P10). Everything else in this ADR
can proceed immediately, since none of it requires collected data.

## Sources

- [Git LFS billing — GitHub Docs](https://docs.github.com/billing/managing-billing-for-git-large-file-storage/about-billing-for-git-large-file-storage)
- [LFS metered billing FAQ — GitHub community discussion](https://github.com/orgs/community/discussions/61362)
- [Storage limits — Hugging Face Hub](https://huggingface.co/docs/hub/en/storage-limits)
- [Spaces overview — Hugging Face](https://huggingface.co/docs/hub/en/spaces-overview)
- [Size limitations — Zenodo support](https://support.zenodo.org/help/en-gb/1-upload-deposit/80-what-are-the-size-limitations-of-zenodo)
- [DPDP Rules 2025 notified — PIB](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf)
- [Oracle quietly halves free-tier Ampere A1 limits — InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- [Oracle Cloud free tier 2026 changes — TerminalBytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/)
- [Colab vs Kaggle free GPU — Clusy](https://www.clusy.io/compare/colab-vs-kaggle)
