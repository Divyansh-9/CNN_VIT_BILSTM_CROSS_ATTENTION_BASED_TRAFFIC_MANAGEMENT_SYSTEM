"""A17 pilot — how often does the congestion class actually change? (S06)

This is the measurement PRD amendment **A28** pre-registered, and it is run under
that pre-registration: the statistic is fixed in advance, and the clips that need
a particular answer do not get to decide it.

    python scripts/pilot_a17.py --clips <dir>
    python scripts/pilot_a17.py --clips <dir> --limit 1     # validate the pipeline

Two questions gate the whole corpus design:

* do the PRD §14.1 count thresholds (LOW < 5, MED 5-15, HIGH > 15) fit real
  heterogeneous traffic?
* does the class change often enough over 60 s for a forecast to be learnable?

A stated limitation, up front rather than in a footnote: **these counts are
whole-frame, not per-lane.** §14.1's thresholds are defined per lane, and no lane
polygons exist for third-party clips. A whole-frame count is therefore several
times a per-lane count and will saturate at HIGH. So two labelings are reported:

1. **spec** — §14.1 thresholds applied as written. Expected to saturate; that
   saturation is itself a finding about applying per-lane thresholds to a whole
   frame, and is reported rather than hidden.
2. **tercile** — the clip's own count distribution split into thirds. This
   measures the timescale on which *relative* congestion changes, which is what
   A17 actually asks and what `step_s` must be set from.

Neither is a substitute for per-lane counts on lane-annotated footage. Both are
honest about which question they answer.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.labels import (  # noqa: E402
    CongestionClass,
    label_from_count,
    smooth_counts,
)
from scripts.triage_footage import printable  # noqa: E402

T_MINUS_ONE = 59            # T=60 timesteps, so 59 intervals span the window
PERCENTILE = 75             # A28: pre-registered, biases toward a LARGER step_s

# COCO ids that are vehicles. Person and bicycle are excluded: §14.1 counts
# vehicles, and a footpath crowded with pedestrians is not congestion.
VEHICLE_IDS = {2, 3, 5, 7}          # car, motorcycle, bus, truck


def count_series(path: Path, *, every_s: float = 1.0, model=None) -> list[int]:
    """Vehicle count once per second. 1 Hz regardless of the step_s under debate.

    Sampling faster than any candidate `step_s` is what keeps the measurement
    independent of the value it is used to choose (A28).
    """
    import cv2

    handle = cv2.VideoCapture(str(path))
    fps = handle.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(handle.get(cv2.CAP_PROP_FRAME_COUNT))
    counts: list[int] = []

    index = 0
    while index < total:
        handle.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = handle.read()
        if not ok:
            break
        result = model(frame, verbose=False, imgsz=640)[0]
        classes = result.boxes.cls.tolist() if result.boxes is not None else []
        counts.append(sum(1 for c in classes if int(c) in VEHICLE_IDS))
        index += int(fps * every_s)

    handle.release()
    return counts


def transitions(labels: list[int]) -> list[float]:
    """Seconds between consecutive class changes."""
    moments = [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
    if len(moments) < 2:
        return []
    return [float(b - a) for a, b in zip(moments, moments[1:])]


def tercile_labels(counts: list[int]) -> list[int]:
    ordered = sorted(counts)
    if len(set(ordered)) < 3:
        return [1] * len(counts)
    low = ordered[len(ordered) // 3]
    high = ordered[2 * len(ordered) // 3]
    return [0 if c <= low else (2 if c > high else 1) for c in counts]


def analyse(path: Path, model) -> dict:
    counts = count_series(path, model=model)
    if len(counts) < 30:
        return {"file": path.name, "samples": len(counts), "usable": False}

    # Smooth BEFORE labelling, exactly as the corpus pipeline does.
    #
    # Skipping this produced a median inter-transition gap of **1 second** on the
    # Andheri clip — congestion does not change every second. Raw per-frame counts
    # swing 6-13-23, and with thresholds at 5 and 15 a count oscillating around 15
    # flips MEDIUM/HIGH on almost every frame. The measurement was of detector
    # jitter, and the A28 rule dutifully returned step_s = 1 s: the most extreme
    # value available, in exactly the direction the amendment is biased toward.
    #
    # An artifact that lands on your preferred answer is the most dangerous kind.
    smoothed = smooth_counts(counts)
    spec = [int(label_from_count(c)) for c in smoothed]
    tercile = tercile_labels(smoothed)

    spec_gaps = transitions(spec)
    tercile_gaps = transitions(tercile)
    histogram = {c.name: spec.count(int(c)) for c in CongestionClass}

    return {
        "file": path.name,
        "samples": len(counts),
        "usable": True,
        "count_min": min(smoothed),
        "count_median": int(statistics.median(smoothed)),
        "count_max": max(smoothed),
        "spec_low": histogram["LOW"],
        "spec_medium": histogram["MEDIUM"],
        "spec_high": histogram["HIGH"],
        "spec_saturated": max(histogram.values()) == len(smoothed),
        "spec_transitions": len(spec_gaps),
        "spec_median_gap_s": round(statistics.median(spec_gaps), 1) if spec_gaps else None,
        "tercile_transitions": len(tercile_gaps),
        "tercile_median_gap_s": (
            round(statistics.median(tercile_gaps), 1) if tercile_gaps else None
        ),
        "tercile_gaps": tercile_gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clips", type=Path, required=True)
    parser.add_argument("--limit", type=int, help="validate on N clips first")
    parser.add_argument("--weights", default="yolov8n.pt")
    parser.add_argument(
        "--out", type=Path, default=Path("experiments/results/pilot_a17.csv")
    )
    args = parser.parse_args(argv)

    from ultralytics import YOLO

    model = YOLO(args.weights)

    videos = sorted(
        p for p in args.clips.rglob("*") if p.suffix.lower() in {".mp4", ".mkv", ".mov"}
    )
    if args.limit:
        videos = videos[: args.limit]

    rows, all_gaps = [], []
    for video in videos:
        print(f"  {printable(video.name, 46):<46}", end="", flush=True)
        try:
            row = analyse(video, model)
        except Exception as error:                       # noqa: BLE001
            print(f" ERROR {printable(str(error), 40)}")
            continue
        if not row["usable"]:
            print(f" too short ({row['samples']} samples)")
            continue
        rows.append(row)
        all_gaps.extend(row.pop("tercile_gaps"))
        print(
            f" counts {row['count_min']}-{row['count_median']}-{row['count_max']}"
            f"  spec {row['spec_transitions']} trans"
            f"{' (SATURATED)' if row['spec_saturated'] else ''}"
            f"  tercile {row['tercile_transitions']} trans,"
            f" median gap {row['tercile_median_gap_s']}s"
        )

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as handle:
            fields = sorted({k for r in rows for k in r})
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fields})
        print(f"\n  wrote {args.out}")

    if all_gaps:
        all_gaps.sort()
        p75 = all_gaps[min(len(all_gaps) - 1, int(0.75 * len(all_gaps)))]
        implied = -(-p75 // T_MINUS_ONE)          # ceil, per A28
        print(f"\n  inter-transition gaps: n={len(all_gaps)}  "
              f"median {statistics.median(all_gaps):.0f}s  P75 {p75:.0f}s")
        print(f"  A28 rule: step_s = ceil(P75 / {T_MINUS_ONE}) = {implied:.0f} s")
        print(
            f"\n  PRELIMINARY. A28 requires >=5 INDEPENDENT vantage points "
            f"(distinct camera and location).\n"
            f"  This ran on {len(rows)} clip(s); count the distinct locations before "
            f"quoting the number."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
