"""D1: the deployed detector's class names reach the wire only through the
project's decided mapping, and no class name can crash the edge loop.

The ITD detector says 'two wheeler', 'autorickshaw', 'LCV', 'bicycle' and
'pedestrain'; the contract's `VehicleCount` accepts PRD §12.2's eight classes.
`EdgeNode.tick` built a `VehicleCount` from the detector's names and raised an
uncaught ContractError on the first two-wheeler, which ended the edge loop and
with it FR-A06's local cycle (Phase C, finding D1).

The mapping is the one the project already decided (`scripts/pseudo_label.py`,
`class_mapping.yaml`, DATASETS §6): LCV merges into truck, bicycle is dropped
rather than merged. It is not a new taxonomy decision, and no PCU weighting is
introduced: every kept vehicle still counts one.
"""

from __future__ import annotations

import logging

import pytest

from contracts.mqtt import VEHICLE_CLASSES

ITD = ["two wheeler", "autorickshaw", "car", "bus", "LCV", "truck", "bicycle", "pedestrain"]


def classes():
    import edge.classes as module
    return module


def test_every_itd_class_has_an_explicit_decision():
    mapping = classes().load_itd_mapping()
    assert set(mapping) == set(ITD), "a detector class with no decision would be guessed at"


def test_the_decided_mapping_in_wire_spelling():
    mapping = classes().load_itd_mapping()
    assert mapping == {"two wheeler": "motorcycle", "autorickshaw": "auto-rickshaw",
                       "car": "car", "bus": "bus", "LCV": "truck", "truck": "truck",
                       "pedestrain": "pedestrian", "bicycle": None}
    assert all(v in VEHICLE_CLASSES for v in mapping.values() if v is not None)


def test_the_yaml_agrees_with_the_mapping_pseudo_labelling_already_uses():
    from scripts.pseudo_label import ITD_TO_OURS

    yaml_mapping = {k: v for k, v in classes().load_itd_mapping(spelling="dataset").items()
                    if v is not None}
    assert yaml_mapping == ITD_TO_OURS


def test_normalise_maps_merges_drops_and_reports():
    kept, dropped, unknown = classes().normalise(
        {"two wheeler": 3, "LCV": 1, "truck": 2, "bicycle": 4, "car": 5},
        classes().load_itd_mapping())
    assert kept == {"motorcycle": 3, "truck": 3, "car": 5}
    assert dropped == {"bicycle": 4} and unknown == {}


def test_an_unknown_class_is_reported_not_guessed_and_does_not_raise():
    kept, dropped, unknown = classes().normalise({"spaceship": 2, "car": 1},
                                                 classes().load_itd_mapping())
    assert kept == {"car": 1} and dropped == {} and unknown == {"spaceship": 2}


def test_contract_names_pass_through_unchanged():
    kept, dropped, unknown = classes().normalise({"car": 2, "motorcycle": 1, "auto-rickshaw": 1})
    assert kept == {"car": 2, "motorcycle": 1, "auto-rickshaw": 1}
    assert dropped == {} and unknown == {}


# ------------------------------------------------------------------ the node --

def node(**kwargs):
    from edge.node import EdgeNode, RecordingTransport
    return EdgeNode(intersection_id="j1", transport=RecordingTransport(), **kwargs)


def test_a_node_with_the_detector_mapping_publishes_valid_counts_from_detector_names():
    from contracts.mqtt import Topic, decode

    n = node(detector_classes=classes().load_itd_mapping())
    out = n.tick({"lane_0": {"two wheeler": 2, "bicycle": 1, "LCV": 1}}, fps=0.5, now=1.0)
    assert out["delivered"] == ["lane_0"]
    topic, payload, _ = n.transport.sent[0]
    count = decode(Topic.VEHICLE_COUNT, payload)
    assert count.types == {"motorcycle": 2, "truck": 1} and count.count == 3
    assert n.excluded == {"bicycle": 1}


@pytest.mark.parametrize("kwargs, types", [
    ({}, {"two wheeler": 2}),                                      # no mapping configured
    ({"detector_classes": "itd"}, {"spaceship": 1, "car": 3}),     # a class with no decision
], ids=["detector-name-without-mapping", "unknown-class-beside-known"])
def test_an_undecided_class_withholds_the_count_and_never_crashes_the_loop(kwargs, types, caplog):
    """Withheld, not understated: publishing the car alone would report 3
    vehicles where 4 were seen, which is the missing-as-zero error (P97a)."""
    if kwargs.get("detector_classes") == "itd":
        kwargs = {"detector_classes": classes().load_itd_mapping()}
    n = node(**kwargs)
    with caplog.at_level(logging.WARNING):
        out = n.tick({"lane_0": types}, fps=0.5, now=1.0)
    assert out["delivered"] == [] and out["mode"].value == "M-NORMAL"
    assert not [t for t, _, _ in n.transport.sent if t.endswith("vehicle_count")]
    assert "withheld" in caplog.text


def test_the_local_cycle_is_still_reached_when_every_count_is_refused():
    """If counts can never be delivered the node must still fall back (FR-A06),
    not die: a refused publish is not an acknowledgement."""
    n = node()
    n.last_ack = 0.0
    out = n.tick({"lane_0": {"spaceship": 1}}, fps=0.5, now=11.0)
    assert out["mode"].value == "M-LOCAL" and out["green_s"] == 30
