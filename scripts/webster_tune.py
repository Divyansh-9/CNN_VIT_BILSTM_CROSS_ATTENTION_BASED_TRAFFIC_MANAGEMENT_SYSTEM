"""P121 — tune Webster on `pulsed`, once, under its pre-registration.

    python scripts/webster_tune.py

Implements `experiments/results/scenario_pulsed/PREREGISTRATION_P121_webster.md`:

- 7 saturation flows × 2 start-up lost times;
- 20 tuning seeds (400-419), disjoint from evaluation, qualification, design
  and training;
- ADR-012's disqualifications;
- selection by the lowest mean `mean_total_delay_s` (ADR-021 A1.5).

It writes the per-seed rows, the selection, and a provenance sidecar. It
refuses to run twice, or unless the pre-registration is committed unchanged.
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/scenario_pulsed")
PREREG = ROOT / "PREREGISTRATION_P121_webster.md"
ROWS = ROOT / "webster_tuning.csv"
SELECTION = ROOT / "webster_selection.json"
REGIME = "pulsed"
SATURATION_FLOWS = (525, 600, 660, 750, 900, 1050, 1283)
LOST_TIMES = (0.0, 4.0)
SEEDS = tuple(range(400, 420))
DURATION_S = 1800
METRIC = "mean_total_delay_s"


def committed_unchanged(path: Path) -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path)]).returncode == 0
    return tracked and clean


def main(argv: list[str] | None = None) -> int:
    import argparse

    from experiments.provenance import write_sidecar
    from simulation.runner import run_episode
    from simulation.webster import Webster, select_best

    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    if SELECTION.exists():
        raise SystemExit(f"{SELECTION} exists: the tuning runs once (P121)")
    if not committed_unchanged(PREREG):
        raise SystemExit(f"{PREREG} must be committed, unchanged, before tuning")
    if set(SEEDS) & set(range(30)):
        raise SystemExit("tuning seeds overlap the evaluation seeds 0-29")

    per_seed, summary = [], []
    for flow in SATURATION_FLOWS:
        for lost in LOST_TIMES:
            runs = []
            for seed in SEEDS:
                controller = Webster(saturation_flow_per_metre=float(flow),
                                     lost_time_startup_s=lost)
                row = run_episode(controller, regime=REGIME, seed=seed,
                                  duration_s=DURATION_S, total_delay=True).as_row()
                row.update({"saturation_flow": flow, "lost_time_startup_s": lost,
                            "clamp_rate": round(controller.clamp_rate, 4)})
                runs.append(row)
            per_seed += runs

            def mean(key):
                return round(statistics.fmean(float(r[key]) for r in runs), 4)

            summary.append({"saturation_flow": flow, "lost_time_startup_s": lost,
                            "seeds": len(runs), METRIC: mean(METRIC),
                            "mean_wait_s": mean("mean_wait_s"), "clamp_rate": mean("clamp_rate"),
                            "arrived_fraction": mean("arrived_fraction"),
                            "starvation_events": mean("starvation_events"),
                            "throughput": mean("throughput")})
            s = summary[-1]
            print(f"  s={flow:>5} lost={lost:>3}: total delay {s[METRIC]:7.2f} s, wait "
                  f"{s['mean_wait_s']:6.2f} s, clamp {s['clamp_rate']:.0%}, arrived "
                  f"{s['arrived_fraction']:.3f}", flush=True)

    ordered = sorted(summary, key=lambda r: (r["saturation_flow"], r["lost_time_startup_s"]))
    chosen = select_best(ordered, metric=METRIC)            # min() keeps the first of ties
    by_wait = select_best(ordered, metric="mean_wait_s")

    ROWS.parent.mkdir(parents=True, exist_ok=True)
    fields = list(per_seed[0])
    with ROWS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(per_seed)
    SELECTION.write_bytes((json.dumps({
        "protocol": "PREREGISTRATION_P121_webster.md", "regime": REGIME,
        "seeds": list(SEEDS), "duration_s": DURATION_S, "lateral_resolution": 0.8,
        "rule": chosen.rule, "selected": chosen.best,
        "rejected": [{"row": r, "reason": why} for r, why in chosen.rejected],
        "summary": summary,
        "reported_mean_wait_rule_would_select": by_wait.best,
    }, indent=2) + "\n").encode("utf-8"))
    write_sidecar(ROWS)
    print(f"\n  {chosen.rule}")
    if chosen.best:
        print(f"  SELECTED s={chosen.best['saturation_flow']} lost="
              f"{chosen.best['lost_time_startup_s']}: {chosen.best[METRIC]} s total delay")
    else:
        print("  NOTHING QUALIFIES: no Webster's best is claimed (P121)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
