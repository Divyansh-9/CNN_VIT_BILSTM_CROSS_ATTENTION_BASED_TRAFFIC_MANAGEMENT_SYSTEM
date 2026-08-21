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
# PRD §14.4 specifies A-H across five seeds. 42 is the project seed (NFR-07);
# the other four are fixed here rather than drawn, so a rerun is a rerun.
DEFAULT_SEEDS = (42, 1, 7, 13, 21)


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
        folds = sorted({str(r.get("fold", "?")) for r in rows})
        seeds = sorted({str(r.get("seed", "?")) for r in rows})
        entry = {"config": config, "n_runs": len(rows), "n_folds": len(folds),
                 "n_seeds": len(seeds), "folds": " ".join(folds),
                 "seeds": " ".join(seeds)}
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
        # P57. Macro F1 divides by THREE classes and scores an absent one 0, so
        # a fold whose test camera has no HIGH window caps mechanically at
        # 0.667. A reader who does not know the convention reads 0.4977 as half
        # of 1.0 when it is three-quarters of what was reachable.
        #
        # Both conventions are derived here rather than added to `metrics.py`,
        # because the per-run CSVs already carry `f1_*` and `support_*` and a
        # suite is in flight — changing the columns mid-run would leave half the
        # fold files with one header and half with another.
        present = []
        ceilings = []
        highs = []
        for row in rows:
            supported = [c for c in ("low", "medium", "high")
                         if float(row.get(f"support_{c}", 0) or 0) > 0]
            if supported:
                present.append(sum(float(row[f"f1_{c}"]) for c in supported)
                               / len(supported))
                ceilings.append(len(supported) / 3)
            total = sum(float(row.get(f"support_{c}", 0) or 0)
                        for c in ("low", "medium", "high"))
            if total:
                highs.append(float(row.get("support_high", 0) or 0) / total)
        entry["macro_f1_present_mean"] = (
            round(sum(present) / len(present), 4) if present else "")
        entry["macro_f1_ceiling"] = (
            round(sum(ceilings) / len(ceilings), 4) if ceilings else "")
        entry["test_high_share"] = (
            round(sum(highs) / len(highs), 4) if highs else "")

        # P54. How far this config moved on ONE fold when only the seed
        # changed, averaged over folds. If it exceeds the distance between two
        # configs, the ablation has not separated them and the table should say
        # so rather than leaving a reader to rank rows that are noise apart.
        spreads = []
        for fold in folds:
            same = [float(r["macro_f1"]) for r in rows
                    if str(r.get("fold", "?")) == fold]
            if len(same) > 1:
                spreads.append(max(same) - min(same))
        entry["macro_f1_seed_spread"] = (
            round(sum(spreads) / len(spreads), 4) if spreads else "")

        # Per-run macro F1 in the summary too. A mean of 0.61 over folds of
        # 0.83 and 0.39 is a different result from four folds of 0.61, and the
        # interval alone does not distinguish them at n=4.
        entry["macro_f1_by_run"] = " ".join(
            f"{r.get('fold', '?')}/{r.get('seed', '?')}:{r['macro_f1']}"
            for r in sorted(rows,
                            key=lambda r: (str(r.get("fold")), str(r.get("seed")))))

        # ADR-022 asks for the four per-fold numbers beside the interval. Four
        # raw numbers are more honest than any CI computed over four numbers,
        # and the folds are not exchangeable — one has no HIGH window at all.
        by_fold = {}
        for row in rows:
            by_fold.setdefault(str(row.get("fold", "?")), []).append(
                float(row["macro_f1"]))
        entry["macro_f1_per_fold"] = " ".join(
            f"{fold}:{sum(v) / len(v):.4f}" for fold, v in sorted(by_fold.items()))
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
    parser.add_argument("--seeds", type=int, nargs="+", default=[42],
                        help="PRD §14.4 asks for five: 42 1 7 13 21. Defaults "
                             "to one so a quick look stays quick — but a "
                             "one-seed table is not an ablation (P54)")
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
        # Not a bare `fold*.csv` glob. P59's per-window files match it, and they
        # carry `config`, `seed` and `fold` columns of their own — so they would
        # be ingested as metrics rows without erroring, contributing 140 rows
        # per run to a summary that would look plausible and be nonsense.
        existing = sorted(p for p in args.out.glob("fold*.csv")
                          if not p.name.endswith(".predictions.csv"))
        if not existing:
            raise SystemExit(f"no fold CSVs under {args.out} to re-stat")
        summary = summarise(existing, args.summary)
    else:
        folds = fold_count(args.corpus, args.clips, args.min_test_sequences)

        # P55. One process per config, not one per fold. Eight models built
        # back to back in a single process ran a 6 GB card into a driver-level
        # access violation at a config that varied between runs, so the
        # `--ablation` flag is expanded here instead of being passed through:
        # a fresh interpreter is the only thing that reliably hands the whole
        # allocation back. It also means a crash costs one config rather than a
        # whole fold's worth of training.
        if args.ablation:
            from mfstnet.model import iter_ablation_configs

            configs = [c.name for c in iter_ablation_configs()]
        else:
            configs = [args.config]

        print(f"  {folds} fold(s) x {len(args.seeds)} seed(s) x "
              f"{len(configs)} config(s) = "
              f"{folds * len(args.seeds) * len(configs)} runs, "
              f"one process each (P55)")
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
            for seed in args.seeds:
                for config in configs:
                    target = (args.out /
                              f"fold{index}_seed{seed}_{config}.csv")
                    # Resumable, because this suite has now died three times to
                    # things outside it — twice to the machine sleeping, once to
                    # P55. 160 runs is four hours, and starting from zero each
                    # time is how a suite never finishes. A run counts as done
                    # only when BOTH artifacts exist: a metrics row without its
                    # per-window predictions is exactly the state P59 exists to
                    # prevent, so a half-written run is redone rather than kept.
                    predictions = target.with_name(
                        f"{target.stem}_{config}.predictions.csv")
                    if not args.force and target.exists() and predictions.exists():
                        written.append(target)
                        print(f"      fold {index} seed {seed} {config}  "
                              f"already done")
                        continue
                    command = [sys.executable, "-u",
                               "scripts/train_mfstnet.py",
                               "--corpus", str(view),
                               "--cache", str(args.cache),
                               "--device", args.device, "--seed", str(seed),
                               "--config", config, "--out", str(target)]
                    if args.epochs:
                        command += ["--epochs", str(args.epochs)]
                    if args.force:
                        command.append("--force")
                    subprocess.run(command, check=True)
                    written.append(target)
        summary = summarise(written, args.summary)

    print()
    print("  {:<8}{:>6}{:>6}{:>10}{:>20}{:>13}".format(
        "config", "folds", "seeds", "macroF1", "95% CI", "seed spread"))
    for entry in summary:
        interval = (f"[{entry['macro_f1_lo']}, {entry['macro_f1_hi']}]"
                    if entry["macro_f1_lo"] != "" else "-")
        print("  {:<8}{:>6}{:>6}{:>10}{:>20}{:>13}".format(
            entry["config"], entry["n_folds"], entry["n_seeds"],
            entry["macro_f1_mean"], interval,
            entry["macro_f1_seed_spread"] or "-"))

    # P54. Ranking rows that are noise apart is the failure this guards.
    spreads = [e["macro_f1_seed_spread"] for e in summary
               if e["macro_f1_seed_spread"] != ""]
    means = sorted(e["macro_f1_mean"] for e in summary
                   if e["macro_f1_mean"] != "")
    if spreads and len(means) > 1:
        closest = min(b - a for a, b in zip(means, means[1:]))
        if max(spreads) > closest:
            print()
            print(f"  WARNING  largest seed spread {max(spreads):.4f} exceeds "
                  f"the closest gap between")
            print(f"           two configs, {closest:.4f}. Those two are not "
                  f"separated by this table.")
    elif not spreads:
        print()
        print("  WARNING  one seed per fold. Config differences on this corpus "
              "have been")
        print("           measured smaller than seed-to-seed movement (P54); "
              "pass --seeds 42 1 7 13 21.")

    # P57. The class the controller exists to act on.
    ceilings = [e["macro_f1_ceiling"] for e in summary
                if e.get("macro_f1_ceiling") != ""]
    shares = [e["test_high_share"] for e in summary
              if e.get("test_high_share") != ""]
    if ceilings and min(ceilings) < 1.0:
        print()
        print(f"  WARNING  macro F1 is capped at {min(ceilings):.3f} on average, "
              f"not 1.0 — a test camera")
        print("           with no HIGH window scores that class 0 by convention. "
              "Report the")
        print("           ceiling beside the score, or the number reads as half "
              "of one.")
    if shares and min(shares) < 0.05:
        print(f"  WARNING  HIGH is {min(shares):.1%} of some fold's test split. "
              f"A signal controller")
        print("           acts on HIGH; a table that cannot separate it cannot "
              "bear on control.")
    print()
    print(f"  wrote {args.summary}")
    print("  Every fold's test split is ONE camera. The interval is over folds,")
    print("  not over sequences, and it is the number to quote (ADR-019).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
