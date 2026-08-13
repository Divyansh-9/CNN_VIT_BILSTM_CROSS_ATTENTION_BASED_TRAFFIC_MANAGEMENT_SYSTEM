"""Tests for the dual-path encoders and grid alignment (S23, PRD amendment A24).

`pretrained=False` throughout: these assert **geometry**, not representation
quality, and downloading ~200 MB of backbone weights on every CI run would buy
nothing. One test does exercise the real weights and is skipped by default.

    python -m pytest tests/test_encoders.py -q
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch", reason="model tests need torch")
pytest.importorskip("timm", reason="model tests need timm")

import torch.nn as nn  # noqa: E402

from mfstnet.encoders import (  # noqa: E402
    CNNBranch,
    DualPathEncoder,
    EncoderConfig,
    ViTBranch,
)

CFG = EncoderConfig(pretrained=False)


@pytest.fixture(scope="module")
def encoder():
    return DualPathEncoder(CFG)


@pytest.fixture(scope="module")
def batch():
    return torch.randn(2, 3, 224, 224)


# ------------------------------------------------------- the A24 defect --

def test_the_two_backbones_natively_disagree_on_token_count():
    """The defect itself, asserted so nobody 'simplifies' the alignment away.

    Cross-attention returns one output per query, so Z_A carries the CNN's token
    count and Z_B the ViT's. The gate is elementwise. 49 != 257.
    """
    vit = ViTBranch(CFG)
    vit_tokens = vit.native_grid**2 + vit.num_prefix
    cnn_tokens = 7 * 7                      # ResNet-50 stride 32 at 224

    assert vit_tokens == 257, "DINOv2 patch-14 at 224 gives 256 patches + CLS"
    assert cnn_tokens == 49
    assert cnn_tokens != vit_tokens, "if these ever match, this test is obsolete"


def test_dinov2_uses_patch_14_not_16():
    """A12 changed the backbone and with it the geometry. Anything hardcoding
    197 tokens breaks silently."""
    vit = ViTBranch(CFG)
    assert vit.patch_size == 14
    assert vit.native_grid == 16


def test_the_supervised_arm_also_disagreed():
    """BB-1 is the PRD's original pair. The defect predates the DINOv2 switch —
    it was 49 against 197."""
    vit = ViTBranch(EncoderConfig(vit="vit_small_patch16_224", pretrained=False))
    assert vit.patch_size == 16
    assert vit.native_grid**2 + vit.num_prefix == 197
    assert 197 != 49


# ------------------------------------------------------------- alignment --

def test_both_branches_emit_the_same_shape(encoder, batch):
    f_cnn, f_vit = encoder(batch)
    assert f_cnn.shape == f_vit.shape == (2, CFG.tokens, CFG.d_model)


def test_the_gate_can_now_execute(encoder, batch):
    """The whole point of A24: `g·Z_A + (1−g)·Z_B` is elementwise."""
    f_cnn, f_vit = encoder(batch)
    gate = nn.Linear(2 * CFG.d_model, 1)

    g = torch.sigmoid(gate(torch.cat([f_cnn, f_vit], dim=-1)))
    fused = g * f_cnn + (1 - g) * f_vit

    assert fused.shape == f_cnn.shape
    assert torch.isfinite(fused).all()
    assert 0.0 < g.min() and g.max() < 1.0


def test_mismatched_maps_raise_rather_than_broadcast(encoder, batch):
    """A silent broadcast would be worse than a crash. Forced by monkeypatching
    one branch to a different grid."""
    other = CNNBranch(EncoderConfig(grid=14, pretrained=False))
    encoder_bad = DualPathEncoder(CFG)
    encoder_bad.cnn = other

    with pytest.raises(RuntimeError, match="A24"):
        encoder_bad(batch)


# ------------------------------------------------------- spatial structure --

def test_maps_are_returned_for_roi_pooling(encoder, batch):
    """A8 pools per lane, which needs a map. A flat token sequence is not one."""
    cnn_map, vit_map = encoder.forward_maps(batch)
    assert cnn_map.shape == vit_map.shape == (2, CFG.d_model, CFG.grid, CFG.grid)


def test_flattening_is_the_inverse_of_the_map(encoder, batch):
    cnn_map, _ = encoder.forward_maps(batch)
    f_cnn, _ = encoder(batch)
    assert torch.allclose(cnn_map.flatten(2).transpose(1, 2), f_cnn, atol=1e-6)


# ------------------------------------------------------------ config --

@pytest.mark.parametrize("grid", [7, 14])
def test_grid_size_is_configurable(grid, batch):
    """Never hardcode G — attention cost scales as (G²)² and the Week-2 pilots
    decide whether 7 is coarse enough."""
    enc = DualPathEncoder(EncoderConfig(grid=grid, pretrained=False))
    f_cnn, f_vit = enc(batch)
    assert f_cnn.shape == f_vit.shape == (2, grid * grid, CFG.d_model)


def test_backbones_are_frozen_by_default(encoder):
    """ADR-005: the feature cache is only valid while they are."""
    assert not any(p.requires_grad for p in encoder.cnn.backbone.parameters())
    assert not any(p.requires_grad for p in encoder.vit.backbone.parameters())


def test_only_the_projections_train(encoder):
    """Frozen backbones leave the two 1×1 projections. Everything else that
    trains lives downstream in fusion, temporal and the heads."""
    trainable = encoder.trainable_parameters
    total = sum(p.numel() for p in encoder.parameters())
    assert 0 < trainable < 0.05 * total
    assert all(p.requires_grad for p in encoder.cnn.project.parameters())


def test_an_unknown_cnn_backbone_is_rejected():
    with pytest.raises(ValueError, match="unknown CNN backbone"):
        CNNBranch(EncoderConfig(cnn="not_a_model", pretrained=False))


def test_convnext_arm_produces_the_same_geometry(batch):
    """BB-3. Different channel count, same aligned output."""
    enc = DualPathEncoder(EncoderConfig(cnn="convnext_tiny", pretrained=False))
    f_cnn, f_vit = enc(batch)
    assert f_cnn.shape == f_vit.shape == (2, CFG.tokens, CFG.d_model)


# --------------------------------------------------------- real weights --

@pytest.mark.skipif(
    "not config.getoption('--run-pretrained', default=False)",
    reason="downloads ~200 MB; run with --run-pretrained",
)
def test_pretrained_weights_load_and_produce_finite_features(batch):
    enc = DualPathEncoder(EncoderConfig(pretrained=True))
    f_cnn, f_vit = enc(batch)
    assert torch.isfinite(f_cnn).all() and torch.isfinite(f_vit).all()
    assert f_cnn.std() > 0 and f_vit.std() > 0
