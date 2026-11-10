"""The local workbench: the dashboard, with the actions only this computer can take (D29, D40, D41).

    python scripts/demo_launcher.py --mosquitto <mosquitto.exe> --clips-root <footage folder>

then open the address it prints. It serves the built dashboard as its only page,
so analysing a recording, replaying one through the system and watching the
result all happen in one interface.

**Why the actions live in this process and not in the server.** The server holds
no detector, no OpenCV and no footage, and the edge is not part of its stack
(ADR-003). The dashboard it serves stays read-only and its read client, `api.js`,
stays GET-only. What this process adds is reached only through the dashboard's
`workbench.js`, which exists only when the page is served from here (it asks
`/workbench/capabilities` first, and the server has no such route). Its POSTs can
start or stop an analysis or a replay, find a file, open a folder window, or save
a provisional camera. None of them reaches a signal.

**What crosses the browser.** A recording's number, a camera's id, a file's name,
size and fingerprint, lane positions, and text about the work. Never a path, and
never a frame (NFR-13): the video plays in the page from a file the viewer opened,
and this process never serves it. A folder is shown to it through this computer's
own folder window, and only the folder's name comes back.

**It binds to 127.0.0.1 only**, and a request is refused unless its Host names this
address, its Origin, if any, is this address, and a POST is JSON. So another site
open in the same browser cannot start anything, directly or through DNS rebinding.

**The live panels** read the server's read-only endpoints. While a replay runs they
are passed through to that replay's server unchanged; otherwise nothing is
published, `/evidence` comes from the server's own function over the same committed
files, and `/health` says no replay is running.

**Every replay gets a new stack and a new database.** So the previous run's forecast
cannot appear under the new clip (the D27 gap needs a restart on one server).

**What it does not establish:** a replay is not S65, an analysis is not accuracy,
and nothing here forecasts or drives the signal (P97a). An analysis and a replay
never run at once, because both need the GPU.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.console import use_utf8  # noqa: E402
from scripts.demo_e2e import CAMERA_SOURCE, Stack  # noqa: E402
from scripts.demo_live import (DEFAULT_MINUTES, LIVE_ID, MILESTONES, MIN_MINUTES, REHEARSED, Clip,  # noqa: E402
                               available_clips, port_free, run_with_cleanup)
from scripts.workbench import Analyses, Cameras, Locator, Refused, catalogue, choose_folder  # noqa: E402

use_utf8()

__all__ = ["Launcher", "Refused", "SERVER_GETS", "make_handler", "main", "static_file", "status_text"]

DIST = ROOT / "dashboard" / "dist"
RESULTS = ROOT / "data" / "_workbench"
CAMERA_ENV = "STMS_CAMERA_URL"   # as edge.run.CAMERA_ENV: read there, never here
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff2": "font/woff2",
                ".woff": "font/woff"}
HOLD_S = 900.0      # how long the page stays up after the footage ends; Stop ends it sooner
MAX_BODY = 1024
DRAIN = 1024 * 1024  # the most read from a request that will be refused
# Measured on the RTX 4050 laptop: 12 to 57 s for the edge to report, later on a cold
# start. So ranges, and the page shows the real time once a step has happened.
EXPECTED = {MILESTONES[0]: "within 1 min", MILESTONES[1]: "1 to 2 min", MILESTONES[2]: "2 to 3 min",
            MILESTONES[3]: "2 to 3 min", MILESTONES[4]: "3 to 4 min"}


CAMERA_MILESTONE = "the edge reports the live camera"
MAX_MINUTES = 180.0          # the longest replay offered: a replay plays in real time


class Launcher:
    """One run at a time: a listed clip, any recording the workbench found (D42),
    or the live camera (D42). `runner(clip, report, stop[, minutes=])` does the
    work and returns its exit status; it is `run_clip` except in the tests.

    **The camera address never passes through here.** It is `STMS_CAMERA_URL` in
    the environment this process was started with, which the edge inherits; this
    only knows whether it is set."""

    def __init__(self, clips, runner, *, minutes: float, dashboard_url: str, ports=(),
                 camera_configured: bool = False) -> None:
        self.clips, self.runner, self.minutes = clips, runner, minutes
        self.dashboard_url, self.ports, self.camera_configured = dashboard_url, ports, camera_configured
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stopping = threading.Event()
        self.clip, self.code, self.started = None, None, 0.0
        self.kind, self.run_minutes = "replay", minutes
        self.notes: list[tuple[float, str]] = []

    def report(self, text: str) -> None:
        with self.lock:
            self.notes.append((time.monotonic() - self.started, text))

    def start(self, number) -> None:
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(self.clips):
            raise Refused(HTTPStatus.BAD_REQUEST, "that is not a clip on the list")
        self._begin(self.clips[number - 1], "replay", None)

    def start_recording(self, clip: Clip, minutes) -> None:
        """Any recording and declared camera, for `minutes` of footage in real time."""
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not MIN_MINUTES <= minutes <= MAX_MINUTES:
            raise Refused(HTTPStatus.BAD_REQUEST, f"a replay plays {MIN_MINUTES:g} to {MAX_MINUTES:g} minutes of footage")
        self._begin(clip, "replay", float(minutes))

    def start_camera(self, camera_id: str, profile: Path) -> None:
        if not self.camera_configured:
            raise Refused(HTTPStatus.CONFLICT, "no camera is configured: set STMS_CAMERA_URL in the environment, "
                                               "then start the workbench again")
        self._begin(Clip(Path(CAMERA_SOURCE), camera_id, profile), "camera", None)

    def _begin(self, clip, kind: str, minutes) -> None:
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise Refused(HTTPStatus.CONFLICT, "a run is in progress; stop it first")
            for port in self.ports:
                if not port_free(port):
                    raise Refused(HTTPStatus.CONFLICT, f"port {port} is already in use; stop what holds it")
            self.clip, self.code, self.notes, self.kind = clip, None, [], kind
            self.run_minutes = minutes if minutes is not None else self.minutes
            self.started = time.monotonic()
            self.stopping = threading.Event()
            self.thread = threading.Thread(target=self._run, args=(clip, self.stopping, minutes), daemon=True)
            self.thread.start()

    def _run(self, clip, stopping, minutes=None) -> None:
        try:
            extra = {"minutes": minutes} if minutes is not None else {}
            code = self.runner(clip, self.report, stopping, **extra)
        except Exception as error:      # noqa: BLE001 - shown on the page, not lost in a thread
            self.report(f"FAILED: {type(error).__name__}: {error}")
            code = 1
        with self.lock:
            self.code = code

    def stop(self, wait_s: float | None = None) -> None:
        self.stopping.set()
        if wait_s is not None and self.thread is not None:
            self.thread.join(wait_s)

    def snapshot(self) -> dict:
        with self.lock:
            notes = list(self.notes)
            running = self.thread is not None and self.thread.is_alive()
            code, clip, kind, minutes = self.code, self.clip, self.kind, self.run_minutes
        reached = {text: at for at, text in notes if text in MILESTONES}
        ready = any(text.startswith("ready:") for _, text in notes)
        finished = any(text.startswith(("replay finished", "camera stream ended")) for _, text in notes)
        problem = next((text for _, text in reversed(notes) if text.startswith(("NOT READY", "FAILED"))), None)
        live = kind == "camera"
        state = dict(running=running, code=code, ready=ready, finished=finished, problem=problem, kind=kind,
                     clip=("live camera" if live else clip.id) if clip else None,
                     camera=clip.camera if clip else None, minutes=None if live else minutes,
                     camera_configured=self.camera_configured,
                     stopping=self.stopping.is_set() and running,
                     dashboard=self.dashboard_url if running and ready else None,
                     milestones=[{"name": CAMERA_MILESTONE if live and m == MILESTONES[0] else m,
                                  "expected": "within 1 min" if live and m == MILESTONES[0] else EXPECTED[m],
                                  "at_s": round(reached[m]) if m in reached else None}
                                 for m in MILESTONES])
        state["status"] = status_text(state)
        return state

    def listing(self) -> list[dict]:
        """Numbers and names only: a path never reaches the browser."""
        return [{"number": n, "id": c.id, "camera": c.camera, "rehearsed": c.id == REHEARSED}
                for n, c in enumerate(self.clips, 1)]


def status_text(s: dict) -> str:
    """What the page says, so nobody has to guess what the system is doing."""
    done = [m for m in s["milestones"] if m["at_s"] is not None]
    if s["problem"] and not s["running"]:
        return "Run failed: see the details below"
    if s["stopping"]:
        return "Stopping"
    if s["running"]:
        if s["finished"]:
            if s.get("kind") == "camera":
                return "The camera stream ended: the streams are going stale, as they should"
            return "Replay finished: the streams are going stale, as they should"
        if s.get("kind") == "camera" and s["ready"] and s["milestones"][0]["at_s"] is None:
            return "Connecting to the camera"
        if not s["ready"]:
            return "Starting the pipeline: proving the broker and ingest carry a real message"
        if len(done) < 2:
            return "Warming up: the forecasters are collecting history"
        return "Forecasts available"
    if s["code"] == 130:
        return "Stopped"
    if s["code"] == 0:
        return "Finished"
    if s["code"] is not None:
        return "Run failed: see the details below"
    return "Ready to run"


def run_clip(args):
    """The real runner: `demo_live`'s whole run, reporting here, stoppable from here."""

    def runner(clip, report, stopping, minutes: float | None = None) -> int:
        class Reporting(Stack):
            def mark(self, text: str) -> None:
                super().mark(text)
                report(text)

        def sleep(seconds: float) -> None:
            if stopping.wait(seconds):
                raise KeyboardInterrupt      # demo_live's own way out: it stops what it started

        source = CAMERA_SOURCE if str(clip.path) == CAMERA_SOURCE else clip.path
        run = SimpleNamespace(mosquitto=args.mosquitto, http_port=args.http_port, mqtt_port=args.mqtt_port,
                              minutes=minutes or args.minutes, hold=HOLD_S, chosen=clip, clip=source,
                              camera=clip.camera, profile=clip.profile)
        return run_with_cleanup(run, stack_class=Reporting, sleep=sleep)

    return runner


