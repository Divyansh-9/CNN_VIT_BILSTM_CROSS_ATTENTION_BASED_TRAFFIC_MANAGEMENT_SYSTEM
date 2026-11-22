import pytest

from server.camera_monitor import CameraMonitor, camera_source
from scripts.video_history import VideoHistory


@pytest.mark.parametrize("source", ["file:///tmp/private", "ftp://camera", "rtsp://", "bad input"])
def test_rejects_non_camera_sources(source):
    with pytest.raises(ValueError):
        camera_source(source)


def test_camera_sources_and_stale_frame():
    assert camera_source("webcam:0") == 0
    assert camera_source("rtsp://192.0.2.1/stream") == "rtsp://192.0.2.1/stream"
    assert camera_source("https://camera.example/feed") == "https://camera.example/feed"
    session = CameraMonitor()
    session.publish(status="Connected", frame="abc")
    assert session.snapshot()["frame"] == "abc"
    session.updated -= 10
    assert session.snapshot()["status"] == "Connecting"
    assert session.snapshot()["frame"] is None
    session.disconnect()
    assert session.snapshot()["status"] == "Disconnected"


def test_recorded_monitoring_is_archived_when_playback_finishes(tmp_path):
    history = VideoHistory(tmp_path / "jobs.sqlite")
    identifier = history.start("traffic.mp4", 10, "junction", pending_replay=True)
    history.finish(identifier, "a" * 64, None)
    assert history.recent() == []
    assert history.reveal_replay(identifier)
    assert history.recent()[0]["id"] == identifier
    assert not history.reveal_replay("unknown")
