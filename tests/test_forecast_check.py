"""Each forecast beside what it forecast: contract, edge pairing, server (D26, ADR-014 §2)."""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import (CongestionClass, CongestionPrediction, ContractError,  # noqa: E402
                            CountForecast, ForecastCheck, Topic, decode)
from edge.check import ForecastChecker  # noqa: E402
from edge.persistence import classify  # noqa: E402
from edge.samples import SampleError  # noqa: E402

MARKER = "QUOTEDBACK"
TEXT = {"content-type": "text/plain"}
SESSION = "a1b2c3d4e5f6"
CLASS_MODEL, COUNT_MODEL = "persistence@2431c6641b9c", "ridge@73532968dcf2"
LOW, MED = 2.0, 5.0


def check(made=10.0, checked=70.0, session=SESSION, classes=None, counts=None, **extra):
    classes = {"N": {"forecast": "HIGH", "observed": "MEDIUM"}} if classes is None else classes
    counts = {"N": {"forecast": 6.1, "observed": 5.4}} if counts is None else counts
    return ForecastCheck(session=session, made_ts=made, checked_ts=checked, classes=classes,
                         counts=counts, class_model=CLASS_MODEL if classes else None,
                         count_model=COUNT_MODEL if counts else None, **extra)


# ------------------------------------------------------------------ contract --

def test_a_check_round_trips_and_its_topic_is_its_own():
    decoded = decode(Topic.FORECAST_CHECK, check().encode())
    assert decoded.classes == {"N": {"forecast": "HIGH", "observed": "MEDIUM"}}
    assert Topic.FORECAST_CHECK.render("j1") == "stms/j1/forecast/check"
    assert Topic.FORECAST_CHECK.qos == 0
    assert decode(Topic.FORECAST_CHECK, check(made=0.0, checked=60.0).encode()).made_ts == 0.0   # video time


@pytest.mark.parametrize("bad", [
    dict(session="XYZ"),
    dict(made=70.0, checked=10.0),                       # checked before it was made
    dict(made=-1.0),
    dict(classes={}, counts={}),                         # compares nothing
    dict(classes={"X": {"forecast": "HIGH", "observed": "LOW"}}),
    dict(classes={"N": {"forecast": MARKER, "observed": "LOW"}}),
    dict(classes={"N": {"forecast": "HIGH", "observed": "LOW", "extra": MARKER}}),
    dict(counts={"N": {"forecast": -1.0, "observed": 2.0}}),
    dict(counts={"N": {"forecast": float("nan"), "observed": 2.0}}),
    dict(counts={"N": {"forecast": 1.0}}),               # a forecast with nothing to compare it to
])
def test_a_bad_check_is_refused_without_quoting_it(bad):
    args = {"made": 10.0, "checked": 70.0, "session": SESSION, "classes": None, "counts": None}
    args.update(bad)
    with pytest.raises(ContractError) as refused:
        check(**args)
    assert MARKER not in str(refused.value)


def test_each_side_names_its_model_when_and_only_when_it_is_compared():
    with pytest.raises(ContractError):
        ForecastCheck(SESSION, 10.0, 70.0, {"N": {"forecast": "LOW", "observed": "LOW"}}, {},
                      class_model=None)
    with pytest.raises(ContractError):
        ForecastCheck(SESSION, 10.0, 70.0, {"N": {"forecast": "LOW", "observed": "LOW"}}, {},
                      class_model=CLASS_MODEL, count_model=COUNT_MODEL)
    with pytest.raises(ContractError):
        ForecastCheck(SESSION, 10.0, 70.0, {}, {"N": {"forecast": 1.0, "observed": 1.0}},
                      count_model=CLASS_MODEL)                       # a class model on counts


# ---------------------------------------------------------------- edge pairing --

LANES = {"lane_0": "N", "lane_1": "S"}


def predictions(classes=("HIGH", "LOW")):
    return CongestionPrediction({a: CongestionClass(c) for a, c in zip("NS", classes)},
                                {a: 0.8 for a in "NS"[:len(classes)]}, None, CLASS_MODEL)


def counts(values=(6.0, 1.0)):
    return CountForecast(dict(zip("NS", values)), COUNT_MODEL)


