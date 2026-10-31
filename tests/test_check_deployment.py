"""scripts/check_deployment.py: what it says is as strong as what it did (D30)."""

from __future__ import annotations

import importlib.metadata
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import check_deployment as cd  # noqa: E402
from scripts.check_deployment import (FAIL, INVALID, MISSING, NOT_CHECKED, PASS, UNREACHABLE, WARN, Check,  # noqa: E402
                                      render, result_of)

SECRET_URL = "rtsp://operator:hunter2@10.0.0.9/stream"


def statuses(checks):
    return [c.status for c in checks]


# --------------------------------------------------------------- the result line --

def test_a_failure_blocks_and_nothing_else_does():
    ok, warn, none = Check("a", PASS, "x"), Check("a", WARN, "x"), Check("a", NOT_CHECKED, "x")
    bad = Check("a", FAIL, "x", MISSING)
    assert result_of([ok, warn, none]).startswith("READY")
    assert result_of([ok, bad]).startswith("BLOCKED")


def test_the_result_counts_what_was_not_checked_so_ready_cannot_hide_it():
    line = result_of([Check("a", PASS, "x"), Check("a", NOT_CHECKED, "y")])
    assert line == "READY: 1 passed, 0 warnings, 0 failed, 1 not checked"


def test_the_report_says_ready_is_not_proof_and_names_the_kind_and_the_remedy():
    text = render([Check("detector", FAIL, "weights not found", MISSING, "restore them")])
    assert "[FAIL] missing: weights not found" in text and "-> restore them" in text
    for needed in ("does not show the system working", "S67", "S65"):
        assert needed in text


