"""NFR-11: both MQTT clients can authenticate, and a credential never leaks.

Before this, neither `MqttTransport` (edge) nor `PredictionIngest` (server)
could send a username or password, so a broker configured as NFR-11 requires
(`allow_anonymous false`) refused both. These tests need no broker. The ones
in `test_mqtt_live.py` prove the same against a real broker that enforces
authentication.
"""

from __future__ import annotations

import pytest

pytest.importorskip("paho.mqtt")

from contracts.broker import (PASSWORD_ENV, USERNAME_ENV, CredentialError,  # noqa: E402
                              Credentials, credentials_from_env)

#: A synthetic canary, not a credential: if it appears in output, something leaked.
CANARY = "canary-value-for-leak-checks"


def test_neither_variable_set_means_an_anonymous_connection():
    assert credentials_from_env({}) is None
    assert credentials_from_env({USERNAME_ENV: "", PASSWORD_ENV: ""}) is None


def test_both_variables_set_give_credentials():
    creds = credentials_from_env({USERNAME_ENV: " edge-ne8th ", PASSWORD_ENV: CANARY})
    assert creds == Credentials("edge-ne8th", CANARY)


def test_the_password_is_not_in_the_repr():
    creds = Credentials("edge-ne8th", CANARY)
    assert CANARY not in repr(creds) and CANARY not in str(creds)


@pytest.mark.parametrize("environ, named", [
    ({USERNAME_ENV: "edge-ne8th"}, PASSWORD_ENV),
    ({USERNAME_ENV: "edge-ne8th", PASSWORD_ENV: ""}, PASSWORD_ENV),
    ({PASSWORD_ENV: CANARY}, USERNAME_ENV),
    ({USERNAME_ENV: "  ", PASSWORD_ENV: CANARY}, USERNAME_ENV),
])
def test_half_a_credential_is_refused_and_names_the_variable_not_the_value(environ, named):
    with pytest.raises(CredentialError) as refused:
        credentials_from_env(environ)
    message = str(refused.value)
    assert f"{named} is not" in message
    assert CANARY not in message and "edge-ne8th" not in message


@pytest.fixture
def username_pw_set_calls(monkeypatch):
    import paho.mqtt.client as mqtt

    calls = []
    original = mqtt.Client.username_pw_set

    def spy(self, username, password=None):
        calls.append((username, password))
        return original(self, username, password)

    monkeypatch.setattr(mqtt.Client, "username_pw_set", spy)
    return calls


@pytest.mark.parametrize("build", ["edge", "server"])
def test_each_client_sends_credentials_only_when_given(build, username_pw_set_calls):
    from edge.mqtt_transport import MqttTransport
    from server.mqtt_ingest import PredictionIngest

    make = {"edge": lambda c: MqttTransport(client_id="edge-x", credentials=c),
            "server": lambda c: PredictionIngest(credentials=c)}[build]
    make(None)
    assert username_pw_set_calls == []
    make(Credentials("edge-ne8th", CANARY))
    assert username_pw_set_calls == [("edge-ne8th", CANARY)]


def test_a_refused_connection_is_recorded_by_reason_code_only():
    from paho.mqtt.reasoncodes import ReasonCode
    from paho.mqtt.packettypes import PacketTypes

    from edge.mqtt_transport import MqttTransport
    from server.mqtt_ingest import PredictionIngest

    refused = ReasonCode(PacketTypes.CONNACK, "Not authorized")
    for client in (MqttTransport(client_id="edge-x", credentials=Credentials("u", CANARY)),
                   PredictionIngest(credentials=Credentials("u", CANARY))):
        client._on_connect(client.client, None, None, refused)
        assert client.connect_refused == "Not authorized"
        assert CANARY not in client.connect_refused


def test_the_ingest_refuses_half_a_credential_at_start_up(monkeypatch, capsys):
    from server import mqtt_ingest

    monkeypatch.setenv(USERNAME_ENV, "server-ingest")
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    with pytest.raises(SystemExit) as stop:
        mqtt_ingest.main(["--port", "1"])
    assert PASSWORD_ENV in str(stop.value) and "server-ingest" not in str(stop.value)


def test_the_start_up_line_names_every_subscribed_topic():
    # It used to name the prediction topic only, though the ingest also
    # subscribes to the count forecast (ADR-027).
    from contracts.mqtt import Topic
    from server.mqtt_ingest import INGESTED, subscription_summary

    # Since D21 it also takes the observed per-lane counts, for FR-UI03, and
    # since D22 the heartbeat, which names the edge's source.
    line = subscription_summary("127.0.0.1", 1883)
    # Since D26 the forecast checks too (ADR-014 §2).
    assert line == ("subscribed to stms/+/congestion/prediction, stms/+/count/forecast, "
                    "stms/+/+/vehicle_count, stms/+/system/heartbeat and "
                    "stms/+/forecast/check on 127.0.0.1:1883")
    assert {Topic.PREDICTION, Topic.COUNT_FORECAST, Topic.VEHICLE_COUNT,
            Topic.HEARTBEAT, Topic.FORECAST_CHECK} == set(INGESTED)
