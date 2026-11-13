"""P126 — audit the no-forecast replicates on `pulsed`, and lock what passed.

    python scripts/p126_audit.py --log 42=PATH --log 1=PATH --log 7=PATH
    python scripts/p126_audit.py --dry-run --only 42 7     # early check, writes nothing
    python scripts/p126_audit.py --verify                  # re-check an existing lock

Runs gates 1 and 2 of ADR-021 A2.3 on each of the three checkpoints
(training seeds 42, 1 and 7). It writes the lock only if **every** check on
**every** checkpoint passes.

**Gate 1 — the checkpoint is the final, intended run.**
- The weights and sidecar exist; both are hashed.
- `scripts/verify_ppo_checkpoint.py` passes:
  - not a smoke run;
  - the model's own `num_timesteps` ≥ 500,000. SB3 saves only after `learn`
    returns, and the sidecar is written after the save, so a full count means
    the final weights;
  - the observation contract;
  - a legal decision;
  - regime, arm and sublane as configured.
- The sidecar records the scenario seed rule, the no-forecast producer, and
  a forecast audit covering at least 500,000 observations.
- The policy's architecture and hyperparameters equal `ppo_config.yaml` and
  SB3's `MlpPolicy` default:
  - observation 17;
  - 2 actions;
  - two 64-unit hidden layers for both policy and value;
  - learning rate, `n_steps`, `batch_size`, `gamma`, `gae_lambda`,
    `clip_range` and `ent_coef`.
- The training log, if given, ends without a traceback.

**Gate 2 — parity on seed 999** (never an evaluation seed). The policy acts
identically in `TrafficSignalEnv` and `run_episode` + `PPOController` for a
full 1800 s episode: every decision, and all 17 inputs.

**The lock** (`no_forecast_lock.json`) records:
- each checkpoint's SHA-256 and its sidecar's;
- the SHA-256 of `ppo_config.yaml`, `spec.yaml` and `scenarios.yaml`;
- the observation-contract digest;
- the commit.

`train_ppo.py` refuses the surrogate arm if its frozen policy, or any of those
configs, differs from the lock. The ceiling then provably uses the qualified
artifacts.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

LOCK = Path("experiments/results/scenario_pulsed/no_forecast_lock.json")
SEEDS = (42, 1, 7)
CONFIGS = (Path("simulation/configs/ppo_config.yaml"), Path("mfstnet/configs/spec.yaml"),
           Path("simulation/configs/scenarios.yaml"))
PARITY_SEED = 999


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint(seed: int) -> Path:
    return Path(f"models/ppo/ppo_no-forecast_pulsed_keep_or_switch_seed{seed}.zip")


def architecture(model, ppo: dict) -> dict:
    import torch.nn as nn

    def widths(net):
        return [m.out_features for m in net.modules() if isinstance(m, nn.Linear)]

    extractor = model.policy.mlp_extractor
    clip = model.clip_range(1.0) if callable(model.clip_range) else model.clip_range
    lr = model.lr_schedule(1.0) if callable(model.lr_schedule) else model.learning_rate
    return {
        "observation 17": model.observation_space.shape == (17,),
        "2 actions": getattr(model.action_space, "n", None) == 2,
        "policy net 64x64": widths(extractor.policy_net) == [64, 64],
        "value net 64x64": widths(extractor.value_net) == [64, 64],
        "learning_rate": abs(float(lr) - float(ppo["learning_rate"])) < 1e-12,
        "n_steps": model.n_steps == ppo["n_steps"],
        "batch_size": model.batch_size == ppo["batch_size"],
        "gamma": model.gamma == ppo["gamma"],
        "gae_lambda": model.gae_lambda == ppo["gae_lambda"],
        "clip_range": abs(float(clip) - float(ppo["clip_range"])) < 1e-12,
        "ent_coef": model.ent_coef == ppo["ent_coef"],
    }


def audit(seed: int, log: Path | None, ppo_config: dict) -> dict:
    from stable_baselines3 import PPO

    from scripts.verify_ppo_checkpoint import main as verify

    path = checkpoint(seed)
    side = Path(str(path) + ".provenance.json")
    checks: dict[str, bool] = {"checkpoint exists": path.exists(), "sidecar exists": side.exists()}
    if not all(checks.values()):
        return {"checks": checks, "passed": False}
    sidecar = json.loads(side.read_text(encoding="utf-8"))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = verify(["--checkpoint", str(path), "--expect-steps", "500000",
                       "--expect-regime", "pulsed", "--expect-arm", "no-forecast",
                       "--equivalence-seed", str(PARITY_SEED)])
    checks["verify_ppo_checkpoint incl. seed-999 parity (gates 1 and 2)"] = code == 0
    checks["scenario seed rule"] = str(sidecar.get("episode_seed_rule", "")).startswith("offset")
    checks["no-forecast producer"] = sidecar.get("forecast_producer") == {"producer": "none"}
    checks["audited >= 500,000 observations"] = int(
        sidecar.get("forecast_audit_observations", 0)) >= 500_000
    model = PPO.load(str(path).removesuffix(".zip"), device="cpu")
    arch = architecture(model, ppo_config["ppo"])
    checks.update({f"architecture: {k}": v for k, v in arch.items()})
    if log is not None:
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        checks["training log ends without a traceback"] = "Traceback" not in text
    return {"checkpoint": str(path), "sha256": sha256(path), "sidecar_sha256": sha256(side),
            "num_timesteps": int(model.num_timesteps), "git_commit": sidecar.get("git_commit"),
            "verify_output": out.getvalue().splitlines(),
            # Plain bools: numpy's bool_ is not JSON-serialisable, and the first
            # full audit failed on exactly that when writing the lock.
            "checks": {k: bool(v) for k, v in checks.items()},
            "passed": all(bool(v) for v in checks.values())}


def write_atomically(path: Path, body: dict) -> None:
    """Write, then rename: a reader never sees a half-written lock."""
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes((json.dumps(body, indent=2) + "\n").encode("utf-8"))
    tmp.replace(path)


def verify_lock() -> int:
    """Re-hash every artifact the lock names, and check its commit exists."""
    if not LOCK.exists():
        raise SystemExit(f"no lock at {LOCK}")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    problems = [] if lock.get("passed") else ["the lock does not record a pass"]
    for seed, r in lock["replicates"].items():
        for key, path in (("sha256", Path(r["checkpoint"])),
                          ("sidecar_sha256", Path(r["checkpoint"] + ".provenance.json"))):
            if not path.exists() or sha256(path) != r[key]:
                problems.append(f"seed {seed}: {path} differs from the lock")
    for name, digest in lock["configs_sha256"].items():
        if not Path(name).exists() or sha256(Path(name)) != digest:
            problems.append(f"{name} differs from the lock")
    if subprocess.run(["git", "cat-file", "-e", f"{lock['commit']}^{{commit}}"],
                      capture_output=True).returncode != 0:
        problems.append(f"commit {lock['commit']} not found")
    for line in problems or ["every locked artifact, config and the commit match"]:
        print(f"  {'FAIL' if problems else 'OK'}  {line}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    import yaml

    from simulation.contract import contract_digest

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--log", action="append", default=[],
                        help="SEED=PATH of that run's training log")
    parser.add_argument("--only", type=int, nargs="+", help="with --dry-run: these seeds")
    parser.add_argument("--dry-run", action="store_true", help="audit, write nothing")
    parser.add_argument("--verify", action="store_true", help="re-check the existing lock")
    args = parser.parse_args(argv)
    if args.verify:
        return verify_lock()
    if args.only and not args.dry_run:
        raise SystemExit("--only is for --dry-run: the lock needs all three replicates")
    logs = {int(k): Path(v) for k, v in (item.split("=", 1) for item in args.log)}
    if LOCK.exists() and not args.dry_run:
        raise SystemExit(f"{LOCK} exists: the replicates are already locked")

    ppo_config = yaml.safe_load(CONFIGS[0].read_text(encoding="utf-8"))
    report = {}
    for seed in (args.only or SEEDS):
        report[seed] = audit(seed, logs.get(seed), ppo_config)
        print(f"  seed {seed}: {'PASS' if report[seed]['passed'] else 'FAIL'}")
        for name, ok in report[seed]["checks"].items():
            if not ok:
                print(f"    FAIL  {name}")
    passed = all(r["passed"] for r in report.values())
    body = {"what": "no-forecast replicates on pulsed, gates 1-2 (ADR-021 A2.3, P126)",
            "parity_seed": PARITY_SEED, "passed": passed,
            "configs_sha256": {str(p): sha256(p) for p in CONFIGS},
            "observation_contract": contract_digest(),
            "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True).stdout.strip(),
            "replicates": {str(s): r for s, r in report.items()}}
    if args.dry_run:
        print(f"\n  DRY RUN, nothing written: {'all passed' if passed else 'FAILED'}")
        return 0 if passed else 1
    target = LOCK if passed else LOCK.with_name("no_forecast_audit_FAILED.json")
    write_atomically(target, body)
    print(f"\n  {'LOCKED' if passed else 'NOT LOCKED: stop and investigate'} -> {target}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
