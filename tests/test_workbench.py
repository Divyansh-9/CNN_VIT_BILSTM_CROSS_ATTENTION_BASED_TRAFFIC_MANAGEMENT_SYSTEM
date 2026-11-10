"""scripts/workbench.py and its routes in scripts/demo_launcher.py (D40, D41).

A video the viewer opened is found on this computer by its fingerprint, analysed
for a camera the viewer declares, checked, and stored by key. A new camera is
placed in the page and gets its levels from its first recording. Over real HTTP on
a real socket, with a fake analysis tool: the real tool is run by hand and recorded
in the changelog.
"""

from __future__ import annotations

import http.client
import json
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edge.profile import load_profile  # noqa: E402
from scripts import workbench  # noqa: E402
from scripts.demo_launcher import SERVER_GETS, Launcher, make_handler, static_file  # noqa: E402
from scripts.demo_live import REHEARSED, Clip  # noqa: E402
from scripts.workbench import (Analyses, Cameras, Check, Locator, Recording, analysis_key,  # noqa: E402
                               calibration_limits, catalogue, fingerprint, preflight, progress_line, redact,
                               validate_result)

PROFILE = ROOT / "cameras" / "150th_Eastgate.json"
needs_profile = pytest.mark.skipif(not (ROOT / "experiments/results/bellevue_pilot/persistence_v1.json").exists(),
                                   reason="Bellevue-derived specs absent (public tree)")
INPUTS = {"detector_sha256": "d" * 64, "schema": 2}
LANES = [{"centre": [0.25, 0.5], "approach": "N"}, {"centre": [0.75, 0.5], "approach": "S"}]


def result_for(clip: str, camera: str = "150th_Eastgate", samples: int = 150, lanes=("lane_0", "lane_1"),
               approaches=("N", "S")) -> dict:
    """What analyze_video writes, small: counts that vary, so levels can be set from them."""
    rows = []
    for k in range(samples):
        counts = {lane: (k * (i + 2)) % (5 + 2 * i) for i, lane in enumerate(lanes)}
        rows.append({"t": k * 2.0, "counts": counts, "boxes": [], "detections": [], "level": None,
                     "number": None, "then": None})
    for k, row in enumerate(rows):
        after = rows[k + 1:k + 31]
        if len(after) == 30:
            row["then"] = {a: {"level": "LOW", "number": round(sum(s["counts"][lane] for s in after) / 30, 4)}
                           for lane, a in zip(lanes, approaches)}
    return {"kind": "stms-video-analysis", "schema": 2, "camera": camera, "clip": clip, "step_s": 2,
            "duration_s": samples * 2.0, "limits": {"low": 0.0, "med": 0.5}, "known_limits": [],
            "models": {"level": "persistence@x", "number": "ridge@x"}, "samples": rows}


class Tool:
    """A fake analyze_video: reports progress, writes a result, waits to be told."""

    def __init__(self, *, samples=150, code=0, write=True, last="done"):
        self.samples, self.code, self.write, self.last = samples, code, write, last
        self.go, self.calls = threading.Event(), []

    def __call__(self, video, profile, out, on_progress, stopping):
        self.calls.append((video, profile, out))
        for k in range(0, self.samples, 5):
            on_progress(k * 2.0, self.samples * 2.0)
        while not self.go.wait(0.01):
            if stopping.is_set():
                return 130, []
        if self.write:
            camera = load_profile(profile).camera_id
            out.write_text(json.dumps(result_for(video.stem, camera, self.samples)), encoding="utf-8")
        return self.code, [self.last]


def passing(length=300.0):
    def check(recording, profile_path):
        return [Check("Camera profile", True, "ok")], load_profile(profile_path), length
    return check