def feed(checker, series, start=0, forecast=lambda i: (predictions(), counts()), step_s=2.0):
    """Push samples i = start…; each step forecasts as `forecast(i)` says. Returns
    {index of the sample that completed it: check}."""
    done = {}
    for i in range(start, len(series)):
        p, c = forecast(i)
        for result in checker.step({"lane_0": series[i][0], "lane_1": series[i][1]}, i * step_s, p, c):
            done[i] = result
    return done


def test_a_forecast_is_checked_against_the_mean_of_exactly_the_next_30_samples():
    """The target P105 and P94–P103 scored: future_mean(v, e) = mean(v[e+1..e+30])."""
    rng = random.Random(7)
    series = [(rng.randint(0, 9), rng.randint(0, 9)) for _ in range(80)]
    done = feed(ForecastChecker(LANES, LOW, MED, SESSION), series)
    assert sorted(done) == list(range(30, 80))           # the first is complete at sample 30
    for i, result in done.items():
        e = i - 30
        future = [sum(s[k] for s in series[e + 1:e + 31]) / 30 for k in (0, 1)]
        assert result.made_ts == e * 2.0 and result.checked_ts == i * 2.0
        assert result.counts["N"]["observed"] == pytest.approx(future[0], abs=1e-4)
        assert result.counts["S"]["observed"] == pytest.approx(future[1], abs=1e-4)
        assert result.classes["N"]["observed"] == classify(future[0], LOW, MED).value
        assert result.classes["N"]["forecast"] == "HIGH" and result.counts["N"]["forecast"] == 6.0
        assert result.session == SESSION


@pytest.mark.parametrize("at", [1, 15, 29])
def test_a_gap_drops_every_pending_forecast_rather_than_matching_the_nearest(at):
    checker = ForecastChecker(LANES, LOW, MED, SESSION)
    done = []
    for i in range(70):
        ts = i * 2.0 + (10.0 if i >= at else 0.0)        # a 12 s gap before sample `at`
        done += [(i, r) for r in checker.step({"lane_0": 1, "lane_1": 1}, ts, predictions(), counts())]
    assert checker.dropped == at                         # every forecast made before the gap
    assert all(r.made_ts >= at * 2.0 + 10.0 for _, r in done)   # none spans the gap
    assert done[0][0] == at + 30


def test_a_refused_sample_does_not_count_toward_the_30():
    checker = ForecastChecker(LANES, LOW, MED, SESSION)
    checker.step({"lane_0": 4, "lane_1": 4}, 0.0, predictions(), counts())
    taken = []
    for i in range(1, 30):
        if i == 5:
            with pytest.raises(SampleError):
                checker.step({"lane_0": -1, "lane_1": 4}, 9.0, None, None)
        taken += checker.step({"lane_0": i % 3, "lane_1": 0}, i * 2.0, None, None)
    assert taken == []                                   # 29 accepted and 1 refused: not yet
    taken = checker.step({"lane_0": 30 % 3, "lane_1": 0}, 60.0, None, None)
    assert len(taken) == 1 and taken[0].made_ts == 0.0   # due on the 30th accepted sample
    expected = sum(i % 3 for i in range(1, 31)) / 30     # the refused one is in no mean
    assert taken[0].counts["N"]["observed"] == pytest.approx(expected, abs=1e-4)


def test_an_approach_either_side_lacks_is_absent_never_zero():
    forecast = lambda i: (predictions(), CountForecast({"N": 2.0}, COUNT_MODEL))   # no S count
    done = feed(ForecastChecker(LANES, LOW, MED, SESSION), [(1, 1)] * 40, forecast=forecast)
    first = done[30]
    assert set(first.classes) == {"N", "S"} and set(first.counts) == {"N"}


def test_a_class_without_a_count_forecast_is_still_checked_and_names_one_model():
    """Persistence forecasts after 30 samples, ridge only after 60."""
    done = feed(ForecastChecker(LANES, LOW, MED, SESSION), [(1, 1)] * 40,
                forecast=lambda i: (predictions(), None))
    assert done[30].counts == {} and done[30].count_model is None and done[30].class_model == CLASS_MODEL


