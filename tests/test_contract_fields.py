"""P141: the two network-facing payloads are typed to the field, and a refusal
never repeats what the sender wrote.

Only `CongestionPrediction` and `CountForecast` reach the server, over HTTP and
through the MQTT ingest, so they are where schema v2's "no free text across the
edge boundary" has to hold. Before P141:

- `confidences`, `horizon_sec` and `ts` on a prediction, and `ts` on a count
  forecast, were never type-checked, so a string in any of them was accepted
  and stored in SQLite;
- several refusal messages quoted the submitted version, model, approach keys
  or values, and the HTTP endpoints return the message as the 422 body.
"""

from __future__ import annotations

import json
import math
import sqlite3
from types import SimpleNamespace

import pytest

from contracts.mqtt import (CongestionClass, CongestionPrediction, ContractError,
                            CountForecast, Topic, decode)

MARKER = "SECRET-PAYLOAD-MARKER"   # must never come back in a response or reach SQLite


def prediction(**override) -> dict:
    data = json.loads(CongestionPrediction(
        predictions={"N": CongestionClass.LOW, "E": CongestionClass.HIGH},
        confidences={"N": 0.7619926199261993, "E": 0.9123},
        gate_value=0.73, model="G@0123456789ab").encode())
    data.update(override)
    return data


def count_forecast(**override) -> dict:
    data = json.loads(CountForecast(counts={"N": 4.2, "W": 0.0},
                                    model="ridge@0123456789ab").encode())
    data.update(override)
    return data


# ------------------------------------------------ 1. fields typed and bounded --

HUGE = 10 ** 400          # valid JSON, beyond float range: math.isfinite raises on it


def short(value) -> str:
    return repr(value)[:24]


BAD_CONFIDENCE = [MARKER, None, True, -0.01, 1.01, float("nan"), float("inf"), [0.5],
                  {"p": 0.5}, HUGE]
BAD_HORIZON = [MARKER, "60", 60.0, True, 30, 0, -60, None, HUGE]
# 4102444800 is 2100-01-01: the bound that closes a ~300-digit integer channel.
BAD_TS = [MARKER, None, True, float("nan"), float("inf"), -1.0, 0, [1.0], HUGE,
          int("9" * 300), 4_102_444_800, 5e9]


@pytest.mark.parametrize("value", BAD_CONFIDENCE, ids=short)
def test_a_confidence_must_be_a_probability(value):
    with pytest.raises(ContractError, match="confidences"):
        decode(Topic.PREDICTION, json.dumps(prediction(confidences={"N": value, "E": 0.5})))


@pytest.mark.parametrize("value", BAD_HORIZON, ids=short)
@pytest.mark.parametrize("topic, build", [(Topic.PREDICTION, prediction),
                                          (Topic.COUNT_FORECAST, count_forecast)],
                         ids=["prediction", "count-forecast"])
def test_a_horizon_must_be_the_integer_60(topic, build, value):
    with pytest.raises(ContractError, match="horizon_sec"):
        decode(topic, json.dumps(build(horizon_sec=value)))


@pytest.mark.parametrize("value", BAD_TS, ids=short)
@pytest.mark.parametrize("topic, build", [(Topic.PREDICTION, prediction),
                                          (Topic.COUNT_FORECAST, count_forecast)],
                         ids=["prediction", "count-forecast"])
def test_a_timestamp_must_be_positive_finite_epoch_seconds_before_2100(topic, build, value):
    with pytest.raises(ContractError, match="ts"):
        decode(topic, json.dumps(build(ts=value)))


@pytest.mark.parametrize("value", [True, False, MARKER, -0.01, 1.01, float("nan"), HUGE],
                         ids=short)
def test_a_gate_value_must_be_a_number_in_0_1_or_null(value):
    """`true` passed before P141, because bool is an int and True <= 1."""
    with pytest.raises(ContractError, match="gate_value"):
        decode(Topic.PREDICTION, json.dumps(prediction(gate_value=value)))


@pytest.mark.parametrize("value", [True, False, MARKER, -1.0, 201.0, float("nan"), HUGE],
                         ids=short)
def test_a_forecast_count_must_be_a_number_in_range(value):
    """`true` passed before P141, for the same reason as the gate."""
    with pytest.raises(ContractError, match="forecast count"):
        decode(Topic.COUNT_FORECAST, json.dumps(count_forecast(counts={"N": value})))