def wait_for(predicate, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def videos(tmp_path):
    folder = tmp_path / "secret" / "footage"
    folder.mkdir(parents=True)
    for name in ("b_clip.mp4", "a_clip.MOV", "notes.txt"):
        (folder / name).write_bytes(name.encode() * 1000)
    (folder / "nested").mkdir()
    (folder / "nested" / "c_clip.mkv").write_bytes(b"c" * 5000)
    return folder


def make(videos, tmp_path, tool, check=None, locator=None):
    cameras = Cameras([load_profile(PROFILE)], tmp_path / "results" / "cameras")
    return Analyses(catalogue([videos, videos]), cameras, tmp_path / "results", runner=tool,
                    inputs=lambda: INPUTS, check=check or passing(), locator=locator)


# ---------------------------------------------------------------- the parts ---

def test_the_catalogue_finds_every_video_once_and_nothing_else(videos):
    names = [r.name for r in catalogue([videos, videos])]
    assert names == ["a_clip.MOV", "b_clip.mp4", "c_clip.mkv"]


def test_a_fingerprint_follows_the_bytes_not_the_name(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"x" * 10_000)
    shutil.copy(a, b)
    assert fingerprint(a, chunk=1024) == fingerprint(b, chunk=1024)
    b.write_bytes(b"x" * 5_000 + b"y" + b"x" * 4_999)
    assert fingerprint(a, chunk=1024) != fingerprint(b, chunk=1024)


def test_the_browser_fingerprint_pinned_in_the_dashboard_tests_is_this_one(tmp_path):
    """dashboard.test.jsx pins these digests for workbench.js; they must stay this function's."""
    path = tmp_path / "v.bin"
    path.write_bytes(bytes(range(256)) * 3 + b"tail")
    assert fingerprint(path, chunk=16) == "c79c81ce0e54fdd56549d9788f98fbf6dea85e315fa59c5d1fab303433b9724e"
    assert fingerprint(path) == "92c5de5adda0b4dff34a8c497dc0b6b1c7d7be706769384b5b54cdcba1f59561"


def test_the_key_changes_with_anything_the_result_depends_on():
    base = analysis_key("v" * 64, "clip", "p" * 64, INPUTS)
    assert base == analysis_key("v" * 64, "clip", "p" * 64, dict(INPUTS))
    for changed in (analysis_key("w" * 64, "clip", "p" * 64, INPUTS), analysis_key("v" * 64, "clip2", "p" * 64, INPUTS),
                    analysis_key("v" * 64, "clip", "q" * 64, INPUTS),
                    analysis_key("v" * 64, "clip", "p" * 64, {**INPUTS, "detector_sha256": "e" * 64})):
        assert changed != base
    assert workbench.KEY.fullmatch(base)


def test_progress_lines_are_read_and_everything_else_is_not():
    assert progress_line("PROGRESS 10.0 3600.0\n") == (10.0, 3600.0)
    for other in ("  1.0 of 60.0 min", "PROGRESS ten 3600", "note: PROGRESS 1 2", ""):
        assert progress_line(other) is None


def test_the_tool_writes_the_progress_line_the_workbench_reads():
    pytest.importorskip("cv2")
    from scripts.analyze_video import progress_line as written

    assert progress_line(written(12.0, 3599.5)) == (12.0, 3599.5)


def test_a_path_is_cut_to_its_file_name():
    text = redact(r"no such video: D:\secret\footage\clip.mp4 and /home/me/secret/x.json")
    assert "secret" not in text and "clip.mp4" in text and "x.json" in text


@pytest.mark.parametrize("change, reason", [
    ({"kind": "other"}, "not a schema 2"), ({"schema": 1}, "not a schema 2"),
    ({"camera": "150th_Newport"}, "different camera"), ({"clip": "other"}, "different camera or clip"),
    ({"samples": []}, "no samples"), ({"samples": [{"t": 0}] * 100}, "holds 100 samples")])
def test_a_result_that_is_not_the_one_asked_for_is_refused(tmp_path, change, reason):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({**result_for("clip"), **change}), encoding="utf-8")
    assert reason in validate_result(path, camera="150th_Eastgate", clip="clip", duration_s=300.0)


def test_a_result_that_matches_passes(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(result_for("clip", samples=149)), encoding="utf-8")
    assert validate_result(path, camera="150th_Eastgate", clip="clip", duration_s=300.0) is None
    assert "not JSON" in validate_result(tmp_path / "none.json", camera="x", clip="y", duration_s=1.0)


@needs_profile
def test_the_preflight_refuses_with_a_reason_and_writes_nothing(tmp_path):
    video = Recording(tmp_path / "Bellevue_150th_Eastgate__2017-09-10_19-08-25.mp4")
    checks, profile, length = preflight(video, PROFILE, probe=lambda _: (1280, 720), duration=lambda _: 240.0)
    by = {c.name: c for c in checks}
    assert by["Camera profile"].ok and by["Video can be read"].detail == "1280 × 720"
    assert by["Long enough"].ok is False and "at least 5 min" in by["Long enough"].detail
    checks, _, _ = preflight(video, PROFILE, probe=lambda _: None, duration=lambda _: 600.0)
    assert {c.name: c.ok for c in checks}["Video can be read"] is False
    checks, _, _ = preflight(video, tmp_path / "missing.json", probe=lambda _: (1, 1), duration=lambda _: 600.0)
    assert {c.name: c.ok for c in checks}["Camera profile"] is False
    assert "missing.json" in checks[0].detail and str(tmp_path) not in checks[0].detail
    assert list(tmp_path.iterdir()) == []


