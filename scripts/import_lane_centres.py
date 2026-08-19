"""Turn the placement page's JSON into reviewed per-camera lane files.

    python scripts/import_lane_centres.py --json lane_centres.json --out data/lanes_reviewed

`docs/demo/place_lanes.html` emits one object per camera with the centres a
person clicked. This validates them and writes the per-camera files
`build_corpus.py` consumes, with `reviewed: true` — the only place that flag is
ever set, because it means a human looked.

**Why an import step rather than writing the files from the page.** A browser
page cannot be trusted to produce well-formed corpus inputs, and the checks
below are the ones that matter:

* **Two centres minimum.** One lane is not an intersection, and the per-lane
  congestion head (PRD §8.1) needs more than one approach to predict.
* **Centres inside the frame**, in normalised coordinates. A page bug emitting
  pixels would otherwise produce a lane nothing ever reaches.
* **Centres far enough apart.** Two clicks a few pixels apart split a road
  arbitrarily; the assignment would be disjoint and meaningless.
* **Every camera accounted for.** A camera silently missing from the JSON is a
  camera silently dropped from the corpus.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIN_SEPARATION = 0.05


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, required=True,
                        help="saved or pasted from docs/demo/place_lanes.html")
    parser.add_argument("--surveyed", type=Path, default=Path("data/lanes_itd"),
                        help="the automatic survey, for clip paths and detection counts")
    parser.add_argument("--out", type=Path, default=Path("data/lanes_reviewed"))
    parser.add_argument("--max-radius", type=float, default=0.25)
    parser.add_argument("--min-separation", type=float, default=MIN_SEPARATION)
    args = parser.parse_args(argv)

    from mfstnet.corpus.lanes import LaneCentres

    placed = json.loads(args.json.read_text(encoding="utf-8"))
    if not isinstance(placed, list) or not placed:
        raise SystemExit(f"{args.json} is not a non-empty list of cameras")

    surveyed = {}
    for path in args.surveyed.glob("*.json"):
        if path.name == "survey_summary.json":
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        surveyed[spec.get("clip")] = spec

    args.out.mkdir(parents=True, exist_ok=True)
    written, problems = 0, []
    print(f"  {len(placed)} camera(s) in {args.json.name}\n")
    print("  {:<48}{:>7}{:>12}".format("clip", "lanes", "separation"))

    for entry in placed:
        clip = entry.get("clip")
        lanes = entry.get("lanes") or []
        if len(lanes) < 2:
            problems.append(f"{clip}: {len(lanes)} centre(s); an intersection needs 2+")
            continue

        # Left-to-right, so `lane_0` means the same thing on every camera and
        # click order does not leak into the data.
        centres = sorted((tuple(l["centre"]) for l in lanes), key=lambda c: c[0])
        names = tuple(f"lane_{i}" for i in range(len(centres)))

        closest = min(math.dist(a, b)
                      for i, a in enumerate(centres) for b in centres[i + 1:])
        if closest < args.min_separation:
            problems.append(
                f"{clip}: two centres are {closest:.3f} apart, under "
                f"{args.min_separation}. That splits one road arbitrarily.")
            continue

        try:
            resolved = LaneCentres(names=names, centres=tuple(centres),
                                   max_radius=args.max_radius)
        except ValueError as error:
            problems.append(f"{clip}: {error}")
            continue

        spec = surveyed.get(clip, {})
        stem = entry.get("camera") or clip
        (args.out / f"{stem}.json").write_text(json.dumps({
            "clip": clip,
            "surveyed_from": spec.get("surveyed_from", ""),
            "reviewed": True,
            "max_radius": resolved.max_radius,
            "lanes": [{"name": n, "centre": list(c)}
                      for n, c in zip(resolved.names, resolved.centres)],
            "note": ("Placed by hand over a detection-density heatmap. P23: "
                     "automatic centres moved 0.164 of frame width when the "
                     "detector changed, so they are not used unreviewed. "
                     "P17: these belong to THIS camera only."),
        }, indent=2), encoding="utf-8")
        written += 1
        print("  {:<48}{:>7}{:>12.3f}".format(clip[:46], len(centres), closest))

    missing = sorted(set(surveyed) - {e.get("clip") for e in placed})
    if missing:
        print(f"\n  NOT PLACED — {len(missing)} camera(s) surveyed but absent "
              f"from the JSON:")
        for clip in missing:
            print(f"    {clip[:70]}")
        print("  Each is silently dropped from the corpus unless that is intended.")

    if problems:
        print(f"\n  REJECTED {len(problems)}:")
        for problem in problems:
            print(f"    {problem}")

    print(f"\n  wrote {written} reviewed lane file(s) to {args.out}")
    if not written:
        raise SystemExit("nothing usable was imported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
