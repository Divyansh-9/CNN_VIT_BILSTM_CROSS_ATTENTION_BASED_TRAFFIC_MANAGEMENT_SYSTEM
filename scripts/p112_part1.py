"""P112 Part 1 — fault-handling integrity of the fail-safe gate, in SUMO.

    python scripts/p112_part1.py

Implements Part 1 of `experiments/results/safety/PREREGISTRATION_P112.md`,
with its Amendment 1. Five seeds (42, 1, 7, 13, 21), saturated, 1800 s. The
fault schedule, recovery definition and invariants are all fixed there.

**The ground truth is the harness's own record of what it injected, never
the gate's reasons.** For every decision the harness knows:

- whether a message was delivered;
- its age;
- which approaches carried which class;
- whether counts or queues were corrupt.

From that alone it computes the decider the protocol expects, and the
invariants compare the gate against it.

**The forecast stream is ground-truth-now: the class of SUMO's current
counts. It is not a forecast** (P112). It refuses to run unless the
no-forecast checkpoint is the full retrain under the amended layout.
**Any single violation fails Part 1.** Exit 1 on failure.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

SEEDS = (42, 1, 7, 13, 21)
REGIME, DURATION_S = "saturated", 1800
CHECKPOINT = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
OUT = Path("experiments/results/safety/p112_part1.json")
APPROACHES = ("N", "S", "E", "W")
CLASSES = ("LOW", "MEDIUM", "HIGH")
MAX_AGE = 10.0


def cls_of(count: int, low_max: int, med_max: int) -> str:
    return "LOW" if count <= low_max else ("MEDIUM" if count <= med_max else "HIGH")


class FaultSchedule:
    """The frozen per-decision fault draws (P112 Part 1 table)."""

    def __init__(self, seed: int, low_max: int, med_max: int) -> None:
        self.rng = random.Random(10_000 + seed)
        self.low_max, self.med_max = low_max, med_max
        self.burst = 0

    def draw(self, observation: dict) -> tuple[dict, dict]:
        rng = self.rng
        truth = {"faults": []}
        counts = dict(observation["counts"])
        queues = dict(observation["queues"])

        # F1, a missing message, in bursts.
        if self.burst > 0:
            missing, self.burst = True, self.burst - 1
        elif rng.random() < 0.10:
            missing, self.burst = True, rng.randint(1, 6) - 1
        else:
            missing = False
        # F2 stale / F2b boundary / healthy age: one draw.
        u = rng.random()
        if u < 0.08:
            age, kind = 10.0 + (1.0 - rng.random()) * 20.0, "F2"   # (10, 30]
        elif u < 0.10:
            age, kind = 10.0, "F2b"
        elif u < 0.12:
            age, kind = 9.9, "F2b"
        else:
            age, kind = rng.random() * 8.0, None
        # F3 dropout and F4 invalid class.
        dropped = rng.sample(APPROACHES, rng.choice((1, 2))) if rng.random() < 0.10 else []
        present = [a for a in APPROACHES if a not in dropped]
        invalid = {}
        if rng.random() < 0.03:
            invalid[rng.choice(present)] = rng.choice(("MED", "", None))
        # F5 and F6, corrupt counts or queues.
        for name, values, rate in (("F5", counts, 0.05), ("F6", queues, 0.02)):
            if rng.random() < rate:
                a, how = rng.choice(APPROACHES), rng.choice(("missing", "negative", "nan"))
                if how == "missing":
                    values.pop(a)
                else:
                    values[a] = -1 if how == "negative" else math.nan
                truth["faults"].append(name)

        message = None
        if missing:
            truth["faults"].append("F1")
        else:
            message = {a: cls_of(observation["counts"][a], self.low_max, self.med_max)
                       for a in present}
            message.update({a: v for a, v in invalid.items()})
            if kind:
                truth["faults"].append(kind)
            if dropped:
                truth["faults"].append("F3")
            if invalid:
                truth["faults"].append("F4")
        inputs_valid = "F5" not in truth["faults"] and "F6" not in truth["faults"]
        complete = (message is not None and age <= MAX_AGE
                    and all(message.get(a) in CLASSES for a in APPROACHES))
        truth.update({"message": message, "age": None if missing else age,
                      "inputs_valid": inputs_valid,
                      "complete_fresh_valid": inputs_valid and complete,
                      "boundary": kind == "F2b",
                      "expected": ("webster" if not inputs_valid else
                                   "forecast" if complete else "no_forecast")})
        injected = {**observation, "counts": counts, "queues": queues,
                    "forecast": message, "forecast_age_s": None if missing else age}
        return injected, truth


class Recording:
    """Wraps the degraded cycle so I4 can compare the applied action with its output."""

    def __init__(self, inner) -> None:
        self.inner, self.outputs, self.name = inner, [], "degraded"

    def reset(self) -> None:
        self.inner.reset()
        self.outputs.clear()

    def decide(self, observation: dict):
        action = self.inner.decide(observation)
        self.outputs.append((observation.get("step"), tuple(action)))
        return action


class Harness:
    name = "p112_part1"

    def __init__(self, gated, schedule) -> None:
        self.gated, self.schedule, self.truths = gated, schedule, []

    def reset(self) -> None:
        self.gated.reset()
        self.truths.clear()

    def decide(self, observation: dict):
        injected, truth = self.schedule.draw(observation)
        self.truths.append(truth)
        return self.gated.decide(injected)


def expected_slots(state_spec, truth) -> dict:
    values = state_spec["normalisers"]["forecast_class_value"]
    off = state_spec["forecast_unavailable"]
    index = state_spec["index_map"]
    slots = {i: 0.0 for i in off["class_slots"]}
    if truth["message"] is None:
        slots[off["age_slot"]] = 1.0
        return slots
    for a in APPROACHES:
        if truth["message"].get(a) in CLASSES:
            slots[index[f"mfst_pred_{a}"]] = values[truth["message"][a]]
    slots[off["age_slot"]] = min(truth["age"], MAX_AGE) / MAX_AGE
    return slots


def check(harness, degraded, state_spec) -> list[str]:
    from simulation.forecast_state import forecast_slots

    v = []
    decisions, truths = harness.gated.decisions, harness.truths
    if len(decisions) != len(truths):
        return [f"I6: {len(decisions)} decisions for {len(truths)} injections"]
    probe_steps = {c["step"] for c in harness.gated.forecast_aware.calls}
    degraded_out = dict(degraded.outputs)
    previous = None
    changes = 0
    for d, t in zip(decisions, truths):
        if d.decider != t["expected"]:
            tag = ("I4" if t["expected"] == "webster" or d.decider == "webster"
                   else "I1" if d.decider == "forecast" else "I5")
            v.append(f"{tag}: step {d.step} decided by {d.decider}, expected "
                     f"{t['expected']} (faults {t['faults']})")
        if d.decider == "forecast" and not t["complete_fresh_valid"]:
            v.append(f"I1: step {d.step} forecast decision on an invalid message")
        if d.decider == "forecast" and d.step not in probe_steps:
            v.append(f"I1: step {d.step} forecast decision not seen by the probe")
        # I2: the encoder, judged against what was injected.
        built = (forecast_slots(state_spec, t["message"], t["age"])
                 if t["message"] is not None else forecast_slots(state_spec, None, None))
        want = expected_slots(state_spec, t)
        if any(abs(built[i] - want[i]) > 1e-12 for i in want):
            v.append(f"I2: step {d.step} encoder {built} != expected {want}")
        if d.decider == "forecast" and d.slots != expected_slots(state_spec, t):
            v.append(f"I2: step {d.step} the forecast-aware state does not match the message")
        if d.decider == "no_forecast" and d.slots != expected_slots(state_spec, {"message": None}):
            v.append(f"I2: step {d.step} the no-forecast state carries forecast values")
        # I4: corrupt inputs -> the degraded cycle, and its action applied.
        if not t["inputs_valid"] and (d.decider != "webster"
                                      or degraded_out.get(d.step) != d.action):
            v.append(f"I4: step {d.step} corrupt inputs not handled by the degraded cycle")
        # I5: an otherwise-valid boundary age (10.0 or 9.9 s) is accepted.
        if t["boundary"] and t["complete_fresh_valid"] and d.decider != "forecast":
            v.append(f"I5: step {d.step} age {t['age']} refused although within the bound")
        if d.decider != previous:
            changes += 1
            previous = d.decider
    log = harness.gated.gate.log
    if len(log) != changes:
        v.append(f"I3: {len(log)} logged changes, {changes} observed")
    if any(not reasons for _, _, reasons in log):
        v.append("I3: a logged change has no reason")
    return v


def main(argv: list[str] | None = None) -> int:
    import argparse

    import yaml

    from simulation.contract import assert_compatible
    from simulation.controllers import Fixed
    from simulation.gated_controller import GatedController
    from simulation.ppo_controller import PPOController
    from simulation.runner import run_episode

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", type=Path, metavar="OUT",
                        help="harness check only: one seed, 900 s, smoke checkpoint "
                             "allowed, written to OUT. Never the Part 1 result")
    args = parser.parse_args(argv)
    seeds, duration, out = (SEEDS[:1], 900, args.check) if args.check else (SEEDS, DURATION_S, OUT)

    sidecar = json.loads(Path(str(CHECKPOINT) + ".provenance.json").read_text(encoding="utf-8"))
    if not args.check and (sidecar.get("smoke") or sidecar.get("timesteps") != 500_000):
        raise SystemExit(f"{CHECKPOINT} is not the full retrain (timesteps "
                         f"{sidecar.get('timesteps')}, smoke {sidecar.get('smoke')}); "
                         f"Part 1 runs only after it (P112)")
    assert_compatible(CHECKPOINT, action_space="keep_or_switch")
    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    state_spec, congestion = spec["ppo_state"], spec["congestion"]

    report = {"protocol": "PREREGISTRATION_P112.md, Part 1 (with Amendment 1)",
              "stream": "ground-truth-now (not a forecast)",
              "checkpoint": str(CHECKPOINT), "checkpoint_contract": sidecar["observation_contract"],
              "seeds": {}}
    failed = False
    for seed in seeds:
        degraded = Recording(Fixed(green_s=30))
        gated = GatedController(no_forecast=PPOController(CHECKPOINT, action_space="keep_or_switch"),
                                degraded=degraded, state_spec=state_spec)
        harness = Harness(gated, FaultSchedule(seed, congestion["low_max"], congestion["med_max"]))
        harness.reset()
        try:
            result = run_episode(harness, regime=REGIME, seed=seed, duration_s=duration)
            violations = check(harness, degraded, state_spec)
        except Exception as error:                       # I6
            result, violations = None, [f"I6: episode raised {type(error).__name__}: {error}"]
        faults = {}
        for t in harness.truths:
            for f in t["faults"]:
                faults[f] = faults.get(f, 0) + 1
        deciders = {}
        for d in gated.decisions:
            deciders[d.decider] = deciders.get(d.decider, 0) + 1
        report["seeds"][seed] = {
            "decisions": len(gated.decisions), "by_decider": deciders, "faults": faults,
            "probe_calls": len(gated.forecast_aware.calls),
            "transitions": len(gated.gate.log),
            "episode": result.as_row() if result else None,
            "violations": violations}
        failed = failed or bool(violations)
        print(f"  seed {seed}: {len(gated.decisions)} decisions {deciders} faults {faults} "
              f"violations {len(violations)}", flush=True)
    report["passed"] = not failed
    if args.check:
        report["note"] = "HARNESS CHECK ONLY: not the Part 1 result"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(report, indent=2) + "\n").encode("utf-8"))
    print(f"\n  {'harness check' if args.check else 'Part 1'} "
          f"{'PASSED' if not failed else 'FAILED'}: {out}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