@needs_profile
def test_the_calibration_hour_is_noted_not_refused(tmp_path):
    hour = load_profile(PROFILE).calibrated_on
    video = Recording(tmp_path / f"Bellevue_150th_Eastgate__{hour}.mp4")
    checks, _, _ = preflight(video, PROFILE, probe=lambda _: (1, 1), duration=lambda _: 600.0)
    assert {c.name: c.ok for c in checks}.get("Calibration hour", "absent") is None


# ------------------------------------------------------- finding the file ---

def test_a_file_is_found_by_name_size_and_fingerprint_and_by_nothing_less(tmp_path):
    here, there = tmp_path / "here", tmp_path / "there" / "deep"
    here.mkdir()
    there.mkdir(parents=True)
    real = there / "Clip.MP4"
    real.write_bytes(b"r" * 3000)
    (here / "clip.mp4").write_bytes(b"x" * 3000)           # same name and size, other bytes
    locator = Locator([here, tmp_path / "there"], standard=False)
    found, complete = locator.find("clip.mp4", 3000, fingerprint(real))
    assert found == real.resolve() and complete
    assert locator.find("clip.mp4", 2999, fingerprint(real)) == (None, True)
    assert Locator([here], standard=False).find("clip.mp4", 3000, fingerprint(real)) == (None, True)


def test_a_search_that_runs_out_of_time_says_so(tmp_path):
    (tmp_path / "a").mkdir()
    ticks = iter([0.0, 100.0, 100.0, 100.0])
    found, complete = Locator([tmp_path], standard=False).find("x.mp4", 1, "0" * 64, budget_s=1.0,
                                                               clock=lambda: next(ticks))
    assert found is None and not complete


def test_a_folder_shown_once_is_remembered_and_searched_first(tmp_path):
    memory = tmp_path / "folders.json"
    shown = tmp_path / "shown"
    shown.mkdir()
    Locator([], memory, standard=False).remember(shown)
    assert Locator([], memory, standard=False).folders() == [shown.resolve()]


