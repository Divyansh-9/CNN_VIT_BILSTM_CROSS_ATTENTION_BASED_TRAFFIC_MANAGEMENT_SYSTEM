"""A malformed payload is a ContractError everywhere, never a crash (P140).

`decode` converted enums and read fields outside its own error handling, and
assumed the JSON was an object. So a payload with an unknown class, a missing
field, a top-level `[]` or `null`, or invalid UTF-8 raised a bare ValueError,
KeyError, AttributeError or UnicodeDecodeError. The HTTP endpoint answered 500
instead of 422, and the MQTT ingest, which caught only ContractError, let it
escape into paho's network thread.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from contracts.mqtt import (CommandSource, CongestionClass, CongestionPrediction,
                            ContractError, Heartbeat, Mode, SignalCommand, Topic, decode)

MARKER = "SECRET-PAYLOAD-MARKER"   # must never reach a record or a log line
TOPIC = "stms/x/congestion/prediction"


def prediction(**override) -> dict:
    data = json.loads(CongestionPrediction(
        predictions={"N": CongestionClass.LOW}, confidences={"N": 1.0},
        gate_value=None, model="persistence@0123456789ab").encode())
    data.update(override)
    return data


def without(data: dict, key: str) -> dict:
    return {k: v for k, v in data.items() if k != key}


UNKNOWN_CLASS = json.dumps(prediction(predictions={"N": MARKER}))
MISSING_PREDICTIONS = json.dumps(without(prediction(), "predictions"))
TOP_LEVEL_ARRAY = "[]"
TOP_LEVEL_NULL = "null"
INVALID_UTF8 = b'{"v": 2, "x": "' + MARKER.encode() + b'\xff\xfe"}'

MALFORMED = [
    (Topic.PREDICTION, UNKNOWN_CLASS),
    (Topic.PREDICTION, MISSING_PREDICTIONS),
    (Topic.PREDICTION, json.dumps(prediction(predictions=["N", "LOW"]))),
    (Topic.PREDICTION, TOP_LEVEL_ARRAY),
    (Topic.PREDICTION, TOP_LEVEL_NULL),
    (Topic.PREDICTION, INVALID_UTF8),
    (Topic.HEARTBEAT, json.dumps(dict(json.loads(Heartbeat(
        edge_status="online", mode=Mode.NORMAL, mfstnet_active=False,
        ppo_active=False).encode()), mode=MARKER))),
    (Topic.SIGNAL_COMMAND, json.dumps(dict(json.loads(SignalCommand(
        phase="NS_GREEN", duration=30, source=CommandSource.PPO_AGENT).encode()),
        source=MARKER))),
]


@pytest.mark.parametrize("topic, raw", MALFORMED, ids=[
    "unknown-class", "missing-predictions", "predictions-not-mapping", "top-level-array",
    "top-level-null", "invalid-utf8", "unknown-mode", "unknown-source"])
def test_every_malformed_payload_is_a_contract_error(topic, raw):
    with pytest.raises(ContractError) as refused:
        decode(topic, raw)
    assert MARKER not in str(refused.value)


def test_a_valid_payload_still_decodes():
    assert decode(Topic.PREDICTION, json.dumps(prediction())).predictions == {
        "N": CongestionClass.LOW}


@pytest.fixture
def database(tmp_path, monkeypatch):
    import server.app
    monkeypatch.setattr(server.app, "DATABASE", tmp_path / "test.sqlite")


@pytest.mark.parametrize("raw", [UNKNOWN_CLASS, MISSING_PREDICTIONS,
                                 TOP_LEVEL_ARRAY, TOP_LEVEL_NULL],
                         ids=["unknown-class", "missing-predictions", "top-level-array",
                              "top-level-null"])
def test_the_http_endpoint_answers_422_not_500(database, raw, write_headers):
    from fastapi.testclient import TestClient

    from server.app import app

    client = TestClient(app, raise_server_exceptions=False, headers=write_headers)
    response = client.post("/prediction/x", content=raw,
                           headers={"content-type": "text/plain"})
    assert response.status_code == 422
    assert MARKER not in response.text


def message(raw) -> SimpleNamespace:
    return SimpleNamespace(topic=TOPIC, payload=raw.encode() if isinstance(raw, str) else raw)


@pytest.fixture
def ingest(database):
    pytest.importorskip("paho.mqtt")
    from server.mqtt_ingest import PredictionIngest
    return PredictionIngest()


@pytest.mark.parametrize("raw", [UNKNOWN_CLASS, TOP_LEVEL_ARRAY, TOP_LEVEL_NULL, INVALID_UTF8],
                         ids=["unknown-class", "top-level-array", "top-level-null",
                              "invalid-utf8"])
def test_a_malformed_message_is_refused_and_the_next_valid_one_is_stored(ingest, raw, caplog):
    with caplog.at_level(logging.DEBUG):
        ingest._on_message(None, None, message(raw))
        ingest._on_message(None, None, message(json.dumps(prediction())))
    assert (len(ingest.refused), ingest.stored, len(ingest.failed)) == (1, 1, 0)
    assert MARKER not in repr(ingest.refused) and MARKER not in caplog.text


def test_a_storage_failure_is_counted_apart_from_refusals_and_ingest_continues(
        ingest, monkeypatch, caplog):
    import server.app

    real = server.app.store_prediction
    calls = []

    def locked_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError(f"database is locked {MARKER}")
        return real(*args, **kwargs)

    monkeypatch.setattr(server.app, "store_prediction", locked_once)
    with caplog.at_level(logging.DEBUG):
        ingest._on_message(None, None, message(json.dumps(prediction())))
        ingest._on_message(None, None, message(json.dumps(prediction())))
    assert (len(ingest.failed), len(ingest.refused), ingest.stored) == (1, 0, 1)
    assert ingest.failed[0][1].startswith("RuntimeError")
    assert "ingest failed to process a message" in caplog.text
    assert MARKER not in repr(ingest.failed) and MARKER not in caplog.text
