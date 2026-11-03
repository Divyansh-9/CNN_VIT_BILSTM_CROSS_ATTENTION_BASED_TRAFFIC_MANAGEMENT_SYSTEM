"""UI fixtures: the real server holding one chosen state, for testing the dashboard (D36).

    python scripts/ui_fixture.py --list                   # every state, and the usability test's four
    python scripts/ui_fixture.py --state missing_count    # page and API on 127.0.0.1; type a state to switch
    python scripts/ui_fixture.py --write-fixtures         # rewrite dashboard/src/fixtures/ from the real server
    python scripts/ui_fixture.py --clean                  # remove folders left by runs that were killed

**A test tool, never evidence.** Every value in a state is made up to exercise the page: the
counts, classes, forecasts and checks describe no road and no camera. The model ids are
`persistence@000000000000` and `ridge@000000000000`, which name no real model, and every
heartbeat says replay with the label `TEST_FIXTURE_<state>`, so the page shows REPLAY and never
LIVE CAMERA. Nothing produced here may be quoted as a result.

**The real server, not a mock.** A state is loaded through the server's own `store_*` functions
with payloads built by `contracts/mqtt.py`, and every response is `server/app.py` answering from
a temporary SQLite file.

**Two processes, so the page outlives the API.** A page host on `--port` serves the built
dashboard and forwards GET requests to the API process on `--api-port`. `server_down` stops only
the API process. The page host then closes each forwarded connection without an answer, so the
browser sees the network failure a dead server causes, and the page stays open. An HTTP error
from a running API is passed through unchanged, so the two cases stay distinct.

**Contained.** Both ports must be free. The database lives in a new folder under the system temp
directory, and the API process refuses any other path, so the deployment database
(`data/server/stms.sqlite`) is never opened. No broker, edge or camera is started, and nothing
listens beyond 127.0.0.1. The API process runs without a write token, so it refuses every POST.
On `quit`, Ctrl+C or an error, the API process is stopped by the handle this run holds, and only
then is the folder deleted. A run killed outright leaves its folder behind: the next run names
it, and `--clean` removes it once its owner is no longer running.

**Fixtures for the contract check.** `--write-fixtures` generates each state in-process with the
server's clock fixed, so every response is exact and repeatable, and writes
`dashboard/src/fixtures/<state>.json`. `tests/test_ui_fixture.py` regenerates them from the
server and fails on any difference, and `dashboard/src/fixtures.test.js` checks the same files
with the page's own validators. `/evidence` is left out: it reads committed result files and git
history, not the database, so it is the same in every state.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.client
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.mqtt import (CongestionClass, CongestionPrediction, CountForecast,  # noqa: E402
                            ForecastCheck, Heartbeat, Mode, VehicleCount)
from scripts.console import use_utf8  # noqa: E402

FIXTURE_ID = "test-fixture"
SESSION = "000000000001"
CLASS_MODEL = "persistence@000000000000"
COUNT_MODEL = "ridge@000000000000"
LANES = {"lane_0": "N", "lane_1": "S", "lane_2": "E", "lane_3": "W"}
FIXTURES = ROOT / "dashboard" / "src" / "fixtures"
DIST = ROOT / "dashboard" / "dist"
DEPLOYED_DATABASE = ROOT / "data" / "server" / "stms.sqlite"
TEMP_PREFIX = "stms-ui-fixture-"
#: Fixture generation uses its own prefix, so --clean can never mistake one for a run.
GENERATE_PREFIX = "stms-fixture-generate-"
OWNER_FILE = "owner.json"
#: The server's clock while fixtures are generated: 2026-01-01 00:00:00 UTC.
CLOCK = 1_767_225_600.0
#: Where in its imaginary clip the fixture replay says it is.
POSITION_S = 600.0
#: How often a fed state is sent again, as the edge sends every 2 s step.
FEED_EVERY_S = 2.0
FPS = 0.5
API_READY_S = 30.0
#: The four states of docs/demo/USABILITY-TEST-5-PERSON.md, in its order.
USABILITY = ("missing_count", "normal", "stale_edge", "server_down")
#: Paths the page host forwards to the API: the dashboard's read-only endpoints.
API_PREFIXES = ("/health", "/sites", "/evidence", "/heartbeat/", "/prediction/", "/count_forecast/",
                "/vehicle_count/", "/forecast_check/")
CONFIDENCE = {"LOW": 0.82, "MEDIUM": 0.55, "HIGH": 0.61}
OTHER_CLASS = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "MEDIUM"}
#: Forecast-check pattern: which minute disagrees, and by how much the count was off.
CHECK_MISSES = {1: "E", 3: "N"}
CHECK_OFFSETS = (0.4, -0.3, 0.1, 0.6, -0.2)
#: How the history's counts vary, so a chart of them is not a flat line.
HISTORY_DELTA = (0, 1, 2, 1, 0, -1)


@dataclass(frozen=True)
class State:
    purpose: str
    #: What the page's status banner says for this state: documentation, and checked by the tests.
    banner: str
    heartbeat: bool = True
    classes: dict | None = None        # approach -> congestion class
    counts: dict | None = None         # approach -> forecast mean count
    lanes: dict | None = None          # lane -> {vehicle class: count}, the latest observed counts
    recent_min: int = 0                # minutes of observed counts before the latest, one per minute
    day_h: int = 0                     # hours of observed counts before those, one per hour
    checks: int = 0                    # forecast checks, a minute apart
    ago_s: float = 1.0                 # how long before now the latest messages arrived
    fed: bool = True                   # whether the runner keeps sending them, as a running edge does
    api: bool = True                   # False: no API process at all (server_down)


NORMAL_CLASSES = {"N": "MEDIUM", "S": "LOW", "E": "HIGH", "W": "LOW"}
NORMAL_COUNTS = {"N": 3.2, "S": 1.1, "E": 6.4, "W": 0.8}
NORMAL_LANES = {"lane_0": {"car": 3}, "lane_1": {"car": 1},
                "lane_2": {"car": 4, "bus": 1, "auto-rickshaw": 1}, "lane_3": {"motorcycle": 1}}
NORMAL = dict(classes=NORMAL_CLASSES, counts=NORMAL_COUNTS, lanes=NORMAL_LANES,
              recent_min=15, day_h=24, checks=5)
UP = "Updates are arriving from a recording"

STATES: dict[str, State] = {
    "missing_count": State("The first minutes of a run: the level forecast has started, the vehicle "
                           "number has not.", "Only the congestion level forecast is arriving",
                           classes=NORMAL_CLASSES, lanes=NORMAL_LANES, recent_min=2),
    "normal": State("Everything arriving: both forecasts, counts on four lanes, history and checks.",
                    UP, **NORMAL),
    "stale_edge": State("The edge stopped over 60 s ago. Nothing new arrives; the forecasts describe a "
                        "minute that has passed.", "No recent updates", **NORMAL, ago_s=90.0, fed=False),
    "server_down": State("The API process is stopped. The page stays open and every request fails as "
                         "unreachable.", "Cannot reach the server", heartbeat=False, fed=False, api=False),
    "partial": State("Arriving, with approaches missing: no level for E and W, no number for W, and "
                     "lane_3 has never reported.", f"{UP}, with approaches E, W missing",
                     classes={"N": "MEDIUM", "S": "LOW"}, counts={"N": 3.2, "S": 1.1, "E": 6.4},
                     lanes={k: v for k, v in NORMAL_LANES.items() if k != "lane_3"}, recent_min=15),
    "no_data": State("The server is reachable and nothing has been published for this intersection.",
                     "No forecast yet", heartbeat=False, fed=False),
    "high": State("Busy on every approach, with counts above the drawing's scale break of 10.", UP,
                  classes={a: "HIGH" for a in "NSEW"}, counts={"N": 12.5, "S": 9.8, "E": 16.2, "W": 11.0},
                  lanes={"lane_0": {"car": 10, "motorcycle": 2, "bus": 1}, "lane_1": {"car": 8, "truck": 1, "motorcycle": 1},
                         "lane_2": {"car": 12, "bus": 2, "auto-rickshaw": 2}, "lane_3": {"car": 9, "motorcycle": 2}},
                  recent_min=15, day_h=24, checks=5),
    "low": State("Quiet on every approach, with a forecast of zero vehicles for W.", UP,
                 classes={a: "LOW" for a in "NSEW"}, counts={"N": 0.4, "S": 0.2, "E": 0.6, "W": 0.0},
                 lanes={"lane_0": {"car": 1}, "lane_1": {}, "lane_2": {"car": 1}, "lane_3": {}},
                 recent_min=15, day_h=24, checks=5),
    "edge_silent": State("The edge stopped 30 s ago: its last forecasts are still inside their 60 s. In the "
                         "runner it becomes No recent updates 30 s later, as a real stop does.",
                         "The edge unit has stopped reporting", **NORMAL, ago_s=30.0, fed=False),
}


# --- loading a state into the real server -------------------------------------------------

class Clock:
    """Stands in for the `time` module inside `server.app` while a state is loaded or, for the
    fixtures, served: `time()` answers `t`. Every other attribute is the real module's."""

    def __init__(self, t: float):
        self.t = t

    def time(self) -> float:
        return self.t

    def __getattr__(self, name):
        return getattr(time, name)