def static_file(dist: Path, url_path: str) -> tuple[bytes, str] | None:
    """A file of the built dashboard, or None. Only under `dist`, only known types."""
    rel = unquote(url_path[len("/dashboard/"):]) or "index.html"
    base = dist.resolve()
    target = (base / rel).resolve()
    if base not in target.parents or target.suffix not in STATIC_TYPES or not target.is_file():
        return None
    return target.read_bytes(), STATIC_TYPES[target.suffix]


#: The server's read-only endpoints, as the dashboard's api.js allows them. While a
#: replay runs, they are passed through to its server unchanged; nothing else is.
_ID = r"[A-Za-z0-9_-]{1,32}"
SERVER_GETS = tuple(re.compile(p) for p in (
    rf"^/count_forecast/{_ID}/(latest|history)$", rf"^/prediction/{_ID}/(latest|history)$",
    rf"^/vehicle_count/{_ID}/history\?window=(1h|6h|24h)$", rf"^/vehicle_count/{_ID}/latest$",
    rf"^/heartbeat/{_ID}/latest$", rf"^/forecast_check/{_ID}/recent$", r"^/sites$", r"^/evidence$",
    r"^/health$"))


def local_evidence() -> tuple[int, bytes]:
    """`/evidence` with no replay running: the server's own function over the same
    committed files, so the Results section reads exactly what the server would."""
    try:
        from server.app import evidence

        return HTTPStatus.OK, json.dumps(evidence()).encode("utf-8")
    except Exception as error:          # noqa: BLE001 - the page shows evidence as unavailable
        return HTTPStatus.SERVICE_UNAVAILABLE, json.dumps({"detail": f"evidence unavailable: {type(error).__name__}"}).encode()


