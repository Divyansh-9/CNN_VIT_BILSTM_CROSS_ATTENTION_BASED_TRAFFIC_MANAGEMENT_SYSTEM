"""Record the commit behind every committed result file, for a container (D15).

    python deploy/evidence_commits.py --git-dir .git --out evidence_commits.json

Run while the server image is built, where the repository history exists. The
server reads the map through `STMS_EVIDENCE_COMMITS` only when `git log` cannot
answer, so the dashboard names the real commit and date (ADR-014) instead of
"uncommitted". The answers are git's own, never typed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git(git_dir: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "safe.directory=*", f"--git-dir={git_dir}", *args],
                          capture_output=True, text=True, check=True).stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--git-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--under", default="experiments/results")
    args = ap.parse_args(argv)
    commits = {}
    for path in git(args.git_dir, "ls-tree", "-r", "--name-only", "HEAD", "--", args.under).split():
        out = git(args.git_dir, "log", "-1", "--format=%h %cs", "HEAD", "--", path).split()
        if len(out) == 2:
            commits[path] = {"commit": out[0], "date": out[1]}
    if not commits:
        print(f"no committed files under {args.under}: is the history shallow?")
        return 1
    args.out.write_text(json.dumps(commits, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(commits)} files mapped to their last commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
