"""How much corpus the surveyed footage yields, per step size — the A28 evidence.

    python scripts/corpus_yield.py

A28 proposes `step_s=2` against the PRD's 5. The usual argument for it is that
it produces more sequences, and that argument is weak: consecutive windows
overlap heavily, so sequence count inflates freely without adding information.

This computes the number that does not inflate. Two things are reported per
step size:

* **independent segments** — non-overlapping windows, `duration // min_clip_s`.
  This is the honest sample count, and it is what a reviewer should be told.
* **cameras contributing at all** — a clip shorter than `min_clip_s` yields
  exactly zero (A15), so raising `step_s` silently deletes whole cameras.

The second is the real argument. Sequences from one camera are correlated;
cameras are the unit over which the model has to generalise, and a corpus that
drops from eleven cameras to seven has lost something a longer clip cannot
replace.

Duplicate cameras are collapsed first: M6 Motorway and "Road traffic video for
object recognition" are one viewpoint at 0.981 correlation (P22), and counting
both would overstate independent evidence by a whole camera.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

RESULTS = Path("experiments/results/corpus_yield.csv")
STEPS = (1, 2, 5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--survey", type=Path,
                        default=Path("data/lanes_itd/survey_summary.json"))
    parser.add_argument("--timesteps", type=int, default=60, help="T, PRD §8.2")
    parser.add_argument("--horizon-s", type=int, default=60, help="PRD §8.2")
    parser.add_argument("--stride-s", type=int, default=30)
    parser.add_argument("--max-unassigned", type=float, default=0.35,
                        help="P17's gate; a camera over it is rejected by "
                             "build_corpus and contributes nothing")
    parser.add_argument("--min-density", type=float, default=15.0,
                        help="mean detections per sampled frame. PRD 14.1 puts "
                             "the MEDIUM->HIGH boundary at 15 vehicles, so a "
                             "camera whose AVERAGE frame does not reach it "
                             "cannot show sustained HIGH congestion. Its HIGH "
                             "class is then noise however the thresholds are "
                             "later calibrated, because per-camera percentiles "
                             "will manufacture one out of an empty road")
    parser.add_argument("--survey-frames", type=int, default=60,
                        help="frames survey_all.py sampled per clip, to turn "
                             "its detection total into a rate")
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    from mfstnet.corpus.windows import WindowGeometry

    if not args.survey.is_file():
        raise SystemExit(
            f"{args.survey} not found. Run scripts/survey_all.py first — the "
            f"durations come from the survey, not from a hand-kept list."
        )
    entries = json.loads(args.survey.read_text(encoding="utf-8"))

    # Collapse duplicate viewpoints. Two files of one camera are one camera's
    # worth of evidence however many sequences they yield between them, and
    # survey_all has already done the grouping — `camera_id` is its answer.
    # Keeping the LONGEST clip of each camera, since that is the one that
    # decides whether the camera contributes at a given step size at all.
    seen: set[str] = set()
    distinct = []
    for entry in sorted(entries, key=lambda e: -e.get("seconds", 0.0)):
        camera = entry.get("camera_id") or entry["camera"]
        if camera in seen:
            continue
        seen.add(camera)
        distinct.append(entry)

    rows = []
    for entry in distinct:
        seconds = float(entry.get("seconds", 0.0))
        rate = float(entry.get("unassigned_rate", 0.0))
        density = float(entry.get("detections", 0)) / max(args.survey_frames, 1)
        dense_enough = density >= args.min_density
        row = {"clip": entry["clip"], "camera": entry["camera"],
               "seconds": round(seconds, 1),
               "unassigned_rate": round(rate, 4),
               "detections_per_frame": round(density, 1),
               "dense_enough": dense_enough,
               "clears_gate": rate <= args.max_unassigned and dense_enough}
        for step in STEPS:
            g = WindowGeometry(T=args.timesteps, step_s=step,
                               horizon_s=args.horizon_s, stride_s=args.stride_s)
            frames = int(seconds // step)
            row[f"sequences_step{step}"] = (
                (frames - g.min_frames) // g.stride_frames + 1
                if frames >= g.min_frames else 0
            )
            row[f"independent_step{step}"] = int(seconds // g.min_clip_s)
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {len(entries)} clip(s) -> {len(distinct)} distinct camera(s)\n")
    print("  {:<32}{:>8}{:>7}{:>8}{:>9}{:>14}".format(
        "camera", "seconds", "det/fr", "seq @2s", "indep @2s", "gate"))
    for row in rows:
        if row["clears_gate"]:
            gate = "ok"
        elif not row["dense_enough"]:
            gate = f"{row['detections_per_frame']:.0f}/fr THIN"
        else:
            gate = f"{row['unassigned_rate']:.0%} OUT"
        print("  {:<32}{:>8.0f}{:>7.1f}{:>8}{:>9}{:>14}".format(
            row["clip"][:30], row["seconds"], row["detections_per_frame"],
            row["sequences_step2"], row["independent_step2"], gate))

    print()
    print("  {:<12}{:>12}{:>14}{:>12}{:>10}".format(
        "step", "sequences", "independent", "inflation", "cameras"))
    for step in STEPS:
        g = WindowGeometry(T=args.timesteps, step_s=step,
                           horizon_s=args.horizon_s, stride_s=args.stride_s)
        usable = [r for r in rows if r["clears_gate"]]
        seq = sum(r[f"sequences_step{step}"] for r in usable)
        ind = sum(r[f"independent_step{step}"] for r in usable)
        cams = sum(1 for r in usable if r[f"independent_step{step}"])
        print("  {:<12}{:>12}{:>14}{:>11.1f}x{:>7} of {}".format(
            f"{step}s", seq, ind, seq / max(ind, 1), cams, len(rows)))
        print("  {:<12}{:>12}".format("", f"needs >= {g.min_clip_s}s per clip"))

    thin = [r for r in rows if not r["dense_enough"]]
    if thin:
        print(f"\n  {len(thin)} camera(s) under {args.min_density:.0f} "
              f"detections/frame, excluded from the totals above:")
        for row in thin:
            print(f"    {row['clip'][:52]}  {row['detections_per_frame']:.1f}/fr")
        print("  Length and steadiness say nothing about whether a road carries "
              "traffic.")
        print("  These clips pass triage and are the LONGEST footage available, "
              "which is")
        print("  exactly why the gate is needed: duration and density run "
              "opposite here.")

    rejected = [r for r in rows
                if not r["clears_gate"] and r["dense_enough"]]
    if rejected:
        print(f"\n  {len(rejected)} camera(s) over the {args.max_unassigned:.0%} "
              f"unassigned gate, excluded from the totals above:")
        for row in rejected:
            print(f"    {row['clip'][:52]}  {row['unassigned_rate']:.1%}")
        print("  P25: a camera can fail this for having the wrong lane COUNT "
              "rather than")
        print("  for being unusable — check before writing it off.")

    print(f"\n  wrote {args.out}")
    print("  Sequence counts inflate with overlap and independent segments do "
          "not;")
    print("  report the second, and report how many cameras contributed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
