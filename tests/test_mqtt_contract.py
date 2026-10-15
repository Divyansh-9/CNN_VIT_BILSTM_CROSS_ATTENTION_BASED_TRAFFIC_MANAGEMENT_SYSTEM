"""Cross-topic MQTT contract test (PLAN-01 WI-09-adjacent, TRIAGE-001).

Written before three owners build against the schema in different weeks, which
is the only time this test is cheap.

    python -m pytest tests/test_mqtt_contract.py -q
"""

from __future__ import annotations

import pytest

from contracts.mqtt import (
    SCHEMA_VERSION,
    VEHICLE_CLASSES,
    CommandSource,
    CongestionClass,
    CongestionPrediction,
    ContractError,
    EmergencyDetect,
    Heartbeat,
    Mode,
    QoS,
    SignalCommand,
    Topic,
    VehicleCount,
    decode,
)


# ------------------------------------------------------------------- QoS --

@pytest.mark.parametrize(
    "topic, qos",
    [
        (Topic.VEHICLE_COUNT, QoS.AT_LEAST_ONCE),
        (Topic.EMERGENCY, QoS.EXACTLY_ONCE),
        (Topic.SIGNAL_COMMAND, QoS.AT_LEAST_ONCE),
        (Topic.PREDICTION, QoS.AT_MOST_ONCE),
        (Topic.HEARTBEAT, QoS.AT_MOST_ONCE),
    ],
)
def test_qos_matches_prd_17_1(topic, qos):
    assert topic.qos is qos


def test_emergency_is_exactly_once_and_that_is_not_a_preference():
    """A duplicate fires a spurious preemption; a loss risks a life."""
    assert Topic.EMERGENCY.qos == 2


def test_qos_cannot_be_overridden_per_call():
    """The structural fix. QoS is attached to the topic, so three owners cannot
    pass three different levels for the same topic in three different weeks."""
    with pytest.raises(AttributeError):
        Topic.EMERGENCY.qos = QoS.AT_MOST_ONCE  # type: ignore[misc]


# ---------------------------------------------------------------- topics --

def test_per_lane_topics_render_with_a_lane():
    assert Topic.VEHICLE_COUNT.render("int01", "N") == "stms/int01/N/vehicle_count"
    assert Topic.EMERGENCY.render("int01", "S") == "stms/int01/S/emergency/detect"


def test_a_per_lane_topic_without_a_lane_is_an_error():
    with pytest.raises(ContractError, match="per-lane"):
        Topic.VEHICLE_COUNT.render("int01")


def test_a_global_topic_with_a_lane_is_an_error():
    with pytest.raises(ContractError, match="not per-lane"):
        Topic.SIGNAL_COMMAND.render("int01", "N")


# ------------------------------------------------------- D1 · one spelling --

def test_the_wire_spelling_is_medium_not_med():
    assert CongestionClass.MEDIUM.value == "MEDIUM"
    with pytest.raises(ValueError):
        CongestionClass("MED")


def test_a_raw_string_prediction_is_rejected():
    with pytest.raises(ContractError, match="never MED"):
        CongestionPrediction(
            predictions={"N": "MEDIUM"},  # type: ignore[dict-item]
            confidences={"N": 0.9}, gate_value=0.5, model="G@0123456789ab",
        )


# ------------------------------------------------- D2 · types is specified --

def test_types_must_use_the_eight_prd_classes():
    with pytest.raises(ContractError, match="unknown vehicle class"):
        VehicleCount(count=1, types={"spaceship": 1}, fps=12.0)


def test_types_must_sum_to_count():
    """A breakdown that disagrees with its total is worse than no breakdown —
    a consumer cannot tell which number to trust."""
    with pytest.raises(ContractError, match="types sum to"):
        VehicleCount(count=10, types={"car": 3}, fps=12.0)


def test_a_consistent_count_is_accepted():
    vc = VehicleCount(count=5, types={"car": 3, "motorcycle": 2}, fps=12.4)
    assert vc.count == 5
    assert set(vc.types) <= set(VEHICLE_CLASSES)


# ---------------------------------------------------- D3 · operating mode --

def test_heartbeat_carries_the_operating_mode():
    hb = Heartbeat("online", Mode.NORMAL, mfstnet_active=True, ppo_active=True)
    assert hb.mode is Mode.NORMAL


def test_all_five_srs_modes_exist():
    assert {m.value for m in Mode} == {
        "M-PREEMPT", "M-MANUAL", "M-LOCAL", "M-NO-PREDICT", "M-NORMAL"
    }


