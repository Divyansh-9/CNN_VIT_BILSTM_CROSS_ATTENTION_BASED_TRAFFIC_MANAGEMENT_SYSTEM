"""The 60-frame label audit: per-lane error with frame-clustered intervals.

    python scripts/compare_audit_combined.py \\
        --manual experiments/results/bellevue_pilot/audit_manual.json \\
                 experiments/results/bellevue_pilot/audit_manual_2.json

Implements the expansion section of
`experiments/results/bellevue_pilot/AUDIT_PROTOCOL.md`, written before the 40
new frames were chosen. It refuses unless every frame in `audit_frames.json`
and `audit_frames_2.json` has been counted. `compare_audit.py` and its pilot
output are left as they were.

**Per lane:** the mean signed error (detector − hand), the undercount
percentage (1 − Σdetector / Σhand), exact agreement, and Pearson and Spearman
correlation. Each gets a 95% bootstrap interval with **the frame as the
cluster** — a frame's four lanes come from one image and are resampled
together.

**Quiet against busy** splits at the median hand count of each lane, because
the hand count is the reference. The painted symbol is reported across all 60
frames.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CORPUS = Path("data/corpus_bellevue")
ROOT = Path("experiments/results/bellevue_pilot")
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "south", "lane_3": "east"}
SYMBOL = (0.20, 0.73)
RESAMPLES = 10_000
OUT = ROOT / "audit_comparison_60.json"


def pearson(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out, i = [0.0] * len(v), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def stats(hand, det):
    err = [d - h for d, h in zip(det, hand)]
    total = sum(hand)
    return {"signed_error": statistics.mean(err),
            "undercount": (1 - sum(det) / total) if total else float("nan"),
            "exact": sum(e == 0 for e in err) / len(err),
            "pearson": pearson(hand, det),
            "spearman": pearson(ranks(hand), ranks(det))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manual", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    expected = set(json.load(open(ROOT / "audit_frames.json"))["samples"])
    expected |= set(json.load(open(ROOT / "audit_frames_2.json"))["samples"])
    hand = {}
    for path in args.manual:
        for f in json.loads(path.read_text(encoding="utf-8"))["frames"]:
            hand[int(f["sample"])] = f
    missing = sorted(expected - set(hand))
    if missing:
        raise SystemExit(f"{len(missing)} of {len(expected)} frames not counted, "
                         f"e.g. {missing[:5]}. The audit compares all of them.")

    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        det = {int(r["sample"]): r for r in csv.DictReader(handle)}
    symbol = set()
    with (CORPUS / "detections.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            k = int(r["sample"])
            if k in expected and r["cls"] == "bicycle":
                cx = (float(r["x1"]) + float(r["x2"])) / 2
                cy = (float(r["y1"]) + float(r["y2"])) / 2
                if math.hypot(cx - SYMBOL[0], cy - SYMBOL[1]) < 0.06:
                    symbol.add(k)

    frames = sorted(expected)
    table = {k: {lane: (int(hand[k][lane]), int(det[k]["count_" + lane]))
                 for lane in LANES} for k in frames}
    rng = random.Random(0)
    report = {"frames": len(frames), "symbol_frames": len(symbol), "per_lane": {}}

    print(f"\n  {len(frames)} frames; painted symbol reported as a bicycle in "
          f"{len(symbol)} of {len(frames)}\n")
    for lane, name in LANES.items():
        h = [table[k][lane][0] for k in frames]
        d = [table[k][lane][1] for k in frames]
        point = stats(h, d)
        boots = {key: [] for key in point}
        for _ in range(RESAMPLES):
            sample = [frames[rng.randrange(len(frames))] for _ in frames]
            hs = [table[k][lane][0] for k in sample]
            ds = [table[k][lane][1] for k in sample]
            if len(set(hs)) < 2 or len(set(ds)) < 2:
                continue
            for key, value in stats(hs, ds).items():
                boots[key].append(value)
        ci = {key: [sorted(v)[int(.025 * len(v))], sorted(v)[int(.975 * len(v)) - 1]]
              for key, v in boots.items() if v}
        median = statistics.median(h)
        quiet = [i for i, x in enumerate(h) if x <= median]
        busy = [i for i, x in enumerate(h) if x > median]
        split = {}
        for label, idx in (("quiet", quiet), ("busy", busy)):
            if len(idx) >= 3:
                sub = stats([h[i] for i in idx], [d[i] for i in idx])
                split[label] = {"n": len(idx), "undercount": round(sub["undercount"], 3),
                                "signed_error": round(sub["signed_error"], 2)}
        report["per_lane"][lane] = {
            "approach": name, "hand_mean": round(statistics.mean(h), 2),
            "detector_mean": round(statistics.mean(d), 2),
            **{key: round(value, 3) for key, value in point.items()},
            "ci95": {key: [round(a, 3), round(b, 3)] for key, (a, b) in ci.items()},
            "split_at_hand_median": median, **split}
        e = report["per_lane"][lane]
        print(f"  {lane} {name:<6} hand {e['hand_mean']:>5}  det {e['detector_mean']:>5}  "
              f"error {e['signed_error']:+.2f} {e['ci95'].get('signed_error')}  "
              f"undercount {e['undercount']:.0%} {e['ci95'].get('undercount')}")
        print(f"  {'':<13} exact {e['exact']:.0%}  Pearson {e['pearson']:.2f} "
              f"{e['ci95'].get('pearson')}  Spearman {e['spearman']:.2f}")
        if split:
            print(f"  {'':<13} quiet (n={split.get('quiet', {}).get('n')}): undercount "
                  f"{split.get('quiet', {}).get('undercount')}   busy (n="
                  f"{split.get('busy', {}).get('n')}): undercount "
                  f"{split.get('busy', {}).get('undercount')}")

    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
