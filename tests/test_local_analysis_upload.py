from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.video_history import VideoHistory
from server import local_analysis


def test_upload_and_saved_video_require_loopback_and_completed_session(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(local_analysis.router)
    history = VideoHistory(tmp_path / "jobs.sqlite")
    recorded = []

    def add(path, *, upload_key):
        recorded.append((path, upload_key))
        return 1

    store = SimpleNamespace(results_dir=tmp_path, add=add, history=history)
    monkeypatch.setattr(local_analysis, "analyses", lambda: store)
    monkeypatch.setenv("STMS_LOCAL_ANALYSIS", "1")
    origin = "http://127.0.0.1:8083"
    with TestClient(app, base_url=origin, client=("192.0.2.5", 50101)) as remote:
        assert remote.get("/workbench/capabilities").status_code == 404
        assert remote.post("/workbench/upload", headers={"Origin": origin}).status_code == 404
    with TestClient(app, base_url=origin, client=("127.0.0.1", 50101)) as client:
        headers = {"Content-Type": "application/octet-stream", "X-STMS-Filename": "camera.webm"}
        assert client.post("/workbench/upload", headers=headers, content=b"test video").status_code == 404
        headers["Origin"] = origin
        invalid = {**headers, "X-STMS-Filename": "..%2Fcamera.webm"}
        assert client.post("/workbench/upload", headers=invalid, content=b"test video").status_code == 415
        response = client.post("/workbench/upload", headers=headers, content=b"test video")
        assert response.json() == {"recording": 1, "size": 10}
        path, key = recorded[0]
        assert path.read_bytes() == b"test video" and path.is_relative_to(tmp_path / "uploads")
        job = history.start(path.name, 10, "whole-frame", pending_replay=True, upload_key=key)
        history.finish(job, "a" * 64, None)
        url = f"/workbench/video/{job}"
        assert client.get(url).status_code == 404
        assert history.reveal_replay(job)
        replay = client.get(url, headers={"Range": "bytes=0-3"})
        assert replay.status_code == 206 and replay.content == b"test"
        assert replay.headers["Content-Type"] == "video/webm"
        assert history.recent()[0]["has_video"] == 1
