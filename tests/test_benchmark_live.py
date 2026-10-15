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
