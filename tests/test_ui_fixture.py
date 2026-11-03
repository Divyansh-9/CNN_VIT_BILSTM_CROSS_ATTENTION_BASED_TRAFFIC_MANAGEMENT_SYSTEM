"""D36: UI fixtures from the real server, and the runner that serves them.

The contract check: every committed fixture in dashboard/src/fixtures/ must be exactly what the
real server sends today, generated with its clock fixed. dashboard/src/fixtures.test.js checks the
same files against the page's own validators, so a change on either side fails one of the two.
The planted changes below prove the check can fail, which a check that only passes cannot show.

The runner tests start real processes and need uvicorn; the contract tests need fastapi and httpx.
All three are pinned in requirements.txt and installed by CI's fast job, so a missing one **fails**
here rather than skips: a skip would only hide a broken environment and go green over these tests.
"""

from __future__ import annotations

import http.client
import importlib
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_fixture as fx  # noqa: E402

SCRIPT = ROOT / "scripts" / "ui_fixture.py"


def require(module: str):
    """Import a dependency these tests need, or fail. Never skip (see the module docstring)."""
    try:
        return importlib.import_module(module)
    except ImportError as error:
        pytest.fail(f"{module} is required here and pinned in requirements.txt ({error}). "
                    f"Install it rather than skip these tests.", pytrace=False)


@pytest.fixture(scope="module")
def server():
    require("fastapi")
    require("httpx")
    import server.app as server

    return server


def test_a_missing_dependency_fails_rather_than_skips():
    with pytest.raises(pytest.fail.Exception, match="pinned in requirements.txt"):
        require("stms_no_such_module")


def committed(name: str) -> tuple[dict, str]:
    text = (fx.FIXTURES / f"{name}.json").read_text(encoding="utf-8").replace("\r\n", "\n")
    return json.loads(text), text


# --- the contract check ----------------------------------------------------------------------

def test_the_committed_files_are_exactly_the_states():
    assert {p.stem for p in fx.FIXTURES.glob("*.json")} == set(fx.fixture_names())
    assert set(fx.USABILITY) <= set(fx.STATES)


@pytest.mark.parametrize("name", fx.fixture_names())
def test_each_fixture_is_exactly_what_the_server_sends(server, name):
    generated = fx.generate(name)
    expected, text = committed(name)
    difference = fx.first_difference(expected, generated)
    assert difference is None, (
        f"{name}: {difference}. The server no longer sends what the page was tested against. If the "
        f"change is intended, run `python scripts/ui_fixture.py --write-fixtures` and review the diff.")
    assert fx.canonical(generated) == text


def test_generation_is_repeatable_because_the_clock_is_fixed(server):
    """Nothing is normalised before the comparison. A field that changed between runs, such as an
    age read from a real clock, would fail here and in the check above."""
    assert fx.canonical(fx.generate("edge_silent")) == fx.canonical(fx.generate("edge_silent"))


def test_a_renamed_field_in_the_server_is_caught(server, monkeypatch):
    real = server.freshness

    def renamed(received_at, horizon_sec, now=None):
        out = real(received_at, horizon_sec, now)
        return {"age_seconds" if key == "age_s" else key: value for key, value in out.items()}

    monkeypatch.setattr(server, "freshness", renamed)
    difference = fx.first_difference(committed("normal")[0], fx.generate("normal"))
    assert difference is not None and "age_s: missing from the server's response" in difference


def test_a_changed_type_in_the_server_is_caught(server, monkeypatch):
    real = server.freshness

    def whole_seconds(received_at, horizon_sec, now=None):
        out = real(received_at, horizon_sec, now)
        return {**out, "age_s": int(round(out["age_s"]))}

    monkeypatch.setattr(server, "freshness", whole_seconds)
    difference = fx.first_difference(committed("normal")[0], fx.generate("normal"))
    assert difference is not None and "float became int" in difference


def test_a_changed_value_in_the_server_is_caught(server, monkeypatch):
    monkeypatch.setattr(server, "HEARTBEAT_NOTE", "a different note")
    difference = fx.first_difference(committed("normal")[0], fx.generate("normal"))
    assert difference is not None and "/heartbeat/test-fixture/latest" in difference and "note" in difference


