"""Check the status board against what is actually on disk (P46).

    python scripts/check_build_log.py

`BUILD-LOG.md` carries a step table per phase, and it has now gone stale twice.
The first time, S18b in that same file recorded the cost:

> The status board said Phase 3, step S18. The board was eight days stale ...
> **A reader would have concluded the project was stalled in Phase 3. It was
> not.**

It happened again. S32, S33 and S34 read as not-started while the SUMO network,
the heterogeneous vehicle types and a committed 30-seed baseline benchmark were
all sitting in the repository.

A board is only worth reading if it is checked, so this checks it. Each step
with an inspectable output declares what that output is, and the script reports
two kinds of drift:

* **understated** — marked not-started, but its artifact exists. This is the one
  that makes a project look stalled when it is not.
* **overstated** — marked done, but its artifact is missing. This is the one
  that makes a project look finished when it is not, which is worse.

Steps whose completion is not a file — a walkthrough meeting, a recording
session needing institutional permission — declare no artifact and are skipped
rather than guessed at. Exits 1 on any drift, so it can gate a commit.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DONE, NOT_STARTED, PARTIAL = "✅", "⬜", "🟨"


def rows_with(path: Path, minimum: int = 1) -> bool:
    """A CSV counts as an artifact only if it has data rows, not just a header."""
    if not path.is_file():
        return False
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle)) >= minimum


def files_matching(pattern: str, minimum: int = 1) -> bool:
    return len(list(ROOT.glob(pattern))) >= minimum


# What each step produces, where that is a thing a machine can look at.
# A step absent from this map is not checked — see the module docstring.
ARTIFACTS: dict[str, tuple[str, callable]] = {
    "S23": ("mfstnet/encoders.py", lambda: (ROOT / "mfstnet" / "encoders.py").is_file()),
    "S24": ("mfstnet/fusion.py", lambda: (ROOT / "mfstnet" / "fusion.py").is_file()),
    "S25": ("mfstnet/temporal.py", lambda: (ROOT / "mfstnet" / "temporal.py").is_file()),
    "S26": ("experiments/results/overfit_check.csv",
            lambda: rows_with(ROOT / "experiments" / "results" / "overfit_check.csv", 8)),
    "S27": ("mfstnet/cache.py", lambda: (ROOT / "mfstnet" / "cache.py").is_file()),
    "S27b": ("data/lanes_reviewed/*.json",
             lambda: files_matching("data/lanes_reviewed/*.json", 12)),
    "S28": ("experiments/results/ablation.csv",
            lambda: rows_with(ROOT / "experiments" / "results" / "ablation.csv")),
    "S32": ("simulation/networks/intersection.net.xml",
            lambda: (ROOT / "simulation" / "networks" / "intersection.net.xml").is_file()),
    "S33": ("simulation/networks/vtypes.add.xml",
            lambda: (ROOT / "simulation" / "networks" / "vtypes.add.xml").is_file()),
    "S34": ("experiments/results/benchmark_runs.csv (>=30 rows)",
            lambda: rows_with(ROOT / "experiments" / "results" / "benchmark_runs.csv", 30)),
    "S35": ("experiments/results/webster_sweep.csv",
            lambda: rows_with(ROOT / "experiments" / "results" / "webster_sweep.csv")),
    "S36": ("simulation/envs/traffic_env.py",
            lambda: (ROOT / "simulation" / "envs" / "traffic_env.py").is_file()),
    "S37": ("models/ppo/*.zip", lambda: files_matching("models/ppo/*.zip")),
    "S38": ("experiments/results/benchmark_stats.csv",
            lambda: rows_with(ROOT / "experiments" / "results" / "benchmark_stats.csv")),
    "S31": ("models/*.onnx", lambda: files_matching("models/**/*.onnx")),
}


def parse_board(path: Path) -> list[tuple[str, str, str]]:
    text = path.read_text(encoding="utf-8")
    return [(step, desc.strip(), status.strip())
            for step, desc, status
            in re.findall(r"^\| (S\d+[a-z]?) \| ([^|]+?) \| ([^|]+?) \|", text, re.M)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--board", type=Path, default=ROOT / "BUILD-LOG.md")
    args = parser.parse_args(argv)

    board = parse_board(args.board)
    checkable = [(s, d, st) for s, d, st in board if s in ARTIFACTS]
    print(f"  {len(board)} steps on the board, {len(checkable)} with an "
          f"inspectable artifact\n")

    understated, overstated = [], []
    for step, desc, status in checkable:
        where, exists = ARTIFACTS[step]
        present = exists()
        if status == NOT_STARTED and present:
            understated.append((step, desc, where))
        elif status == DONE and not present:
            overstated.append((step, desc, where))

    if understated:
        print(f"  UNDERSTATED — marked {NOT_STARTED} but the artifact exists:")
        for step, desc, where in understated:
            print(f"    {step:<6}{desc[:44]:<46}{where}")
        print("    A board that hides finished work makes a project read as "
              "stalled.\n")

    if overstated:
        print(f"  OVERSTATED — marked {DONE} but the artifact is missing:")
        for step, desc, where in overstated:
            print(f"    {step:<6}{desc[:44]:<46}{where}")
        print("    This is the worse direction: it makes unfinished work read "
              "as done.\n")

    if not understated and not overstated:
        print("  every checkable step agrees with the filesystem")
        return 0

    print(f"  {len(understated)} understated, {len(overstated)} overstated")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
