"""ADR-020 as amended (P97a, Option D): the forecast state and the fallback gate.

The rule these pin: missing data never silently becomes a valid traffic
observation. It holds in steady state, during partial camera failure, and
during recovery.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.forecast_state import ForecastGate, forecast_slots  # noqa: E402

STATE = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))["ppo_state"]
ALL = {"N": "LOW", "S": "MEDIUM", "E": "HIGH", "W": "LOW"}
FULL = {"N": 5, "S": 1, "E": 0, "W": 9}


def obs(forecast=ALL, age=2.0, counts=FULL, queues=FULL):
    return {"counts": counts, "queues": queues, "forecast": forecast, "forecast_age_s": age}


# ---------------------------------------------------------------- encoding --

def test_no_forecast_message_reads_absent_everywhere_and_age_one():
    slots = forecast_slots(STATE, None, None)
    assert [slots[i] for i in (11, 12, 13, 14)] == [0.0] * 4 and slots[16] == 1.0


def test_classes_map_to_thirds_and_age_is_normalised():
    slots = forecast_slots(STATE, ALL, 2.0)
    assert [slots[i] for i in (11, 12, 13, 14)] == pytest.approx([1 / 3, 2 / 3, 1.0, 1 / 3])
    assert slots[16] == pytest.approx(0.2)


def test_age_saturates_at_the_cap():
    assert forecast_slots(STATE, ALL, 60.0)[16] == 1.0


def test_a_missing_approach_is_absent_never_low():
    slots = forecast_slots(STATE, {"N": "HIGH", "E": "LOW", "W": "LOW"}, 1.0)
    assert slots[12] == 0.0                         # S: absent
    assert slots[13] == pytest.approx(1 / 3)        # E: a real LOW
    assert slots[12] != slots[13]


def test_an_unknown_class_is_absent_not_guessed():
    assert forecast_slots(STATE, {**ALL, "S": "MED"}, 1.0)[12] == 0.0


@pytest.mark.parametrize("age", [None, -1.0, math.nan, math.inf, True])
def test_a_message_without_a_valid_age_is_refused(age):
    with pytest.raises(ValueError):
        forecast_slots(STATE, ALL, age)


def test_a_layout_where_a_class_equals_absent_is_refused():
    broken = {**STATE, "normalisers": {**STATE["normalisers"],
              "forecast_class_value": {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0}}}
    with pytest.raises(ValueError, match="ambiguous"):
        forecast_slots(broken, ALL, 1.0)


# -------------------------------------------------------------------- gate --

def test_complete_fresh_valid_inputs_allow_the_forecast_policy():
    assert ForecastGate().check(obs()).decider == "forecast"


def test_the_ten_second_boundary_is_inclusive():
    gate = ForecastGate()
    assert gate.check(obs(age=10.0)).decider == "forecast"
    stale = gate.check(obs(age=10.5))
    assert stale.decider == "no_forecast" and "10.5 s old" in stale.reasons[0]


def test_no_message_selects_the_no_forecast_policy():
    result = ForecastGate().check(obs(forecast=None, age=None))
    assert result.decider == "no_forecast" and result.reasons == ("no forecast message",)


def test_partial_camera_failure_is_not_enough():
    result = ForecastGate().check(obs(forecast={"N": "LOW", "E": "LOW", "W": "LOW"}))
    assert result.decider == "no_forecast" and "no forecast for S" in result.reasons


def test_an_invalid_class_is_not_enough():
    result = ForecastGate().check(obs(forecast={**ALL, "W": "MED"}))
    assert result.decider == "no_forecast" and any("W invalid" in r for r in result.reasons)


@pytest.mark.parametrize("counts", [{"N": 5, "S": 1, "E": 0},              # a lane missing
                                    {**FULL, "E": -1},                     # negative
                                    {**FULL, "E": math.nan}])              # not a number
def test_invalid_counts_go_to_webster_whatever_the_forecast(counts):
    result = ForecastGate().check(obs(counts=counts))
    assert result.decider == "webster"


def test_a_missing_queue_also_goes_to_webster():
    assert ForecastGate().check(obs(queues={"N": 1, "S": 1, "E": 1})).decider == "webster"


def test_recovery_needs_a_complete_fresh_message_and_every_switch_is_logged():
    gate = ForecastGate()
    partial = {"N": "LOW", "E": "LOW", "W": "LOW"}
    deciders = [gate.check(o).decider for o in (
        obs(),                                  # healthy
        obs(forecast=partial),                  # a camera loses S
        obs(forecast=partial, age=1.0),         # still partial: no premature recovery
        obs(age=12.0),                          # complete but stale: still no
        obs(age=1.0),                           # complete and fresh: recovered
    )]
    assert deciders == ["forecast", "no_forecast", "no_forecast", "no_forecast", "forecast"]
    assert [(a, b) for a, b, _ in gate.log] == [(None, "forecast"), ("forecast", "no_forecast"),
                                                ("no_forecast", "forecast")]
    assert all(reasons for _, _, reasons in gate.log)


# ----------------------------------------------------- the policy's input --

def test_the_policy_input_refuses_a_missing_count_rather_than_reading_zero():
    from simulation.ppo_controller import PPOController

    controller = object.__new__(PPOController)       # no checkpoint needed to build a state
    controller.state_spec, controller.index = STATE, STATE["index_map"]
    controller.norm, controller.dim = STATE["normalisers"], STATE["dim"]
    controller.action_space = "phase_duration"         # index 10 is not under test here
    good = {"counts": FULL, "queues": FULL, "phase": 0}
    vector = controller.observe(good)
    assert len(vector) == 17 and vector[16] == 1.0 and all(vector[i] == 0.0 for i in (11, 12, 13, 14))
    with pytest.raises(ValueError, match="not zero"):
        controller.observe({**good, "counts": {"N": 5, "S": 1, "E": 0}})