@needs_profile
def test_locate_turns_a_found_file_into_a_number_and_sends_no_path(videos, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    video = elsewhere / "new.mp4"
    video.write_bytes(b"n" * 4000)
    jobs = make(videos, tmp_path, Tool(), locator=Locator([elsewhere], standard=False))
    assert jobs.locate("b_clip.mp4", (videos / "b_clip.mp4").stat().st_size,
                       fingerprint(videos / "b_clip.mp4")) == {"found": True, "recording": 2}
    answer = jobs.locate("new.mp4", 4000, fingerprint(video))
    assert answer == {"found": True, "recording": 4} and jobs.recordings[3].path == video.resolve()
    assert jobs.locate("new.mp4", 4000, fingerprint(video)) == answer
    assert jobs.locate("gone.mp4", 1, "0" * 64) == {"found": False, "searched_everything": True}
    for bad in (("../x.mp4", 1, "0" * 64), ("x.mp4", 0, "0" * 64), ("x.mp4", True, "0" * 64), ("x.mp4", 1, "short")):
        with pytest.raises(workbench.Refused):
            jobs.locate(*bad)


# ---------------------------------------------------------------- cameras ---

def test_levels_follow_adr_017s_rule_and_refuse_a_flat_recording():
    rows = result_for("c", samples=300)["samples"]
    low, med = calibration_limits(rows, ["lane_0", "lane_1"])
    assert 0 <= low < med
    flat = [{"counts": {"lane_0": 2, "lane_1": 2}} for _ in range(300)]
    with pytest.raises(ValueError, match="barely varies"):
        calibration_limits(flat, ["lane_0", "lane_1"])
    with pytest.raises(ValueError, match="too short"):
        calibration_limits(rows[:80], ["lane_0", "lane_1"])


@needs_profile
def test_a_new_camera_is_provisional_says_so_and_stays_out_of_the_committed_folder(tmp_path):
    cameras = Cameras([load_profile(PROFILE)], tmp_path / "cams")
    made = cameras.create("Gate_2", LANES, 0.2, "x.mp4")
    assert made.camera_id == "Gate_2" and made.lane_map == {"lane_0": "N", "lane_1": "S"}
    assert cameras.is_provisional(made) and cameras.needs_levels(made)
    assert any("Provisional" in line for line in made.limitations)
    assert not (ROOT / "cameras" / "Gate_2.json").exists()
    listed = {c["id"]: c for c in cameras.listing()}
    assert listed["Gate_2"]["provisional"] and not listed["Gate_2"]["levels_set"]
    assert not listed["150th_Eastgate"]["provisional"] and listed["150th_Eastgate"]["levels_set"]


@needs_profile
@pytest.mark.parametrize("camera_id, lanes, reach, says", [
    ("bad name!", LANES, 0.2, "1 to 32"), ("x" * 33, LANES, 0.2, "1 to 32"), ("Gate", [], 0.2, "one to four"),
    ("Gate", LANES * 3, 0.2, "one to four"), ("Gate", [{"centre": [1.2, 0], "approach": "N"}], 0.2, "inside the picture"),
    ("Gate", [{"centre": [0.1, 0.1], "approach": "Q"}], 0.2, "N, S, E or W"),
    ("Gate", [LANES[0], {**LANES[1], "approach": "N"}], 0.2, "share an approach"), ("Gate", LANES, 0.9, "between"),
    ("150th_eastgate", LANES, 0.2, "exists")])
def test_a_new_camera_is_refused_rather_than_repaired(tmp_path, camera_id, lanes, reach, says):
    cameras = Cameras([load_profile(PROFILE)], tmp_path / "cams")
    with pytest.raises(workbench.Refused, match=says):
        cameras.create(camera_id, lanes, reach, "x.mp4")


@needs_profile
def test_a_new_cameras_first_analysis_sets_its_levels_and_reclasses_from_the_counts(videos, tmp_path):
    tool = Tool(samples=150)
    tool.go.set()
    jobs = make(videos, tmp_path, tool)
    jobs.cameras.create("Gate_2", LANES, 0.2, "b_clip.mp4")
    jobs.start(2, "Gate_2")
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert s["problem"] is None and [st["id"] for st in s["stages"]] == ["check", "analyse", "levels", "validate", "open"]
    profile = jobs.cameras.get("Gate_2")
    assert not jobs.cameras.needs_levels(profile)
    result = json.loads(jobs.result_path(s["key"]).read_text(encoding="utf-8"))
    low, med = calibration_limits(result["samples"], ["lane_0", "lane_1"])
    assert result["limits"] == {"low": low, "med": med}
    assert any(row["level"] for row in result["samples"]) and result["samples"][29]["level"] is not None
    assert result["samples"][0]["level"] is None
    assert any("set from the first recording" in line for line in result["known_limits"])
    # A second recording keeps the levels the first one set.
    jobs.start(1, "Gate_2")
    assert wait_for(lambda: not jobs.running())
    assert [st["id"] for st in jobs.snapshot()["stages"]] == ["check", "analyse", "validate", "open"]


@needs_profile
def test_a_flat_first_recording_leaves_the_camera_without_levels(videos, tmp_path):
    class Flat(Tool):
        def __call__(self, video, profile, out, on_progress, stopping):
            result = result_for(video.stem, "Gate_2")
            for row in result["samples"]:
                row["counts"] = {"lane_0": 1, "lane_1": 1}
            out.write_text(json.dumps(result), encoding="utf-8")
            return 0, []

    jobs = make(videos, tmp_path, Flat())
    jobs.cameras.create("Gate_2", LANES, 0.2, "b_clip.mp4")
    jobs.start(2, "Gate_2")
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert {st["id"]: st["state"] for st in s["stages"]}["levels"] == "failed" and "barely varies" in s["problem"]
    assert jobs.cameras.needs_levels(jobs.cameras.get("Gate_2"))
    assert not list((tmp_path / "results").glob("*.json"))


# ---------------------------------------------------------------- the jobs ---

@needs_profile
def test_a_job_runs_the_stages_in_order_and_stores_by_key(videos, tmp_path):
    tool = Tool()
    jobs = make(videos, tmp_path, tool)
    jobs.start(2, "150th_Eastgate")
    assert wait_for(lambda: jobs.snapshot()["stages"][1]["state"] == "running" and jobs.snapshot()["progress"])
    s = jobs.snapshot()
    assert [st["state"] for st in s["stages"]] == ["done", "running", "waiting", "waiting"]
    assert s["progress"]["total"] == 150 and s["key"] is None and s["recording"] == "b_clip.mp4"
    tool.go.set()
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert [st["state"] for st in s["stages"]] == ["done"] * 4 and s["problem"] is None
    assert s["progress"] == {"done": 150, "total": 150, "eta_s": None}
    assert jobs.result_path(s["key"]) == tmp_path / "results" / f"{s['key']}.json"
    assert not list((tmp_path / "results").glob("*.partial.json"))
    assert str(tmp_path) not in json.dumps(s)


@needs_profile
def test_the_same_recording_and_camera_reopen_without_running_again(videos, tmp_path):
    tool = Tool()
    tool.go.set()
    jobs = make(videos, tmp_path, tool)
    jobs.start(2, "150th_Eastgate")
    assert wait_for(lambda: not jobs.running())
    first = jobs.snapshot()["key"]
    jobs.start(2, "150th_Eastgate")
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert len(tool.calls) == 1 and s["cached"] and s["key"] == first
    assert s["status"] == "Analysed before: ready at once"


@needs_profile
@pytest.mark.parametrize("tool, stage, says", [
    (Tool(code=1, write=False, last=r"profile refused: D:\secret\cameras\x.json"), "analyse", "exited with 1"),
    (Tool(samples=10), "validate", "holds 10 samples")])
def test_a_failure_says_which_stage_and_why_and_stores_nothing(videos, tmp_path, tool, stage, says):
    tool.go.set()
    jobs = make(videos, tmp_path, tool)
    jobs.start(1, "150th_Eastgate")
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert {st["id"]: st["state"] for st in s["stages"]}[stage] == "failed"
    assert says in s["problem"] and "secret" not in s["problem"] and s["key"] is None
    assert not list((tmp_path / "results").glob("*.json"))


@needs_profile
def test_a_refused_preflight_never_starts_the_tool(videos, tmp_path):
    tool = Tool()

    def short(recording, profile_path):
        return [Check("Long enough", False, "4.0 min. It needs at least 5 min")], load_profile(profile_path), 240.0

    jobs = make(videos, tmp_path, tool, check=short)
    jobs.start(1, "150th_Eastgate")
    assert wait_for(lambda: not jobs.running())
    s = jobs.snapshot()
    assert tool.calls == [] and s["stages"][0]["state"] == "failed" and "at least 5 min" in s["problem"]
    assert s["checks"] == [{"name": "Long enough", "ok": False, "detail": "4.0 min. It needs at least 5 min"}]


@needs_profile
def test_stop_ends_the_tool_and_leaves_nothing_behind(videos, tmp_path):
    tool = Tool()
    jobs = make(videos, tmp_path, tool)
    jobs.start(1, "150th_Eastgate")
    assert wait_for(lambda: jobs.snapshot()["progress"] is not None)
    jobs.stop(wait_s=5)
    s = jobs.snapshot()
    assert s["status"] == "Stopped" and not jobs.running()
    assert not list((tmp_path / "results").glob("*.json"))


@needs_profile
def test_the_time_left_is_shown_only_once_it_is_measured(videos, tmp_path):
    now = {"t": 0.0}
    jobs = Analyses(catalogue([videos]), Cameras([load_profile(PROFILE)], tmp_path / "c"), tmp_path,
                    inputs=lambda: INPUTS, clock=lambda: now["t"])
    jobs._progress(0.0, 300.0)
    now["t"] = 5.0
    jobs._progress(10.0, 300.0)
    assert jobs.snapshot()["progress"]["eta_s"] is None
    now["t"] = 20.0
    jobs._progress(40.0, 300.0)       # 20 samples in 20 s, 129 to go
    assert jobs.snapshot()["progress"] == {"done": 21, "total": 150, "eta_s": 129}


@needs_profile
@pytest.mark.parametrize("recording, camera", [(0, "150th_Eastgate"), (4, "150th_Eastgate"), (1, "nope"), (1, 1),
                                               ("1", "150th_Eastgate"), (True, "150th_Eastgate"), (None, None)])
def test_only_a_listed_recording_and_camera_start_a_job(videos, tmp_path, recording, camera):
    jobs = make(videos, tmp_path, Tool())
    with pytest.raises(workbench.Refused):
        jobs.start(recording, camera)
    assert not jobs.running()


# ------------------------------------------------------------- over HTTP ---

class Upstream(BaseHTTPRequestHandler):
    """Stands in for a replay's server."""

    def do_GET(self):
        body = json.dumps({"from": "replay", "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


@pytest.fixture
def site(videos, tmp_path):
    tool = Tool()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    jobs = make(videos, tmp_path, tool, locator=Locator([], tmp_path / "folders.json", standard=False))
    clips = [Clip(videos / "b_clip.mp4", "150th_Eastgate"), Clip(Path(f"D:/x/{REHEARSED}.mp4"), "150th_Eastgate")]
    jobs.replay = {clips[0].path.resolve(): 1}
    runs = []

    def runner(clip, report, stopping, **options):
        runs.append((clip, options))
        stopping.wait(5)
        return 130

    launcher = Launcher(clips, runner, minutes=7, dashboard_url="http://127.0.0.1:18080/dashboard/?id=live")
    launcher.runs = runs
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "outside.js").write_text("secret", encoding="utf-8")
    replay = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=replay.serve_forever, daemon=True).start()
    holder = {"upstream": None, "dialog": None, "dialogs": 0}

    def dialog():
        holder["dialogs"] += 1
        return holder["dialog"]

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        launcher, lambda: holder["port"], jobs, dist, lambda: holder["upstream"], dialog))
    holder["port"] = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", holder["port"], timeout=5)
        sent = {"Host": f"127.0.0.1:{holder['port']}"}
        if body is not None:
            sent["Content-Type"] = "application/json"
        sent.update(headers or {})
        c.request(method, path, json.dumps(body) if body is not None else None, sent)
        r = c.getresponse()
        return r.status, r.read(), dict(r.getheaders())

    yield call, tool, jobs, launcher, holder, replay.server_address[1], elsewhere
    tool.go.set()
    launcher.stop(wait_s=5)
    jobs.stop(wait_s=5)
    for s in (server, replay):
        s.shutdown()
        s.server_close()


