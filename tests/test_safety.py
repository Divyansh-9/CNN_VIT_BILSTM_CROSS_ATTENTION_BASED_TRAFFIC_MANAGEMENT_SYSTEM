"""The actuation rules, tested without starting a server.

FR-A03 to FR-A06 are Must Have requirements about what the signal is allowed to
do. `simulation/controllers.py` states the principle for the simulator —
"safety clamping, yellow and all-red live in the runner, so no controller,
learned or otherwise, can produce an unsafe program" — and the deployed path
needs the same guarantee, because a PPO policy is exactly the kind of component
that will eventually request a 2-second green because a reward surface said so.

A rule that can only be exercised by starting a web server is a rule that gets
tested once.
"""

from __future__ import annotations

import pytest

from server.safety import EW, NS, Decision, SafetyLimits, SignalGuard


@pytest.fixture
def guard():
    return SignalGuard(phase=NS, elapsed_s=60.0)


# ------------------------------------------------------------ FR-A03 green --


def test_a_green_below_the_minimum_is_raised(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=2)
    assert decision.green_s == 10
    assert decision.clamped is True


def test_a_green_above_the_maximum_is_lowered(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=600)
    assert decision.green_s == 90
    assert decision.clamped is True


def test_a_green_within_limits_is_untouched(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=45)
    assert decision.green_s == 45
    assert decision.clamped is False
    assert decision.source == "policy"


def test_a_switch_before_the_minimum_green_is_held():
    """The rule that stops a policy oscillating. It holds the CURRENT phase —
    honouring the switch and clamping its duration would still have switched."""
    guard = SignalGuard(phase=NS, elapsed_s=4.0)
    decision = guard.decide(proposed_phase=EW, proposed_green_s=30)
    assert decision.phase == NS
    assert decision.source == "hold"
    assert "below the 10s minimum" in decision.reason


def test_staying_in_phase_before_the_minimum_is_allowed():
    """Only a SWITCH is restricted. Extending the current green is not."""
    guard = SignalGuard(phase=NS, elapsed_s=4.0)
    assert guard.decide(proposed_phase=NS, proposed_green_s=30).source == "policy"


# --------------------------------------------------------- FR-A04 all-red --


def test_a_phase_change_carries_all_red(guard):
    assert guard.decide(proposed_phase=EW, proposed_green_s=30).all_red_s == 3


def test_staying_in_phase_carries_no_all_red(guard):
    assert guard.decide(proposed_phase=NS, proposed_green_s=30).all_red_s == 0


# ------------------------------------------------------- FR-A05 emergency --


def test_emergency_preempts_the_policy(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=90,
                            emergency_approach="N")
    assert decision.source == "emergency"
    assert decision.phase == NS


def test_emergency_outranks_the_minimum_green():
    """Deliberate ordering. A minimum-green rule that delays an ambulance is a
    rule applied to the wrong thing."""
    guard = SignalGuard(phase=NS, elapsed_s=1.0)
    decision = guard.decide(proposed_phase=NS, proposed_green_s=30,
                            emergency_approach="E")
    assert decision.source == "emergency"
    assert decision.phase == EW


def test_emergency_outranks_the_mqtt_fallback():
    guard = SignalGuard(phase=NS, elapsed_s=60.0)
    decision = guard.decide(proposed_phase=NS, proposed_green_s=30,
                            emergency_approach="W",
                            seconds_since_heartbeat=999)
    assert decision.source == "emergency"


@pytest.mark.parametrize("approach,expected", [
    ("N", NS), ("S", NS), ("E", EW), ("W", EW), ("n", NS), ("e", EW)])
def test_every_approach_maps_to_a_phase(guard, approach, expected):
    decision = guard.decide(proposed_phase=NS, proposed_green_s=30,
                            emergency_approach=approach)
    assert decision.phase == expected


# -------------------------------------------------------- FR-A06 fallback --


def test_a_stale_heartbeat_falls_back_to_webster(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=30,
                            seconds_since_heartbeat=11)
    assert decision.source == "webster"
    assert "FR-A06" in decision.reason


def test_a_heartbeat_inside_the_timeout_does_not_fall_back(guard):
    decision = guard.decide(proposed_phase=EW, proposed_green_s=30,
                            seconds_since_heartbeat=9.9)
    assert decision.source == "policy"


def test_the_fallback_green_is_still_clamped(guard):
    """Webster is a formula, not a trusted oracle. FR-A03 still applies."""
    decision = guard.decide(proposed_phase=EW, proposed_green_s=30,
                            seconds_since_heartbeat=30, webster_green_s=400)
    assert decision.source == "webster"
    assert decision.green_s == 90


# ------------------------------------------------------------ guard state --


def test_a_phase_change_resets_the_elapsed_timer(guard):
    guard.apply(guard.decide(proposed_phase=EW, proposed_green_s=30))
    assert guard.phase == EW and guard.elapsed_s == 0.0


def test_staying_in_phase_accumulates_elapsed(guard):
    before = guard.elapsed_s
    guard.apply(guard.decide(proposed_phase=NS, proposed_green_s=30))
    assert guard.elapsed_s == before + 30


def test_every_decision_states_which_rule_fired(guard):
    """When a signal does something surprising, the question is always which
    rule fired, and an answer reconstructed from logs afterwards is a guess."""
    for kwargs in ({"proposed_phase": EW, "proposed_green_s": 45},
                   {"proposed_phase": EW, "proposed_green_s": 1},
                   {"proposed_phase": EW, "proposed_green_s": 30,
                    "emergency_approach": "N"},
                   {"proposed_phase": EW, "proposed_green_s": 30,
                    "seconds_since_heartbeat": 60}):
        decision = guard.decide(**kwargs)
        assert isinstance(decision, Decision)
        assert decision.reason.strip()


def test_limits_come_from_one_place_not_from_literals():
    """FR-A03..A06's numbers are PRD values. A handler that hardcodes 10 is a
    handler that will disagree with the next one."""
    limits = SafetyLimits()
    assert (limits.min_green_s, limits.max_green_s) == (10, 90)
    assert limits.all_red_s == 3
    assert limits.emergency_response_s == 3
    assert limits.mqtt_timeout_s == 10
