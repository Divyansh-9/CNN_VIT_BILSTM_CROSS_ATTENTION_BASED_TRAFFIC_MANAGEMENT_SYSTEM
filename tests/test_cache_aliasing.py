"""A cached window must be a copy, never a view into the mapping (P55).

`read_window` memory-maps the clip file so a 60-frame window can be sliced
without materialising a 1,000-frame clip (P29). The returned tensor then went
through `.to(dtype)` — which, when the tensor is *already* that dtype, is a
no-op that returns the same tensor. So asking for the cache's own fp16 handed
back a view into a mapping that was released as soon as the function returned.

Touching it later was an access violation in several threads at once, with no
Python frame, at a moment that depended on when the collector ran. It was
invisible while every caller asked for fp32, because widening copies; P35 made
the training path request fp16 to halve what crosses the bus, and turned every
window into a dangling view.

The assertion here is on **storage size**, not on values. A view into the
mapping carries the whole clip's storage; a copy carries only the window's. That
distinction is checkable without dereferencing freed memory, which is the one
thing a test for this must not do.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from mfstnet.cache import FeatureCache, PreprocessingSpec  # noqa: E402

T = 4
FRAMES = 20


@pytest.fixture
def cache(tmp_path):
    spec = PreprocessingSpec()
    store = FeatureCache(tmp_path, spec)
    store.init()
    cnn = torch.randn(FRAMES, 8, 7, 7, dtype=torch.float16)
    vit = torch.randn(FRAMES, 4, 16, 16, dtype=torch.float16)
    store.write_clip("corpus", "clip", list(range(FRAMES)), cnn, vit)
    return store


def window_elements(branch_channels: int, grid: int) -> int:
    return T * branch_channels * grid * grid


@pytest.mark.parametrize("dtype", [torch.float16, torch.float32])
def test_the_window_owns_its_storage(cache, dtype):
    """fp16 is the case that was broken; fp32 is the case that hid it."""
    cnn, vit = cache.read_window("corpus", "clip", 5, T, dtype=dtype)
    for tensor, channels, grid in ((cnn, 8, 7), (vit, 4, 16)):
        expected = window_elements(channels, grid) * tensor.element_size()
        actual = tensor.untyped_storage().nbytes()
        assert actual == expected, (
            f"{tensor.dtype} window holds {actual} bytes of storage for "
            f"{expected} bytes of window — it is a view into the mapped clip, "
            f"and the mapping is not kept alive."
        )


def test_the_only_view_relationship_left_is_the_unsqueeze(cache):
    """`read_window` ends with `.unsqueeze(0)`, so the result IS a view — of the
    copy. What matters is that whatever it views is window-sized rather than
    clip-sized; a base holding the whole clip would be the mapping."""
    cnn, vit = cache.read_window("corpus", "clip", 5, T, dtype=torch.float16)
    for tensor in (cnn, vit):
        base = tensor._base
        assert base is None or base.numel() == tensor.numel()


def test_the_values_still_match_the_clip(cache):
    """A copy is only correct if it is a copy of the right frames."""
    _, cnn_all, _ = cache.read_clip("corpus", "clip", dtype=torch.float16)
    cnn, _ = cache.read_window("corpus", "clip", 5, T, dtype=torch.float16)
    assert torch.equal(cnn.squeeze(0), cnn_all[5:5 + T])


def test_mutating_a_window_cannot_reach_the_cache(cache):
    """The property a view would break, stated directly."""
    cnn, _ = cache.read_window("corpus", "clip", 0, T, dtype=torch.float16)
    cnn.fill_(0)
    again, _ = cache.read_window("corpus", "clip", 0, T, dtype=torch.float16)
    assert not torch.equal(again, cnn)


def test_windows_survive_the_payload_going_out_of_scope(cache):
    """The failure, as closely as it can be reproduced without crashing.

    Every window is read and dropped before any is touched, so the mappings
    behind them have all been released by the time the sums run.
    """
    import gc

    held = [cache.read_window("corpus", "clip", start, T, dtype=torch.float16)
            for start in range(FRAMES - T)]
    gc.collect()
    assert all(float(cnn.float().sum()) == float(cnn.float().sum())
               for cnn, _ in held)
