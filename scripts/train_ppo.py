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

**Every checkpoint carries a sidecar, and a short run will not overwrite a long
one** (P47). A 3,000-step smoke run and a 500,000-step training run wrote to the
same filename, and nothing on disk told them apart — a `.zip` records weights,
not how long they were trained for. The same rule `train_mfstnet.py` applies to
`ablation.csv` applies here: refuse, name the run being protected, and offer
`--force` to whoever means it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from experiments.provenance import environment  # noqa: E402
from scripts.seed import set_seed  # noqa: E402
from simulation.contract import contract_digest  # noqa: E402

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


def sidecar_path(checkpoint: Path) -> Path:
    """Where a checkpoint's provenance lives. `.zip` in, `.provenance.json` out."""
    return Path(str(checkpoint) + ".provenance.json")


def guard_checkpoint(checkpoint: Path, timesteps: int, *, force: bool = False) -> None:
    """Refuse to replace a longer run's weights with a shorter run's (P47).

    Checked **before** training, not after: discovering at the end of an hour
    that the result cannot be written has already cost the hour.

    Three cases, and the third is the one that bites:

    * no checkpoint — nothing to protect, proceed.
    * a sidecar recording FEWER timesteps — this run supersedes it, proceed.
    * **a checkpoint with no sidecar at all** — every checkpoint written before
      P47 is in this state. Its length is unknown, so it cannot be compared, and
      an unknown-length checkpoint is exactly what caused a 16-August file to be
      read as that day's output. Say so and require `--force`.
    """
    if force or not checkpoint.exists():
        return

    side = sidecar_path(checkpoint)
    if not side.exists():
        raise SystemExit(f"""
{checkpoint.name} exists and has no provenance sidecar, so how long it trained
for is unknown, and this {timesteps:,}-step run cannot be shown to supersede it.
Move it aside, or pass --force if replacing it is what you mean.""")

    recorded = json.loads(side.read_text(encoding="utf-8"))
    previous = int(recorded.get("timesteps", 0))
    if previous > timesteps:
        kind = " (smoke)" if recorded.get("smoke") else ""
        raise SystemExit(f"""
{checkpoint.name} holds a {previous:,}-step run{kind}, and this one is
{timesteps:,} steps. A short run silently replacing a long one is how a
benchmark ends up measuring the wrong weights.
Pass --force if replacing it is what you mean.""")



class ProducerRefused(SystemExit):
    """A forecast arm whose producer is absent, disabled or invalid (P52, fail closed)."""


def _refuse(message: str):
    raise ProducerRefused(f"refusing to train: {message}. A surrogate-named checkpoint "
                          f"must never silently be a no-forecast policy (P52).")


