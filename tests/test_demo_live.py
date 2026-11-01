"""scripts/demo_live.py: only runnable clips, nothing on an unready stack, clean exits (D28).

Everything here is headless and uses no broker. The real stack is exercised by
hand and recorded in the changelog: these pin the decisions around it.
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import demo_live  # noqa: E402
from scripts.demo_live import (MILESTONES, Clip, NotReady, available_clips, choose,  # noqa: E402
                               main, readiness, run_demo, run_sheet, watch)

LANES = ["lane_0", "lane_1", "lane_2", "lane_3"]
CALIBRATION = "P103 calibration hour, Sun 2017-09-10 18:08 (q33/q67 of 60 s means, ADR-017)"


@pytest.fixture
def world(tmp_path):
    """Cameras: one with a valid profile, one whose spec changed, others with none."""
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"cameras": {
        "150th_Eastgate": {"low": 1, "med": 2, "source": CALIBRATION},
        "150th_Absent": {"low": 1, "med": 2, "source": CALIBRATION},
        "NE8th": {"low": 2, "med": 8, "source": "absolute 2/8"},
    }}), encoding="utf-8")
    profiles = tmp_path / "cameras"
    profiles.mkdir()
    digest = hashlib.sha256(spec.read_bytes()).hexdigest()
    for camera, sha in (("150th_Eastgate", digest), ("NE8th", "0" * 64)):   # NE8th: a stale hash, so invalid
        (profiles / f"{camera}.json").write_text(json.dumps({
            "schema_version": 1, "camera_id": camera,
            "geometry": {"coordinates": "normalised_image", "max_radius": 0.25,
                         "lanes": [{"name": n, "centre": [0.1 + i / 10, 0.5]} for i, n in enumerate(LANES)]},
            "lane_map": dict(zip(LANES, "NSEW")),
            "calibration": {"persistence_spec": "spec.json", "spec_sha256": sha, "key": camera},
            "limitations": [], "provenance": {}, "direction": {"status": "declared"}, "evidence": [],
        }), encoding="utf-8")
    clips = tmp_path / "clips" / "nested"
    clips.mkdir(parents=True)
    for stem in ("Bellevue_150th_Eastgate__2017-09-10_22-08-28",     # sorts before the rehearsed one
                 "Bellevue_150th_Eastgate__2017-09-11_14-08-31", "Bellevue_150th_Eastgate__2017-09-11_10-08-31",
                 "Bellevue_150th_Eastgate__2017-09-10_18-08-24",     # the calibration hour
                 "Bellevue_150th_Absent__2017-09-11_10-08-31",       # no lane geometry
                 "Bellevue_NE8th__2017-09-11_10-08-31",              # three lanes, the stack maps four
                 "Bellevue_Unknown__2017-09-11_10-08-31",            # no thresholds
                 "holiday"):
        (clips / f"{stem}.mp4").write_bytes(b"")
    return SimpleNamespace(root=tmp_path / "clips", profiles=profiles, project=tmp_path)


def clips_of(world):
    return available_clips(world.root, world.profiles, world.project)


# ------------------------------------------------------------------ the menu --

def test_only_calibrated_clips_are_offered_the_rehearsed_one_first(world):
    assert [c.id for c in clips_of(world)] == ["Bellevue_150th_Eastgate__2017-09-11_10-08-31",
                                               "Bellevue_150th_Eastgate__2017-09-10_22-08-28",
                                               "Bellevue_150th_Eastgate__2017-09-11_14-08-31"]


def test_the_committed_profiles_offer_exactly_the_three_ready_cameras(tmp_path):
    """A clean checkout: the profiles are committed, only the footage is not."""
    for camera in ("150th_Eastgate", "150th_Newport", "150th_SE38th", "NE8th"):
        (tmp_path / f"Bellevue_{camera}__2017-09-11_10-08-31.mp4").write_bytes(b"")
    clips = available_clips(tmp_path)
    assert {c.camera for c in clips} == {"150th_Eastgate", "150th_Newport", "150th_SE38th"}
    assert all(c.profile.name == f"{c.camera}.json" for c in clips)


def test_every_clip_runs_through_its_own_profile(world):
    assert {c.profile.name for c in clips_of(world)} == {"150th_Eastgate.json"}


def test_a_clip_is_chosen_by_number_or_id_and_anything_else_is_refused(world):
    clips = clips_of(world)
    assert choose(clips, "2") is clips[1]
    assert choose(clips, clips[1].id) is clips[1]
    assert choose(clips, None, ask=lambda _: "1") is clips[0]
    for bad in ("0", "4", "-1", "abc", "Bellevue_NE8th__2017-09-11_10-08-31"):
        with pytest.raises(ValueError, match="clips that can run"):
            choose(clips, bad)


# ---------------------------------------------------------------- refusals -----

def base_argv(world, tmp_path, *extra):
    exe = tmp_path / "mosquitto.exe"
    exe.write_bytes(b"")
    return ["--mosquitto", str(exe), "--clips-root", str(world.root), *extra]


@pytest.fixture
def refusals(world, tmp_path, monkeypatch):
    """main() with this world's clips, and a run that must never be reached."""
    monkeypatch.setattr(demo_live, "available_clips", lambda root: clips_of(world))
    started = []
    monkeypatch.setattr(demo_live, "run_with_cleanup", lambda args: started.append(args) or 0)
    return SimpleNamespace(argv=lambda *extra: base_argv(world, tmp_path, *extra), started=started)


