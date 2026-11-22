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



def test_hosted_uploads_require_auth_and_belong_to_their_account(monkeypatch, tmp_path):
    from server import app as server

    origin = "https://stms.example"
    monkeypatch.setenv("STMS_HOSTED_ORIGIN", origin)
    monkeypatch.setenv("STMS_AUTH_DB", str(tmp_path / "accounts.sqlite"))
    monkeypatch.setattr(local_analysis, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(local_analysis, "hosted_stores", {})
    monkeypatch.setattr(local_analysis, "readiness", lambda: ("test.pt", ""))
    headers = {"Origin": origin, "Content-Type": "application/octet-stream",
               "X-STMS-Filename": "traffic.mp4"}

    def sign_in(client, who):
        auth_headers = {"Origin": origin}
        password = "Signal-Green-43!"
        assert client.post("/auth/register", headers=auth_headers, json={
            "username": who, "full_name": who, "email": who + "@example.test", "password": password,
            "confirm_password": password, "accept_terms": True,
        }).is_success
        assert client.post("/auth/login", headers=auth_headers, json={
            "identifier": who, "password": password,
        }).is_success

    with TestClient(server.app, base_url=origin, client=("192.0.2.8", 5080)) as first, \
         TestClient(server.app, base_url=origin, client=("192.0.2.9", 5081)) as second:
        assert first.get("/workbench/capabilities").status_code == 401
        assert first.post("/workbench/upload", headers=headers, content=b"video").status_code == 401
        sign_in(first, "firstdriver")
        sign_in(second, "seconddriver")
        assert first.get("/workbench/capabilities").json()["hosted"]
        assert first.post("/workbench/upload", headers={**headers, "Origin": "https://elsewhere.example"},
                          content=b"video").status_code == 403
        assert first.post("/workbench/folder", headers={"Origin": origin}, json={}).status_code == 404
        assert first.post("/workbench/monitor/connect", headers={"Origin": origin},
                          json={"source": "rtsp://camera.example/stream"}).status_code == 400
        upload = first.post("/workbench/upload", headers=headers, content=b"video")
        assert upload.json() == {"recording": 1, "size": 5}
        owner = first.get("/auth/me").json()["user"]["id"]
        store = local_analysis.hosted_stores[owner][0]
        key = store.recordings[0].upload_key
        job = store.history.start("traffic.mp4", 5, "whole-frame", upload_key=key)
        result_key = "c" * 64
        store.history.finish(job, result_key, None, {"clip": "traffic"})
        assert first.get(f"/workbench/video/{job}").content == b"video"
        assert first.get(f"/workbench/analysis/{result_key}").json() == {"clip": "traffic"}
        assert second.get("/workbench/jobs").json() == []
        assert second.get(f"/workbench/video/{job}").status_code == 404
        assert second.get(f"/workbench/analysis/{result_key}").status_code == 404
        assert second.post("/workbench/jobs", headers={"Origin": origin},
                           json={"recording": 1, "camera": "whole-frame"}).status_code == 400