@needs_profile
def test_the_address_opens_the_dashboard_and_there_is_no_second_page(site):
    call, *_ = site
    status, _, headers = call("GET", "/")
    assert status == 302 and headers["Location"] == "/dashboard/?id=live#analyze"
    assert json.loads(call("GET", "/workbench/capabilities")[1])["workbench"] is True


@needs_profile
def test_the_lists_carry_numbers_names_and_camera_ids_and_never_a_path(site):
    call, *_ = site
    status, raw, _ = call("GET", "/workbench/recordings")
    lists = json.loads(raw)
    assert status == 200 and b"secret" not in raw and b"footage" not in raw
    assert [r["name"] for r in lists["recordings"]] == ["a_clip.MOV", "b_clip.mp4", "c_clip.mkv"]
    assert [r["replay"] for r in lists["recordings"]] == [None, 1, None]
    assert json.loads(call("GET", "/workbench/cameras")[1])[0]["id"] == "150th_Eastgate"


@needs_profile
def test_a_job_started_over_http_is_followed_and_its_results_read_by_key(site):
    call, tool, jobs, *_ = site
    tool.go.set()
    assert call("POST", "/workbench/jobs", {"recording": 2, "camera": "150th_Eastgate"})[0] == 202
    assert wait_for(lambda: not jobs.running())
    key = json.loads(call("GET", "/workbench/jobs/current")[1])["key"]
    status, raw, headers = call("GET", f"/workbench/analysis/{key}")
    assert status == 200 and json.loads(raw)["clip"] == "b_clip" and headers["Content-Type"] == "application/json"
    for bad in (f"/workbench/analysis/{'0' * 64}", "/workbench/analysis/..%2F..%2Fx", f"/workbench/analysis/{key}.json",
                "/workbench/video/1", "/video/1"):
        assert call("GET", bad)[0] == 404