def test_a_raw_string_mode_is_rejected():
    with pytest.raises(ContractError, match="FR-UI01"):
        Heartbeat("online", "M-NORMAL", True, True)  # type: ignore[arg-type]


# --------------------------------------------------- D4 · command sources --

def test_all_four_command_sources_exist():
    assert {s.value for s in CommandSource} == {
        "ppo_agent", "webster_fallback", "emergency", "manual"
    }


def test_a_raw_string_source_is_rejected():
    with pytest.raises(ContractError, match="CommandSource"):
        SignalCommand("NS_GREEN", 45, "ppo_agent")  # type: ignore[arg-type]


# ------------------------------------------------------ D5 · schema version --

def test_every_payload_carries_a_version():
    payloads = [
        VehicleCount(1, {"car": 1}, 12.0),
        EmergencyDetect("ambulance", 0.91, 3),
        SignalCommand("NS_GREEN", 45, CommandSource.PPO_AGENT),
        CongestionPrediction({"N": CongestionClass.HIGH}, {"N": 0.9}, 0.7, "G@0123456789ab"),
        Heartbeat("online", Mode.NORMAL, True, True),
    ]
    for p in payloads:
        assert f'"v":{SCHEMA_VERSION}' in p.encode()


def test_a_version_mismatch_says_so_rather_than_looking_malformed():
    """Without this, every other mismatch presents as bad data and the debugging
    starts in the wrong place."""
    raw = '{"count":1,"types":{"car":1},"fps":12.0,"ts":0,"v":99}'
    with pytest.raises(ContractError, match="Version mismatch"):
        decode(Topic.VEHICLE_COUNT, raw)


def test_an_unversioned_payload_is_rejected():
    with pytest.raises(ContractError, match="no 'v' field"):
        decode(Topic.VEHICLE_COUNT, '{"count":1,"types":{"car":1},"fps":12.0,"ts":0}')


# ------------------------------------------------- D6 · string to state value --

@pytest.mark.parametrize(
    "cls, value", [(CongestionClass.LOW, 0.0), (CongestionClass.MEDIUM, 0.5),
                   (CongestionClass.HIGH, 1.0)]
)
def test_class_maps_to_the_normalised_state_value(cls, value):
    """PRD §13.1 divides by 2, so HIGH maps to 1.0."""
    assert cls.to_state_value() == value


def test_state_values_come_out_in_lane_order():
    pred = CongestionPrediction(
        predictions={"N": CongestionClass.HIGH, "S": CongestionClass.MEDIUM,
                     "E": CongestionClass.LOW, "W": CongestionClass.LOW},
        confidences={l: 0.9 for l in "NSEW"}, gate_value=0.73, model="G@0123456789ab",
    )
    assert pred.to_state_values() == [1.0, 0.5, 0.0, 0.0]


def test_a_missing_lane_yields_zero_and_the_vector_keeps_its_length():
    """FR-A06 zeroes indices 11–14 when MFSTNet is unavailable. Shortening the
    vector instead would invalidate every trained checkpoint."""
    pred = CongestionPrediction(
        predictions={"N": CongestionClass.HIGH},
        confidences={"N": 0.9}, gate_value=0.5, model="G@0123456789ab",
    )
    values = pred.to_state_values()
    assert len(values) == 4
    assert values == [1.0, 0.0, 0.0, 0.0]


# ------------------------------------------------------- round trip --

@pytest.mark.parametrize(
    "topic, payload",
    [
        (Topic.VEHICLE_COUNT, VehicleCount(5, {"car": 3, "motorcycle": 2}, 12.4, ts=1.0)),
        (Topic.EMERGENCY, EmergencyDetect("ambulance", 0.91, 3, ts=1.0)),
        (Topic.SIGNAL_COMMAND, SignalCommand("NS_GREEN", 45, CommandSource.PPO_AGENT, ts=1.0)),
        (Topic.HEARTBEAT, Heartbeat("online", Mode.LOCAL, False, True, ts=1.0)),
    ],
)
def test_every_payload_round_trips(topic, payload):
    assert decode(topic, payload.encode()) == payload


def test_prediction_round_trips_with_its_enums_intact():
    pred = CongestionPrediction(
        predictions={"N": CongestionClass.HIGH, "S": CongestionClass.LOW},
        confidences={"N": 0.87, "S": 0.91}, gate_value=0.73,
        model="G@0123456789ab", ts=1.0,
    )
    back = decode(Topic.PREDICTION, pred.encode())
    assert back.predictions["N"] is CongestionClass.HIGH
    assert back.gate_value == 0.73


