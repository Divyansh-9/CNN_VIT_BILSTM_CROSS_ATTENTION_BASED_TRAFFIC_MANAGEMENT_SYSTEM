"""D3: the committed edge program, `edge/run.py`.

Before D3 the deployed path (detector -> counting -> persistence + ridge ->
publish -> fallback) ran only inside the Phase C harness, outside the
repository (HLD §9-C1). These tests pin the six things PLAN-D3 says "done"
means, without a camera, a detector or a broker: detections are handed in, and
the link is a `RecordingTransport` whose `up` is flipped by hand.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import weakref

import pytest

from contracts.mqtt import Mode, Topic
from edge.classes import load_itd_mapping
from edge.node import EdgeNode, RecordingTransport
from mfstnet.corpus.counting import Detection
from mfstnet.corpus.lanes import LaneCentres

ID = "ne8th"
CENTRES = {"lane_0": (0.15, 0.5), "lane_1": (0.5, 0.2), "lane_2": (0.8, 0.4)}
APPROACHES = ["lane_0=W", "lane_1=N", "lane_2=E"]


@pytest.fixture(autouse=True)
def no_broker_credentials(monkeypatch):
    # The developer's own STMS_MQTT_* must not change what these tests see.
    from contracts.broker import CA_FILE_ENV, PASSWORD_ENV, USERNAME_ENV

    monkeypatch.delenv(USERNAME_ENV, raising=False)
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    monkeypatch.delenv(CA_FILE_ENV, raising=False)


def run_module():
    import edge.run as module
    return module


def det(cls: str, lane: str, confidence: float = 0.9) -> Detection:
    x, y = CENTRES[lane]
    return Detection(cls=cls, confidence=confidence, x1=x - 0.01, y1=y - 0.01,
                     x2=x + 0.01, y2=y + 0.01)


@pytest.fixture
def files(tmp_path):
    lanes = tmp_path / "lanes.json"
    lanes.write_text(json.dumps({"reviewed": True, "max_radius": 0.25, "lanes": [
        {"name": n, "centre": list(c)} for n, c in CENTRES.items()]}), encoding="utf-8")
    clip, weights = tmp_path / "clip.mp4", tmp_path / "weights.pt"
    clip.write_bytes(b"not decoded by these tests")
    weights.write_bytes(b"not loaded by these tests")
    return {"lanes": lanes, "clip": clip, "weights": weights, "dir": tmp_path}


def argv(files, **override):
    args = {"--source": str(files["clip"]), "--lanes": str(files["lanes"]),
            "--approaches": APPROACHES, "--camera": "NE8th",
            "--intersection-id": ID, "--weights": str(files["weights"])}
    args.update(override)
    out = []
    for flag, value in args.items():
        if value is None:
            continue
        out += [flag, *value] if isinstance(value, list) else [flag, value]
    return out


def settings(files, **override):
    return run_module().parse_args(argv(files, **override))


def loop_for(files, transport=None):
    module = run_module()
    s = settings(files)
    node = EdgeNode(intersection_id=s.intersection_id, transport=transport or RecordingTransport(),
                    detector_classes=load_itd_mapping())
    return module.EdgeLoop(node, s.lanes, s.approaches,
                           module.PersistenceForecaster(s.persistence_spec, s.camera, s.approaches),
                           module.RidgeCountForecaster(s.ridge_spec, s.approaches),
                           min_confidence=s.conf)


TRAFFIC = [det("car", "lane_0"), det("two wheeler", "lane_1"), det("bus", "lane_2")]


# ---- 1. start-up arguments ---------------------------------------------------

def test_valid_arguments_produce_the_settings(files):
    s = settings(files)
    assert s.intersection_id == ID and s.camera == "NE8th"
    assert s.approaches == {"lane_0": "W", "lane_1": "N", "lane_2": "E"}
    assert s.lanes.names == ("lane_0", "lane_1", "lane_2")
    assert (s.broker_host, s.broker_port) == ("127.0.0.1", 1883)
    assert (s.conf, s.imgsz) == (0.45, 992)


def test_a_corpus_manifest_is_accepted_as_the_lane_file(files):
    manifest = files["dir"] / "manifest.json"
    manifest.write_text(json.dumps({"lane_centres": [
        {"name": n, "centre": list(c)} for n, c in CENTRES.items()]}), encoding="utf-8")
    assert settings(files, **{"--lanes": str(manifest)}).lanes.names == tuple(CENTRES)


@pytest.mark.parametrize("missing", ["--source", "--lanes", "--approaches", "--camera",
                                     "--intersection-id"])
def test_a_missing_required_argument_is_refused(files, missing):
    with pytest.raises(SystemExit) as stop:
        settings(files, **{missing: None})
    assert stop.value.code == 2


@pytest.mark.parametrize("bad", ["ne 8th", "x" * 33, "a/b", "", "ne8th\n", "në8th"])
def test_an_intersection_id_outside_the_p142_pattern_is_refused(files, bad, capsys):
    with pytest.raises(SystemExit):
        settings(files, **{"--intersection-id": bad})
    assert "intersection id must be 1 to 32 characters" in capsys.readouterr().err


@pytest.mark.parametrize("port", ["0", "65536", "-1", "mqtt"])
def test_an_invalid_broker_port_is_refused(files, port):
    with pytest.raises(SystemExit):
        settings(files, **{"--broker-port": port})


def test_broker_host_and_port_are_taken(files):
    s = settings(files, **{"--broker-host": "10.0.0.5", "--broker-port": "8883"})
    assert (s.broker_host, s.broker_port) == ("10.0.0.5", 8883)


@pytest.mark.parametrize("approaches", [
    ["lane_0=W", "lane_1=N"],                       # a lane left out
    ["lane_0=W", "lane_1=N", "lane_2=E", "lane_3=S"],  # a lane the file does not have
    ["lane_0=W", "lane_1=W", "lane_2=E"],           # two lanes, one approach
    ["lane_0=X", "lane_1=N", "lane_2=E"],           # not an approach
    ["lane_0", "lane_1=N", "lane_2=E"],             # no '='
    ["lane_0=W", "lane_0=S", "lane_1=N", "lane_2=E"],  # one lane twice
])
def test_an_approach_mapping_that_does_not_cover_the_lanes_is_refused(files, approaches):
    with pytest.raises(SystemExit):
        settings(files, **{"--approaches": approaches})


def test_an_unreviewed_lane_file_is_refused(files):
    files["lanes"].write_text(json.dumps({"lanes": [
        {"name": n, "centre": list(c)} for n, c in CENTRES.items()]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        settings(files)


@pytest.mark.parametrize("camera", ["Nowhere", "150th_Eastgate"])
def test_a_camera_without_matching_thresholds_is_refused(files, camera):
    # Nowhere has no thresholds; 150th_Eastgate was calibrated on 4 lanes, not 3.
    with pytest.raises(SystemExit):
        settings(files, **{"--camera": camera})


@pytest.mark.parametrize("flag", ["--source", "--weights", "--lanes"])
def test_a_missing_file_is_refused(files, flag):
    with pytest.raises(SystemExit):
        settings(files, **{flag: str(files["dir"] / "absent")})


def test_broker_credentials_come_from_the_environment_and_stay_out_of_the_repr(
        files, monkeypatch):
    from contracts.broker import PASSWORD_ENV, USERNAME_ENV, Credentials

    assert settings(files).credentials is None
    monkeypatch.setenv(USERNAME_ENV, "edge-ne8th")
    monkeypatch.setenv(PASSWORD_ENV, "canary-broker-value")
    s = settings(files)
    assert s.credentials == Credentials("edge-ne8th", "canary-broker-value")
    assert "canary-broker-value" not in repr(s)


@pytest.mark.parametrize("set_name", ["username", "password"])
def test_half_a_broker_credential_is_refused_at_start_up_without_echoing_it(
        files, monkeypatch, capsys, set_name):
    from contracts.broker import PASSWORD_ENV, USERNAME_ENV

    if set_name == "username":
        monkeypatch.setenv(USERNAME_ENV, "edge-ne8th")
    else:
        monkeypatch.setenv(PASSWORD_ENV, "canary-broker-value")
    with pytest.raises(SystemExit) as stop:
        settings(files)
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert (PASSWORD_ENV if set_name == "username" else USERNAME_ENV) in err
    assert "canary-broker-value" not in err and "edge-ne8th" not in err


def test_an_unusable_ca_file_is_refused_at_start_up_not_ignored(files, monkeypatch, capsys):
    # D10: a CA path that cannot be used must never fall back to plain TCP.
    from contracts.broker import CA_FILE_ENV

    monkeypatch.setenv(CA_FILE_ENV, str(files["dir"] / "absent-ca.pem"))
    with pytest.raises(SystemExit) as stop:
        settings(files)
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert CA_FILE_ENV in err and "absent-ca.pem" not in err


def test_a_usable_ca_file_is_taken_from_the_environment(files, monkeypatch):
    from contracts.broker import CA_FILE_ENV
    from scripts.tls_material import make_ca, openssl

    if openssl() is None:
        pytest.skip("needs the openssl command")
    assert settings(files).ca_file is None
    ca = make_ca(files["dir"], "run-ca")[0]
    monkeypatch.setenv(CA_FILE_ENV, str(ca))
    assert settings(files).ca_file == ca


def test_the_camera_url_comes_from_the_environment_and_is_never_echoed(files, monkeypatch,
                                                                       capsys):
    module = run_module()
    monkeypatch.delenv(module.CAMERA_ENV, raising=False)
    with pytest.raises(SystemExit):
        settings(files, **{"--source": "camera"})
    # Synthetic: example credentials on a documentation address (RFC 5737).
    secret = "rtsp://example-user:example-pass@192.0.2.9/stream"  # pragma: allowlist secret  ggignore
    monkeypatch.setenv(module.CAMERA_ENV, secret)
    assert settings(files, **{"--source": "camera"}).source == "camera"
    with pytest.raises(SystemExit):        # a later refusal must not quote it either
        settings(files, **{"--source": "camera", "--intersection-id": "bad id"})
    captured = capsys.readouterr()
    assert "example-pass" not in captured.out + captured.err


def test_the_counting_defaults_come_from_the_config_not_the_script(files, monkeypatch):
    # D5: point the program at another counting block and the defaults follow.
    module = run_module()
    config = files["dir"] / "mapping.yaml"
    config.write_text(f"counting:\n  detector_weights: {files['weights'].as_posix()}\n"
                      "  confidence_threshold: 0.5\n  imgsz: 640\n", encoding="utf-8")
    monkeypatch.setattr(module, "COUNTING_FILE", config)
    s = settings(files, **{"--weights": None})
    assert (s.weights, s.conf, s.imgsz) == (files["weights"], 0.5, 640)
    # The command line still overrides the config.
    assert settings(files, **{"--conf": "0.6", "--imgsz": "320"}).conf == 0.6


def test_the_committed_counting_block_is_what_the_corpus_was_built_with():
    # The values are not new: the committed corpus manifest records them.
    module = run_module()
    weights, conf, imgsz = module.load_counting(module.COUNTING_FILE)
    manifest = json.loads((module.ROOT / "data/corpus/manifest.json").read_text(encoding="utf-8"))
    assert (weights.name, conf, imgsz) == (manifest["detector"], manifest["conf"],
                                          manifest["imgsz"])
    assert weights == module.ROOT / "models" / "external" / manifest["detector"]


def test_a_counting_block_missing_a_setting_is_refused(files, monkeypatch, capsys):
    module = run_module()
    config = files["dir"] / "mapping.yaml"
    config.write_text("counting:\n  confidence_threshold: 0.45\n  imgsz: 992\n",
                      encoding="utf-8")
    monkeypatch.setattr(module, "COUNTING_FILE", config)
    with pytest.raises(SystemExit):
        settings(files)
    assert "detector_weights" in capsys.readouterr().err


# ---- 2. the two count representations ---------------------------------------

def test_forecasters_get_raw_totals_and_the_wire_gets_the_mapped_breakdown(files):
    loop = loop_for(files)
    out = loop.step([det("two wheeler", "lane_0"), det("two wheeler", "lane_0"),
                     det("bicycle", "lane_0"), det("LCV", "lane_1")], ts=0.0, now=100.0)
    # The forecasters were calibrated on totals with bicycles in them.
    assert out["totals"] == {"lane_0": 3, "lane_1": 1, "lane_2": 0}
    assert loop.persistence.buffer.series("lane_0") == [3]
    assert loop.ridge.buffer.series("lane_0") == [3]
    # The wire carries contract classes only; the bicycle is dropped (D1).
    sent = {topic: json.loads(payload) for topic, payload, _ in loop.node.transport.sent}
    lane_0 = sent[Topic.VEHICLE_COUNT.render(ID, "lane_0")]
    assert (lane_0["count"], lane_0["types"]) == (2, {"motorcycle": 2})
    assert sent[Topic.VEHICLE_COUNT.render(ID, "lane_1")]["types"] == {"truck": 1}
    assert sent[Topic.VEHICLE_COUNT.render(ID, "lane_2")]["count"] == 0
    assert loop.node.excluded == {"bicycle": 1}


def test_detections_below_the_calibrated_confidence_count_in_neither(files):
    loop = loop_for(files)
    out = loop.step([det("car", "lane_0", confidence=0.44), det("car", "lane_0")],
                    ts=0.0, now=100.0)
    assert out["totals"]["lane_0"] == 1
    sent = {topic: json.loads(payload) for topic, payload, _ in loop.node.transport.sent}
    assert sent[Topic.VEHICLE_COUNT.render(ID, "lane_0")]["count"] == 1


# ---- 3. window warm-up and reset --------------------------------------------

def test_no_class_forecast_before_30_samples_and_no_count_forecast_before_60(files):
    loop = loop_for(files)
    statuses = [loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k) for k in range(60)]
    assert [s["prediction"] for s in statuses[:29]] == ["warming up"] * 29
    assert statuses[29]["prediction"] == "published"
    assert [s["count_forecast"] for s in statuses[:59]] == ["warming up"] * 59
    assert statuses[59]["count_forecast"] == "published"


def test_a_gap_resets_both_windows(files):
    loop = loop_for(files)
    for k in range(60):
        loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k)
    after_gap = [loop.step(TRAFFIC, ts=200.0 + 2 * k, now=300.0 + 2 * k) for k in range(30)]
    assert [s["prediction"] for s in after_gap[:29]] == ["warming up"] * 29
    assert after_gap[29]["prediction"] == "published"
    assert all(s["count_forecast"] == "warming up" for s in after_gap)


def test_a_missing_lane_is_refused_not_read_as_zero_and_does_not_crash(files):
    loop = loop_for(files)
    for k in range(30):
        loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k)
    full, last = loop.lanes, loop.persistence.buffer.series("lane_2")[-1]
    loop.lanes = LaneCentres(names=("lane_0", "lane_1"),
                             centres=(CENTRES["lane_0"], CENTRES["lane_1"]))
    out = loop.step(TRAFFIC, ts=60.0, now=160.0)
    assert (out["prediction"], out["count_forecast"]) == ("refused", "refused")
    assert loop.refused == 2
    # Nothing was filled in for lane_2, and the refusal itself reset nothing.
    assert len(loop.persistence.buffer.series("lane_2")) == 30
    assert loop.persistence.buffer.series("lane_2")[-1] == last
    assert loop.persistence.buffer.resets == 0
    # But the refused step is a hole: the next sample is 4 s after the last
    # accepted one, so the window restarts instead of bridging the missing step.
    loop.lanes = full
    assert loop.step(TRAFFIC, ts=62.0, now=162.0)["prediction"] == "warming up"
    assert loop.persistence.buffer.resets == 1


# ---- 4. publishing and acknowledgement --------------------------------------

def test_every_publish_uses_its_contract_topic_and_that_topics_qos(files):
    loop = loop_for(files)
    for k in range(60):
        loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k)
    expected = {Topic.VEHICLE_COUNT.render(ID, lane): Topic.VEHICLE_COUNT.qos for lane in CENTRES}
    expected |= {Topic.PREDICTION.render(ID): Topic.PREDICTION.qos,
                 Topic.COUNT_FORECAST.render(ID): Topic.COUNT_FORECAST.qos,
                 Topic.HEARTBEAT.render(ID): Topic.HEARTBEAT.qos}
    seen = {}
    for topic, _, qos in loop.node.transport.sent:
        seen.setdefault(topic, set()).add(qos)
    assert seen == {topic: {qos} for topic, qos in expected.items()}


def test_last_ack_advances_only_on_a_successful_publish(files):
    loop = loop_for(files)
    for k in range(30):
        loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k)
    assert loop.node.last_ack == 158.0
    loop.node.transport.up = False
    out = loop.step(TRAFFIC, ts=60.0, now=160.0)
    assert out["delivered"] == [] and out["prediction"] == "not delivered"
    assert loop.node.last_ack == 158.0
    loop.node.transport.up = True
    loop.step(TRAFFIC, ts=62.0, now=162.0)
    assert loop.node.last_ack == 162.0


# ---- 5. local fallback and recovery, measured from last_ack -----------------

def test_local_mode_is_timed_from_the_last_acknowledgement_not_from_the_drop(files):
    loop = loop_for(files)
    for now in (100.0, 102.0, 104.0):          # acknowledged
        assert loop.step(TRAFFIC, ts=now, now=now)["mode"] is Mode.NORMAL
    loop.node.transport.up = False             # the link drops at 106
    modes = {now: loop.step(TRAFFIC, ts=now, now=now)["mode"]
             for now in (106.0, 108.0, 110.0, 112.0, 114.0, 116.0)}
    # 114 is 10 s after the last ack, not over it; 116 is 12 s after the ack
    # but only 10 s after the drop, so a drop-timed rule would still say NORMAL.
    assert modes[114.0] is Mode.NORMAL
    assert modes[116.0] is Mode.LOCAL
    loop.node.transport.up = True
    assert loop.step(TRAFFIC, ts=118.0, now=118.0)["mode"] is Mode.NORMAL


def test_the_local_cycle_runs_while_the_link_is_down(files):
    loop = loop_for(files)
    loop.step(TRAFFIC, ts=0.0, now=100.0)
    loop.node.transport.up = False
    phases = [loop.step(TRAFFIC, ts=2.0 * k, now=100.0 + 2 * k)["phase"] for k in range(6, 9)]
    assert phases == ["EW", "NS", "EW"]


def test_fallback_is_still_decided_while_the_camera_is_reconnecting(files):
    loop = loop_for(files)
    loop.step(TRAFFIC, ts=0.0, now=100.0)
    loop.node.transport.up = False
    assert loop.idle(now=109.0)["mode"] is Mode.NORMAL
    assert loop.idle(now=111.0)["mode"] is Mode.LOCAL


def test_recovery_is_reported_as_the_link_not_as_signal_control(files, caplog):
    # The log used to say "the server is driving again"; no server drives a signal.
    import logging

    caplog.set_level(logging.INFO, logger="edge.run")
    loop = loop_for(files)
    loop.step(TRAFFIC, ts=0.0, now=100.0)
    loop.node.transport.up = False
    assert loop.step(TRAFFIC, ts=12.0, now=112.0)["mode"] is Mode.LOCAL
    loop.node.transport.up = True
    out = loop.step(TRAFFIC, ts=14.0, now=114.0)
    assert out["mode"] is Mode.NORMAL
    restored = [r.getMessage() for r in caplog.records if "link restored" in r.getMessage()]
    assert restored == ["link restored: publishes are acknowledged again"]
    for text in (*restored, out["reason"]):
        assert "driv" not in text and "server" not in text


# ---- 6. frames stay in memory -----------------------------------------------

class Frame:
    """Stands in for a decoded frame; weak-referenceable, unlike bytes."""

    __slots__ = ("pixels", "__weakref__")

    def __init__(self) -> None:
        self.pixels = bytearray(64)


def test_frames_are_dropped_each_step_and_nothing_is_written(files, monkeypatch):
    module = run_module()
    s = settings(files, **{"--samples": "40"})
    node = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    refs: list[weakref.ref] = []

    def frames():
        for k in range(45):
            # The previous frame must already be gone: the loop kept nothing.
            assert not refs or refs[-1]() is None, f"frame {k - 1} outlived its step"
            frame = Frame()
            refs.append(weakref.ref(frame))
            yield 2.0 * k, frame
            del frame

    def detector(frame):
        assert isinstance(frame, Frame)
        return list(TRAFFIC)

    real_open, real_os_open = builtins.open, os.open

    def guarded_open(file, mode="r", *args, **kwargs):
        assert not set(mode) & set("wax+"), f"opened {file} for writing"
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT), f"opened {path} for writing"
        return real_os_open(path, flags, *args, **kwargs)

    before = sorted(p.name for p in files["dir"].iterdir())
    monkeypatch.chdir(files["dir"])
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    loop = module.run(s, node=node, detector=detector, frames=frames())
    monkeypatch.undo()
    assert len(refs) == 40                     # --samples stopped it
    assert all(ref() is None for ref in refs)
    assert sorted(p.name for p in files["dir"].iterdir()) == before
    assert loop.persistence.ready
    assert not any(isinstance(v, Frame) for v in vars(loop).values())


def test_a_missing_frame_ticks_the_node_without_counting(files):
    module = run_module()
    s = settings(files)
    node = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    calls = []
    loop = module.run(s, node=node, detector=lambda f: calls.append(f) or list(TRAFFIC),
                      frames=iter([(0.0, Frame()), (2.0, None), (4.0, Frame())]))
    assert len(calls) == 2
    # The missing step is a gap, so the window restarted rather than bridging it.
    assert len(loop.persistence.buffer.series("lane_0")) == 1
    heartbeats = [t for t in node.transport.topics() if t == Topic.HEARTBEAT.render(ID)]
    assert len(heartbeats) == 3


def test_every_heartbeat_names_the_replay_position_and_the_lane_map(files):
    """D22: a replay's position follows video time, step by step, missing
    frames included, and the lane map is the one the forecasters were given."""
    module = run_module()
    s = settings(files)
    node = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    source = module.describe_source(s, 300.0)
    module.run(s, node=node, detector=lambda f: list(TRAFFIC), source=source,
               frames=iter([(0.0, Frame()), (2.0, None), (4.0, Frame())]))
    sent = [json.loads(p) for t, p, _ in node.transport.sent if t == Topic.HEARTBEAT.render(ID)]
    assert [b["source"]["position_s"] for b in sent] == [0.0, 2.0, 4.0]
    assert {b["source"]["session"] for b in sent} == {source["session"]}
    assert all(b["source"]["kind"] == "replay" and b["lanes"] == s.approaches for b in sent)

def test_a_full_run_publishes_checks_on_their_own_topic_with_the_run_session(files):
    """D26: class checks once persistence has forecast and 30 more samples
    came; count checks once ridge has, 30 after its first forecast."""
    module = run_module()
    s = settings(files)
    node = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    source = module.describe_source(s, 300.0)
    module.run(s, node=node, detector=lambda f: list(TRAFFIC), source=source,
               frames=iter([(i * 2.0, Frame()) for i in range(100)]))
    sent = [json.loads(p) for t, p, _ in node.transport.sent if t == Topic.FORECAST_CHECK.render(ID)]
    assert sent and {c["session"] for c in sent} == {source["session"]}
    assert all(c["checked_ts"] - c["made_ts"] == 60.0 for c in sent)
    assert any(c["counts"] for c in sent) and all(c["classes"] for c in sent)
    assert set(sent[-1]["classes"]) == set(s.approaches.values())


def test_a_failing_check_never_stops_a_forecast(files, monkeypatch):
    module = run_module()
    s = settings(files)
    frames = lambda: iter([(i * 2.0, Frame()) for i in range(70)])
    healthy = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    module.run(s, node=healthy, detector=lambda f: list(TRAFFIC), frames=frames())

    def broken(self, *args):
        raise RuntimeError("a fault in the check, not in the forecasts")

    monkeypatch.setattr(module.ForecastChecker, "step", broken)
    failing = EdgeNode(intersection_id=ID, transport=RecordingTransport())
    loop = module.run(s, node=failing, detector=lambda f: list(TRAFFIC), frames=frames())
    forecasts = lambda n: [t for t, _, _ in n.transport.sent
                           if t in (Topic.PREDICTION.render(ID), Topic.COUNT_FORECAST.render(ID))]
    assert forecasts(failing) == forecasts(healthy) and forecasts(failing)
    assert loop.check_failures == 70
    assert Topic.FORECAST_CHECK.render(ID) not in failing.transport.topics()
