"""Training has to actually reach the GPU (P32).

`build_cache.py` had a `--device` flag from the start. `train_mfstnet.py` had
no device handling at all — no `.to()`, no `.cuda()`, nothing — so the model
and every batch stayed on the CPU whatever build of torch was installed.

That is the half of the problem a CUDA wheel does not fix, and it is invisible:
training runs, the loss falls, the numbers are right. It is simply slow, on a
machine whose GPU is idle.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

torch = pytest.importorskip("torch")

from scripts.train_mfstnet import move, resolve_device


def test_an_explicit_device_is_taken_literally():
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda") == "cuda"
    assert resolve_device("cuda:1") == "cuda:1"


def test_auto_follows_what_torch_can_see():
    """Not a hardcoded answer — the point is that it tracks the environment,
    so the same command is right on the laptop and on Colab."""
    assert resolve_device("auto") == ("cuda" if torch.cuda.is_available() else "cpu")


def test_auto_reports_cpu_when_cuda_is_absent(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_device("auto") == "cpu"


def test_auto_reports_cuda_when_cuda_is_present(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert resolve_device("auto") == "cuda"


def test_move_carries_every_tensor():
    batch = (torch.randn(2, 3), torch.randn(2, 4), torch.zeros(2, dtype=torch.long))
    moved = move(batch, "cpu")
    assert all(t.device.type == "cpu" for t in moved)
    assert [tuple(t.shape) for t in moved] == [(2, 3), (2, 4), (2,)]


def test_move_tolerates_a_disabled_branch():
    """Ablation configs A and B run one branch only, and the other arrives as
    None. `None.to(device)` would end the run on config A."""
    cnn, vit, masks = move((torch.randn(2, 3), None, torch.randn(2, 4, 7, 7)), "cpu")
    assert vit is None
    assert cnn is not None and masks is not None


def test_move_preserves_values():
    original = torch.arange(6, dtype=torch.float32).reshape(2, 3)
    (moved,) = move((original,), "cpu")
    assert torch.equal(moved, original)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device here")
def test_the_model_and_its_masks_reach_the_gpu():
    """`lane_masks` is a registered buffer, so `.to()` must carry it. If it did
    not, the einsum in LanePool would fail on mixed devices mid-epoch rather
    than at construction."""
    from mfstnet.model import MFSTNet, MFSTNetConfig

    cfg = MFSTNetConfig(n_lanes=2)
    grid = cfg.encoder.grid
    masks = torch.zeros(2, grid, grid)
    masks[0, 0, 0] = masks[1, grid - 1, grid - 1] = 1.0

    model = MFSTNet(cfg, masks).to("cuda")
    assert model.lane_pool.masks.device.type == "cuda"

    cnn = torch.randn(1, 2, cfg.encoder.cnn_channels, grid, grid, device="cuda")
    vit = torch.randn(1, 2, cfg.encoder.vit_channels, grid, grid, device="cuda")
    with torch.no_grad():
        out = model(cnn, vit)
    assert out.logits.device.type == "cuda"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device here")
def test_per_sample_masks_work_on_the_gpu():
    """P26's per-camera geometry arrives with the batch rather than the model,
    so it is the one thing `.to(model)` does not carry."""
    from mfstnet.model import MFSTNet, MFSTNetConfig

    cfg = MFSTNetConfig(n_lanes=2)
    grid = cfg.encoder.grid
    masks = torch.zeros(2, grid, grid)
    masks[0, 0, 0] = masks[1, grid - 1, grid - 1] = 1.0

    model = MFSTNet(cfg, masks).to("cuda")
    cnn = torch.randn(2, 2, cfg.encoder.cnn_channels, grid, grid)
    vit = torch.randn(2, 2, cfg.encoder.vit_channels, grid, grid)
    per_sample = torch.stack([masks, masks])

    cnn, vit, per_sample = move((cnn, vit, per_sample), "cuda")
    with torch.no_grad():
        out = model(cnn, vit, lane_masks=per_sample)
    assert out.logits.shape == (2, 2, cfg.n_classes)


# ------------------------------------------------- the fp16 data path (P35) --

def test_cast_widens_after_the_move():
    """The cache stores fp16 and the model wants fp32. Widening on the CPU
    means `torch.stack` allocates and the PCIe transfer ships twice the bytes —
    measured at half an epoch on the pilot corpus.
    """
    half = torch.randn(4, 3, dtype=torch.float16)
    (moved,) = move((half,), "cpu", cast=torch.float32)
    assert moved.dtype == torch.float32


def test_widening_fp16_to_fp32_is_exact():
    """Why the optimisation is free rather than a trade. Every fp16 value is
    representable in fp32, so it cannot matter where the widening happens —
    and the measured run confirmed it: same macro-F1, same gate_mean.
    """
    half = (torch.randn(1000, dtype=torch.float32)).to(torch.float16)
    on_cpu = half.to(torch.float32)
    (on_device,) = move((half,), "cpu", cast=torch.float32)
    assert torch.equal(on_cpu, on_device)


def test_cast_leaves_integer_tensors_alone():
    """Labels travel in the same batch and must stay long — casting them to
    float would break CrossEntropyLoss with an unhelpful message."""
    labels = torch.zeros(4, dtype=torch.long)
    (moved,) = move((labels,), "cpu", cast=torch.float32)
    assert moved.dtype == torch.long


def test_cast_is_optional():
    half = torch.randn(4, dtype=torch.float16)
    (moved,) = move((half,), "cpu")
    assert moved.dtype == torch.float16


def test_cast_still_tolerates_a_disabled_branch():
    cnn, vit = move((torch.randn(2, 2, dtype=torch.float16), None), "cpu",
                    cast=torch.float32)
    assert vit is None
    assert cnn.dtype == torch.float32
