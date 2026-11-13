"""ADR-022 Q2: do two configs decide differently, on the windows we have?

    python scripts/discordance.py --a G --b H

Q1 — does the architecture generalise to an unseen camera — is answered by
`run_loco.py` over four fold means and is underpowered by construction. Q2 is a
different question with a different unit: **given the 572 lane-windows actually
evaluated, do G and H produce different decisions at all?**

The headline is the **discordance count**. It needs no distributional
assumption: if two configs disagree on nine windows out of 572, that is a
complete description of the difference between them and a *p*-value adds
nothing.

**McNemar's `p` is reported with its assumption violated, and said so.** It
treats the windows as independent and they are emphatically not — consecutive
windows from one camera share 54 of 60 frames (A28). It will overstate
significance, possibly by a large factor. It is here because "decision-identical"
and "different, but the fold test cannot see it" are distinct situations that Q1
alone cannot separate, and **it cannot support a generalisation claim.**

## The reproduction check, which runs first and cannot be skipped

The predictions this reads may come from runs made after the metrics table was
published. If seeding or determinism has drifted even slightly, Q1 and Q2 would
describe **different models**, and the discordance count would not be about the
table in the paper.

So before anything is computed, every predictions file is re-scored and its
metrics compared against the committed row for the same config, fold and seed.
**Any mismatch refuses the whole run.** A discordance count from unverified
predictions is worse than no discordance count, because it looks like evidence.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.metrics import evaluate  # noqa: E402

CLASSES = ("LOW", "MEDIUM", "HIGH")
RESULTS = Path("experiments/results/loco")
TOLERANCE = 1e-4          # the committed CSVs round to four decimals


def load_predictions(directory: Path, config: str) -> dict:
    """(fold, seed) -> ordered list of prediction records for `config`."""
    found = collections.defaultdict(list)
    for path in sorted(directory.glob(f"*_{config}.predictions.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                found[(row["fold"], row["seed"])].append(row)
    return found


def load_metrics(directory: Path, config: str) -> dict:
    """(fold, seed) -> the committed metrics row for `config`."""
    found = {}
    for path in sorted(directory.glob("fold*.csv")):
        if path.name.endswith(".predictions.csv"):
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["config"] == config:
                    found[(str(row.get("fold", "")), str(row.get("seed", "")))] = row
    return found


def verify_reproduction(config: str, predictions: dict, metrics: dict) -> list[str]:
    """Re-score every predictions file and compare with the committed row.

    Returns a list of problems. Empty means the predictions describe the same
    models the published table describes.
    """
    problems = []
    for key, records in sorted(predictions.items()):
        row = metrics.get(key)
        if row is None:
            problems.append(
                f"{config} fold {key[0]} seed {key[1]}: predictions exist with "
                f"no committed metrics row to check them against")
            continue
        true = [CLASSES.index(r["true"]) for r in records]
        pred = [CLASSES.index(r["pred"]) for r in records]
        report = evaluate(true, pred, CLASSES)
        for field, got in (("macro_f1", report.macro_f1),
                           ("accuracy", report.accuracy),
                           ("qwk", report.qwk)):
            want = float(row[field])
            if abs(round(got, 4) - want) > TOLERANCE:
                problems.append(
                    f"{config} fold {key[0]} seed {key[1]}: {field} re-scores to "
                    f"{got:.4f} against a committed {want:.4f}. These "
                    f"predictions are not the model the table describes.")
    missing = sorted(set(metrics) - set(predictions))
    if missing:
        problems.append(
            f"{config}: {len(missing)} committed run(s) have no predictions "
            f"file — {missing[:3]}. Re-run those before computing discordance, "
            f"or the comparison covers a different set of runs than the table.")
    return problems


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided binomial test on the discordant pairs.

    Exact rather than the chi-square approximation because the discordant count
    here is expected to be small, and the approximation is poor below about 25.
    """
    from math import comb

    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dir", type=Path, default=RESULTS)
    parser.add_argument("--a", default="G")
    parser.add_argument("--b", default="H")
    parser.add_argument("--out", type=Path,
                        default=Path("experiments/results/discordance.csv"))
    args = parser.parse_args(argv)

    predictions = {c: load_predictions(args.dir, c) for c in (args.a, args.b)}
    metrics = {c: load_metrics(args.dir, c) for c in (args.a, args.b)}

    for config in (args.a, args.b):
        if not predictions[config]:
            raise SystemExit(
                f"no {config} predictions under {args.dir}. Runs made before "
                f"P59 did not write them, and a metrics row cannot be "
                f"un-aggregated into the decisions behind it — re-run {config}."
            )

    problems = []
    for config in (args.a, args.b):
        problems += verify_reproduction(config, predictions[config],
                                        metrics[config])
    if problems:
        print("  REPRODUCTION CHECK FAILED — refusing to compute discordance\n")
        for problem in problems:
            print(f"    {problem}")
        print("\n  A discordance count from unverified predictions is worse "
              "than none:")
        print("  it looks like evidence.")
        return 1
    print(f"  reproduction check passed for {args.a} and {args.b}\n")

    shared = sorted(set(predictions[args.a]) & set(predictions[args.b]))
    rows, totals = [], collections.Counter()
    for key in shared:
        a_rows, b_rows = predictions[args.a][key], predictions[args.b][key]
        if len(a_rows) != len(b_rows):
            raise SystemExit(f"fold {key[0]} seed {key[1]}: {len(a_rows)} vs "
                             f"{len(b_rows)} windows — not the same test split")
        b_only = sum(1 for x, y in zip(a_rows, b_rows)
                     if x["correct"] == "0" and y["correct"] == "1")
        a_only = sum(1 for x, y in zip(a_rows, b_rows)
                     if x["correct"] == "1" and y["correct"] == "0")
        differ = sum(1 for x, y in zip(a_rows, b_rows) if x["pred"] != y["pred"])
        rows.append({
            "fold": key[0], "seed": key[1], "n_windows": len(a_rows),
            "different_predictions": differ,
            f"{args.a}_right_{args.b}_wrong": a_only,
            f"{args.b}_right_{args.a}_wrong": b_only,
            "mcnemar_p_INDEPENDENCE_VIOLATED": round(mcnemar(a_only, b_only), 5),
        })
        totals["n"] += len(a_rows)
        totals["differ"] += differ
        totals["a_only"] += a_only
        totals["b_only"] += b_only

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {args.a} vs {args.b} over {len(shared)} run pair(s), "
          f"{totals['n']} lane-windows")
    print(f"  different predictions: {totals['differ']} "
          f"({totals['differ'] / max(totals['n'], 1):.2%})")
    print(f"  {args.a} right / {args.b} wrong: {totals['a_only']}")
    print(f"  {args.b} right / {args.a} wrong: {totals['b_only']}")
    print(f"  McNemar exact p = {mcnemar(totals['a_only'], totals['b_only']):.5f}"
          f"   <- INDEPENDENCE VIOLATED")
    print()
    print("  The discordance count is the reportable number. McNemar's p treats")
    print("  windows as independent; consecutive windows share 54 of 60 frames,")
    print("  so it overstates significance and CANNOT support a generalisation")
    print("  claim (ADR-022 Q2). Q1 is the number that bears on the architecture.")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
