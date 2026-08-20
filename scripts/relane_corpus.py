"""Re-derive a corpus under different lane centres, without the detector (P28).

    python scripts/relane_corpus.py --corpus data/corpus --lanes-dir data/lanes_v2

`counts.csv` holds occupancy under one particular set of lane centres, so
moving a centre by hand would otherwise mean another pass of the detector over
every clip -- hours, for a change that is a few clicks. `detections.csv` holds
the same pass's output in normalised coordinates and **does not depend on the
lanes at all**, so the counts can be rebuilt from it in seconds.

This is the same argument the corpus manifest already makes for thresholds,
applied to the other half. Between them:

| changing | costs |
|---|---|
| label thresholds | `relabel_corpus.py` -- seconds |
| **lane centres** | **this script -- seconds** |
| detector, confidence, `step_s`, `imgsz` | `build_corpus.py` -- hours |

Lane placement is done by eye over a detection heatmap and is not going to be
right first time. Making it revisable is what lets it be judged against the
counts it produces rather than against how it looks.

**What this does not do.** It cannot change the detector, the confidence
threshold, the sampling rate or the image size -- those change which detections
exist. Splits are carried over unchanged, so that a lane change is the only
difference between two corpora.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.counting import Detection, count_frame  # noqa: E402
from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402
from mfstnet.corpus.splits import assert_no_clip_leakage  # noqa: E402
from mfstnet.corpus.windows import WindowGeometry, sequences_from_clip  # noqa: E402

from scripts.build_corpus import lane_names, load_reviewed_lanes  # noqa: E402


def read_detections(path: Path) -> dict[str, dict[int, list[Detection]]]:
    """`clip_id -> sample index -> detections`, from the lane-free CSV."""
    by_clip: dict[str, dict[int, list[Detection]]] = defaultdict(
        lambda: defaultdict(list))
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_clip[row["clip_id"]][int(row["sample"])].append(
                Detection(
                    cls=row["cls"], confidence=float(row["confidence"]),
                    x1=float(row["x1"]), y1=float(row["y1"]),
                    x2=float(row["x2"]), y2=float(row["y2"]),
                )
            )
    return by_clip


def samples_from_counts(path: Path) -> dict[str, int]:
    """Series length per clip, from counts.csv.

    Only the `clip_id` and `sample` columns are read, and those are
    **lane-independent** even though the counts beside them are not: every
    sampled frame gets a row whether or not the detector saw anything in it.
    That is what makes this a complete answer where the detections alone are
    not — a run of empty frames at the end of a clip leaves no detection rows
    at all, so the highest detection index understates the series.
    """
    if not path.is_file():
        return {}
    highest: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            clip, sample = row["clip_id"], int(row["sample"])
            if sample >= highest.get(clip, -1):
                highest[clip] = sample
    return {clip: n + 1 for clip, n in highest.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--lanes-dir", type=Path, required=True,
                        help="reviewed per-camera lanes, from import_lane_centres.py")
    parser.add_argument("--out", type=Path,
                        help="defaults to --corpus, rewriting it in place")
    parser.add_argument("--low-max", type=int)
    parser.add_argument("--med-max", type=int)
    args = parser.parse_args(argv)

    out = args.out or args.corpus
    detections_csv = args.corpus / "detections.csv"
    if not detections_csv.is_file():
        raise SystemExit(
            f"{detections_csv} not found. A corpus built before P28 stored only "
            f"per-lane counts, which cannot be re-derived under new lanes -- "
            f"rebuild it once with build_corpus.py and every later lane change "
            f"is free."
        )

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    per_clip_lanes = load_reviewed_lanes(args.lanes_dir)
    detections = read_detections(detections_csv)
    # A plain dict from here on: `samples.get(index, [])` on a defaultdict
    # would insert the missing key and quietly grow the mapping while it is
    # being read.
    detections = {clip: dict(samples) for clip, samples in detections.items()}

    conf = float(manifest["conf"])
    step_s = manifest["step_s"]
    low_max = args.low_max if args.low_max is not None else manifest["low_max"]
    med_max = args.med_max if args.med_max is not None else manifest["med_max"]

    # Lanes are keyed by clip FILENAME and the corpus by clip STEM, because a
    # stem is what survives into a CSV. Matching on stem keeps one mapping.
    lanes_by_stem = {Path(clip).stem: lanes for clip, lanes in per_clip_lanes.items()}
    absent = sorted(set(detections) - set(lanes_by_stem))
    if absent:
        raise SystemExit(
            f"{len(absent)} clip(s) in the corpus have no reviewed lanes, e.g. "
            f"{absent[0][:60]}. Counting one camera through another's lanes "
            f"counts the wrong region (P17)."
        )

    geometry = WindowGeometry(T=manifest["T"], step_s=step_s,
                              horizon_s=manifest["horizon_s"],
                              stride_s=manifest["stride_s"])

    names = lane_names(next(iter(lanes_by_stem.values())))
    print(f"  {len(detections)} clip(s), {len(names)} lane(s) each, "
          f"conf {conf}, step {step_s}s")
    print(f"  thresholds LOW<={low_max}  MEDIUM<={med_max}")
    print()
    print("  {:<44}{:>9}{:>13}".format("clip", "samples", "unassigned"))

    # A frame the detector found nothing in writes no rows, so iterating the
    # keys of detections.csv would skip it -- and an empty frame is zero
    # traffic, a LOW label, not missing data. Worse, compacting the series
    # breaks the index arithmetic: window position i would stop meaning sample
    # i, and every label would be read from the wrong moment.
    per_clip_samples = manifest.get("samples_per_clip") or samples_from_counts(
        args.corpus / "counts.csv")
    if not per_clip_samples:
        per_clip_samples = {c: max(s) + 1 for c, s in detections.items()}
        print("  NOTE: neither samples_per_clip nor counts.csv is available, so")
        print("  the series length comes from the highest detection index.")
        print("  Trailing frames with no detections cannot be recovered.")
        print()
    short = {c: (per_clip_samples[c], max(s) + 1) for c, s in detections.items()
             if per_clip_samples.get(c, 0) < max(s) + 1}
    if short:
        raise SystemExit(
            f"the recorded sample count is shorter than the detections for "
            f"{len(short)} clip(s), e.g. {sorted(short)[0][:40]} "
            f"{short[sorted(short)[0]]}. That would silently drop windows."
        )

    all_counts, all_sequences, lanes_by_clip = [], [], {}
    for clip_id in sorted(detections):
        clip_lanes = lanes_by_stem[clip_id]
        samples = detections[clip_id]
        rows = []
        for index in range(per_clip_samples[clip_id]):
            counts = count_frame(samples.get(index, []), clip_lanes,
                                 min_confidence=conf)
            row = {"clip_id": clip_id, "sample": index,
                   "t_s": round(index * step_s, 2)}
            for name in lane_names(clip_lanes):
                row[f"count_{name}"] = counts.per_lane.get(name, 0)
            row["unassigned"] = counts.unassigned
            rows.append(row)

        assigned = sum(r[f"count_{n}"] for r in rows for n in lane_names(clip_lanes))
        outside = sum(r["unassigned"] for r in rows)
        rate = outside / max(assigned + outside, 1)
        print("  {:<44}{:>9}{:>12.1%}".format(clip_id[:42], len(rows), rate))

        lanes_by_clip[clip_id] = clip_lanes
        all_counts.extend(rows)
        all_sequences.extend(sequences_from_clip(clip_id, len(rows), geometry))

    if not all_sequences:
        raise SystemExit("no clip yielded a sequence under this geometry")

    by_clip: dict[str, list[dict]] = defaultdict(list)
    for row in all_counts:
        by_clip[row["clip_id"]].append(row)
    smoothed = {
        clip_id: {name: smooth_counts([r[f"count_{name}"] for r in rows])
                  for name in lane_names(lanes_by_clip[clip_id])}
        for clip_id, rows in by_clip.items()
    }

    # Splits are reused verbatim. Re-deriving them would move clips between
    # train and test for a reason unrelated to the lanes, and a comparison
    # against the previous corpus would then mean nothing.
    splits = manifest.get("splits") or {}
    unknown = sorted({s.clip_id for s in all_sequences} - set(splits))
    if unknown:
        raise SystemExit(
            f"the manifest has no split for {unknown[0][:50]}. Splits are "
            f"carried over unchanged so that a lane change is the only "
            f"difference between two corpora."
        )

    labelled = []
    for sequence in all_sequences:
        series = smoothed[sequence.clip_id]
        entry = {"clip_id": sequence.clip_id, "split": splits[sequence.clip_id],
                 "start_index": sequence.start_index,
                 "label_index": sequence.label_index}
        for name in lane_names(lanes_by_clip[sequence.clip_id]):
            entry[f"label_{name}"] = label_from_count(
                int(round(series[name][sequence.label_index])),
                low_max=low_max, med_max=med_max).name
        labelled.append(entry)

    assert_no_clip_leakage([e["clip_id"] for e in labelled],
                           [e["split"] for e in labelled])

    out.mkdir(parents=True, exist_ok=True)
    if out != args.corpus:
        (out / "detections.csv").write_bytes(detections_csv.read_bytes())
    with (out / "counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_counts[0]))
        writer.writeheader()
        writer.writerows(all_counts)
    with (out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labelled[0]))
        writer.writeheader()
        writer.writerows(labelled)

    manifest["lanes"] = names
    manifest["low_max"], manifest["med_max"] = low_max, med_max
    manifest["lane_centres_by_clip"] = {
        clip_id: {"lanes": [{"name": n, "centre": list(c)}
                            for n, c in zip(cl.names, cl.centres)],
                  "max_radius": cl.max_radius}
        for clip_id, cl in sorted(lanes_by_clip.items())
    }
    first = next(iter(lanes_by_clip.values()))
    manifest["lane_centres"] = [{"name": n, "centre": list(c)}
                                for n, c in zip(first.names, first.centres)]
    manifest["max_radius"] = first.max_radius
    manifest["relaned_from"] = str(args.corpus)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                       encoding="utf-8")

    import collections
    print()
    print(f"  {len(labelled)} sequences over {len(by_clip)} clip(s) -> {out}")
    for name in names:
        dist = collections.Counter(e[f"label_{name}"] for e in labelled)
        total = sum(dist.values())
        parts = "  ".join(f"{k} {dist.get(k, 0) / total:5.1%}"
                          for k in ("LOW", "MEDIUM", "HIGH"))
        print(f"    {name:<18}{parts}")
    print()
    print("  The feature cache is unaffected -- lane geometry is applied at ROI")
    print("  pooling, so there is no need to re-run build_cache.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
