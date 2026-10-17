"""P125 — select the clamped, demand-proportional Webster arm from committed tuning data.

    python scripts/select_clamped_webster.py

Implements `experiments/results/scenario_pulsed/PREREGISTRATION_P125_clamped.md`.

It reads P122's committed per-seed tuning rows and keeps the seven
configurations with 0 s lost time. It disqualifies any configuration that
completes fewer than 85% of trips, then selects the lowest mean
`mean_total_delay_s`, with ties going to the lower saturation flow.

**No episode is run.** The clamp-rate rule is deliberately not applied:
clamping defines this arm. It refuses to run twice, or before the
pre-registration is committed unchanged.
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

from scripts.webster_tune import committed_unchanged  # noqa: E402

ROOT = Path("experiments/results/scenario_pulsed")
PREREG = ROOT / "PREREGISTRATION_P125_clamped.md"
ROWS = ROOT / "webster_tuning.csv"
OUT = ROOT / "clamped_selection.json"
METRIC = "mean_total_delay_s"
MIN_ARRIVED = 0.85


def main(argv: list[str] | None = None) -> int:
    import argparse

    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: the selection runs once (P125)")
    if not committed_unchanged(PREREG) or not committed_unchanged(ROWS):
        raise SystemExit("the pre-registration and the tuning rows must be committed, unchanged")

    with ROWS.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if float(r["lost_time_startup_s"]) == 0.0]
    if {int(r["seed"]) for r in rows} & set(range(30)):
        raise SystemExit("tuning rows include evaluation seeds")
    summary = []
    for flow in sorted({int(r["saturation_flow"]) for r in rows}):
        runs = [r for r in rows if int(r["saturation_flow"]) == flow]

        def mean(key):
            return round(statistics.fmean(float(r[key]) for r in runs), 4)

        summary.append({"saturation_flow": flow, "lost_time_startup_s": 0.0, "seeds": len(runs),
                        METRIC: mean(METRIC), "mean_wait_s": mean("mean_wait_s"),
                        "clamp_rate": mean("clamp_rate"),
                        "arrived_fraction": mean("arrived_fraction")})
    qualified = [s for s in summary if s["arrived_fraction"] >= MIN_ARRIVED]
    best = min(qualified, key=lambda s: (s[METRIC], s["saturation_flow"])) if qualified else None
    OUT.write_bytes((json.dumps({
        "protocol": "PREREGISTRATION_P125_clamped.md", "source": str(ROWS),
        "label": "Webster split, clamped cycle (s, 0 s lost time)",
        "rule": (f"lowest mean {METRIC} among 0 s lost-time configurations with arrived "
                 f"fraction >= {MIN_ARRIVED}; clamp rule not applied; ties to lower s"),
        "selected": best,
        "rejected": [s for s in summary if s not in qualified],
        "summary": summary}, indent=2) + "\n").encode("utf-8"))
    for s in summary:
        print(f"  s={s['saturation_flow']:>5}: total delay {s[METRIC]:7.2f} s, clamp "
              f"{s['clamp_rate']:.0%}, arrived {s['arrived_fraction']:.3f}")
    print(f"\n  SELECTED s={best['saturation_flow']}, 0 s lost time: {best[METRIC]} s"
          if best else "\n  NOTHING QUALIFIES: no clamped arm (P125)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