def test_gate_value_survives_the_round_trip():
    """FR-UI05 and BR-07 depend on it. A16 removed the gate from the PPO STATE,
    not from this payload — a reader of that amendment might delete it here."""
    pred = CongestionPrediction({"N": CongestionClass.LOW}, {"N": 0.5}, 0.42, "G@0123456789ab", ts=1.0)
    assert decode(Topic.PREDICTION, pred.encode()).gate_value == 0.42


# ------------------------------------------------------ requirement guards --

def test_emergency_below_the_fr_p04_threshold_is_rejected():
    with pytest.raises(ContractError, match="0.75"):
        EmergencyDetect("ambulance", 0.60, 3)


def test_a_single_frame_emergency_is_rejected():
    """The conjunction is the contract: one high-confidence frame is not
    evidence, and a spurious preemption costs every approach its green."""
    with pytest.raises(ContractError, match="consecutive"):
        EmergencyDetect("ambulance", 0.99, 1)


@pytest.mark.parametrize("duration", [5, 95])
def test_a_green_outside_fr_a03_bounds_is_rejected(duration):
    with pytest.raises(ContractError, match="FR-A03"):
        SignalCommand("NS_GREEN", duration, CommandSource.PPO_AGENT)


def test_all_red_is_exempt_from_the_green_bounds():
    SignalCommand("ALL_RED", 3, CommandSource.EMERGENCY)


def test_a_gate_value_outside_zero_one_is_rejected():
    with pytest.raises(ContractError, match="gate_value"):
        CongestionPrediction({"N": CongestionClass.LOW}, {"N": 0.5}, 1.7, "m")


def test_predictions_and_confidences_must_cover_the_same_lanes():
    with pytest.raises(ContractError, match="same lanes"):
        CongestionPrediction(
            {"N": CongestionClass.LOW}, {"N": 0.5, "S": 0.5}, 0.5, "m"
        )


# --------------------------------------------------------------------------
#  NFR-13 by size: nothing frame-sized crosses the boundary
# --------------------------------------------------------------------------

def test_a_frame_smuggled_through_a_free_text_field_is_refused():
    import base64

    from contracts.mqtt import (MAX_PAYLOAD_BYTES, CongestionClass,
                                CongestionPrediction, ContractError)

    frame = base64.b64encode(bytes(30_000)).decode()     # a small JPEG
    # Refused twice over in v2: the model id is a pattern, so the frame never
    # reaches the size cap. The cap is the second line, for any future field.
    with pytest.raises(ContractError, match="config@12-hex"):
        CongestionPrediction(
            predictions={"N": CongestionClass.LOW}, confidences={"N": 0.9},
            gate_value=0.5, model=frame)
    assert MAX_PAYLOAD_BYTES < 30_000


def test_an_oversized_inbound_payload_is_refused_before_parsing():
    from contracts.mqtt import ContractError, Topic, decode

    with pytest.raises(ContractError, match="cap"):
        decode(Topic.PREDICTION, '{"x":"' + "A" * 10_000 + '"}')


def test_real_payloads_sit_far_below_the_cap():
    from contracts.mqtt import (MAX_PAYLOAD_BYTES, CongestionClass,
                                CongestionPrediction)

    payload = CongestionPrediction(
        predictions={l: CongestionClass.HIGH for l in "NSEW"},
        confidences={l: 0.97 for l in "NSEW"}, gate_value=0.53,
        model="G@4cc8c2b41f2d")
    assert len(payload.encode()) < MAX_PAYLOAD_BYTES // 10


# --------------------------------------------------------------------------
#  schema v2: no free text crosses the boundary (ADR-026)
# --------------------------------------------------------------------------

def test_prediction_keys_must_be_approaches():
    from contracts.mqtt import CongestionClass, CongestionPrediction, ContractError

    with pytest.raises(ContractError, match="approaches"):
        CongestionPrediction(predictions={"lane_0": CongestionClass.LOW},
                             confidences={"lane_0": 0.9}, gate_value=None,
                             model="H@0123456789ab")


def test_an_absent_gate_is_none_and_survives_the_round_trip():
    from contracts.mqtt import (CongestionClass, CongestionPrediction, Topic,
                                decode)

    sent = CongestionPrediction(predictions={"N": CongestionClass.HIGH},
                                confidences={"N": 0.8}, gate_value=None,
                                model="H@0123456789ab")
    assert decode(Topic.PREDICTION, sent.encode()).gate_value is None


def test_emergency_type_is_a_closed_set():
    from contracts.mqtt import ContractError, EmergencyDetect

    EmergencyDetect("ambulance", 0.9, 3)
    with pytest.raises(ContractError, match="unknown emergency type"):
        EmergencyDetect("aGVsbG8gd29ybGQ=", 0.9, 3)