@pytest.mark.parametrize("topic, data", [
    (Topic.PREDICTION, prediction(model="G@0123456789ab\n")),
    (Topic.COUNT_FORECAST, count_forecast(model="ridge@0123456789ab\n")),
], ids=["prediction", "count-forecast"])
def test_a_model_id_with_a_trailing_newline_is_refused(topic, data):
    """`$` with `re.match` also matches before a final newline."""
    with pytest.raises(ContractError, match="model"):
        decode(topic, json.dumps(data))


@pytest.mark.parametrize("raw", [
    json.dumps(prediction()),
    json.dumps(prediction(confidences={"N": 0, "E": 1})),          # integer bounds
    json.dumps(prediction(ts=1690000000)),                          # integer epoch, as PRD §17
    json.dumps(prediction(gate_value=None)),                        # configs A, B, H
    json.dumps(count_forecast()),
    json.dumps(count_forecast(ts=1690000000)),
], ids=["prediction", "integer-confidences", "integer-ts", "no-gate", "count-forecast",
        "count-integer-ts"])
def test_every_valid_payload_still_decodes(raw):
    decode(Topic.PREDICTION if "predictions" in raw else Topic.COUNT_FORECAST, raw)


def test_what_the_real_producers_emit_still_encodes_and_decodes():
    """The three producers' shapes: measured precision (persistence), a
    four-decimal softmax maximum (MFSTNet) and a four-decimal ridge count."""
    persistence = CongestionPrediction(
        predictions={"N": CongestionClass.MEDIUM}, confidences={"N": 0.5554382259767687},
        gate_value=None, model="persistence@0123456789ab")
    mfstnet = CongestionPrediction(
        predictions={a: CongestionClass.LOW for a in "NSEW"},
        confidences={a: round(0.98765, 4) for a in "NSEW"},
        gate_value=round(0.4321, 4), model="G@0123456789ab")
    ridge = CountForecast(counts={a: round(3.14159, 4) for a in "NSEW"},
                          model="ridge@0123456789ab")
    for topic, payload in ((Topic.PREDICTION, persistence), (Topic.PREDICTION, mfstnet),
                           (Topic.COUNT_FORECAST, ridge)):
        assert decode(topic, payload.encode()) == payload


# ------------------------------------------ 2. refusals do not echo the input --

ECHO_CASES = [
    (Topic.PREDICTION, dict(prediction(), v=MARKER)),
    (Topic.PREDICTION, prediction(model=MARKER)),
    (Topic.PREDICTION, prediction(predictions={MARKER: "LOW"}, confidences={MARKER: 0.5})),
    (Topic.PREDICTION, prediction(gate_value=MARKER)),
    (Topic.PREDICTION, prediction(confidences={"N": MARKER, "E": 0.5})),
    (Topic.PREDICTION, prediction(horizon_sec=MARKER)),
    (Topic.PREDICTION, prediction(ts=MARKER)),
    (Topic.COUNT_FORECAST, dict(count_forecast(), v=MARKER)),
    (Topic.COUNT_FORECAST, count_forecast(model=MARKER)),
    (Topic.COUNT_FORECAST, count_forecast(counts={MARKER: 1.0})),
    (Topic.COUNT_FORECAST, count_forecast(counts={"N": MARKER})),
    (Topic.COUNT_FORECAST, count_forecast(horizon_sec=MARKER)),
    (Topic.COUNT_FORECAST, count_forecast(ts=MARKER)),
    # Messages P141 did not rewrite, pinned so a later edit cannot start quoting:
    (Topic.PREDICTION, prediction(predictions={"N": "LOW"}, confidences={MARKER: 0.5})),
    (Topic.PREDICTION, {k: v for k, v in prediction(model=MARKER).items() if k != "v"}),
    (Topic.PREDICTION, prediction(confidences={"N": HUGE, "E": 0.5}, model=MARKER)),
]
ECHO_IDS = ["version", "model", "approach-key", "gate", "confidence", "horizon", "ts",
            "count-version", "count-model", "count-key", "count-value", "count-horizon",
            "count-ts", "same-lanes", "missing-version", "overflow"]


