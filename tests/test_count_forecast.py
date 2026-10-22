"""ADR-027: the next-minute count forecast, kept apart from the class forecast.

P105 measured the frozen ridge model as a better count forecaster than
persistence on untouched footage, and the project owner gave it that role
only. These tests pin what makes the served forecaster the measured one, and
what keeps the count from being read as a class, served stale, or filled in
with zeros.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import (ContractError, CongestionClass, CongestionPrediction,  # noqa: E402
                            CountForecast, QoS, Topic, decode)
from edge.count_forecast import RidgeCountForecaster, change_features  # noqa: E402
from edge.node import EdgeNode, RecordingTransport  # noqa: E402
from edge.samples import SampleError  # noqa: E402

SPEC = Path("experiments/results/bellevue_pilot/p105_ridge_v1.json")

# V3: Bellevue-derived files are absent from the sanitised public tree; the tests
# that read them skip there, and run everywhere the files exist.
needs_bellevue = pytest.mark.skipif(not SPEC.exists(),
                                     reason="Bellevue-derived file absent (public tree)")
MAPPING = {"lane_0": "W", "lane_1": "N", "lane_2": "E"}


def series(seed=0, n=200):
    rng = random.Random(seed)
    level, out = 4.0, []
    for i in range(n):
        level = max(0.0, level + rng.gauss(0, 0.3))
        out.append(max(0, int(rng.gauss(level + 2 * ((i // 30) % 2), 1))))
    return out


def fill(forecaster, values, *, ts0=0.0):
    out = None
    for i, v in enumerate(values):
        out = forecaster.step({lane: v for lane in MAPPING}, ts=ts0 + 2.0 * i)
    return out


# ------------------------------------------------------------ the method --

def test_features_are_p105s_features():
    # The P105 pipeline script is absent from the public copy (P136); skip there.
    scored = pytest.importorskip("scripts.p105_freeze").change_features

    v = series()
    for s in (0, 37, 120):
        assert change_features(v[s:s + 60]) == pytest.approx(scored(v, s), abs=1e-12)


@needs_bellevue
def test_the_forecast_is_p105s_forecast():
    recent_mean = pytest.importorskip("scripts.p105_freeze").recent_mean

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    v = series(seed=4)
    f = RidgeCountForecaster(SPEC, MAPPING)
    out = fill(f, v[:60])
    delta = sum(c * x for c, x in zip(spec["coef"], change_features(v[:60])))
    assert out.counts["W"] == pytest.approx(max(0.0, recent_mean(v, 59) + delta), abs=1e-4)
    assert out.model == "ridge@" + "73532968dcf2"


@needs_bellevue
def test_only_the_frozen_spec_is_served(tmp_path):
    tampered = tmp_path / "ridge.json"
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec["coef"][0] += 0.01
    tampered.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen"):
        RidgeCountForecaster(tampered, MAPPING)


# ---------------------------------------------------- operational checks --

@needs_bellevue
def test_no_forecast_from_less_than_two_minutes():
    f = RidgeCountForecaster(SPEC, MAPPING)
    assert fill(f, [3] * 59) is None
    assert f.step({lane: 3 for lane in MAPPING}, ts=118.0) is not None


@needs_bellevue
def test_a_gap_resets_the_window_instead_of_joining_two_stretches():
    f = RidgeCountForecaster(SPEC, MAPPING)
    fill(f, [3] * 60)
    assert f.ready
    f.step({lane: 3 for lane in MAPPING}, ts=118.0 + 10.0)     # a 10 s dropout
    assert not f.ready and "gap" in f.buffer.last_reset_reason


@needs_bellevue
def test_out_of_order_samples_are_refused():
    f = RidgeCountForecaster(SPEC, MAPPING)
    f.step({lane: 1 for lane in MAPPING}, ts=10.0)
    with pytest.raises(SampleError, match="not after"):
        f.step({lane: 1 for lane in MAPPING}, ts=9.0)


@pytest.mark.parametrize("bad", [{"lane_0": 1, "lane_1": 1},                 # a lane missing
                                 {"lane_0": -1, "lane_1": 1, "lane_2": 1},   # negative
                                 {"lane_0": 1.5, "lane_1": 1, "lane_2": 1},  # not a count
                                 {"lane_0": 999, "lane_1": 1, "lane_2": 1}]) # impossible
@needs_bellevue
def test_implausible_or_incomplete_samples_are_refused(bad):
    with pytest.raises(SampleError):
        RidgeCountForecaster(SPEC, MAPPING).step(bad, ts=0.0)


# ---------------------------------------------------------- the contract --

@pytest.mark.parametrize("counts, model", [({"N": -0.1}, "ridge@0123456789ab"),
                                           ({"N": math.nan}, "ridge@0123456789ab"),
                                           ({"N": 500.0}, "ridge@0123456789ab"),
                                           ({}, "ridge@0123456789ab"),
                                           ({"X": 1.0}, "ridge@0123456789ab"),
                                           ({"N": 1.0}, "persistence@0123456789ab"),
                                           ({"N": 1.0}, "G@0123456789ab")])
def test_the_count_contract_refuses_what_it_must(counts, model):
    with pytest.raises(ContractError):
        CountForecast(counts=counts, model=model)


def test_a_class_forecast_cannot_be_named_as_the_count_model():
    with pytest.raises(ContractError):
        CongestionPrediction(predictions={"N": CongestionClass.LOW}, confidences={"N": 0.5},
                             gate_value=None, model="ridge@0123456789ab")


def test_the_count_travels_on_its_own_topic_and_never_reads_as_mfstnet():
    transport = RecordingTransport()
    node = EdgeNode("j9", transport)
    forecast = CountForecast(counts={"N": 2.25}, model="ridge@0123456789ab")
    assert node.publish_count_forecast(forecast, now=1.0)
    topic, payload, qos = transport.sent[-1]
    assert topic == "stms/j9/count/forecast" and qos == Topic.COUNT_FORECAST.qos == QoS.AT_MOST_ONCE
    assert decode(Topic.COUNT_FORECAST, payload).counts == {"N": 2.25}
    assert node.forecasting is False


# ------------------------------------------------------------ the server --

@pytest.fixture
def client(tmp_path, monkeypatch, write_headers):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "count.sqlite")
    return TestClient(server.app, headers=write_headers), server


def test_the_server_keeps_count_and_class_apart_and_lists_absences(client):
    http, _ = client
    forecast = CountForecast(counts={"N": 1.5, "E": 0.0}, model="ridge@0123456789ab")
    assert http.post("/count_forecast/j1", content=forecast.encode(),
                     headers={"content-type": "text/plain"}).status_code == 200
    latest = http.get("/count_forecast/j1/latest").json()
    assert latest["role"] == "next_minute_count (ridge)"
    assert latest["counts"] == {"N": 1.5, "E": 0.0}            # a real zero stays a zero
    assert latest["missing_approaches"] == ["S", "W"]           # absent stays absent
    assert latest["stale"] is False
    assert http.get("/prediction/j1/latest").status_code == 404  # no class was sent


def test_a_forecast_older_than_its_horizon_is_labelled_stale(client):
    _, server = client
    assert server.freshness(100.0, 60, now=150.0) == {"age_s": 50.0, "stale": False}
    assert server.freshness(100.0, 60, now=161.0) == {"age_s": 61.0, "stale": True}


def test_the_ingest_routes_each_topic_to_its_own_store():
    from server.mqtt_ingest import intersection_of, route

    assert route("stms/j1/count/forecast") == ("j1", Topic.COUNT_FORECAST)
    assert route("stms/j1/congestion/prediction") == ("j1", Topic.PREDICTION)
    assert intersection_of("stms/j1/congestion/prediction") == "j1"
    with pytest.raises(ContractError):
        intersection_of("stms/j1/count/forecast")
    with pytest.raises(ContractError):
        route("stms/j1/system/heartbeat")