@contextlib.contextmanager
def server_clock(clock: Clock):
    """Point `server.app`'s clock at `clock`, and always put the real one back."""
    import server.app as server

    real = server.time
    server.time = clock
    try:
        yield server
    finally:
        server.time = real


def _heartbeat(name: str, ts: float) -> Heartbeat:
    source = {"kind": "replay", "session": SESSION, "label": f"TEST_FIXTURE_{name}",
              "position_s": POSITION_S, "duration_s": None}
    return Heartbeat("online", Mode.NORMAL, False, False, ts=ts, source=source, lanes=dict(LANES),
                     directions_verified=False)


def _prediction(state: State, ts: float) -> CongestionPrediction:
    return CongestionPrediction(predictions={a: CongestionClass(c) for a, c in state.classes.items()},
                                confidences={a: CONFIDENCE[c] for a, c in state.classes.items()},
                                gate_value=None, model=CLASS_MODEL, ts=ts)


def _check(state: State, i: int, ts: float) -> ForecastCheck:
    """The i-th of `state.checks` checks, a minute apart on the replay's own clock, the newest
    checked at POSITION_S. Some minutes disagree, so the ribbon is not a row of identical cells."""
    made = POSITION_S - 60.0 * (state.checks - i)
    classes = {a: {"forecast": c, "observed": OTHER_CLASS[c] if CHECK_MISSES.get(i) == a else c}
               for a, c in (state.classes or {}).items()}
    counts = {a: {"forecast": v, "observed": round(max(v + CHECK_OFFSETS[i % len(CHECK_OFFSETS)], 0.0), 1)}
              for a, v in (state.counts or {}).items()}
    return ForecastCheck(session=SESSION, made_ts=made, checked_ts=made + 60.0, classes=classes, counts=counts,
                         class_model=CLASS_MODEL if classes else None,
                         count_model=COUNT_MODEL if counts else None, ts=ts)


