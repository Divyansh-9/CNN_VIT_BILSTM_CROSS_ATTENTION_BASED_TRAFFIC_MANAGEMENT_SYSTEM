"""The edge serves only a verified graph, mapped to approaches explicitly (ADR-026)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edge.forecaster import DeploymentError, VerifiedGraph  # noqa: E402


def graph(tmp_path, *, passed=True, tamper=False, sidecar=True,
          tamper_weights=False, legacy=False) -> Path:
    """A real two-file ONNX model: the graph, and its weights stored
    externally in `g.onnx.data`, the way torch's exporter writes MFSTNet."""
    onnx = pytest.importorskip("onnx")
    import numpy as np
    from onnx import TensorProto, helper, numpy_helper

    from mfstnet.onnx_files import file_hashes

    weight = numpy_helper.from_array(np.ones((64, 64), np.float32), "w")
    node = helper.make_node("MatMul", ["x", "w"], ["y"])
    model = helper.make_model(helper.make_graph(
        [node], "g",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 64])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 64])],
        initializer=[weight]))
    path = tmp_path / "g.onnx"
    onnx.save_model(model, str(path), save_as_external_data=True,
                    all_tensors_to_one_file=True, location="g.onnx.data",
                    size_threshold=0)
    if sidecar:
        record = {"passed": passed, "config": "G",
                  "graph_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "lane_names": ["lane_0", "lane_1", "lane_2", "lane_3"]}
        if not legacy:
            record["files_sha256"] = file_hashes(path)
        path.with_suffix(".provenance.json").write_text(json.dumps(record))
    if tamper:
        path.write_bytes(path.read_bytes() + b"tampered")
    if tamper_weights:
        data = tmp_path / "g.onnx.data"
        data.write_bytes(bytes(len(data.read_bytes())))     # untrained zeros
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


def test_weights_replaced_after_verification_are_refused(tmp_path):
    """P90. The graph file is untouched and only its external weights are
    swapped — exactly what a graph-only hash would have let through."""
    with pytest.raises(DeploymentError, match="g.onnx.data"):
        VerifiedGraph.load(graph(tmp_path, tamper_weights=True))


def test_a_sidecar_without_per_file_hashes_is_refused(tmp_path):
    with pytest.raises(DeploymentError, match="P90"):
        VerifiedGraph.load(graph(tmp_path, legacy=True))


def test_a_missing_weights_file_is_refused(tmp_path):
    path = graph(tmp_path)
    (tmp_path / "g.onnx.data").unlink()
    with pytest.raises(DeploymentError, match="missing"):
        VerifiedGraph.load(path)


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