def test_first_difference_names_what_changed():
    base = {"a": 1, "b": [1.0, True], "c": {"d": "x"}}
    assert fx.first_difference(base, json.loads(json.dumps(base))) is None
    assert "missing" in fx.first_difference(base, {"b": [1.0, True], "c": {"d": "x"}})
    assert "new in" in fx.first_difference(base, {**base, "z": 0})
    assert "float became int" in fx.first_difference(base, {**base, "b": [1, True]})
    assert "bool became int" in fx.first_difference(base, {**base, "b": [1.0, 1]})
    assert "2 items became 1" in fx.first_difference(base, {**base, "b": [1.0]})
    assert "'x' became 'y'" in fx.first_difference(base, {**base, "c": {"d": "y"}})


# --- what the fixtures hold ------------------------------------------------------------------

def responses(name: str) -> dict:
    return committed(name)[0]["responses"]


def body(name: str, path: str):
    reply = responses(name)[path.replace("{id}", fx.FIXTURE_ID)]
    return reply["status"], reply["body"]


def test_no_fixture_names_a_real_model_or_a_live_camera():
    for name in fx.fixture_names():
        text = committed(name)[1]
        assert set(re.findall(r"(?:persistence|ridge|[A-H])@[0-9a-f]{12}", text)) <= {fx.CLASS_MODEL, fx.COUNT_MODEL}
        status, beat = body(name, "/heartbeat/{id}/latest")
        if status == 200:
            assert beat["source"]["kind"] == "replay"
            assert beat["source"]["label"] == f"TEST_FIXTURE_{name}"
            assert beat["directions_verified"] is False
        for site in body(name, "/sites")[1]["sites"]:
            assert site["kind"] == "replay" and site["label"].startswith("TEST_FIXTURE_")


def test_each_state_holds_what_it_says():
    fresh = lambda name, path: body(name, path)[1]["stale"] is False  # noqa: E731
    for name in ("normal", "high", "low", "partial", "missing_count"):
        assert fresh(name, "/heartbeat/{id}/latest") and fresh(name, "/prediction/{id}/latest")
    assert body("missing_count", "/count_forecast/{id}/latest")[0] == 404
    for path in ("/heartbeat/{id}/latest", "/prediction/{id}/latest", "/count_forecast/{id}/latest"):
        assert body("stale_edge", path)[1]["stale"] is True
    assert body("edge_silent", "/heartbeat/{id}/latest")[1]["stale"] is True
    assert not body("edge_silent", "/prediction/{id}/latest")[1]["stale"]
    assert body("partial", "/prediction/{id}/latest")[1]["missing_approaches"] == ["E", "W"]
    assert body("partial", "/count_forecast/{id}/latest")[1]["missing_approaches"] == ["W"]
    assert "lane_3" not in body("partial", "/vehicle_count/{id}/latest")[1]["lanes"]
    assert body("low", "/count_forecast/{id}/latest")[1]["counts"]["W"] == 0.0
    assert max(body("high", "/count_forecast/{id}/latest")[1]["counts"].values()) > 10
    # Nothing published: each latest value is 404, each history is an empty list, never zeros.
    for path in ("/heartbeat/{id}/latest", "/prediction/{id}/latest", "/count_forecast/{id}/latest",
                 "/vehicle_count/{id}/latest", "/forecast_check/{id}/recent"):
        assert body("no_data", path)[0] == 404, path
    for path in ("/prediction/{id}/history", "/count_forecast/{id}/history"):
        assert body("no_data", path) == (200, {"intersection_id": fx.FIXTURE_ID, "rows": []})
    for window in ("1h", "6h", "24h"):
        status, buckets = body("no_data", f"/vehicle_count/{{id}}/history?window={window}")
        assert status == 200 and buckets["lanes"] == [] and all(b["lanes"] == {} for b in buckets["buckets"])
    assert body("no_data", "/sites")[1]["sites"] == []


# --- the API process refuses any database but a new one in its own run folder ----------------

