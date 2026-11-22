"""Recording analysis for loopback and authenticated hosted dashboards."""

import json
import hashlib
import os
import re
import sqlite3
import tempfile
import threading
from contextvars import ContextVar
from functools import lru_cache, partial
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool
from server.camera_monitor import CameraMonitor, camera, camera_source

router = APIRouter(prefix="/workbench", include_in_schema=False)
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data/server/video_analysis"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
folder_open = threading.Lock()
store_lock = threading.Lock()
live_lock = threading.Lock()
offline_lock = threading.Lock()
account = ContextVar("analysis_account", default=None)
hosted_stores = {}
upload_slots = threading.BoundedSemaphore(2)
HOSTED_UPLOAD_MAX = 512 * 1024**2
HOSTED_ACCOUNT_MAX = 2 * 1024**3
VIDEO_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
               ".mkv": "video/x-matroska", ".avi": "video/x-msvideo", ".webm": "video/webm"}
FILENAME = re.compile(r'[^<>:"/\\|?*\x00-\x1f]{1,180}')


def hosted_origin():
    return os.environ.get("STMS_HOSTED_ORIGIN", "").rstrip("/")


def hosted_request(request: Request):
    origin = hosted_origin()
    host = request.headers.get("host", "")
    return (origin in {f"https://{host}", f"http://{host}"} and bool(host)
            and request.headers.get("sec-fetch-site") in {None, "same-origin", "none"}
            and (request.method != "POST" or request.headers.get("origin") == origin))


def allowed(request: Request) -> bool:
    return account.get() is not None if hosted_origin() else loopback_allowed(request)


def loopback_allowed(request: Request) -> bool:
    if os.environ.get("STMS_LOCAL_ANALYSIS") != "1" or not request.client:
        return False
    if request.client.host not in {"127.0.0.1", "::1"}:
        return False
    host = request.headers.get("host", "")
    try:
        if urlsplit("//" + host).hostname not in LOOPBACK:
            return False
    except ValueError:
        return False
    if request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
        return False
    if request.method == "POST":
        return request.headers.get("origin") == f"http://{host}"
    return True


@lru_cache(maxsize=1)
def build_store():
    return make_store(RESULTS, hosted=False)


