"""Re-run the Webster saturation-flow sweep (ADR-012, post-P15).

    python scripts/webster_sweep.py --seeds 5

**Why this must be redone, and why it matters more than it did.** The original
sweep ran before P15 — `setPhase` without `setPhaseDuration`, so SUMO's built-in
program was driving the light and no Webster configuration was actually
controlling anything. Every row of that sweep described the same default cycle
under different labels.

Post-P15 Webster is the strongest baseline by a wide margin: **14.05 s against
fixed-time's 26.18 s, p < 0.00001, d = 2.94**. Which saturation flow it runs at
is therefore no longer a detail — it sets the bar PPO has to clear, and a bar set
too low would flatter the learned controller.

**The two disqualifications from ADR-012 still apply** and are enforced by
`webster.select_best`, not re-implemented here:

* a configuration clamping on more than half its decisions is not running
  Webster, it is running a fixed cycle wearing Webster's name;
* a low mean wait achieved while completing fewer trips is survivorship — the
  vehicles that waited longest never finished, so they never entered the average.

If nothing qualifies, that is the finding. No "Webster's best" claim is made.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ADR-012: no published value fits a mixed-traffic Indian approach, so the sweep
# brackets the plausible range rather than asserting one.
SATURATION_FLOWS = (525, 660, 750, 900, 1050, 1283)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--duration", type=int, default=1200)
    parser.add_argument("--out", type=Path,
                        default=Path("experiments/results/webster_sweep.csv"))
    args = parser.parse_args(argv)

    from simulation.runner import run_episode
    from simulation.webster import Webster, select_best

    rows = []
    print(f"  {'s (pcu/h/m)':>12}{'mean wait':>11}{'clamp rate':>12}"
          f"{'arrived':>9}{'queue':>8}")
    for flow in SATURATION_FLOWS:
        waits, clamps, arrived, queues = [], [], [], []
        for seed in range(1, args.seeds + 1):
            controller = Webster(saturation_flow_per_metre=float(flow))
            result = run_episode(controller, regime=args.regime, seed=seed,
                                 duration_s=args.duration)
            waits.append(result.mean_wait_s)
            arrived.append(result.arrived_fraction)
            queues.append(result.mean_queue)
            clamps.append(controller.clamps / max(controller.decisions, 1))

        row = {
            "saturation_flow_per_metre": flow,
            "seeds": args.seeds,
            "regime": args.regime,
            "mean_wait_s": round(statistics.fmean(waits), 3),
            "clamp_rate": round(statistics.fmean(clamps), 4),
            "arrived_fraction": round(statistics.fmean(arrived), 4),
            "mean_queue": round(statistics.fmean(queues), 3),
        }
        rows.append(row)
        print(f"  {flow:>12}{row['mean_wait_s']:>11.2f}{row['clamp_rate']:>12.1%}"
              f"{row['arrived_fraction']:>9.1%}{row['mean_queue']:>8.1f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    selection = select_best(rows)
    print()
    for row, reason in getattr(selection, "rejected", []):
        print(f"  REJECTED s={row['saturation_flow_per_metre']}: {reason}")
    best = getattr(selection, "best", None)
    if best:
        print(f"\n  SELECTED s={best['saturation_flow_per_metre']} "
              f"at {best['mean_wait_s']:.2f} s "
              f"(clamp {best['clamp_rate']:.1%}, arrived {best['arrived_fraction']:.1%})")
    else:
        print("\n  NOTHING QUALIFIES. Report the sweep and make no "
              "'Webster's best' claim (ADR-012).")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
