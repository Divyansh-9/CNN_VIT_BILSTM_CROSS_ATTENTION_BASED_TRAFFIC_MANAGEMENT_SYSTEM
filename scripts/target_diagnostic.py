"""P93 — how predictable is each candidate target from its own past? (no model)

    python scripts/target_diagnostic.py --corpus data/corpus_bellevue_cal

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P93.md`. It
reads `counts.csv` and the corpus's **training and validation** windows only;
the test period is never touched. Writes `target_diagnostic.json` beside the
pre-registration.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.labels import smooth_counts  # noqa: E402
from mfstnet.metrics import evaluate  # noqa: E402

LEVELS = ["LOW", "MEDIUM", "HIGH"]
DIRS = ["fall", "stay", "rise"]
TOLERANCE = 1.0
ROOM_BELOW = 0.80
MIN_CLASS = 10
RESAMPLES = 10_000
OUT = Path("experiments/results/bellevue_pilot/target_diagnostic.json")


def mean(xs):
    return sum(xs) / len(xs)


def direction(delta: float) -> int:
    return 0 if delta < -TOLERANCE else (2 if delta > TOLERANCE else 1)


def autocorr(series: list[float], lag: int) -> float:
    m = mean(series)
    num = sum((series[i] - m) * (series[i + lag] - m) for i in range(len(series) - lag))
    den = sum((x - m) ** 2 for x in series)
    return num / den if den else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    lanes = list(manifest["lanes"])
    bounds = next(iter(manifest["thresholds_by_clip"].values()))
    lo, mid = bounds["low_max"], bounds["med_max"]
    level = lambda x: 0 if x <= lo else (1 if x <= mid else 2)  # noqa: E731

    c = {lane: [] for lane in lanes}
    with (args.corpus / "counts.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for lane in lanes:
                c[lane].append(int(row["count_" + lane]))
    smoothed = {lane: smooth_counts(v, 3) for lane, v in c.items()}

    with (args.corpus / "sequences.csv").open(encoding="utf-8") as handle:
        windows = [r for r in csv.DictReader(handle) if r["split"] in ("train", "val")]

    # One record per (window, lane): every target and every baseline.
    records = {"train": [], "val": []}
    for w in windows:
        e = int(w["start_index"]) + manifest["T"] - 1
        for lane in lanes:
            s = c[lane]
            past = mean(s[e - 29:e + 1])
            prior = mean(s[e - 59:e - 29])
            future = mean(s[e + 1:e + 31])
            trend_level = past + (past - prior)
            records[w["split"]].append({
                "window": w["start_index"], "lane": lane,
                "level_true": level(future), "level_persist": level(past),
                "level_trend": level(trend_level),
                "future": future, "past": past, "trend_value": trend_level,
                "dir_true": direction(future - past), "dir_persist": 1,
                "dir_trend": direction(past - prior),
                "inst_true": level(round(smoothed[lane][e + 30])),
            })

    def score(rows, truth, pred, names):
        rep = evaluate([r[truth] for r in rows], [r[pred] for r in rows], names)
        return {"macro_f1": round(rep.macro_f1, 4), "accuracy": round(rep.accuracy, 4),
                "qwk": round(rep.qwk, 4)}

    val = records["val"]
    out = {"n_val_windows": len({r["window"] for r in val}), "n_val_decisions": len(val)}

    out["distribution"] = {
        split: {
            "level": {LEVELS[k]: v for k, v in sorted(Counter(r["level_true"] for r in rs).items())},
            "direction": {DIRS[k]: v for k, v in sorted(Counter(r["dir_true"] for r in rs).items())},
        } for split, rs in records.items()}

    out["level"] = {"persistence": score(val, "level_true", "level_persist", LEVELS),
                    "trend": score(val, "level_true", "level_trend", LEVELS),
                    "persistence_mae": round(mean([abs(r["future"] - r["past"]) for r in val]), 3),
                    "trend_mae": round(mean([abs(r["future"] - r["trend_value"]) for r in val]), 3)}
    out["direction"] = {"persistence": score(val, "dir_true", "dir_persist", DIRS),
                        "trend": score(val, "dir_true", "dir_trend", DIRS)}
    out["instantaneous_reference"] = {
        "persistence": score([{**r, "p": r["level_persist"]} for r in val], "inst_true", "p", LEVELS)}

    out["per_lane_level_persistence_accuracy"] = {
        lane: round(mean([int(r["level_true"] == r["level_persist"]) for r in val if r["lane"] == lane]), 3)
        for lane in lanes}

    # Paired bootstrap over validation windows: trend minus persistence.
    by_window = {}
    for r in val:
        by_window.setdefault(r["window"], []).append(r)
    groups = list(by_window.values())
    rng = random.Random(0)

    def boot(truth, a, b, names):
        diffs = []
        for _ in range(RESAMPLES):
            sample = [x for _ in groups for x in groups[rng.randrange(len(groups))]]
            t = [x[truth] for x in sample]
            diffs.append(evaluate(t, [x[a] for x in sample], names).macro_f1
                         - evaluate(t, [x[b] for x in sample], names).macro_f1)
        diffs.sort()
        return [round(diffs[int(.025 * RESAMPLES)], 4), round(diffs[int(.975 * RESAMPLES) - 1], 4)]

    out["level"]["trend_minus_persistence_ci"] = boot("level_true", "level_trend", "level_persist", LEVELS)
    out["direction"]["trend_minus_persistence_ci"] = boot("dir_true", "dir_trend", "dir_persist", DIRS)

    # Signal-cycle check on the TRAINING period only.
    train_end = max(int(w["start_index"]) for w in windows if w["split"] == "train") + 89
    out["autocorrelation_train"] = {
        lane: {f"{2 * lag}s": round(autocorr([float(x) for x in c[lane][:train_end + 1]], lag), 3)
               for lag in (1, 5, 10, 15, 20, 30, 45, 60, 90)}
        for lane in lanes}

    # Decision rules, as pre-registered.
    val_dist = out["distribution"]["val"]
    def room(target):
        f1 = out[target]["persistence"]["macro_f1"]
        support = val_dist[target]
        names = LEVELS if target == "level" else DIRS
        starved = [n for n in names if support.get(n, 0) < MIN_CLASS]
        return {"persistence_macro_f1": f1, "below_0_80": f1 < ROOM_BELOW,
                "classes_under_10": starved, "room": f1 < ROOM_BELOW and not starved}
    out["decision"] = {"level": room("level"), "direction": room("direction")}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
