"""A page for choosing a clip and starting the demonstration from a browser (D29).

    python scripts/demo_launcher.py --mosquitto <mosquitto.exe> --clips-root <footage folder>

then open the address it prints. It runs `scripts/demo_live.py` on the chosen clip
and shows how far that has got, with a link to the dashboard.

**Why this is not a section of the dashboard.** The dashboard is read-only by
construction, its tests fail on any POST, and it says so on screen. The server
behind it holds no detector, no OpenCV and no footage, and the edge is not part of
its stack (ADR-003). So what starts a run lives here, in a separate process that
exists only for the demonstration, on the laptop that holds the footage. Nothing
in `server/` or `dashboard/` changes, and no route is added to either.

**What crosses the browser.** A clip's number from the list, and text about the
run. Never a path, and never a frame (NFR-13). There is no upload: a camera needs
lane geometry and calibrated thresholds, so an unknown video could not run anyway.

**It binds to 127.0.0.1 only**, and a request is refused unless its Host names this
address, its Origin, if any, is this page, and a POST is JSON. So another site open
in the same browser cannot start a run, directly or through DNS rebinding.

**Every run gets a new stack and a new database.** So the previous run's forecast
cannot appear under the new clip (the D27 gap needs a restart on one server).

**What it does not establish:** the same as `demo_live.py`. It is a replay, not S65,
and it forecasts traffic, not the signal.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.console import use_utf8  # noqa: E402
from scripts.demo_e2e import Stack  # noqa: E402
from scripts.demo_live import (DEFAULT_MINUTES, LIVE_ID, MILESTONES, MIN_MINUTES, REHEARSED,  # noqa: E402
                               available_clips, port_free, run_with_cleanup)

use_utf8()

__all__ = ["Launcher", "Refused", "make_handler", "main", "page", "status_text"]

THEME = ROOT / "dashboard" / "src" / "theme.css"
HOLD_S = 900.0      # how long the page stays up after the footage ends; Stop ends it sooner
MAX_BODY = 1024
DRAIN = 1024 * 1024  # the most read from a request that will be refused
# Measured on the RTX 4050 laptop: 12 to 57 s for the edge to report, later on a cold
# start. So ranges, and the page shows the real time once a step has happened.
EXPECTED = {MILESTONES[0]: "within 1 min", MILESTONES[1]: "1 to 2 min", MILESTONES[2]: "2 to 3 min",
            MILESTONES[3]: "2 to 3 min", MILESTONES[4]: "3 to 4 min"}


class Refused(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


class Launcher:
    """One run at a time. `runner(clip, report, stop)` does the work and returns
    its exit status; it is `run_clip` except in the tests."""

    def __init__(self, clips, runner, *, minutes: float, dashboard_url: str, ports=()) -> None:
        self.clips, self.runner, self.minutes = clips, runner, minutes
        self.dashboard_url, self.ports = dashboard_url, ports
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stopping = threading.Event()
        self.clip, self.code, self.started = None, None, 0.0
        self.notes: list[tuple[float, str]] = []

    def report(self, text: str) -> None:
        with self.lock:
            self.notes.append((time.monotonic() - self.started, text))

    def start(self, number) -> None:
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(self.clips):
            raise Refused(HTTPStatus.BAD_REQUEST, "that is not a clip on the list")
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise Refused(HTTPStatus.CONFLICT, "a run is in progress; stop it first")
            for port in self.ports:
                if not port_free(port):
                    raise Refused(HTTPStatus.CONFLICT, f"port {port} is already in use; stop what holds it")
            self.clip, self.code, self.notes = self.clips[number - 1], None, []
            self.started = time.monotonic()
            self.stopping = threading.Event()
            self.thread = threading.Thread(target=self._run, args=(self.clip, self.stopping), daemon=True)
            self.thread.start()

    def _run(self, clip, stopping) -> None:
        try:
            code = self.runner(clip, self.report, stopping)
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
            code, clip = self.code, self.clip
        reached = {text: at for at, text in notes if text in MILESTONES}
        ready = any(text.startswith("ready:") for _, text in notes)
        finished = any(text.startswith("replay finished") for _, text in notes)
        problem = next((text for _, text in reversed(notes) if text.startswith(("NOT READY", "FAILED"))), None)
        state = dict(running=running, code=code, ready=ready, finished=finished, problem=problem,
                     clip=clip.id if clip else None,
                     stopping=self.stopping.is_set() and running,
                     dashboard=self.dashboard_url if running and ready else None,
                     milestones=[{"name": m, "expected": EXPECTED[m], "at_s": round(reached[m]) if m in reached else None}
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
            return "Replay finished: the streams are going stale, as they should"
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

    def runner(clip, report, stopping) -> int:
        class Reporting(Stack):
            def mark(self, text: str) -> None:
                super().mark(text)
                report(text)

        def sleep(seconds: float) -> None:
            if stopping.wait(seconds):
                raise KeyboardInterrupt      # demo_live's own way out: it stops what it started

        run = SimpleNamespace(mosquitto=args.mosquitto, http_port=args.http_port, mqtt_port=args.mqtt_port,
                              minutes=args.minutes, hold=HOLD_S, chosen=clip, clip=clip.path, camera=clip.camera,
                              profile=clip.profile)
        return run_with_cleanup(run, stack_class=Reporting, sleep=sleep)

    return runner


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>STMS demo launcher</title>
<link rel="icon" href="data:,">
<style>
__THEME__
main { max-width: 720px; margin: 0 auto; padding: 16px; }
h1 { font-size: 22px; margin: 8px 0 4px; }
section { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; margin-top: 14px; }
p { margin: 6px 0; }
.note { color: var(--muted); font-size: 13px; }
label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
select { width: 100%; font: 14px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
.row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
button, a.open { font: 600 14px var(--sans); color: var(--ink); background: transparent; border: 1px solid var(--muted); border-radius: 8px; padding: 8px 14px; cursor: pointer; text-decoration: none; }
button.go, a.open { border-color: var(--brand); }
button:disabled { color: var(--muted); border-color: var(--line); cursor: default; }
#status { font-size: 17px; font-weight: 600; }
ul { list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 6px; }
li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; font-size: 14px; }
li span:last-child { font: 13px var(--mono); color: var(--muted); }
li[data-reached="true"] span:last-child { color: var(--ink); }
#problem { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--bad); font: 13px var(--mono); }
[hidden] { display: none !important; }
</style></head>
<body><main>
<h1>Try a clip</h1>
<p class="note">Runs one recorded clip through the deployed system: detector, both forecasters, MQTT, server and dashboard.</p>
<section aria-label="What this shows">
<p><b>Recorded footage, not a camera.</b> A real camera stream has not been qualified yet (S65).</p>
<p><b>It forecasts traffic, not the signal.</b> For each approach, the congestion class and the vehicle count of the next 60 s: the load a signal would have to handle. It sends no signal commands, and the signal heads read "not connected" (P97a).</p>
<p class="note">The dashboard's forecast check is agreement with the detector's own later counts, not accuracy.</p>
</section>
<section aria-label="Choose a clip">
<label for="clip">Clip (only cameras with lane geometry and calibrated thresholds can run)</label>
<select id="clip"></select>
<p class="note">Plays __MINUTES__ minutes of footage in real time. The first results take a few minutes because the forecasters need history; that cannot be skipped.</p>
<div class="row">
<button id="run" class="go" type="button">Run demonstration</button>
<button id="stop" type="button" disabled>Stop</button>
<a id="open" class="open" target="_blank" rel="noopener" hidden>Open the dashboard</a>
</div>
</section>
<section aria-label="Progress" aria-live="polite">
<p id="status">Ready to run</p>
<p class="note" id="which"></p>
<ul id="steps"></ul>
<p id="problem" hidden></p>
</section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const send = async (path, body) => {
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { const e = await r.json().catch(() => ({})); $("problem").hidden = false; $("problem").textContent = e.error || "refused"; }
};
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
function draw(s) {
  $("status").textContent = s.status;
  $("which").textContent = s.clip || "";
  $("run").disabled = s.running;
  $("clip").disabled = s.running;
  $("stop").disabled = !s.running || s.stopping;
  $("open").hidden = !s.dashboard;
  if (s.dashboard) $("open").href = s.dashboard;
  if (s.problem || s.running) { $("problem").hidden = !s.problem; $("problem").textContent = s.problem || ""; }
  $("steps").replaceChildren(...s.milestones.map((m) => {
    const li = document.createElement("li");
    li.dataset.reached = m.at_s !== null;
    const name = document.createElement("span"), when = document.createElement("span");
    name.textContent = m.name;
    when.textContent = m.at_s !== null ? `at ${clock(m.at_s)}` : m.expected;
    li.append(name, when);
    return li;
  }));
}
async function tick() {
  try { draw(await (await fetch("/state")).json()); }
  catch { $("status").textContent = "The launcher is not answering"; }
}
async function load() {
  const clips = await (await fetch("/clips")).json();
  $("clip").replaceChildren(...clips.map((c) => {
    const o = document.createElement("option");
    o.value = c.number;
    o.textContent = c.id + (c.rehearsed ? "  (rehearsed)" : "");
    return o;
  }));
}
$("run").onclick = async () => { $("problem").hidden = true; await send("/run", { clip: Number($("clip").value) }); tick(); };
$("stop").onclick = async () => { await send("/stop", {}); tick(); };
load(); tick(); setInterval(tick, 2000);
</script>
</body></html>
"""


