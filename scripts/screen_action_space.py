"""Screen the two PPO action spaces at N seeds each (ADR-015, DECISION-BRIEF §1).

    python scripts/screen_action_space.py --seeds 5 --timesteps 50000

The guide is being asked to choose between PRD §13.1's 12 discrete
(phase, duration) actions and the literature-standard keep-or-switch at a fixed
decision interval. ADR-015 committed to deciding that **on measured numbers**,
and this is the measurement.

**Both arms are scored on `mean_wait_s`, not on episode reward.** The reward is a
lane-sum shaping signal computed every step; the §14.3 headline is a per-vehicle
mean from tripinfo. They are different quantities, and the two action spaces make
very different numbers of decisions per episode — 45 against 7 over 300 s — so
comparing accumulated reward would compare decision frequency as much as control
quality. Screening on the shaping signal and then benchmarking on tripinfo could
pick the wrong arm outright.

**Why screening is cheap and deciding late is not.** Changing the action space
after the 30-seed benchmark invalidates every checkpoint. Screening costs about
one arm's worth of training; discovering the answer afterwards costs all of it.

**This is a screen, not the benchmark.** Fewer timesteps, fewer seeds, and no
significance claim — it exists to rank two options, not to publish a result.
`experiments/results/benchmark_stats.csv` remains the reported comparison.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.results_io import merge_by_key  # noqa: E402

ACTION_SPACES = ("phase_duration", "keep_or_switch")


def evaluate(model, action_space: str, *, regime: str, seed: int,
             episode_s: int, episodes: int) -> list[float]:
    """Mean per-vehicle wait per episode, on held-out seeds."""
    from simulation.envs.traffic_env import TrafficSignalEnv

    waits = []
    for offset in range(episodes):
        env = TrafficSignalEnv(
            action_space=action_space, regime=regime,
            # Evaluation seeds are deliberately disjoint from training seeds —
            # scoring a policy on the episodes it trained on measures memory.
            seed=10_000 + seed * 100 + offset,
            episode_s=episode_s,
        )
        observation, _ = env.reset()
        done = False
        while not done:
            action, _ = model.predict(observation, deterministic=True)
            observation, _, terminated, truncated, _ = env.step(int(action))
            done = terminated or truncated
        waits.append(env.mean_wait_s())
        env.close()
    return waits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--timesteps", type=int, default=50_000)
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--episode-s", type=int, default=900)
    parser.add_argument("--eval-episodes", type=int, default=3)
    parser.add_argument("--arm", default="no-forecast")
    parser.add_argument("--out", type=Path,
                        default=Path("experiments/results/action_space_screen.csv"))
    args = parser.parse_args(argv)

    from scripts.train_ppo import train

    # RESUME. Each cell costs about half an hour, so a killed run must not throw
    # away the ones that finished — this happened once and cost 65 minutes.
    rows = []
    if args.out.exists():
        with args.out.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                # Only this regime's cells. The file may hold others, and
                # `rows` is what gets written back for this regime — loading a
                # different regime's rows here would copy them into this one.
                if row.get("regime") != args.regime:
                    continue
                row["seed"] = int(row["seed"])
                row["timesteps"] = int(row["timesteps"])
                row["episode_s"] = int(row["episode_s"])
                row["eval_episodes"] = int(row["eval_episodes"])
                row["mean_wait_s"] = float(row["mean_wait_s"])
                row["seconds"] = float(row["seconds"])
                rows.append(row)
        if rows:
            print(f"  resuming: {len(rows)} cell(s) already done in {args.out}")

    done = {(r["action_space"], r["seed"]) for r in rows}
    for action_space in ACTION_SPACES:
        for seed in range(1, args.seeds + 1):
            if (action_space, seed) in done:
                print(f"  {action_space:<16} seed {seed}  skipped (already done)")
                continue
            started = time.perf_counter()
            train(
                args.arm, timesteps=args.timesteps, regime=args.regime,
                seed=seed, episode_s=args.episode_s, action_space=action_space,
            )
            from stable_baselines3 import PPO

            suffix = "" if action_space == "phase_duration" else f"_{action_space}"
            model = PPO.load(
                f"models/ppo/ppo_{args.arm}_{args.regime}{suffix}_seed{seed}"
            )
            waits = evaluate(model, action_space, regime=args.regime, seed=seed,
                             episode_s=args.episode_s, episodes=args.eval_episodes)
            elapsed = time.perf_counter() - started
            mean = statistics.fmean(waits)
            rows.append({
                "action_space": action_space, "seed": seed,
                "timesteps": args.timesteps, "regime": args.regime,
                "episode_s": args.episode_s, "eval_episodes": args.eval_episodes,
                "mean_wait_s": round(mean, 3),
                "per_episode_waits": ";".join(f"{w:.3f}" for w in waits),
                "seconds": round(elapsed, 1),
            })
            print(f"  {action_space:<16} seed {seed}  mean_wait {mean:>7.2f}s  "
                  f"({elapsed / 60:.1f} min)")

            # Rewritten after every seed so a crash mid-screen does not lose the
            # seeds already paid for. Keyed on regime, so screening a second
            # demand level adds to this file rather than deleting the first
            # (see experiments/results_io). `quiet` because this runs in a loop.
            merge_by_key(args.out, rows, args.regime, key="regime", quiet=True)

    print(f"\n  {'action space':<18}{'seeds':>7}{'mean wait':>12}{'sd':>9}{'best':>9}")
    summary = {}
    for action_space in ACTION_SPACES:
        values = [r["mean_wait_s"] for r in rows if r["action_space"] == action_space]
        if not values:
            continue
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        summary[action_space] = statistics.fmean(values)
        print(f"  {action_space:<18}{len(values):>7}{summary[action_space]:>12.2f}"
              f"{sd:>9.2f}{min(values):>9.2f}")

    if len(summary) == 2:
        a, b = summary["phase_duration"], summary["keep_or_switch"]
        winner = "keep_or_switch" if b < a else "phase_duration"
        print(f"\n  lower is better. Screen favours **{winner}** "
              f"({min(a, b):.2f}s vs {max(a, b):.2f}s, "
              f"{abs(a - b) / max(a, b) * 100:.1f}% apart).")
        print("  A SCREEN, NOT A RESULT: few seeds, short training, no significance")
        print("  test. It ranks two options so the choice is informed; the reported")
        print("  comparison stays the 30-run benchmark.")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