def test_the_exit_status_follows_the_result(monkeypatch, capsys):
    monkeypatch.setattr(cd, "installation", lambda a: [Check("a", WARN, "x")])
    assert cd.main([]) == 0
    monkeypatch.setattr(cd, "installation", lambda a: [Check("a", FAIL, "x", MISSING)])
    assert cd.main([]) == 1
    capsys.readouterr()
    assert cd.main(["--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["result"].startswith("BLOCKED") and data["checks"][0]["kind"] == MISSING


@pytest.mark.parametrize("partial", [["--source", "x.mp4"], ["--camera", "c"], ["--approaches", "a=N"],
                                     ["--source", "x.mp4", "--camera", "c"]])
def test_half_a_combination_is_refused_not_guessed(partial, capsys):
    with pytest.raises(SystemExit) as stop:
        cd.main(partial)
    assert stop.value.code == 2 and "go together" in capsys.readouterr().err


# ------------------------------------------------------------------ the runtime --

def test_python_other_than_the_supported_version_warns():
    assert cd.check_python((3, 12, 1)).status == PASS
    assert cd.check_python((3, 14, 4)).status == WARN


def test_packages_tell_missing_broken_and_off_pin_apart():
    def version_of(package):
        if package == "fastapi":
            raise importlib.metadata.PackageNotFoundError
        return "9.9" if package == "pydantic" else "1.0"

    def importer(module):
        if module == "cv2":
            raise OSError("[WinError 1114] a DLL failed")     # what a broken install really raises

    checks = {c.what.split()[0]: c for c in cd.check_packages({"pydantic": "2.0"}, version_of, importer)}
    assert (checks["fastapi"].status, checks["fastapi"].kind) == (FAIL, MISSING)
    assert (checks["opencv-python-headless"].status, checks["opencv-python-headless"].kind) == (FAIL, INVALID)
    assert checks["pydantic"].status == WARN and "pins 2.0" in checks["pydantic"].what
    assert checks["uvicorn"].status == PASS


def test_a_broken_torch_is_reported_not_raised(monkeypatch):
    real = __import__

    def fake(name, *args, **kwargs):
        if name == "torch":
            raise OSError("[WinError 1114]")
        return real(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake)
    check = cd.check_compute()
    assert (check.status, check.kind) == (FAIL, INVALID)


def test_no_gpu_warns_that_the_step_is_unmeasured_and_does_not_block():
    assert cd.check_compute(True).status == PASS
    check = cd.check_compute(False)
    assert check.status == WARN and "unmeasured" in check.what


# ----------------------------------------------------- evidence of different weight

def settings_for(path):
    return lambda: (path, 0.25, 992)


def test_a_file_that_exists_is_weaker_than_a_model_that_loaded(tmp_path):
    weights = tmp_path / "w.pt"
    assert statuses(cd.check_detector(False, settings=settings_for(weights)))[-1] == FAIL
    weights.write_bytes(b"not a model")

    def corrupt(_):
        raise RuntimeError("bad pickle")

    last = cd.check_detector(False, load=corrupt, settings=settings_for(weights))[-1]
    assert (last.status, last.kind) == (FAIL, INVALID) and "exist" in last.what     # exists, and does not load
    assert cd.check_detector(False, load=lambda _: 34, settings=settings_for(weights))[-1].what == "weights load, 34 classes"


def test_quick_says_not_checked_and_never_passes_what_it_skipped(tmp_path):
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"")

    def must_not_load(_):
        raise AssertionError("--quick must not load the detector")

    assert cd.check_detector(True, load=must_not_load, settings=settings_for(weights))[-1].status == NOT_CHECKED
    args = SimpleNamespace(source=str(weights), quick=True)
    assert cd.check_source(args, reader=lambda s: pytest.fail("must not decode"))[0].status == NOT_CHECKED


def test_settings_that_cannot_be_read_are_invalid_not_a_crash():
    def broken():
        raise ValueError("the counting block has no imgsz")

    check = cd.check_detector(False, settings=broken)[0]
    assert (check.status, check.kind) == (FAIL, INVALID) and "imgsz" in check.what


# --------------------------------------------------------------------- the specs --

def test_a_ridge_spec_that_is_not_the_frozen_one_is_invalid(tmp_path):
    (tmp_path / "persistence_v1.json").write_text(json.dumps({"cameras": {"c": {}}}), encoding="utf-8")
    (tmp_path / "p105_ridge_v1.json").write_text("{}", encoding="utf-8")
    checks = cd.check_specs(tmp_path)
    assert checks[0].status == PASS and (checks[1].status, checks[1].kind) == (FAIL, INVALID)


def test_the_committed_specs_pass():
    assert statuses(cd.check_specs()) == [PASS, PASS]


def test_missing_and_unreadable_specs_are_told_apart(tmp_path):
    assert cd.check_specs(tmp_path)[0].kind == MISSING
    (tmp_path / "persistence_v1.json").write_text("not json", encoding="utf-8")
    assert cd.check_specs(tmp_path)[0].kind == INVALID


def test_a_camera_without_lanes_is_a_note_at_the_installation_level(tmp_path):
    (tmp_path / "persistence_v1.json").write_text(json.dumps({"cameras": {"a": {}, "b": {}}}), encoding="utf-8")
    corpus = tmp_path / "corpus"
    (corpus / "a").mkdir(parents=True)
    (corpus / "a" / "manifest.json").write_text("{}", encoding="utf-8")
    assert statuses(cd.check_cameras(tmp_path, corpus)) == [PASS, WARN]


# -------------------------------------------------------------------- the broker --

def test_a_missing_broker_says_how_to_fix_it(monkeypatch, tmp_path):
    monkeypatch.setattr(cd.shutil, "which", lambda _: None)
    assert cd.check_broker(None, False)[0].kind == MISSING
    assert cd.check_broker(tmp_path / "absent.exe", False)[0].kind == MISSING


def test_a_broker_that_exits_at_once_is_invalid(tmp_path):
    """A real child process that does not stay up."""
    if sys.platform == "win32":
        pytest.skip("needs a stand-in executable that exits; covered on the real broker by hand")
    exe = tmp_path / "mosquitto"
    exe.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    exe.chmod(0o755)
    (tmp_path / "mosquitto_passwd").write_text("", encoding="utf-8")
    assert cd.check_broker(exe, False)[-1].kind == INVALID


def test_quick_does_not_start_the_broker(tmp_path):
    exe = tmp_path / "mosquitto.exe"
    exe.write_bytes(b"")
    (tmp_path / "mosquitto_passwd.exe").write_bytes(b"")
    assert cd.check_broker(exe, True)[-1].status == NOT_CHECKED


def test_a_missing_passwd_tool_is_a_failure(tmp_path):
    exe = tmp_path / "mosquitto.exe"
    exe.write_bytes(b"")
    assert any(c.status == FAIL and "mosquitto_passwd" in c.what for c in cd.check_broker(exe, True))


def test_a_real_broker_when_one_is_available():
    exe = cd.os.environ.get("MOSQUITTO_EXE")
    if not exe:
        pytest.skip("set MOSQUITTO_EXE to test against a real Mosquitto")
    assert cd.check_broker(Path(exe), False)[-1].status == PASS


# ------------------------------------------------- dashboard, storage and ports ----

def test_the_dashboard_build_must_be_there_and_whole(tmp_path):
    assert cd.check_dashboard(tmp_path).kind == MISSING
    (tmp_path / "index.html").write_text('<script src="/dashboard/assets/a.js"></script>', encoding="utf-8")
    assert cd.check_dashboard(tmp_path).kind == INVALID            # refers to a file that is not there
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "a.js").write_text("", encoding="utf-8")
    assert cd.check_dashboard(tmp_path).status == PASS


