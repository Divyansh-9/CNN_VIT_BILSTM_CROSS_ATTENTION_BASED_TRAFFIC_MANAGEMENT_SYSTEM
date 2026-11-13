"""Observed counts are kept 48 h and pruned at most hourly, driven by writes (D24)."""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import (CongestionClass, CongestionPrediction, Heartbeat, Mode,  # noqa: E402
                            VehicleCount)

NOW = 1_800_000_000.0
H = 3600.0


@pytest.fixture
def server(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "retention.sqlite")
    monkeypatch.setattr(server, "_next_prune", 0.0)
    server.connect().close()
    return server


def put(server, at, intersection="j1", lane="lane_0"):
    with sqlite3.connect(server.DATABASE) as connection:
        connection.execute("INSERT INTO vehicle_counts VALUES (?,?,?,?,?)", (at, intersection, lane, 1, 0.5))


def ages(server):
    with sqlite3.connect(server.DATABASE) as connection:
        return sorted(round((NOW - at) / H, 2) for (at,) in connection.execute("SELECT at FROM vehicle_counts"))


def test_rows_older_than_48_hours_go_and_the_cutoff_itself_stays(server):
    for age in (47.9, 48.0, 48.1, 100.0, 0.0):
        put(server, NOW - age * H)
    assert server.prune_vehicle_counts(NOW) == 2
    assert ages(server) == [0.0, 47.9, 48.0]


def test_pruning_twice_deletes_nothing_more(server):
    put(server, NOW - 49 * H)
    assert server.prune_vehicle_counts(NOW) == 1
    assert server.prune_vehicle_counts(NOW) == 0


def test_every_intersection_and_lane_is_pruned_alike(server):
    for intersection, lane in (("j1", "lane_0"), ("j2", "lane_3")):
        put(server, NOW - 50 * H, intersection, lane)
        put(server, NOW - 1 * H, intersection, lane)
    server.prune_vehicle_counts(NOW)
    assert ages(server) == [1.0, 1.0]


def test_only_observed_counts_are_pruned(server):
    """Forecasts and the heartbeat are not raw counts and keep their own rules."""
    server.store_prediction("j1", CongestionPrediction(
        {"N": CongestionClass.LOW}, {"N": 0.8}, None, "persistence@2431c6641b9c").encode())
    server.store_heartbeat("j1", Heartbeat("online", Mode.NORMAL, False, False).encode())
    with sqlite3.connect(server.DATABASE) as connection:
        for table in ("predictions", "heartbeats"):
            connection.execute(f"UPDATE {table} SET at = ?", (NOW - 100 * H,))
    put(server, NOW - 100 * H)
    server.prune_vehicle_counts(NOW)
    with sqlite3.connect(server.DATABASE) as connection:
        assert [connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("vehicle_counts", "predictions", "heartbeats")] == [0, 1, 1]


def test_pruning_runs_at_most_hourly(server, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "prune_vehicle_counts", lambda now: calls.append(now) or 0)
    for t in (NOW, NOW + 600, NOW + 3599, NOW + 3600, NOW + 3700):
        server.maybe_prune_vehicle_counts(t)
    assert calls == [NOW, NOW + 3600]


def test_a_failed_prune_is_logged_retried_soon_and_never_fails_the_store(server, monkeypatch, caplog):
    attempts = []

    def locked(now):
        attempts.append(now)
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(server, "prune_vehicle_counts", locked)
    with caplog.at_level(logging.WARNING, logger=server.log.name):
        payload = server.store_vehicle_count("j1", "lane_0", VehicleCount(2, {"car": 2}, 0.5).encode())
    assert payload.count == 2
    assert "prune failed (OperationalError)" in caplog.text
    first = attempts[0]
    server.maybe_prune_vehicle_counts(first + 30)       # inside the retry wait: not yet
    server.maybe_prune_vehicle_counts(first + 61)       # after it: tried again, not an hour later
    assert len(attempts) == 2
    with sqlite3.connect(server.DATABASE) as connection:
        assert connection.execute("SELECT COUNT(*) FROM vehicle_counts").fetchone() == (1,)


def test_storing_a_count_prunes_and_the_24_hour_view_is_untouched(server, monkeypatch):
    from fastapi.testclient import TestClient

    put(server, NOW - 60 * H)                            # expired
    put(server, NOW - 23 * H)                            # inside the longest view
    monkeypatch.setattr(server.time, "time", lambda: NOW)
    server.store_vehicle_count("j1", "lane_0", VehicleCount(3, {"car": 3}, 0.5).encode())
    assert ages(server) == [0.0, 23.0]
    view = TestClient(server.app).get("/vehicle_count/j1/history?window=24h").json()
    assert sum(b["lanes"].get("lane_0", {}).get("n", 0) for b in view["buckets"]) == 2