def test_the_api_process_refuses_any_other_database(tmp_path, monkeypatch):
    monkeypatch.setattr(fx.tempfile, "tempdir", str(tmp_path))
    run = tmp_path / f"{fx.TEMP_PREFIX}abc"
    run.mkdir()
    assert "deployment database" in fx._inside_a_run_folder(fx.DEPLOYED_DATABASE)
    assert "must be in a" in fx._inside_a_run_folder(tmp_path / "loose.sqlite")
    assert "not made by a fixture run" in fx._inside_a_run_folder(run / "a.sqlite")
    (run / fx.OWNER_FILE).write_text("{}", encoding="utf-8")
    assert fx._inside_a_run_folder(run / "a.sqlite") is None
    (run / "a.sqlite").write_bytes(b"")
    assert "must be new" in fx._inside_a_run_folder(run / "a.sqlite")


def test_the_api_process_exits_rather_than_open_the_deployment_database(tmp_path):
    before = fx.DEPLOYED_DATABASE.stat().st_mtime_ns if fx.DEPLOYED_DATABASE.exists() else None
    done = subprocess.run([sys.executable, str(SCRIPT), "--serve-api", "normal", "--db", str(fx.DEPLOYED_DATABASE),
                           "--api-port", str(free_port())], capture_output=True, text=True, encoding="utf-8",
                          timeout=60, cwd=ROOT, env=temp_env(tmp_path))
    assert done.returncode == 2 and "deployment database" in done.stderr
    after = fx.DEPLOYED_DATABASE.stat().st_mtime_ns if fx.DEPLOYED_DATABASE.exists() else None
    assert before == after


def test_clean_removes_only_folders_whose_owner_has_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(fx.tempfile, "tempdir", str(tmp_path))
    finished = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    folders = {}
    for kind, pid in (("dead", int(finished.stdout)), ("alive", os.getpid()), ("ownerless", None)):
        folders[kind] = tmp_path / f"{fx.TEMP_PREFIX}{kind}"
        folders[kind].mkdir()
        if pid is not None:
            (folders[kind] / fx.OWNER_FILE).write_text(json.dumps({"pid": pid}), encoding="utf-8")
    (tmp_path / f"{fx.GENERATE_PREFIX}busy").mkdir()
    assert fx.clean(remove=True) == 1
    assert not folders["dead"].exists()
    assert folders["alive"].exists() and folders["ownerless"].exists()
    assert (tmp_path / f"{fx.GENERATE_PREFIX}busy").exists()


# --- the runner, as real processes ------------------------------------------------------------

def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def temp_env(tmp_path: Path) -> dict:
    """The runner's temp directory is the test's, so every folder it makes is visible here."""
    return {**os.environ, "TMP": str(tmp_path), "TEMP": str(tmp_path), "TMPDIR": str(tmp_path),
            "PYTHONIOENCODING": "utf-8"}


