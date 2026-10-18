"""V3-4 — build a sanitised public copy of the repository, locally. Never pushes.

    python scripts/build_public_tree.py --out <empty dir>
    python scripts/build_public_tree.py --out <dir> --run-tests     # also run the fast suite there

**The source is `git archive HEAD`:** committed content only. Uncommitted edits
and untracked files can never enter the copy.

**Excluded, each with its reason, all recorded in the manifest:**

| rule | why |
|---|---|
| `experiments/results/bellevue_pilot/**` | Bellevue-derived results and models; licence unresolved (S63) |
| `experiments/results/v1/v1_sample_manifest.json` | Bellevue clip ids and timestamps |
| `data/corpus/{counts,detections,sequences}.csv` | per-frame counts and detections derived from third-party footage; 9 of 9 cameras unreleasable (`check_claims`, `releasable`) |
| any image or video under `data/` | frames from third-party footage (PUBLICATION-READINESS, problem 2) |
| `docs/demo/MFSTNet-*` (docx, pptx, pdf) | the submitted synopsis documents: personal identity, hands-off, publication is the owner's call |

**Flagged for the owner's review, not excluded.** Text files that **mention**
Bellevue (aggregate numbers quoted in documents), and result files derived
from the corpus cameras. Whether aggregates may be published is part of the
licence decision; a script cannot decide it.

**Verified.** After building, the tree is re-scanned. Any excluded pattern
present fails the build, with exit code 1.

**This does not resolve licensing or authorise publication.** Nothing is
pushed.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

EXCLUDE = (
    ("experiments/results/bellevue_pilot/*", "Bellevue-derived; licence unresolved (S63)"),
    ("experiments/results/v1/v1_sample_manifest.json", "Bellevue clip ids and timestamps"),
    ("data/corpus/counts.csv", "derived from third-party footage; cameras unreleasable"),
    ("data/corpus/detections.csv", "derived from third-party footage; cameras unreleasable"),
    ("data/corpus/sequences.csv", "derived from third-party footage; cameras unreleasable"),
    ("data/*.jpg", "third-party frame"), ("data/*.jpeg", "third-party frame"),
    ("data/*.png", "third-party frame"), ("data/*.webp", "third-party frame"),
    ("data/*.mp4", "third-party video"),
    ("docs/demo/MFSTNet-*", "submitted synopsis documents: personal identity; owner's call"),
) + tuple((p, "submitted-document toolchain: holds personal identity (names, roll numbers); "
              "hands-off; owner's call") for p in (
    "scripts/synopsis_content.py", "scripts/synopsis_phase1_content.py",
    "scripts/phase1_progress_content.py", "scripts/build_synopsis*.py",
    "scripts/build_phase1_progress_*.py", "scripts/check_synopsis.py",
    "scripts/check_progress_report.py", "scripts/build_review_pptx.py", "scripts/docx_writer.py",
    "tests/test_deck_geometry.py", "tests/test_progress_report.py"))
# P136: the owner's disposition of the review list. Corpus-derived results and
# the Bellevue pipeline scripts stay out of the public copy until their terms
# are reviewed. Core code that only names a restricted path cannot be left out
# without breaking the public build, so it stays in and is flagged for
# file-level review instead, as are the records that quote aggregates.
EXCLUDE = EXCLUDE + tuple((p, "owner disposition (P136): corpus-derived results, excluded until "
                              "the dataset terms are reviewed") for p in (
    "experiments/results/loco/*", "experiments/results/baselines_loco/*",
    "experiments/results/loco_foreign/*")) + tuple(
    (p, "owner disposition (P136): Bellevue pipeline script, excluded pending a file-level "
        "rights review") for p in (
    "scripts/p9[0-9]_*.py", "scripts/p9[0-9]b_*.py", "scripts/p10[0-9]_*.py",
    "scripts/fetch_bellevue.py", "scripts/count_audit_page.py", "scripts/compare_audit*.py",
    "scripts/c1_freeze.py", "scripts/c1L_freeze.py", "scripts/persistence_freeze.py",
    "scripts/detector_benchmark.py", "scripts/horizon_eval.py", "scripts/rehorizon_corpus.py",
    "scripts/sustained_corpus.py", "scripts/target_diagnostic.py",
    "scripts/v1_label_page.py", "scripts/v1_target_fidelity.py", "scripts/v1_sample.py",
    "scripts/v1_pilot_agreement.py", "tests/test_v1.py",
    "tests/test_rehorizon_corpus.py", "tests/test_sustained_corpus.py"))
CORE_REVIEW = {"server/app.py", "simulation/count_forecasts.py", "scripts/build_public_tree.py",
               "data/cameras.json", "tests/test_count_forecast.py",
               "tests/test_dashboard_evidence.py", "tests/test_faw.py",
               "tests/test_persistence_forecaster.py", "tests/test_public_tree.py"}
RECORD_REVIEW = {"BUILD-LOG.md", "docs/00-planning/PRD-CHANGELOG.md",
                 "docs/00-planning/PUBLICATION-READINESS.md"}

PUBLIC_BRANCH_TODO = ("remove the synopsis and progress-report build and check steps from "
                      ".github/workflows/tests.yml in the public branch (their scripts are excluded)")
REVIEW_MARKERS = (b"Bellevue", b"bellevue")
REVIEW_PREFIXES = ("experiments/results/loco", "experiments/results/baselines_loco")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".csv", ".txt", ".jsx", ".js", ".html"}


def excluded(path: str) -> str | None:
    """The reason `path` must not be public, or None."""
    for pattern, reason in EXCLUDE:
        if fnmatch.fnmatch(path, pattern):
            return reason
    return None


import re as _re

AGGREGATE = _re.compile(rb"(?i)(bellevue|P9[5-9]|P10[0-9]|P11[0-9]).{0,200}?\b\d+\.\d{2,4}\b")
LICENCE = _re.compile(rb"(?i)bellevue.{0,300}?(licen[cs]|redistribut|permission|copyright|terms of use)"
                      rb"|(licen[cs]|redistribut|permission|copyright).{0,300}?bellevue")
DATASET = _re.compile(rb"(?i)(_bellevue|bellevue_pilot|fetch_bellevue|corpus_p10[0-9]|drive_id)")


def disposition(path: str, category: str) -> str:
    """The owner's preliminary disposition for a kept, flagged file (P136). Not a clearance."""
    if path in CORE_REVIEW:
        return "kept: core code naming a restricted path; file-level review"
    if path in RECORD_REVIEW:
        return "kept: project record quoting aggregates; redaction review before any release"
    return {"licence reference": "review individually; generic citations may be publishable",
            "aggregate results": "review individually for disclosure restrictions",
            "mention only": "likely retain if no restricted data or unsupported claim",
            "dataset-specific material": "kept pending a file-level rights review",
            }.get(category, "review")