@needs_profile
def test_a_folder_is_asked_for_through_this_computers_window_and_only_its_name_returns(site):
    call, _, jobs, _, holder, _, elsewhere = site
    video = elsewhere / "far.mp4"
    video.write_bytes(b"f" * 2000)
    ask = {"name": "far.mp4", "size": 2000, "fingerprint": fingerprint(video)}
    assert json.loads(call("POST", "/workbench/locate", ask)[1]) == {"found": False, "searched_everything": True}
    holder["dialog"] = None
    assert json.loads(call("POST", "/workbench/folder", {})[1]) == {"added": None}
    holder["dialog"] = elsewhere
    status, raw, _ = call("POST", "/workbench/folder", {})
    assert status == 200 and json.loads(raw) == {"added": "elsewhere"} and str(elsewhere.parent).encode() not in raw
    assert json.loads(call("POST", "/workbench/locate", ask)[1]) == {"found": True, "recording": 4}
    assert holder["dialogs"] == 2


@needs_profile
def test_a_new_camera_is_saved_from_numbers_and_listed_as_provisional(site):
    call, *_ = site
    status, raw, _ = call("POST", "/workbench/cameras", {"id": "Gate_2", "lanes": LANES, "max_radius": 0.2, "recording": 2})
    assert status == 201 and json.loads(raw) == {"id": "Gate_2"}
    listed = {c["id"]: c for c in json.loads(call("GET", "/workbench/cameras")[1])}
    assert listed["Gate_2"]["provisional"] and not listed["Gate_2"]["levels_set"]
    assert call("POST", "/workbench/cameras", {"id": "Gate_2", "lanes": LANES, "max_radius": 0.2, "recording": 2})[0] == 409
    assert call("POST", "/workbench/cameras", {"id": "Gate_3", "lanes": LANES, "max_radius": 0.2, "recording": 9})[0] == 400