class Runner:
    def __init__(self, tmp_path: Path, state: str, port: int | None = None, dist: Path | None = None):
        require("uvicorn")
        self.port, self.api_port = port or free_port(), free_port()
        self.dist = dist or make_dist(tmp_path)
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--state", state, "--port", str(self.port), "--api-port",
             str(self.api_port), "--dist", str(self.dist)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            cwd=ROOT, env=temp_env(tmp_path), creationflags=flags)
        self.lines: queue.Queue = queue.Queue()
        self.seen: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))
        self.lines.put(None)

    def wait_for(self, text: str, timeout: float = 90.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                raise AssertionError(f"runner exited before {text!r}:\n" + "\n".join(self.seen))
            self.seen.append(line)
            if text in line:
                return line
        raise AssertionError(f"no {text!r} within {timeout} s:\n" + "\n".join(self.seen))

    def send(self, command: str) -> None:
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def folder(self) -> Path:
        return Path(next(line for line in self.seen if line.startswith("run folder: ")).split(": ", 1)[1])

    def get(self, path: str):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", path)
        reply = connection.getresponse()
        return reply.status, reply.getheader("Content-Type"), reply.read()

    def quit(self) -> int:
        self.send("quit")
        code = self.proc.wait(60)
        self.drain()
        return code

    def drain(self) -> None:
        while True:
            try:
                line = self.lines.get(timeout=5)
            except queue.Empty:
                return
            if line is None:
                return
            self.seen.append(line)


def make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><title>stub page</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export const ok = true;", encoding="utf-8")
    return dist


def run_folders(tmp_path: Path) -> list[Path]:
    return sorted(tmp_path.glob(f"{fx.TEMP_PREFIX}*"))


def wait_until(check, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.2)
    return False


def test_the_runner_serves_a_state_goes_down_recovers_and_cleans_up(tmp_path):
    runner = Runner(tmp_path, "normal")
    try:
        runner.wait_for("Open: ")
        status, kind, page = runner.get("/dashboard/?id=test-fixture")
        assert status == 200 and b"stub page" in page
        assert runner.get("/dashboard/assets/app.js")[1].startswith("text/javascript")
        status, _, raw = runner.get("/heartbeat/test-fixture/latest")
        beat = json.loads(raw)
        assert status == 200 and beat["source"]["label"] == "TEST_FIXTURE_normal" and beat["source"]["kind"] == "replay"
        assert json.loads(runner.get("/prediction/test-fixture/latest")[2])["model"] == fx.CLASS_MODEL
        # An HTTP error from a running API passes through as itself.
        assert runner.get("/count_forecast/someone-else/latest")[0] == 404
        connection = http.client.HTTPConnection("127.0.0.1", runner.port, timeout=10)
        connection.request("POST", "/heartbeat/test-fixture", body="x")
        assert connection.getresponse().status == 405
        # A fed state stays fresh while it is watched.
        time.sleep(fx.FEED_EVERY_S * 2.5)
        assert json.loads(runner.get("/heartbeat/test-fixture/latest")[2])["age_s"] < 4

        runner.send("server_down")
        runner.wait_for("state: server_down")
        with pytest.raises((http.client.RemoteDisconnected, ConnectionError)):
            runner.get("/health")
        assert runner.get("/dashboard/")[0] == 200          # the page itself stays up

        runner.send("normal")
        runner.wait_for("state: normal")
        assert runner.get("/health")[0] == 200              # and recovers when the API returns
        folder = runner.folder()
        assert folder.is_dir() and (folder / fx.OWNER_FILE).is_file()
        assert runner.quit() == 0
        assert not folder.exists() and run_folders(tmp_path) == []
        assert wait_until(lambda: fx_port_free(runner.api_port))
    finally:
        if runner.proc.poll() is None:
            runner.proc.kill()


def fx_port_free(port: int) -> bool:
    from scripts.demo_live import port_free

    return port_free(port)


def test_the_runner_runs_twice_in_a_row(tmp_path):
    for _ in range(2):
        runner = Runner(tmp_path, "no_data")
        try:
            runner.wait_for("Open: ")
            assert runner.get("/prediction/test-fixture/latest")[0] == 404
            assert runner.quit() == 0
            assert run_folders(tmp_path) == []
        finally:
            if runner.proc.poll() is None:
                runner.proc.kill()


def test_an_interrupt_stops_the_api_and_removes_the_folder(tmp_path):
    runner = Runner(tmp_path, "normal")
    try:
        runner.wait_for("Open: ")
        folder = runner.folder()
        runner.proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        runner.proc.wait(60)
        runner.drain()
        assert not folder.exists(), "\n".join(runner.seen)
        assert wait_until(lambda: fx_port_free(runner.api_port))
    finally:
        if runner.proc.poll() is None:
            runner.proc.kill()


def test_the_runner_refuses_a_port_in_use_and_starts_nothing(tmp_path):
    require("uvicorn")
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        runner = Runner(tmp_path, "normal", port=holder.getsockname()[1])
        code = runner.proc.wait(60)
        runner.drain()
    assert code == 1 and any("REFUSED: --port" in line for line in runner.seen)
    assert run_folders(tmp_path) == []


def test_the_runner_refuses_an_unbuilt_dashboard(tmp_path):
    empty = tmp_path / "nothing-built"
    empty.mkdir()
    done = subprocess.run([sys.executable, str(SCRIPT), "--dist", str(empty), "--port", str(free_port()),
                           "--api-port", str(free_port())], capture_output=True, text=True, encoding="utf-8",
                          timeout=60, cwd=ROOT, env=temp_env(tmp_path), stdin=subprocess.DEVNULL)
    assert done.returncode == 1 and "npm run build" in done.stderr
    assert run_folders(tmp_path) == []
