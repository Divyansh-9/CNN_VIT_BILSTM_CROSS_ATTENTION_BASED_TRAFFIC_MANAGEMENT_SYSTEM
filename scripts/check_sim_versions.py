"""Fail fast if the simulation stack is not the one the committed results came from (P137).

    python scripts/check_sim_versions.py

Every committed SUMO and PPO result was produced with the versions pinned in
`requirements.txt`. An unpinned CI install once drew SUMO 1.28.0, and a
committed Webster episode then re-ran to 29.499 s instead of 28.814 s. This
check reads the pins from `requirements.txt` (one source), compares the
installed versions, and exits 1 on any mismatch, naming each package. It runs
in CI before the simulation suites, so environment drift is an explicit
failure, not a puzzling one.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

PACKAGES = ("eclipse-sumo", "traci", "sumolib", "gymnasium", "stable-baselines3")
REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def pins(text: str) -> dict[str, str]:
    """`name==version` lines from a requirements file, names lower-cased."""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            out[name.strip().lower().replace("_", "-")] = version.strip()
    return out


def mismatches(pinned: dict[str, str], installed) -> list[str]:
    problems = []
    for package in PACKAGES:
        want = pinned.get(package)
        if want is None:
            problems.append(f"{package}: not pinned in requirements.txt")
            continue
        try:
            got = installed(package)
        except metadata.PackageNotFoundError:
            problems.append(f"{package}: not installed (requirements.txt pins {want})")
            continue
        if got != want:
            problems.append(f"{package}: installed {got}, requirements.txt pins {want}")
    return problems


def main() -> int:
    pinned = pins(REQUIREMENTS.read_text(encoding="utf-8"))
    problems = mismatches(pinned, metadata.version)
    for package in PACKAGES:
        print(f"  {package:18} pinned {pinned.get(package, '-')}")
    if problems:
        for p in problems:
            print(f"  MISMATCH  {p}")
        return 1
    print("  simulation stack matches requirements.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