def test_a_step_with_no_forecast_is_never_checked():
    done = feed(ForecastChecker(LANES, LOW, MED, SESSION), [(1, 1)] * 40,
                forecast=lambda i: (predictions(), counts()) if i == 3 else (None, None))
    assert list(done) == [33]


def test_a_restart_starts_empty_and_never_pairs_with_the_last_run():
    first = ForecastChecker(LANES, LOW, MED, SESSION)
    feed(first, [(1, 1)] * 20)
    assert len(first.pending) == 20
    second = ForecastChecker(LANES, LOW, MED, "0123456789ab")
    done = feed(second, [(1, 1)] * 20)
    assert done == {} and len(second.pending) == 20


# -------------------------------------------------------------------- server --

@pytest.fixture
def server(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "checks.sqlite")
    return TestClient(server.app, headers=write_headers), server


def store_every_step(server, minutes, session=SESSION, start=0.0, **kw):
    for k in range(int(minutes * 30)):
        made = start + k * 2.0
        server.store_forecast_check("j1", check(made=made, checked=made + 60.0, session=session, **kw).encode())


def test_no_check_yet_is_a_404_never_agreement_or_zero(server):
    http, _ = server
    assert http.get("/forecast_check/j1/recent").status_code == 404


def test_the_page_gets_the_last_20_minutes_one_minute_apart_by_edge_time(server):
    http, srv = server
    store_every_step(srv, 30)                            # 900 checks, one per 2 s step
    body = http.get("/forecast_check/j1/recent").json()
    made = [s["made_ts"] for s in body["slots"]]
    assert len(made) == 20 and all(s["kind"] == "check" for s in body["slots"])
    assert [b - a for a, b in zip(made, made[1:])] == [60.0] * 19   # minutes that do not overlap
    assert made[-1] == 29 * 60.0                         # the newest minute that has begun
    assert body["summary"]["N"] == {"class": {"agreed": 0, "n": 20}, "count": {"mean_abs_diff": 0.7, "n": 20}}
    assert "Not a benchmark" in body["label"] and "forecasts are made from" in body["label"]
    assert "not MFSTNet" in body["limits"] and "%" not in json.dumps(body)


def test_a_broken_minute_is_a_gap_slot_never_skipped_or_filled(server):
    http, srv = server
    store_every_step(srv, 5)                             # made 0 … 298 s
    store_every_step(srv, 5, start=10 * 60.0)            # made 600 … 898 s
    slots = http.get("/forecast_check/j1/recent").json()["slots"]
    kinds = "".join("c" if s["kind"] == "check" else "g" for s in slots)
    # Minutes 0–4 and 10–14 each have a check at their start; minutes 5–9
    # have none, so they are five gap slots.
    assert kinds == "c" * 5 + "g" * 5 + "c" * 5


def test_a_cell_never_changes_once_drawn(server):
    """The grid is absolute in edge time, so later checks only add cells."""
    http, srv = server
    store_every_step(srv, 3)
    before = http.get("/forecast_check/j1/recent").json()["slots"]
    store_every_step(srv, 2, start=3 * 60.0)
    after = http.get("/forecast_check/j1/recent").json()["slots"]
    assert after[:len(before)] == before and len(after) == len(before) + 2


@pytest.mark.parametrize("step_s", [1.9, 2.0, 2.3, 2.7, 3.0])
def test_a_healthy_stream_with_jitter_has_no_false_gap(server, step_s):
    """A camera's steps are not exactly 2 s, and the edge's window accepts any
    step up to 3 s. So every step it keeps must leave every minute a check."""
    _, srv = server
    checks = [check(made=1000.0 + k * step_s, checked=1060.0 + k * step_s)
              for k in range(int(25 * 60 / step_s))]
    slots = srv.space_checks(checks)
    assert len(slots) == 20 and all(s["kind"] == "check" for s in slots)
    made = [s["made_ts"] for s in slots]
    assert all(57.0 < b - a < 63.0 for a, b in zip(made, made[1:]))   # still a minute apart