@needs_profile
def test_the_live_panels_read_the_replays_server_while_one_runs_and_nothing_else(site):
    call, _, _, _, holder, replay_port, _ = site
    assert call("GET", "/prediction/live/latest")[0] == 404
    assert json.loads(call("GET", "/health")[1])["status"] == "ok"
    holder["upstream"] = replay_port
    status, raw, _ = call("GET", "/prediction/live/latest")
    assert status == 200 and json.loads(raw) == {"from": "replay", "path": "/prediction/live/latest"}
    assert json.loads(call("GET", "/vehicle_count/live/history?window=1h")[1])["path"].endswith("window=1h")
    for not_passed in ("/observation", "/prediction/live", "/vehicle_count/live/history?window=2h", "/docs"):
        assert call("GET", not_passed)[0] == 404, not_passed


def test_only_the_dashboards_read_endpoints_are_passed_through():
    """The same list as dashboard/src/api.js ALLOWED, minus the workbench's own read."""
    allowed = (ROOT / "dashboard" / "src" / "api.js").read_text(encoding="utf-8").split("ALLOWED = [", 1)[1].split("];", 1)[0]
    patterns = [line.strip() for line in allowed.splitlines() if line.strip().startswith("/^")]
    assert len(patterns) == len(SERVER_GETS) + 1
    for path in ("/count_forecast/a/latest", "/prediction/a/history", "/vehicle_count/a/history?window=6h",
                 "/vehicle_count/a/latest", "/heartbeat/a/latest", "/forecast_check/a/recent", "/sites", "/evidence",
                 "/health"):
        assert any(p.match(path) for p in SERVER_GETS), path
    for path in ("/observation", "/signal/command", "/prediction/a", "/workbench/jobs"):
        assert not any(p.match(path) for p in SERVER_GETS), path


@needs_profile
def test_the_built_dashboard_is_served_and_nothing_outside_it(site):
    call, *_ = site
    status, raw, headers = call("GET", f"/dashboard/?analysis={'a' * 64}")
    assert status == 200 and b"root" in raw and headers["Content-Type"].startswith("text/html")
    assert call("GET", "/dashboard/assets/app.js")[2]["Content-Type"].startswith("text/javascript")
    assert call("GET", "/dashboard")[0] == 301
    for bad in ("/dashboard/../outside.js", "/dashboard/%2e%2e/outside.js", "/dashboard/assets/../../outside.js",
                "/dashboard/missing.js"):
        assert call("GET", bad)[0] == 404, bad