def build_producer(config: dict, arm: str, *, quality: float | None, regime: str,
                   action_space: str, episode_s: int):
    """The forecast producer for `arm`, or a refusal naming what is wrong.

    Fail closed: every check below is a reason not to train at all.
    """
    import hashlib

    import yaml

    from simulation.forecast_producer import NoForecast, Surrogate
    from simulation.scenarios import is_scenario

    if arm not in config["arms"]:
        _refuse(f"unknown arm {arm!r}; expected one of {list(config['arms'])}")
    spec = config["arms"][arm]
    kind = spec.get("forecast")
    if kind == "none":
        if quality is not None:
            _refuse(f"--quality means nothing for the {arm} arm")
        return NoForecast()
    if kind == "mfstnet":
        _refuse("the mfstnet arm needs camera frames, which SUMO does not produce (Phase 3)")
    if kind != "surrogate":
        _refuse(f"arm {arm!r} declares no known forecast producer ({kind!r})")

    if quality is None:
        _refuse("the surrogate arm needs --quality")
    grid = [float(q) for q in spec["quality_grid"]]
    if float(quality) not in grid:
        _refuse(f"quality {quality} is not on the pre-registered grid {grid} (ADR-021 A1.3)")
    if action_space != "keep_or_switch":
        _refuse("the surrogate arm is defined for keep_or_switch decisions only")
    if not is_scenario(regime):
        _refuse(f"{regime!r} is a constant regime with no qualified headroom (P114, A1.1)")

    frozen = Path(spec["frozen_policy"])
    if not frozen.exists():
        _refuse(f"the oracle's frozen policy {frozen} does not exist")
    side = sidecar_path(frozen)
    if not side.exists():
        _refuse(f"{frozen} has no provenance sidecar")
    recorded = json.loads(side.read_text(encoding="utf-8"))
    wanted = {"arm": "no-forecast", "regime": regime, "action_space": "keep_or_switch",
              "smoke": False, "observation_contract": contract_digest(),
              "lateral_resolution": config["env"]["lateral_resolution"]}
    wrong = {k: recorded.get(k) for k, v in wanted.items() if recorded.get(k) != v}
    if int(recorded.get("timesteps", 0)) < int(config["ppo"]["total_timesteps"]):
        wrong["timesteps"] = recorded.get("timesteps")
    if wrong:
        _refuse(f"{frozen} is not the full scenario-trained no-forecast policy: {wrong}")

    requal = Path(spec["requalification"])
    if not requal.exists():
        _refuse(f"no requalification record at {requal}; it must pass first (A1.1)")
    result = json.loads(requal.read_text(encoding="utf-8"))
    sha = hashlib.sha256(frozen.read_bytes()).hexdigest()
    if not result.get("passed"):
        _refuse(f"the requalification at {requal} did not pass")
    if result.get("frozen_policy_sha256") != sha:
        _refuse(f"the requalification was run on a different policy than {frozen}")

    from simulation.oracle import ReplayOracle

    congestion = yaml.safe_load(
        Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))["congestion"]
    oracle = ReplayOracle(frozen, regime, episode_s=episode_s,
                          lateral_resolution=config["env"]["lateral_resolution"])
    return Surrogate(float(quality), oracle, low_max=congestion["low_max"],
                     med_max=congestion["med_max"], max_age_s=float(spec["max_age_s"]),
                     tau_s=float(spec["tau_s"]))


