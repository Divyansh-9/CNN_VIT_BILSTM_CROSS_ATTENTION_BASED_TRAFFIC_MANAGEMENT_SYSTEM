"""P52 inspection — how much could a perfect t+60 class forecast tell the policy?

    python scripts/p52_headroom.py --regime saturated
    python scripts/p52_headroom.py --regime oversaturated --seeds 100 101

ADR-021 runs a perfect-forecast ceiling first because a null there would be
"decisive". That holds only if the forecast carries information the state does
not already hold. This script measures that **before** anything is trained. It
trains nothing and changes no checkpoint.

For each controller (the retrained no-forecast PPO policy and the benchmark's
Webster) it runs SUMO and records each approach's count at every decision. It
pairs each decision with the class realised about 60 s later: the first later
decision at least 60 s on, and no more than 75 s on. That realised class is
what ADR-021's oracle would hand the policy.

Reported per controller:

- **the class mix** of the realised future class. A near-constant class is a
  near-constant input;
- **persistence:** the current class used as the forecast. The policy can
  compute it from indices 0-3 already, so it is the information floor. Its
  agreement with the oracle bounds what the oracle adds;
- **the transition table:** current class against future class;
- **a state-only classifier** (logistic regression, leave-one-episode-out):
  the future class predicted from the 9 features the policy already sees.
  Exploratory, from a handful of episodes.

**The seeds default to 100-104**, disjoint from the benchmark's evaluation
seeds 0-29 and from the training seed 42. This is a design measurement, and it
does not touch the seeds a later result is scored on.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CHECKPOINT = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
APPROACHES = ("N", "S", "E", "W")
CLASSES = ("LOW", "MEDIUM", "HIGH")
LEAD_MIN_S, LEAD_MAX_S = 60, 75


class Recorder:
    """Wraps a controller and records what it was shown at every decision."""

    def __init__(self, inner) -> None:
        self.inner, self.name, self.rows = inner, getattr(inner, "name", "controller"), []

    def reset(self) -> None:
        self.inner.reset()
        self.rows = []

    def decide(self, observation: dict):
        self.rows.append({"step": observation["step"], "phase": observation["phase"],
                          "counts": dict(observation["counts"]),
                          "queues": dict(observation["queues"])})
        return self.inner.decide(observation)


def class_of(count: int, low_max: int, med_max: int) -> int:
    return 0 if count <= low_max else (1 if count <= med_max else 2)


def pairs(rows: list[dict], low_max: int, med_max: int) -> list[dict]:
    """One record per (decision, approach) with a realised class 60-75 s on."""
    out = []
    steps = [r["step"] for r in rows]
    for i, row in enumerate(rows):
        j = next((k for k in range(i + 1, len(rows)) if steps[k] >= row["step"] + LEAD_MIN_S),
                 None)
        if j is None or steps[j] > row["step"] + LEAD_MAX_S:
            continue
        for a_index, a in enumerate(APPROACHES):
            out.append({
                "lead_s": steps[j] - row["step"],
                "now": class_of(row["counts"][a], low_max, med_max),
                "future": class_of(rows[j]["counts"][a], low_max, med_max),
                "features": ([row["counts"][b] for b in APPROACHES]
                             + [row["queues"][b] for b in APPROACHES]
                             + [1.0 if row["phase"] == 0 else 0.0]
                             + [1.0 if k == a_index else 0.0 for k in range(4)]),
            })
    return out


def summarise(records: list[dict], groups: list[str]) -> dict:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score

    y = np.array([r["future"] for r in records])
    now = np.array([r["now"] for r in records])
    X = np.array([r["features"] for r in records], dtype=float)
    g = np.array(groups)
    predicted = np.empty_like(y)
    for episode in sorted(set(groups)):
        train, test = g != episode, g == episode
        if len(set(y[train].tolist())) < 2:
            predicted[test] = y[train][0]
            continue
        model = LogisticRegression(max_iter=2000).fit(X[train], y[train])
        predicted[test] = model.predict(X[test])

    def scores(guess):
        return {"accuracy": round(float(accuracy_score(y, guess)), 4),
                "macro_f1_3class": round(float(f1_score(y, guess, average="macro",
                                                        labels=[0, 1, 2], zero_division=0)), 4)}

    share = Counter(y.tolist())
    transitions = Counter(zip(now.tolist(), y.tolist()))
    leads = sorted(r["lead_s"] for r in records)
    return {
        "pairs": len(records),
        "lead_s": {"min": leads[0], "median": leads[len(leads) // 2], "max": leads[-1]},
        "future_class_share": {c: round(share.get(k, 0) / len(y), 4) for k, c in enumerate(CLASSES)},
        "oracle_differs_from_persistence": round(float((y != now).mean()), 4),
        "persistence": scores(now),
        "state_only_logreg_leave_one_episode_out": scores(predicted),
        "transitions_now_to_future": {f"{CLASSES[a]}->{CLASSES[b]}": n
                                      for (a, b), n in sorted(transitions.items())},
    }


def main(argv: list[str] | None = None) -> int:
    import yaml

    from scripts.benchmark import WEBSTER_SATURATION
    from simulation.ppo_controller import PPOController
    from simulation.runner import run_episode
    from simulation.webster import Webster

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--seeds", type=int, nargs="+", default=[100, 101, 102, 103, 104])
    parser.add_argument("--duration-s", type=int, default=1800)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if set(args.seeds) & set(range(30)):
        raise SystemExit("seeds 0-29 are the benchmark's evaluation seeds; a design "
                         "measurement does not use them")

    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    low_max, med_max = spec["congestion"]["low_max"], spec["congestion"]["med_max"]
    makers = {
        "ppo_no_forecast": lambda: PPOController(CHECKPOINT, action_space="keep_or_switch"),
        "webster": lambda: Webster(saturation_flow_per_metre=WEBSTER_SATURATION),
    }
    report = {"what": "P52 inspection: information a perfect t+60 class forecast could add",
              "regime": args.regime, "seeds": args.seeds, "duration_s": args.duration_s,
              "thresholds": {"low_max": low_max, "med_max": med_max},
              "lead_window_s": [LEAD_MIN_S, LEAD_MAX_S],
              "checkpoint": str(CHECKPOINT), "controllers": {}}
    for name, make in makers.items():
        records, groups, episodes = [], [], {}
        for seed in args.seeds:
            recorder = Recorder(make())
            recorder.reset()
            result = run_episode(recorder, regime=args.regime, seed=seed,
                                 duration_s=args.duration_s)
            got = pairs(recorder.rows, low_max, med_max)
            records += got
            groups += [str(seed)] * len(got)
            episodes[seed] = {"decisions": len(recorder.rows), "pairs": len(got),
                              "mean_wait_s": result.as_row()["mean_wait_s"]}
            print(f"  {args.regime} {name} seed {seed}: {len(recorder.rows)} decisions, "
                  f"{len(got)} pairs", flush=True)
        report["controllers"][name] = {**summarise(records, groups), "episodes": episodes}

    out = args.out or Path(f"experiments/results/p52/headroom_{args.regime}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    for name, r in report["controllers"].items():
        print(f"  {name}: future {r['future_class_share']}, oracle differs from "
              f"persistence on {r['oracle_differs_from_persistence']:.1%}")
    print(f"  written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
