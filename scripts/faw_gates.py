"""P132 — the FAW study's two gates, each run once under the pre-registration.

    python scripts/faw_gates.py feasibility    # C1: seeds 600-609
    python scripts/faw_gates.py power          # C2: seeds 610-639, only after C1 passed

Implements `experiments/results/faw/PREREGISTRATION_P132_faw.md` §4 and §5.

**It refuses** if the pre-registration is not committed unchanged, or if the
gate's result already exists. Power refuses unless feasibility passed.

**It evaluates nothing:** the evaluation (C4) is not authorised.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.ceiling_eval import committed_unchanged  # noqa: E402

ROOT = Path("experiments/results/faw")
PREREG = ROOT / "PREREGISTRATION_P132_faw.md"
FEASIBILITY = ROOT / "faw_feasibility.json"
POWER = ROOT / "faw_power.json"
REGIME, DURATION_S, RECORD_S = "pulsed", 1800, 1875
DESIGN_SEEDS = tuple(range(600, 610))
PILOT_SEEDS = tuple(range(610, 640))
CHANGE_S, GATE_SHARE = 1, 0.10
MEI, ALPHA, POWER_TARGET, N_MAX, N_MIN = 0.02, 0.025, 0.80, 200, 30


def make_now():
    from simulation.webster import Webster

    return Webster(saturation_flow_per_metre=600.0, lost_time_startup_s=0.0)


def write(path: Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes((json.dumps(body, indent=2, default=float) + "\n").encode("utf-8"))
    tmp.replace(path)


def preflight(target: Path) -> None:
    if target.exists():
        raise SystemExit(f"{target} exists: this gate runs once (P132)")
    if not committed_unchanged(PREREG):
        raise SystemExit(f"{PREREG} must be committed, unchanged, before any gate runs")


class Probe:
    """W-now, recording each decision's time, phase, green and observed counts."""

    def __init__(self) -> None:
        self.inner = make_now()
        self.name = "W-now"
        self.series: dict[int, tuple] = {}
        self.decisions: list[tuple] = []

    @property
    def clamp_rate(self) -> float:
        return self.inner.clamp_rate

    def reset(self) -> None:
        self.inner.reset()
        self.series, self.decisions = {}, []

    def observe_second(self, step: int, counts: dict) -> None:
        self.series[int(step)] = tuple(counts[a] for a in "NSEW")

    def decide(self, observation: dict):
        phase, green = self.inner.decide(observation)
        self.decisions.append((int(observation["step"]), phase, green,
                               dict(observation["counts"])))
        return phase, green


def feasibility() -> int:
    from simulation.count_forecasts import RidgeCountDemand, next_minute_mean
    from simulation.runner import run_episode

    preflight(FEASIBILITY)
    rule = make_now()                                          # pure arithmetic only
    counted = changed = changed3 = 0
    abs_delta, ridge_counted, ridge_changed, ridge_ready_total = [], 0, 0, 0
    # No oracle MAE: on W-now's own trajectory the oracle is that future exactly.
    mae = {"ridge": [], "persistence": []}
    clamps, per_seed = [], {}
    for seed in DESIGN_SEEDS:
        probe = Probe()
        run_episode(probe, regime=REGIME, seed=seed, duration_s=RECORD_S)
        last = max(probe.series)
        series = [probe.series[s] for s in range(last + 1)]   # KeyError on any gap
        ridge = RidgeCountDemand()
        for s in range(last + 1):
            ridge.observe_second(s, dict(zip("NSEW", series[s])))
        seed_counted = seed_changed = 0
        for t, phase, green_now, counts in probe.decisions:
            if t >= DURATION_S:
                continue
            if rule.green_for(counts, phase)[0] != green_now:
                raise SystemExit(f"seed {seed} t={t}: green_for does not reproduce W-now's "
                                 f"green; the counterfactual would not be comparable (P132 §4)")
            real = next_minute_mean(series, t)
            green_oracle = rule.green_for(real, phase)[0]
            delta = abs(green_oracle - green_now)
            counted += 1
            seed_counted += 1
            changed += delta >= CHANGE_S
            seed_changed += delta >= CHANGE_S
            changed3 += delta >= 3
            abs_delta.append(delta)
            forecast = ridge({"step": t, "counts": counts})
            for a in "NSEW":
                mae["persistence"].append(abs(counts[a] - real[a]))
            if t >= 118:                                       # ridge has 60 samples, 2 s apart
                ridge_ready_total += 1
                ridge_counted += 1
                ridge_changed += abs(rule.green_for(forecast, phase)[0] - green_now) >= CHANGE_S
                for a in "NSEW":
                    mae["ridge"].append(abs(forecast[a] - real[a]))
        clamps.append(probe.clamp_rate)
        per_seed[seed] = {"decisions_counted": seed_counted, "changed_oracle": seed_changed}
        print(f"  seed {seed}: {seed_counted} decisions, {seed_changed} oracle-changed splits",
              flush=True)
    share = changed / counted
    passed = share >= GATE_SHARE
    body = {"protocol": "PREREGISTRATION_P132_faw.md section 4", "gate": "C1 feasibility",
            "seeds": list(DESIGN_SEEDS), "decisions_counted": counted,
            "changed_split_definition": f"|green_oracle - green_now| >= {CHANGE_S} s",
            "changed_oracle": changed, "changed_share_oracle": share,
            "threshold": GATE_SHARE, "passed": passed,
            "reported": {
                "share_changed_by_3s_or_more": changed3 / counted,
                "mean_abs_delta_green_s": statistics.fmean(abs_delta),
                "ridge_ready_decisions": ridge_ready_total,
                "ridge_ready_share": ridge_ready_total / counted,
                "changed_share_ridge_over_ready": (ridge_changed / ridge_counted
                                                   if ridge_counted else None),
                "mae_vs_realised_next_minute_mean": {k: (statistics.fmean(v) if v else None)
                                                     for k, v in mae.items()},
                "w_now_clamp_rate": statistics.fmean(clamps)},
            "per_seed": per_seed}
    write(FEASIBILITY, body)
    print(f"\n  C1: {changed}/{counted} = {share:.3f} of splits changed by the oracle "
          f"(gate {GATE_SHARE}): {'PASS' if passed else 'STOP: the study ends here (P132 §4)'}")
    return 0 if passed else 1