def _history_types(types: dict, k: int) -> dict:
    """A history sample: the lane's latest total, varied by `k`, all counted as cars."""
    n = max(sum(types.values()) + HISTORY_DELTA[k % len(HISTORY_DELTA)], 0)
    return {"car": n} if n else {}


def send_latest(server, name: str, state: State, ts: float) -> None:
    """What the edge sends every step: counts per lane, the forecasts, the newest check and the
    heartbeat. Stored through the server's own entry points, so each is validated as real input."""
    for lane, types in (state.lanes or {}).items():
        server.store_vehicle_count(FIXTURE_ID, lane, VehicleCount(sum(types.values()), dict(types), FPS, ts).encode())
    if state.classes:
        server.store_prediction(FIXTURE_ID, _prediction(state, ts).encode())
    if state.counts:
        server.store_count_forecast(FIXTURE_ID, CountForecast(dict(state.counts), COUNT_MODEL, ts=ts).encode())
    if state.checks:
        server.store_forecast_check(FIXTURE_ID, _check(state, state.checks - 1, ts).encode())
    if state.heartbeat:
        server.store_heartbeat(FIXTURE_ID, _heartbeat(name, ts).encode())


def load(name: str, clock: Clock, now: float) -> None:
    """Store `name`'s state as if it had arrived over time, ending `ago_s` before `now`. Must run
    inside `server_clock(clock)`: each store is dated by moving the clock."""
    import server.app as server

    state = STATES[name]
    latest = now - state.ago_s
    for lane, types in (state.lanes or {}).items():
        for h in range(state.day_h, 0, -1):
            clock.t = latest - state.recent_min * 60 - h * 3600
            server.store_vehicle_count(FIXTURE_ID, lane, VehicleCount(
                sum(_history_types(types, h).values()), _history_types(types, h), FPS, clock.t).encode())
        for m in range(state.recent_min, 0, -1):
            clock.t = latest - m * 60
            server.store_vehicle_count(FIXTURE_ID, lane, VehicleCount(
                sum(_history_types(types, m).values()), _history_types(types, m), FPS, clock.t).encode())
    for i in range(state.checks - 1):
        clock.t = latest - 60.0 * (state.checks - 1 - i)
        server.store_forecast_check(FIXTURE_ID, _check(state, i, clock.t).encode())
    clock.t = latest
    send_latest(server, name, state, latest)
    clock.t = now


