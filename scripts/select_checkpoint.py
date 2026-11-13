"""Choose the deployment checkpoint by the pre-registered rule, validation only.

    python scripts/select_checkpoint.py

Applies `experiments/results/loco_foreign/PREREGISTRATION.md`, written before
any S61 run existed:

1. **Config** — higher mean `val_macro_f1` over all its runs.
2. **Fold** — test *and* validation cameras both declared `traffic_type:
   mixed`; the largest test set if several qualify.
3. **Seed** — highest `val_macro_f1` within that config and fold; ties go to
   the seed listed first in the pre-registration.

**No test column is read.** Each result CSV is opened and only the columns in
`READ` are taken from it, so the rule cannot see a test score even by accident.
The test camera's size is read from the fold manifest's window counts, which
are a property of the split and not of any result.

Writes `selection.json` beside the results: the chosen checkpoint, the rule's
inputs, every candidate's validation score, and any run recorded as failed.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

#: The only columns this script may read from a result file.
READ = ("config", "seed", "fold", "val_macro_f1")
SEED_ORDER = (42, 1, 7, 13, 21)


def validation_rows(results: Path) -> list[dict]:
    rows = []
    for path in sorted(results.glob("fold*_seed*_?.csv")):
        if path.name.endswith(".predictions.csv"):
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("val_macro_f1", "") == "":
                    raise SystemExit(f"{path.name} has no val_macro_f1; it was "
                                     f"trained before S61 and cannot be selected")
                rows.append({k: row[k] for k in READ})
    return rows


def fold_facts(views: Path, cameras: dict) -> dict[int, dict]:
    facts = {}
    for directory in sorted(views.glob("fold*")):
        manifest = json.loads((directory / "manifest.json")
                              .read_text(encoding="utf-8"))
        with (directory / "sequences.csv").open(encoding="utf-8") as handle:
            sizes = Counter(r["split"] for r in csv.DictReader(handle))
        test, val = manifest["fold_test_camera"], manifest["fold_val_camera"]
        regime = lambda c: cameras.get(c, {}).get("traffic_type")  # noqa: E731
        facts[int(manifest["fold"])] = {
            "test_camera": test, "val_camera": val,
            "test_regime": regime(test), "val_regime": regime(val),
            "test_windows": sizes["test"],
        }
    return facts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--results", type=Path,
                        default=Path("experiments/results/loco_foreign"))
    parser.add_argument("--views", type=Path,
                        default=Path("data/corpus_loco_foreign"))
    parser.add_argument("--checkpoints", type=Path,
                        default=Path("models/mfstnet/foreign"))
    parser.add_argument("--cameras", type=Path,
                        default=Path("data/cameras.json"))
    args = parser.parse_args(argv)

    rows = validation_rows(args.results)
    cameras = json.loads(args.cameras.read_text(encoding="utf-8"))["cameras"]
    folds = fold_facts(args.views, cameras)
    failures = []
    failed = args.results / "failures.csv"
    if failed.is_file():
        with failed.open(encoding="utf-8") as handle:
            failures = list(csv.DictReader(handle))

    by_config: dict[str, list[float]] = {}
    for row in rows:
        by_config.setdefault(row["config"], []).append(float(row["val_macro_f1"]))
    means = {c: statistics.mean(v) for c, v in by_config.items()}
    print("\n  1. config, by mean validation macro-F1 over all its runs")
    for c, v in sorted(by_config.items()):
        print(f"       {c}: {means[c]:.4f} over {len(v)} run(s)")
    config = max(sorted(means), key=lambda c: means[c])

    qualifying = {f: d for f, d in folds.items()
                  if d["test_regime"] == "mixed" and d["val_regime"] == "mixed"}
    if not qualifying:
        raise SystemExit("no fold has both test and validation cameras in the "
                         "mixed regime; the pre-registered rule cannot apply")
    fold = max(sorted(qualifying), key=lambda f: qualifying[f]["test_windows"])
    print(f"\n  2. fold, test and validation both mixed, largest test set")
    for f, d in sorted(folds.items()):
        mark = "<-" if f == fold else ("ok" if f in qualifying else "  ")
        print(f"       {mark} fold {f}: test {d['test_regime']:<10} "
              f"({d['test_windows']} windows), val {d['val_regime']}")

    candidates = sorted(
        (r for r in rows if r["config"] == config and int(r["fold"]) == fold),
        key=lambda r: (-float(r["val_macro_f1"]),
                       SEED_ORDER.index(int(r["seed"]))
                       if int(r["seed"]) in SEED_ORDER else 99))
    if not candidates:
        raise SystemExit(f"no completed run of config {config} on fold {fold}")
    print(f"\n  3. seed, highest validation macro-F1 in config {config}, "
          f"fold {fold}")
    for r in candidates:
        print(f"       seed {int(r['seed']):>3}: {float(r['val_macro_f1']):.4f}")
    chosen = candidates[0]
    seed = int(chosen["seed"])
    checkpoint = args.checkpoints / f"mfstnet_{config}_seed{seed}_fold{fold}.pt"
    if not checkpoint.is_file():
        raise SystemExit(f"selected {checkpoint}, which does not exist")

    record = {
        "rule": "experiments/results/loco_foreign/PREREGISTRATION.md",
        "columns_read": list(READ),
        "config_means": {c: round(m, 4) for c, m in means.items()},
        "fold": fold, "fold_facts": folds[fold],
        "candidates": [{"seed": int(r["seed"]),
                        "val_macro_f1": float(r["val_macro_f1"])}
                       for r in candidates],
        "selected": {"config": config, "seed": seed, "fold": fold,
                     "checkpoint": str(checkpoint)},
        "runs_completed": len(rows), "runs_failed": failures,
    }
    out = args.results / "selection.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"\n  selected {checkpoint}")
    print(f"  {len(rows)} run(s) completed, {len(failures)} recorded as failed")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
