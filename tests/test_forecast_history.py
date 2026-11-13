"""Forecast history: what the server recorded, read back (S42)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import CongestionClass, CongestionPrediction, CountForecast  # noqa: E402

TEXT = {"content-type": "text/plain"}


@pytest.fixture
def client(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "history.sqlite")
    return TestClient(server.app, headers=write_headers), server


def post_class(http, classes):
    prediction = CongestionPrediction(
        predictions={a: CongestionClass(c) for a, c in classes.items()},
        confidences={a: 0.7 for a in classes}, gate_value=None,
        model="persistence@2431c6641b9c")
    assert http.post("/prediction/j1", content=prediction.encode(), headers=TEXT).status_code == 200


def post_count(http, counts):
    forecast = CountForecast(counts=counts, model="ridge@73532968dcf2")
    assert http.post("/count_forecast/j1", content=forecast.encode(), headers=TEXT).status_code == 200


def test_class_history_is_newest_first_and_lists_absences(client):
    http, _ = client
    post_class(http, {"N": "LOW", "S": "MEDIUM", "E": "HIGH", "W": "LOW"})
    post_class(http, {"N": "HIGH", "E": "LOW"})
    rows = http.get("/prediction/j1/history").json()["rows"]
    assert [r["predictions"] for r in rows] == [{"N": "HIGH", "E": "LOW"},
                                               {"N": "LOW", "S": "MEDIUM", "E": "HIGH", "W": "LOW"}]
    assert rows[0]["missing_approaches"] == ["S", "W"]      # absent, never LOW
    assert rows[0]["role"] == "congestion_class (persistence)"
    assert rows[0]["at"] >= rows[1]["at"]


def test_count_history_keeps_a_real_zero_and_an_absence_apart(client):
    http, _ = client
    post_count(http, {"N": 0.0, "E": 2.5})
    row = http.get("/count_forecast/j1/history").json()["rows"][0]
    assert row["counts"] == {"N": 0.0, "E": 2.5}
    assert row["missing_approaches"] == ["S", "W"]
    assert row["role"] == "next_minute_count (ridge)"


def test_the_two_histories_never_mix(client):
    http, _ = client
    post_class(http, {"N": "LOW"})
    assert http.get("/count_forecast/j1/history").json()["rows"] == []
    assert len(http.get("/prediction/j1/history").json()["rows"]) == 1


def test_nothing_recorded_is_an_empty_list_not_an_error(client):
    http, _ = client
    for path in ("/prediction/j1/history", "/count_forecast/j1/history"):
        response = http.get(path)
        assert response.status_code == 200
        assert response.json() == {"intersection_id": "j1", "rows": []}


def test_limit_is_at_least_one_and_clamped_above(client, monkeypatch):
    http, server = client
    for _ in range(3):
        post_count(http, {"N": 1.0})
    assert len(http.get("/count_forecast/j1/history?limit=2").json()["rows"]) == 2
    assert http.get("/count_forecast/j1/history?limit=0").status_code == 422
    assert http.get("/count_forecast/j1/history?limit=-1").status_code == 422
    monkeypatch.setattr(server, "HISTORY_MAX", 2)
    assert len(http.get("/count_forecast/j1/history?limit=100").json()["rows"]) == 2


def test_an_invalid_intersection_id_is_refused_without_being_quoted(client):
    http, _ = client
    for path in ("/prediction/%3Cscript%3E/history", "/count_forecast/a.b/history"):
        response = http.get(path)
        assert response.status_code == 422
        assert "<script>" not in response.text


def test_history_reads_stay_open_without_a_token(client):
    from fastapi.testclient import TestClient

    _, server = client
    reader = TestClient(server.app)
    assert reader.get("/prediction/j1/history").status_code == 200
    assert reader.get("/count_forecast/j1/history").status_code == 200
