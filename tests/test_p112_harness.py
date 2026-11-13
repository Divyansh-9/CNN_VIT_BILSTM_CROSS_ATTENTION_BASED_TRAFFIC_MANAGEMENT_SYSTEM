"""P112 Part 1's invariants must be able to fail.

A checker that reports zero violations is only evidence if it can report a
violation. These tests drive the real harness and checker, with no SUMO, over
synthetic observations. They break the gate in each way the protocol cares
about, and require the matching invariant to catch it.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.p112_part1 import FaultSchedule, Harness, Recording, check  # noqa: E402
from simulation.forecast_state import ForecastGate  # noqa: E402
from simulation.gated_controller import GatedController  # noqa: E402

SPEC = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))


class Fixed:
    name = "fixed"

    def reset(self):
        pass

    def decide(self, observation):
        return (0, 30)


class NoForecast(Fixed):
    def decide(self, observation):
        return (1, 10)


def drive(gate: ForecastGate, decisions: int = 600, seed: int = 3):
    degraded = Recording(Fixed())
    gated = GatedController(no_forecast=NoForecast(), degraded=degraded,
                            state_spec=SPEC["ppo_state"])
    harness = Harness(gated, FaultSchedule(seed, SPEC["congestion"]["low_max"],
                                           SPEC["congestion"]["med_max"]))
    harness.reset()
    gated.gate = gate
    rng = random.Random(seed)
    for step in range(decisions):
        counts = {a: rng.randint(0, 25) for a in "NSEW"}
        harness.decide({"counts": counts, "queues": dict(counts), "phase": 0, "step": step})
    return check(harness, degraded, SPEC["ppo_state"])


def test_the_real_gate_passes():
    assert drive(ForecastGate()) == []


def test_a_gate_that_ignores_staleness_is_caught():
    violations = drive(ForecastGate(max_age_s=1e9))
    assert any(v.startswith("I1") for v in violations)


def test_a_gate_that_accepts_partial_coverage_is_caught():
    violations = drive(ForecastGate(required=("N",)))
    assert any(v.startswith("I1") for v in violations)


def test_a_gate_that_ignores_corrupt_counts_is_caught():
    class Careless(ForecastGate):
        def check(self, observation):
            clean = {**observation, "counts": {a: 1 for a in "NSEW"},
                     "queues": {a: 1 for a in "NSEW"}}
            return super().check(clean)

    violations = drive(Careless())
    assert any(v.startswith("I4") for v in violations)


def test_a_too_strict_boundary_is_caught():
    violations = drive(ForecastGate(max_age_s=9.95))      # refuses an age of exactly 10.0
    assert any(v.startswith("I5") or "expected forecast" in v for v in violations)


@pytest.mark.parametrize("seed", [0, 1])
def test_the_schedule_is_reproducible(seed):
    a, b = (FaultSchedule(seed, 4, 15) for _ in range(2))
    obs = {"counts": {x: 7 for x in "NSEW"}, "queues": {x: 2 for x in "NSEW"}}
    assert [a.draw(obs)[1]["faults"] for _ in range(50)] == \
           [b.draw(obs)[1]["faults"] for _ in range(50)]
