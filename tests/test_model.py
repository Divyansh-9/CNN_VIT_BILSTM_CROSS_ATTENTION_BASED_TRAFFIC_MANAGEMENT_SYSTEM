"""Tests for fusion, temporal modelling and the assembled model (S24–S26).

These run on **random cached features**, never on images, which is both what
ADR-005 specifies and what keeps the suite fast enough to sit in CI. Backbone
geometry is tested separately in `test_encoders.py`.

    python -m pytest tests/test_model.py -q
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch", reason="model tests need torch")

import torch.nn.functional as F  # noqa: E402

from mfstnet.corpus.geometry import Polygon  # noqa: E402
from mfstnet.fusion import CrossAttentionFusion, FusionConfig  # noqa: E402
from mfstnet.model import (  # noqa: E402
    ABLATION_CONFIGS,
    MFSTNet,
    MFSTNetConfig,
    ablation_config,
)
from mfstnet.temporal import (  # noqa: E402
    LanePool,
    TemporalConfig,
    TemporalEncoder,
    lane_masks,
)

GRID, D, B, T, LANES = 7, 256, 2, 6, 4

QUADS = (
    Polygon("north", ((0.30, 0.00), (0.70, 0.00), (0.70, 0.45), (0.30, 0.45))),
    Polygon("south", ((0.30, 0.55), (0.70, 0.55), (0.70, 1.00), (0.30, 1.00))),
    Polygon("east", ((0.72, 0.30), (1.00, 0.30), (1.00, 0.70), (0.72, 0.70))),
    Polygon("west", ((0.00, 0.30), (0.28, 0.30), (0.28, 0.70), (0.00, 0.70))),
)


@pytest.fixture(scope="module")
def masks():
    return lane_masks(QUADS, GRID)


@pytest.fixture
def maps():
    torch.manual_seed(0)
    return torch.randn(B, T, D, GRID, GRID), torch.randn(B, T, D, GRID, GRID)


def _build(name, masks):
    return MFSTNet(ablation_config(name), masks)


def _feed(model, cnn, vit):
    return model(
        cnn if model.cfg.fusion.use_cnn else None,
        vit if model.cfg.fusion.use_vit else None,
    )


# --------------------------------------------------------------- fusion --

def test_both_cross_attention_directions_produce_different_outputs():
    """FR-M03. If Z_A and Z_B were equal the second direction would be dead
    weight and the gate would have nothing to arbitrate."""
    torch.manual_seed(0)
    fusion = CrossAttentionFusion(FusionConfig(d_model=D)).eval()
    f_cnn, f_vit = torch.randn(B, 49, D), torch.randn(B, 49, D)

    z_a, _ = fusion.attn_a(query=f_cnn, key=f_vit, value=f_vit, need_weights=False)
    z_b, _ = fusion.attn_b(query=f_vit, key=f_cnn, value=f_cnn, need_weights=False)

    assert not torch.allclose(z_a, z_b, atol=1e-4)


def test_gate_is_returned_and_bounded():
    """BR-07 / FR-M04: the gate is a research artifact, not an internal."""
    fusion = CrossAttentionFusion(FusionConfig(d_model=D, use_gate=True)).eval()
    with torch.no_grad():
        fused, gate = fusion(torch.randn(B, 49, D), torch.randn(B, 49, D))

    assert gate is not None and gate.shape == (B, 49, 1)
    assert 0.0 < float(gate.min()) and float(gate.max()) < 1.0
    assert fused.shape == (B, 49, D)


def test_gate_is_none_when_disabled():
    """Config E is bidirectional without the gate — Phase 1's endpoint."""
    fusion = CrossAttentionFusion(FusionConfig(d_model=D, use_gate=False)).eval()
    _, gate = fusion(torch.randn(B, 49, D), torch.randn(B, 49, D))
    assert gate is None


def test_mismatched_token_counts_raise_the_a24_error():
    fusion = CrossAttentionFusion(FusionConfig(d_model=D))
    with pytest.raises(ValueError, match="A24"):
        fusion(torch.randn(B, 49, D), torch.randn(B, 257, D))