def make_store(results, *, hosted):
    from edge.profile import load_profiles
    from scripts.workbench import Analyses, Cameras, Locator, run_tool, tool_inputs
    from scripts.video_history import VideoHistory

    cores = os.cpu_count() or 1
    threads = min(2, max(1, cores // 2))
    conserve = not hosted and os.environ.get("STMS_QUEUE_OFFLINE_DURING_LIVE", "1" if cores < 4 else "0") == "1"
    scratch = tempfile.TemporaryDirectory(prefix="stms-video-workers-") if conserve else None
    pause = Path(scratch.name) / "live-active" if scratch else None

    def release_live():
        if pause:
            pause.unlink(missing_ok=True)

    profiles, _ = load_profiles()
    offline = Analyses([], Cameras(profiles, results / "cameras"), results,
                       locator=None if hosted else Locator([ROOT / "data/dev_footage"], results / "folders.json"),
                       history=VideoHistory(results / "jobs.sqlite"), pause_file=pause,
                       runner=partial(run_tool, worker_threads=threads, background=True, pause_file=pause),
                       inputs=lambda: {**tool_inputs(), "device": "cpu"})
    demo = Analyses([], offline.cameras, results, history=offline.history, catalogue_from=offline,
                    runner=partial(run_tool, worker_threads=threads), on_release=release_live,
                    inputs=(lambda: {**tool_inputs(), "device": "cpu"}) if hosted else tool_inputs)
    demo.worker_threads = threads
    offline.history.migrate_reports(lambda key: read_cached_report(offline, key))
    return offline, demo, CameraMonitor() if hosted else camera, scratch


def read_cached_report(store, key):
    path = store.result_path(key)
    if path:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None


def workspace():
    with store_lock:
        owner = account.get()
        if owner is None:
            return build_store()
        if owner not in hosted_stores:
            hosted_stores[owner] = make_store(RESULTS / "accounts" / str(owner), hosted=True)
        return hosted_stores[owner]


def analyses(mode="offline"):
    return workspace()[1 if mode == "live" else 0]


def camera_monitor():
    return workspace()[2] if account.get() is not None else camera


def other_workspace_running(mode):
    owner = account.get()
    if owner is None:
        return False
    with store_lock:
        workspaces = [store for key, store in hosted_stores.items() if key != owner]
    return any((store[1].running() or store[2].running()) if mode == "live" else store[0].running()
               for store in workspaces)


def with_live_slot(start):
    with live_lock:
        offline, demo = analyses(), analyses("live")
        if demo.running() or camera_monitor().running():
            raise HTTPException(409, "Stop the current live source before starting another")
        if other_workspace_running("live"):
            raise HTTPException(409, "The server's Live slot is in use. Try again when it is available.")
        pause = offline.pause_file
        if pause:
            pause.touch()
        try:
            return start(demo)
        except BaseException:
            if pause:
                pause.unlink(missing_ok=True)
            raise


def readiness():
    from scripts.tracked_video import detector_settings, policy_settings

    problems = []
    model = None
    missing = [name for name in ("cv2", "torch", "ultralytics", "yaml", "lap", "scipy") if find_spec(name) is None]
    if missing:
        problems.append(f"Missing detector dependencies: {', '.join(missing)}.")
    if "yaml" not in missing:
        try:
            weights, _, _ = detector_settings()
            model = weights.name
            if not weights.is_file():
                problems.append(f"Missing detector weights: {model}.")
            policy_settings()
        except (OSError, TypeError, ValueError):
            problems.append("The detector or video policy configuration is invalid.")
    return model, " ".join(problems)


@router.get("/capabilities")
def capabilities(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    from scripts.workbench import MIN_S

    model, problem = readiness()
    return {"workbench": True, "replay": False, "analysis_ready": not problem,
            "analysis_problem": problem, "minimum_duration_s": MIN_S, "max_video_bytes": upload_limit(),
            "hosted": account.get() is not None,
            "server_camera": bool(os.environ.get("STMS_HOSTED_CAMERA_URL")) if account.get() is not None else None,
            "history": True, "monitoring": True, "uploads": True, "streaming_demo": True,
            "model": model, "tracker": "ByteTrack", "parallel_analysis": True, "manage_history": True}


def upload_limit():
    from scripts.workbench import MAX_VIDEO_BYTES
    return HOSTED_UPLOAD_MAX if account.get() is not None else MAX_VIDEO_BYTES


def upload_name(name):
    path = Path(name)
    if not FILENAME.fullmatch(name) or path.suffix.lower() not in VIDEO_TYPES or path.is_reserved():
        raise HTTPException(415, "Choose a valid MP4, MOV, AVI, MKV, M4V or WebM filename.")
    return name


@router.post("/upload")
async def upload(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    if request.headers.get("content-type") != "application/octet-stream":
        raise HTTPException(415, "Send the selected video file.")
    hosted = account.get() is not None
    if hosted and not upload_slots.acquire(blocking=False):
        raise HTTPException(429, "The server is receiving other recordings. Try again shortly.")
    try:
        return await store_upload(request, hosted)
    finally:
        if hosted:
            upload_slots.release()


async def store_upload(request, hosted):
    limit = upload_limit()
    name = upload_name(unquote(request.headers.get("x-stms-filename", "")))
    size_header = request.headers.get("content-length", "")
    if size_header and (not size_header.isascii() or not size_header.isdecimal()
                        or not 0 < int(size_header) <= limit):
        raise HTTPException(413, f"Choose a non-empty recording up to {limit // 1024**2} MiB.")
    # Stream directly to a private sibling of the result store. A per-upload cap
    # applies to the actual bytes even when the client omits Content-Length.
    def stage():
        root = analyses().results_dir / "uploads"
        root.mkdir(parents=True, exist_ok=True)
        return root, tempfile.NamedTemporaryFile(dir=root, prefix=".incoming-", delete=False)

    try:
        root, handle = await run_in_threadpool(stage)
    except OSError as error:
        raise HTTPException(507, "The analysis service could not open video storage. Check free disk space and folder permissions.") from error
    temp = Path(handle.name)
    digest = hashlib.sha256()
    size = 0
    try:
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, f"The recording exceeds {limit // 1024**2} MiB.")
            await run_in_threadpool(handle.write, chunk)
            digest.update(chunk)
        if not size or (size_header and size != int(size_header)):
            raise HTTPException(400, "The recording upload was empty or incomplete.")
        key = digest.hexdigest()

        def commit():
            handle.close()
            target = root / key / name
            with store_lock:
                if not target.exists():
                    if hosted and sum(path.stat().st_size for path in root.glob("*/*") if path.is_file()) + size > HOSTED_ACCOUNT_MAX:
                        raise HTTPException(413, "This account has reached its 2 GiB recording storage limit.")
                    target.parent.mkdir(exist_ok=True)
                    os.replace(temp, target)
            return analyses().add(target, upload_key=key)

        return {"recording": await run_in_threadpool(commit), "size": size}
    except OSError as error:
        raise HTTPException(507, "The analysis service could not save the video. Check free disk space.") from error
    finally:
        handle.close()
        temp.unlink(missing_ok=True)


@router.get("/video/{job_id}")
def saved_video(job_id: str, request: Request):
    if not allowed(request) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404)
    from scripts.workbench import KEY

    store = analyses()
    source = store.history.source(job_id)
    if not source or not KEY.fullmatch(source["upload_key"]):
        raise HTTPException(404, "This session has no saved video.")
    name = upload_name(source["filename"])
    path = store.results_dir / "uploads" / source["upload_key"] / name
    if not path.is_file() or path.stat().st_size != source["size"]:
        raise HTTPException(404, "The saved video is missing.")
    return FileResponse(path, media_type=VIDEO_TYPES[path.suffix.lower()],
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/cameras")
def cameras(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    return analyses().cameras.listing()


@router.get("/jobs/current")
def current_job(request: Request, mode: str = "offline"):
    if not allowed(request):
        raise HTTPException(404)
    if mode not in {"offline", "live"}:
        raise HTTPException(404)
    return analyses(mode).snapshot()


@router.get("/jobs/active")
def active_jobs(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    live = analyses("live").snapshot()
    monitor = camera_monitor()
    if monitor.running():
        state = monitor.snapshot()
        live = {"running": True, "recording": state.get("source") or "Camera",
                "status": state["status"], "progress": None}
    return {"offline": analyses().snapshot(), "live": live}


@router.get("/monitor/camera")
def camera_status(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    return camera_monitor().snapshot()


@router.get("/monitor/demo/{job_id}")
def demo_updates(job_id: str, request: Request, offset: int = 0):
    if not allowed(request) or not 0 <= offset <= 1_000_000:
        raise HTTPException(404)
    batch = analyses("live").monitor_batch(job_id, offset)
    if batch is None:
        raise HTTPException(404, "This monitoring session is unavailable.")
    return batch


@router.get("/jobs")
def jobs(request: Request):
    if not allowed(request):
        raise HTTPException(404)
    store = analyses()
    return [{**job, "alert_statuses": store.history.statuses(job["id"])} for job in store.history.recent()]


@router.get("/analysis/{key}")
def result(key: str, request: Request):
    if not allowed(request):
        raise HTTPException(404)
    store = analyses()
    report = store.history.report(key)
    headers = {"Cache-Control": "no-store"}
    if report is not None:
        return Response(report, media_type="application/json", headers=headers)
    path = store.result_path(key)
    if path is None:
        raise HTTPException(404, "No stored results for that key")
    return FileResponse(path, media_type="application/json", headers=headers)


def manage_offline(store, name, body):
    with offline_lock:
        if name == "history/delete":
            identifier = body.get("job_id")
            if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
                raise HTTPException(400, "Supply the offline analysis ID.")
            if store.running():
                raise HTTPException(409, "Wait for the offline analysis to finish before deleting a saved report.")
            if not store.history.delete_offline(identifier, store.remove_cached_report):
                raise HTTPException(404, "No saved offline analysis with that ID.")
            if store.snapshot()["job_id"] == identifier:
                store.clear_offline_workspace()
            return {"deleted": 1}
        if name == "history/reset" and body.get("confirm") is not True:
            raise HTTPException(400, "Confirm that all offline results should be deleted.")
        key = store.clear_offline_workspace()
        if name == "history/new":
            return {"ready": True}
        return {"deleted": store.history.delete_offline(None, store.remove_cached_report, extra_key=key)}


def action(name, body):
    store = analyses()
    if name in {"history/new", "history/reset", "history/delete"}:
        return manage_offline(store, name, body)
    if name == "rejected":
        filename, size, reason = (body.get(k) for k in ("filename", "size", "reason"))
        reasons = {"format": "Unsupported video file extension",
                   "size": f"The recording must be non-empty and at most {upload_limit() // 1024**2} MiB"}
        if (not isinstance(filename, str) or not 0 < len(filename) <= 255 or any(c in filename for c in ("/", "\\"))
                or type(size) is not int or not 0 <= size <= 2 ** 53 - 1
                or not isinstance(reason, str) or reason not in reasons):
            raise HTTPException(400, "Supply valid video metadata")
        with offline_lock:
            identifier = store.history.start(filename, size, "Unassigned")
            store.history.finish(identifier, None, reasons[reason])
        return {"job_id": identifier}
    if name == "locate":
        return store.locate(body.get("name"), body.get("size"), body.get("fingerprint"))
    if name == "folder":
        from scripts.workbench import choose_folder

        if not folder_open.acquire(blocking=False):
            raise HTTPException(409, "The folder picker is already open")
        try:
            folder = choose_folder()
            if folder:
                store.locator.remember(folder)
        finally:
            folder_open.release()
        return {"added": bool(folder)}
    if name == "cameras":
        recording = store._pick(body.get("recording"), store.recordings, "recording")
        profile = store.cameras.create(body.get("id"), body.get("lanes"), body.get("max_radius"), recording.name)
        return {"id": profile.camera_id}
    if name == "jobs/stop":
        identifier = body.get("job_id")
        if identifier is not None:
            if not isinstance(identifier, str):
                raise HTTPException(400, "Supply the session ID")
            return {"stopping": analyses("live").stop(wait_s=2, identifier=identifier)
                    or store.stop(identifier=identifier)}
        store.stop()
        return {"stopping": True}
    if name == "monitor/finish":
        identifier = body.get("job_id")
        if not isinstance(identifier, str) or not store.history.reveal_replay(identifier):
            raise HTTPException(404, "No completed monitoring session")
        return {"saved": True}
    if name == "monitor/disconnect":
        camera_monitor().disconnect()
        return {"disconnected": True}
    if name == "monitor/connect":
        try:
            source = body.get("source")
            if account.get() is not None:
                registered = os.environ.get("STMS_HOSTED_CAMERA_URL")
                if source != "registered-camera" or not registered:
                    raise HTTPException(400, "Select a camera configured on the STMS server.")
                source = registered
            source = camera_source(source)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        _, problem = readiness()
        if problem:
            raise HTTPException(503, problem)
        profile = store.cameras.get(body.get("camera"))
        def connect(demo):
            if not camera_monitor().connect(demo, profile, source):
                raise HTTPException(409, "Stop the current live source before connecting")
        with_live_slot(connect)
        return {"status": "Connecting"}
    if name == "alerts/status":
        identifier, event, status = (body.get(k) for k in ("job_id", "event_id", "status"))
        if status not in ("Active", "Acknowledged", "Resolved") or not isinstance(event, str):
            raise HTTPException(400, "Supply a known alert and status")
        job = next((job for job in store.history.recent() if job["id"] == identifier), None)
        if job is None:
            raise HTTPException(404, "No matching analysis job")
        if job["status"] == "Failed":
            known = event == "processing-error"
        else:
            report = store.history.report(job["result_key"])
            saved = json.loads(report) if report else read_cached_report(store, job["result_key"])
            events = (saved or {}).get("traffic", {}).get("alerts", [])
            known = any(item["id"] == event for item in events)
        if not known:
            raise HTTPException(404, "No matching alert")
        if not store.history.set_status(identifier, event, status):
            raise HTTPException(404, "No matching analysis job")
        return {"status": status}
    if account.get() is not None:
        _, problem = readiness()
        if problem:
            raise HTTPException(503, problem)
    if body.get("monitoring") is True:
        identifier = with_live_slot(lambda demo: demo.start(body.get("recording"), body.get("camera"),
                                                            pending_replay=True))
    else:
        with offline_lock:
            if other_workspace_running("offline"):
                raise HTTPException(409, "The server's analysis slot is in use. Try again when it is available.")
            identifier = store.start(body.get("recording"), body.get("camera"))
    return {"started": True, "job_id": identifier}


@router.post("/{name:path}")
async def run_action(name: str, request: Request):
    if name not in {"locate", "folder", "cameras", "jobs", "jobs/stop", "alerts/status", "rejected", "monitor/finish",
                    "monitor/connect", "monitor/disconnect", "history/new", "history/reset", "history/delete"} or not allowed(request):
        raise HTTPException(404)
    if account.get() is not None and name in {"locate", "folder"}:
        raise HTTPException(404)
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise HTTPException(415, "Send JSON")
    from scripts.workbench import Refused

    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 4096:
            raise HTTPException(413, "Request is too large")
        raw.extend(chunk)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise HTTPException(400, "Invalid JSON") from error
    if not isinstance(body, dict):
        raise HTTPException(400, "Send a JSON object")
    try:
        return await run_in_threadpool(action, name, body)
    except Refused as error:
        raise HTTPException(error.status, error.message) from error
    except (OSError, sqlite3.Error) as error:
        if not name.startswith("history/"):
            raise
        raise HTTPException(507, "Could not update analysis storage. Check disk space and folder permissions, then retry.") from error
