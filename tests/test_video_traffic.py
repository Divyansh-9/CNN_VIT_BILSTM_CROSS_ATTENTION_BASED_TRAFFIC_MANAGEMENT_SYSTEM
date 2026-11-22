"""Recording measurements, evidence, and durable analysis identity."""

from types import SimpleNamespace

import pytest

from mfstnet.corpus.counting import Detection
from scripts.video_history import VideoHistory


def test_import_and_reset_preserve_unclassified_legacy_and_live_reports(tmp_path):
    from contextlib import closing
    import json

    history = VideoHistory(tmp_path / "jobs.sqlite")
    first = history.start("early.mp4", 42, "whole-frame")
    live = history.start("live.mp4", 42, "whole-frame", pending_replay=True)
    legacy = history.start("unclassified.mp4", 42, "whole-frame")
    keys = ("a" * 64, "b" * 64, "c" * 64)
    reports = {key: {"clip": name} for key, name in zip(keys, ("early", "live", "unclassified"))}
    for identifier, key in zip((first, live, legacy), keys):
        history.finish(identifier, key, None)
    with closing(history.connect()) as db, db:
        db.execute("UPDATE video_jobs SET mode=NULL")
        for identifier, timestamp in zip((first, live, legacy), range(3)):
            db.execute("UPDATE video_jobs SET started_at=? WHERE id=?", (f"2020-01-0{timestamp + 1}", identifier))
    history = VideoHistory(history.path)
    history.migrate_reports(reports.get)
    assert history.reveal_replay(live)
    assert {row["id"]: row["mode"] for row in history.recent()} == {
        first: "offline", live: "demo", legacy: "legacy",
    }
    removed = []
    assert history.delete_offline(None, removed.append) == 1
    assert removed == [keys[0]]
    assert history.report(keys[0]) is None
    assert json.loads(history.report(keys[1])) == reports[keys[1]]
    assert json.loads(history.report(keys[2])) == reports[keys[2]]
from scripts.video_traffic import Crossings, Policy, summarize


PROFILE = SimpleNamespace(
    lanes=[("lane_0", (.5, .2)), ("lane_1", (.8, .5)), ("lane_2", (.5, .8)), ("lane_3", (.2, .5))],
    lane_map={"lane_0": "N", "lane_1": "E", "lane_2": "S", "lane_3": "W"},
    max_radius=.18,
)


def recording(per_lane):
    return {
        "duration_s": 60.0, "step_s": 2.0,
        "lanes": [{"name": lane, "approach": approach} for lane, approach in PROFILE.lane_map.items()],
        "samples": [{"t": t, "counts": dict(zip(PROFILE.lane_map, per_lane))} for t in range(0, 60, 2)],
    }


def car(x, y):
    return Detection("car", .9, x - .01, y - .01, x + .01, y + .01)


@pytest.mark.parametrize("counts,level,green,congestion", [
    ((0, 0, 0, 0), "Low", 15, False),
    ((1, 0, 0, 0), "Low", 30, False),
    ((4, 2, 2, 1), "High", 45, True),
    ((6, 3, 2, 1), "Severe", 60, True),
])
def test_occupancy_and_signal_advice_follow_measurements(counts, level, green, congestion):
    policy = Policy()
    report = summarize(recording(counts), Crossings(PROFILE, policy), policy)
    assert report["crossings"] == [] and sum(report["by_type"].values()) == 0
    assert report["average_visible"] == sum(counts)
    assert report["windows"][0]["level"] == level and report["windows"][0]["green"]["N"] == green
    triggered = [a for a in report["alerts"] if a["type"] == "Traffic congestion"]
    assert bool(triggered) is congestion
    if congestion:
        assert len(triggered) == 1
        assert triggered[0]["t"] == 28 and triggered[0]["evidence"]["visible"] == sum(counts)
    else:
        assert report["alerts"] == []


