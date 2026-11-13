"""ADR-022 Q1: does the architecture generalise better than its own floor?

    python scripts/gate_vs_probe.py --a G --b H

**Written and committed before the results exist.** ADR-022 fixed the test, the
aggregation order, the power calculation and the material threshold in advance
precisely so none of them could be chosen after seeing `loco_summary.csv`. That
is worth more if the *code* is also fixed in advance — a pre-registration that
leaves the analysis to be written afterwards has left the analysis free.

## The test, exactly as ADR-022 fixes it

1. within each fold, the **mean over seeds** for A and for B;
2. the **difference of those means** — one number per fold;
3. across folds, the paired mean and a bootstrap 95% CI.

Not the reverse order, and not pooled. With a seed spread of the magnitude P54
measured, averaging seeds first shrinks within-fold noise by about sqrt(seeds)
before the fold-level variance is estimated; the other order mixes seed noise
into the fold denominator, and the choice is worth about that factor.

## What it refuses to say

A non-significant result at n=4 is **not** evidence of equivalence. This prints
`CANNOT DISTINGUISH` with the minimum detectable difference beside it, and never
"equivalent" or "the gate adds nothing" — claims this design cannot support in
either direction.

The minimum detectable difference is `t_crit(df=n-1)/sqrt(n) * sd`, and on this
corpus it has been larger than the entire span of the config table (P70). When
that is true the honest output is that the experiment resolves nothing, which is
a statement about the experiment rather than about the architecture.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from experiments.statistics import bootstrap_ci  # noqa: E402

RESULTS = Path("experiments/results/loco")
OUT = Path("experiments/results/gate_vs_probe.csv")

# Two-sided 0.05 critical values, df = n - 1. Tabulated rather than computed so
# the numbers in ADR-022 and the numbers here are visibly the same.
T_CRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
          7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
MATERIAL = 0.05          # ADR-022, three-class-with-zeros convention


def per_fold_means(directory: Path, config: str) -> dict:
    """fold -> mean macro F1 over that fold's seeds. Step 1 of the order."""
    runs = {}
    for path in sorted(directory.glob("fold*.csv")):
        if path.name.endswith(".predictions.csv"):
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["config"] != config:
                    continue
                runs.setdefault(str(row.get("fold", "?")), []).append(
                    float(row["macro_f1"]))
    return {fold: statistics.fmean(v) for fold, v in runs.items()}, runs


def minimum_detectable(sd: float, n: int) -> float:
    """`t_crit(df=n-1)/sqrt(n) * sd`. The gap this design could resolve."""
    if n < 2:
        return float("inf")
    return T_CRIT.get(n - 1, 1.96) / (n ** 0.5) * sd


def compare(directory: Path, a: str, b: str) -> dict:
    a_means, a_runs = per_fold_means(directory, a)
    b_means, b_runs = per_fold_means(directory, b)
    folds = sorted(set(a_means) & set(b_means))
    if not folds:
        raise SystemExit(
            f"no fold has both {a} and {b}. Run the suite first — "
            f"scripts/run_loco.py --ablation --seeds 42 1 7 13 21"
        )

    differences = [a_means[f] - b_means[f] for f in folds]        # step 2
    n = len(differences)
    mean, low, high = bootstrap_ci(differences)                   # step 3
    sd = statistics.stdev(differences) if n > 1 else float("nan")
    mdd = minimum_detectable(sd, n) if n > 1 else float("inf")

    separated = n > 1 and (low > 0 or high < 0)
    material = separated and abs(mean) >= MATERIAL
    return {
        "a": a, "b": b, "n_folds": n,
        "seeds_per_fold": min(len(v) for v in list(a_runs.values())
                              + list(b_runs.values())),
        "folds": " ".join(folds),
        "difference_per_fold": " ".join(
            f"{f}:{a_means[f] - b_means[f]:+.4f}" for f in folds),
        "mean_difference": round(mean, 4),
        "ci_low": round(low, 4), "ci_high": round(high, 4),
        "sd_of_fold_differences": round(sd, 4) if n > 1 else "",
        "minimum_detectable_difference": round(mdd, 4) if n > 1 else "",
        "material_threshold": MATERIAL,
        "interval_excludes_zero": separated,
        "material": material,
        "verdict": ("MATERIAL" if material
                    else "SEPARATED BUT NOT MATERIAL" if separated
                    else "CANNOT DISTINGUISH"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dir", type=Path, default=RESULTS)
    parser.add_argument("--a", default="G", help="the fuller architecture")
    parser.add_argument("--b", default="H", help="the floor (A22's linear probe)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    result = compare(args.dir, args.a, args.b)

    print(f"  ADR-022 Q1 — does {args.a} generalise better than {args.b}?")
    print(f"  aggregation: mean over seeds within fold, then difference, "
          f"then across folds")
    print()
    print(f"  folds                {result['n_folds']}  "
          f"({result['seeds_per_fold']} seed(s) each)")
    print(f"  per fold             {result['difference_per_fold']}")
    print(f"  mean difference      {result['mean_difference']:+.4f}")
    print(f"  95% CI               [{result['ci_low']:+.4f}, "
          f"{result['ci_high']:+.4f}]")
    if result["sd_of_fold_differences"] != "":
        print(f"  sd of fold diffs     {result['sd_of_fold_differences']:.4f}")
        print(f"  min detectable diff  "
              f"{result['minimum_detectable_difference']:.4f}   "
              f"<- what this design could resolve")
    print()
    print(f"  VERDICT: {result['verdict']}")

    if result["verdict"] == "CANNOT DISTINGUISH":
        print()
        print("  This is NOT evidence of equivalence. The design is underpowered:")
        print(f"  it could only resolve a difference of "
              f"{result['minimum_detectable_difference']}, and the observed one is")
        print(f"  {abs(result['mean_difference']):.4f}. Report it as underpowered "
              f"to separate,")
        print("  never as 'equivalent' or 'the gate adds nothing' (ADR-022).")
    elif result["verdict"] == "SEPARATED BUT NOT MATERIAL":
        print()
        print(f"  The interval excludes zero, but the difference is below the "
              f"pre-registered")
        print(f"  material threshold of {MATERIAL}. At this n a significant "
              f"result on a gap")
        print("  this small is a small-sample artifact before it is a finding.")

    print()
    print("  Q1 is the number that bears on the architecture. Q2 "
          "(scripts/discordance.py)")
    print("  answers a different question and cannot substitute for it.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
