"""S65's live benchmark never exposes the camera URL (benchmark_live.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark_live import input_args, redact, source_url  # noqa: E402


@pytest.mark.parametrize("url, shown", [
    ("rtsp://admin:hunter2@192.168.1.64:554/Streaming/Channels/101",
     "rtsp://192.168.1.64:554"),
    ("rtsp://cam.local/live?token=abc123", "rtsp://cam.local"),
    ("rtsps://user:pw@cam.example:322/s", "rtsps://cam.example:322"),
])
def test_credentials_path_and_query_are_never_shown(url, shown):
    assert redact(url) == shown
    for secret in ("hunter2", "admin", "abc123", "token", "pw", "Channels"):
        assert secret not in redact(url) or secret in shown


def test_a_file_standing_in_for_a_camera_shows_its_name_only():
    assert redact("C:/some/dir/h264_1080p.mp4") == "h264_1080p.mp4"


def test_the_url_comes_from_the_environment_not_an_argument(monkeypatch):
    monkeypatch.delenv("STMS_CAMERA_URL", raising=False)
    with pytest.raises(SystemExit, match="environment"):
        source_url("STMS_CAMERA_URL")
    monkeypatch.setenv("STMS_CAMERA_URL", "rtsp://cam/s")
    assert source_url("STMS_CAMERA_URL") == "rtsp://cam/s"


def test_rtsp_uses_tcp_and_a_socket_timeout_so_a_dead_camera_ends_the_read():
    args = input_args("rtsp://cam/s", realtime=False)
    assert args[args.index("-rtsp_transport") + 1] == "tcp"
    assert "-timeout" in args
    assert "-re" not in args


def test_realtime_pacing_is_only_for_a_file_standing_in():
    assert "-re" in input_args("clip.mp4", realtime=True)
    assert "-rtsp_transport" not in input_args("clip.mp4", realtime=True)


# ---------------------------------------------- V2: criteria 5-7, no disk --

def test_capture_refuses_to_write_raw_video_without_an_authorisation(tmp_path):
    from scripts.benchmark_live import capture

    with pytest.raises(SystemExit, match="NFR-13"):
        capture("rtsp://cam/stream", 5, tmp_path / "x.mp4")
    assert not list(tmp_path.iterdir())


def test_timestamps_pass_only_when_monotonic_and_evenly_spaced():
    from scripts.benchmark_live import timestamp_report

    good = timestamp_report([[0, 2, 4, 6, 8], [0, 2, 4]], 2.0)   # a reconnect restarts the clock
    assert good["passed_5"] and good["c5_monotonic"] and good["c5_spacing_ok_share"] == 1.0
    assert not timestamp_report([[0, 2, 1, 3]], 2.0)["passed_5"]      # went backwards
    assert not timestamp_report([[0, 2, 6, 8]], 2.0)["passed_5"]      # a 4 s hole: 1 of 3 off
    assert not timestamp_report([], 2.0)["passed_5"]                  # nothing measured


def test_latency_needs_the_transport_measured_and_both_budgets_met():
    from scripts.benchmark_live import latency_report

    fast = [(t, t + 0.05, t + 0.08) for t in range(100)]
    assert latency_report(fast)["passed_6"]
    assert not latency_report([(t, t + 0.05, None) for t in range(100)])["passed_6"]  # no server
    slow_model = [(t, t + 0.30, t + 0.32) for t in range(100)]
    assert not latency_report(slow_model)["passed_6"]
    slow_link = [(t, t + 0.05, t + 0.40) for t in range(100)]
    assert not latency_report(slow_link)["passed_6"]


def test_freshness_counts_an_unreachable_server_as_stale():
    from scripts.benchmark_live import freshness_report

    assert freshness_report([1.0] * 100)["passed_7"]
    assert not freshness_report([1.0] * 97 + [float("inf")] * 3)["passed_7"]
    assert not freshness_report([])["passed_7"]


def test_http_transport_times_predictions_and_reports_a_down_link():
    from scripts.benchmark_live import HttpTransport

    calls = []
    t = HttpTransport("http://srv:8000/", "live", post=lambda url, body: calls.append(url) or 200)
    t.publish("stms/live/congestion/prediction", "{}", 0)
    t.publish("stms/live/heartbeat", "{}", 0)                       # not timed, not sent
    assert calls == ["http://srv:8000/prediction/live"] and len(t.acknowledged) == 1
    down = HttpTransport("http://srv", "live", post=lambda url, body: 503)
    with pytest.raises(ConnectionError):
        down.publish("stms/live/congestion/prediction", "{}", 0)