# --- fixtures for the contract check --------------------------------------------------------

def endpoints() -> list[str]:
    """Every database-backed GET the dashboard makes for one intersection. `/evidence` is not
    one: it reads committed result files and git history, the same in every state."""
    i = FIXTURE_ID
    return ["/health", "/sites", f"/heartbeat/{i}/latest", f"/prediction/{i}/latest",
            f"/count_forecast/{i}/latest", f"/prediction/{i}/history", f"/count_forecast/{i}/history",
            f"/vehicle_count/{i}/latest", *(f"/vehicle_count/{i}/history?window={w}" for w in ("1h", "6h", "24h")),
            f"/forecast_check/{i}/recent"]


def generate(name: str) -> dict:
    """One state's responses from the real server, its clock fixed at CLOCK throughout, so the
    same code always gives the same bytes. Nothing is normalised afterwards."""
    from fastapi.testclient import TestClient

    import server.app as server

    state = STATES[name]
    if not state.api:
        raise ValueError(f"{name} has no server to answer: every request fails as unreachable")
    clock = Clock(CLOCK)
    # The prune timer is the server's own state: put it back, so generating a fixture
    # leaves the server module as it found it.
    saved = server.DATABASE, server._next_prune
    with tempfile.TemporaryDirectory(prefix=GENERATE_PREFIX) as folder:
        server.DATABASE = Path(folder) / "fixture.sqlite"
        try:
            with server_clock(clock):
                load(name, clock, CLOCK)
                client = TestClient(server.app)
                responses = {}
                for path in endpoints():
                    reply = client.get(path)
                    responses[path] = {"status": reply.status_code, "body": reply.json()}
        finally:
            server.DATABASE, server._next_prune = saved
    return {"state": name, "purpose": state.purpose, "banner": state.banner, "clock": CLOCK,
            "generated_by": "python scripts/ui_fixture.py --write-fixtures", "responses": responses}


