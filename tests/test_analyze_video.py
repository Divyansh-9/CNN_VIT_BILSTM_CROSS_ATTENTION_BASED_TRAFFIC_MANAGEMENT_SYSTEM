"""D34: a whole recording becomes numbers the Analyze a video page can follow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytest.importorskip("cv2")

from edge.profile import load_profile  # noqa: E402
from edge.run import PILOT  # noqa: E402
from mfstnet.corpus.counting import Detection  # noqa: E402
from scripts import analyze_video as tool  # noqa: E402
from scripts.tracked_video import TrackedVideo, detector_settings  # noqa: E402


def test_detector_override_sets_inference_size(monkeypatch, tmp_path):
    weights = tmp_path / "custom.pt"
    monkeypatch.setenv("STMS_VIDEO_WEIGHTS", str(weights))
    monkeypatch.setenv("STMS_VIDEO_CONF", "0.4")
    monkeypatch.setenv("STMS_VIDEO_IMGSZ", "960")
    assert detector_settings() == (weights, .4, 960)
    monkeypatch.setenv("STMS_VIDEO_IMGSZ", "950")
    with pytest.raises(ValueError, match="multiple of 32"):
        detector_settings()


def test_cctv_checkpoint_class_names_have_occupancy_weights():
    result = tool.pcu_table(["Hatchback", "Two-wheeler", "Mini-bus", "LCV", "car"])
    assert result["weights"]["Hatchback"] == result["weights"]["car"]
    assert {"Two-wheeler", "Mini-bus", "LCV"} <= result["weights"].keys()


def test_occupancy_keeps_detections_without_associated_track_ids():
    capture = []
    boxes = SimpleNamespace(xyxy=[(5, 5, 15, 15), (25, 25, 35, 35)], conf=[.9, .8], cls=[0, 0])
    boxes.cpu = lambda: SimpleNamespace(numpy=lambda: boxes)
    analyzer = TrackedVideo.__new__(TrackedVideo)
    analyzer.size, analyzer.ids, analyzer.frames_processed = 640, [0], 0
    analyzer.model = SimpleNamespace(names={0: "car"}, predict=lambda *_, **__: [
        SimpleNamespace(orig_shape=(100, 100), orig_img=None, boxes=boxes)])
    analyzer.tracker = SimpleNamespace(update=lambda *_: [(5, 5, 15, 15, 7, .9, 0, 0)])
    analyzer.crossings = SimpleNamespace(observe=lambda _, rows, ids, __: capture.append((rows, ids)))
    analyzer.classes = {"car": "car"}
    detections, ids = analyzer.track(None, 0)
    assert len(detections) == 2 and ids == [7, None]
    assert capture == [([detections[0]], [7])]

PROFILE = ROOT / "cameras" / "150th_Eastgate.json"
needs_specs = pytest.mark.skipif(not tool.RIDGE_SPEC.exists() or not (PILOT / "persistence_v1.json").exists(),
                                 reason="Bellevue-derived specs absent (public tree)")


def box_at(centre, confidence=0.9) -> Detection:
    x, y = centre
    return Detection(cls="car", confidence=confidence, x1=x - 0.01, y1=y - 0.01, x2=x + 0.01, y2=y + 0.01)


def run(samples: int, per_lane):
    profile = load_profile(PROFILE)
    frames = ((k * 2.0, k) for k in range(samples))

    def detector(frame):
        out = []
        for i, (_, centre) in enumerate(profile.lanes):
            out += [box_at(centre)] * per_lane(frame, i)
        return out

    return profile, tool.analyse(frames, detector, profile, ridge_spec=tool.RIDGE_SPEC, min_confidence=0.25,
                                 clip="example", duration_s=samples * 2.0)


@needs_specs
def test_forecasts_start_when_the_deployed_forecasters_would():
    _, result = run(100, lambda k, i: 1)
    s = result["samples"]
    assert s[28]["level"] is None and s[29]["level"] is not None   # 30 samples: 1 min
    assert s[58]["number"] is None and s[59]["number"] is not None  # 60 samples: 2 min


@needs_specs
def test_video_count_blend_uses_only_the_two_minutes_available_at_prediction_time():
    from edge.count_forecast import RidgeCountForecaster
    from statistics import fmean

    def demand(k, lane):
        return (1 if k < 30 else 4) + lane
    profile, result = run(100, demand)
    _, changed = run(100, lambda k, lane: demand(k, lane) if k < 60 else 0)
    ridge = RidgeCountForecaster(tool.RIDGE_SPEC, profile.lane_map)
    for row in result["samples"][:60]:
        baseline = ridge.step(row["counts"], row["t"])
    assert result["models"]["number"].startswith("video-blend-70/30:ridge@")
    counts = result["samples"][59]["number"]
    assert counts == changed["samples"][59]["number"]
    assert result["samples"][59]["then"] != changed["samples"][59]["then"]
    for lane, approach in profile.lane_map.items():
        history = fmean(row["counts"][lane] for row in result["samples"][:60])
        assert counts[approach] == round(.7 * baseline.counts[approach] + .3 * history, 4)


@needs_specs
def test_counts_and_boxes_are_per_lane_and_normalised():
    _, result = run(40, lambda k, i: i)
    sample = result["samples"][0]
    assert sample["counts"] == {"lane_0": 0, "lane_1": 1, "lane_2": 2, "lane_3": 3}
    assert len(sample["boxes"]) == 6
    assert all(0.0 <= v <= 1.0 for box in sample["boxes"] for v in box)


@needs_specs
def test_then_is_the_following_sixty_seconds_classed_by_the_same_limits():
    # Quiet for the first 40 samples, then two vehicles in lane 0's view for good.
    profile, result = run(100, lambda k, i: 2 if (k >= 40 and i == 0) else 0)
    approach = profile.lane_map["lane_0"]
    s = result["samples"]
    assert s[39]["then"][approach] == {"level": "HIGH", "number": 2.0}
    assert s[9]["then"][approach] == {"level": "LOW", "number": 0.0}
    assert s[100 - 30 - 1]["then"] is not None and s[100 - 30]["then"] is None   # the video ends first


@needs_specs
def test_the_output_is_numbers_and_names_no_folder():
    _, result = run(40, lambda k, i: 1)
    text = json.dumps(result)
    assert result["kind"] == tool.KIND and result["clip"] == "example"
    assert ":\\\\" not in text and str(ROOT) not in text
    assert result["limits"]["low"] < result["limits"]["med"]
    assert result["directions_verified"] is False
    assert {lane["approach"] for lane in result["lanes"]} == {"N", "S", "E", "W"}


def test_refuses_a_missing_video_and_will_not_replace_results(tmp_path, capsys):
    out = tmp_path / "a.json"
    assert tool.main(["--video", str(tmp_path / "none.mp4"), "--profile", str(PROFILE), "--out", str(out)]) == 1
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    out.write_text("{}")
    assert tool.main(["--video", str(video), "--profile", str(PROFILE), "--out", str(out)]) == 1
    assert out.read_text() == "{}"
    assert "exists" in capsys.readouterr().err


@needs_specs
def test_refuses_an_unreadable_video(tmp_path, capsys):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"not a video")
    assert tool.main(["--video", str(video), "--profile", str(PROFILE), "--out", str(tmp_path / "o.json")]) == 1
    assert "at least 2 seconds of readable video" in capsys.readouterr().err


# D35: class details for the Engineering view, in a new schema.
@needs_specs
def test_detections_match_the_boxes_and_rebuild_the_counts():
    _, result = run(40, lambda k, i: i)
    assert result["schema"] == 2
    for sample in result["samples"]:
        assert len(sample["detections"]) == len(sample["boxes"])
        rebuilt = {lane: 0 for lane in sample["counts"]}
        for cls, confidence, lane in sample["detections"]:
            assert cls == "car" and confidence == 0.9
            rebuilt[lane] += 1
        assert rebuilt == sample["counts"]


def test_pcu_table_uses_the_projects_mapping_and_never_guesses():
    table = tool.pcu_table(["car", "two wheeler", "LCV", "bicycle", "autorickshaw", "not a class"])
    assert table["weights"] == {"car": 1.0, "two wheeler": 0.3, "LCV": 5.0, "bicycle": 0.2, "autorickshaw": 1.2}
    assert "ADR-017" in table["source"]
