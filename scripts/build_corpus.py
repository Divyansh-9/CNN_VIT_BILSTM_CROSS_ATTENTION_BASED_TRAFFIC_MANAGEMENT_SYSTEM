"""Turn video clips into MFSTNet training sequences (S15, ADR-002, PRD §8.6).

    python scripts/build_corpus.py --clips data/dev_footage --lanes motorway
    python scripts/build_corpus.py --clips D:/footage --lanes junction --out data/corpus

Every component of this has existed for weeks — `corpus.windows` for the index
arithmetic, `corpus.counting` for occupancy, `corpus.labels` for the §14.1
thresholds, `corpus.splits` for leakage-free partitioning, `corpus.geometry` for
lane assignment. **What did not exist was the assembly**, which is why MFSTNet
has never seen real data.

    frames -> detector -> per-lane counts -> smoothed -> §14.1 label
                                                     -> windows -> splits

**Counts are sampled at `step_s`, not at video frame rate.** A15 fixes the
arithmetic: T=60 observations at 5 s spacing covers 295 s, and the label sits
`horizon_s` past the last observation, so a clip under 360 s yields nothing.

**Splits are cut by CLIP, never by sequence** (ADR-002). Consecutive windows
share most of their frames, so sequence-level splitting puts near-duplicates on
both sides and reports a validation score that means nothing. `assert_no_clip_leakage`
is called on the result rather than trusted.

**This writes counts and labels, not features.** Backbone caching is ADR-005's
job and depends on the preprocessing hash; keeping them separate means a label
rule can change without re-encoding video, and a backbone can change without
re-counting.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.counting import Detection, count_frame  # noqa: E402
from mfstnet.corpus.geometry import Polygon  # noqa: E402
from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402
from mfstnet.corpus.splits import assert_no_clip_leakage, assign_splits  # noqa: E402
from mfstnet.corpus.windows import WindowGeometry, sequences_from_clip  # noqa: E402

# Lane layouts. A motorway is two carriageways, not four approaches — ADR-016
# Phase 1 validates the ARCHITECTURE, and the number of lanes is a config, not
# an architectural constant. The junction layout is what §8.6 specifies.
LANE_SETS = {
    "junction": (
        Polygon("north", ((0.30, 0.00), (0.70, 0.00), (0.70, 0.45), (0.30, 0.45))),
        Polygon("south", ((0.30, 0.55), (0.70, 0.55), (0.70, 1.00), (0.30, 1.00))),
        Polygon("east", ((0.72, 0.30), (1.00, 0.30), (1.00, 0.70), (0.72, 0.70))),
        Polygon("west", ((0.00, 0.30), (0.28, 0.30), (0.28, 0.70), (0.00, 0.70))),
    ),
    "motorway": (
        Polygon("left_carriageway", ((0.00, 0.45), (0.48, 0.45), (0.48, 1.00), (0.00, 1.00))),
        Polygon("right_carriageway", ((0.52, 0.45), (1.00, 0.45), (1.00, 1.00), (0.52, 1.00))),
    ),
}


def sample_counts(clip: Path, lanes, model, ids, names, *, step_s: float,
                  conf: float) -> tuple[list[dict], int]:
    """Per-lane occupancy every `step_s` seconds. Returns (rows, n_samples)."""
    import cv2

    capture = cv2.VideoCapture(str(clip))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, int(round(fps * step_s)))

    rows = []
    for index in range(0, total, stride):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        result = model.predict(source=frame, conf=conf, verbose=False)[0]
        height, width = result.orig_shape
        detections = [
            Detection(
                cls=names[int(c)], confidence=float(p),
                # Normalised, because lane polygons are resolution-independent.
                x1=b[0] / width, y1=b[1] / height,
                x2=b[2] / width, y2=b[3] / height,
            )
            for b, c, p in zip(result.boxes.xyxy.tolist(),
                               result.boxes.cls.tolist(),
                               result.boxes.conf.tolist())
            if int(c) in ids
        ]
        counts = count_frame(detections, lanes, min_confidence=conf)
        row = {"clip_id": clip.stem, "sample": len(rows),
               "t_s": round(len(rows) * step_s, 2)}
        for lane in lanes:
            row[f"count_{lane.name}"] = counts.per_lane.get(lane.name, 0)
        row["unassigned"] = counts.unassigned
        rows.append(row)
    capture.release()
    return rows, len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clips", type=Path, required=True,
                        help="a video file, or a directory of them")
    parser.add_argument("--lanes", choices=sorted(LANE_SETS), default="junction",
                        help="a built-in layout; superseded by --polygons")
    parser.add_argument(
        "--polygons", type=Path,
        help="lanes.json from scripts/survey_lanes.py. ONE file describes ONE "
             "camera, and every clip in the build is assumed to come from that "
             "camera — which is what P17 requires: polygons live in the image "
             "plane, so a corpus cannot span cameras",
    )
    parser.add_argument("--weights", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--conf", type=float, default=0.45,
                        help="the pinned counting operating point (S14b)")
    # Integers, because WindowGeometry derives FRAME strides from these and a
    # float stride is not a valid range() step. The spec values are integral
    # anyway (A15, PRD §8.2); accepting floats here only invites a crash deep in
    # the window arithmetic rather than at the argument.
    parser.add_argument("--step-s", type=int, default=5, help="A15")
    parser.add_argument("--horizon-s", type=int, default=60, help="PRD §8.2")
    parser.add_argument("--timesteps", type=int, default=60, help="T, PRD §8.2")
    parser.add_argument("--stride-s", type=int, default=30)
    parser.add_argument("--split-mode", choices=("clip", "temporal"), default="clip",
                        help="'clip' assigns whole clips (ADR-002) and needs "
                             "enough clips to fill three splits. 'temporal' "
                             "splits ONE camera's timeline by time, discarding "
                             "windows within a window-length of each boundary "
                             "so no test window shares a frame with training")
    parser.add_argument("--low-max", type=int, default=4,
                        help="highest count still LOW. PRD 14.1 says 4. "
                             "A parameter because the corpus stores COUNTS, "
                             "which are threshold-independent -- see below")
    parser.add_argument("--med-max", type=int, default=15,
                        help="highest count still MEDIUM. PRD 14.1 says 15")
    parser.add_argument("--out", type=Path, default=Path("data/corpus"))
    parser.add_argument(
        "--max-unassigned", type=float, default=0.35,
        help="refuse a clip whose detections mostly fall OUTSIDE every lane "
             "polygon. A polygon is defined in the image plane, so it belongs "
             "to one camera; applied to another it counts the wrong region and "
             "every label built on it is arbitrary (P17). Measured across 13 "
             "clips with one shared polygon set: 13.5%% to 94%% assigned",
    )
    parser.add_argument(
        "--exclude", nargs="*", default=["Bellevue"],
        help="substrings of paths to skip. Bellevue is excluded BY DEFAULT: the "
             "detector is measurably out of domain there (0.73 detections/frame "
             "against an oblique reference of 9.88), so its counts would enter "
             "the corpus as false LOW labels and contaminate it silently",
    )
    args = parser.parse_args(argv)

    from ultralytics import YOLO

    from scripts.pilot_a17 import vehicle_ids

    clips = (
        sorted(args.clips.rglob("*.mp4")) if args.clips.is_dir() else [args.clips]
    )
    if args.exclude:
        kept = [c for c in clips
                if not any(bad in str(c) for bad in args.exclude)]
        if len(kept) != len(clips):
            print(f"  excluded {len(clips) - len(kept)} clip(s) matching "
                  f"{args.exclude} — the detector is out of domain there,")
            print("  and a wrong count becomes a wrong LABEL, which is worse "
                  "than no data at all")
            print()
        clips = kept
    if not clips:
        raise SystemExit(f"no usable .mp4 under {args.clips}")

    if args.polygons:
        spec = json.loads(args.polygons.read_text(encoding="utf-8"))
        lanes = tuple(
            Polygon(entry["name"], tuple(tuple(v) for v in entry["points"]))
            for entry in spec["lanes"]
        )
        print(f"  lanes surveyed from {spec.get('clip', args.polygons.name)} "
              f"({len(lanes)}), disjoint={spec.get('disjoint')}")
        if not spec.get("disjoint", True):
            raise SystemExit(
                "those polygons OVERLAP. Overlapping lanes double-count every "
                "vehicle in the shared region, so the counts are wrong before "
                "any threshold is applied. Edit the JSON and re-check."
            )
    else:
        lanes = LANE_SETS[args.lanes]
    model = YOLO(str(args.weights))
    ids = vehicle_ids(model)
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))

    geometry = WindowGeometry(T=args.timesteps, step_s=args.step_s,
                              horizon_s=args.horizon_s, stride_s=args.stride_s)
    minimum = (args.timesteps - 1) * args.step_s + args.horizon_s
    print(f"  lanes {args.lanes} ({len(lanes)}), T={args.timesteps}, "
          f"step {args.step_s}s, horizon {args.horizon_s}s")
    print(f"  a clip needs >= {minimum:.0f}s to yield ANY sequence (A15)\n")

    import cv2

    all_counts, all_sequences, skipped, rejected = [], [], [], []
    for clip in clips:
        # Duration first. Running the detector over a clip that cannot yield a
        # single window is pure waste, and most of a mixed footage directory is
        # short clips — this turns a directory scan from hours into minutes.
        probe = cv2.VideoCapture(str(clip))
        fps = probe.get(cv2.CAP_PROP_FPS) or 25.0
        seconds = int(probe.get(cv2.CAP_PROP_FRAME_COUNT)) / fps if fps else 0.0
        probe.release()
        if seconds < minimum:
            skipped.append((clip.stem, seconds))
            continue

        rows, n = sample_counts(clip, lanes, model, ids, names,
                                step_s=args.step_s, conf=args.conf)

        # P17. Counts through a mismatched polygon are not low counts, they are
        # counts of the wrong region — and a balanced label distribution over
        # meaningless counts is worse than an obviously broken one.
        assigned = sum(r[f"count_{lane.name}"] for r in rows for lane in lanes)
        unassigned = sum(r["unassigned"] for r in rows)
        rate = unassigned / max(assigned + unassigned, 1)
        if rate > args.max_unassigned:
            rejected.append((clip.stem, rate))
            print(f"  {clip.stem[:44]:<46} REJECTED — {rate:.0%} of detections "
                  f"fall outside every lane")
            continue

        sequences = sequences_from_clip(clip.stem, n, geometry)
        if not sequences:
            skipped.append((clip.stem, n * args.step_s))
            print(f"  {clip.stem[:44]:<46} {n:>4} samples  0 sequences (too short)")
            continue
        all_counts.extend(rows)
        all_sequences.extend(sequences)
        print(f"  {clip.stem[:44]:<46} {n:>4} samples  {len(sequences):>4} sequences")

    if not all_sequences:
        raise SystemExit(
            f"\nNo clip yielded a sequence. Every one is shorter than {minimum:.0f}s.\n"
            f"That is A15's arithmetic, not a bug: T={args.timesteps} observations "
            f"at {args.step_s}s spacing\nspan {(args.timesteps-1)*args.step_s:.0f}s, "
            f"and the label sits {args.horizon_s:.0f}s past the last one."
        )

    # Labels, from smoothed per-lane counts at the LABEL index of each window.
    by_clip: dict[str, list[dict]] = {}
    for row in all_counts:
        by_clip.setdefault(row["clip_id"], []).append(row)
    smoothed = {
        clip_id: {
            lane.name: smooth_counts([r[f"count_{lane.name}"] for r in rows])
            for lane in lanes
        }
        for clip_id, rows in by_clip.items()
    }

    if args.split_mode == "temporal":
        if len(by_clip) > 1:
            raise SystemExit(
                f"--split-mode temporal splits ONE camera's timeline, but "
                f"{len(by_clip)} clips were given. Two clips from different "
                f"cameras cannot share a timeline; use --split-mode clip."
            )
        window_frames = geometry.T + geometry.label_offset_frames
        per_sequence = assign_splits_temporal(
            [s.start_index for s in all_sequences], window_frames=window_frames)
        kept = [(s, v) for s, v in zip(all_sequences, per_sequence) if v is not None]
        dropped = len(all_sequences) - len(kept)
        print(f"  temporal split: {len(kept)} window(s) kept, {dropped} discarded "
              f"as boundary buffers ({window_frames} frames each side)")
        all_sequences = [s for s, _ in kept]
        splits = None
        sequence_split = {id(s): v for s, v in kept}
    else:
        splits = assign_splits(sorted(by_clip))
        sequence_split = None

    labelled = []
    for sequence in all_sequences:
        series = smoothed[sequence.clip_id]
        entry = {
            "clip_id": sequence.clip_id,
            "split": (splits[sequence.clip_id] if splits
                      else sequence_split[id(sequence)]),
            "start_index": sequence.start_index,
            "label_index": sequence.label_index,
        }
        for lane in lanes:
            count = series[lane.name][sequence.label_index]
            entry[f"label_{lane.name}"] = label_from_count(
                int(round(count)), low_max=args.low_max, med_max=args.med_max).name
        labelled.append(entry)

    # Verified, not assumed. Consecutive windows share most of their frames, so
    # a clip appearing in two splits means the model has effectively seen the
    # test set — and it presents as suspiciously good validation, not as an error.
    if args.split_mode == "clip":
        assert_no_clip_leakage(
            [e["clip_id"] for e in labelled], [e["split"] for e in labelled]
        )

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_counts[0]))
        writer.writeheader()
        writer.writerows(all_counts)
    with (args.out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labelled[0]))
        writer.writeheader()
        writer.writerows(labelled)
    (args.out / "manifest.json").write_text(json.dumps({
        "lanes": [lane.name for lane in lanes],
        "T": args.timesteps, "step_s": args.step_s,
        "horizon_s": args.horizon_s, "stride_s": args.stride_s,
        "detector": args.weights.name, "conf": args.conf,
        "clips": sorted(by_clip), "splits": splits,
        "split_mode": args.split_mode,
        "auto_labelled": True,
        "low_max": args.low_max, "med_max": args.med_max,
        "threshold_note": (
            "The expensive pass produces counts.csv, which is "
            "THRESHOLD-INDEPENDENT. Labels in sequences.csv are a cheap "
            "derivation on top. scripts/relabel_corpus.py regenerates them "
            "under different thresholds in seconds, without re-running the "
            "detector -- so a threshold decision is a config change, never a "
            "reason to delay building the corpus."
        ),
        "reporting_note": (
            "A32: auto-labelled. Labels are a deterministic function of the "
            "count, so count-sequence baselines observe the label-generating "
            "variable directly. The HEADLINE comparison must use the "
            "human-verified test split."
        ),
    }, indent=2), encoding="utf-8")

    import collections
    print(f"\n  {len(labelled)} sequences over {len(by_clip)} clip(s)")
    print(f"  splits: {collections.Counter(splits.values())}")
    for lane in lanes:
        dist = collections.Counter(e[f"label_{lane.name}"] for e in labelled)
        total = sum(dist.values())
        parts = "  ".join(f"{k} {dist.get(k,0)/total:5.1%}"
                          for k in ("LOW", "MEDIUM", "HIGH"))
        print(f"    {lane.name:<20}{parts}")
    if skipped:
        print(f"\n  {len(skipped)} clip(s) too short: "
              + ", ".join(f"{n} ({d:.0f}s)" for n, d in skipped[:4]))
    print(f"\n  wrote {args.out}/counts.csv, sequences.csv, manifest.json")
    print("  AUTO-LABELLED (A32). The headline comparison needs human-verified")
    print("  labels, because count baselines see the label-generating variable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
