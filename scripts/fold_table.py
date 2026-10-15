"""The fold-level score table, and what each aggregation actually averages.

Required before submission (P85): no macro-F1 mean may be quoted without its
fold composition, because the sign of ADR-022's pre-registered comparison
depends on which folds are in it.

    python scripts/fold_table.py
    python scripts/fold_table.py --config G H

Reads the per-run CSVs under `experiments/results/loco/`; writes nothing.

**Two aggregations, defined here rather than implied.**

``all folds``   the unweighted mean over the four leave-one-camera-out folds.
                Unweighted, so a 63-window camera and an 11-window camera count
                equally. That is deliberate — each fold is one camera, and the
                question is how the model transfers to *a* camera, not to *a
                window* — but it means the aggregate is not a per-window
                average and must not be read as one.

``in-regime``   the same unweighted mean over the folds whose camera is
                declared ``traffic_type: mixed``. It answers a different
                question — generalisation within the target regime — and is
                not a corrected version of the first.

**And a third column that tests whether the difference is real.** Fold 0's test
camera contains **no HIGH windows at all**, and the runner's own warning says
macro-F1 "is being dragged down by a class that does not occur", since an
absent class scores 0 by convention across three classes. `macro_f1_present`
averages only the classes actually present in that fold's test split. If the
ADR-022 sign flip survives in that column, it is not an artefact of class
support; if it does not, the flip is about which classes were evaluable rather
than which camera was held out.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "experiments" / "results" / "loco"
CAMERAS = ROOT / "data" / "cameras.json"
CLASSES = ("low", "medium", "high")

RUN_RE = re.compile(r"^fold(\d+)_seed(\d+)_([A-H])\.csv$")


def declared() -> tuple[dict, list[str]]:
    payload = json.loads(CAMERAS.read_text(encoding="utf-8"))
    cameras = payload.get("cameras", payload)
    target = payload.get("target_domain", {}).get("traffic_type", [])
    return cameras, target


def macro_f1_present(row: dict) -> float | None:
    """Macro-F1 over the classes that actually occur in this test split."""
    scores = [float(row[f"f1_{name}"]) for name in CLASSES
              if row.get(f"support_{name}", "").strip()
              and int(float(row[f"support_{name}"])) > 0]
    return statistics.mean(scores) if scores else None


def load() -> tuple[dict, dict]:
    """(config, fold) -> list of runs, and fold -> fold facts."""
    runs: dict[tuple[str, int], list[dict]] = defaultdict(list)
    folds: dict[int, dict] = {}
    for path in sorted(RUNS.glob("fold*_seed*_?.csv")):
        match = RUN_RE.match(path.name)
        if not match:
            continue
        fold, _seed, config = int(match.group(1)), match.group(2), match.group(3)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            continue
        row = rows[0]
        runs[(config, fold)].append(row)
        folds.setdefault(fold, {
            "camera": row.get("test_camera", "?"),
            "n": int(float(row.get("n", 0) or 0)),
            "support": {name: int(float(row.get(f"support_{name}", 0) or 0))
                        for name in CLASSES},
        })
    return runs, folds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", nargs="*", default=None,
                        help="limit to these ablation configs")
    args = parser.parse_args(argv)

    cameras, target = declared()
    runs, folds = load()
    if not runs:
        print(f"  no per-run CSVs under {RUNS.relative_to(ROOT)}")
        return 1

    configs = sorted({config for config, _fold in runs})
    if args.config:
        configs = [c for c in configs if c in args.config]

    print("\n  Fold composition — each fold holds out one camera entirely "
          "(ADR-019)\n")
    print(f"  {'fold':>4}  {'camera':<34} {'regime':<11} {'win':>4} "
          f"{'LOW':>5} {'MED':>5} {'HIGH':>5}")
    in_regime = set()
    for fold in sorted(folds):
        facts = folds[fold]
        regime = cameras.get(facts["camera"], {}).get("traffic_type", "?")
        if regime in target:
            in_regime.add(fold)
        support = facts["support"]
        flag = "  <- no HIGH to score" if support["high"] == 0 else ""
        print(f"  {fold:>4}  {facts['camera'][:33]:<34} {regime:<11} "
              f"{facts['n']:>4} {support['low']:>5} {support['medium']:>5} "
              f"{support['high']:>5}{flag}")

    excluded = sorted(set(folds) - in_regime)
    print(f"\n  in-regime folds ({', '.join(map(str, sorted(in_regime)))}) "
          f"are traffic_type {target}; excluded: "
          f"{', '.join(map(str, excluded)) or 'none'}")

    print(f"\n  macro-F1 per fold, mean over seeds, with both aggregations\n")
    header = (f"  {'cfg':>4} " + " ".join(f"{'f' + str(f):>7}" for f in sorted(folds))
              + f" {'ALL':>8} {'IN-REG':>8} {'ALLpres':>8} {'IN-REGpres':>10}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    table: dict[str, dict[str, float]] = {}
    for config in configs:
        per_fold, per_fold_present = {}, {}
        for fold in sorted(folds):
            rows = runs.get((config, fold), [])
            if not rows:
                continue
            per_fold[fold] = statistics.mean(
                float(row["macro_f1"]) for row in rows)
            present = [macro_f1_present(row) for row in rows]
            present = [p for p in present if p is not None]
            if present:
                per_fold_present[fold] = statistics.mean(present)

        if not per_fold:
            continue
        every = statistics.mean(per_fold.values())
        inside = statistics.mean([v for k, v in per_fold.items()
                                  if k in in_regime]) if in_regime else float("nan")
        every_p = statistics.mean(per_fold_present.values())
        inside_p = statistics.mean([v for k, v in per_fold_present.items()
                                    if k in in_regime]) if in_regime else float("nan")
        table[config] = {"all": every, "in": inside,
                         "all_present": every_p, "in_present": inside_p}
        cells = " ".join(f"{per_fold.get(f, float('nan')):>7.4f}"
                         for f in sorted(folds))
        print(f"  {config:>4} {cells} {every:>8.4f} {inside:>8.4f} "
              f"{every_p:>8.4f} {inside_p:>10.4f}")

    if "G" in table and "H" in table:
        g, h = table["G"], table["H"]
        print(f"\n  ADR-022, the full model G against the linear probe H:\n")
        print(f"    {'aggregation':<34} {'G':>8} {'H':>8} {'G-H':>9}  winner")
        for label, key in (("all folds, all 3 classes", "all"),
                           ("in-regime folds, all 3 classes", "in"),
                           ("all folds, present classes only", "all_present"),
                           ("in-regime, present classes only", "in_present")):
            delta = g[key] - h[key]
            print(f"    {label:<34} {g[key]:>8.4f} {h[key]:>8.4f} "
                  f"{delta:>+9.4f}  {'G' if delta > 0 else 'H'}")

        flips_support = (g["all"] - h["all"]) * (g["all_present"] - h["all_present"]) < 0
        flips_folds = (g["all"] - h["all"]) * (g["in"] - h["in"]) < 0
        print()
        if flips_folds and not flips_support:
            print("    The flip is driven by FOLD COMPOSITION, and survives "
                  "correcting for\n    absent classes. It is about which "
                  "camera is held out.")
        elif flips_support:
            print("    The flip also appears when only present classes are "
                  "scored, so part\n    of it is about which classes were "
                  "evaluable, not only which camera.")
        else:
            print("    No sign change under this aggregation.")

    print("\n  Neither aggregate is the corrected version of the other. They "
          "answer\n  different questions and both must be reported with their "
          "denominators.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