def test_static_files_stay_under_the_build(tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("x", encoding="utf-8")
    (tmp_path / "secret.html").write_text("no", encoding="utf-8")
    assert static_file(tmp_path / "dist", "/dashboard/")[0] == b"x"
    assert static_file(tmp_path / "dist", "/dashboard/../secret.html") is None
    assert static_file(tmp_path / "dist", "/dashboard/%2E%2E/secret.html") is None


@needs_profile
def test_analysis_and_replay_take_turns_on_the_gpu(site):
    call, tool, jobs, launcher, *_ = site
    assert call("POST", "/workbench/replay/start", {"clip": 1})[0] == 202
    status, raw, _ = call("POST", "/workbench/jobs", {"recording": 1, "camera": "150th_Eastgate"})
    assert status == 409 and b"replay is running" in raw
    launcher.stop(wait_s=5)
    assert call("POST", "/workbench/jobs", {"recording": 1, "camera": "150th_Eastgate"})[0] == 202
    status, raw, _ = call("POST", "/workbench/replay/start", {"clip": 1})
    assert status == 409 and b"analysis is running" in raw


@needs_profile
@pytest.mark.parametrize("headers", [{"Host": "evil.example:80"}, {"Origin": "http://evil.example"}])
def test_another_site_can_neither_start_work_nor_read_anything(site, headers):
    call, tool, jobs, _, holder, *_ = site
    assert call("POST", "/workbench/jobs", {"recording": 1, "camera": "150th_Eastgate"}, headers)[0] == 403
    assert call("POST", "/workbench/folder", {}, headers)[0] == 403
    assert call("POST", "/workbench/cameras", {"id": "X", "lanes": LANES, "max_radius": 0.2, "recording": 1}, headers)[0] == 403
    assert call("GET", "/workbench/recordings", None, headers)[0] == 403
    assert call("GET", f"/workbench/analysis/{'a' * 64}", None, headers)[0] == 403
    assert not jobs.running() and holder["dialogs"] == 0


@needs_profile
def test_a_get_never_starts_anything(site):
    call, tool, jobs, _, holder, *_ = site
    for path in ("/workbench/jobs?recording=1&camera=150th_Eastgate", "/workbench/folder", "/workbench/replay/start"):
        call("GET", path)
    assert not jobs.running() and tool.calls == [] and holder["dialogs"] == 0


# ------------------------------------------------- D42: any recording, the camera ---

@needs_profile
def test_any_found_recording_replays_for_the_length_chosen_with_its_declared_camera(site):
    call, _, jobs, launcher, *_ = site
    status, raw, _ = call("POST", "/workbench/replay/start", {"recording": 3, "camera": "150th_Eastgate", "minutes": 30})
    assert status == 202, raw
    assert wait_for(lambda: launcher.runs)
    clip, options = launcher.runs[-1]
    assert clip.path == jobs.recordings[2].path and clip.camera == "150th_Eastgate" and clip.profile == PROFILE.resolve()
    assert options == {"minutes": 30.0}
    state = json.loads(call("GET", "/workbench/replay/state")[1])
    assert state["kind"] == "replay" and state["minutes"] == 30.0 and state["clip"] == "c_clip"
    launcher.stop(wait_s=5)


@needs_profile
@pytest.mark.parametrize("body, status", [
    ({"recording": 3, "camera": "150th_Eastgate", "minutes": 2}, 400),
    ({"recording": 3, "camera": "150th_Eastgate", "minutes": 999}, 400),
    ({"recording": 3, "camera": "150th_Eastgate", "minutes": "7"}, 400),
    ({"recording": 9, "camera": "150th_Eastgate", "minutes": 7}, 400),
    ({"recording": 3, "camera": "nope", "minutes": 7}, 400)])
def test_a_replay_of_a_recording_is_refused_rather_than_guessed(site, body, status):
    call, _, _, launcher, *_ = site
    assert call("POST", "/workbench/replay/start", body)[0] == status
    assert not launcher.runs


@needs_profile
def test_a_camera_without_levels_cannot_replay_until_its_first_analysis(site):
    call, _, jobs, launcher, *_ = site
    jobs.cameras.create("Gate_2", LANES, 0.2, "x.mp4")
    status, raw, _ = call("POST", "/workbench/replay/start", {"recording": 1, "camera": "Gate_2", "minutes": 7})
    assert status == 409 and b"levels are not set" in raw and not launcher.runs


@needs_profile
def test_the_camera_cannot_start_unless_this_computer_was_given_one(site):
    call, _, _, launcher, *_ = site
    assert json.loads(call("GET", "/workbench/capabilities")[1])["camera_configured"] is False
    status, raw, _ = call("POST", "/workbench/camera/start", {"camera": "150th_Eastgate"})
    assert status == 409 and b"STMS_CAMERA_URL" in raw and not launcher.runs


@needs_profile
def test_a_configured_camera_runs_as_a_camera_and_says_so(site):
    call, _, _, launcher, *_ = site
    launcher.camera_configured = True
    assert call("POST", "/workbench/camera/start", {"camera": "150th_Eastgate"})[0] == 202
    assert wait_for(lambda: launcher.runs)
    clip, options = launcher.runs[-1]
    assert str(clip.path) == "camera" and clip.camera == "150th_Eastgate" and options == {}
    state = json.loads(call("GET", "/workbench/replay/state")[1])
    assert state["kind"] == "camera" and state["clip"] == "live camera" and state["minutes"] is None
    assert state["milestones"][0]["name"] == "the edge reports the live camera"
    assert b"rtsp" not in call("GET", "/workbench/replay/state")[1]
    launcher.stop(wait_s=5)


def test_the_stack_runs_a_camera_unpaced_and_unbounded_and_a_clip_paced_and_bounded(tmp_path):
    from types import SimpleNamespace

    from scripts.demo_e2e import Stack
    from scripts.demo_live import source_kind

    started = {}

    class Recording(Stack):
        def env(self, name):
            return {}

        def start(self, name, argv, env=None):
            started[name] = argv

    for clip, samples in (("camera", None), (str(tmp_path / "x.mp4"), 90)):
        args = SimpleNamespace(clip=clip, profile=PROFILE, mqtt_port=1883, http_port=18000, camera="150th_Eastgate")
        Recording(args, tmp_path).start_edge("live", samples)
        argv = started["edge"]
        assert argv[argv.index("--source") + 1] == clip
        if clip == "camera":
            assert "--realtime" not in argv and "--samples" not in argv and source_kind(args) == "camera"
        else:
            assert "--realtime" in argv and argv[argv.index("--samples") + 1] == "90" and source_kind(args) == "replay"