def test_storage_says_writable_and_warns_when_short(tmp_path):
    checks = cd.check_storage(tmp_path / "server", free_of=lambda p: 5 * 1024 ** 3)
    assert statuses(checks) == [PASS, PASS]
    assert statuses(cd.check_storage(tmp_path / "server", free_of=lambda p: 1024))[-1] == WARN


def test_storage_that_cannot_be_written_is_invalid(tmp_path):
    a_file = tmp_path / "taken"
    a_file.write_text("", encoding="utf-8")
    check = cd.check_storage(a_file / "server")[0]
    assert (check.status, check.kind) == (FAIL, INVALID)


def test_a_held_port_fails_and_names_its_holder_and_a_free_one_passes():
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        check = cd.check_ports({"server": port})[0]
    assert check.status == FAIL and str(port) in check.what and "held by" in check.what
    assert cd.check_ports({"server": port})[0].status == PASS


# -------------------------------------------------------------------- one camera --

def camera_args(tmp_path, **over):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    lanes = tmp_path / "lanes.json"
    lanes.write_text(json.dumps({"reviewed": True, "max_radius": 0.25, "lanes": [
        {"name": "lane_0", "centre": [0.1, 0.5]}, {"name": "lane_1", "centre": [0.5, 0.2]},
        {"name": "lane_2", "centre": [0.8, 0.4]}]}), encoding="utf-8")
    values = dict(source=str(clip), camera="NE8th", lanes=lanes, intersection_id="check", quick=True,
                  approaches=["lane_0=W", "lane_1=N", "lane_2=E"])
    return SimpleNamespace(**{**values, **over})


@pytest.fixture
def edge_ready(monkeypatch):
    """The weights are not in CI; the edge's other rules are what is under test."""
    pytest.importorskip("yaml")
    pytest.importorskip("mfstnet")
    import edge.run as run

    original = run.load_counting
    monkeypatch.setattr(run, "load_counting", lambda p: (Path(__file__), 0.25, 992))
    return original


def test_the_edge_itself_decides_and_a_good_combination_builds_both_forecasters(tmp_path, edge_ready):
    accepted, settings = cd.check_edge_accepts(camera_args(tmp_path))
    assert accepted.status == PASS and settings.camera == "NE8th"
    assert statuses(cd.check_forecasters(settings)) == [PASS, PASS]


@pytest.mark.parametrize("over, words, kind", [
    (dict(camera="Nowhere"), "no thresholds", INVALID),
    (dict(approaches=["lane_0=W", "lane_1=N"]), "does not cover|covers", INVALID),
    (dict(approaches=["lane_0=W", "lane_1=W", "lane_2=E"]), "two lanes to one approach", INVALID),
    (dict(source="D:/nothing/here.mp4"), "no such video file", MISSING),
])
def test_a_bad_combination_is_refused_in_the_edges_own_words(tmp_path, edge_ready, over, words, kind):
    import re

    accepted, settings = cd.check_edge_accepts(camera_args(tmp_path, **over))
    assert settings is None and accepted.status == FAIL and accepted.kind == kind
    assert re.search(words, accepted.what) and accepted.what.startswith("the edge would refuse this")


def test_a_refusal_stops_the_later_camera_checks_and_says_so(tmp_path, edge_ready):
    checks = cd.selected(camera_args(tmp_path, camera="Nowhere"))
    assert checks[0].status == FAIL and checks[1].status == NOT_CHECKED


def test_a_port_bound_but_not_listening_is_held_though_a_connection_is_refused():
    """What a connect probe gets wrong: a real run reported a held port as free."""
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))                      # no listen(): connecting is refused
        port = held.getsockname()[1]
        with socket.socket() as attempt:
            attempt.settimeout(1.0)
            assert attempt.connect_ex(("127.0.0.1", port)) != 0
        assert cd.check_ports({"server": port})[0].status == FAIL


def test_a_refusal_lists_the_cameras_that_are_configured(tmp_path, edge_ready):
    accepted, _ = cd.check_edge_accepts(camera_args(tmp_path, camera="Nowhere"))
    assert "150th_Eastgate" in accepted.action and "calibration" in accepted.action