def canonical(data: dict) -> str:
    """The one way a fixture is written: sorted keys, so text equality is content equality."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def fixture_names() -> list[str]:
    return [name for name, state in STATES.items() if state.api]


def first_difference(expected, actual, path: str = "$") -> str | None:
    """Where two fixtures first differ, by name, type or value. None when they are equal.
    Types are compared exactly: 3 and 3.0, or 1 and true, are different."""
    if type(expected) is not type(actual):
        return f"{path}: {type(expected).__name__} became {type(actual).__name__}"
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                return f"{path}.{key}: missing from the server's response"
            if key not in expected:
                return f"{path}.{key}: new in the server's response"
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: {len(expected)} items became {len(actual)}"
        for i, (e, a) in enumerate(zip(expected, actual)):
            found = first_difference(e, a, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if expected == actual else f"{path}: {expected!r} became {actual!r}"


def write_fixtures(folder: Path = FIXTURES) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name in fixture_names():
        path = folder / f"{name}.json"
        path.write_text(canonical(generate(name)), encoding="utf-8", newline="\n")
        written.append(path)
    for extra in sorted(set(folder.glob("*.json")) - set(written)):
        print(f"  not a state any more, left in place for review: {extra.name}")
    return written


# --- the API process ------------------------------------------------------------------------

def _inside_a_run_folder(db: Path) -> str | None:
    """Why `db` may not be used, or None. Only a new file in a run folder under this machine's
    temp directory, never the deployment database."""
    db = db.resolve()
    folder = db.parent
    if db == DEPLOYED_DATABASE.resolve():
        return "that is the deployment database"
    if folder.parent != Path(tempfile.gettempdir()).resolve() or not folder.name.startswith(TEMP_PREFIX):
        return f"the database must be in a {TEMP_PREFIX}* folder in {tempfile.gettempdir()}"
    if not (folder / OWNER_FILE).is_file():
        return "that folder was not made by a fixture run"
    if db.exists():
        return "the database must be new"
    return None


def feed(server, name: str, state: State, every: float = FEED_EVERY_S) -> None:
    """Send the state again every step, so a fresh state stays fresh while someone looks at it."""
    while True:
        time.sleep(every)
        try:
            send_latest(server, name, state, time.time())
        except Exception as error:  # a locked database, say: the next step tries again
            print(f"feed: {type(error).__name__}: {error}", file=sys.stderr, flush=True)


def serve_api(name: str, db: Path, port: int) -> int:
    """The API process: the real server on `db`, loaded with `name`, then fed if the state is."""
    problem = _inside_a_run_folder(db)
    if problem:
        print(f"REFUSED: {problem}. Nothing was started.", file=sys.stderr)
        return 2
    import uvicorn

    import server.app as server

    server.DATABASE = db.resolve()
    state = STATES[name]
    clock = Clock(time.time())
    with server_clock(clock):
        load(name, clock, clock.t)
    if state.fed:
        threading.Thread(target=feed, args=(server, name, state), daemon=True).start()
    uvicorn.run(server.app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    return 0


class ApiProcess:
    """The API process, started and stopped only through the handle this run holds."""

    def __init__(self, work: Path, port: int):
        self.work, self.port, self.proc, self.db, self.n = work, port, None, None, 0

    def start(self, name: str) -> None:
        self.stop()
        self.n += 1
        self.db = self.work / f"state-{self.n}.sqlite"
        env = {k: v for k, v in os.environ.items() if k != "STMS_API_TOKEN"}
        env["PYTHONIOENCODING"] = "utf-8"
        # stdin is never the runner's own: on Windows a child that inherits a handle the command
        # reader is blocked on stalls at start-up until the next command is typed.
        with (self.work / "api.log").open("a", encoding="utf-8") as log:
            self.proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--serve-api", name, "--db", str(self.db),
                 "--api-port", str(self.port)], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, env=env)
        deadline = time.monotonic() + API_READY_S
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"the API process exited during start-up:\n{self.log_tail()}")
            if _get(self.port, "/health")[0] == 200:
                return
            time.sleep(0.2)
        raise RuntimeError(f"the API process did not answer /health within {API_READY_S:.0f} s:\n{self.log_tail()}")

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None
        if self.db is not None:
            for path in (self.db, self.db.with_name(self.db.name + "-journal")):
                with contextlib.suppress(OSError):
                    path.unlink()
            self.db = None

    def log_tail(self, lines: int = 8) -> str:
        log = self.work / "api.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        return "\n".join(text.splitlines()[-lines:])


def _get(port: int, path: str) -> tuple[int | None, bytes]:
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("GET", path)
        reply = connection.getresponse()
        return reply.status, reply.read()
    except OSError:
        return None, b""


# --- the page host --------------------------------------------------------------------------

class PageHandler(SimpleHTTPRequestHandler):
    """Serves the built dashboard at /dashboard/ and forwards its GET requests to the API."""

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript",
                      ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                      ".json": "application/json", ".html": "text/html"}

    def do_GET(self):
        if self.path in ("/", "/dashboard"):
            self.send_response(302)
            self.send_header("Location", f"/dashboard/?id={FIXTURE_ID}#live")
            self.end_headers()
            return
        if self.path.startswith("/dashboard/"):
            self.path = self.path[len("/dashboard"):]
            return super().do_GET()
        if self.path.startswith(API_PREFIXES):
            return self.forward()
        self.send_error(404)

    def do_HEAD(self):
        self.send_error(405)

    def do_POST(self):
        self.send_error(405, "this page host forwards GET only")

    do_PUT = do_DELETE = do_PATCH = do_POST

    def forward(self) -> None:
        try:
            connection = http.client.HTTPConnection("127.0.0.1", self.server.api_port, timeout=10)
            connection.request("GET", self.path, headers={"Accept": "application/json"})
            reply = connection.getresponse()
            body = reply.read()
        except OSError:
            # No API: answer nothing and close, as a dead server does. The browser reports a
            # network failure, which the dashboard shows as "server unreachable".
            self.close_connection = True
            return
        self.send_response(reply.status)
        self.send_header("Content-Type", reply.getheader("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 - the base class's name
        pass


class PageHost(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, dist: Path, api_port: int):
        self.api_port = api_port
        super().__init__(("127.0.0.1", port), functools.partial(PageHandler, directory=str(dist)))


# --- the run --------------------------------------------------------------------------------

def _alive(pid: int) -> bool:
    """Whether a process is running. On Windows `os.kill(pid, 0)` would end it, so it asks."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        code = ctypes.c_ulong()
        try:
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_folders() -> list[tuple[Path, int | None, bool]]:
    """Every fixture run folder in the temp directory: (folder, owner pid, owner running)."""
    out = []
    for folder in sorted(Path(tempfile.gettempdir()).glob(f"{TEMP_PREFIX}*")):
        if not folder.is_dir():
            continue
        try:
            pid = int(json.loads((folder / OWNER_FILE).read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            pid = None
        out.append((folder, pid, pid is not None and _alive(pid)))
    return out


def clean(remove: bool) -> int:
    """Name every folder left by a run whose owner has stopped, and remove those when asked.
    A folder whose owner is still running is never touched, and neither is one with no owner
    recorded: it may be a run that is still starting."""
    left = 0
    for folder, pid, running in run_folders():
        if running:
            continue
        if pid is None:
            print(f"  no owner recorded, so not touched: {folder}")
            continue
        left += 1
        if remove:
            shutil.rmtree(folder, ignore_errors=True)
            print(f"  removed {folder} (owner {pid} is not running)" if not folder.exists()
                  else f"  could not remove {folder}")
        else:
            print(f"  left by a run that did not finish (owner {pid} is not running): {folder}. "
                  f"--clean removes it.")
    return left


def _interrupt(_signum, _frame):
    raise KeyboardInterrupt


def run(name: str, port: int, api_port: int, dist: Path) -> int:
    from scripts.demo_live import port_free

    if not (dist / "index.html").is_file():
        print(f"The dashboard is not built ({dist}). Run: cd dashboard && npm run build", file=sys.stderr)
        return 1
    for flag, value in (("--port", port), ("--api-port", api_port)):
        if not port_free(value):
            print(f"REFUSED: {flag} {value} is already in use. Nothing was started.", file=sys.stderr)
            return 1
    clean(remove=False)
    work = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
    (work / OWNER_FILE).write_text(json.dumps({"pid": os.getpid(), "started": time.time()}), encoding="utf-8")
    print(f"run folder: {work}", flush=True)
    api, host = ApiProcess(work, api_port), None
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, _interrupt)
    else:
        signal.signal(signal.SIGTERM, _interrupt)
    try:
        host = PageHost(port, dist, api_port)
        threading.Thread(target=host.serve_forever, daemon=True).start()
        switch(api, name)
        print(f"\nOpen: http://127.0.0.1:{port}/dashboard/?id={FIXTURE_ID}#live", flush=True)
        print("Type a state to switch, server_down to stop the API, list, or quit. Ctrl+C also stops.", flush=True)
        commands: queue.Queue = queue.Queue()

        def read():
            for line in sys.stdin:
                commands.put(line.strip())
            commands.put(None)

        threading.Thread(target=read, daemon=True).start()
        while True:
            try:
                command = commands.get(timeout=0.5)
            except queue.Empty:
                continue
            if command is None:
                commands = queue.Queue()        # input closed: keep serving until Ctrl+C
                continue
            if command in ("quit", "exit", "q"):
                break
            if command == "list":
                print_states()
            elif command in STATES:
                switch(api, command)
            elif command:
                print(f"unknown: {command}. Type a state name, list or quit.", flush=True)
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    except RuntimeError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    finally:
        api.stop()
        if host is not None:
            host.shutdown()
            host.server_close()
        shutil.rmtree(work, ignore_errors=True)
        print(f"run folder removed: {work}" if not work.exists() else f"run folder could not be removed: {work}",
              flush=True)
    return 0


def switch(api: ApiProcess, name: str) -> None:
    state = STATES[name]
    if state.api:
        api.start(name)
    else:
        api.stop()
    print(f"state: {name} (expect the banner: {state.banner}). {state.purpose}", flush=True)


def print_states() -> None:
    for name, state in STATES.items():
        mark = f"  usability {USABILITY.index(name) + 1}" if name in USABILITY else ""
        print(f"  {name:14s}{mark:13s} {state.banner}")


def main(argv: list[str] | None = None) -> int:
    use_utf8()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", choices=STATES, default=USABILITY[0], help="the state to start in")
    ap.add_argument("--port", type=int, default=18100, help="the page host (default 18100)")
    ap.add_argument("--api-port", type=int, default=18101, help="the API process (default 18101)")
    ap.add_argument("--dist", type=Path, default=DIST, help="the built dashboard (default dashboard/dist)")
    ap.add_argument("--list", action="store_true", help="print the states and stop")
    ap.add_argument("--write-fixtures", action="store_true", help="rewrite dashboard/src/fixtures/ and stop")
    ap.add_argument("--clean", action="store_true", help="remove folders left by killed runs, and stop")
    ap.add_argument("--serve-api", choices=STATES, help=argparse.SUPPRESS)
    ap.add_argument("--db", type=Path, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.serve_api:
        if args.db is None:
            ap.error("--serve-api needs --db")
        return serve_api(args.serve_api, args.db, args.api_port)
    if args.list:
        print_states()
        return 0
    if args.write_fixtures:
        for path in write_fixtures():
            print(f"  wrote {path.relative_to(ROOT)}")
        print("Review the diff: a change here is a change in what the server sends the page.")
        return 0
    if args.clean:
        n = clean(remove=True)
        print(f"{n} folder(s) left by killed runs" if n else "nothing to clean")
        return 0
    return run(args.state, args.port, args.api_port, args.dist)


if __name__ == "__main__":
    sys.exit(main())