def test_an_invalid_selection_starts_nothing(refusals, capsys):
    with pytest.raises(SystemExit) as stop:
        main(refusals.argv("--clip", "9"))
    assert stop.value.code == 2 and refusals.started == []
    assert "clips that can run" in capsys.readouterr().err


def test_a_clip_too_short_to_show_anything_is_refused(refusals, capsys):
    with pytest.raises(SystemExit):
        main(refusals.argv("--clip", "1", "--minutes", "2"))
    assert refusals.started == [] and "first count comparison" in capsys.readouterr().err


def test_a_busy_port_is_refused_before_anything_starts(refusals, capsys):
    """Otherwise an old server's /health would answer for a stack that never started."""
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        assert main(refusals.argv("--clip", "1", "--http-port", str(port))) == 1
    assert refusals.started == [] and "already in use" in capsys.readouterr().err


def test_list_only_lists(refusals, capsys):
    assert main(refusals.argv("--list")) == 0
    assert refusals.started == [] and "(rehearsed)" in capsys.readouterr().out


def test_a_good_selection_runs_with_the_camera_of_that_clip(refusals):
    assert main(refusals.argv("--clip", "3")) == 0
    args = refusals.started[0]
    assert args.camera == "150th_Eastgate" and args.clip.stem.endswith("14-08-31")
    assert args.profile.name == "150th_Eastgate.json"


# --------------------------------------------------------------- readiness -----

class Proc:
    def __init__(self, ends=None, code=0):
        self.returncode, self._ends, self._code, self.terminated = None, ends, code, False

    def poll(self):
        if self._ends is not None:
            self._ends -= 1
            if self._ends < 0:
                self.returncode = self._code
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -1

    def wait(self, _timeout=None):
        return self.returncode


class FakeStack:
    """The Stack's surface, with a store that fills only when told to."""

    def __init__(self, tmp_path, *, ingest_works=True, health=True, edge=None, answers=None):
        self.work, self.base = tmp_path, "http://x"
        self.procs, self.marks, self.started = {}, [], []
        self.ingest_works, self.health, self.edge = ingest_works, health, edge or Proc(ends=3)
        self.answers = answers if answers is not None else DONE
        self.published = False
        self.args = SimpleNamespace(mqtt_port=1)

    def mark(self, text):
        self.marks.append(text)

    def start_broker(self):
        self.procs["broker"] = Proc()

    def start_server(self):
        self.procs["server"] = Proc()

    def start_ingest(self):
        self.procs["ingest"] = Proc()

    def start_edge(self, intersection, samples):
        self.started.append((intersection, samples))
        self.procs["edge"] = self.edge

    def wait_until(self, probe, _timeout):
        return probe()

    def get(self, path):
        if path == "/health":
            return (200, {}) if self.health else (0, None)
        if path.startswith(f"/heartbeat/{demo_live.PROBE_ID}"):
            return (200, {}) if self.published and self.ingest_works else (404, None)
        return self.answers.get(path, (404, None))


DONE = {"/heartbeat/live/latest": (200, {"source": {"kind": "replay"}}),
        "/prediction/live/latest": (200, {}), "/count_forecast/live/latest": (200, {}),
        "/forecast_check/live/recent": (200, {"slots": [{"kind": "check", "classes": {"N": {}}, "counts": {"N": {}}}]})}


