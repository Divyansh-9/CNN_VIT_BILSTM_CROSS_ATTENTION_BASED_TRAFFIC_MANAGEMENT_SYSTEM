"""How far the forecasting corpus is from being enough, and what would close it.

ADR-024 withdrew the graded lane-discipline sweep, which leaves one question
deciding where the next block of effort goes: **is the corpus the bottleneck,
and is there a route to more of it?** This answers the first half with
arithmetic rather than impression, and states what the second half would cost.

    python scripts/corpus_gap.py

Reads the committed corpus and `data/cameras.json`; writes nothing. The point
is that "we need more data" is not a plan until it is a number of
camera-hours, and that number is derivable from the window geometry the corpus
manifest already fixes.

**The arithmetic, and why overlapping windows are not independent samples.** A
window spans `T * step_s` seconds of footage and the next one starts
`stride_s` later, so a clip of duration *d* yields about
`(d - T*step_s) / stride_s` windows per lane. With `stride_s` shorter than the
span, consecutive windows share most of their frames: they inflate the count
and not the information. The honest denominators are therefore reported
separately — windows, independent clip-spans, and cameras — because the
effective sample size for a leave-one-camera-out protocol is the last of them.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"

#: Cameras contributing at least this many windows are fold-eligible under
#: ADR-019. Stated here because the gap is measured against folds, not windows.
MIN_WINDOWS_PER_FOLD = 10


def windows_per_hour(manifest: dict) -> float:
    """Lane-windows one fixed camera yields per hour of continuous footage."""
    span_s = manifest["T"] * manifest["step_s"]
    return max(0.0, (3600 - span_s) / manifest["stride_s"])


def main() -> int:
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    with (CORPUS / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    span_s = manifest["T"] * manifest["step_s"]
    overlap = max(0.0, (span_s - manifest["stride_s"]) / span_s)
    per_hour = windows_per_hour(manifest)

    by_clip = Counter(row["clip_id"] for row in rows)
    by_split = Counter(row["split"] for row in rows)
    eligible = {clip: n for clip, n in by_clip.items()
                if n >= MIN_WINDOWS_PER_FOLD}

    print(f"\n  window geometry  ·  T={manifest['T']} × step {manifest['step_s']} s "
          f"= {span_s} s span, stride {manifest['stride_s']} s")
    print(f"  consecutive windows share {overlap:.0%} of their footage, so a "
          f"window is not an independent observation")
    print(f"  one hour of one fixed camera yields about {per_hour:.0f} "
          f"lane-windows\n")

    print(f"  corpus today      {len(rows)} windows across {len(by_clip)} clips")
    print(f"    splits          " + "  ".join(
        f"{name} {count}" for name, count in sorted(by_split.items())))
    print(f"    fold-eligible   {len(eligible)} clips at "
          f"≥{MIN_WINDOWS_PER_FOLD} windows "
          f"({', '.join(f'{c}:{n}' for c, n in sorted(eligible.items(), key=lambda kv: -kv[1]))})")
    footage_h = len(rows) * manifest["stride_s"] / 3600
    print(f"    implied footage  about {footage_h:.2f} h of distinct "
          f"camera-time\n")

    print("  what a target would cost, at that yield:\n")
    print(f"    {'target windows':>15}  {'camera-hours':>12}  "
          f"{'at 8 cameras':>14}")
    for target in (500, 1000, 2000, 5000):
        hours = target / per_hour
        print(f"    {target:>15}  {hours:>12.1f}  {hours / 8:>11.1f} h each")

    print(f"\n  The binding constraint is not the window count. ADR-019 scores "
          f"by\n  leave-one-camera-out, so the effective sample size is the "
          f"{len(eligible)} fold-eligible\n  cameras — and no amount of extra "
          f"footage from those same cameras raises it.")
    print(f"  More hours deepen each fold; more cameras add folds. Only the "
          f"second\n  widens what the result can claim.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
