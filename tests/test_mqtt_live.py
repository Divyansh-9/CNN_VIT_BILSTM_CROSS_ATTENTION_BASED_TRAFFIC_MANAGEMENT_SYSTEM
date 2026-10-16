"""Edge to broker to server over a real MQTT broker (ADR-026).

Every other edge test uses `RecordingTransport`. This one starts an actual
broker on a free local port, connects the edge's `MqttTransport` and the
server's `PredictionIngest` to it, and checks that a prediction published at
the edge is stored by the server — and that a payload the contract refuses is
not. It needs a broker; it uses amqtt (pure Python) and skips without it.

    AMQTT_PYTHON=<python with amqtt installed> pytest tests/test_mqtt_live.py

`AMQTT_PYTHON` lets the broker run from an environment of its own, so its
dependencies never meet the project's. Without it, the current interpreter is
used if it can import amqtt.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("paho.mqtt")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def broker_command(config: Path) -> list[str] | None:
    python = os.environ.get("AMQTT_PYTHON")
    if python:
        script = Path(python).with_name("amqtt.exe" if os.name == "nt" else "amqtt")
        if script.is_file():
            return [str(script), "-c", str(config)]
        return [python, "-m", "amqtt.scripts.broker_script", "-c", str(config)]
    found = shutil.which("amqtt")
    return [found, "-c", str(config)] if found else None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def broker(tmp_path):
    port = free_port()
    config = tmp_path / "broker.yaml"
    config.write_text(
        "listeners:\n  default:\n    type: tcp\n"
        f"    bind: 127.0.0.1:{port}\n"
        "plugins:\n  amqtt.plugins.authentication.AnonymousAuthPlugin:\n"
        "    allow_anonymous: true\n", encoding="utf-8")
    command = broker_command(config)
    if command is None:
        pytest.skip("no amqtt broker available; set AMQTT_PYTHON")
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.2)
    else:
        process.kill()
        pytest.skip("broker did not start")
    yield port
    process.kill()
    process.wait(timeout=10)


@pytest.fixture
def database(tmp_path, monkeypatch):
    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "live.sqlite")
    return server


def wait_until(predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_a_prediction_published_at_the_edge_is_stored_by_the_server(
        broker, database):
    from fastapi.testclient import TestClient

    from contracts.mqtt import CongestionClass, CongestionPrediction
    from edge.mqtt_transport import MqttTransport
    from edge.node import EdgeNode
    from server.mqtt_ingest import PredictionIngest

    ingest = PredictionIngest(port=broker)
    transport = MqttTransport(port=broker, client_id="edge-j7")
    try:
        assert ingest.start(), "server could not subscribe"
        assert transport.start(), "edge could not connect"
        node = EdgeNode(intersection_id="j7", transport=transport)
        sent = CongestionPrediction(
            predictions={a: CongestionClass.HIGH for a in "NSEW"},
            confidences={a: 0.81 for a in "NSEW"}, gate_value=None,
            model="H@0123456789ab")
        assert node.publish_prediction(sent)
        assert wait_until(lambda: ingest.stored == 1)
    finally:
        transport.stop()
        ingest.stop()

    latest = TestClient(database.app).get("/prediction/j7/latest").json()
    assert latest["model"] == "H@0123456789ab"
    assert latest["predictions"] == {a: "HIGH" for a in "NSEW"}
    assert latest["gate_value"] is None
    assert latest["state_11_14"] == [1.0, 1.0, 1.0, 1.0]


def test_a_payload_the_contract_refuses_is_counted_not_stored(broker, database):
    import paho.mqtt.client as mqtt

    from server.mqtt_ingest import PredictionIngest

    ingest = PredictionIngest(port=broker)
    rogue = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rogue")
    try:
        assert ingest.start()
        rogue.connect("127.0.0.1", broker)
        rogue.loop_start()
        info = rogue.publish("stms/j7/congestion/prediction",
                             '{"v":2,"predictions":{},"confidences":{},'
                             '"gate_value":null,"model":"aGVsbG8="}', qos=1)
        info.wait_for_publish(timeout=5)
        assert wait_until(lambda: len(ingest.refused) == 1)
        assert ingest.stored == 0
        assert "aGVsbG8" not in ingest.refused[0][1]
    finally:
        rogue.loop_stop()
        rogue.disconnect()
        ingest.stop()


def test_publishing_without_a_broker_raises_so_fr_a06_can_fire():
    from edge.mqtt_transport import MqttTransport

    transport = MqttTransport(port=free_port(), client_id="edge-alone")
    with pytest.raises(ConnectionError):
        transport.publish("stms/j7/heartbeat", "{}", 0)


def test_a_three_lane_camera_reports_its_missing_approach(database):
    """P97a: south is absent, not LOW. Since P109 the state values carry null
    for it, never 0.0, and the response also names it as missing."""
    from fastapi.testclient import TestClient

    from contracts.mqtt import CongestionClass, CongestionPrediction

    payload = CongestionPrediction(
        predictions={a: CongestionClass.MEDIUM for a in "NEW"},
        confidences={a: 0.7 for a in "NEW"}, gate_value=None,
        model="G@0123456789ab")
    client = TestClient(database.app)
    posted = client.post("/prediction/j3", content=payload.encode(),
                         headers={"content-type": "text/plain"}).json()
    assert posted["missing_approaches"] == ["S"]
    assert posted["state_11_14"] == [2 / 3, None, 2 / 3, 2 / 3]   # S absent, not LOW
    assert client.get("/prediction/j3/latest").json()["missing_approaches"] == ["S"]