def required_n(delta: float, sd: float) -> int | None:
    from scipy import stats

    if sd <= 0:
        return 2
    effect = delta / sd
    for n in range(2, 100_000):
        df = n - 1
        crit = stats.t.ppf(1 - ALPHA / 2, df)
        nc = effect * n ** 0.5
        power = (1 - stats.nct.cdf(crit, df, nc)) + stats.nct.cdf(-crit, df, nc)
        if power >= POWER_TARGET:
            return n
    return None


def power() -> int:
    from simulation.count_forecasts import (ForecastWebster, OracleMeanCount, RidgeCountDemand,
                                            baseline_series)
    from simulation.runner import run_episode

    preflight(POWER)
    if not FEASIBILITY.exists() or not json.loads(FEASIBILITY.read_text(encoding="utf-8"))["passed"]:
        raise SystemExit("C1 has not passed; C2 does not run (P132 §5)")
    rows = []
    for seed in PILOT_SEEDS:
        now = run_episode(make_now(), regime=REGIME, seed=seed, duration_s=DURATION_S,
                          total_delay=True).as_row()
        series = baseline_series(make_now, REGIME, seed, RECORD_S)
        oracle_ctrl = ForecastWebster(make_now(), OracleMeanCount(series), "W-oracle")
        oracle = run_episode(oracle_ctrl, regime=REGIME, seed=seed, duration_s=DURATION_S,
                             total_delay=True).as_row()
        ridge_ctrl = ForecastWebster(make_now(), RidgeCountDemand(), "W-ridge")
        ridge = run_episode(ridge_ctrl, regime=REGIME, seed=seed, duration_s=DURATION_S,
                            total_delay=True).as_row()
        rows.append({"seed": seed, "now": now["mean_total_delay_s"],
                     "oracle": oracle["mean_total_delay_s"], "ridge": ridge["mean_total_delay_s"],
                     "arrived": {"now": now["arrived_fraction"], "oracle": oracle["arrived_fraction"],
                                 "ridge": ridge["arrived_fraction"]},
                     "oracle_transfer": oracle_ctrl.transfer_report(),
                     "ridge_transfer": ridge_ctrl.transfer_report()})
        print(f"  seed {seed}: done", flush=True)
    diffs = [r["oracle"] - r["now"] for r in rows]
    mean_now = statistics.fmean(r["now"] for r in rows)
    delta = MEI * mean_now
    sd = statistics.stdev(diffs)
    n = required_n(delta, sd)
    passed = n is not None and n <= N_MAX
    body = {"protocol": "PREREGISTRATION_P132_faw.md section 5", "gate": "C2 power",
            "seeds": list(PILOT_SEEDS), "alpha": ALPHA, "power": POWER_TARGET,
            "minimum_effect_of_interest": {"fraction_of_w_now_delay": MEI, "seconds": delta},
            "pilot_mean_w_now_delay_s": mean_now, "paired_sd_oracle_minus_now": sd,
            "required_n": n, "n_max": N_MAX, "passed": passed,
            "evaluation_n_if_authorised": (max(N_MIN, n) if passed else None),
            "pilot_effects_NOT_EVIDENCE": {
                "oracle_minus_now_mean_s": statistics.fmean(diffs),
                "ridge_minus_now_mean_s": statistics.fmean(r["ridge"] - r["now"] for r in rows)},
            "rows": rows}
    write(POWER, body)
    print(f"\n  C2: paired SD {sd:.3f} s, MEI {delta:.3f} s -> n = {n} "
          f"(max {N_MAX}): {'PASS' if passed else 'STOP: not adequately powered (P132 §5)'}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("gate", choices=("feasibility", "power"))
    return {"feasibility": feasibility, "power": power}[parser.parse_args(argv).gate]()


if __name__ == "__main__":
    raise SystemExit(main())