def forecast_audit(env, producer):
    """Checks every observation the policy is trained on; raises on the first violation.

    No-forecast: 11-14 read absent and 16 reads 1.0. Surrogate: 11-14 hold a
    class value, never absent, and 16 is an age within the gate's bound.
    """
    import gymnasium as gym
    import numpy as np

    from simulation.forecast_producer import NoForecast

    plain = isinstance(producer, NoForecast)
    classes = np.array([1 / 3, 2 / 3, 1.0])

    class ForecastAudit(gym.Wrapper):
        def __init__(self, inner):
            super().__init__(inner)
            self.checked = 0

        def _check(self, obs):
            slots, age = np.asarray(obs[11:15], dtype=float), float(obs[16])
            if plain:
                ok = bool((slots == 0.0).all()) and age == 1.0
            else:
                ok = (bool((np.abs(slots[:, None] - classes) < 1e-6).any(axis=1).all())
                      and 0.0 <= age <= 1.0)
            if not ok:
                raise RuntimeError(f"forecast audit failed for {producer.name}: slots "
                                   f"{slots.tolist()}, age {age} (P52)")
            self.checked += 1
            return obs

        def reset(self, **kwargs):
            obs, info = self.env.reset(**kwargs)
            return self._check(obs), info

        def step(self, action):
            obs, *rest = self.env.step(action)
            return (self._check(obs), *rest)

    return ForecastAudit(env)


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
    force: bool = False,
    quality: float | None = None,
) -> dict:
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor

    from simulation.envs.traffic_env import TrafficSignalEnv

    config = load_config()
    ppo = config["ppo"]
    seed = seed if seed is not None else config["seed"]
    timesteps = timesteps or (3_000 if smoke else ppo["total_timesteps"])
    episode_s = episode_s or (300 if smoke else config["env"]["episode_s"])

    # Fail closed before anything else (P52): a forecast arm without a valid
    # producer does not train at all.
    producer = build_producer(config, arm, quality=quality, regime=regime,
                              action_space=action_space, episode_s=episode_s)

    # Before the env, before the model, before an hour of learning: the run
    # has to be allowed to write its result at all (P47).
    out.mkdir(parents=True, exist_ok=True)
    suffix = "" if action_space == "phase_duration" else f"_{action_space}"
    label = arm if quality is None else f"{arm}-q{float(quality):.2f}"
    path = out / f"ppo_{label}_{regime}{suffix}_seed{seed}"
    guard_checkpoint(path.with_suffix(".zip"), timesteps, force=force)

    set_seed(seed)
    audited = forecast_audit(
        TrafficSignalEnv(
            regime=regime,
            seed=seed,
            episode_s=episode_s,
            use_mfstnet=config["arms"][arm]["use_mfstnet"],
            # ADR-015. The screening arm the guide is being asked to choose
            # between; see DECISION-BRIEF item 1.
            action_space=action_space,
            lateral_resolution=config["env"]["lateral_resolution"],
            forecast=producer,
        ), producer)
    env = Monitor(audited)

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
        # CPU deliberately, and pinned rather than left to Stable-Baselines3's
        # auto-selection (P38).
        #
        # SB3 picks CUDA when torch can see a GPU, and for an MlpPolicy that is
        # slower than CPU — it warns as much itself. Nothing here is a
        # convolution: the observation is a 16-dim vector (PRD §13.1) and the
        # net is two small dense layers, so per-step kernel launch and host
        # transfer cost more than the arithmetic saves.
        #
        # This only started mattering when torch became a CUDA build, so a
        # benchmark taken before that and one taken after would not have been
        # comparable. Pinning it keeps every PPO number on one device, which is
        # what NFR-07 and the 30-seed benchmark need.
        device="cpu",
    )
    model.learn(total_timesteps=timesteps, progress_bar=False)

    # Fail closed after training too: a surrogate run whose producer never sent
    # a message is a no-forecast policy, and is not saved under this name.
    stats = dict(getattr(producer, "stats", {}))
    if quality is not None and not stats.get("messages"):
        raise ProducerRefused("the surrogate producer sent no message during training; "
                              "nothing saved (P52)")
    model.save(path)
    env.close()

    info = {
        "arm": arm,
        "action_space": action_space,
        "regime": regime,
        "seed": seed,
        "timesteps": timesteps,
        "episode_s": episode_s,
        "smoke": smoke,
        # What the policy learned to read. P52: the length of the state vector
        # is already guarded, but a permuted or re-normalised index keeps the
        # length and changes the meaning, and nothing raises on that by itself.
        "observation_contract": contract_digest(),
        "checkpoint": str(path) + ".zip",
        # P119 and P115: the dynamics and the seeds the policy trained under.
        "lateral_resolution": config["env"]["lateral_resolution"],
        "episode_seed_rule": ("seed + episode"
                              if regime in ("light", "saturated", "oversaturated")
                              else "offset + stride * seed + episode (P115 section 4)"),
        "quality": quality,
        "forecast_producer": producer.describe(),
        "forecast_audit_observations": audited.checked,
        "forecast_producer_stats": {k: (v if k != "ages" else {str(a): n for a, n in v.items()})
                                    for k, v in stats.items()},
    }
    # The weights and the facts that give them meaning, written together. P38
    # put PPO on the CPU deliberately; the sidecar is where that is recorded,
    # so a benchmark can check that two arms were measured on one device.
    sidecar = sidecar_path(path.with_suffix(".zip"))
    sidecar.write_text(
        json.dumps(environment(**info, device="cpu"), indent=2) + chr(10),
        encoding="utf-8")
    info["provenance"] = str(sidecar)
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arm", default="no-forecast")
    parser.add_argument("--action-space", default="phase_duration",
                        choices=("phase_duration", "keep_or_switch"),
                        help="ADR-015 screening arm")
    parser.add_argument("--regime", default="saturated")
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--quality", type=float,
                        help="surrogate arm only: forecast quality q on the ADR-021 grid")
    parser.add_argument("--smoke", action="store_true",
                        help="short run that exercises the same code path")
    parser.add_argument("--force", action="store_true",
                        help="replace a checkpoint this run cannot be shown to "
                             "supersede (P47)")
    args = parser.parse_args(argv)

    info = train(
        args.arm, timesteps=args.timesteps, regime=args.regime,
        seed=args.seed, smoke=args.smoke, action_space=args.action_space,
        force=args.force, quality=args.quality,
    )
    for key, value in info.items():
        print(f"  {key:12} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