def test_the_grid_tolerance_is_the_longest_step_the_edge_keeps(server):
    from edge.samples import STEP_S

    assert server[1].CHECK_GRID_S == 1.5 * STEP_S        # SampleBuffer's max_gap_s


def test_a_minute_whose_start_has_no_check_is_a_gap(server):
    """A check made mid-minute (the window broke at its start) does not stand
    in for the minute: its forecast would overlap the previous one's."""
    http, srv = server
    for made in (0.0, 90.0, 120.0):
        srv.store_forecast_check("j1", check(made=made, checked=made + 60.0).encode())
    kinds = [s["kind"] for s in http.get("/forecast_check/j1/recent").json()["slots"]]
    assert kinds == ["check", "gap", "check"]


def test_the_denominators_are_counted_apart(server):
    http, srv = server
    for k in range(3):
        made = k * 60.0
        counts_ = {} if k == 0 else {"N": {"forecast": 2.0, "observed": 1.0}}
        srv.store_forecast_check("j1", check(made=made, checked=made + 60.0, counts=counts_,
                                             classes={"N": {"forecast": "LOW", "observed": "LOW"}}).encode())
    summary = http.get("/forecast_check/j1/recent").json()["summary"]["N"]
    assert summary == {"class": {"agreed": 3, "n": 3}, "count": {"mean_abs_diff": 1.0, "n": 2}}


def test_only_the_latest_session_is_shown(server):
    http, srv = server
    store_every_step(srv, 3, session="0123456789ab")
    store_every_step(srv, 1, session=SESSION, start=0.0)
    body = http.get("/forecast_check/j1/recent").json()
    assert body["session"] == SESSION and len(body["slots"]) == 1


def test_checks_go_stale_and_are_kept_an_hour_on_their_own(server, monkeypatch):
    http, srv = server
    srv.store_forecast_check("j1", check().encode())
    received = srv.time.time()
    monkeypatch.setattr(srv.time, "time", lambda: received + 11.0)
    assert http.get("/forecast_check/j1/recent").json()["stale"] is True
    monkeypatch.setattr(srv.time, "time", lambda: received + 3601.0)
    srv.store_forecast_check("j1", check(made=200.0, checked=260.0).encode())   # the store prunes
    with sqlite3.connect(srv.DATABASE) as connection:
        assert connection.execute("SELECT made_ts FROM forecast_checks").fetchall() == [(200.0,)]


def test_checks_never_touch_the_forecast_history(server):
    http, srv = server
    srv.store_count_forecast("j1", counts().encode())
    store_every_step(srv, 2)
    with sqlite3.connect(srv.DATABASE) as connection:
        assert connection.execute("SELECT COUNT(*) FROM count_forecasts").fetchone() == (1,)
    assert len(http.get("/count_forecast/j1/history").json()["rows"]) == 1


def test_posting_needs_the_write_token_and_a_refusal_does_not_echo(server):
    http, srv = server
    from fastapi.testclient import TestClient

    assert TestClient(srv.app).post("/forecast_check/j1", content=check().encode(),
                                    headers=TEXT).status_code in (401, 403)
    bad = json.loads(check().encode())
    bad["classes"]["N"]["forecast"] = MARKER
    refused = http.post("/forecast_check/j1", content=json.dumps(bad), headers=TEXT)
    assert refused.status_code == 422 and MARKER not in refused.text


def test_the_ingest_stores_a_check_and_a_bad_one_does_not_stop_the_others(tmp_path, monkeypatch):
    pytest.importorskip("paho.mqtt")
    import server.app as srv
    from server.mqtt_ingest import PredictionIngest

    monkeypatch.setattr(srv, "DATABASE", tmp_path / "ingest.sqlite")
    receiver = PredictionIngest()
    for payload in (b'{"v": 2, "session": "x"}', check().encode().encode(), counts().encode().encode()):
        topic = "stms/j1/count/forecast" if b"ridge@" in payload and b"made_ts" not in payload \
            else "stms/j1/forecast/check"
        receiver._on_message(None, None, SimpleNamespace(topic=topic, payload=payload))
    assert (receiver.stored, len(receiver.refused), len(receiver.failed)) == (2, 1, 0)