@pytest.mark.parametrize("topic, data", ECHO_CASES, ids=ECHO_IDS)
def test_a_refusal_never_repeats_the_submitted_value(topic, data):
    with pytest.raises(ContractError) as refused:
        decode(topic, json.dumps(data))
    assert MARKER not in str(refused.value)


@pytest.fixture
def client(tmp_path, monkeypatch, write_headers):
    from fastapi.testclient import TestClient

    import server.app
    monkeypatch.setattr(server.app, "DATABASE", tmp_path / "test.sqlite")
    return TestClient(server.app.app, raise_server_exceptions=False, headers=write_headers)


def stored_rows(database) -> list:
    """Every forecast row stored. A database that was never created holds none:
    the server opens it only after a payload decodes."""
    if not database.exists():
        return []
    with sqlite3.connect(database) as connection:
        return [r for table in ("predictions", "count_forecasts")
                for r in connection.execute(f"SELECT * FROM {table}")]


@pytest.mark.parametrize("topic, data", ECHO_CASES, ids=ECHO_IDS)
def test_over_http_the_refusal_is_422_without_the_value_and_nothing_is_stored(client, topic, data):
    import server.app

    path = "/prediction/x" if topic is Topic.PREDICTION else "/count_forecast/x"
    response = client.post(path, content=json.dumps(data), headers={"content-type": "text/plain"})
    assert response.status_code == 422
    assert MARKER not in response.text
    assert stored_rows(server.app.DATABASE) == []


@pytest.mark.parametrize("topic, data", [
    (Topic.PREDICTION, prediction(confidences={"N": HUGE, "E": 0.5})),
    (Topic.PREDICTION, prediction(gate_value=HUGE)),
    (Topic.PREDICTION, prediction(ts=HUGE)),
    (Topic.COUNT_FORECAST, count_forecast(counts={"N": HUGE})),
    (Topic.COUNT_FORECAST, count_forecast(ts=HUGE)),
], ids=["confidence", "gate", "ts", "count", "count-ts"])
def test_an_integer_beyond_float_range_is_a_refusal_not_a_server_failure(client, topic, data):
    """It used to raise OverflowError: HTTP 500, and the ingest filed it as the
    server's own failure rather than the producer's."""
    pytest.importorskip("paho.mqtt")
    import server.app
    from server.mqtt_ingest import PredictionIngest

    path, mqtt_topic = (("/prediction/x", "stms/x/congestion/prediction")
                        if topic is Topic.PREDICTION else
                        ("/count_forecast/x", "stms/x/count/forecast"))
    raw = json.dumps(data)
    assert client.post(path, content=raw, headers={"content-type": "text/plain"}).status_code == 422
    ingest = PredictionIngest()
    ingest._on_message(None, None, SimpleNamespace(topic=mqtt_topic, payload=raw.encode()))
    assert (len(ingest.refused), len(ingest.failed), ingest.stored) == (1, 0, 0)
    assert stored_rows(server.app.DATABASE) == []


def test_over_http_a_valid_payload_is_still_stored(client):
    import server.app

    for path, data in (("/prediction/x", prediction()), ("/count_forecast/x", count_forecast())):
        response = client.post(path, content=json.dumps(data),
                               headers={"content-type": "text/plain"})
        assert response.status_code == 200
    with sqlite3.connect(server.app.DATABASE) as connection:
        rows = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("predictions", "count_forecasts")}
    assert rows == {"predictions": 1, "count_forecasts": 1}


def test_the_refusal_still_names_the_field_and_what_was_expected():
    """Stable and useful without the value: the field, and the rule."""
    with pytest.raises(ContractError) as refused:
        decode(Topic.PREDICTION, json.dumps(prediction(model=MARKER)))
    assert "model" in str(refused.value) and "config@12-hex" in str(refused.value)
    with pytest.raises(ContractError) as refused:
        decode(Topic.PREDICTION, json.dumps(dict(prediction(), v=MARKER)))
    assert "Version mismatch" in str(refused.value) and "v2" in str(refused.value)


def test_nan_is_not_smuggled_in_as_a_number():
    assert math.isnan(float("nan"))   # the JSON encoder writes NaN; decode must refuse it
    raw = json.dumps(prediction(confidences={"N": float("nan"), "E": 0.5}))
    assert "NaN" in raw
    with pytest.raises(ContractError):
        decode(Topic.PREDICTION, raw)
