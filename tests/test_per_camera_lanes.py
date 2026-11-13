"""Per-camera lane geometry — P26.

A corpus spans cameras, and a lane lives in ONE camera's image plane (P17).
The model was built with a single `[L, G, G]` mask buffer applied to every
sequence, so in a multi-camera corpus every camera but one was pooled through
somebody else's lanes. Nothing raised: the shapes agree, the loss falls, and
the numbers look ordinary.

These pin the fix at both ends — the model accepting geometry as an input, and
the corpus recording one set per camera rather than one for all of them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

torch = pytest.importorskip("torch")

from mfstnet.temporal import LanePool


def corner_masks(grid: int, corners: list[tuple[int, int]]) -> "torch.Tensor":
    """One-hot mask per lane at the given cell, so pooling is exactly readable."""
    masks = torch.zeros(len(corners), grid, grid)
    for i, (r, c) in enumerate(corners):
        masks[i, r, c] = 1.0
    return masks


def test_shared_masks_still_pool_the_same_way():
    """The single-camera path is unchanged — the fix must not move it."""
    pool = LanePool(corner_masks(4, [(0, 0), (3, 3)]))
    maps = torch.arange(2 * 1 * 3 * 4 * 4, dtype=torch.float32).reshape(2, 1, 3, 4, 4)
    out = pool(maps)
    assert out.shape == (2, 1, 2, 3)
    assert out[0, 0, 0].tolist() == maps[0, 0, :, 0, 0].tolist()
    assert out[0, 0, 1].tolist() == maps[0, 0, :, 3, 3].tolist()


def test_per_sample_masks_pool_each_item_through_its_own_geometry():
    """The defect, at the level it actually occurs. Two items in one batch, two
    different cameras, two different lane positions."""
    pool = LanePool(corner_masks(4, [(0, 0), (3, 3)]))
    maps = torch.arange(2 * 1 * 3 * 4 * 4, dtype=torch.float32).reshape(2, 1, 3, 4, 4)

    # item 0 keeps the shared geometry; item 1's lanes sit elsewhere entirely.
    per_sample = torch.stack([
        corner_masks(4, [(0, 0), (3, 3)]),
        corner_masks(4, [(1, 2), (2, 1)]),
    ])
    out = pool(maps, per_sample)

    assert out.shape == (2, 1, 2, 3)
    assert out[0, 0, 0].tolist() == maps[0, 0, :, 0, 0].tolist()
    assert out[1, 0, 0].tolist() == maps[1, 0, :, 1, 2].tolist()
    assert out[1, 0, 1].tolist() == maps[1, 0, :, 2, 1].tolist()


def test_per_sample_masks_differ_from_shared_masks():
    """If these agreed, the bug would have been harmless and the fix pointless."""
    pool = LanePool(corner_masks(4, [(0, 0), (3, 3)]))
    maps = torch.randn(2, 1, 3, 4, 4)
    wrong = pool(maps)
    right = pool(maps, torch.stack([
        corner_masks(4, [(0, 0), (3, 3)]),
        corner_masks(4, [(1, 2), (2, 1)]),
    ]))
    assert not torch.allclose(wrong[1], right[1])
    assert torch.allclose(wrong[0], right[0])      # item 0 unchanged


def test_a_batch_of_masks_must_match_the_batch():
    pool = LanePool(corner_masks(4, [(0, 0), (3, 3)]))
    maps = torch.randn(2, 1, 3, 4, 4)
    with pytest.raises(ValueError, match="batch"):
        pool(maps, torch.stack([corner_masks(4, [(0, 0), (3, 3)])]))   # 1 vs 2


def test_masks_with_the_wrong_lane_count_raise():
    pool = LanePool(corner_masks(4, [(0, 0), (3, 3)]))
    maps = torch.randn(2, 1, 3, 4, 4)
    three = torch.stack([corner_masks(4, [(0, 0), (3, 3), (1, 1)])] * 2)
    with pytest.raises(ValueError, match="lane"):
        pool(maps, three)


def test_model_forward_takes_geometry_as_an_input():
    """End to end: the same features under two geometries must not agree."""
    from mfstnet.model import MFSTNet, MFSTNetConfig

    cfg = MFSTNetConfig(n_lanes=2)
    grid = cfg.encoder.grid
    model = MFSTNet(cfg, corner_masks(grid, [(0, 0), (grid - 1, grid - 1)])).eval()

    d_cnn = model.cfg.encoder.cnn_channels
    d_vit = model.cfg.encoder.vit_channels
    cnn = torch.randn(2, 3, d_cnn, grid, grid)
    vit = torch.randn(2, 3, d_vit, grid, grid)

    with torch.no_grad():
        shared = model(cnn, vit).logits
        moved = model(cnn, vit, lane_masks=torch.stack([
            corner_masks(grid, [(0, 0), (grid - 1, grid - 1)]),
            corner_masks(grid, [(1, 2), (2, 1)]),
        ])).logits

    assert shared.shape == moved.shape == (2, 2, cfg.n_classes)
    assert torch.allclose(shared[0], moved[0], atol=1e-5)
    assert not torch.allclose(shared[1], moved[1], atol=1e-5)


# --------------------------------------------------------------- corpus side --

def write_lane_file(directory: Path, clip: str, centres: list[tuple[float, float]],
                    reviewed: bool = True) -> None:
    import json

    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{clip.replace('.', '_')}.json").write_text(json.dumps({
        "clip": clip, "reviewed": reviewed,
        "lanes": [{"name": f"lane_{i}", "centre": list(c)}
                  for i, c in enumerate(centres)],
    }), encoding="utf-8")


def test_cameras_may_have_different_positions(tmp_path):
    """The normal case, and the whole reason geometry is per camera."""
    from scripts.build_corpus import load_reviewed_lanes

    write_lane_file(tmp_path, "a.mp4", [(0.2, 0.5), (0.7, 0.5)])
    write_lane_file(tmp_path, "b.mp4", [(0.4, 0.8), (0.5, 0.3)])
    lanes = load_reviewed_lanes(tmp_path)

    assert set(lanes) == {"a.mp4", "b.mp4"}
    assert lanes["a.mp4"].centres != lanes["b.mp4"].centres


def test_cameras_may_not_disagree_on_lane_count(tmp_path):
    """P26. The head is built once at a fixed width, so a ragged corpus cannot
    train — and it must say so here, naming the cameras, rather than surfacing
    as a shape error deep inside the first epoch."""
    from scripts.build_corpus import load_reviewed_lanes

    write_lane_file(tmp_path, "two.mp4", [(0.2, 0.5), (0.7, 0.5)])
    write_lane_file(tmp_path, "four.mp4",
                    [(0.2, 0.5), (0.7, 0.5), (0.4, 0.2), (0.5, 0.8)])

    with pytest.raises(SystemExit, match="disagree on lane count"):
        load_reviewed_lanes(tmp_path)


def test_unreviewed_lanes_are_still_refused(tmp_path):
    """P23 — automatic centres move 0.164 of frame width between detectors."""
    from scripts.build_corpus import load_reviewed_lanes

    write_lane_file(tmp_path, "a.mp4", [(0.2, 0.5), (0.7, 0.5)], reviewed=False)
    with pytest.raises(SystemExit, match="not reviewed"):
        load_reviewed_lanes(tmp_path)


def test_two_cameras_produce_different_roi_masks():
    """The consequence the manifest fix exists to prevent: if these agreed,
    pooling every camera through one set would have been harmless."""
    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.temporal import lane_masks_from_centres

    a = LaneCentres(names=("lane_0", "lane_1"),
                    centres=((0.2, 0.5), (0.7, 0.5)), max_radius=0.4)
    b = LaneCentres(names=("lane_0", "lane_1"),
                    centres=((0.4, 0.15), (0.5, 0.85)), max_radius=0.4)

    ma, mb = lane_masks_from_centres(a, 7), lane_masks_from_centres(b, 7)
    assert ma.shape == mb.shape == (2, 7, 7)
    assert not torch.allclose(ma, mb)