def review_category(path: str, content: bytes) -> str:
    """A first-pass category for the owner's review (P135). Not a legal judgement.

    The order is restrictive first: dataset-specific material, then corpus-derived
    results, then licence references, then aggregate results, then mention only.
    """
    if "bellevue" in path.lower() or DATASET.search(content):
        return "dataset-specific material"
    if path.startswith(REVIEW_PREFIXES):
        return "corpus-derived results"
    if LICENCE.search(content):
        return "licence reference"
    if AGGREGATE.search(content):
        return "aggregate results"
    return "mention only"


def needs_review(path: str, content: bytes) -> str | None:
    if path.startswith(REVIEW_PREFIXES):
        return "derived from corpus cameras whose licences are unresolved"
    if Path(path).suffix in TEXT_SUFFIXES and any(m in content for m in REVIEW_MARKERS):
        return "mentions Bellevue (quoted aggregates?)"
    return None


def head_files() -> list[tuple[str, bytes]]:
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"],
                             capture_output=True, check=True).stdout
    out = []
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                out.append((member.name, tar.extractfile(member).read()))
    return out


def build(files: list[tuple[str, bytes]], out: Path) -> dict:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; build into an empty directory")
    kept, dropped, review = [], [], []
    for path, content in files:
        reason = excluded(path)
        if reason:
            dropped.append({"path": path, "reason": reason})
            continue
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        kept.append(path)
        why = needs_review(path, content)
        if why:
            category = review_category(path, content)
            review.append({"path": path, "why": why, "category": category,
                           "disposition": disposition(path, category)})
    leaks = [str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*")
             if p.is_file() and excluded(str(p.relative_to(out)).replace("\\", "/"))]
    manifest = {"what": "sanitised public tree, built locally from git HEAD; NOT published",
                "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                         capture_output=True, text=True).stdout.strip(),
                "kept": len(kept), "excluded": dropped, "review_required": review,
                "leaks_found_on_rescan": leaks, "passed": not leaks,
                "public_branch_todo": [PUBLIC_BRANCH_TODO],
                "review_by_category": {c: sum(r["category"] == c for r in review)
                                       for c in sorted({r["category"] for r in review})},
                "note": "does not resolve licensing or authorise publication"}
    (out / "PUBLIC_TREE_MANIFEST.json").write_text(json.dumps(manifest, indent=1),
                                                   encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true",
                        help="run CI's fast suite inside the built tree")
    parser.add_argument("--review-report", type=Path,
                        help="also write the review list (path, category, why) as CSV, plus the "
                             "frames already public on origin/main")
    args = parser.parse_args(argv)
    manifest = build(head_files(), args.out)
    if args.review_report:
        import csv

        args.review_report.parent.mkdir(parents=True, exist_ok=True)
        with args.review_report.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["category", "disposition", "path", "why"])
            writer.writeheader()
            for r in sorted(manifest["review_required"], key=lambda r: (r["category"], r["path"])):
                writer.writerow({k: r[k] for k in ("category", "disposition", "path", "why")})
        public = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/main"],
                                capture_output=True, text=True).stdout.splitlines()
        frames = [f for f in public if excluded(f) and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        args.review_report.with_name("already_public_frames.txt").write_text(
            "# third-party frames already public on origin/main (V3-5; removal is the owner's call)\n"
            + "\n".join(frames) + "\n", encoding="utf-8")
        print(f"  review by category: {manifest['review_by_category']}; "
              f"{len(frames)} frames already public")
    print(f"  kept {manifest['kept']}, excluded {len(manifest['excluded'])}, "
          f"flagged for review {len(manifest['review_required'])}, "
          f"rescan leaks {len(manifest['leaks_found_on_rescan'])}")
    if not manifest["passed"]:
        return 1
    if args.run_tests:
        # A published branch is a git repository, and some tests ask git; build
        # the single squashed commit the public branch would be.
        for command in (["git", "init", "-q"], ["git", "add", "-A"],
                        ["git", "-c", "user.name=public-tree", "-c", "user.email=public-tree@local",
                         "commit", "-q", "-m", "sanitised public tree (local, never pushed)"]):
            subprocess.run(command, cwd=args.out, check=True, capture_output=True)
        ignore = ["test_encoders.py", "test_model.py", "test_cache.py", "test_sumo_network.py",
                  "test_simulation.py", "test_checkpoint_guard.py", "test_video_sampling.py"]
        result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "-p",
                                 "no:cacheprovider", *[f"--ignore=tests/{n}" for n in ignore]],
                                cwd=args.out)
        print(f"  fast suite in the public tree: exit {result.returncode}")
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
