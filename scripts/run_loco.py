"""Run the ablation once per camera fold and aggregate (ADR-019).

    python scripts/run_loco.py --corpus data/corpus --clips data/_corpus_clips \
        --cache data/cache_corpus --ablation --device cuda

`train_mfstnet.py` trains against one corpus directory holding one split.
ADR-019 replaces the single 60/20/20 draw with leave-one-camera-out, so the same
training runs once per fold against a fold view produced by
`resplit_corpus.py`. This drives that loop and then writes the aggregate.

**The aggregate is generated, never transcribed** (NFR-09/10, BR-18). Each fold
writes its own CSV; the summary is computed from those files by this script, so
regenerating it cannot drift from the runs it describes. Deleting the summary
and re-running `--restat` rebuilds it without retraining.

**Why the mean over folds and not the pooled predictions.** Pooling every fold's
test predictions into one confusion matrix weights each camera by how many
windows it happens to contribute, and one camera holds 41% of this corpus. The
fold mean weights each camera equally, which is the quantity the paper claims:
how the model does *on a camera it has not seen*, not how it does on this
particular mixture of cameras.

The interval is a bootstrap over **four folds**, and four is a small sample for
a percentile bootstrap. It is reported because NFR-10 requires an interval, and
it is reported with `n_folds` beside it because an interval over four points
says less than one over thirty and should not be read as if it said the same.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from experiments.statistics import bootstrap_ci  # noqa: E402
from mfstnet.corpus.folds import MINIMUM_TEST_SEQUENCES  # noqa: E402

RESULTS = Path("experiments/results/loco")
SUMMARY = Path("experiments/results/loco_summary.csv")
AGGREGATED = ("macro_f1", "weighted_f1", "accuracy", "qwk", "ordinal_mae",
              "off_by_two_rate", "gate_mean", "gate_std")


def fold_count(corpus: Path, clips: Path, minimum: int) -> int:
    """Ask `resplit_corpus.py` rather than recomputing camera identity here.

    Two implementations of "how many folds are there" is one more than can be
    kept in agreement, and the answer depends on scene signatures read from the
    footage.
    """
    result = subprocess.run(
        [sys.executable, "scripts/resplit_corpus.py", "--corpus", str(corpus),
         "--clips", str(clips), "--fold", "0", "--out", str(RESULTS / "_probe"),
         "--min-test-sequences", str(minimum), "--list"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)
    for line in result.stdout.splitlines():
        if "fold(s)" in line:
            return int(line.split(",")[-1].strip().split()[0])
    raise SystemExit("could not read the fold count from resplit_corpus.py: "
                     + result.stdout)


def summarise(fold_files: list[Path], out: Path) -> list[dict]:
    """Mean and bootstrap 95% CI per config, across folds."""
    by_config: dict[str, list[dict]] = {}
    for path in fold_files:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                by_config.setdefault(row["config"], []).append(row)
    if not by_config:
        raise SystemExit("the fold CSVs hold no rows")

    summary = []
    for config, rows in sorted(by_config.items()):
        entry = {"config": config, "n_folds": len(rows),
                 "folds": " ".join(sorted(str(r.get("fold", "?")) for r in rows))}
        for field in AGGREGATED:
            values = [float(r[field]) for r in rows
                      if r.get(field) not in (None, "", "None")]
            if not values:
                entry[f"{field}_mean"] = ""
                entry[f"{field}_lo"] = entry[f"{field}_hi"] = ""
                continue
            mean, low, high = bootstrap_ci(values)
            entry[f"{field}_mean"] = round(mean, 4)
            entry[f"{field}_lo"] = round(low, 4)
            entry[f"{field}_hi"] = round(high, 4)
        # Per-fold macro F1 in the summary too. A mean of 0.61 over folds of
        # 0.83 and 0.39 is a different result from four folds of 0.61, and the
        # interval alone does not distinguish them at n=4.
        entry["macro_f1_by_fold"] = " ".join(
            f"{r.get('fold', '?')}:{r['macro_f1']}"
            for r in sorted(rows, key=lambda r: str(r.get("fold"))))
        summary.append(entry)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--clips", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--config", default="G")
    parser.add_argument("--ablation", action="store_true")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-test-sequences", type=int,
                        default=MINIMUM_TEST_SEQUENCES)
    parser.add_argument("--views", type=Path, default=Path("data/corpus_loco"))
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--restat", action="store_true",
                        help="rebuild the summary from existing fold CSVs "
                             "without retraining anything")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    if args.restat:
        existing = sorted(args.out.glob("fold*.csv"))
        if not existing:
            raise SystemExit(f"no fold CSVs under {args.out} to re-stat")
        summary = summarise(existing, args.summary)
    else:
        folds = fold_count(args.corpus, args.clips, args.min_test_sequences)
        print(f"  {folds} fold(s), min {args.min_test_sequences} test window(s) "
              f"per camera (ADR-019)")
        print()
        written = []
        for index in range(folds):
            view = args.views / f"fold{index}"
            print(f"  --- fold {index}: building view {view}")
            subprocess.run(
                [sys.executable, "scripts/resplit_corpus.py",
                 "--corpus", str(args.corpus), "--clips", str(args.clips),
                 "--fold", str(index), "--out", str(view),
                 "--min-test-sequences", str(args.min_test_sequences)],
                check=True,
            )
            target = args.out / f"fold{index}.csv"
            command = [sys.executable, "scripts/train_mfstnet.py",
                       "--corpus", str(view), "--cache", str(args.cache),
                       "--device", args.device, "--seed", str(args.seed),
                       "--out", str(target)]
            if args.ablation:
                command.append("--ablation")
            else:
                command += ["--config", args.config]
            if args.epochs:
                command += ["--epochs", str(args.epochs)]
            if args.force:
                command.append("--force")
            subprocess.run(command, check=True)
            written.append(target)
        summary = summarise(written, args.summary)

    print()
    print("  {:<8}{:>8}{:>10}{:>20}{:>10}".format(
        "config", "folds", "macroF1", "95% CI", "QWK"))
    for entry in summary:
        interval = (f"[{entry['macro_f1_lo']}, {entry['macro_f1_hi']}]"
                    if entry["macro_f1_lo"] != "" else "-")
        print("  {:<8}{:>8}{:>10}{:>20}{:>10}".format(
            entry["config"], entry["n_folds"], entry["macro_f1_mean"],
            interval, entry["qwk_mean"]))
    print()
    print(f"  wrote {args.summary}")
    print("  Every fold's test split is ONE camera. The interval is over folds,")
    print("  not over sequences, and it is the number to quote (ADR-019).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
