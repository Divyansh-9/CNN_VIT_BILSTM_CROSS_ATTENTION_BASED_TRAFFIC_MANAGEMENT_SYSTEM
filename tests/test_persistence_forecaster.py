"""Persistence on the edge (P104): the scored method, the frozen spec, the contract.

P103 measured persistence as the best transferable forecaster and the project
owner adopted it for the prototype. These tests pin what makes the served
forecaster the same thing that was measured: the window, the full-precision
boundaries, the spec-derived model id, and that it never reads as MFSTNet.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.mqtt import (CongestionClass, CongestionPrediction, ContractError,  # noqa: E402
                           Topic, decode)
from edge.node import EdgeNode, RecordingTransport  # noqa: E402
from edge.persistence import WINDOW, PersistenceForecaster, calibrate, classify, load_spec  # noqa: E402

SPEC = Path("experiments/results/bellevue_pilot/persistence_v1.json")

# V3: Bellevue-derived files are absent from the sanitised public tree; the tests
# that read them skip there, and run everywhere the files exist.
needs_bellevue = pytest.mark.skipif(not SPEC.exists(),
                                     reason="Bellevue-derived file absent (public tree)")
MAPPING = {"lane_0": "W", "lane_1": "N", "lane_2": "E", "lane_3": "S"}


def forecaster(camera="150th_Newport"):
    return PersistenceForecaster(SPEC, camera, MAPPING)


@needs_bellevue
def test_it_waits_for_a_full_minute():
    f = forecaster()
    for _ in range(WINDOW - 1):
        assert f.step({lane: 1 for lane in MAPPING}) is None
    assert f.step({lane: 1 for lane in MAPPING}) is not None


@needs_bellevue
def test_the_forecast_is_the_class_of_the_last_minutes_mean():
    f = forecaster()
    spec, _ = load_spec(SPEC)
    low, med = spec["cameras"]["150th_Newport"]["low"], spec["cameras"]["150th_Newport"]["med"]
    for i in range(WINDOW + 10):          # older samples must fall out of the window
        f.step({"lane_0": 50 if i < 10 else 0, "lane_1": 1, "lane_2": 2, "lane_3": 9})
    out = f.predict()
    assert out.predictions["W"] == classify(0.0, low, med) == CongestionClass.LOW
    assert out.predictions["N"] == classify(1.0, low, med)
    assert out.predictions["S"] == CongestionClass.HIGH


@needs_bellevue
def test_a_boundary_mean_is_classed_at_full_precision():
    # Newport's q33 is 0.5333…; a mean of 16/30 sits exactly on it and is LOW.
    # P103 found a four-decimal threshold (0.5333) moved such decisions up a class.
    spec, _ = load_spec(SPEC)
    low = spec["cameras"]["150th_Newport"]["low"]
    assert low == 16 / 30
    f = forecaster()
    for i in range(WINDOW):
        f.step({"lane_0": 1 if i < 16 else 0, "lane_1": 0, "lane_2": 0, "lane_3": 0})
    assert f.predict().predictions["W"] == CongestionClass.LOW


@needs_bellevue
def test_the_model_id_names_the_frozen_spec_and_passes_the_contract():
    out = forecaster()
    for _ in range(WINDOW):
        out.step({lane: 3 for lane in MAPPING})
    prediction = out.predict()
    assert prediction.model.startswith("persistence@") and len(prediction.model) == 24
    assert prediction.gate_value is None
    assert decode(Topic.PREDICTION, prediction.encode()).model == prediction.model


def test_the_contract_still_refuses_any_other_model_name():
    for bad in ("persistance@0123456789ab", "persistence@xyz", "I@0123456789ab", "persistence"):
        with pytest.raises(ContractError):
            CongestionPrediction(predictions={"N": CongestionClass.LOW},
                                 confidences={"N": 0.5}, gate_value=None, model=bad)


@needs_bellevue
def test_confidence_is_the_measured_precision_of_the_called_class():
    spec, _ = load_spec(SPEC)
    f = forecaster()
    for _ in range(WINDOW):
        f.step({lane: 0 for lane in MAPPING})
    out = f.predict()
    assert out.confidences["N"] == spec["confidence_is_measured_precision"]["LOW"]


@needs_bellevue
def test_a_persistence_forecast_never_reads_as_mfstnet_active():
    node = EdgeNode("junction-1", RecordingTransport())
    f = forecaster()
    for _ in range(WINDOW):
        f.step({lane: 2 for lane in MAPPING})
    assert node.publish_prediction(f.predict(), now=1.0)
    assert node.forecasting is False


@needs_bellevue
def test_an_uncalibrated_camera_is_refused():
    with pytest.raises(ValueError, match="calibrate"):
        PersistenceForecaster(SPEC, "116th_NE12th", MAPPING)


def test_calibrate_is_q33_q67_at_full_precision():
    low, med = calibrate([i / 30 for i in range(31)])
    assert (low, med) == pytest.approx((0.33, 0.67))
    assert isinstance(low, float)


@needs_bellevue
@pytest.mark.skipif(not Path("data/corpus_p103").is_dir(), reason="needs the local P103 corpus")
def test_it_reproduces_p103s_persistence_decisions():
    from scripts import p103_eval as ev

    windows = json.loads(Path("experiments/results/bellevue_pilot/p103_test_windows.json")
                         .read_text(encoding="utf-8"))
    spec, _ = load_spec(SPEC)
    for camera in ev.CAMERAS:
        counts, lanes = ev.load(camera)
        mine = [w for w in windows if w["camera"] == camera][:40]
        entry = spec["cameras"][camera]
        for w in mine:
            e = w["start"] + 59
            series = counts[w["clip"]]
            for j in range(len(lanes)):
                mean = sum(series[x][j] for x in range(e - WINDOW + 1, e + 1)) / WINDOW
                got = ["LOW", "MEDIUM", "HIGH"].index(classify(mean, entry["low"], entry["med"]).name)
                # P103 scored with four-decimal thresholds; only exact-boundary means may differ.
                if got != w["persistence"][j]:
                    assert abs(mean - entry["low"]) < 1e-9 or abs(mean - entry["med"]) < 1e-9
