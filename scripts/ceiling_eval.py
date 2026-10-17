"""P128 — the ADR-021 ceiling: audit the forecast arms, then evaluate every frozen arm once.

    python scripts/ceiling_eval.py audit      # gates 1-2 for the six forecast checkpoints -> lock
    python scripts/ceiling_eval.py run        # ONCE: all six arms on paired seeds 0-29
    python scripts/ceiling_eval.py restat     # re-derive every statistic from the committed CSV

Implements `experiments/results/ceiling/PREREGISTRATION_P128_ceiling.md`. Every
number, rule and reading is fixed there, and `decide()` is the rule written as
code.

**`run` refuses** unless all of these hold:
- the pre-registration is committed unchanged;
- both locks verify: the no-forecast replicates (P126) and the forecast
  replicates (`audit`);
- the result does not already exist.

An episode that raises is re-run once, identically. If it fails again, the
whole evaluation stops. **No seed is dropped or replaced.**

**The forecast arms are the oracle (q = 1) and persistence (q = 0).** Both are
fed by the same producer that trained them (`simulation.forecast_eval`).
Every oracle number is **oracle-input: an upper bound, not achievable.**
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/ceiling")
PREREG = ROOT / "PREREGISTRATION_P128_ceiling.md"
RUNS = ROOT / "ceiling_runs.csv"
STATS = ROOT / "ceiling_stats.json"
FORECAST_LOCK = ROOT / "forecast_lock.json"
NO_FORECAST_LOCK = Path("experiments/results/scenario_pulsed/no_forecast_lock.json")
REGIME, DURATION_S = "pulsed", 1800
EVAL_SEEDS = tuple(range(30))
TRAINING_SEEDS = (42, 1, 7)
PARITY_SEED = 999
METRIC = "mean_total_delay_s"
D_MIN = 0.5
ALPHA = 0.05
MIN_ARRIVED = 0.85
STARVATION_MARGIN = 1.0
WEAK_TRANSFER = 0.80
PPO_ARMS = {"no-forecast": None, "persistence": 0.0, "oracle": 1.0}
BASELINES = {
    "webster_s660_lost4": {"kind": "webster", "s": 660.0, "lost": 4.0},
    "fixed_30": {"kind": "fixed", "green": 30},
    "webster_split_clamped_s600_lost0": {"kind": "webster", "s": 600.0, "lost": 0.0},
}
LOW_MAX, MED_MAX = 4, 15


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint(arm: str, seed: int) -> Path:
    if arm == "no-forecast":
        return Path(f"models/ppo/ppo_no-forecast_pulsed_keep_or_switch_seed{seed}.zip")
    return Path(f"models/ppo/ppo_surrogate-q{PPO_ARMS[arm]:.2f}_pulsed_keep_or_switch_seed{seed}.zip")


# ------------------------------------------------------------- the rule ----

def paired(a: list[float], b: list[float]) -> dict:
    """a - b per seed: negative means a has the lower delay."""
    from experiments.statistics import bootstrap_ci, cohens_d_paired, paired_t_test

    diffs = [x - y for x, y in zip(a, b)]
    t, p = paired_t_test(a, b)
    mean, low, high = bootstrap_ci(diffs)
    return {"n": len(diffs), "mean_a": statistics.fmean(a), "mean_b": statistics.fmean(b),
            "mean_diff": mean, "ci95": [low, high], "t": t, "p": p,
            "d": cohens_d_paired(a, b)}


def holm(tests: dict) -> None:
    ordered = sorted(tests.values(), key=lambda e: e["p"])
    still = True
    for rank, entry in enumerate(ordered):
        entry["holm_threshold"] = ALPHA / (len(ordered) - rank)
        entry["holm_significant"] = still and entry["p"] <= entry["holm_threshold"]
        still = still and entry["holm_significant"]


def beats(entry: dict) -> bool:
    return entry["holm_significant"] and entry["mean_diff"] < 0 and entry["d"] <= -D_MIN


def decide(primary: dict, operational: dict, transfer: float | None,
           replicate_directions: dict) -> dict:
    """The pre-registered reading (P128 section 6), as code."""
    vs_none, vs_persist = primary["oracle_vs_no_forecast"], primary["oracle_vs_persistence"]
    b_none, b_persist = beats(vs_none), beats(vs_persist)
    harm = [k for k, e in primary.items()
            if e["holm_significant"] and e["mean_diff"] > 0 and e["d"] >= D_MIN]
    if b_none and b_persist and operational["passed"]:
        reading = ("forecast information adds control value beyond the current deployable "
                   "forecast: the ceiling clears")
        cleared = True
    elif b_none and b_persist:
        reading = ("lower delay than both comparators, but the operational gate fails: "
                   "the ceiling does not clear")
        cleared = False
    elif b_none:
        reading = "a forecast input channel helps; foresight beyond persistence is not shown"
        cleared = False
    elif b_persist:
        reading = ("beats persistence but not no-forecast: inconsistent, reported as measured; "
                   "the ceiling does not clear")
        cleared = False
    else:
        reading = "no demonstrated control benefit from forecasts under the tested conditions"
        cleared = False
    qualifiers = []
    if cleared and any(v > 0 for pair in replicate_directions.values() for v in pair.values()):
        qualifiers.append("fragile: at least one training-seed replicate reverses direction")
    if transfer is not None and transfer < WEAK_TRANSFER:
        qualifiers.append(f"oracle transfer weak: realised accuracy {transfer:.3f} < "
                          f"{WEAK_TRANSFER}")
    if harm:
        qualifiers.append(f"the oracle arm is materially WORSE in: {harm}")
    qualifiers.append("oracle-input: an upper bound, not achievable; simulation evidence only")
    return {"cleared": cleared, "reading": reading, "qualifiers": qualifiers,
            "beats_no_forecast": b_none, "beats_persistence": b_persist}


def analyse(rows: list[dict]) -> dict:
    """Every pre-registered statistic, from the per-episode rows alone."""
    from experiments.statistics import bootstrap_ci

    def per_seed(arm: str, policy=None) -> list[float]:
        out = []
        for s in EVAL_SEEDS:
            vals = [float(r[METRIC]) for r in rows if r["arm"] == arm and int(r["eval_seed"]) == s
                    and (policy is None or r["policy"] == str(policy))]
            if not vals:
                raise ValueError(f"missing {arm} {policy} seed {s}: the pairing is broken")
            out.append(statistics.fmean(vals))
        return out

    arms = {arm: per_seed(arm) for arm in [*PPO_ARMS, *BASELINES]}
    primary = {"oracle_vs_no_forecast": paired(arms["oracle"], arms["no-forecast"]),
               "oracle_vs_persistence": paired(arms["oracle"], arms["persistence"])}
    holm(primary)

    def arm_mean(arm, key):
        vals = [float(r[key]) for r in rows if r["arm"] == arm and r.get(key) not in ("", None)]
        return statistics.fmean(vals) if vals else None

    operational = {"oracle_arrived": arm_mean("oracle", "arrived_fraction"),
                   "oracle_starvation": arm_mean("oracle", "starvation_events"),
                   "no_forecast_starvation": arm_mean("no-forecast", "starvation_events")}
    operational["passed"] = (operational["oracle_arrived"] >= MIN_ARRIVED and
                             operational["oracle_starvation"] <=
                             operational["no_forecast_starvation"] + STARVATION_MARGIN)
    directions = {}
    for seed in TRAINING_SEEDS:
        o = per_seed("oracle", seed)
        directions[str(seed)] = {
            "vs_no_forecast": statistics.fmean(a - b for a, b in zip(o, per_seed("no-forecast", seed))),
            "vs_persistence": statistics.fmean(a - b for a, b in zip(o, per_seed("persistence", seed)))}
    transfer = arm_mean("oracle", "acc_oracle_realised")
    decision = decide(primary, operational, transfer, directions)
    secondary = {f"{arm}_vs_{base}": paired(arms[arm], arms[base])
                 for arm in PPO_ARMS for base in BASELINES}
    summary = {}
    for arm in arms:
        mean, low, high = bootstrap_ci(arms[arm])
        summary[arm] = {METRIC: mean, "ci95": [low, high],
                        **{k: arm_mean(arm, k) for k in (
                            "mean_wait_s", "arrived_fraction", "starvation_events", "throughput",
                            "max_wait_s", "clamp_rate", "oracle_realised_agreement",
                            "acc_forecast_realised", "acc_oracle_realised",
                            "acc_persistence_realised", "producer_informed_share")}}
    return {"protocol": "PREREGISTRATION_P128_ceiling.md", "metric": METRIC,
            "eval_seeds": list(EVAL_SEEDS), "decision": decision, "primary": primary,
            "operational_gate": operational, "replicate_directions": directions,
            "secondary_descriptive_unadjusted": secondary, "arms": summary}


# ---------------------------------------------------------- the episodes --

def committed_unchanged(path: Path) -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path)]).returncode == 0
    return tracked and clean


def verify_lock(lock_path: Path) -> list[str]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems = [] if lock.get("passed") else [f"{lock_path} does not record a pass"]
    for seed, r in lock["replicates"].items():
        if sha256(Path(r["checkpoint"])) != r["sha256"]:
            problems.append(f"{r['checkpoint']} differs from {lock_path}")
    for name, digest in lock["configs_sha256"].items():
        if sha256(Path(name)) != digest:
            problems.append(f"{name} differs from {lock_path}")
    return problems


def make_producer(q: float, oracle):
    from simulation.forecast_producer import Surrogate

    return Surrogate(q, oracle, low_max=LOW_MAX, med_max=MED_MAX)


def frozen_oracle():
    from simulation.oracle import ReplayOracle

    lock = json.loads(NO_FORECAST_LOCK.read_text(encoding="utf-8"))
    frozen = Path(lock["replicates"]["42"]["checkpoint"])
    return ReplayOracle(frozen, REGIME, episode_s=DURATION_S, lateral_resolution=0.8)


def episode(arm: str, policy, seed: int, oracle) -> dict:
    from simulation.controllers import Fixed
    from simulation.forecast_eval import ForecastFeeding
    from simulation.ppo_controller import PPOController
    from simulation.runner import run_episode
    from simulation.webster import Webster

    feeding = None
    if arm in PPO_ARMS:
        controller = PPOController(checkpoint(arm, policy), action_space="keep_or_switch")
        if PPO_ARMS[arm] is not None:
            feeding = ForecastFeeding(controller, make_producer(PPO_ARMS[arm], oracle), seed)
            controller = feeding
    else:
        spec = BASELINES[arm]
        controller = (Webster(saturation_flow_per_metre=spec["s"], lost_time_startup_s=spec["lost"])
                      if spec["kind"] == "webster" else Fixed(green_s=spec["green"]))
    row = run_episode(controller, regime=REGIME, seed=seed, duration_s=DURATION_S,
                      total_delay=True).as_row()
    row.update({"arm": arm, "policy": str(policy), "eval_seed": seed,
                "clamp_rate": round(controller.clamp_rate, 4) if hasattr(controller, "clamp_rate")
                else ""})
    if feeding is not None:
        row.update({k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in feeding.report().items()})
    return row


def run() -> int:
    from experiments.provenance import write_sidecar

    if RUNS.exists():
        raise SystemExit(f"{RUNS} exists: the ceiling evaluation runs once (P128)")
    if not committed_unchanged(PREREG):
        raise SystemExit(f"{PREREG} must be committed, unchanged, before the evaluation")
    for lock in (NO_FORECAST_LOCK, FORECAST_LOCK):
        if not lock.exists():
            raise SystemExit(f"no lock at {lock}")
        problems = verify_lock(lock)
        if problems:
            raise SystemExit("lock verification failed: " + "; ".join(problems))
    oracle = frozen_oracle()
    plan = [(arm, p) for arm in PPO_ARMS for p in TRAINING_SEEDS] + [(b, b) for b in BASELINES]
    rows = []
    for arm, policy in plan:
        for seed in EVAL_SEEDS:
            try:
                row = episode(arm, policy, seed, oracle)
            except Exception as first:                       # noqa: BLE001
                print(f"  {arm} {policy} seed {seed} raised {first!r}; re-running once", flush=True)
                try:
                    row = episode(arm, policy, seed, oracle)
                except Exception as second:                  # noqa: BLE001
                    ROOT.mkdir(parents=True, exist_ok=True)
                    (ROOT / "ceiling_FAILED.json").write_text(json.dumps({
                        "arm": arm, "policy": str(policy), "eval_seed": seed,
                        "errors": [repr(first), repr(second)], "completed_rows": len(rows)},
                        indent=2) + "\n", encoding="utf-8")
                    raise SystemExit("an episode failed twice: the evaluation stops (P128 §7)")
            rows.append(row)
        print(f"  {arm:34} {str(policy):34} done", flush=True)
    fields = sorted({k for r in rows for k in r})
    with RUNS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    write_sidecar(RUNS)
    return restat()


def restat() -> int:
    with RUNS.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = analyse(rows)
    STATS.write_bytes((json.dumps(result, indent=2, default=float) + "\n").encode("utf-8"))
    d = result["decision"]
    print(f"\n  READING: {d['reading']}")
    for q in d["qualifiers"]:
        print(f"    - {q}")
    for name, e in result["primary"].items():
        print(f"  {name}: diff {e['mean_diff']:+.3f} s [{e['ci95'][0]:+.3f}, {e['ci95'][1]:+.3f}], "
              f"d {e['d']:+.3f}, p {e['p']:.2e}, Holm {'sig' if e['holm_significant'] else 'n.s.'}")
    return 0


# ------------------------------------------------------------- the audit --

def audit() -> int:
    """Gates 1-2 for the six forecast checkpoints, then the forecast lock (atomic)."""
    import yaml
    from stable_baselines3 import PPO

    from scripts.p126_audit import CONFIGS, architecture
    from simulation.contract import contract_digest
    from simulation.equivalence import compare, trace_env, trace_runner

    if FORECAST_LOCK.exists():
        raise SystemExit(f"{FORECAST_LOCK} exists")
    problems = verify_lock(NO_FORECAST_LOCK)
    if problems:
        raise SystemExit("; ".join(problems))
    nf_lock = json.loads(NO_FORECAST_LOCK.read_text(encoding="utf-8"))
    frozen_sha = nf_lock["replicates"]["42"]["sha256"]
    ppo = yaml.safe_load(Path("simulation/configs/ppo_config.yaml").read_text(encoding="utf-8"))
    oracle = frozen_oracle()
    report = {}
    for arm in ("persistence", "oracle"):
        q = PPO_ARMS[arm]
        for seed in TRAINING_SEEDS:
            path = checkpoint(arm, seed)
            side = Path(str(path) + ".provenance.json")
            checks = {"checkpoint exists": path.exists(), "sidecar exists": side.exists()}
            if all(checks.values()):
                s = json.loads(side.read_text(encoding="utf-8"))
                model = PPO.load(str(path).removesuffix(".zip"), device="cpu")
                prod = s.get("forecast_producer", {})
                stats = s.get("forecast_producer_stats", {})
                informed = stats.get("informed_messages", 0) / max(stats.get("messages", 0), 1)
                checks.update({
                    "arm surrogate": s.get("arm") == "surrogate",
                    "quality": s.get("quality") == q and prod.get("q") == q,
                    "regime pulsed": s.get("regime") == REGIME,
                    "keep_or_switch": s.get("action_space") == "keep_or_switch",
                    "not smoke": s.get("smoke") is False,
                    "500,000 steps": int(s.get("timesteps", 0)) >= 500_000
                                     and model.num_timesteps >= 500_000,
                    "sublane 0.8": s.get("lateral_resolution") == 0.8,
                    "contract": s.get("observation_contract") == contract_digest(),
                    "oracle replays the locked seed-42 policy":
                        prod.get("frozen_policy_sha256") == frozen_sha,
                    "audited >= 500,000 observations":
                        int(s.get("forecast_audit_observations", 0)) >= 500_000,
                    "producer sent messages": stats.get("messages", 0) > 0,
                    "informed share is q": abs(informed - q) < 1e-9,
                    "code clean at launch": s.get("code_at_start", {}).get("dirty_paths") == [],
                })
                checks.update({f"architecture: {k}": bool(v)
                               for k, v in architecture(model, ppo["ppo"]).items()})
                result = compare(trace_env(model, REGIME, PARITY_SEED, DURATION_S,
                                           forecast=make_producer(q, oracle)),
                                 trace_runner(path, REGIME, PARITY_SEED, DURATION_S,
                                              producer=make_producer(q, oracle)))
                checks["seed-999 parity with forecast messages"] = bool(result["identical"])
            checks = {k: bool(v) for k, v in checks.items()}
            report[f"{arm}_{seed}"] = {
                "checkpoint": str(path), "checks": checks, "passed": all(checks.values()),
                **({"sha256": sha256(path), "sidecar_sha256": sha256(side)}
                   if path.exists() and side.exists() else {})}
            print(f"  {arm} seed {seed}: {'PASS' if report[f'{arm}_{seed}']['passed'] else 'FAIL'}")
            for k, ok in checks.items():
                if not ok:
                    print(f"    FAIL  {k}")
    passed = all(r["passed"] for r in report.values())
    body = {"what": "forecast replicates (persistence q=0, oracle q=1), gates 1-2 (P128)",
            "passed": passed, "frozen_policy_sha256": frozen_sha,
            "configs_sha256": {str(p): sha256(p) for p in CONFIGS},
            "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True).stdout.strip(),
            "replicates": report}
    target = FORECAST_LOCK if passed else ROOT / "forecast_audit_FAILED.json"
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes((json.dumps(body, indent=2) + "\n").encode("utf-8"))
    tmp.replace(target)
    print(f"\n  {'LOCKED' if passed else 'NOT LOCKED: stop and investigate'} -> {target}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=("audit", "run", "restat"))
    args = parser.parse_args(argv)
    return {"audit": audit, "run": run, "restat": restat}[args.mode]()


if __name__ == "__main__":
    raise SystemExit(main())