def test_gate_without_bidirectional_is_rejected():
    """The gate arbitrates between two directions. With one there is nothing
    to weigh, and a config that silently ignored the flag would put a wrong
    row in the ablation table."""
    with pytest.raises(ValueError, match="bidirectional"):
        FusionConfig(mode="unidirectional", use_gate=True)


def test_single_branch_cannot_request_fusion():
    with pytest.raises(ValueError, match="needs both branches"):
        FusionConfig(mode="bidirectional", use_vit=False)


def test_no_branch_at_all_is_rejected():
    with pytest.raises(ValueError, match="at least one branch"):
        FusionConfig(use_cnn=False, use_vit=False)


# ------------------------------------------------------- lane ROI pooling --

def test_lane_masks_are_normalised_and_disjoint(masks):
    assert masks.shape == (LANES, GRID, GRID)
    for lane in masks:
        assert float(lane.sum()) == pytest.approx(1.0)
    # No cell is claimed by two lanes.
    assert int(((masks > 0).sum(dim=0) > 1).sum()) == 0


def test_a_lane_covering_no_grid_cell_raises():
    """At G=7 a cell is 1/7 of the frame. A sliver lane pools nothing and would
    predict from noise — silently."""
    sliver = Polygon("sliver", ((0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02)))
    with pytest.raises(ValueError, match="grid cells"):
        lane_masks((sliver,), GRID)


def test_lane_pooling_reads_only_its_own_region(masks):
    """The A8 property. Change the map inside the north lane only; north's
    pooled vector must move and the others must not."""
    pool = LanePool(masks)
    maps = torch.zeros(1, 1, D, GRID, GRID)
    before = pool(maps)

    north_cells = masks[0] > 0
    maps[0, 0, :, north_cells] = 5.0
    after = pool(maps)

    assert not torch.allclose(before[0, 0, 0], after[0, 0, 0])
    for lane in range(1, LANES):
        assert torch.allclose(before[0, 0, lane], after[0, 0, lane])


def test_four_lanes_give_four_different_predictions(masks, maps):
    """Amendment A8's whole reason for existing. PRD §8.1 as written pooled
    globally and applied one shared head four times, which is four identical
    predictions by arithmetic."""
    model = _build("G", masks).eval()
    with torch.no_grad():
        logits = model(*maps).logits[0]

    for lane in range(1, LANES):
        assert not torch.allclose(logits[0], logits[lane], atol=1e-5)


# ------------------------------------------------------------- temporal --

@pytest.mark.parametrize("pooling", ["last", "mean", "attention"])
def test_temporal_encoder_collapses_time(pooling):
    encoder = TemporalEncoder(TemporalConfig(d_model=D, pooling=pooling))
    assert encoder(torch.randn(B, T, D)).shape == (B, D)


def test_bilstm_hidden_width_must_match_d_model():
    """Bidirectional doubles the hidden size. 2x128 = 256 is not a coincidence
    to be edited casually (PRD §8.2)."""
    with pytest.raises(ValueError, match="d_model"):
        TemporalEncoder(TemporalConfig(d_model=256, hidden=64))


def test_temporal_ordering_matters():
    """A model that ignores sequence order cannot forecast. Reversing the
    sequence must change the output — with mean pooling it would not, which is
    exactly why config H is the linear-probe floor and not the full model."""
    torch.manual_seed(0)
    encoder = TemporalEncoder(TemporalConfig(d_model=D, pooling="last")).eval()
    x = torch.randn(1, T, D)
    with torch.no_grad():
        assert not torch.allclose(encoder(x), encoder(x.flip(1)), atol=1e-5)


# ----------------------------------------------------- ablation harness --

@pytest.mark.parametrize("name", ABLATION_CONFIGS)
def test_every_ablation_config_runs_from_config_alone(name, masks, maps):
    """NFR-15. All eight rows of §14.4 with no code edit between them."""
    model = _build(name, masks).eval()
    with torch.no_grad():
        out = _feed(model, *maps)

    assert out.logits.shape == (B, LANES, 3)
    assert torch.isfinite(out.logits).all()


