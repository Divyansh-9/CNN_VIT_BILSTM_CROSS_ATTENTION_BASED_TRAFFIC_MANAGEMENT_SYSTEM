"""30-seed benchmark across every controller (S38, FR-R07, FR-R08, PRD §14.3).

Every method runs on the **same seeds**, because a seed fixes the demand stream:
method A and method B on seed 7 face identical traffic. That pairing is the whole
reason 30 runs is enough to separate methods whose difference is smaller than the
between-seed spread — and the spread here is large.

    python scripts/benchmark.py --seeds 30 --regime saturated
    python scripts/benchmark.py --seeds 5 --duration 300     # quick check

Raw per-run rows are written to `experiments/results/benchmark_runs.csv` and the
pairwise statistics to `benchmark_stats.csv`. Re-running one regime replaces
only that regime's rows, so the files accumulate regimes rather than being
overwritten. **Both are committed** (NFR-09):
the paper's tables are generated from the CSVs by a committed script, never
transcribed from a printed summary.

PPO arms appear here automatically once checkpoints exist under `models/ppo/`.
Until then the table is the three classical baselines, which is exactly the
comparison the RL half must eventually beat — and having it first means the bar
was set before the agent was trained rather than after.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.results_io import merge_by_key  # noqa: E402
from experiments.statistics import compare  # noqa: E402
from simulation.controllers import Fixed, LongestQueue  # noqa: E402
from simulation.runner import run_episode  # noqa: E402
from simulation.webster import Webster, disqualification  # noqa: E402

RESULTS = Path("experiments/results")

# Webster at s=750 — the only configuration that qualified under ADR-012 rev 2's
# selection rule at the capacity knee. Using the sweep's naive best (s=1050)
# would put a 100%-clamped fixed cycle in this table under Webster's name.
WEBSTER_SATURATION = 750.0


def controllers() -> dict[str, callable]:
    """Factories, not instances — Webster accumulates clamp counts per episode.

    **`fixed` is deliberately untuned, and that is the point of it.** A 30 s
    green is not optimised for any of the three regimes and is not meant to be:
    it stands for the status-quo signal this project claims to improve on, which
    in the field is a cycle set once and left alone as demand changes around it.

    `webster` is the tuned-offline baseline — it recomputes cycle and split from
    measured flow, which is what a competent traffic engineer would deploy. The
    two are not redundant. Beating `fixed` shows the problem is real; beating
    `webster` shows the method is worth having. **Only the second is a result**,
    and any claim that cites `fixed` alone should be read as the weaker one.

    Stated here because an untuned fixed-time arm reads as a straw man when
    nothing says it was chosen to be untuned.
    """
    return {
        "fixed": lambda: Fixed(green_s=30),
        "longest_queue": lambda: LongestQueue(),
        "webster": lambda: Webster(saturation_flow_per_metre=WEBSTER_SATURATION),
    }


def run_benchmark(
    *,
    seeds: int = 30,
    regime: str = "saturated",
    duration_s: int = 1200,
    out: Path = RESULTS,
) -> tuple[list[dict], list[dict]]:
    factories = controllers()
    rows: list[dict] = []

    for seed in range(seeds):
        for name, factory in factories.items():
            controller = factory()
            result = run_episode(
                controller, regime=regime, seed=seed, duration_s=duration_s
            )
            row = result.as_row()
            row["method"] = name          # not controller.name — Webster encodes s
            if hasattr(controller, "clamp_rate"):
                row["clamp_rate"] = round(controller.clamp_rate, 4)
            rows.append(row)
        print(f"  seed {seed + 1}/{seeds} done", flush=True)

    out.mkdir(parents=True, exist_ok=True)
    verdicts = validate(rows)
    stats = analyse(rows, regime=regime, verdicts=verdicts)
    runs_path = merge_by_regime(out / "benchmark_runs.csv", rows, regime)
    stats_path = merge_by_regime(out / "benchmark_stats.csv", stats, regime)

    print(f"\n  wrote {runs_path}\n  wrote {stats_path}")
    return rows, stats


def merge_by_regime(path: Path, rows: list[dict], regime: str) -> Path:
    """Replace this regime's rows; leave every other regime untouched.

    Kept as a name because the tests and the P18 write-up refer to it, but the
    implementation now lives in `experiments.results_io` — `webster_sweep.py`
    and `screen_action_space.py` have the same fixed-filename shape, so the
    hazard was never specific to this script.
    """
    return merge_by_key(path, rows, regime, key="regime")



def validate(rows: list[dict]) -> dict[str, str]:
    """Per-method verdict under ADR-012's disqualifications. Empty string = citable.

    ADR-012 already defined when a measurement cannot be cited — a controller
    that clamped every decision is not running its method, and a mean wait over
    a run that completed a fraction of its trips excludes the vehicles that
    waited longest. Those checks lived only in `webster_sweep.py`, so **the
    reported comparison was never subject to them.**

    It should have been. Applied retrospectively, the three-regime benchmark
    contained a Webster arm at light demand clamping on 100% of decisions, and
    an oversaturated regime in which all three controllers finished under 85% of
    trips. Both were already-defined disqualifications that nothing checked
    because the rule sat in the wrong file.

    Verdicts are aggregated over seeds, matching how the comparison is reported:
    a single unlucky seed should not void a method, and a method that clamps on
    average is not rescued by one seed that did not.
    """
    aggregate: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = aggregate.setdefault(row["method"], {"arrived": [], "clamp": []})
        bucket["arrived"].append(float(row["arrived_fraction"]))
        if row.get("clamp_rate") not in ("", None):
            bucket["clamp"].append(float(row["clamp_rate"]))

    verdicts: dict[str, str] = {}
    for method, bucket in aggregate.items():
        summary = {"arrived_fraction": fmean(bucket["arrived"])}
        if bucket["clamp"]:
            summary["clamp_rate"] = fmean(bucket["clamp"])
        verdicts[method] = disqualification(summary) or ""
    return verdicts


def analyse(
    rows: list[dict],
    *,
    regime: str,
    verdicts: dict[str, str] | None = None,
    metric: str = "mean_wait_s",
) -> list[dict]:
    """Every pairwise comparison, keyed by seed so pairing cannot slip."""
    verdicts = verdicts or {}
    by_method: dict[str, dict[int, float]] = {}
    for row in rows:
        by_method.setdefault(row["method"], {})[int(row["seed"])] = float(row[metric])

    names = sorted(by_method)
    out: list[dict] = []
    print()

    disqualified = {m: why for m, why in verdicts.items() if why}
    if disqualified:
        print(f"  !! {len(disqualified)} method(s) DISQUALIFIED in '{regime}' "
              f"(ADR-012) — the comparisons below are printed but not citable:")
        for method, why in sorted(disqualified.items()):
            print(f"     {method}: {why}")
        print()

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            comparison = compare(
                by_method[a], by_method[b], name_a=a, name_b=b
            )
            print(comparison.summary(), "\n")
            row = comparison.as_row()
            row["regime"] = regime
            row["metric"] = metric
            # Carried into the CSV so a reader of the committed file sees the
            # disqualification without having to re-derive it, and so a paper
            # table generated from this file can exclude the rows itself.
            row["a_disqualified"] = verdicts.get(a, "")
            row["b_disqualified"] = verdicts.get(b, "")
            row["citable"] = not (verdicts.get(a) or verdicts.get(b))
            out.append(row)
    return out


def restat(out: Path = RESULTS) -> list[dict]:
    """Recompute `benchmark_stats.csv` from the committed `benchmark_runs.csv`.

    NFR-09/10 require the paper's tables to come from committed CSVs via a
    committed script. That only holds if the statistics can be regenerated
    without re-running 270 episodes — otherwise a change to how results are
    analysed becomes a change nobody re-derives, and the CSV and the analysis
    drift apart.

    Simulations are not re-run and raw rows are not touched. Only the derived
    statistics are rebuilt.
    """
    import csv

    runs = out / "benchmark_runs.csv"
    with runs.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{runs} is empty")

    stats: list[dict] = []
    for regime in sorted({row["regime"] for row in rows}):
        subset = [row for row in rows if row["regime"] == regime]
        print(f"\n=== {regime} ({len(subset)} runs) ===")
        stats += analyse(subset, regime=regime, verdicts=validate(subset))

    merge_rows = {regime: [s for s in stats if s["regime"] == regime]
                  for regime in {s["regime"] for s in stats}}
    for regime, regime_stats in merge_rows.items():
        merge_by_key(out / "benchmark_stats.csv", regime_stats, regime, key="regime")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=30, help="FR-R07 specifies 30")
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--duration", type=int, default=1200)
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument("--restat", action="store_true",
                        help="recompute statistics from the committed runs CSV; "
                             "runs no simulations")
    args = parser.parse_args(argv)

    if args.restat:
        restat(out=args.out)
        return 0

    run_benchmark(
        seeds=args.seeds, regime=args.regime,
        duration_s=args.duration, out=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
