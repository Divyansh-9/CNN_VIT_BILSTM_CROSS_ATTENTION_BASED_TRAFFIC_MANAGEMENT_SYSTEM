# Publication readiness — why this branch is not on GitHub yet, and what unblocks it

**Date:** 2026-10-16 · **Status:** blocked on project-owner decisions ·
**Nothing has been pushed.**

## The situation

| | |
|---|---|
| GitHub repository | `Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM`, **PUBLIC** |
| `origin/main` | `0c3d917` (2026-08-20), the last CI run |
| local branch | `feat/edge-deployment-and-evaluation-protocol`, **no upstream**, 130+ commits ahead |
| standing rule | no push or merge without the project owner's explicit approval |

**Pushing to a public repository publishes**, and once published, the material
may be cached or indexed even if it is deleted later.

## What blocks a push to the public repository

1. **Bellevue-derived material: 337 files** under
   `experiments/results/bellevue_pilot/`. They are counts, hand-count audits,
   per-window results, frozen models fitted on Bellevue counts, and the
   source's Drive file ids (`p105_files.json`). **The Bellevue licence is
   unresolved, recorded as "internal engineering only, not publishable"**
   (S63). Research availability does not imply redistribution rights. Only
   `scripts/fetch_bellevue.py` is already public.
2. **Frames from third-party videos.** `data/lanes*/…preview.jpg` are
   lane-placement previews rendered from source traffic videos. **19 are
   unpushed, and 18 are already public on `main`.** Publishing them
   republishes other people's footage. They also sit uneasily with the camera
   claim NFR-13 makes (no frame leaves the edge), even though these are
   development artefacts and not edge output.

The documentation also quotes aggregate Bellevue results (the changelog,
REPORT.md and this file). Whether aggregate statistics may be published under
the licence is part of the same owner decision.

## Options, for the project owner

| option | what happens | publishes Bellevue material? | effort |
|---|---|---|---|
| **A. Make the repository private, then push** the branch and open a **draft PR** to `main` | CI runs on the full history; collaborators keep access; nothing becomes public | no | minutes (a GitHub setting, which is the owner's action) |
| **B. Resolve the licence first** | the outreach drafts already exist (`OUTREACH-2026-10-15.md`); push once rights are confirmed | only if granted | depends on the replies |
| **C. Publish a sanitised public branch** (ADR-013: "the public demo is deliberately smaller") | a branch from `origin/main` carrying the current tree **minus** Bellevue-derived results and third-party frames, as one squashed commit; the full history stays private or local | no | about an hour; the Bellevue-reading tests would need to skip when their files are absent |
| **D. Also remove the 18 already-public previews** | a deletion commit removes them from `main`'s tip; removing them from **history** needs a force-push rewrite | — | a deletion is small; a rewrite is disruptive and the owner's call |

**Recommendation: A now** (private, push, draft PR, so CI checks everything),
**then B or C** for anything public, **and D's deletion commit**. A force-push
history rewrite only if the owner judges it necessary.

## CI is ready for whichever push happens

The branch's CI was audited before any push (P111). Run as is, the `fast` job
would have **failed at collection**. `tests/test_checkpoint_guard.py` imports
torch through `scripts/train_ppo.py`, and **47 of the 74 test files have never
run in CI**. Fixed:

- **`fast` job:** installs the pinned numpy, fastapi, pydantic and httpx, so
  the P104–P110 guards run instead of skipping. The two torch- and OpenCV-only
  files move to the `model` job.
- **`model` job:** gains `opencv-python-headless` and those two files.
- **New `dashboard` job:** `npm ci`, `npm test` (12) and `npm run build`.
- **Verified locally:** the `fast` command passes in a clean environment with
  exactly its install list (Python 3.14 locally; CI uses 3.12). The dashboard
  job's three commands pass from a clean `npm ci`. The `model` job can only
  be confirmed on the runner.
