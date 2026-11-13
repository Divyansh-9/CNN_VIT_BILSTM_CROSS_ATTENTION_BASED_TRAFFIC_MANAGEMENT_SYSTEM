"""Camera profiles: ADR-028's acceptance criteria, one test or more for each (D31)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contracts.mqtt import Heartbeat, Mode, Topic, decode  # noqa: E402
from edge.node import EdgeNode, RecordingTransport  # noqa: E402
from edge.profile import ProfileError, binding, canonical_hash, load_profile, load_profiles  # noqa: E402
from scripts.camera_profile import record_evidence  # noqa: E402

CAMERAS = ROOT / "cameras"
SPEC = {"cameras": {"cam_a": {"low": 1, "med": 2, "lanes": 2, "source": "calibration hour, Sun 2017-09-10 18:08"}}}
SECRET = "rtsp://operator:hunter2@10.0.0.9/stream"


def write_profile(tmp_path, **over):
    spec = tmp_path / "spec.json"
    spec.write_bytes(json.dumps(SPEC).encode())
    raw = {
        "schema_version": 1, "camera_id": "cam_a",
        "geometry": {"coordinates": "normalised_image", "max_radius": 0.25,
                     "lanes": [{"name": "lane_0", "centre": [0.2, 0.3]}, {"name": "lane_1", "centre": [0.7, 0.8]}]},
        "lane_map": {"lane_0": "N", "lane_1": "S"},
        "calibration": {"persistence_spec": "spec.json", "spec_sha256": hashlib.sha256(spec.read_bytes()).hexdigest(), "key": "cam_a"},
        "limitations": [], "provenance": {"placed_by": "x", "how": "y", "record": "z"},
        "direction": {"status": "declared"}, "evidence": [],
    }
    raw.update(over)
    path = tmp_path / "cam_a.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def load(path):
    return load_profile(path, path.parent)


# ----------------------------------------------------------------- validation ---

def test_a_good_profile_loads(tmp_path):
    p = load(write_profile(tmp_path))
    assert p.camera_id == "cam_a" and p.lane_map["lane_1"] == "S" and p.lanes[1] == ("lane_1", (0.7, 0.8))
    assert p.max_radius == 0.25 and p.calibrated_on == "2017-09-10_18-08"


def test_a_missing_profile_says_so(tmp_path):
    with pytest.raises(ProfileError, match="no profile at"):
        load(tmp_path / "cam_a.json")


@pytest.mark.parametrize("over, words", [
    (dict(schema_version=2), "schema_version"),
    (dict(camera_id="other"), "file's name"),
    (dict(camera_id="has space"), "short code"),
    (dict(lane_map={"lane_0": "N"}), "cover exactly"),
    (dict(lane_map={"lane_0": "N", "lane_1": "N"}), "distinct"),
    (dict(lane_map={"lane_0": "N", "lane_1": "Q"}), "distinct one of"),
    (dict(direction={"status": "probably"}), "direction.status"),
    (dict(limitations="not a list"), "limitations"),
    (dict(evidence=[{"kind": "vibes", "binds": "x"}]), "evidence"),
    (dict(geometry={"coordinates": "pixels", "max_radius": 0.25, "lanes": []}), "normalised_image"),
    (dict(geometry={"coordinates": "normalised_image", "max_radius": 0.25,
                    "lanes": [{"name": "lane_0", "centre": [2, 0.3]}, {"name": "lane_1", "centre": [0.7, 0.8]}]}), "within the image"),
])
def test_a_bad_profile_fails_with_a_specific_diagnostic(tmp_path, over, words):
    with pytest.raises(ProfileError, match=words):
        load(write_profile(tmp_path, **over))


def test_malformed_json_is_named_not_a_traceback(tmp_path):
    path = tmp_path / "cam_a.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="not readable JSON"):
        load(path)


# ------------------------------------------------------------- spec integrity ---

def test_a_missing_spec_is_rejected(tmp_path):
    path = write_profile(tmp_path)
    (tmp_path / "spec.json").unlink()
    with pytest.raises(ProfileError, match="not found"):
        load(path)


def test_a_changed_spec_is_rejected(tmp_path):
    path = write_profile(tmp_path)
    (tmp_path / "spec.json").write_bytes(b'{"cameras": {"cam_a": {"low": 9, "med": 10}}}')
    with pytest.raises(ProfileError, match="does not match its recorded hash"):
        load(path)


def test_a_spec_without_this_camera_is_rejected(tmp_path):
    spec = tmp_path / "spec.json"
    path = write_profile(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["calibration"]["key"] = "someone_else"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert spec.is_file()
    with pytest.raises(ProfileError, match="no thresholds for someone_else"):
        load(path)


def test_the_frozen_specs_are_what_the_committed_profiles_recorded():
    """Reproducibility: adding profiles changed no frozen spec, and no id moved."""
    good, bad = load_profiles(CAMERAS)
    assert bad == [] and {p.camera_id for p in good} == {"150th_Eastgate", "150th_Newport", "150th_SE38th"}
    from edge.persistence import load_spec

    for profile in good:
        assert load_spec(profile.spec_path)[1] == "persistence@2431c6641b9c"     # the id every forecast carries


# ------------------------------------------------------------- the deterministic hash

def test_equivalent_profiles_hash_alike():
    assert canonical_hash({"a": 1, "b": [1, 2]}) == canonical_hash({"b": [1, 2], "a": 1})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_reformatting_a_profile_does_not_void_its_evidence(tmp_path):
    path = write_profile(tmp_path)
    record_evidence(path, "direction", how="frame", by="me", date="2026-11-01", note="looked", root=tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(raw, indent=8, sort_keys=True), encoding="utf-8")
    assert load(path).directions_verified


# ------------------------------------------------------- evidence and invalidation

def rewrite(path, change):
    raw = json.loads(path.read_text(encoding="utf-8"))
    change(raw)
    path.write_text(json.dumps(raw), encoding="utf-8")


def with_all_evidence(tmp_path):
    path = write_profile(tmp_path)
    for kind, ref in (("direction", ""), ("replay", "run-1"), ("live", "S65-report")):
        record_evidence(path, kind, how="frame", by="me", date="2026-11-01", note="n", ref=ref, root=tmp_path)
    return path


def test_a_changed_lane_map_voids_direction_evidence_only(tmp_path):
    path = with_all_evidence(tmp_path)
    rewrite(path, lambda r: r["lane_map"].update(lane_0="S", lane_1="N"))
    p = load(path)
    assert not p.evidence("direction") and p.stale_evidence("direction") and not p.directions_verified
    assert p.evidence("replay") and p.evidence("live")


def test_a_moved_lane_voids_all_of_it(tmp_path):
    path = with_all_evidence(tmp_path)
    rewrite(path, lambda r: r["geometry"]["lanes"][0].update(centre=[0.21, 0.3]))
    p = load(path)
    assert not p.evidence("direction") and not p.evidence("replay") and not p.evidence("live")


def test_a_wider_lane_radius_voids_all_of_it(tmp_path):
    path = with_all_evidence(tmp_path)
    rewrite(path, lambda r: r["geometry"].update(max_radius=0.3))
    p = load(path)
    assert not p.evidence("direction") and not p.evidence("replay") and not p.evidence("live")


def test_new_thresholds_void_what_was_counted_and_leave_direction(tmp_path):
    path = with_all_evidence(tmp_path)
    other = tmp_path / "spec_2.json"
    other.write_bytes(json.dumps({"cameras": {"cam_a": {"low": 3, "med": 5, "lanes": 2}}}).encode())
    digest = hashlib.sha256(other.read_bytes()).hexdigest()
    rewrite(path, lambda r: r["calibration"].update(persistence_spec="spec_2.json", spec_sha256=digest))
    p = load(path)
    assert p.evidence("direction") and p.directions_verified
    assert not p.evidence("replay") and p.stale_evidence("replay")
    assert not p.evidence("live") and p.stale_evidence("live")


def test_new_limitations_or_provenance_void_nothing(tmp_path):
    path = with_all_evidence(tmp_path)
    rewrite(path, lambda r: r["limitations"].append("a note"))
    p = load(path)
    assert p.evidence("direction") and p.evidence("replay") and p.directions_verified


def test_verified_needs_the_status_and_matching_evidence(tmp_path):
    claimed = write_profile(tmp_path, direction={"status": "verified"})
    assert not load(claimed).directions_verified                        # a claim with no evidence
    path = write_profile(tmp_path)
    assert not load(path).directions_verified
    record_evidence(path, "direction", how="frame", by="me", date="2026-11-01", note="n", root=tmp_path)
    assert load(path).directions_verified


def test_does_not_apply_is_never_verified(tmp_path):
    path = write_profile(tmp_path, direction={"status": "does_not_apply"})
    assert not load(path).directions_verified


def test_live_evidence_must_name_its_s65_report(tmp_path):
    with pytest.raises(ProfileError, match="S65"):
        record_evidence(write_profile(tmp_path), "live", how="stream", by="me", date="d", note="n", root=tmp_path)


def test_recording_binds_what_stands_now_and_refuses_a_broken_profile(tmp_path):
    path = write_profile(tmp_path)
    entry = record_evidence(path, "replay", how="demo_live", by="me", date="d", note="n", root=tmp_path)
    assert entry["binds"] == binding(json.loads(path.read_text(encoding="utf-8")), "replay")
    assert load(path).direction_status == "declared"                    # replay says nothing about direction


# --------------------------------------------------------- nothing secret in a file

def test_a_profile_has_nowhere_to_put_a_stream_url(tmp_path):
    with pytest.raises(ProfileError, match="fields must be exactly"):
        load(write_profile(tmp_path, stream=SECRET))


def test_no_committed_profile_holds_a_url_or_a_path_outside_the_repository():
    for path in CAMERAS.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "rtsp" not in text and "://" not in text and "D:" not in text and "C:" not in text, path.name


# ----------------------------------------------------------- the committed profiles

@pytest.mark.parametrize("camera", ["150th_Eastgate", "150th_Newport", "150th_SE38th"])
def test_every_committed_profile_declares_and_claims_no_direction(camera):
    p = load_profile(CAMERAS / f"{camera}.json")
    assert p.direction_status == "declared" and not p.directions_verified and p.raw["evidence"] == []
    assert len(p.lanes) == 4 and p.raw["provenance"]["placed_by"] == "project owner"


def test_known_weaknesses_travel_with_the_camera():
    assert any("parked" in t for t in load_profile(CAMERAS / "150th_Eastgate.json").limitations)
    assert any("signal housing" in t for t in load_profile(CAMERAS / "150th_Newport.json").limitations)


def test_the_lanes_match_the_owners_recorded_placement():
    """PREREGISTRATION_P103.md, Amendment 1: the committed numbers, read back."""
    text = (ROOT / "experiments/results/bellevue_pilot/PREREGISTRATION_P103.md").read_text(encoding="utf-8")
    for camera in ("150th_Eastgate", "150th_Newport", "150th_SE38th"):
        row = next(line for line in text.splitlines() if line.startswith(f"| {camera} | lane_0"))
        for name, (x, y) in load_profile(CAMERAS / f"{camera}.json").lanes:
            assert f"{name} ({x:.4f}, {y:.4f})" in row


# ------------------------------------------------------------------ the edge -----

@pytest.fixture
def edge(monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    pytest.importorskip("mfstnet")
    import edge.run as run

    monkeypatch.setattr(run, "load_counting", lambda p: (Path(__file__), 0.25, 992))
    for name in ("STMS_MQTT_USERNAME", "STMS_MQTT_PASSWORD", "STMS_MQTT_CA_FILE"):
        monkeypatch.delenv(name, raising=False)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    return SimpleNamespace(run=run, clip=clip)


def base(edge, *extra):
    return ["--source", str(edge.clip), "--intersection-id", "j1", *extra]


def test_a_profile_gives_the_edge_what_the_flags_would(edge):
    s = edge.run.parse_args(base(edge, "--profile", str(CAMERAS / "150th_Eastgate.json")))
    assert s.camera == "150th_Eastgate" and s.approaches == {"lane_0": "N", "lane_1": "S", "lane_2": "E", "lane_3": "W"}
    assert s.lanes.names == ("lane_0", "lane_1", "lane_2", "lane_3") and s.lanes.max_radius == 0.25
    assert s.lanes.centres[0] == (0.207, 0.7197) and s.directions_verified is False


def test_the_same_camera_by_flags_and_by_profile_agree(edge):
    """Backwards compatibility: and the two ways in give one configuration."""
    manifest = ROOT / "data" / "corpus_p103" / "150th_Eastgate" / "manifest.json"
    if not manifest.is_file():
        pytest.skip("the corpus is not committed")
    by_flags = edge.run.parse_args(base(edge, "--lanes", str(manifest), "--camera", "150th_Eastgate",
                                        "--approaches", "lane_0=N", "lane_1=S", "lane_2=E", "lane_3=W"))
    by_profile = edge.run.parse_args(base(edge, "--profile", str(CAMERAS / "150th_Eastgate.json")))
    assert by_flags.lanes == by_profile.lanes and by_flags.approaches == by_profile.approaches
    assert by_flags.persistence_spec.resolve() == by_profile.persistence_spec.resolve()
    assert by_flags.directions_verified is False


@pytest.mark.parametrize("flag", [["--camera", "x"], ["--lanes", "x.json"], ["--approaches", "a=N"], ["--persistence-spec", "x.json"]])
def test_a_flag_beside_a_profile_is_refused_not_silently_overridden(edge, flag, capsys):
    with pytest.raises(SystemExit):
        edge.run.parse_args(base(edge, "--profile", str(CAMERAS / "150th_Eastgate.json"), *flag))
    assert "already says" in capsys.readouterr().err


def test_a_bad_profile_stops_the_edge_with_its_reason(edge, capsys):
    with pytest.raises(SystemExit):
        edge.run.parse_args(base(edge, "--profile", "cameras/nowhere.json"))
    assert "no profile at" in capsys.readouterr().err


@pytest.mark.parametrize("missing", ["--lanes", "--approaches", "--camera"])
def test_without_a_profile_the_flags_are_still_required(edge, missing, capsys):
    argv = {"--lanes": ["x.json"], "--approaches": ["a=N"], "--camera": ["NE8th"]}
    del argv[missing]
    with pytest.raises(SystemExit):
        edge.run.parse_args(base(edge, *[part for pair in argv.items() for part in (pair[0], *pair[1])]))
    assert f"{missing} is required" in capsys.readouterr().err


def test_verified_reaches_the_edge_only_through_matching_evidence(edge, tmp_path, monkeypatch):
    path = write_profile(tmp_path)
    monkeypatch.setattr(edge.run, "load_profile", lambda p: load_profile(p, tmp_path))
    argv = base(edge, "--profile", str(path))
    assert edge.run.parse_args(argv).directions_verified is False
    record_evidence(path, "direction", how="frame", by="me", date="d", note="n", root=tmp_path)
    assert edge.run.parse_args(argv).directions_verified is True


# ---------------------------------------------------- the heartbeat and the server

def test_the_heartbeat_carries_it_and_absent_reads_false():
    old = json.loads(Heartbeat("online", Mode.NORMAL, False, False, ts=1.0).encode())
    del old["directions_verified"]
    assert decode(Topic.HEARTBEAT, json.dumps(old)).directions_verified is False     # an older edge
    assert decode(Topic.HEARTBEAT, Heartbeat("online", Mode.NORMAL, False, False, ts=1.0, directions_verified=True).encode()).directions_verified is True


def test_the_heartbeat_refuses_anything_but_a_boolean():
    from contracts.mqtt import ContractError

    for bad in ("true", 1, None):
        with pytest.raises(ContractError, match="directions_verified"):
            Heartbeat("online", Mode.NORMAL, False, False, ts=1.0, directions_verified=bad)


def test_the_node_sends_what_it_was_given():
    node = EdgeNode(intersection_id="j1", transport=RecordingTransport(), directions_verified=True)
    node.publish_heartbeat(now=1_800_000_000.0)
    assert json.loads(node.transport.sent[-1][1])["directions_verified"] is True


def test_the_server_serves_it(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "h.sqlite")
    server.store_heartbeat("j1", Heartbeat("online", Mode.NORMAL, False, False).encode())
    body = TestClient(server.app, headers=write_headers).get("/heartbeat/j1/latest").json()
    assert body["directions_verified"] is False


def test_the_schema_version_did_not_move():
    from contracts.mqtt import SCHEMA_VERSION

    assert SCHEMA_VERSION == 2
