"""The edge serves only a verified graph, mapped to approaches explicitly (ADR-026)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edge.forecaster import DeploymentError, VerifiedGraph  # noqa: E402


def graph(tmp_path, *, passed=True, tamper=False, sidecar=True) -> Path:
    path = tmp_path / "g.onnx"
    path.write_bytes(b"graph bytes")
    if sidecar:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".provenance.json").write_text(json.dumps({
            "passed": passed, "graph_sha256": digest, "config": "G",
            "lane_names": ["lane_0", "lane_1", "lane_2", "lane_3"]}))
    if tamper:
        path.write_bytes(b"a different, untrained graph")
    return path


def test_a_verified_graph_loads_and_names_itself_by_content(tmp_path):
    loaded = VerifiedGraph.load(graph(tmp_path))
    assert loaded.model_id.startswith("G@")
    assert len(loaded.model_id) == len("G@") + 12


def test_a_graph_without_a_sidecar_is_refused(tmp_path):
    with pytest.raises(DeploymentError, match="no provenance"):
        VerifiedGraph.load(graph(tmp_path, sidecar=False))


def test_a_graph_that_failed_verification_is_refused(tmp_path):
    with pytest.raises(DeploymentError, match="did not pass"):
        VerifiedGraph.load(graph(tmp_path, passed=False))


def test_a_graph_replaced_after_verification_is_refused(tmp_path):
    """An untrained export runs as cleanly as a trained one (P87); the hash
    is what ties the served bytes to the ones that were checked."""
    with pytest.raises(DeploymentError, match="replaced after verification"):
        VerifiedGraph.load(graph(tmp_path, tamper=True))


@pytest.mark.parametrize("mapping, match", [
    ({"lane_0": "N", "lane_1": "S", "lane_2": "E"}, "Every lane"),
    ({"lane_0": "N", "lane_1": "N", "lane_2": "E", "lane_3": "W"}, "distinct"),
    ({"lane_0": "N", "lane_1": "S", "lane_2": "E", "lane_3": "X"}, "distinct"),
])
def test_lane_to_approach_must_be_complete_and_one_to_one(tmp_path, mapping,
                                                          match):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("torch")
    from edge.forecaster import EdgeForecaster

    with pytest.raises(DeploymentError, match=match):
        EdgeForecaster(VerifiedGraph.load(graph(tmp_path)), mapping,
                       timesteps=60)


def test_the_heartbeat_reports_forecasting_from_what_was_published():
    from contracts.mqtt import CongestionClass, CongestionPrediction
    from edge.node import EdgeNode, RecordingTransport

    node = EdgeNode(intersection_id="j1", transport=RecordingTransport())
    assert node.forecasting is False
    node.publish_prediction(CongestionPrediction(
        predictions={"N": CongestionClass.HIGH}, confidences={"N": 0.8},
        gate_value=0.5, model="G@0123456789ab"))
    assert node.forecasting is True
    assert node.transport.sent[-1][0] == "stms/j1/congestion/prediction"
