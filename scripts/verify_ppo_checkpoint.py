"""Verify a PPO checkpoint before anything is scored with it (P112, P113).

    python scripts/verify_ppo_checkpoint.py --checkpoint models/ppo/X.zip --expect-steps 500000

A provenance sidecar records the length a run **asked for**. This checks what
the checkpoint **is**. Every check must pass, and it exits 1 otherwise:

1. **Not a smoke run.** The sidecar says `smoke: false` and asks for at least
   `--expect-steps`.
2. **Training completed.** The model's own `num_timesteps`, the steps it
   actually learned, is at least `--expect-steps`. SB3 rounds a run up to
   whole rollouts of `n_steps`, so a few steps over is expected, and any
   shortfall is a failure.
3. **The layout matches.** `assert_compatible` passes against the current
   `spec.yaml` (ADR-020 as amended), the sidecar's contract equals the current
   digest, and the policy's observation space has `spec.dim` inputs.
4. **The policy runs.** One decision is made on a state built by the
   controller from a valid observation, and it is a legal action.
5. **With `--expect-regime`:** the sidecar records that regime, the arm
   (`--expect-arm`), and the sublane setting the environment trains under now
   (P119).
6. **With `--equivalence-seed N`:** the policy acts identically in training
   (`TrafficSignalEnv`) and evaluation (`run_episode` + `PPOController`) on
   seed N for a full episode, decision for decision, including every
   observation (P116, P119, P120). Never use an evaluation seed (0-29).

It prints a record suitable for the changelog and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()


def main(argv: list[str] | None = None) -> int:
    import yaml
    from stable_baselines3 import PPO

    from simulation.contract import assert_compatible, contract_digest
    from simulation.ppo_controller import PPOController

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expect-steps", type=int, required=True)
    parser.add_argument("--action-space", default="keep_or_switch")
    parser.add_argument("--expect-regime")
    parser.add_argument("--expect-arm", default="no-forecast")
    parser.add_argument("--equivalence-seed", type=int)
    args = parser.parse_args(argv)
    if args.equivalence_seed is not None and 0 <= args.equivalence_seed < 30:
        raise SystemExit("seeds 0-29 are evaluation seeds; verify on another seed")

    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    sidecar = json.loads(Path(str(args.checkpoint) + ".provenance.json").read_text(encoding="utf-8"))
    model = PPO.load(str(args.checkpoint).removesuffix(".zip"), device="cpu")
    checks = {
        "not a smoke run": (not sidecar.get("smoke")
                            and int(sidecar.get("timesteps", 0)) >= args.expect_steps),
        "training completed (num_timesteps)": int(model.num_timesteps) >= args.expect_steps,
        "observation space is spec.dim": model.observation_space.shape == (spec["ppo_state"]["dim"],),
        "sidecar contract is the current digest": sidecar.get("observation_contract") == contract_digest(spec),
    }
    try:
        assert_compatible(args.checkpoint, action_space=args.action_space)
        checks["assert_compatible"] = True
    except SystemExit as error:
        checks["assert_compatible"] = False
        print(f"  assert_compatible: {error}")
    try:
        controller = PPOController(args.checkpoint, action_space=args.action_space)
        phase, green = controller.decide({"counts": {a: 3 for a in "NSEW"},
                                          "queues": {a: 1 for a in "NSEW"},
                                          "waits": {}, "phase": 0, "step": 0,
                                          "green_elapsed": 0})
        checks["a decision is made"] = phase in (0, 1) and green > 0
    except Exception as error:                                  # noqa: BLE001
        checks["a decision is made"] = False
        print(f"  decision failed: {type(error).__name__}: {error}")

    if args.expect_regime:
        ppo = yaml.safe_load(Path("simulation/configs/ppo_config.yaml").read_text(encoding="utf-8"))
        checks["sidecar regime"] = sidecar.get("regime") == args.expect_regime
        checks["sidecar arm"] = sidecar.get("arm") == args.expect_arm
        checks["sublane as configured (P119)"] = (
            sidecar.get("lateral_resolution") == ppo["env"]["lateral_resolution"])
    if args.equivalence_seed is not None:
        from simulation.equivalence import compare, trace_env, trace_runner

        regime = args.expect_regime or sidecar.get("regime")
        result = compare(trace_env(model, regime, args.equivalence_seed, 1800),
                         trace_runner(args.checkpoint, regime, args.equivalence_seed, 1800))
        checks["training and evaluation identical (P116, P119, P120)"] = result["identical"]
        print(f"  equivalence     {result}")

    print(f"  checkpoint      {args.checkpoint}")
    print(f"  num_timesteps   {model.num_timesteps} (expected >= {args.expect_steps})")
    print(f"  contract        {sidecar.get('observation_contract')} (current {contract_digest(spec)})")
    print(f"  obs space       {model.observation_space.shape}")
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
