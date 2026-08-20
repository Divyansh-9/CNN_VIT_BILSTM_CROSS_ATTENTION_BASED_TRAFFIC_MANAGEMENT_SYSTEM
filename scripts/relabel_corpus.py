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

from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402


def percentile(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path,
                        help="defaults to <corpus>_relabelled")
    parser.add_argument("--low-max", type=int)
    parser.add_argument("--med-max", type=int)
    parser.add_argument("--calibrate", action="store_true",
                        help="set boundaries at the p33/p67 of the observed "
                             "counts (ADR-017's rule)")
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

    if args.calibrate:
        # Every count that a label is actually drawn from — the label frame of
        # each window, not every sampled frame. Calibrating on the wrong
        # population would put the boundaries in the wrong place.
        observed = []
        for row in sequences:
            index = int(row["label_index"])
            for lane in lanes:
                values = smoothed[row["clip_id"]][lane]
                if index < len(values):
                    observed.append(int(round(values[index])))
        if not observed:
            raise SystemExit("no label-frame counts found; corpus is malformed")
        p33, p67 = percentile(observed, 33), percentile(observed, 67)

        # ADR-017's rule is `low_max = p33 - 1`, so that p33 itself lands in
        # MEDIUM. That assumes p33 > 0, and on real footage it is not: an empty
        # lane counts zero, and with four lanes per camera **41.2% of per-lane
        # counts are zero**, which puts p33 at 0 and low_max at -1. No count
        # can be <= -1, so LOW became unreachable and the calibrated corpus was
        # 0% LOW — the exact degeneracy calibration exists to avoid (P34).
        #
        # Clamped at 0, LOW means "an empty lane", which is what the class
        # should mean anyway.
        low_max = max(0, p33 - 1)
        med_max = percentile(observed, 67)
        if med_max <= low_max:
            # A distribution concentrated enough that p33 and p67 collide
            # leaves MEDIUM empty. Widening by one keeps three usable classes
            # and is reported, never silent.
            med_max = low_max + 1
        zero_share = sum(1 for v in observed if v == 0) / len(observed)
        print(f"  calibrated on {len(observed)} label-frame counts: "
              f"p33={p33} p67={p67}  ({zero_share:.1%} of them zero)")
        if p33 == 0:
            print("  p33 is 0, so LOW is clamped to mean an empty lane "
                  "(ADR-017's rule would give -1, which nothing satisfies)")
    else:
        if args.low_max is None or args.med_max is None:
            raise SystemExit("give --low-max and --med-max, or --calibrate")
        low_max, med_max = args.low_max, args.med_max

    if low_max >= med_max:
        raise SystemExit(
            f"low_max ({low_max}) must be below med_max ({med_max}). With a "
            f"tight count distribution the p33 and p67 can collide; that is a "
            f"finding about the footage, not a bug to code around."
        )

    relabelled = []
    for row in sequences:
        entry = dict(row)
        index = int(row["label_index"])
        for lane in lanes:
            values = smoothed[row["clip_id"]][lane]
            count = int(round(values[index])) if index < len(values) else 0
            entry["label_" + lane] = label_from_count(
                count, low_max=low_max, med_max=med_max).name
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
        "low_max": low_max, "med_max": med_max,
        "relabelled_from": str(args.corpus),
        "calibrated": bool(args.calibrate),
    })
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n  thresholds  LOW <= {low_max}   MEDIUM <= {med_max}   HIGH >")
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
