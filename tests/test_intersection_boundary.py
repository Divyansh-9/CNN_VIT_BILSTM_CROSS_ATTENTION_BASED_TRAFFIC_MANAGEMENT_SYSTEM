"""P142: the intersection id is a closed pattern everywhere it enters the
server, and no framework-generated error repeats what the sender wrote.

The id arrives outside the payload — in the URL path, in the MQTT topic, and
in the `/observation` body — so the 4,096-byte payload cap never applied to
it. It was stored in SQLite and echoed back, at any length (P141's review
stored a 48,000-character one). FastAPI's own 422s quoted the submitted
input, and `/observation` stored `emergency_approach` as free text.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from types import SimpleNamespace
from urllib.parse import quote

import pytest

import contracts.mqtt as contract
from contracts.mqtt import (CongestionClass, CongestionPrediction, ContractError,
                            CountForecast)


def check_intersection_id(value):
    # Looked up at call time, so a run against the code before P142 reports
    # each case rather than one import error.
    return contract.check_intersection_id(value)

MARKER = "SECRETMARKER"   # must never come back in a response, a record, a log or a row

VALID_IDS = ["j1", "int01", "live", "a", "A-b_9", "x" * 32]
INVALID_IDS = {
    "too-long": "x" * 33,
    "huge": MARKER * 1000,               # 12,000 characters
    "dot": f"{MARKER}.x",
    "trailing-newline": f"{MARKER}\n",   # passes `match` with `$`; only `fullmatch` refuses it
    "space": f"{MARKER} x",
    "non-ascii": f"{MARKER}ü",
    "plus": f"{MARKER}+",
    "percent": f"{MARKER}%",
}


def prediction() -> str:
    return CongestionPrediction(predictions={"N": CongestionClass.LOW}, confidences={"N": 0.8},
                                gate_value=None, model="G@0123456789ab").encode()


def count_forecast() -> str:
    return CountForecast(counts={"N": 2.0}, model="ridge@0123456789ab").encode()


def observation(**override) -> dict:
    body = {"intersection_id": "j1", "counts": {"N": 3, "S": 1, "E": 0, "W": 2},
            "queues": {"N": 1, "S": 0, "E": 0, "W": 1}}
    body.update(override)
    return body


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import server.app
    monkeypatch.setattr(server.app, "DATABASE", tmp_path / "test.sqlite")
    monkeypatch.setattr(server.app, "guards", {})
    return TestClient(server.app.app, raise_server_exceptions=False)


def stored(database) -> list:
    if not database.exists():
        return []
    with sqlite3.connect(database) as connection:
        return [r for table in ("predictions", "count_forecasts", "observations")
                for r in connection.execute(f"SELECT * FROM {table}")]


def text(*things) -> str:
    return " ".join(repr(t) for t in things)


# ----------------------------------------------------------------- the rule --

@pytest.mark.parametrize("identifier", VALID_IDS)
def test_a_valid_id_passes(identifier):
    assert check_intersection_id(identifier) == identifier


@pytest.mark.parametrize("identifier", list(INVALID_IDS.values()) + ["", None, 7],
                         ids=list(INVALID_IDS) + ["empty", "none", "int"])
def test_an_invalid_id_is_refused_without_being_quoted(identifier):
    with pytest.raises(ContractError) as refused:
        check_intersection_id(identifier)
    assert MARKER not in str(refused.value) and "1 to 32" in str(refused.value)


# ------------------------------------------------------------------- HTTP --

@pytest.mark.parametrize("identifier", list(INVALID_IDS.values()), ids=list(INVALID_IDS))
def test_every_endpoint_refuses_an_invalid_id_and_stores_nothing(client, identifier):
    import server.app

    # Percent-encoded, as a real client sends it; the route handler receives the
    # decoded id. httpx refuses a raw control character such as a newline.
    path_id = quote(identifier, safe="")
    calls = [
        ("post", f"/prediction/{path_id}", prediction()),
        ("post", f"/count_forecast/{path_id}", count_forecast()),
        ("get", f"/prediction/{path_id}/latest", None),
        ("get", f"/count_forecast/{path_id}/latest", None),
        ("get", f"/history/{path_id}", None),
    ]
    for method, path, body in calls:
        if method == "post":
            response = client.post(path, content=body, headers={"content-type": "text/plain"})
        else:
            response = client.get(path)
        assert response.status_code == 422, path[:40]
        assert MARKER not in response.text, path[:40]
    response = client.post("/observation", json=observation(intersection_id=identifier))
    assert response.status_code == 422 and MARKER not in response.text
    assert stored(server.app.DATABASE) == []


@pytest.mark.parametrize("identifier", VALID_IDS)
def test_every_endpoint_still_serves_a_valid_id(client, identifier):
    headers = {"content-type": "text/plain"}
    assert client.post(f"/prediction/{identifier}", content=prediction(), headers=headers).status_code == 200
    assert client.post(f"/count_forecast/{identifier}", content=count_forecast(),
                       headers=headers).status_code == 200
    assert client.get(f"/prediction/{identifier}/latest").status_code == 200
    assert client.get(f"/count_forecast/{identifier}/latest").status_code == 200
    assert client.post("/observation", json=observation(intersection_id=identifier)).status_code == 200
    assert len(client.get(f"/history/{identifier}").json()["rows"]) == 1


def test_a_404_for_a_valid_id_does_not_quote_it(client):
    for path in ("/prediction/nowhere/latest", "/count_forecast/nowhere/latest"):
        response = client.get(path)
        assert response.status_code == 404 and "nowhere" not in response.text


# ------------------------------------------------- framework-level echoes --

@pytest.mark.parametrize("path, kwargs", [
    ("/prediction/j1", {"json": {"x": MARKER}}),                 # JSON-typed body
    ("/count_forecast/j1", {"json": [MARKER]}),
    ("/observation", {"json": observation(counts={MARKER: 1})}),
    ("/observation", {"json": observation(queues={MARKER: 1})}),
    ("/observation", {"json": observation(emergency_approach=MARKER)}),
    ("/observation", {"json": observation(counts={"N": MARKER})}),
    ("/observation", {"content": f'{{"intersection_id": "{MARKER}', "headers": {"content-type": "application/json"}}),
], ids=["json-prediction", "json-count", "count-key", "queue-key", "emergency", "count-value",
        "broken-json"])
def test_a_request_validation_error_never_repeats_the_input(client, path, kwargs):
    import server.app

    response = client.post(path, **kwargs)
    assert response.status_code == 422
    assert MARKER not in response.text
    assert "input" not in response.json()["detail"][0]
    assert stored(server.app.DATABASE) == []


@pytest.mark.parametrize("limit", [MARKER, "-1", "0"])
def test_history_refuses_a_bad_limit_without_quoting_it(client, limit):
    response = client.get(f"/history/j1?limit={limit}")
    assert response.status_code == 422 and MARKER not in response.text


def test_history_still_clamps_a_large_limit(client):
    import server.app

    assert client.post("/observation", json=observation()).status_code == 200
    with sqlite3.connect(server.app.DATABASE) as connection:
        row = connection.execute("SELECT * FROM observations").fetchone()
        connection.executemany(f"INSERT INTO observations VALUES ({','.join('?' * len(row))})",
                               [row] * 600)
    assert len(client.get("/history/j1?limit=100000").json()["rows"]) == 500


def test_a_validation_error_still_says_which_field_and_why(client):
    detail = client.post("/observation", json=observation(emergency_approach="NE")).json()["detail"]
    assert detail[0]["loc"] == ["body", "emergency_approach"]
    assert detail[0]["msg"] and detail[0]["type"]


@pytest.mark.parametrize("approach", ["N", "S", "E", "W", None])
def test_a_valid_emergency_approach_is_still_accepted(client, approach):
    response = client.post("/observation", json=observation(emergency_approach=approach))
    assert response.status_code == 200


@pytest.mark.parametrize("approach", ["n", "e"])
def test_a_lower_case_emergency_approach_still_preempts(client, approach):
    """SignalGuard has always upper-cased it; refusing it would drop the command."""
    response = client.post("/observation", json=observation(emergency_approach=approach))
    assert response.status_code == 200 and response.json()["source"] == "emergency"


# ----------------------------------------------- /observation numeric bounds --

@pytest.mark.parametrize("field, value", [
    ("counts", {"N": -1}), ("counts", {"N": 10_001}), ("counts", {"N": 2 ** 63 - 1}),
    ("counts", {"N": 10 ** 30}), ("queues", {"N": -5}), ("queues", {"N": 10_001}),
    ("seconds_since_heartbeat", -1.0), ("seconds_since_heartbeat", 1.2345678901234567e300),
    ("seconds_since_heartbeat", 1_000_001.0), ("forecast_age_s", -0.5),
    ("forecast_age_s", 1e308), ("forecast", {"N": MARKER}), ("forecast", {MARKER: "LOW"}),
], ids=["count-negative", "count-over", "count-int64", "count-overflow", "queue-negative",
        "queue-over", "heartbeat-negative", "heartbeat-huge", "heartbeat-over",
        "forecast-age-negative", "forecast-age-huge", "forecast-class", "forecast-key"])
def test_an_out_of_bound_observation_is_refused_and_stores_nothing(client, field, value):
    import server.app

    response = client.post("/observation", json=observation(**{field: value}))
    assert response.status_code == 422 and MARKER not in response.text
    assert stored(server.app.DATABASE) == []


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_a_non_finite_heartbeat_age_is_refused_rather_than_skipping_the_fallback(client, literal):
    """`NaN > timeout` is False, so a NaN age used to bypass the FR-A06 fallback."""
    body = json.dumps(observation()).replace('"counts"', f'"seconds_since_heartbeat": {literal}, "counts"')
    response = client.post("/observation", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("field, value", [
    ("counts", {"N": 0, "S": 10_000}), ("seconds_since_heartbeat", 0.0),
    ("seconds_since_heartbeat", 12.5), ("forecast_age_s", 3.0),
    ("forecast", {"N": "LOW", "E": "HIGH"}),
], ids=["count-bounds", "heartbeat-zero", "heartbeat-stale", "forecast-age", "forecast"])
def test_an_in_bound_observation_is_still_accepted(client, field, value):
    assert client.post("/observation", json=observation(**{field: value})).status_code == 200


def test_a_stale_heartbeat_still_triggers_the_fallback(client):
    response = client.post("/observation", json=observation(seconds_since_heartbeat=12.5))
    assert response.json()["source"] == "webster"


# -------------------------------------------- redirects and the access log --

@pytest.mark.parametrize("path, headers", [
    (f"/history/{MARKER}.x/", {}),
    (f"/prediction/{MARKER}x/latest/", {}),
    (f"/health/?q={MARKER}", {"host": f"{MARKER}.example"}),
], ids=["history", "latest", "health-query-host"])
def test_a_trailing_slash_is_not_redirected_with_the_path_in_a_header(client, path, headers):
    response = client.get(path, headers=headers, follow_redirects=False)
    assert not 300 <= response.status_code < 400
    assert "location" not in response.headers
    assert MARKER not in response.text and MARKER not in repr(dict(response.headers))


@pytest.mark.parametrize("target, logged", [
    ("/prediction/j1/latest", "/prediction/j1/latest"),
    ("/history/j1?limit=5", "/history/j1?<query>"),
    (f"/history/{MARKER}%0A%3Cscript%3E", "<refused path>"),
    ("/history/" + MARKER * 500, "<refused path>"),
    (f"/health?q={MARKER}", "/health?<query>"),
    ("/evidence", "/evidence"),
    (f"/history/{MARKER}x/", "<unmatched path>"),        # plain tokens, but no route: a 404
    (f"/{MARKER}/{MARKER}", "<unmatched path>"),
    # The review's case: a route matches, but the id is one the contract refuses.
    # `.` passes the segment test and not INTERSECTION_ID.
    (f"/history/{MARKER}.x", "<refused path>"),
    (f"/prediction/{MARKER}.x/latest", "<refused path>"),
    (f"/count_forecast/{MARKER}.x/latest?limit=1", "<refused path>"),
    ("/history/" + "x" * 33, "<refused path>"),           # plain token, one char too long
    ("/history/" + "x" * 32, "/history/" + "x" * 32),     # the longest valid id is logged
], ids=["plain", "query", "encoded", "huge", "query-marker", "evidence", "trailing-slash",
        "no-route", "dotted-id-history", "dotted-id-latest", "dotted-id-with-query",
        "id-33-chars", "id-32-chars"])
def test_the_access_log_line_never_holds_a_refused_target_or_a_query(target, logged):
    import server.app

    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                               '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:5000", "GET", target, "1.1", 422), None)
    assert server.app.AccessLogFilter().filter(record)
    assert record.getMessage() == f'127.0.0.1:5000 - "GET {logged} HTTP/1.1" 422'
    assert any(isinstance(f, server.app.AccessLogFilter)
               for f in logging.getLogger("uvicorn.access").filters)


@pytest.fixture
def static_mount(tmp_path):
    """The `/dashboard` mount as `server.app` adds it when `dashboard/dist`
    exists. A built dist is absent in a test checkout, so it is added here."""
    from fastapi.staticfiles import StaticFiles
    from fastapi.routing import Mount

    import server.app

    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    mount = Mount("/dashboard", app=StaticFiles(directory=tmp_path, html=True), name="dashboard")
    server.app.app.router.routes.append(mount)
    yield
    server.app.app.router.routes.remove(mount)


@pytest.mark.parametrize("target, logged", [
    (f"/dashboard/{MARKER}", "/dashboard/<static>"),
    (f"/dashboard/{MARKER}/{MARKER}.js?q={MARKER}", "/dashboard/<static>?<query>"),
    ("/dashboard/", "/dashboard/<static>"),
    ("/dashboard/assets/index-CuJEFCth.js", "/dashboard/<static>"),
], ids=["sub-path", "nested-with-query", "root", "real-asset"])
def test_a_static_mount_is_logged_without_its_sender_chosen_sub_path(static_mount, target, logged):
    """The review's second case: a mount matches ANY sub-path, so matching it
    says nothing about whether the sub-path is safe to log."""
    import server.app

    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                               '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:5000", "GET", target, "1.1", 404), None)
    server.app.AccessLogFilter().filter(record)
    assert record.getMessage() == f'127.0.0.1:5000 - "GET {logged} HTTP/1.1" 404'
    assert MARKER not in record.getMessage()


# -------------------------------------------------------------- MQTT ingest --

@pytest.fixture
def ingest(client):
    pytest.importorskip("paho.mqtt")
    from server.mqtt_ingest import PredictionIngest
    return PredictionIngest()


@pytest.mark.parametrize("identifier", list(INVALID_IDS.values()), ids=list(INVALID_IDS))
def test_the_ingest_refuses_an_invalid_topic_id_and_never_records_or_logs_it(ingest, identifier, caplog):
    import server.app

    with caplog.at_level(logging.DEBUG):
        for topic, raw in ((f"stms/{identifier}/congestion/prediction", prediction()),
                           (f"stms/{identifier}/count/forecast", count_forecast())):
            ingest._on_message(None, None, SimpleNamespace(topic=topic, payload=raw.encode()))
    assert (len(ingest.refused), len(ingest.failed), ingest.stored) == (2, 0, 0)
    assert MARKER not in text(ingest.refused, ingest.failed) and MARKER not in caplog.text
    assert len(text(ingest.refused)) < 200          # bounded, whatever the topic length
    assert stored(server.app.DATABASE) == []


def test_a_storage_failure_on_a_valid_topic_is_still_recorded_with_its_topic(ingest, monkeypatch):
    import server.app

    def broken(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(server.app, "store_prediction", broken)
    ingest._on_message(None, None, SimpleNamespace(topic="stms/j1/congestion/prediction",
                                                   payload=prediction().encode()))
    assert ingest.failed and ingest.failed[0][0] == "stms/j1/congestion/prediction"


@pytest.mark.parametrize("identifier", ["j1", "x" * 32])
def test_the_ingest_still_stores_a_valid_topic_id(ingest, identifier):
    for topic, raw in ((f"stms/{identifier}/congestion/prediction", prediction()),
                       (f"stms/{identifier}/count/forecast", count_forecast())):
        ingest._on_message(None, None, SimpleNamespace(topic=topic, payload=raw.encode()))
    assert (ingest.stored, len(ingest.refused), len(ingest.failed)) == (2, 0, 0)


@pytest.mark.parametrize("topic", [
    f"stms/{MARKER}.x/congestion/prediction",       # routable shape, bad id
    f"stms/{MARKER}/x/y",                           # not an ingested topic at all
    f"stms/{MARKER}",                               # too few levels
], ids=["bad-id", "unknown-topic", "short"])
def test_route_refuses_without_quoting_the_topic(topic):
    from server.mqtt_ingest import route

    with pytest.raises(ContractError) as refused:
        route(topic)
    assert MARKER not in str(refused.value)


def test_intersection_of_refuses_a_count_topic_without_quoting_it():
    from server.mqtt_ingest import intersection_of

    with pytest.raises(ContractError) as refused:
        intersection_of(f"stms/{MARKER}/count/forecast")     # MARKER is a valid id
    assert MARKER not in str(refused.value)


def test_a_refusal_is_logged_without_the_topic(ingest, caplog):
    with caplog.at_level(logging.WARNING, logger="server.mqtt_ingest"):
        ingest._on_message(None, None, SimpleNamespace(
            topic=f"stms/{MARKER}.x/congestion/prediction", payload=prediction().encode()))
    assert "ingest refused a message on <unrouted topic>" in caplog.text
    assert MARKER not in caplog.text


@pytest.mark.parametrize("identifier", list(INVALID_IDS.values()), ids=list(INVALID_IDS))
def test_an_edge_node_refuses_an_invalid_id_at_start_up(identifier):
    from edge.node import EdgeNode, RecordingTransport

    with pytest.raises(ContractError) as refused:
        EdgeNode(intersection_id=identifier, transport=RecordingTransport())
    assert MARKER not in str(refused.value)


def test_an_edge_node_with_a_valid_id_still_publishes():
    from edge.node import EdgeNode, RecordingTransport

    transport = RecordingTransport()
    EdgeNode(intersection_id="j1", transport=transport).publish_heartbeat(now=1.0)
    assert transport.topics() == ["stms/j1/system/heartbeat"]
