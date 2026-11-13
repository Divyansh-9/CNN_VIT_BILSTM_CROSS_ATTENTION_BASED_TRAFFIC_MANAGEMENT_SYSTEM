"""The edge node, and the fallback that is the point of it (S40, FR-A06).

FR-A06 says the node switches to a locally embedded cycle within 10 seconds of
losing MQTT. That behaviour is the reason this component is interesting and the
hardest thing to exercise against a real broker, so the transport is an
interface and the link is dropped by setting a flag.

A fallback that can only be tested by unplugging something is a fallback nobody
tests.
"""

from __future__ import annotations

import json

import pytest

from contracts.mqtt import ContractError, Mode, QoS
from edge.node import EdgeNode, LocalWebster, RecordingTransport


@pytest.fixture
def node():
    return EdgeNode("j1", RecordingTransport(), last_ack=1000.0)


# --------------------------------------------------------------- NFR-13 --


def test_only_counts_and_heartbeats_are_published(node):
    """No frame ever leaves this process. The published topics are the whole
    surface, so listing them is the check."""
    node.tick({"lane_0": {"car": 3}}, fps=10.0, now=1000.0)
    for topic in node.transport.topics():
        assert topic.endswith(("vehicle_count", "heartbeat"))


def test_no_published_payload_carries_pixels(node):
    node.tick({"lane_0": {"car": 3}}, fps=10.0, now=1000.0)
    for _, payload, _ in node.transport.sent:
        body = json.loads(payload)
        for banned in ("image", "frame", "jpeg", "png", "data"):
            assert banned not in body


# ------------------------------------------------------- the contract --


def test_topics_and_qos_come_from_the_contract(node):
    node.tick({"lane_0": {"car": 3}}, fps=10.0, now=1000.0)
    sent = dict((topic, qos) for topic, _, qos in node.transport.sent)
    assert sent["stms/j1/lane_0/vehicle_count"] == QoS.AT_LEAST_ONCE
    assert sent["stms/j1/system/heartbeat"] == QoS.AT_MOST_ONCE


def test_a_breakdown_that_does_not_sum_is_refused(node):
    """`VehicleCount` enforces it, and the node builds that type rather than a
    dict — so a malformed publish raises here, not at the far end."""
    with pytest.raises(ContractError):
        from contracts.mqtt import VehicleCount

        VehicleCount(count=99, types={"car": 3}, fps=10.0)


def test_an_unknown_vehicle_class_is_refused():
    from contracts.mqtt import VehicleCount

    with pytest.raises(ContractError):
        VehicleCount(count=1, types={"spaceship": 1}, fps=10.0)


# -------------------------------------------------------------- FR-A06 --


def test_a_healthy_link_leaves_the_server_driving(node):
    result = node.tick({"lane_0": {"car": 3}}, fps=10.0, now=1000.0)
    assert result["mode"] is Mode.NORMAL
    assert result["phase"] is None


def test_a_dropped_link_switches_to_the_local_cycle(node):
    node.transport.up = False
    result = node.tick({"lane_0": {"car": 3}}, fps=10.0, now=1011.0)
    assert result["mode"] is Mode.LOCAL
    assert result["phase"] in ("NS", "EW")
    assert result["green_s"] == 30
    assert "FR-A06" in result["reason"]


def test_the_timeout_boundary_is_the_declared_one(node):
    node.transport.up = False
    assert node.tick({"l": {"car": 1}}, 10.0, now=1009.9)["mode"] is Mode.NORMAL
    assert node.tick({"l": {"car": 1}}, 10.0, now=1010.1)["mode"] is Mode.LOCAL


def test_the_node_measures_its_own_publishes_not_a_received_heartbeat(node):
    """A node that cannot publish must notice. A heartbeat sent BY the node
    could never cover the case where the node is the thing that is cut off."""
    node.transport.up = False
    node.tick({"l": {"car": 1}}, 10.0, now=1005.0)
    assert node.last_ack == 1000.0        # unchanged: nothing got through
    node.transport.up = True
    node.tick({"l": {"car": 1}}, 10.0, now=1006.0)
    assert node.last_ack == 1006.0


def test_recovery_returns_to_normal(node):
    node.transport.up = False
    assert node.tick({"l": {"car": 1}}, 10.0, now=1020.0)["mode"] is Mode.LOCAL
    node.transport.up = True
    assert node.tick({"l": {"car": 1}}, 10.0, now=1021.0)["mode"] is Mode.NORMAL


def test_counts_are_not_reported_delivered_when_the_link_is_down(node):
    node.transport.up = False
    assert node.tick({"a": {"car": 1}, "b": {"bus": 1}}, 10.0,
                     now=1001.0)["delivered"] == []


def test_the_heartbeat_reports_degraded_while_degraded(node):
    node.transport.up = False
    node.tick({"l": {"car": 1}}, 10.0, now=1030.0)
    node.transport.up = True
    node.publish_heartbeat(now=1030.0)
    body = json.loads(node.transport.sent[-1][1])
    assert body["edge_status"] == "degraded"


# ------------------------------------------------------- local cycle --


def test_the_local_cycle_alternates():
    webster = LocalWebster()
    assert [webster.step()[0] for _ in range(4)] == ["EW", "NS", "EW", "NS"]


def test_the_local_cycle_is_fixed_time_by_design():
    """The node has lost its link, so it has no measured saturation flow to
    solve with and no way to know its counts are still consumed. A known, safe,
    unsurprising cycle is the right degraded behaviour."""
    webster = LocalWebster()
    assert {webster.step()[1] for _ in range(6)} == {30}