class Transport:
    def __init__(self, stack):
        self.stack, self.stopped, self.published = stack, False, []

    def publish(self, topic, payload, qos):
        self.published.append((topic, payload, qos))
        self.stack.published = True

    def stop(self):
        self.stopped = True


def args_for(tmp_path, minutes=7.0, hold=0.0):
    clip = Clip(tmp_path / "Bellevue_150th_Eastgate__2017-09-11_10-08-31.mp4", "150th_Eastgate")
    return SimpleNamespace(chosen=clip, minutes=minutes, hold=hold)


def no_sleep(_seconds):
    return None


def test_a_healthy_stack_is_ready_only_after_a_message_came_all_the_way_back(tmp_path):
    stack = FakeStack(tmp_path)
    stack.start_broker(), stack.start_server(), stack.start_ingest()
    transport = Transport(stack)
    readiness(stack, lambda s: transport, sleep=no_sleep)
    topic, _, _ = transport.published[0]
    assert topic == f"stms/{demo_live.PROBE_ID}/system/heartbeat" and transport.stopped


@pytest.mark.parametrize("fault, expected", [
    (dict(ingest_works=False), "ingest: running, but"),
    (dict(health=False), "server: no answer"),
])
def test_a_part_that_does_not_work_is_named_and_the_edge_never_starts(tmp_path, fault, expected):
    stack = FakeStack(tmp_path, **fault)
    assert run_demo(args_for(tmp_path), stack, connect=lambda s: Transport(s), sleep=no_sleep) == 1
    assert stack.started == [] and any(expected in m for m in stack.marks)


def test_a_broker_that_refuses_is_named_and_the_edge_never_starts(tmp_path):
    def refuse(_stack):
        raise NotReady("broker: refused the connection (Not authorized)")

    stack = FakeStack(tmp_path)
    assert run_demo(args_for(tmp_path), stack, connect=refuse, sleep=no_sleep) == 1
    assert stack.started == [] and any("broker: refused" in m for m in stack.marks)


@pytest.mark.parametrize("name", ["broker", "server", "ingest"])
def test_a_part_that_exited_is_named_with_its_log(tmp_path, name):
    (tmp_path / f"{name}.log").write_text("the reason it stopped\n", encoding="utf-8")
    stack = FakeStack(tmp_path)
    stack.start_broker(), stack.start_server(), stack.start_ingest()
    stack.procs[name] = Proc(ends=0, code=3)
    stack.procs[name].poll()
    def connect(_stack):                                 # a dead part is named before any connection,
        raise NotReady("broker: not reachable over TLS")  # so its own log is shown, not a symptom

    with pytest.raises(NotReady, match=f"{name}: exited") as refused:
        readiness(stack, connect, sleep=no_sleep)
    assert "the reason it stopped" in str(refused.value)


# ------------------------------------------------------------------ the run ----

def test_a_full_run_reports_each_milestone_and_finishes(tmp_path):
    stack = FakeStack(tmp_path)
    assert run_demo(args_for(tmp_path), stack, connect=lambda s: Transport(s), sleep=no_sleep) == 0
    assert stack.started == [("live", 210)]              # 7 minutes of 2 s samples
    assert all(m in stack.marks for m in MILESTONES)
    assert stack.marks[-1] == "DONE"


def test_a_failing_edge_is_a_failed_run_with_its_log(tmp_path):
    (tmp_path / "edge.log").write_text("weights not found\n", encoding="utf-8")
    stack = FakeStack(tmp_path, edge=Proc(ends=0, code=2))
    assert run_demo(args_for(tmp_path), stack, connect=lambda s: Transport(s), sleep=no_sleep) == 1
    assert any("status 2" in m and "weights not found" in m for m in stack.marks)


def test_a_replay_that_ends_short_of_a_milestone_is_a_failed_run(tmp_path):
    answers = {k: v for k, v in DONE.items() if "forecast_check" not in k}
    stack = FakeStack(tmp_path, answers=answers)
    assert run_demo(args_for(tmp_path), stack, connect=lambda s: Transport(s), sleep=no_sleep) == 1
    assert any("first ribbon cell" in m and "FAILED" in m for m in stack.marks)


