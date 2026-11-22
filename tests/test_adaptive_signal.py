import pytest

from scripts.adaptive_signal import AdaptiveSignal, offline_schedule, signal_config
from scripts.video_traffic import Policy


def controller(raw=None):
    lanes = {"L0": "N", "L1": "E", "L2": "S"}
    config = signal_config("test", tuple(lanes.values()), Policy(), raw=raw or {})
    return AdaptiveSignal(config, lanes, {"E", "N"})


def sample(t, n=0, e=0, s=0):
    return {"t": t, "counts": {"L0": n, "L1": e, "L2": s}}


def test_live_updates_before_transition_and_locks_during_clearance():
    live = controller()
    initial = live.observe(sample(0, n=3), [])
    assert initial["phase"]["phase"] == "N"
    assert initial["upcoming"][0]["phase"] == "E"
    changed = live.observe(sample(4, s=9), [])
    assert changed["phase"] == initial["phase"]
    assert changed["upcoming"][0]["phase"] == "S"
    assert changed["upcoming"][0]["start"] == initial["phase"]["end"]
    yellow = live.observe(sample(initial["phase"]["green_end"], e=99), [])
    assert yellow["state"] == "yellow"
    assert yellow["next_locked"]
    assert yellow["upcoming"][0] == changed["upcoming"][0]
    red = live.observe(sample(initial["phase"]["yellow_end"]), [])
    assert red["state"] == "all-red"
    next_green = live.observe(sample(initial["phase"]["end"]), [])
    assert next_green["phase"] == yellow["upcoming"][0]


def test_future_crossings_do_not_change_current_measurements():
    prefix = [{"t": 8, "approach": "E"}]
    full = prefix + [{"t": 12.5, "approach": "E"}]
    left, right = controller(), controller()
    for t in (0, 4, 8, 12):
        assert left.observe(sample(t), prefix) == right.observe(sample(t), full)
    snapshot = right.observe(sample(14, s=None), full)
    assert snapshot["measurements"]["S"] == {"visible": None, "inbound_per_min": None}
    assert snapshot["measurements"]["E"]["inbound_per_min"] == 8.6


def test_offline_full_coverage_fairness_and_explicit_clearance():
    live = controller()
    info = {"windows": [{"t": t, "end": t + 30, "approaches": {"N": 100, "E": 1, "S": 0}}
                        for t in range(0, 600, 30)], "crossings": []}
    config = live.phases, live.yellow, live.red, live.refresh, live.max_red
    schedule = offline_schedule(config, live.lanes, live.lined, info, 600)
    rows = schedule["phases"]
    assert rows[0]["phase"] == "N"
    assert rows[-1]["end"] >= 600
    phases = {p.name: p for p in live.phases}
    for i, row in enumerate(rows):
        assert row["start"] == (rows[i - 1]["end"] if i else 0)
        assert row["yellow_end"] - row["green_end"] == live.yellow
        assert row["end"] - row["yellow_end"] == live.red
        assert phases[row["phase"]].minimum <= row["green_s"] <= phases[row["phase"]].maximum
        assert row["red_wait_s"] <= live.max_red
    for index in range(0, len(rows) - 2, 3):
        assert {r["phase"] for r in rows[index:index+3]} == set(phases)
    short = offline_schedule(config, live.lanes, live.lined,
                             {"windows": info["windows"][:1], "crossings": []}, 5)
    assert short["coverage_s"] == 5
    assert {r["phase"] for r in short["phases"]} == set(phases)


def test_grouped_movements_and_pedestrians_require_explicit_configuration():
    raw = {"phases": [{"name": "Group", "approaches": ["N", "S"]},
                      {"name": "East", "approaches": ["E"]},
                      {"name": "Walk", "pedestrian": True, "walk_s": 7, "pedestrian_clearance_s": 10}]}
    with pytest.raises(ValueError, match="Unverified compatible"):
        controller(raw)
    live = controller({**raw, "compatible": [["N", "S"]]})
    walk = next(p for p in live.phases if p.pedestrian)
    assert walk.minimum == walk.maximum == 17
    with pytest.raises(ValueError, match="infeasible"):
        controller({**raw, "compatible": [["N", "S"]], "max_red_s": 30})
