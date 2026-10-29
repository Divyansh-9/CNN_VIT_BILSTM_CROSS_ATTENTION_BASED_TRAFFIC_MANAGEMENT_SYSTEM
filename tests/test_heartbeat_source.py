"""The heartbeat names the edge's source and lane map, and the server serves it (D22)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import ContractError, Heartbeat, Mode, Topic, decode  # noqa: E402
from edge.node import EdgeNode, RecordingTransport  # noqa: E402

TEXT = {"content-type": "text/plain"}
MARKER = "QUOTEDBACK"
LANES = {"lane_0": "N", "lane_1": "S", "lane_2": "E", "lane_3": "W"}


def replay(session="a1b2c3d4e5f6", position=12.0, duration=180.0):
    return {"kind": "replay", "session": session, "label": "Bellevue_NE8th",
            "position_s": position, "duration_s": duration}


def camera(session="0123456789ab"):
    return {"kind": "camera", "session": session, "label": "NE8th",
            "position_s": None, "duration_s": None}


def beat(source=None, lanes=None, ts=1_800_000_000.0):
    return Heartbeat("online", Mode.NORMAL, False, False, ts=ts, source=source, lanes=lanes)


# ------------------------------------------------------------------ contract --

def test_a_heartbeat_without_a_source_still_decodes_and_reads_as_unknown():
    decoded = decode(Topic.HEARTBEAT, beat().encode())
    assert decoded.source is None and decoded.lanes is None


@pytest.mark.parametrize("source", [replay(), replay(duration=None), camera()])
def test_a_source_and_a_lane_map_round_trip(source):
    decoded = decode(Topic.HEARTBEAT, beat(source, LANES).encode())
    assert dict(decoded.source) == source and dict(decoded.lanes) == LANES


@pytest.mark.parametrize("source", [
    {**replay(), "kind": "live"},                        # a replay cannot call itself live
    {**replay(), "session": "XYZ"},
    {**replay(), "label": f"{MARKER} with spaces"},      # free text never crosses the edge
    {**replay(), "label": "x" * 33},
    {**camera(), "position_s": 4.0},                     # a camera has no clip position
    {**replay(), "position_s": -1.0},
    {**replay(), "position_s": float("nan")},
    replay(position=200.0, duration=180.0),              # past the end of the clip
    {**replay(), "duration_s": 0.0},
    {**replay(), "extra": MARKER},
    {k: v for k, v in replay().items() if k != "session"},
])
def test_a_bad_source_is_refused_without_quoting_it(source):
    with pytest.raises(ContractError) as refused:
        beat(source)
    assert MARKER not in str(refused.value)


@pytest.mark.parametrize("lanes", [
    {"lane_0": "N", "lane_1": "N"},                      # many-to-one is not what the models fit
    {f"{MARKER} lane": "N"},
    {"lane_0": MARKER},
    {},
    {f"lane_{i}": "N" for i in range(5)},
])
def test_a_bad_lane_map_is_refused_without_quoting_it(lanes):
    with pytest.raises(ContractError) as refused:
        beat(lanes=lanes)
    assert MARKER not in str(refused.value)


def test_an_untyped_heartbeat_time_is_refused():
    for ts in (0, -1.0, float("inf"), True, 10**300):
        with pytest.raises(ContractError):
            beat(ts=ts)


# ---------------------------------------------------------------------- edge --

def test_the_node_sends_its_source_and_lanes_on_every_heartbeat():
    node = EdgeNode(intersection_id="j1", transport=RecordingTransport(),
                    source=replay(position=0.0), lanes=dict(LANES))
    node.at_position(6.0)
    node.publish_heartbeat(now=1_800_000_000.0)
    topic, payload, _ = node.transport.sent[-1]
    assert topic == "stms/j1/system/heartbeat"
    sent = json.loads(payload)
    assert sent["source"]["position_s"] == 6.0 and sent["lanes"] == LANES


def test_a_replay_position_past_a_wrong_frame_count_makes_the_duration_unknown():
    node = EdgeNode(intersection_id="j1", transport=RecordingTransport(),
                    source=replay(position=0.0, duration=10.0))
    node.at_position(12.0)
    assert node.source["position_s"] == 12.0 and node.source["duration_s"] is None
    node.publish_heartbeat(now=1_800_000_000.0)         # still a valid heartbeat


def test_a_camera_has_no_position_to_update():
    node = EdgeNode(intersection_id="j1", transport=RecordingTransport(), source=camera())
    node.at_position(1234.5)                             # a camera's ts is a monotonic clock
    assert node.source == camera()


def test_the_source_is_described_by_its_calibration_key_or_clip_never_the_url():
    from edge.run import describe_source, source_label

    settings = SimpleNamespace(source="camera", camera="NE8th")
    first, second = describe_source(settings), describe_source(settings)
    assert first["kind"] == "camera" and first["label"] == "NE8th"
    assert first["session"] != second["session"]         # one session per run
    clip = describe_source(SimpleNamespace(source="D:/x/Bellevue 150th (Newport).mp4",
                                           camera="NE8th"), 180.0)
    assert clip["kind"] == "replay" and clip["duration_s"] == 180.0
    assert clip["label"] == "Bellevue_150th__Newport_"
    beat(clip)                                           # what it builds, the contract takes
    assert len(source_label("x" * 50)) == 32 and source_label("") == "source"


# -------------------------------------------------------------------- server --

@pytest.fixture
def client(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "heartbeat.sqlite")
    return TestClient(server.app, headers=write_headers), server


def test_no_heartbeat_yet_is_a_404_not_a_live_camera(client):
    http, _ = client
    assert http.get("/heartbeat/j1/latest").status_code == 404


def test_the_latest_heartbeat_is_served_with_its_source_lanes_and_age(client):
    http, server = client
    server.store_heartbeat("j1", beat(replay(), LANES).encode())
    body = http.get("/heartbeat/j1/latest").json()
    assert body["source"] == replay() and body["lanes"] == LANES
    assert body["stale"] is False and body["mode"] == "M-NORMAL"
    assert "not when the footage was recorded" in body["note"]


def test_a_heartbeat_older_than_the_link_timeout_is_stale(client, monkeypatch):
    http, server = client
    server.store_heartbeat("j1", beat(camera()).encode())
    received = server.time.time()
    monkeypatch.setattr(server.time, "time", lambda: received + 11.0)
    assert http.get("/heartbeat/j1/latest").json()["stale"] is True


def test_a_heartbeat_without_a_source_is_served_with_source_null(client):
    http, server = client
    server.store_heartbeat("j1", beat().encode())
    assert http.get("/heartbeat/j1/latest").json()["source"] is None


def test_within_a_session_an_older_heartbeat_never_rolls_the_position_back(client):
    http, server = client
    assert server.store_heartbeat("j1", beat(replay(position=40.0), ts=1_800_000_010.0).encode())
    assert server.store_heartbeat("j1", beat(replay(position=38.0), ts=1_800_000_008.0).encode()) is None
    assert http.get("/heartbeat/j1/latest").json()["source"]["position_s"] == 40.0


def test_a_new_session_replaces_the_old_one_whatever_its_clock(client):
    http, server = client
    server.store_heartbeat("j1", beat(replay(position=170.0), ts=1_800_000_100.0).encode())
    # A restart on a clock that went back, now on the camera: the old clip must go.
    server.store_heartbeat("j1", beat(camera(), ts=1_800_000_000.0).encode())
    assert http.get("/heartbeat/j1/latest").json()["source"] == camera()


def test_one_row_per_intersection_however_many_heartbeats(client):
    _, server = client
    for i in range(5):
        server.store_heartbeat("j1", beat(replay(position=float(i)), ts=1_800_000_000.0 + i).encode())
    server.store_heartbeat("j2", beat().encode())
    with sqlite3.connect(server.DATABASE) as connection:
        assert connection.execute("SELECT COUNT(*) FROM heartbeats").fetchone() == (2,)


def test_posting_a_heartbeat_needs_the_write_token_and_a_refusal_does_not_echo(client):
    http, server = client
    from fastapi.testclient import TestClient

    assert TestClient(server.app).post("/heartbeat/j1", content=beat().encode(),
                                       headers=TEXT).status_code == 401
    bad = json.loads(beat().encode())
    bad["source"] = {**replay(), "label": MARKER + " x"}
    refused = http.post("/heartbeat/j1", content=json.dumps(bad), headers=TEXT)
    assert refused.status_code == 422 and MARKER not in refused.text
    assert http.post("/heartbeat/j1", content=beat(camera()).encode(),
                     headers=TEXT).json() == {"intersection_id": "j1", "kept": True}


def test_the_ingest_stores_a_heartbeat(tmp_path, monkeypatch):
    pytest.importorskip("paho.mqtt")
    import server.app as server
    from server.mqtt_ingest import PredictionIngest

    monkeypatch.setattr(server, "DATABASE", tmp_path / "ingest.sqlite")
    receiver = PredictionIngest()
    receiver._on_message(None, None, SimpleNamespace(topic="stms/j1/system/heartbeat",
                                                     payload=beat(camera(), LANES).encode().encode()))
    assert (receiver.stored, len(receiver.refused), len(receiver.failed)) == (1, 0, 0)
    with sqlite3.connect(server.DATABASE) as connection:
        assert connection.execute("SELECT intersection_id FROM heartbeats").fetchall() == [("j1",)]