def pass_through(port: int, path: str) -> tuple[int, bytes]:
    try:
        with urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as reply:
            return reply.status, reply.read()
    except HTTPError as error:
        return error.code, error.read()
    except (URLError, OSError):
        return HTTPStatus.BAD_GATEWAY, b'{"detail": "the replay\'s server is not answering"}'


def make_handler(launcher: Launcher, port_of, analyses: Analyses | None = None, dist: Path = DIST,
                 upstream=lambda: None, folder_dialog=choose_folder):
    """`upstream()` is the replay server's port while one is ready, else None.
    `folder_dialog()` opens this computer's folder dialog; a fake in the tests."""
    dialog_open = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "stms-workbench"
        sys_version = ""

        def log_message(self, *_args) -> None:
            pass                         # a request line is sender-chosen text (P142)

        def reply(self, status, body: bytes, kind: str = "application/json", extra=()) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            for name, value in extra:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def answer(self, status, payload) -> None:
            self.reply(status, json.dumps(payload).encode("utf-8"))

        def local(self) -> bool:
            """Host must name this address, so DNS rebinding gets nowhere; and an
            Origin, when a browser sends one, must be this address."""
            port = port_of()
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{h}" for h in hosts})

        # ------------------------------------------------------------ reads ---
        def do_GET(self) -> None:
            if not self.local():
                return self.answer(HTTPStatus.FORBIDDEN, {"error": "this page answers on its own address only"})
            path = urlsplit(self.path).path
            if path == "/":
                return self.reply(HTTPStatus.FOUND, b"", "text/plain",
                                  (("Location", f"/dashboard/?id={LIVE_ID}#analyze"),))
            if path in ("/clips", "/workbench/replay/clips"):
                return self.answer(HTTPStatus.OK, launcher.listing())
            if path in ("/state", "/workbench/replay/state"):
                return self.answer(HTTPStatus.OK, launcher.snapshot())
            if path == "/dashboard":
                return self.reply(HTTPStatus.MOVED_PERMANENTLY, b"", "text/plain", (("Location", "/dashboard/"),))
            if path.startswith("/dashboard/"):
                if not (dist / "index.html").is_file():
                    return self.reply(HTTPStatus.SERVICE_UNAVAILABLE,
                                      b"The dashboard is not built here. Run: cd dashboard && npm run build",
                                      "text/plain; charset=utf-8")
                found = static_file(dist, path)
                if found is None:
                    return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such file"})
                return self.reply(HTTPStatus.OK, *found)
            if analyses is not None and path.startswith("/workbench/"):
                return self.workbench_get(path)
            if any(p.match(self.path) for p in SERVER_GETS):
                return self.server_get()
            return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})

        def workbench_get(self, path: str) -> None:
            if path == "/workbench/capabilities":
                return self.answer(HTTPStatus.OK, {"workbench": True, "replay": True, "live_id": LIVE_ID,
                                                   "camera_configured": launcher.camera_configured})
            if path == "/workbench/cameras":
                return self.answer(HTTPStatus.OK, analyses.cameras.listing())
            if path == "/workbench/recordings":
                return self.answer(HTTPStatus.OK, analyses.listing())
            if path == "/workbench/jobs/current":
                return self.answer(HTTPStatus.OK, analyses.snapshot())
            if path.startswith("/workbench/analysis/"):
                found = analyses.result_path(path.rsplit("/", 1)[1])
                if found is None:
                    return self.answer(HTTPStatus.NOT_FOUND, {"error": "no stored results for that key"})
                return self.reply(HTTPStatus.OK, found.read_bytes())
            return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})

        def server_get(self) -> None:
            """The live panels: from the replay's server while one runs. Otherwise
            nothing is published, which is what 404 means to the dashboard."""
            port = upstream()
            if port is not None:
                status, body = pass_through(port, self.path)
                return self.reply(status, body)
            if self.path == "/evidence":
                return self.reply(*local_evidence())
            if self.path == "/health":
                return self.answer(HTTPStatus.OK, {"status": "ok", "server": "local workbench, no replay running"})
            return self.answer(HTTPStatus.NOT_FOUND, {"detail": "nothing is being replayed"})

        # ----------------------------------------------------------- actions ---
        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            # Read before any refusal: closing with unread data resets the connection,
            # and on Windows the client then sees an abort instead of the reason.
            raw = self.rfile.read(min(max(length, 0), DRAIN))
            if not self.local():
                return self.answer(HTTPStatus.FORBIDDEN, {"error": "this page answers on its own address only"})
            # A cross-site form cannot send this type without asking first.
            if self.headers.get("Content-Type") != "application/json":
                return self.answer(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send JSON"})
            if not 0 <= length <= MAX_BODY:
                return self.answer(HTTPStatus.BAD_REQUEST, {"error": "bad length"})
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                return self.answer(HTTPStatus.BAD_REQUEST, {"error": "not JSON"})
            body = body if isinstance(body, dict) else {}
            try:
                return self.action(urlsplit(self.path).path, body)
            except Refused as refused:
                return self.answer(refused.status, {"error": refused.message})

        def action(self, path: str, body: dict) -> None:
            if path in ("/stop", "/workbench/replay/stop"):
                launcher.stop()
                return self.answer(HTTPStatus.OK, {"stopping": True})
            if path in ("/run", "/workbench/replay/start", "/workbench/camera/start"):
                if analyses is not None and analyses.running():
                    raise Refused(HTTPStatus.CONFLICT, "an analysis is running; both need the GPU, so stop it first")
                if path == "/workbench/camera/start":
                    if analyses is None:
                        return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})
                    profile = analyses.cameras.get(body.get("camera"))
                    launcher.start_camera(profile.camera_id, profile.path)
                elif analyses is not None and "recording" in body:
                    recording = Analyses._pick(body.get("recording"), analyses.recordings, "recording")
                    camera = body.get("camera")
                    profile = analyses.cameras.get(camera if isinstance(camera, str) else None)
                    if analyses.cameras.needs_levels(profile):
                        raise Refused(HTTPStatus.CONFLICT, "this camera's levels are not set yet: analyse one of "
                                                           "its recordings first")
                    minutes = body.get("minutes")
                    if minutes == "whole":
                        from scripts.workbench import duration_of

                        length = duration_of(recording.path)
                        minutes = round(length / 60.0, 2) if length else None
                    launcher.start_recording(Clip(recording.path, profile.camera_id, profile.path), minutes)
                else:
                    launcher.start(body.get("clip"))
                return self.answer(HTTPStatus.ACCEPTED, {"started": True})
            if analyses is None:
                return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})
            if path == "/workbench/jobs":
                if launcher.thread is not None and launcher.thread.is_alive():
                    raise Refused(HTTPStatus.CONFLICT, "a replay is running; both need the GPU, so stop it first")
                analyses.start(body.get("recording"), body.get("camera"))
                return self.answer(HTTPStatus.ACCEPTED, {"started": True})
            if path == "/workbench/jobs/stop":
                analyses.stop()
                return self.answer(HTTPStatus.OK, {"stopping": True})
            if path == "/workbench/locate":
                return self.answer(HTTPStatus.OK, analyses.locate(body.get("name"), body.get("size"),
                                                                  body.get("fingerprint")))
            if path == "/workbench/folder":
                if not dialog_open.acquire(blocking=False):
                    raise Refused(HTTPStatus.CONFLICT, "the folder window is already open on this computer")
                try:
                    folder = folder_dialog()
                finally:
                    dialog_open.release()
                if folder is None:
                    return self.answer(HTTPStatus.OK, {"added": None})
                analyses.locator.remember(folder)
                return self.answer(HTTPStatus.OK, {"added": folder.name or str(folder.anchor)})
            if path == "/workbench/cameras":
                recording = Analyses._pick(body.get("recording"), analyses.recordings, "recording")
                profile = analyses.cameras.create(body.get("id"), body.get("lanes"), body.get("max_radius"),
                                                  recording.name)
                return self.answer(HTTPStatus.CREATED, {"id": profile.camera_id})
            return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mosquitto", type=Path, required=True, help="mosquitto executable; mosquitto_passwd beside it")
    ap.add_argument("--clips-root", type=Path, required=True, help="folder holding the clips; nothing is copied from it")
    ap.add_argument("--videos-root", type=Path, action="append", default=None,
                    help="a folder to look in for recordings first; repeatable (default: --clips-root). "
                         "Any other folder can be shown to the workbench from the page")
    ap.add_argument("--results-dir", type=Path, default=RESULTS,
                    help="where finished analyses and this computer's provisional cameras are kept "
                         "(default: data/_workbench, not committed)")
    ap.add_argument("--minutes", type=float, default=DEFAULT_MINUTES, help=f"footage to play, at least {MIN_MINUTES:g}")
    ap.add_argument("--port", type=int, default=18080, help="this page's port, on 127.0.0.1 only")
    ap.add_argument("--http-port", type=int, default=18000)
    ap.add_argument("--mqtt-port", type=int, default=18883)
    args = ap.parse_args(argv)
    if not args.mosquitto.is_file():
        ap.error(f"--mosquitto is not a file: {args.mosquitto}")
    if not args.clips_root.is_dir():
        ap.error(f"--clips-root is not a folder: {args.clips_root}")
    roots = args.videos_root or [args.clips_root]
    for root in roots:
        if not root.is_dir():
            ap.error(f"--videos-root is not a folder: {root}")
    if args.minutes < MIN_MINUTES:
        ap.error(f"--minutes must be at least {MIN_MINUTES:g}: the first count comparison takes about 3 minutes")
    clips = available_clips(args.clips_root)
    if not clips:
        ap.error(f"no clip that can run under {args.clips_root}")
    launcher = Launcher(clips, run_clip(args), minutes=args.minutes, ports=(args.http_port, args.mqtt_port),
                        dashboard_url=f"http://127.0.0.1:{args.port}/dashboard/?id={LIVE_ID}",
                        camera_configured=bool(os.environ.get(CAMERA_ENV, "").strip()))
    from edge.profile import load_profiles

    profiles, unusable = load_profiles()
    for path, reason in unusable:
        print(f"note: camera profile {path.name} is not offered: {reason}", flush=True)
    analyses = Analyses(catalogue(roots), Cameras(profiles, args.results_dir / "cameras"), args.results_dir,
                        locator=Locator(roots, args.results_dir / "folders.json"))
    analyses.replay = {clip.path.resolve(): number for number, clip in enumerate(clips, 1)}
    if not (DIST / "index.html").is_file():
        print("NOT READY: dashboard/dist is not built, and the dashboard is this tool's only page. "
              "Run: cd dashboard && npm run build", file=sys.stderr, flush=True)
        return 1

    def upstream() -> int | None:
        state = launcher.snapshot()
        return args.http_port if state["running"] and state["ready"] else None

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                     make_handler(launcher, lambda: args.port, analyses, DIST, upstream))
    except OSError as error:
        print(f"NOT READY: cannot listen on 127.0.0.1:{args.port} ({error})", file=sys.stderr, flush=True)
        return 1
    print(f"Open http://127.0.0.1:{args.port}/  ({len(analyses.recordings)} recordings known, "
          f"{len(profiles)} committed cameras; Ctrl+C here stops everything)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping", flush=True)
    finally:
        launcher.stop(wait_s=30)
        analyses.stop(wait_s=30)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
