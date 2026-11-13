"""Compare the blind hand counts with the detector's counts (label-quality audit).

    python scripts/compare_audit.py --manual experiments/results/bellevue_pilot/audit_manual.json

Implements `experiments/results/bellevue_pilot/AUDIT_PROTOCOL.md`. Reads the
hand counts exported by `data/_bellevue/audit/count_audit.html`, and the
detector's counts for the same samples from the corpus's `counts.csv`, which
this script never modifies.

Per lane it reports the mean absolute error, the signed bias (detector − hand;
negative means the detector misses vehicles) and exact agreement. It also
reports in how many audited frames the detector reported a `bicycle` at the
painted symbol, and the north lane's bias beside the others for the far queue.

**A pilot.** Twenty correlated frames show the direction and rough size of
error, not a definitive accuracy figure.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CORPUS = Path("data/corpus_bellevue")
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "south", "lane_3": "east"}
SYMBOL = (0.20, 0.73)            # the painted bicycle symbol, normalised
OUT = Path("experiments/results/bellevue_pilot/audit_comparison.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manual", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    manual = json.loads(args.manual.read_text(encoding="utf-8"))
    frames = {int(f["sample"]): f for f in manual["frames"]}
    expected = json.loads(Path("experiments/results/bellevue_pilot/audit_frames.json")
                          .read_text(encoding="utf-8"))["samples"]
    missing = sorted(set(expected) - set(frames))
    if missing:
        raise SystemExit(f"{len(missing)} of {len(expected)} frames not counted: "
                         f"{missing}. The audit compares all twenty or none.")

    with (args.corpus / "counts.csv").open(encoding="utf-8") as handle:
        detector = {int(r["sample"]): r for r in csv.DictReader(handle)}
    bikes = {}
    with (args.corpus / "detections.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            k = int(r["sample"])
            if k in frames and r["cls"] == "bicycle":
                cx = (float(r["x1"]) + float(r["x2"])) / 2
                cy = (float(r["y1"]) + float(r["y2"])) / 2
                if math.hypot(cx - SYMBOL[0], cy - SYMBOL[1]) < 0.06:
                    bikes[k] = True

    report = {"annotator": manual.get("annotator"), "frames": len(frames),
              "per_lane": {}, "rows": []}
    for k in sorted(frames):
        row = {"sample": k}
        for lane in LANES:
            row[f"{lane}_hand"] = int(frames[k][lane])
            row[f"{lane}_detector"] = int(detector[k][f"count_{lane}"])
        row["symbol_detected_as_bicycle"] = bool(bikes.get(k))
        row["note"] = frames[k].get("note", "")
        report["rows"].append(row)

    print(f"\n  {len(frames)} frames, annotator {report['annotator']}\n")
    print(f"  {'lane':<14}{'hand mean':>10}{'det mean':>10}{'MAE':>7}"
          f"{'bias':>8}{'exact':>8}")
    for lane, name in LANES.items():
        hand = [r[f"{lane}_hand"] for r in report["rows"]]
        det = [r[f"{lane}_detector"] for r in report["rows"]]
        errors = [d - h for d, h in zip(det, hand)]
        entry = {"approach": name,
                 "hand_mean": round(statistics.mean(hand), 2),
                 "detector_mean": round(statistics.mean(det), 2),
                 "mae": round(statistics.mean(abs(e) for e in errors), 2),
                 "bias": round(statistics.mean(errors), 2),
                 "exact_agreement": round(sum(e == 0 for e in errors) / len(errors), 2),
                 "relative_bias": (round(statistics.mean(errors) / statistics.mean(hand), 3)
                                   if statistics.mean(hand) else None)}
        report["per_lane"][lane] = entry
        print(f"  {lane} {name:<7}{entry['hand_mean']:>10}{entry['detector_mean']:>10}"
              f"{entry['mae']:>7}{entry['bias']:>+8}{entry['exact_agreement']:>8.0%}")

    sym = sum(r["symbol_detected_as_bicycle"] for r in report["rows"])
    report["symbol_frames"] = sym
    north = report["per_lane"]["lane_1"]["relative_bias"]
    others = [report["per_lane"][l]["relative_bias"] for l in ("lane_0", "lane_3")
              if report["per_lane"][l]["relative_bias"] is not None]
    report["north_relative_bias"] = north
    report["west_east_relative_bias"] = others
    print(f"\n  painted symbol reported as a bicycle in {sym} of {len(frames)} frames")
    print(f"  relative bias: north {north}, west/east {others} "
          f"(negative = the detector undercounts)")

    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
