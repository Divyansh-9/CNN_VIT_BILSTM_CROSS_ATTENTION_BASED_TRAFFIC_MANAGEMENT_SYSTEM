"""Tests for the frozen-feature cache (S27, ADR-005, SOW R20).

The behaviour under test is mostly *refusal*. A stale cache is dangerous
precisely because it does not fail visibly — it trains normally and reports
numbers that are wrong — so most of these assert that something raises.

    python -m pytest tests/test_cache.py -q
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch", reason="cache tests need torch")

from mfstnet.cache import (  # noqa: E402
    CacheMismatchError,
    FeatureCache,
    PreprocessingSpec,
)

N, CNN_C, VIT_C = 8, 2048, 384


@pytest.fixture
def features():
    torch.manual_seed(0)
    return torch.randn(N, CNN_C, 7, 7), torch.randn(N, VIT_C, 16, 16)


@pytest.fixture
def cache(tmp_path):
    return FeatureCache(tmp_path / "cache")


# ------------------------------------------------------------ the hash --

def test_the_hash_is_stable_across_instances():
    assert PreprocessingSpec().hash == PreprocessingSpec().hash


@pytest.mark.parametrize(
    "field, value",
    [
        ("cnn", "convnext_tiny"),
        ("vit", "vit_small_patch16_224"),
        ("image_size", 256),
        ("resize_mode", "bicubic"),
        ("normalization", "clip"),
    ],
)
def test_every_invalidating_change_changes_the_hash(field, value):
    """ADR-005 names backbone, resize and normalisation. `resize_mode` is here
    too: a different interpolation gives different features from identical
    inputs, which is the kind of change that slips past a review."""
    assert PreprocessingSpec(**{field: value}).hash != PreprocessingSpec().hash


def test_grid_and_d_model_are_deliberately_not_in_the_hash():
    """They belong to the trainable adapter, downstream of the cache. So the
    G=7 versus G=14 question the pilots decide can be re-run without
    recomputing a single feature — which is the point of the boundary."""
    fields = PreprocessingSpec().__dataclass_fields__
    assert "grid" not in fields and "d_model" not in fields


# ------------------------------------------------------- round trip --

def test_a_clip_survives_the_round_trip(cache, features):
    cnn, vit = features
    cache.write_clip("src1", "clip1", list(range(N)), cnn, vit)
    indices, out_cnn, out_vit = cache.read_clip("src1", "clip1")

    assert indices == list(range(N))
    assert out_cnn.shape == cnn.shape and out_vit.shape == vit.shape
    # fp16 on disk: a real, bounded loss, not an exact round trip.
    assert torch.allclose(out_cnn, cnn, atol=1e-2)


def test_storage_is_fp16(cache, features):
    """Halves the footprint and costs nothing that matters — these are backbone
    activations feeding a 1x1 convolution, not accumulated gradients."""
    cnn, vit = features
    path = cache.write_clip("src1", "clip1", list(range(N)), cnn, vit)
    payload = torch.load(path, map_location="cpu", weights_only=True)
    assert payload["cnn"].dtype == torch.float16


def test_a_window_comes_back_shaped_for_the_model(cache, features):
    cnn, vit = features
    cache.write_clip("src1", "clip1", list(range(N)), cnn, vit)
    win_cnn, win_vit = cache.read_window("src1", "clip1", start=2, length=4)

    assert win_cnn.shape == (1, 4, CNN_C, 7, 7)
    assert win_vit.shape == (1, 4, VIT_C, 16, 16)


def test_a_window_past_the_end_raises_rather_than_padding(cache, features):
    """HLD §8: never pad, never truncate a window — drop the sequence. A padded
    window silently changes what the label refers to."""
    cnn, vit = features
    cache.write_clip("src1", "clip1", list(range(N)), cnn, vit)
    with pytest.raises(IndexError, match="Never pad"):
        cache.read_window("src1", "clip1", start=6, length=8)


def test_one_branch_alone_is_allowed(cache, features):
    """Configs A and B use a single branch and must not pay for the other."""
    cnn, _ = features
    cache.write_clip("src1", "clip1", list(range(N)), cnn, None)
    _, out_cnn, out_vit = cache.read_clip("src1", "clip1")
    assert out_cnn is not None and out_vit is None


def test_a_clip_with_neither_branch_is_rejected(cache):
    with pytest.raises(ValueError, match="nothing to cache"):
        cache.write_clip("src1", "clip1", [0], None, None)


def test_frame_count_must_match_the_index_list(cache, features):
    cnn, vit = features
    with pytest.raises(ValueError, match="frame indices"):
        cache.write_clip("src1", "clip1", [0, 1], cnn, vit)


# --------------------------------------------------- the refusals --

def test_a_cache_from_a_different_backbone_raises_not_warns(tmp_path, features):
    """SOW R20. The single most important behaviour in this module."""
    cnn, vit = features
    FeatureCache(tmp_path / "c").write_clip("s", "c1", list(range(N)), cnn, vit)

    other = FeatureCache(tmp_path / "c", PreprocessingSpec(cnn="convnext_tiny"))
    with pytest.raises(CacheMismatchError, match="convnext_tiny"):
        other.read_clip("s", "c1")


def test_the_mismatch_message_names_the_field_that_changed(tmp_path, features):
    """"Hash mismatch" alone sends someone hunting. Naming the field does not."""
    cnn, vit = features
    FeatureCache(tmp_path / "c").write_clip("s", "c1", list(range(N)), cnn, vit)

    other = FeatureCache(tmp_path / "c", PreprocessingSpec(image_size=256))
    with pytest.raises(CacheMismatchError) as excinfo:
        other.load_manifest()

    message = str(excinfo.value)
    assert "image_size" in message and "224" in message and "256" in message


def test_a_single_stale_file_in_a_valid_cache_raises(tmp_path, features):
    """The manifest and the per-file hash fail differently: one catches a cache
    built by another configuration, the other catches a file copied in."""
    cnn, vit = features
    good = FeatureCache(tmp_path / "c")
    good.write_clip("s", "c1", list(range(N)), cnn, vit)

    path = good.clip_path("s", "c1")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    payload["preprocessing_hash"] = "deadbeefdeadbeef"
    torch.save(payload, path)

    with pytest.raises(CacheMismatchError, match="stale file"):
        good.read_clip("s", "c1")


def test_a_missing_manifest_raises_rather_than_starting_empty(cache):
    """An absent cache is not an empty one. Silently building from nothing would
    look like a very fast first epoch."""
    with pytest.raises(FileNotFoundError, match="not an empty one"):
        cache.load_manifest()


def test_a_missing_clip_raises(cache, features):
    cnn, vit = features
    cache.write_clip("s", "c1", list(range(N)), cnn, vit)
    with pytest.raises(FileNotFoundError, match="no cached features"):
        cache.read_clip("s", "absent")


# -------------------------------------------------------- manifest --

def test_the_manifest_records_the_hash_and_the_commit(cache, features):
    cnn, vit = features
    cache.write_clip("s", "c1", list(range(N)), cnn, vit)

    manifest = FeatureCache(cache.root).load_manifest()
    assert manifest.preprocessing_hash == PreprocessingSpec().hash
    assert manifest.git_commit           # "unknown" outside a checkout, never empty
    assert manifest.clips["s/c1"]["frames"] == N


def test_reopening_a_matching_cache_is_allowed(cache, features):
    cnn, vit = features
    cache.write_clip("s", "c1", list(range(N)), cnn, vit)
    assert FeatureCache(cache.root).init().preprocessing_hash == cache.spec.hash


def test_size_estimate_is_in_the_right_order(cache):
    """A 6-minute clip at 5 s intervals is 72 frames. If this came out in
    gigabytes the caching plan would not survive a laptop."""
    per_clip = cache.estimate_bytes(72)
    assert 10e6 < per_clip < 60e6


# ------------------------------------------------- end to end --

def test_a_cached_window_feeds_the_model_directly(tmp_path):
    """The join that matters: what the cache returns is exactly what
    `MFSTNet.forward` consumes, with no reshaping in between. If these two ever
    drift apart, every config in §14.4 breaks at once."""
    from mfstnet.corpus.geometry import Polygon
    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks

    lanes = (
        Polygon("north", ((0.30, 0.00), (0.70, 0.00), (0.70, 0.45), (0.30, 0.45))),
        Polygon("south", ((0.30, 0.55), (0.70, 0.55), (0.70, 1.00), (0.30, 1.00))),
        Polygon("east", ((0.72, 0.30), (1.00, 0.30), (1.00, 0.70), (0.72, 0.70))),
        Polygon("west", ((0.00, 0.30), (0.28, 0.30), (0.28, 0.70), (0.00, 0.70))),
    )
    cache = FeatureCache(tmp_path / "cache")
    cache.write_clip(
        "src", "clip", list(range(N)),
        torch.randn(N, CNN_C, 7, 7), torch.randn(N, VIT_C, 16, 16),
    )

    cnn, vit = cache.read_window("src", "clip", start=0, length=6)
    model = MFSTNet(ablation_config("G"), lane_masks(lanes, 7)).eval()
    with torch.no_grad():
        out = model(cnn, vit)

    assert out.logits.shape == (1, 4, 3)
    assert out.gate is not None
