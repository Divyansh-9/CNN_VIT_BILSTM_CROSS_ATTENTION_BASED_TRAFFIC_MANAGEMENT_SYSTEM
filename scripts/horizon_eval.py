"""Select on validation, read the test once, and compare with persistence (S63b).

    python scripts/horizon_eval.py --runs experiments/results/bellevue_pilot/h180 \\
        --corpus data/corpus_bellevue_h180 --counts data/corpus_bellevue/counts.csv

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_horizon.md`,
written before any score at a new horizon existed.

1. **Selection reads validation columns only:** `config`, `seed`,
   `val_macro_f1`. It picks the config with the higher mean, then that config's
   best seed, with ties going to the earlier seed in 42 1 7 13 21.
2. **The test period is read once,** for the selected run, from its committed
   per-window predictions (P59).
3. **Persistence** is causal: the label of the **raw** count at the window's
   last observed sample, under the corpus's frozen thresholds. The majority
   class is reported too.
4. **"Beats persistence"** means the paired bootstrap 95% interval of
   (model − persistence) test macro-F1 excludes zero. That is 10,000
   resamples of test windows, each window's lanes kept together. Otherwise the
   result is "not distinguishable".

Writes `horizon_eval.json` beside the runs.
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

CLASSES = ["LOW", "MEDIUM", "HIGH"]
SEEDS = (42, 1, 7, 13, 21)
RESAMPLES = 10_000


def select(runs: Path) -> dict:
    rows = []
    for path in sorted(glob.glob(str(runs / "seed*_?.csv"))):
        with open(path, encoding="utf-8") as handle:
            r = next(csv.DictReader(handle))
        rows.append({"config": r["config"], "seed": int(r["seed"]),
                     "val_macro_f1": float(r["val_macro_f1"])})
    by = {}
    for r in rows:
        by.setdefault(r["config"], []).append(r)
    means = {c: statistics.mean(r["val_macro_f1"] for r in v) for c, v in by.items()}
    config = max(sorted(means), key=lambda c: means[c])
    best = sorted(by[config], key=lambda r: (-r["val_macro_f1"],
                                              SEEDS.index(r["seed"])))[0]
    return {"config_means": {c: round(m, 4) for c, m in means.items()},
            "by_seed": {c: {r["seed"]: r["val_macro_f1"] for r in v}
                        for c, v in by.items()},
            "selected": best}


def macro_f1(true, pred) -> float:
    return evaluate(true, pred, CLASSES).macro_f1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0, help="bootstrap RNG")
    args = parser.parse_args(argv)

    choice = select(args.runs)
    sel = choice["selected"]
    print(f"  validation means {choice['config_means']}")
    for config, seeds in choice["by_seed"].items():
        print(f"    {config}: " + "  ".join(f"s{s}={v:.4f}" for s, v in seeds.items()))
    print(f"  selected {sel['config']} seed {sel['seed']} "
          f"(validation {sel['val_macro_f1']:.4f})")

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    lanes = list(manifest["lanes"])
    bounds = next(iter((manifest.get("thresholds_by_clip") or {}).values()),
                  {"low_max": manifest["low_max"], "med_max": manifest["med_max"]})
    lo, mid = bounds["low_max"], bounds["med_max"]

    def label(count: float) -> int:
        return 0 if count <= lo else (1 if count <= mid else 2)

    with args.counts.open(encoding="utf-8") as handle:
        counts = {(c["clip_id"], int(c["sample"])): c for c in csv.DictReader(handle)}
    pred_path = args.runs / (f"seed{sel['seed']}_{sel['config']}_"
                             f"{sel['config']}.predictions.csv")
    with pred_path.open(encoding="utf-8") as handle:
        model = {(r["clip_id"], int(r["start_index"]), r["lane"]): r
                 for r in csv.DictReader(handle)}

    windows = []                         # [(true[], model[], persistence[])]
    with (args.corpus / "sequences.csv").open(encoding="utf-8") as handle:
        for s in csv.DictReader(handle):
            if s["split"] != "test":
                continue
            start = int(s["start_index"])
            last = counts[(s["clip_id"], start + manifest["T"] - 1)]
            t, m, p = [], [], []
            for lane in lanes:
                row = model[(s["clip_id"], start, lane)]
                t.append(CLASSES.index(row["true"]))
                m.append(CLASSES.index(row["pred"]))
                p.append(label(float(last["count_" + lane])))
            windows.append((t, m, p))

    flat = lambda i: [x for w in windows for x in w[i]]  # noqa: E731
    true, mod, per = flat(0), flat(1), flat(2)
    majority = [max(set(true), key=true.count)] * len(true)
    rep_m, rep_p = evaluate(true, mod, CLASSES), evaluate(true, per, CLASSES)
    diff = rep_m.macro_f1 - rep_p.macro_f1

    rng = random.Random(args.seed)
    boot = []
    for _ in range(RESAMPLES):
        sample = [windows[rng.randrange(len(windows))] for _ in windows]
        t = [x for w in sample for x in w[0]]
        boot.append(macro_f1(t, [x for w in sample for x in w[1]])
                    - macro_f1(t, [x for w in sample for x in w[2]]))
    boot.sort()
    lo_ci, hi_ci = boot[int(0.025 * RESAMPLES)], boot[int(0.975 * RESAMPLES) - 1]
    verdict = ("model beats persistence" if lo_ci > 0 else
               "persistence beats model" if hi_ci < 0 else "not distinguishable")

    support = {c: true.count(i) for i, c in enumerate(CLASSES)}
    per_lane = {lane: sum(int(w[1][j] == w[0][j]) for w in windows)
                for j, lane in enumerate(lanes)}
    result = {
        **choice, "test_windows": len(windows), "test_decisions": len(true),
        "support": support,
        "model": {"macro_f1": round(rep_m.macro_f1, 4),
                  "accuracy": round(rep_m.accuracy, 4), "qwk": round(rep_m.qwk, 4)},
        "persistence": {"macro_f1": round(rep_p.macro_f1, 4),
                        "accuracy": round(rep_p.accuracy, 4),
                        "qwk": round(rep_p.qwk, 4)},
        "majority": {"macro_f1": round(macro_f1(true, majority), 4)},
        "difference_macro_f1": round(diff, 4),
        "bootstrap_95ci": [round(lo_ci, 4), round(hi_ci, 4)],
        "verdict": verdict, "per_lane_correct": per_lane,
        "thresholds": {"low_max": lo, "med_max": mid},
    }
    (args.runs / "horizon_eval.json").write_text(json.dumps(result, indent=2),
                                                 encoding="utf-8")
    print(f"\n  TEST, read once: {len(windows)} windows, {len(true)} decisions, "
          f"support {support}")
    print(f"    model        macro-F1 {rep_m.macro_f1:.4f}  accuracy "
          f"{rep_m.accuracy:.4f}  QWK {rep_m.qwk:.4f}")
    print(f"    persistence  macro-F1 {rep_p.macro_f1:.4f}  accuracy "
          f"{rep_p.accuracy:.4f}  QWK {rep_p.qwk:.4f}")
    print(f"    majority     macro-F1 {result['majority']['macro_f1']:.4f}")
    print(f"    model - persistence {diff:+.4f}, 95% CI [{lo_ci:+.4f}, "
          f"{hi_ci:+.4f}]  ->  {verdict.upper()}")
    print(f"    per-lane correct out of {len(windows)}: {per_lane}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
