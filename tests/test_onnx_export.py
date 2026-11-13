"""The exported graph must compute what the PyTorch model computes, and expose
the gate.

The gate is a research artifact, not an internal detail: it is logged, tracked
on the dashboard (FR-UI05) and analysed in the paper. A graph that dropped it
would still serve predictions, still hit the latency budget, and quietly remove
the thing the architecture chapter is about -- so it is asserted here rather
than assumed.

`T` is small in these tests. Sixty timesteps is the deployed window (PRD §8.2)
and is what `export_onnx.py` defaults to; the properties being checked -- graph
parity, which inputs exist, whether the gate comes out -- do not depend on it,
and exporting eight graphs at T=60 in a unit test would not pay for itself.
"""

from __future__ import annotations

import pytest

pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")

from mfstnet.model import ablation_config, iter_ablation_configs  # noqa: E402
from scripts.export_onnx import build_wrapper, export_one, sample_inputs  # noqa: E402

T = 4


def wrapper_for(name):
    import torch

    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.model import MFSTNet
    from mfstnet.temporal import lane_masks_from_centres

    config = ablation_config(name)
    centres = LaneCentres(
        names=tuple(f"lane_{i}" for i in range(config.n_lanes)),
        centres=tuple((0.2 + 0.2 * i, 0.5) for i in range(config.n_lanes)),
        max_radius=0.25,
    )
    masks = lane_masks_from_centres(centres, config.encoder.grid)
    model = MFSTNet(config, masks).eval()
    wrapped = build_wrapper(model, use_cnn=config.fusion.use_cnn,
                            use_vit=config.fusion.use_vit)
    made = sample_inputs(config, batch=1, timesteps=T)
    return config, wrapped, made


def test_a_disabled_branch_is_absent_from_the_inputs():
    """ONNX has no null. A zero tensor for a disabled branch would export a
    graph computing something the config says it does not."""
    for name in ("A", "B"):
        config, _, made = wrapper_for(name)
        assert ("cnn_maps" in made) == config.fusion.use_cnn
        assert ("vit_maps" in made) == config.fusion.use_vit
        assert len(made) == 1


def test_both_branches_present_when_the_config_fuses():
    _, _, made = wrapper_for("G")
    assert set(made) == {"cnn_maps", "vit_maps"}


def test_a_gated_config_returns_its_gate():
    """FR-UI05. Never discard it from the forward pass."""
    import torch

    _, wrapped, made = wrapper_for("G")
    with torch.no_grad():
        out = wrapped(*made.values())
    assert len(out) == 2, "config G fuses with a gate and must return it"
    assert out[1] is not None


def test_an_ungated_config_returns_only_logits():
    """H is the linear probe (A22): no fusion, so no gate to report."""
    import torch

    _, wrapped, made = wrapper_for("H")
    with torch.no_grad():
        out = wrapped(*made.values())
    assert len(out) == 1


def test_logits_are_per_lane_and_per_class():
    import torch

    config, wrapped, made = wrapper_for("G")
    with torch.no_grad():
        logits = wrapped(*made.values())[0]
    assert tuple(logits.shape) == (1, config.n_lanes, config.n_classes)


@pytest.mark.parametrize("name", ["H", "G"])
def test_onnx_matches_torch(tmp_path, name):
    row = export_one(name, out_dir=tmp_path, batch=1, timesteps=T, opset=18)
    drift = float(row["onnx_vs_torch_max_abs"])
    assert drift < 1e-4, f"{name}: ONNX and PyTorch disagree by {drift:.2e}"


def test_the_exported_row_records_whether_the_gate_survived(tmp_path):
    gated = export_one("G", out_dir=tmp_path, batch=1, timesteps=T, opset=18)
    probe = export_one("H", out_dir=tmp_path, batch=1, timesteps=T, opset=18)
    assert gated["exposes_gate"] is True
    assert probe["exposes_gate"] is False


def test_the_graph_file_is_written(tmp_path):
    row = export_one("H", out_dir=tmp_path, batch=1, timesteps=T, opset=18)
    assert (tmp_path / "mfstnet_H.onnx").is_file()
    assert row["size_mb"] > 0


def test_batch_axis_is_dynamic(tmp_path):
    """A server predicts one intersection at a time, but the graph must not
    hard-code that -- the ablation harness scores in batches."""
    import numpy as np
    import onnxruntime

    export_one("H", out_dir=tmp_path, batch=1, timesteps=T, opset=18)
    session = onnxruntime.InferenceSession(
        str(tmp_path / "mfstnet_H.onnx"), providers=["CPUExecutionProvider"])
    config = ablation_config("H")
    feed = {"vit_maps" if not config.fusion.use_cnn else "cnn_maps": None}
    made = sample_inputs(config, batch=4, timesteps=T)
    got = session.run(None, {k: v.numpy() for k, v in made.items()})
    assert got[0].shape[0] == 4


def test_every_ablation_config_can_be_exported(tmp_path):
    """NFR-15. A config that cannot leave the training harness is not deployable,
    and the ablation table would then compare things of different kinds."""
    failed = []
    for config in iter_ablation_configs():
        try:
            export_one(config.name, out_dir=tmp_path, batch=1, timesteps=T,
                       opset=18)
        except Exception as error:                       # noqa: BLE001
            failed.append(f"{config.name}: {type(error).__name__} {error}")
    assert not failed, "configs that will not export: " + "; ".join(failed)
