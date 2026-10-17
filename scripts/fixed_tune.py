"""P123 — tune the fixed-cycle comparator on `pulsed`, once, under its pre-registration.

    python scripts/fixed_tune.py

Implements `experiments/results/scenario_pulsed/PREREGISTRATION_P123_fixed.md`:

- greens of 10, 15, 20, 30, 45 and 60 s;
- tuning seeds 400-419, the same seeds as Webster's tuning (P121);
- ADR-012's survivorship rule;
- selection by the lowest mean `mean_total_delay_s`.

It refuses to run twice, or unless the pre-registration is committed unchanged.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.webster_tune import DURATION_S, METRIC, REGIME, SEEDS, committed_unchanged  # noqa: E402

ROOT = Path("experiments/results/scenario_pulsed")
PREREG = ROOT / "PREREGISTRATION_P123_fixed.md"
ROWS = ROOT / "fixed_tuning.csv"
SELECTION = ROOT / "fixed_selection.json"
GREENS = (10, 15, 20, 30, 45, 60)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from experiments.provenance import write_sidecar
    from simulation.controllers import Fixed
    from simulation.runner import run_episode
    from simulation.webster import select_best

    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    if SELECTION.exists():
        raise SystemExit(f"{SELECTION} exists: the tuning runs once (P123)")
    if not committed_unchanged(PREREG):
        raise SystemExit(f"{PREREG} must be committed, unchanged, before tuning")

    per_seed, summary = [], []
    for green in GREENS:
        runs = []
        for seed in SEEDS:
            row = run_episode(Fixed(green_s=green), regime=REGIME, seed=seed,
                              duration_s=DURATION_S, total_delay=True).as_row()
            row["green_s"] = green
            runs.append(row)
        per_seed += runs

        def mean(key):
            return round(statistics.fmean(float(r[key]) for r in runs), 4)

        summary.append({"green_s": green, "seeds": len(runs), METRIC: mean(METRIC),
                        "mean_wait_s": mean("mean_wait_s"),
                        "arrived_fraction": mean("arrived_fraction"),
                        "starvation_events": mean("starvation_events"),
                        "throughput": mean("throughput")})
        s = summary[-1]
        print(f"  green {green:>2} s: total delay {s[METRIC]:7.2f} s, wait "
              f"{s['mean_wait_s']:6.2f} s, arrived {s['arrived_fraction']:.3f}", flush=True)

    chosen = select_best(summary, metric=METRIC)            # greens ascending: ties go short
    with ROWS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_seed[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(per_seed)
    SELECTION.write_bytes((json.dumps({
        "protocol": "PREREGISTRATION_P123_fixed.md", "regime": REGIME, "seeds": list(SEEDS),
        "duration_s": DURATION_S, "lateral_resolution": 0.8, "rule": chosen.rule,
        "selected": chosen.best,
        "rejected": [{"row": r, "reason": why} for r, why in chosen.rejected],
        "summary": summary}, indent=2) + "\n").encode("utf-8"))
    write_sidecar(ROWS)
    print(f"\n  {chosen.rule}")
    print(f"  SELECTED green {chosen.best['green_s']} s: {chosen.best[METRIC]} s total delay"
          if chosen.best else "  NOTHING QUALIFIES: no fixed-cycle arm (P123)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
