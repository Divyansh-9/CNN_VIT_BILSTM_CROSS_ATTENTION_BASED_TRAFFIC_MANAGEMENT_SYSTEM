"""P94 — select on validation, freeze, then read each test period once.

    python scripts/p94_eval.py select
    python scripts/p94_eval.py test

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P94.md`.

**`select` reads only `config`, `seed` and `val_macro_f1`** for both targets,
applies the pre-registered rules, and writes `selection_P94.json`. **`test`
refuses to run until that file exists**, so selection cannot follow the test,
even by accident.

- **Config rule:** the higher mean validation macro-F1; on an exact tie, H.
- **Seed rule:** the highest validation macro-F1 within each config; ties go to
  the earlier seed in 42 1 7 13 21.
- **Baseline:** the previous-window mean, `mean(c[e−K+1 … e])`, causal.
- **"Beats":** the paired bootstrap 95% interval of (model − baseline) test
  macro-F1 excludes zero.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.metrics import evaluate  # noqa: E402

ROOT = Path("experiments/results/bellevue_pilot")
#: Each experiment's targets: results folder -> (corpus, K). P97 is the
#: three-lane rerun of P94 under the same rules (PREREGISTRATION_P97.md).
SETS = {
    "P94": {"sus60": ("data/corpus_bellevue_sus60", 30),
            "sus120": ("data/corpus_bellevue_sus120", 60)},
    "P97": {"3lane_sus60": ("data/corpus_bellevue_3lane_sus60", 30),
            "3lane_sus120": ("data/corpus_bellevue_3lane_sus120", 60)},
}
TARGETS = SETS["P94"]

#: Lane ids are assigned left to right on import, so the same id can mean a
#: different approach in different experiments: in P97 lane_2 is EAST, in P94
#: it was south. Results are reported by approach, never by id alone.
LANE_NAMES = {
    "P94": {"lane_0": "west", "lane_1": "north", "lane_2": "south", "lane_3": "east"},
    "P97": {"lane_0": "west", "lane_1": "north", "lane_2": "east"},
}
NAMES = LANE_NAMES["P94"]
SEEDS = (42, 1, 7, 13, 21)
CLASSES = ["LOW", "MEDIUM", "HIGH"]
SELECTION = ROOT / "selection_P94.json"
TEST_OUT = ROOT / "p94_test.json"
RESAMPLES = 10_000


def select() -> int:
    out = {}
    for target in TARGETS:
        rows = []
        for path in sorted(glob.glob(str(ROOT / target / "seed*_?.csv"))):
            with open(path, encoding="utf-8") as handle:
                r = next(csv.DictReader(handle))
            rows.append({"config": r["config"], "seed": int(r["seed"]),
                         "val_macro_f1": float(r["val_macro_f1"])})
        by = {}
        for r in rows:
            by.setdefault(r["config"], []).append(r)
        means = {c: statistics.mean(r["val_macro_f1"] for r in v) for c, v in by.items()}
        top = max(means.values())
        tied = sorted(c for c, m in means.items() if m == top)
        config = "H" if "H" in tied else tied[0]
        seeds = {c: sorted(v, key=lambda r: (-r["val_macro_f1"],
                                              SEEDS.index(r["seed"])))[0]["seed"]
                 for c, v in by.items()}
        out[target] = {"config_means": {c: round(m, 4) for c, m in means.items()},
                       "by_seed": {c: {r["seed"]: r["val_macro_f1"] for r in v}
                                   for c, v in by.items()},
                       "selected_config": config, "selected_seed": seeds,
                       "tie_on_config": len(tied) > 1, "runs": len(rows)}
        print(f"  {target}: means {out[target]['config_means']} -> config "
              f"{config}{' (tie)' if len(tied) > 1 else ''}; seeds {seeds}")
    SELECTION.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"  wrote {SELECTION} — selections frozen; no test period read")
    return 0


def test() -> int:
    if not SELECTION.exists():
        raise SystemExit("run `select` first: the test is read only after "
                         "every selection is frozen")
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    report = {}
    for target, (corpus, K) in TARGETS.items():
        corpus = Path(corpus)
        manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
        lanes = list(manifest["lanes"])
        b = next(iter(manifest["thresholds_by_clip"].values()))
        level = lambda x: 0 if x <= b["low_max"] else (1 if x <= b["med_max"] else 2)  # noqa: E731, B023
        c = {lane: [] for lane in lanes}
        with (corpus / "counts.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for lane in lanes:
                    c[lane].append(int(row["count_" + lane]))
        with (corpus / "sequences.csv").open(encoding="utf-8") as handle:
            test_rows = [r for r in csv.DictReader(handle) if r["split"] == "test"]

        preds = {}
        for config, seed in selection[target]["selected_seed"].items():
            path = ROOT / target / f"seed{seed}_{config}_{config}.predictions.csv"
            with path.open(encoding="utf-8") as handle:
                preds[config] = {(int(r["start_index"]), r["lane"]): r
                                 for r in csv.DictReader(handle)}

        windows = []                     # per window: truth, G, H, baseline
        for r in test_rows:
            start = int(r["start_index"]); e = start + 59
            t, g, h, p = [], [], [], []
            for lane in lanes:
                t.append(CLASSES.index(r["label_" + lane]))
                g.append(CLASSES.index(preds["G"][(start, lane)]["pred"]))
                h.append(CLASSES.index(preds["H"][(start, lane)]["pred"]))
                past = c[lane][e - K + 1:e + 1]
                p.append(level(sum(past) / len(past)))
            windows.append((t, g, h, p))

        flat = lambda i, ws: [x for w in ws for x in w[i]]  # noqa: E731
        truth = flat(0, windows)
        rng = random.Random(0)

        def interval(i: int) -> list[float]:
            diffs = []
            for _ in range(RESAMPLES):
                s = [windows[rng.randrange(len(windows))] for _ in windows]
                t = flat(0, s)
                diffs.append(evaluate(t, flat(i, s), CLASSES).macro_f1
                             - evaluate(t, flat(3, s), CLASSES).macro_f1)
            diffs.sort()
            return [round(diffs[int(.025 * RESAMPLES)], 4),
                    round(diffs[int(.975 * RESAMPLES) - 1], 4)]

        entry = {"test_windows": len(windows), "decisions": len(truth),
                 "support": {cl: truth.count(i) for i, cl in enumerate(CLASSES)},
                 "selected_config": selection[target]["selected_config"]}
        for name, i in (("G", 1), ("H", 2), ("previous_window_mean", 3)):
            rep = evaluate(truth, flat(i, windows), CLASSES)
            entry[name] = {"macro_f1": round(rep.macro_f1, 4),
                           "accuracy": round(rep.accuracy, 4), "qwk": round(rep.qwk, 4),
                           "per_lane_correct": {f"{NAMES.get(lane, lane)} ({lane})":
                                         sum(int(w[i][j] == w[0][j]) for w in windows)
                                     for j, lane in enumerate(lanes)}}
        majority = [max(set(truth), key=truth.count)] * len(truth)
        entry["majority_macro_f1"] = round(evaluate(truth, majority, CLASSES).macro_f1, 4)
        for name, i in (("G", 1), ("H", 2)):
            lo, hi = interval(i)
            entry[name]["minus_baseline_ci"] = [lo, hi]
            entry[name]["verdict"] = ("beats the previous-window mean" if lo > 0 else
                                      "below the previous-window mean" if hi < 0 else
                                      "not distinguishable")
        report[target] = entry

        print(f"\n  {target} (K={K}): {len(windows)} test windows, support {entry['support']}")
        for name in ("G", "H", "previous_window_mean"):
            m = entry[name]
            extra = (f"   minus baseline {m['minus_baseline_ci']} -> {m['verdict']}"
                     if "verdict" in m else "")
            print(f"    {name:<21} F1 {m['macro_f1']:.4f}  acc {m['accuracy']:.4f}  "
                  f"QWK {m['qwk']:.4f}{extra}")
            print(f"    {'':<21} per lane {m['per_lane_correct']}")
        print(f"    majority F1 {entry['majority_macro_f1']:.4f}")
    TEST_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("phase", choices=("select", "test"))
    parser.add_argument("--set", choices=sorted(SETS), default="P94",
                        help="which pre-registered experiment")
    args = parser.parse_args(argv)
    global TARGETS, SELECTION, TEST_OUT, NAMES
    TARGETS = SETS[args.set]
    NAMES = LANE_NAMES[args.set]
    SELECTION = ROOT / f"selection_{args.set}.json"
    TEST_OUT = ROOT / f"{args.set.lower()}_test.json"
    return select() if args.phase == "select" else test()


if __name__ == "__main__":
    raise SystemExit(main())
