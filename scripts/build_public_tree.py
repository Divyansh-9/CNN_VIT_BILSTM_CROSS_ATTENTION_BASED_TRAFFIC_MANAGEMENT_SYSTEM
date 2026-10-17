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
)
REVIEW_MARKERS = (b"Bellevue", b"bellevue")
REVIEW_PREFIXES = ("experiments/results/loco", "experiments/results/baselines_loco")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".csv", ".txt", ".jsx", ".js", ".html"}


def excluded(path: str) -> str | None:
    """The reason `path` must not be public, or None."""
    for pattern, reason in EXCLUDE:
        if fnmatch.fnmatch(path, pattern):
            return reason
    return None


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
            review.append({"path": path, "why": why})
    leaks = [str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*")
             if p.is_file() and excluded(str(p.relative_to(out)).replace("\\", "/"))]
    manifest = {"what": "sanitised public tree, built locally from git HEAD; NOT published",
                "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                         capture_output=True, text=True).stdout.strip(),
                "kept": len(kept), "excluded": dropped, "review_required": review,
                "leaks_found_on_rescan": leaks, "passed": not leaks,
                "note": "does not resolve licensing or authorise publication"}
    (out / "PUBLIC_TREE_MANIFEST.json").write_text(json.dumps(manifest, indent=1),
                                                   encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true",
                        help="run CI's fast suite inside the built tree")
    args = parser.parse_args(argv)
    manifest = build(head_files(), args.out)
    print(f"  kept {manifest['kept']}, excluded {len(manifest['excluded'])}, "
          f"flagged for review {len(manifest['review_required'])}, "
          f"rescan leaks {len(manifest['leaks_found_on_rescan'])}")
    if not manifest["passed"]:
        return 1
    if args.run_tests:
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
