"""Train the PPO signal controller (S37, PRD §13.1).

Hyperparameters come from `simulation/configs/ppo_config.yaml`, never from this
file (NFR-16). The three arms ADR-009 defines differ only by config:

    no-forecast   the 16-dim state with indices 11-14 zeroed. The honest floor,
                  and the only arm that can run before MFSTNet exists
    surrogate     a SUMO-derived congestion proxy in 11-14, standing in for the
                  forecast so the RL half is not blocked on the vision half
    mfstnet       the real forecast. Phase 3 (PRD §2.4)

    python scripts/train_ppo.py --arm no-forecast --timesteps 500000
    python scripts/train_ppo.py --smoke          # ~3k steps, proves the loop runs

`--smoke` exists because a 500,000-step run that fails at step 400,000 has cost a
day. The smoke run is the same code path at 0.6% of the length.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed import set_seed  # noqa: E402

CONFIG = Path("simulation/configs/ppo_config.yaml")


def load_config(path: Path = CONFIG) -> dict:
    import yaml

    if not path.exists():
        raise FileNotFoundError(
            f"no PPO config at {path}. Hyperparameters live in YAML because the "
            f"ablation harness drives configs (NFR-16) — a literal in this script "
            f"that duplicates a config value is a defect."
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def train(
    arm: str = "no-forecast",
    *,
    timesteps: int | None = None,
    regime: str = "saturated",
    seed: int | None = None,
    episode_s: int | None = None,
    out: Path = Path("models/ppo"),
    smoke: bool = False,
    action_space: str = "phase_duration",
) -> dict:
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor

    from simulation.envs.traffic_env import TrafficSignalEnv

    config = load_config()
    ppo = config["ppo"]
    seed = seed if seed is not None else config["seed"]
    timesteps = timesteps or (3_000 if smoke else ppo["total_timesteps"])
    episode_s = episode_s or (300 if smoke else config["env"]["episode_s"])

    if arm not in config["arms"]:
        raise ValueError(f"unknown arm {arm!r}; expected one of {list(config['arms'])}")

    set_seed(seed)
    env = Monitor(
        TrafficSignalEnv(
            regime=regime,
            seed=seed,
            episode_s=episode_s,
            use_mfstnet=config["arms"][arm]["use_mfstnet"],
            # ADR-015. The screening arm the guide is being asked to choose
            # between; see DECISION-BRIEF item 1.
            action_space=action_space,
        )
    )

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=ppo["learning_rate"],
        n_steps=ppo["n_steps"],
        batch_size=ppo["batch_size"],
        gamma=ppo["gamma"],
        gae_lambda=ppo["gae_lambda"],
        clip_range=ppo["clip_range"],
        ent_coef=ppo["ent_coef"],
        seed=seed,
        verbose=0,
    )
    model.learn(total_timesteps=timesteps, progress_bar=False)

    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if action_space == "phase_duration" else f"_{action_space}"
    path = out / f"ppo_{arm}_{regime}{suffix}_seed{seed}"
    model.save(path)
    env.close()

    return {
        "arm": arm,
        "action_space": action_space,
        "regime": regime,
        "seed": seed,
        "timesteps": timesteps,
        "episode_s": episode_s,
        "checkpoint": str(path) + ".zip",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arm", default="no-forecast")
    parser.add_argument("--action-space", default="phase_duration",
                        choices=("phase_duration", "keep_or_switch"),
                        help="ADR-015 screening arm")
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--smoke", action="store_true",
                        help="short run that exercises the same code path")
    args = parser.parse_args(argv)

    info = train(
        args.arm, timesteps=args.timesteps, regime=args.regime,
        seed=args.seed, smoke=args.smoke, action_space=args.action_space,
    )
    for key, value in info.items():
        print(f"  {key:12} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
