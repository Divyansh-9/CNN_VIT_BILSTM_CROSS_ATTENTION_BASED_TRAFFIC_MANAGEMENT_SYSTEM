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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.results_io import merge_by_key  # noqa: E402
from experiments.statistics import compare  # noqa: E402
from simulation.controllers import Fixed, LongestQueue  # noqa: E402
from simulation.runner import run_episode  # noqa: E402
from simulation.webster import Webster  # noqa: E402

RESULTS = Path("experiments/results")

# Webster at s=750 — the only configuration that qualified under ADR-012 rev 2's
# selection rule at the capacity knee. Using the sweep's naive best (s=1050)
# would put a 100%-clamped fixed cycle in this table under Webster's name.
WEBSTER_SATURATION = 750.0


def controllers() -> dict[str, callable]:
    """Factories, not instances — Webster accumulates clamp counts per episode."""
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
    stats = analyse(rows, regime=regime)
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



def analyse(rows: list[dict], *, regime: str, metric: str = "mean_wait_s") -> list[dict]:
    """Every pairwise comparison, keyed by seed so pairing cannot slip."""
    by_method: dict[str, dict[int, float]] = {}
    for row in rows:
        by_method.setdefault(row["method"], {})[int(row["seed"])] = float(row[metric])

    names = sorted(by_method)
    out: list[dict] = []
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
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=30, help="FR-R07 specifies 30")
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--duration", type=int, default=1200)
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    run_benchmark(
        seeds=args.seeds, regime=args.regime,
        duration_s=args.duration, out=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
