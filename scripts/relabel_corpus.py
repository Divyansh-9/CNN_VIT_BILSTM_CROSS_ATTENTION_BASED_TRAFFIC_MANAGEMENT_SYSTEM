"""Relabel an existing corpus under different thresholds, in seconds.

    python scripts/relabel_corpus.py --corpus data/corpus --low-max 10 --med-max 14
    python scripts/relabel_corpus.py --corpus data/corpus --calibrate     # p33/p67

**This script exists because a threshold decision was wrongly treated as a
blocker.** The reasoning went: §14.1's thresholds produce a degenerate corpus
(P20, P21), the fix needs faculty sign-off (ADR-017), therefore no corpus can be
built and MFSTNet cannot train.

Only the first two clauses are true. The expensive pass — running the detector
over every frame of every clip — produces **`counts.csv`, which contains no
thresholds at all**. Labels are a cheap arithmetic derivation on top, written
into `sequences.csv`. Rebuilding them costs seconds and no GPU.

So the corpus can be built now, MFSTNet can train now, and the guide's decision
selects which labelling is the *headline* rather than gating the work. That is a
reporting choice, which is exactly what ADR-017 asks to fix.

**`--calibrate` is a measurement, not a preference.** It reads the p33 and p67
of the observed count distribution and puts the boundaries there, which is
ADR-017's rule. It prints the resulting class shares so a degenerate split is
visible immediately rather than after a training run.

**Nothing is overwritten in place.** A relabelled corpus is written to its own
directory with its thresholds recorded in the manifest, so two labellings can be
trained and compared side by side — which is what settles the question the
sign-off is about.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402


def percentile(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))]


def calibrate_boundaries(observed: list[int]) -> tuple[int, int]:
    """p33/p67 boundaries for one population of counts.

    ADR-017's rule is `low_max = p33 - 1`, putting p33 itself in MEDIUM. That
    assumes p33 > 0, which per-lane counts violate: an empty lane counts zero
    and 41.2% of the pilot's per-lane counts are zero, so p33 = 0 gives
    `low_max = -1` and nothing satisfies `count <= -1`. Clamped at zero, LOW
    means "an empty lane" (P34).

    The second guard covers a distribution tight enough that p33 and p67
    collide, which would otherwise leave MEDIUM empty.
    """
    p33, p67 = percentile(observed, 33), percentile(observed, 67)
    low_max = max(0, p33 - 1)
    med_max = max(p67, low_max + 1)
    return low_max, med_max


def label_frame_counts(sequences, smoothed, lanes, *, clip_id=None) -> list[int]:
    """Counts a label is actually drawn from — the label frame of each window.

    Calibrating on every sampled frame would weight the quiet stretches between
    windows, which no label is ever computed from.
    """
    observed = []
    for row in sequences:
        if clip_id is not None and row["clip_id"] != clip_id:
            continue
        index = int(row["label_index"])
        for lane in lanes:
            values = smoothed[row["clip_id"]][lane]
            if index < len(values):
                observed.append(int(round(values[index])))
    return observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path,
                        help="defaults to <corpus>_relabelled")
    parser.add_argument("--low-max", type=int)
    parser.add_argument("--med-max", type=int)
    parser.add_argument("--calibrate", action="store_true",
                        help="set boundaries at the p33/p67 of the observed "
                             "counts, PER CAMERA (ADR-017 decision 2)")
    parser.add_argument("--calibrate-global", action="store_true",
                        help="one threshold pair pooled across every camera. "
                             "What --calibrate used to do, kept only so the "
                             "two can be compared — ADR-017 rejects it")
    parser.add_argument("--smooth-window", type=int, default=3)
    args = parser.parse_args(argv)

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    lanes = manifest["lanes"]
    with (args.corpus / "counts.csv").open(encoding="utf-8", newline="") as handle:
        counts = list(csv.DictReader(handle))
    with (args.corpus / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        sequences = list(csv.DictReader(handle))

    series: dict[str, dict[str, list[int]]] = {}
    for row in counts:
        clip = series.setdefault(row["clip_id"], {})
        for lane in lanes:
            clip.setdefault(lane, []).append(int(row["count_" + lane]))
    smoothed = {clip: {lane: smooth_counts(values, args.smooth_window)
                       for lane, values in per_lane.items()}
                for clip, per_lane in series.items()}

    clips = sorted({row["clip_id"] for row in sequences})
    if args.calibrate or args.calibrate_global:
        if args.calibrate and args.calibrate_global:
            raise SystemExit("choose one of --calibrate and --calibrate-global")

        if args.calibrate_global:
            # ADR-017 decision 2 rejects this: "A threshold in absolute units
            # describes the view, not the road." Kept only so the two can be
            # put side by side for the sign-off.
            observed = label_frame_counts(sequences, smoothed, lanes)
            if not observed:
                raise SystemExit("no label-frame counts found; corpus is malformed")
            low_max, med_max = calibrate_boundaries(observed)
            bounds = {clip: (low_max, med_max) for clip in clips}
            print(f"  GLOBAL calibration over {len(observed)} label-frame counts: "
                  f"LOW <= {low_max}, MEDIUM <= {med_max}")
            print("  ADR-017 decision 2 asks for per-camera thresholds; this is "
                  "the comparison arm.")
        else:
            # Per camera, which is what ADR-017 decision 2 specifies and what
            # the measurement supports: on the pilot the per-camera p67 ranges
            # from 1 to 19, while the pooled p67 is 3. Pooled thresholds mark
            # nearly everything HIGH on a busy camera and LOW on a quiet one
            # (P37).
            bounds = {}
            print("  {:<40}{:>7}{:>9}{:>9}".format(
                "camera", "n", "LOW <=", "MED <="))
            for clip in clips:
                observed = label_frame_counts(sequences, smoothed, lanes,
                                              clip_id=clip)
                if not observed:
                    raise SystemExit(f"no label-frame counts for {clip}")
                bounds[clip] = calibrate_boundaries(observed)
                zero = sum(1 for v in observed if v == 0) / len(observed)
                note = "  (all-zero p33, LOW means an empty lane)" if zero > 1/3 else ""
                print("  {:<40}{:>7}{:>9}{:>9}{}".format(
                    clip[:38], len(observed), bounds[clip][0], bounds[clip][1], note))
            low_max, med_max = calibrate_boundaries(
                label_frame_counts(sequences, smoothed, lanes))
    else:
        if args.low_max is None or args.med_max is None:
            raise SystemExit("give --low-max and --med-max, --calibrate, "
                             "or --calibrate-global")
        low_max, med_max = args.low_max, args.med_max
        bounds = {clip: (low_max, med_max) for clip in clips}

    for clip, (lo, hi) in bounds.items():
        if lo >= hi:
            raise SystemExit(
                f"{clip}: low_max ({lo}) must be below med_max ({hi}). With a "
                f"tight count distribution p33 and p67 can collide; that is a "
                f"finding about the footage, not a bug to code around."
            )

    relabelled = []
    for row in sequences:
        entry = dict(row)
        index = int(row["label_index"])
        clip_low, clip_med = bounds[row["clip_id"]]
        for lane in lanes:
            values = smoothed[row["clip_id"]][lane]
            count = int(round(values[index])) if index < len(values) else 0
            entry["label_" + lane] = label_from_count(
                count, low_max=clip_low, med_max=clip_med).name
        relabelled.append(entry)

    out = args.out or args.corpus.with_name(args.corpus.name + "_relabelled")
    out.mkdir(parents=True, exist_ok=True)
    # counts.csv is copied unchanged: it is the measurement, and it is the
    # reason this operation is cheap.
    shutil.copyfile(args.corpus / "counts.csv", out / "counts.csv")
    with (out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(relabelled[0]))
        writer.writeheader()
        writer.writerows(relabelled)

    manifest = dict(manifest)
    manifest.update({
        # Kept for readers that expect a single pair; it is the POOLED
        # calibration and is not what the labels were computed with when
        # calibrating per camera. `thresholds_by_clip` is the authority.
        "low_max": low_max, "med_max": med_max,
        "thresholds_by_clip": {clip: {"low_max": lo, "med_max": hi}
                               for clip, (lo, hi) in sorted(bounds.items())},
        "threshold_scope": ("per_camera" if args.calibrate
                            else "global" if args.calibrate_global
                            else "fixed"),
        "relabelled_from": str(args.corpus),
        "calibrated": bool(args.calibrate or args.calibrate_global),
    })
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if manifest["threshold_scope"] == "per_camera":
        print()
        print(f"  thresholds per camera ({len(bounds)} sets), recorded in the "
              f"manifest as thresholds_by_clip")
    else:
        print()
        print(f"  thresholds  LOW <= {low_max}   MEDIUM <= {med_max}   HIGH >")
    print(f"  {len(relabelled)} sequences over {len(lanes)} lane(s)\n")
    degenerate = []
    for split in ("train", "val", "test"):
        rows = [r for r in relabelled if r["split"] == split]
        if not rows:
            continue
        tally = collections.Counter(
            r["label_" + lane] for r in rows for lane in lanes)
        total = sum(tally.values())
        shares = "  ".join(f"{name} {tally[name] / total:>5.1%}"
                           for name in ("LOW", "MEDIUM", "HIGH"))
        print(f"    {split:<6}{len(rows):>5} seq   {shares}")
        for name in ("LOW", "MEDIUM", "HIGH"):
            if tally[name] / total < 0.05:
                degenerate.append(f"{name} is {tally[name] / total:.1%} of {split}")

    if degenerate:
        print("\n  DEGENERATE: " + "; ".join(degenerate))
        print("  Macro F1 over a class with near-zero support is unstable, and")
        print("  undefined at zero. Train on this only to prove the pipeline")
        print("  runs — do not report it as a result.")
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
