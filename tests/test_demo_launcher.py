"""scripts/demo_launcher.py: a clip's number in, progress out, and nothing else (D29).

Over real HTTP on a real socket, with a fake run. The real stack is exercised by hand
and recorded in the changelog.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import demo_launcher  # noqa: E402
from scripts.demo_launcher import Launcher, make_handler, status_text  # noqa: E402
from scripts.demo_live import MILESTONES, REHEARSED, Clip  # noqa: E402

CLIPS = [Clip(Path(f"D:/secret/folder/{REHEARSED}.mp4"), "150th_Eastgate"),
         Clip(Path("D:/secret/folder/Bellevue_150th_Newport__2017-09-11_10-08-31.mp4"), "150th_Newport")]
ROOT = Path(__file__).resolve().parent.parent


class Run:
    """A run that does what a test tells it, and waits to be told."""

    def __init__(self):
        self.go, self.code, self.notes, self.clips = threading.Event(), 0, [], []
        self.raises = None

    def __call__(self, clip, report, stopping):
        self.clips.append(clip)
        for note in self.notes:
            report(note)
        while not self.go.wait(0.01):
            if stopping.is_set():
                return 130
        if self.raises:
            raise self.raises
        return self.code


@pytest.fixture
def site():
    run = Run()
    launcher = Launcher(CLIPS, run, minutes=7, dashboard_url="http://127.0.0.1:18000/dashboard/?id=live")
    holder = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(launcher, lambda: holder["port"]))
    holder["port"] = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", holder["port"], timeout=5)
        sent = {"Host": f"127.0.0.1:{holder['port']}", **({"Content-Type": "application/json"} if method == "POST" else {}), **(headers or {})}
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        for key, value in sent.items():
            c.putheader(key, value)
        if method == "POST":
            c.putheader("Content-Length", str(len(data)))
        c.endheaders(data if method == "POST" else None)
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, raw

    yield call, launcher, run, holder["port"]
    run.go.set()
    launcher.stop(wait_s=2)
    server.shutdown()
    server.server_close()


def state(call):
    return json.loads(call("GET", "/state")[1])


# ------------------------------------------------------------- what it serves --

def test_the_list_gives_numbers_and_names_and_never_a_path(site):
    call, *_ = site
    status, raw = call("GET", "/clips")
    assert status == 200 and b"secret" not in raw
    clips = json.loads(raw)
    assert [c["number"] for c in clips] == [1, 2] and clips[0]["rehearsed"] and not clips[1]["rehearsed"]


def test_nothing_of_a_path_reaches_the_browser_during_a_run(site):
    call, _, run, _ = site
    call("POST", "/run", {"clip": 1})
    assert b"secret" not in call("GET", "/state")[1]
    run.go.set()


def test_the_only_page_is_the_dashboard_on_analyze(site):
    """D41: one interface. The address opens the dashboard; there is no second page."""
    call, *_ = site
    status, _ = call("GET", "/")
    assert status == 302


def test_unknown_addresses_are_not_found(site):
    call, *_ = site
    assert call("GET", "/etc/passwd")[0] == 404
    assert call("POST", "/shutdown", {})[0] == 404


# ------------------------------------------------------------------ refusals ---

@pytest.mark.parametrize("clip", [0, 3, -1, "1", 1.0, True, None, "../../x.mp4", "D:/secret/folder/a.mp4"])
def test_only_a_number_on_the_list_starts_a_run(site, clip):
    call, _, run, _ = site
    status, raw = call("POST", "/run", {"clip": clip})
    assert status == 400 and run.clips == [] and b"secret" not in raw


def test_a_body_that_is_not_an_object_starts_nothing(site):
    call, _, run, _ = site
    assert call("POST", "/run", [1])[0] == 400
    assert call("POST", "/run", b"not json")[0] == 400
    assert call("POST", "/run", {"clip": 1, "pad": "x" * 2000})[0] == 400     # valid, and too long
    assert run.clips == []


def test_a_second_run_is_refused_while_one_is_going(site):
    call, _, run, _ = site
    assert call("POST", "/run", {"clip": 1})[0] == 202
    status, raw = call("POST", "/run", {"clip": 2})
    assert status == 409 and b"in progress" in raw and len(run.clips) == 1


def test_a_busy_port_is_refused_before_anything_starts(site):
    call, launcher, run, _ = site
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        launcher.ports = (held.getsockname()[1],)
        status, raw = call("POST", "/run", {"clip": 1})
    assert status == 409 and b"already in use" in raw and run.clips == []


@pytest.mark.parametrize("headers", [{"Host": "evil.example"},                       # DNS rebinding
                                     {"Origin": "http://evil.example"},              # another site in the browser
                                     {"Origin": "null"}])
def test_another_site_cannot_start_a_run_or_read_the_state(site, headers):
    call, _, run, _ = site
    assert call("POST", "/run", {"clip": 1}, headers)[0] == 403
    assert call("GET", "/state", None, headers)[0] == 403
    assert run.clips == []


def test_a_cross_site_form_cannot_start_a_run(site):
    call, _, run, _ = site
    for kind in ("application/x-www-form-urlencoded", "text/plain", "multipart/form-data"):
        assert call("POST", "/run", {"clip": 1}, {"Content-Type": kind})[0] == 415
    assert run.clips == []


def test_a_get_never_starts_anything(site):
    call, _, run, _ = site
    assert call("GET", "/run")[0] == 404 and run.clips == []


def test_it_listens_on_loopback_only():
    text = (ROOT / "scripts" / "demo_launcher.py").read_text(encoding="utf-8")
    assert 'ThreadingHTTPServer(("127.0.0.1", args.port)' in text and "0.0.0.0" not in text


# ------------------------------------------------------------------- the run ---

def test_the_status_says_what_the_system_is_doing_at_every_stage(site):
    call, _, run, _ = site
    assert state(call)["status"] == "Ready to run"
    call("POST", "/run", {"clip": 1})
    assert state(call)["status"].startswith("Starting the pipeline")
    assert state(call)["dashboard"] is None              # nothing to open yet
    _, launcher, *_ = site
    launcher.report("ready: broker, server and ingest each carried a real message")
    s = state(call)
    assert s["status"].startswith("Warming up") and s["dashboard"].endswith("/dashboard/?id=live")
    launcher.report(MILESTONES[0]), launcher.report(MILESTONES[1])
    assert state(call)["status"] == "Forecasts available"
    launcher.report("replay finished; the page now shows the streams going stale")
    assert state(call)["status"].startswith("Replay finished")
    run.go.set()
    launcher.thread.join(2)
    s = state(call)
    assert s["status"] == "Finished" and s["dashboard"] is None and s["code"] == 0


def test_milestones_show_the_expected_time_until_they_really_happen(site):
    call, launcher, *_ = site
    call("POST", "/run", {"clip": 1})
    assert all(m["at_s"] is None and m["expected"] for m in state(call)["milestones"])
    launcher.report(MILESTONES[1])
    steps = {m["name"]: m["at_s"] for m in state(call)["milestones"]}
    assert steps[MILESTONES[1]] is not None and steps[MILESTONES[2]] is None


@pytest.mark.parametrize("arrange, expected", [
    (lambda r: setattr(r, "code", 1), "Run failed"),
    (lambda r: setattr(r, "raises", RuntimeError("boom")), "Run failed"),
    (lambda r: r.notes.append("NOT READY, the edge was not started. ingest: running, but"), "Run failed"),
])
def test_a_failed_run_says_so_and_shows_why_and_a_new_run_can_follow(site, arrange, expected):
    call, launcher, run, _ = site
    arrange(run)
    call("POST", "/run", {"clip": 1})
    run.go.set()
    launcher.thread.join(2)
    assert state(call)["status"].startswith(expected)
    run.go.clear()
    run.raises, run.code = None, 0
    run.notes.clear()
    assert call("POST", "/run", {"clip": 2})[0] == 202   # the state resets for the new clip
    s = state(call)
    assert s["clip"] == CLIPS[1].id and s["problem"] is None and s["code"] is None


def test_stop_ends_the_run_and_says_stopped(site):
    call, launcher, *_ = site
    call("POST", "/run", {"clip": 1})
    assert call("POST", "/stop", {})[0] == 200
    launcher.thread.join(2)
    s = state(call)
    assert s["status"] == "Stopped" and not s["running"] and s["code"] == 130


def test_stop_with_nothing_running_is_harmless(site):
    call, *_ = site
    assert call("POST", "/stop", {})[0] == 200
    assert state(call)["status"] == "Ready to run"


def test_the_real_runner_stops_through_demo_lives_own_interrupt(monkeypatch, tmp_path):
    """Stop raises what Ctrl+C raises, so one cleanup path covers both."""
    seen = {}

    def fake(run, stack_class, sleep):
        seen.update(run=run, stack_class=stack_class)
        try:
            sleep(5)
        except KeyboardInterrupt:
            return 130
        return 0

    monkeypatch.setattr(demo_launcher, "run_with_cleanup", fake)
    args = type("A", (), dict(mosquitto=tmp_path, http_port=1, mqtt_port=2, minutes=7))()
    stopping = threading.Event()
    stopping.set()
    assert demo_launcher.run_clip(args)(CLIPS[1], lambda _t: None, stopping) == 130
    assert seen["run"].camera == "150th_Newport" and seen["run"].clip == CLIPS[1].path


def test_a_report_goes_to_the_page_as_well_as_the_console(monkeypatch, tmp_path, capsys):
    reported = []

    def fake(run, stack_class, sleep):
        stack_class(run, tmp_path).mark("first class forecast")
        return 0

    monkeypatch.setattr(demo_launcher, "run_with_cleanup", fake)
    args = type("A", (), dict(mosquitto=tmp_path, http_port=1, mqtt_port=2, minutes=7))()
    demo_launcher.run_clip(args)(CLIPS[0], reported.append, threading.Event())
    assert reported == ["first class forecast"] and "first class forecast" in capsys.readouterr().out


def test_status_text_never_claims_a_finished_run_while_one_is_failing():
    blank = [{"at_s": None}] * 5
    failed = dict(problem="FAILED: x", running=False, stopping=False, finished=False, ready=True, code=1, milestones=blank)
    assert status_text(failed).startswith("Run failed")


# ------------------------------------------------- the boundary stays where it is

def test_the_product_gains_no_way_to_start_a_run():
    """D41: only the dashboard's workbench client can ask for work, only from the local
    workbench, and the server gains no route for it."""
    for path in (ROOT / "dashboard" / "src").glob("*.js*"):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        assert "/demo/" not in text and '"/run"' not in text, path.name
        if path.name != "workbench.js":
            assert 'method: "POST"' not in text, path.name
    server = (ROOT / "server" / "app.py").read_text(encoding="utf-8")
    assert "/demo" not in server and "/workbench" not in server
