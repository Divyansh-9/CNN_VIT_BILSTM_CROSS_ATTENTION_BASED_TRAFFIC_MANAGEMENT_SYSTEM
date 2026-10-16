"""P115 — qualify the `pulsed` scenario for ADR-021, before any PPO training.

    python scripts/p115_qualify.py design      # one logged design iteration, seeds 300-309
    python scripts/p115_qualify.py freeze      # freeze the passing iteration's parameters
    python scripts/p115_qualify.py qualify     # ONCE, seeds 200-219, frozen parameters only
    python scripts/p115_qualify.py cost        # D2: wall time with and without the replay oracle

Implements `experiments/results/scenario_pulsed/PREREGISTRATION_P115.md`.

**What is measured, per seed:**

- The frozen no-forecast policy is run in `TrafficSignalEnv` (`keep_or_switch`,
  5 s decisions, 1800 s), the dynamics the ceiling would train under.
- Every approach's count is recorded at **every simulated second**, so the
  oracle is the count at exactly *t* + 60 s.
- The episode is run **twice**: the second run supplies the independent
  targets for the quality check (Q5) and the determinism check (Q4a).
- Q4b runs the same seed under `Fixed(30)` and compares the vehicles SUMO
  loaded each second.

**Recording at every simulated second** wraps the environment's TraCI handle in
a pass-through that records after each `simulationStep`. It reads state only
and changes nothing the environment does.

**Nothing here trains, and seeds 0-29 are never used.**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/scenario_pulsed")
DESIGN_LOG = ROOT / "design_log.json"
FROZEN = ROOT / "frozen.json"
RESULT = ROOT / "qualification.json"
COST = ROOT / "cost.json"
CHECKPOINT = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
CHECKPOINT_SHA = "a7f06ba8c21085155bda998e23163846b7432762048b4ad9343a748339e20985"
SCENARIO = "pulsed"
DESIGN_SEEDS = tuple(range(300, 310))
QUALIFY_SEEDS = tuple(range(200, 220))
MAX_ITERATIONS = 5
EPISODE_S, HORIZON_S = 1800, 60
APPROACHES = ("N", "S", "E", "W")
THRESHOLDS = {"Q1": 0.20, "Q2": 0.10, "Q3": 0.10, "Q5_tolerance": 0.05,
              "Q5_range": 0.15, "Q6": 0.85}


class Recording:
    """Pass-through over the TraCI module that records after every simulated second."""

    def __init__(self, traci, lanes) -> None:
        self._traci, self._lanes = traci, lanes
        self.counts = [self._counts()]           # index = simulation time in s
        self.loaded: list[tuple] = []
        self.arrived = self.departed = 0

    def __getattr__(self, name):
        return getattr(self._traci, name)

    def _counts(self) -> tuple:
        lane = self._traci.lane
        return tuple(sum(lane.getLastStepVehicleNumber(l) for l in self._lanes[a])
                     for a in APPROACHES)

    def simulationStep(self, *args):
        self._traci.simulationStep(*args)
        sim = self._traci.simulation
        self.loaded.append(tuple(sim.getLoadedIDList()))
        self.arrived += sim.getArrivedNumber()
        self.departed += sim.getDepartedNumber()
        self.counts.append(self._counts())


def run(seed: int, policy: str, model=None) -> dict:
    """One 1800 s episode on the scenario. `policy` is 'frozen' or 'fixed30'."""
    from simulation.envs.traffic_env import TrafficSignalEnv
    from simulation.runner import lane_ids

    env = TrafficSignalEnv(regime=SCENARIO, seed=seed, episode_s=EPISODE_S,
                           action_space="keep_or_switch")
    obs, _ = env.reset(seed=seed)
    rec = Recording(env._traci, lane_ids())
    env._traci = rec
    decisions = []
    try:
        while True:
            queues = tuple(sum(rec.lane.getLastStepHaltingNumber(l) for l in lane_ids()[a])
                           for a in APPROACHES)
            decisions.append({"t": env._step_s, "queues": queues, "phase": env._phase})
            if policy == "frozen":
                action = int(model.predict(obs, deterministic=True)[0])
            else:
                action = 1 if env._green_elapsed >= 30 else 0
            obs, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                break
    finally:
        env.close()
    return {"seed": seed, "policy": policy, "counts": rec.counts, "loaded": rec.loaded,
            "decisions": decisions,
            "arrived_fraction": rec.arrived / rec.departed if rec.departed else 0.0}


def class_of(n: int, low_max: int, med_max: int) -> int:
    return 0 if n <= low_max else (1 if n <= med_max else 2)


def rows(first: dict, second: dict, low_max: int, med_max: int) -> list[dict]:
    """One row per (decision, approach) with an oracle 60 s on."""
    out = []
    last = len(first["counts"]) - 1
    for d in first["decisions"]:
        t = d["t"]
        if t + HORIZON_S > last:
            continue
        now, ahead = first["counts"][t], first["counts"][t + HORIZON_S]
        target = second["counts"][t + HORIZON_S] if t + HORIZON_S < len(second["counts"]) else None
        for k, a in enumerate(APPROACHES):
            out.append({"seed": first["seed"], "t": t, "approach": k,
                        "persistence": class_of(now[k], low_max, med_max),
                        "oracle": class_of(ahead[k], low_max, med_max),
                        "target": None if target is None else class_of(target[k], low_max, med_max),
                        "features": (list(now) + list(d["queues"]) + [1.0 if d["phase"] == 0 else 0.0]
                                     + [1.0 if j == k else 0.0 for j in range(4)])})
    return out


def measure(seeds, model, low_max, med_max, *, classifier_train=None) -> tuple[dict, list]:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score

    from simulation.forecast_quality import GRID, construct, corruption_rng, skill

    per_seed, all_rows, q4a, q4b, arrived, arrived_fixed = {}, [], [], [], [], []
    for seed in seeds:
        first = run(seed, "frozen", model)
        second = run(seed, "frozen", model)
        fixed = run(seed, "fixed30")
        q4a.append(first["counts"] == second["counts"])
        q4b.append(first["loaded"][:EPISODE_S] == fixed["loaded"][:EPISODE_S])
        arrived.append(first["arrived_fraction"])
        arrived_fixed.append(fixed["arrived_fraction"])
        r = rows(first, second, low_max, med_max)
        all_rows += r
        per_seed[seed] = {"decisions": len(first["decisions"]), "rows": len(r),
                          "deterministic": q4a[-1], "demand_aligned": q4b[-1],
                          "arrived_fraction": round(first["arrived_fraction"], 4),
                          "arrived_fraction_fixed30": round(fixed["arrived_fraction"], 4)}
        print(f"  seed {seed}: {len(first['decisions'])} decisions, deterministic {q4a[-1]}, "
              f"demand aligned {q4b[-1]}, arrived {first['arrived_fraction']:.3f}", flush=True)

    o = np.array([x["oracle"] for x in all_rows])
    p = np.array([x["persistence"] for x in all_rows])
    y = np.array([-1 if x["target"] is None else x["target"] for x in all_rows])
    X = np.array([x["features"] for x in all_rows], dtype=float)
    g = np.array([x["seed"] for x in all_rows])
    share = {c: round(float((o == k).mean()), 4) for k, c in enumerate(("LOW", "MEDIUM", "HIGH"))}

    # Q3: fitted on other episodes only.
    if classifier_train is None:                         # design: leave one episode out
        guess = np.empty_like(o)
        for s in seeds:
            fit = LogisticRegression(max_iter=3000).fit(X[g != s], o[g != s])
            guess[g == s] = fit.predict(X[g == s])
    else:                                                # qualify: fitted on the design seeds
        Xt, ot = classifier_train
        guess = LogisticRegression(max_iter=3000).fit(Xt, ot).predict(X)
    q3 = float((guess != o).mean())

    # Q5: the grid, built per seed from the first run, scored on the second.
    grid = {}
    for q in GRID:
        forecast = np.empty_like(o)
        for s in seeds:
            m = g == s
            steps = m.sum() // 4
            f = construct(o[m].reshape(steps, 4), p[m].reshape(steps, 4), q,
                          corruption_rng(int(s), q))
            forecast[m] = f.reshape(-1)
        grid[q] = {"skill": round(skill(forecast, p, o, y), 4),
                   "accuracy": round(float((forecast == y).mean()), 4),
                   "macro_f1_3class": round(float(f1_score(y, forecast, labels=[0, 1, 2],
                                                           average="macro", zero_division=0)), 4)}
    f1s = [grid[q]["macro_f1_3class"] for q in GRID]
    transitions = {}
    for a, b in zip(p.tolist(), o.tolist()):
        key = f"{('LOW', 'MEDIUM', 'HIGH')[a]}->{('LOW', 'MEDIUM', 'HIGH')[b]}"
        transitions[key] = transitions.get(key, 0) + 1

    m = {"Q1_oracle_differs_from_persistence": round(float((o != p).mean()), 4),
         "Q2_oracle_class_share": share,
         "Q3_state_classifier_disagrees": round(q3, 4),
         "Q4a_deterministic_seeds": f"{sum(q4a)}/{len(q4a)}",
         "Q4b_demand_aligned_seeds": f"{sum(q4b)}/{len(q4b)}",
         "Q5_grid": {str(q): v for q, v in grid.items()},
         "Q6_mean_arrived_fraction": round(float(np.mean(arrived)), 4),
         "reported_arrived_fraction_fixed30": round(float(np.mean(arrived_fixed)), 4),
         "reported_transitions": transitions,
         "rows": len(all_rows)}
    checks = {
        "Q1": m["Q1_oracle_differs_from_persistence"] >= THRESHOLDS["Q1"],
        "Q2": all(v >= THRESHOLDS["Q2"] for v in share.values()),
        "Q3": q3 >= THRESHOLDS["Q3"],
        "Q4": all(q4a) and all(q4b),
        "Q5": (all(abs(grid[q]["skill"] - q) <= THRESHOLDS["Q5_tolerance"] for q in GRID)
               and all(b > a for a, b in zip(f1s, f1s[1:]))
               and f1s[-1] - f1s[0] >= THRESHOLDS["Q5_range"]),
        "Q6": m["Q6_mean_arrived_fraction"] >= THRESHOLDS["Q6"],
    }
    return {"metrics": m, "checks": checks, "passed": all(checks.values()),
            "per_seed": per_seed}, (X, o)


def load_model():
    from stable_baselines3 import PPO

    sha = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
    if sha != CHECKPOINT_SHA:
        raise SystemExit(f"{CHECKPOINT} is not the frozen policy (sha256 {sha})")
    return PPO.load(str(CHECKPOINT).removesuffix(".zip"), device="cpu")


def spec_thresholds() -> tuple[int, int]:
    import yaml

    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    return spec["congestion"]["low_max"], spec["congestion"]["med_max"]


def params_now() -> dict:
    from simulation.scenarios import load_scenarios, scenario_hash

    params = load_scenarios()[SCENARIO]
    return {"params": params, "hash": scenario_hash(params)}


def committed_unchanged(*paths: Path) -> bool:
    for p in paths:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(p)],
                                 capture_output=True).returncode == 0
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(p)]).returncode != 0
        if not tracked or dirty:
            return False
    return True


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, indent=2) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=("design", "freeze", "qualify", "cost"))
    args = parser.parse_args(argv)
    low_max, med_max = spec_thresholds()
    log = json.loads(DESIGN_LOG.read_text(encoding="utf-8")) if DESIGN_LOG.exists() else []

    if args.mode == "design":
        if len(log) >= MAX_ITERATIONS:
            raise SystemExit(f"{MAX_ITERATIONS} design iterations used; stop and report (P115 §5)")
        if any(entry["passed"] for entry in log):
            raise SystemExit("an iteration already passed; freeze it rather than design further")
        now = params_now()
        report, _ = measure(DESIGN_SEEDS, load_model(), low_max, med_max)
        entry = {"iteration": len(log) + 1, **now, "seeds": list(DESIGN_SEEDS), **report}
        log.append(entry)
        write(DESIGN_LOG, log)
        print(json.dumps({k: entry[k] for k in ("iteration", "hash", "checks", "passed")}, indent=2))
        print(json.dumps(entry["metrics"], indent=2))
        return 0

    if args.mode == "freeze":
        passing = [e for e in log if e["passed"]]
        if not passing:
            raise SystemExit("no design iteration has passed; nothing to freeze")
        chosen = passing[0]
        if params_now()["hash"] != chosen["hash"]:
            raise SystemExit("scenarios.yaml no longer holds the passing iteration's parameters")
        write(FROZEN, {"scenario": SCENARIO, "iteration": chosen["iteration"],
                       "params": chosen["params"], "hash": chosen["hash"],
                       "design_log_sha256": hashlib.sha256(DESIGN_LOG.read_bytes()).hexdigest()})
        print(f"  frozen iteration {chosen['iteration']} ({chosen['hash']}); commit "
              f"{FROZEN}, {DESIGN_LOG} and scenarios.yaml before qualifying")
        return 0

    if args.mode == "qualify":
        if RESULT.exists():
            raise SystemExit(f"{RESULT} exists: qualification runs once (P115 §5)")
        if not FROZEN.exists():
            raise SystemExit("no frozen parameters; run design and freeze first")
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        if params_now()["hash"] != frozen["hash"]:
            raise SystemExit("scenarios.yaml differs from the frozen parameters")
        if not committed_unchanged(FROZEN, DESIGN_LOG, Path("simulation/configs/scenarios.yaml")):
            raise SystemExit("the frozen parameters and design log must be committed, unchanged, "
                             "before qualification")
        model = load_model()
        print("  fitting Q3's classifier on the design seeds (design data, not qualification)")
        _, train = measure(DESIGN_SEEDS, model, low_max, med_max)
        report, _ = measure(QUALIFY_SEEDS, model, low_max, med_max, classifier_train=train)
        write(RESULT, {"protocol": "PREREGISTRATION_P115.md", "attempt": 1,
                       "frozen_hash": frozen["hash"], "seeds": list(QUALIFY_SEEDS),
                       "frozen_policy": str(CHECKPOINT), "frozen_policy_sha256": CHECKPOINT_SHA,
                       "thresholds": THRESHOLDS, **report})
        print(json.dumps({"checks": report["checks"], "passed": report["passed"]}, indent=2))
        print(json.dumps(report["metrics"], indent=2))
        return 0 if report["passed"] else 1

    # cost (D2): ordinary episode vs an episode that also builds its replay oracle.
    model = load_model()
    seeds = DESIGN_SEEDS[:3]
    ordinary, replay = [], []
    for seed in seeds:
        from simulation.envs.traffic_env import TrafficSignalEnv

        a = time.perf_counter()
        env = TrafficSignalEnv(regime=SCENARIO, seed=seed, episode_s=EPISODE_S,
                               action_space="keep_or_switch")
        obs, _ = env.reset(seed=seed)
        steps = 0
        while True:
            obs, _, t1, t2, _ = env.step(int(model.predict(obs, deterministic=True)[0]))
            steps += 1
            if t1 or t2:
                break
        env.close()
        ordinary.append(time.perf_counter() - a)
        b = time.perf_counter()
        run(seed, "frozen", model)                       # the oracle pass, with per-second recording
        replay.append(time.perf_counter() - b)
        print(f"  seed {seed}: ordinary {ordinary[-1]:.1f} s ({steps} steps), "
              f"oracle pass {replay[-1]:.1f} s", flush=True)
    mean_o, mean_r = sum(ordinary) / len(ordinary), sum(replay) / len(replay)
    episodes_per_run = 500_000 / steps
    write(COST, {"host": "team laptop (ADR-003), CPU", "seeds": list(seeds),
                 "ordinary_episode_s": [round(x, 2) for x in ordinary],
                 "oracle_pass_s": [round(x, 2) for x in replay],
                 "steps_per_episode": steps,
                 "multiplier_with_oracle": round((mean_o + mean_r) / mean_o, 2),
                 "episodes_per_500k_run": round(episodes_per_run),
                 "added_hours_per_500k_run_uncached": round(episodes_per_run * mean_r / 3600, 2),
                 "note": ("env stepping with policy inference only; PPO's own update time is "
                          "excluded. The oracle depends only on (scenario, seed, frozen policy), "
                          "so arms sharing a training seed share one cached oracle"),
                 "rejected_alternative": ("SUMO saveState/loadState lookahead: about 1.4 s per "
                                          "lookahead, 522 s against 6.3 s per 1800 s episode "
                                          "(P115 spike)")})
    print(json.loads(COST.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