def test_an_edge_that_never_reports_is_stopped_not_waited_on_for_ever(tmp_path):
    stack = FakeStack(tmp_path, answers={})
    edge = Proc()                                        # runs, and never reports
    code, seen = watch(stack, edge, edge_start_s=4.0, sleep=no_sleep)
    assert code == 1 and seen == set() and edge.terminated


def test_the_hold_counts_down_and_zero_means_none(tmp_path):
    stack = FakeStack(tmp_path)
    demo_live.hold(stack, 60, sleep=no_sleep)
    assert [m for m in stack.marks if "stopping" in m] == ["stopping in 60 s; Ctrl+C stops now",
                                                           "stopping in 30 s; Ctrl+C stops now"]
    stack.marks.clear()
    demo_live.hold(stack, 0, sleep=no_sleep)
    assert stack.marks == []


def test_the_run_sheet_says_what_the_demo_is_not(tmp_path):
    text = run_sheet(args_for(tmp_path).chosen, 7.0, "http://x/dashboard/?id=live")
    for needed in ("not a camera", "S65", "does not predict or control the signal", "not accuracy",
                   "Do not restart", "licence is unresolved", "http://x/dashboard/?id=live",
                   "does not move the system"):
        assert needed in text
    assert "%" not in text


def test_the_dashboard_shows_video_only_from_a_file_opened_in_the_browser():
    """NFR-13, narrowed by D34: no frame ever reaches the page over the network. The
    Analyze page may play a file the viewer opens, through an object URL. No other
    page can show a picture, and no endpoint the page may call can carry one."""
    source = Path(__file__).resolve().parent.parent / "dashboard" / "src"
    for path in source.glob("*.jsx"):
        text = path.read_text(encoding="utf-8")
        assert "<img" not in text and "<iframe" not in text, path.name
        if path.name != "Analyze.jsx" and ".test." not in path.name:
            assert "<video" not in text, path.name
    analyze = (source / "Analyze.jsx").read_text(encoding="utf-8")
    assert analyze.count("<video") == 1 and "src={video.url}" in analyze
    assert "URL.createObjectURL(file)" in analyze
    assert "fetch" not in analyze and "http" not in analyze and "api.js" not in analyze
    allowed = (source / "api.js").read_text(encoding="utf-8")
    assert "video\/" not in allowed and "frame" not in allowed.split("ALLOWED", 1)[1].split("];", 1)[0]


# -------------------------------------------------------------- cleaning up ----

class CleanupStack(FakeStack):
    stopped: list = []

    def __init__(self, args, work):
        super().__init__(work)
        self.args = args
        CleanupStack.stopped = []

    def prepare_broker(self):
        pass

    def stop(self, name):
        CleanupStack.stopped.append(name)
        self.procs.pop(name)


@pytest.mark.parametrize("outcome, code", [(KeyboardInterrupt, 130), (lambda: 1, 1), (lambda: 0, 0)])
def test_every_ending_stops_what_it_started_and_restores_the_database(tmp_path, monkeypatch, outcome, code):
    database = tmp_path / "data" / "stms.sqlite"
    database.parent.mkdir()
    database.write_text("the developer's own store", encoding="utf-8")
    monkeypatch.setattr(demo_live, "DATABASE", database)
    monkeypatch.setattr(demo_live, "Stack", CleanupStack)

    def run(_args, stack, sleep=None):
        stack.start_broker(), stack.start_server(), stack.start_ingest()
        database.write_text("this demo's store", encoding="utf-8")
        if outcome is KeyboardInterrupt:
            raise KeyboardInterrupt
        return outcome()

    monkeypatch.setattr(demo_live, "run_demo", run)
    assert demo_live.run_with_cleanup(SimpleNamespace()) == code
    assert sorted(CleanupStack.stopped) == ["broker", "ingest", "server"]
    assert database.read_text(encoding="utf-8") == "the developer's own store"


def test_with_no_earlier_database_none_is_left_behind(tmp_path, monkeypatch):
    database = tmp_path / "stms.sqlite"
    monkeypatch.setattr(demo_live, "DATABASE", database)
    monkeypatch.setattr(demo_live, "Stack", CleanupStack)
    monkeypatch.setattr(demo_live, "run_demo", lambda _a, _s, sleep=None: database.write_text("x", encoding="utf-8") and 0)
    assert demo_live.run_with_cleanup(SimpleNamespace()) == 0
    assert not database.exists()