def page(minutes: float, theme: Path = THEME) -> str:
    """One self-contained page, in the dashboard's measured palette (D18)."""
    return PAGE.replace("__THEME__", theme.read_text(encoding="utf-8")).replace("__MINUTES__", f"{minutes:g}")


def make_handler(launcher: Launcher, port_of, html: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "stms-demo"
        sys_version = ""

        def log_message(self, *_args) -> None:
            pass                         # a request line is sender-chosen text (P142)

        def reply(self, status, body: bytes, kind: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def answer(self, status, payload) -> None:
            self.reply(status, json.dumps(payload).encode("utf-8"))

        def local(self) -> bool:
            """Host must name this address, so DNS rebinding gets nowhere; and an
            Origin, when a browser sends one, must be this page."""
            port = port_of()
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{h}" for h in hosts})

        def do_GET(self) -> None:
            if not self.local():
                return self.answer(HTTPStatus.FORBIDDEN, {"error": "this page answers on its own address only"})
            if self.path == "/":
                return self.reply(HTTPStatus.OK, html.encode("utf-8"), "text/html; charset=utf-8")
            if self.path == "/clips":
                return self.answer(HTTPStatus.OK, launcher.listing())
            if self.path == "/state":
                return self.answer(HTTPStatus.OK, launcher.snapshot())
            return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})

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
            if self.path == "/stop":
                launcher.stop()
                return self.answer(HTTPStatus.OK, {"stopping": True})
            if self.path != "/run":
                return self.answer(HTTPStatus.NOT_FOUND, {"error": "no such page"})
            try:
                launcher.start(body.get("clip") if isinstance(body, dict) else None)
            except Refused as refused:
                return self.answer(refused.status, {"error": refused.message})
            return self.answer(HTTPStatus.ACCEPTED, {"started": True})

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mosquitto", type=Path, required=True, help="mosquitto executable; mosquitto_passwd beside it")
    ap.add_argument("--clips-root", type=Path, required=True, help="folder holding the clips; nothing is copied from it")
    ap.add_argument("--minutes", type=float, default=DEFAULT_MINUTES, help=f"footage to play, at least {MIN_MINUTES:g}")
    ap.add_argument("--port", type=int, default=18080, help="this page's port, on 127.0.0.1 only")
    ap.add_argument("--http-port", type=int, default=18000)
    ap.add_argument("--mqtt-port", type=int, default=18883)
    args = ap.parse_args(argv)
    if not args.mosquitto.is_file():
        ap.error(f"--mosquitto is not a file: {args.mosquitto}")
    if not args.clips_root.is_dir():
        ap.error(f"--clips-root is not a folder: {args.clips_root}")
    if args.minutes < MIN_MINUTES:
        ap.error(f"--minutes must be at least {MIN_MINUTES:g}: the first count comparison takes about 3 minutes")
    clips = available_clips(args.clips_root)
    if not clips:
        ap.error(f"no clip that can run under {args.clips_root}")
    launcher = Launcher(clips, run_clip(args), minutes=args.minutes, ports=(args.http_port, args.mqtt_port),
                        dashboard_url=f"http://127.0.0.1:{args.http_port}/dashboard/?id={LIVE_ID}")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(launcher, lambda: args.port, page(args.minutes)))
    except OSError as error:
        print(f"NOT READY: cannot listen on 127.0.0.1:{args.port} ({error})", file=sys.stderr, flush=True)
        return 1
    print(f"Open http://127.0.0.1:{args.port}/  (Ctrl+C here stops everything)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping", flush=True)
    finally:
        launcher.stop(wait_s=30)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