def test_whole_frame_counts_confirmed_track_once_without_signal_advice():
    from scripts.recording_profile import WHOLE_FRAME_PATH, load_recording_profile

    profile = load_recording_profile(WHOLE_FRAME_PATH)
    policy = Policy()
    tracks = Crossings(profile, policy)
    vehicle = Detection("car", .9, .4, .4, .6, .6)
    tracks.observe(0, [vehicle], [10], {"car": "car"})
    assert tracks.events == []
    tracks.observe(.25, [vehicle], [10], {"car": "car"})
    tracks.observe(.50, [vehicle], [10], {"car": "car"})
    data = {"lanes": [{"name": "frame", "approach": "N"}], "step_s": 2, "duration_s": 2,
            "samples": [{"t": 0, "counts": {"frame": 1}}]}
    report = summarize(data, tracks, policy)
    assert report["scope"] == "frame"
    assert report["by_type"]["car"] == 1
    assert report["lines"] == [] and report["windows"][0]["green"] == {}


def test_inbound_crossing_counts_once_even_when_the_track_crosses_again():
    policy = Policy()
    tracker = Crossings(PROFILE, policy)
    for i, y in enumerate([.16, .19, .22, .17, .23, .25]):
        tracker.observe(i / 4, [car(.5, y)], [51], {"car": "car"})
    tracker.observe(1.6, [car(.7, .17)], [52], {"car": "car"})
    tracker.observe(1.8, [car(.7, .22)], [52], {"car": "car"})
    assert [(c["track_id"], c["approach"]) for c in tracker.events] == [(51, "N")]
    summary = summarize(recording((1, 0, 0, 0)), tracker, policy)
    assert summary["by_type"]["car"] == summary["windows"][0]["crossings"] == 1


def test_resizing_a_stationary_vehicle_box_does_not_count_as_a_crossing():
    tracker = Crossings(PROFILE, Policy())
    # The trailing edge of track 40 is stable. The leading edge shrinks and
    # stretches, moving only the estimated centre across the line.
    boxes = [(.14, .23), (.14, .26), (.14, .30), (.14, .24)]
    for i, (y1, y2) in enumerate(boxes):
        tracker.observe(i / 4, [Detection("car", .9, .48, y1, .52, y2)], [40], {"car": "car"})
    assert tracker.events == []
    for i, y in enumerate([.17, .185, .199, .213, .23]):
        tracker.observe(1 + i / 4, [car(.5, y)], [41], {"car": "car"})
    assert [(event["track_id"], event["approach"]) for event in tracker.events] == [(41, "N")]


def test_delayed_detector_drift_does_not_complete_a_crossing():
    tracker = Crossings(PROFILE, Policy())
    ys = [.18, .197, .199, .202, .204, .204, .204, .204, .205, .207, .216]
    for i, y in enumerate(ys):
        tracker.observe(i / 4, [car(.5, y)], [40], {"car": "car"})
    assert tracker.events == []


def test_stopped_vehicle_has_a_track_and_timestamp_and_ignores_an_approach_queue():
    tracker = Crossings(PROFILE, Policy(stopped_seconds=5))
    for i in range(26):
        tracker.observe(i / 4, [car(.5, .5), car(.5, .15)], [1, 2], {"car": "car"})
    assert len(tracker.alerts) == 1
    event = tracker.alerts[0]
    assert event["t"] == 5 and event["evidence"] == {"track_id": 1, "stationary_s": 5.0}
    assert "Possible" in event["type"]
    assert "Red" not in event["type"]


def test_failed_and_repeated_analysis_keep_distinct_persisted_records(tmp_path):
    path = tmp_path / "history.sqlite"
    history = VideoHistory(path)
    first = history.start("traffic.mp4", 100, "Bellevue")
    history.finish(first, "a" * 64, None)
    second = history.start("traffic.mp4", 100, "Bellevue")
    history.finish(second, "a" * 64, None)
    bad = history.start("corrupt.mp4", 50, "Bellevue")
    history.finish(bad, None, "No picture could be decoded")
    history.set_status(bad, "processing-error", "Acknowledged")
    restored = VideoHistory(path)
    rows = restored.recent()
    assert [r["id"] for r in rows] == [bad, second, first]
    assert rows[0]["status"] == "Failed" and rows[0]["result_key"] is None
    assert rows[1]["result_key"] == rows[2]["result_key"] == "a" * 64
    assert restored.statuses(bad) == {"processing-error": "Acknowledged"}