@pytest.mark.parametrize("name", ABLATION_CONFIGS)
def test_every_config_has_gradients_everywhere(name, masks, maps):
    """A parameter with no gradient is a module silently doing nothing."""
    model = _build(name, masks).train()
    out = _feed(model, *maps)
    F.cross_entropy(out.logits.reshape(-1, 3), torch.randint(0, 3, (B * LANES,))).backward()

    dead = [
        n for n, p in model.named_parameters()
        if p.requires_grad and (p.grad is None or float(p.grad.abs().sum()) == 0.0)
    ]
    assert not dead, f"config {name} has parameters receiving no gradient: {dead}"


def test_only_config_g_exposes_a_gate(masks, maps):
    """§14.4 puts the gate in G alone. If another config produced one, the
    ablation would not isolate its contribution."""
    for name in ABLATION_CONFIGS:
        model = _build(name, masks).eval()
        with torch.no_grad():
            out = _feed(model, *maps)
        if name == "G":
            assert out.gate is not None and out.gate_mean is not None
        else:
            assert out.gate is None, f"config {name} produced a gate"


def test_config_h_is_genuinely_a_linear_probe(masks):
    """A22. No recurrence, no attention, no hidden layer — otherwise it is not
    the floor it claims to be and 'H approaches G' would mean nothing."""
    cfg = ablation_config("H")
    assert cfg.temporal.use_bilstm is False
    assert cfg.temporal.use_temporal_attn is False
    assert cfg.temporal.pooling == "mean"
    assert cfg.head_hidden == 0

    probe = MFSTNet(cfg, masks)
    full = MFSTNet(ablation_config("G"), masks)
    assert probe.trainable_parameters < 0.25 * full.trainable_parameters


def test_configs_grow_monotonically_in_capacity(masks):
    """C < D < E < F < G. Not a law of nature, but if it ever breaks the table
    is mislabelled and every comparison in §14.4 is suspect."""
    sizes = [
        MFSTNet(ablation_config(n), masks).trainable_parameters
        for n in ("C", "D", "E", "F", "G")
    ]
    assert sizes == sorted(sizes)


def test_unknown_config_name_is_rejected():
    with pytest.raises(ValueError, match="unknown ablation config"):
        ablation_config("Z")


# ----------------------------------------------------- input contracts --

def test_passing_features_for_a_disabled_branch_raises(masks, maps):
    """Config A is CNN-only. Accepting ViT features and ignoring them would make
    the ablation table describe a model that was never run."""
    model = _build("A", masks)
    with pytest.raises(ValueError, match="disables the ViT branch"):
        model(maps[0], maps[1])


def test_missing_features_for_an_enabled_branch_raises(masks, maps):
    model = _build("E", masks)
    with pytest.raises(ValueError, match="no ViT features"):
        model(maps[0], None)


def test_two_caches_of_different_shape_raise(masks, maps):
    """ADR-005: a cache is invalidated by any change to backbone, resize or
    normalisation. Different shapes are the visible half of that."""
    model = _build("E", masks)
    with pytest.raises(ValueError, match="preprocessing_hash"):
        model(maps[0], torch.randn(B, T, D, 14, 14))


def test_lane_mask_count_must_match_the_config(masks):
    cfg = MFSTNetConfig(n_lanes=6)
    with pytest.raises(ValueError, match="6 lanes"):
        MFSTNet(cfg, masks)


def test_lane_masks_must_match_the_encoder_grid():
    coarse = lane_masks(QUADS, 14)
    with pytest.raises(ValueError, match="grid"):
        MFSTNet(MFSTNetConfig(), coarse)


def test_d_model_must_agree_across_stages():
    with pytest.raises(ValueError, match="d_model disagrees"):
        MFSTNetConfig(temporal=TemporalConfig(d_model=128, hidden=64))


# ------------------------------------------------------ determinism --

def test_two_builds_with_the_same_seed_are_identical(masks, maps):
    """NFR-07. Verified on the assembled model, not just on `set_seed`."""
    from scripts.seed import set_seed

    outputs = []
    for _ in range(2):
        set_seed(42)
        model = _build("G", masks).eval()
        with torch.no_grad():
            outputs.append(model(*maps).logits)

    assert torch.equal(outputs[0], outputs[1])
