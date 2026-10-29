"""Observed vehicle counts: stored per lane and served aggregated for FR-UI03 (D21)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import ContractError, Topic, VehicleCount, check_lane  # noqa: E402

TEXT = {"content-type": "text/plain"}
MARKER = "QUOTEDBACK"


@pytest.fixture
def client(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "counts.sqlite")
    return TestClient(server.app, headers=write_headers), server


def count(n, types=None):
    return VehicleCount(count=n, types=types or {"car": n}, fps=0.5).encode()


def disagreeing():
    """A payload whose breakdown disagrees with its total, written as the wire would carry it:
    the contract refuses to build one, so it has to be edited after encoding."""
    data = json.loads(count(1))
    data["count"] = 2
    return json.dumps(data)


def put(server, lane, n, at):
    """A row at a chosen time, as the store would have written it."""
    with sqlite3.connect(server.DATABASE) as connection:
        server.connect().close()                     # create the tables
        connection.execute("INSERT INTO vehicle_counts VALUES (?,?,?,?,?)", (at, "j1", lane, n, 0.5))


# ------------------------------------------------------------ the contract --


def test_a_lane_name_gets_the_ids_bounds_and_is_never_quoted():
    assert check_lane("lane_0") == "lane_0"
    for bad in ("", "lane 0", "x" * 33, f"{MARKER}\n", None, 3):
        with pytest.raises(ContractError) as refused:
            check_lane(bad)
        assert MARKER not in str(refused.value)


# ------------------------------------------------------------- storing --


def test_a_count_is_stored_per_lane_as_a_measurement(client):
    http, server = client
    assert http.post("/vehicle_count/j1/lane_0", content=count(3), headers=TEXT).json() == \
        {"intersection_id": "j1", "lane": "lane_0", "count": 3}
    with sqlite3.connect(server.DATABASE) as connection:
        assert connection.execute("SELECT intersection_id, lane, count FROM vehicle_counts").fetchall() == \
            [("j1", "lane_0", 3)]


def test_a_bad_lane_or_payload_is_refused_and_not_quoted(client):
    http, server = client
    for path, raw in ((f"/vehicle_count/j1/{MARKER}x{'y' * 40}", count(1)),
                      ("/vehicle_count/j1/lane_0", '{"v": 1, "count": -1}'),
                      ("/vehicle_count/j1/lane_0", disagreeing())):    # types disagree with the total
        response = http.post(path, content=raw, headers=TEXT)
        assert response.status_code == 422
        assert MARKER not in response.text
    with sqlite3.connect(server.DATABASE) as connection:
        server.connect().close()
        assert connection.execute("SELECT COUNT(*) FROM vehicle_counts").fetchone() == (0,)


def test_no_stored_column_could_hold_a_frame(client):
    http, server = client
    http.post("/vehicle_count/j1/lane_0", content=count(1), headers=TEXT)
    with sqlite3.connect(server.DATABASE) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(vehicle_counts)")}
    assert columns == {"at", "intersection_id", "lane", "count", "fps"}    # NFR-13: numbers only


def test_writing_a_count_needs_the_write_token(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "counts.sqlite")
    assert TestClient(server.app).post("/vehicle_count/j1/lane_0", content=count(1),
                                       headers=TEXT).status_code in (401, 403)


# ----------------------------------------------------- FR-UI03 windows --


@pytest.mark.parametrize("window, size, n", [("1h", 60, 60), ("6h", 300, 72), ("24h", 900, 96)])
def test_each_window_is_a_fixed_number_of_aligned_buckets(client, window, size, n):
    _, server = client
    view = server.count_buckets("j1", window, now=100_000.0)
    assert (view["bucket_s"], len(view["buckets"])) == (size, n)
    assert view["end"] % size == 0 and view["end"] > 100_000.0 >= view["end"] - size
    assert [b["t"] for b in view["buckets"]] == list(range(view["start"], view["end"], size))


def test_a_bucket_is_the_mean_of_its_samples_and_says_how_many(client):
    _, server = client
    now = 120_000.0                                   # buckets of 60 s, the last one is [120000, 120060)
    for at, n in ((119_940.0, 2), (119_950.0, 4), (119_999.0, 6), (120_010.0, 1)):
        put(server, "lane_0", n, at)
    put(server, "lane_1", 0, 119_945.0)               # a real zero
    buckets = server.count_buckets("j1", "1h", now)["buckets"]
    assert buckets[-2] == {"t": 119_940, "lanes": {"lane_0": {"mean": 4.0, "n": 3},
                                                    "lane_1": {"mean": 0.0, "n": 1}}}
    assert buckets[-1]["lanes"] == {"lane_0": {"mean": 1.0, "n": 1}}


def test_a_gap_stays_a_gap_and_a_missing_lane_is_absent_not_zero(client):
    _, server = client
    now = 120_000.0
    put(server, "lane_0", 3, 119_000.0)
    put(server, "lane_0", 5, 119_990.0)
    view = server.count_buckets("j1", "1h", now)
    filled = [b for b in view["buckets"] if b["lanes"]]
    assert len(filled) == 2                           # everything between them is empty, not zero
    assert all("lane_1" not in b["lanes"] for b in view["buckets"])
    assert view["lanes"] == ["lane_0"]


def test_rows_outside_the_window_and_other_intersections_are_left_out(client):
    _, server = client
    now = 120_000.0
    put(server, "lane_0", 9, now - 3 * 3600)          # older than the 1 h window
    with sqlite3.connect(server.DATABASE) as connection:
        connection.execute("INSERT INTO vehicle_counts VALUES (?,?,?,?,?)", (now - 10, "j2", "lane_0", 7, 0.5))
    assert all(not b["lanes"] for b in server.count_buckets("j1", "1h", now)["buckets"])
    assert any(b["lanes"] for b in server.count_buckets("j1", "6h", now)["buckets"])


def test_the_endpoint_takes_only_the_three_windows(client):
    http, _ = client
    assert http.get("/vehicle_count/j1/history").json()["window"] == "1h"
    for window in ("6h", "24h"):
        assert http.get(f"/vehicle_count/j1/history?window={window}").status_code == 200
    for bad in ("2h", "1H", "1h;", "86400"):
        assert http.get(f"/vehicle_count/j1/history?window={bad}").status_code == 422
    assert http.get(f"/vehicle_count/{MARKER}.x/history").status_code == 422


def test_the_view_says_it_is_a_measurement_not_a_forecast(client):
    http, _ = client
    note = http.get("/vehicle_count/j1/history").json()["note"]
    assert "observed" in note and "not a forecast" in note and "never zero" in note


# ---------------------------------------------------------- the ingest --


@pytest.fixture
def ingest(tmp_path, monkeypatch):
    pytest.importorskip("paho.mqtt")
    import server.app as server
    from server.mqtt_ingest import PredictionIngest

    monkeypatch.setattr(server, "DATABASE", tmp_path / "ingest.sqlite")
    return PredictionIngest(), server


def test_the_ingest_routes_a_lane_count_and_checks_the_lane():
    from server.mqtt_ingest import route

    assert route("stms/j1/lane_0/vehicle_count") == ("j1", Topic.VEHICLE_COUNT)
    for topic in (f"stms/j1/{MARKER}.x/vehicle_count", "stms/j1/lane_0/emergency/detect"):
        with pytest.raises(ContractError) as refused:
            route(topic)
        assert MARKER not in str(refused.value)


def test_the_ingest_stores_a_lane_count_and_refuses_a_bad_one(ingest):
    receiver, server = ingest
    receiver._on_message(None, None, SimpleNamespace(topic="stms/j1/lane_2/vehicle_count",
                                                     payload=count(4).encode()))
    receiver._on_message(None, None, SimpleNamespace(topic="stms/j1/lane_2/vehicle_count",
                                                     payload=b'{"v": 1, "count": -1}'))
    assert (receiver.stored, len(receiver.refused), len(receiver.failed)) == (1, 1, 0)
    with sqlite3.connect(server.DATABASE) as connection:
        assert connection.execute("SELECT lane, count FROM vehicle_counts").fetchall() == [("lane_2", 4)]
