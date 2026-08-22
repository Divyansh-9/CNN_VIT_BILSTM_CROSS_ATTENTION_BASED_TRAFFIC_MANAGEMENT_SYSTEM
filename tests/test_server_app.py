"""The control server's routes (S41, PRD §17).

The rules themselves are tested in `test_safety.py` without HTTP. These test
what the *server* adds: validation, persistence, per-intersection state, and the
two properties that are structural rather than behavioural — NFR-13's no-frames
guarantee and FR-A06's clock living on the server.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from server import app as app_module  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", tmp_path / "test.sqlite")
    app_module.guards.clear()
    return TestClient(app_module.app)


def counts(**overrides):
    payload = {"intersection_id": "j1",
               "counts": {"N": 20, "S": 4, "E": 2, "W": 1},
               "queues": {"N": 12, "S": 2, "E": 1, "W": 0}}
    payload.update(overrides)
    return payload


# ------------------------------------------------------------- NFR-13 --


def test_the_request_model_has_no_field_that_could_carry_a_frame():
    """NFR-13 enforced by shape, not by a check somewhere that gets forgotten.

    Raw frames never leave the edge device. A model with an `image` or `frame`
    field would make that a policy rather than a property.
    """
    fields = set(app_module.Counts.model_fields)
    for banned in ("image", "frame", "jpeg", "png", "data", "payload", "blob"):
        assert banned not in fields


def test_no_stored_column_could_hold_a_frame(client):
    client.post("/observation", json=counts())
    import sqlite3
    with sqlite3.connect(app_module.DATABASE) as connection:
        columns = {row[1] for row in
                   connection.execute("PRAGMA table_info(observations)")}
    for banned in ("image", "frame", "blob"):
        assert banned not in columns


# ------------------------------------------------------------ routing --


def test_health_reports_the_limits(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["limits"]["min_green_s"] == 10
    assert body["limits"]["max_green_s"] == 90


def test_an_observation_returns_a_command_with_its_reason(client):
    body = client.post("/observation", json=counts()).json()
    assert body["phase"] in ("NS", "EW")
    assert 10 <= body["green_s"] <= 90
    assert body["reason"].strip()
    assert body["source"] in ("policy", "hold", "webster", "emergency")


def test_an_unknown_approach_is_refused(client):
    """A typo'd key would otherwise read as zero traffic on that approach,
    which is the most dangerous possible default."""
    response = client.post("/observation",
                           json=counts(counts={"N": 5, "NORTH": 9}))
    assert response.status_code == 422
    assert "NORTH" in response.json()["detail"]


# ---------------------------------------------------------- FR-A05/A06 --


def test_an_emergency_preempts_through_the_route(client):
    body = client.post("/observation",
                       json=counts(emergency_approach="E")).json()
    assert body["source"] == "emergency"
    assert body["phase"] == "EW"


def test_a_stale_heartbeat_falls_back_through_the_route(client):
    body = client.post("/observation",
                       json=counts(seconds_since_heartbeat=45)).json()
    assert body["source"] == "webster"
    assert "FR-A06" in body["reason"]


def test_the_timeout_is_measured_on_the_server_not_the_edge(client):
    """A device that has crashed cannot report that it has crashed. If the
    timeout were measured by the sender it would never fire in the case it
    exists for — so the edge reports when it last spoke and the server judges."""
    fresh = client.post("/observation",
                        json=counts(seconds_since_heartbeat=0)).json()
    stale = client.post("/observation",
                        json=counts(seconds_since_heartbeat=999)).json()
    assert fresh["source"] != "webster"
    assert stale["source"] == "webster"


# ------------------------------------------------------------- state --


def test_each_intersection_keeps_its_own_guard(client):
    client.post("/observation", json=counts(intersection_id="a"))
    client.post("/observation", json=counts(intersection_id="b"))
    assert set(app_module.guards) == {"a", "b"}
    assert app_module.guards["a"] is not app_module.guards["b"]


def test_history_returns_what_was_recorded(client):
    for _ in range(3):
        client.post("/observation", json=counts())
    body = client.get("/history/j1").json()
    assert len(body["rows"]) == 3
    assert all(row["reason"] for row in body["rows"])


def test_history_of_an_unknown_intersection_is_empty_not_an_error(client):
    assert client.get("/history/nowhere").json()["rows"] == []


def test_the_history_limit_is_bounded(client):
    """An unbounded limit is a denial-of-service by query string."""
    client.post("/observation", json=counts())
    assert len(client.get("/history/j1?limit=100000").json()["rows"]) <= 500