def test_no_lane_map_warning_when_the_edge_has_already_refused(tmp_path, edge_ready):
    checks = cd.selected(camera_args(tmp_path, camera="Nowhere"))
    assert not any("lane map" in c.what for c in checks)


def test_the_lane_map_is_never_passed_as_verified(tmp_path, edge_ready):
    checks = cd.selected(camera_args(tmp_path))
    note = [c for c in checks if "lane map" in c.what]
    assert len(note) == 1 and note[0].status == WARN and "as you declared" in note[0].what


def test_a_clip_from_the_calibration_hour_warns(tmp_path):
    spec = tmp_path / "persistence_v1.json"
    spec.write_text(json.dumps({"cameras": {"c": {"source": "P103 calibration hour, Sun 2017-09-10 18:08 (q33)"}}}), encoding="utf-8")
    assert cd.check_calibration_overlap("c", "Bellevue_c__2017-09-10_18-08-24.mp4", tmp_path)[0].status == WARN
    assert cd.check_calibration_overlap("c", "Bellevue_c__2017-09-11_10-08-31.mp4", tmp_path) == []


# --------------------------------------------------------------------- the source -

def clip_args(**over):
    return SimpleNamespace(**{**dict(source="clip.mp4", quick=False), **over})


@pytest.mark.parametrize("seconds, word", [(30, "a class forecast"), (90, "a count forecast"), (150, "a count comparison")])
def test_a_clip_too_short_says_what_it_cannot_show(seconds, word):
    checks = cd.check_source(clip_args(), reader=lambda s: (1280, 720, 30.0, seconds * 30.0))
    assert checks[-1].status == WARN and word in checks[-1].what


def test_a_long_enough_clip_passes_and_a_frame_is_dropped():
    checks = cd.check_source(clip_args(), reader=lambda s: (1280, 720, 30.0, 300 * 30.0))
    assert statuses(checks) == [PASS, PASS] and "and dropped" in checks[0].what


def test_a_clip_that_gives_no_frame_is_invalid():
    check = cd.check_source(clip_args(), reader=lambda s: None)[0]
    assert (check.status, check.kind) == (FAIL, INVALID)


def camera_source(monkeypatch, reader):
    monkeypatch.setenv("STMS_CAMERA_URL", SECRET_URL)
    return cd.check_source(clip_args(source="camera"), reader=reader)


def test_a_dead_stream_is_unreachable_and_its_url_is_never_printed(monkeypatch):
    checks = camera_source(monkeypatch, lambda s: None)
    assert (checks[0].status, checks[0].kind) == (FAIL, UNREACHABLE)
    assert "hunter2" not in render(checks) and SECRET_URL not in render(checks)


def test_a_stream_that_blocks_is_unreachable_not_a_hang(monkeypatch):
    def blocks(_):
        raise subprocess.TimeoutExpired("x", 20)

    check = camera_source(monkeypatch, blocks)[0]
    assert (check.status, check.kind) == (FAIL, UNREACHABLE) and "hunter2" not in check.what


def test_a_live_stream_passes_only_what_was_shown_and_leaves_timing_to_s65(monkeypatch):
    checks = camera_source(monkeypatch, lambda s: (1920, 1080, 25.0, 0.0))
    assert statuses(checks) == [PASS, NOT_CHECKED] and "S65" in checks[1].what
    assert "hunter2" not in render(checks)


def test_no_camera_url_is_missing(monkeypatch):
    monkeypatch.delenv("STMS_CAMERA_URL", raising=False)
    assert cd.check_source(clip_args(source="camera"))[0].kind == MISSING


def test_the_url_reaches_the_probe_through_the_environment_never_the_command_line(monkeypatch):
    seen = {}

    def fake_run(argv, env, **_):
        seen.update(argv=argv, env=env)
        return SimpleNamespace(returncode=3, stdout="")

    monkeypatch.setattr(cd.subprocess, "run", fake_run)
    assert cd.read_source(SECRET_URL) is None
    assert SECRET_URL not in " ".join(seen["argv"]) and seen["env"]["STMS_PROBE_SOURCE"] == SECRET_URL


def test_a_real_clip_is_decoded_when_opencv_is_here(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    path = tmp_path / "tiny.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (64, 48))
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    assert cd.read_source(str(path))[:2] == (64, 48)
    (tmp_path / "not_video.mp4").write_bytes(b"not a video")
    assert cd.read_source(str(tmp_path / "not_video.mp4")) is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["not_video.mp4", "tiny.avi"]     # no frame written
