"""A cached feature must not depend on which device encoded it (P33).

`preprocessing_hash` covers the backbone, the resize and the normalisation, and
ADR-005 has `read_clip` raise on a mismatch rather than warn. It does **not**
cover the device — so a CPU-built and a GPU-built cache carry the same hash and
can be mixed clip by clip.

That would be harmless if the two agreed. They do not, by default:
`torch.backends.cudnn.allow_tf32` is True, giving convolutions a 10-bit
mantissa, and the measured gap on ResNet-50 + DINOv2 is up to 3.8e-2 — well
above the fp16 the cache stores. Since splits are cut by clip, a device
artifact that varies clip by clip is an artifact that varies by split.

`build_cache.py` therefore turns TF32 off, which brings the gap to 6.5e-5 for
4% on a one-time build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

torch = pytest.importorskip("torch")

pytestmark = pytest.mark.skipif(
    not torch.cuda.is_available(), reason="needs a CUDA device to compare against"
)

# fp16 carries 11 bits of significand, so it resolves about 4.9e-4 of a
# tensor's scale. The comparison has to be made AGAINST THE SCALE: an absolute
# threshold reads as a failure on activations whose values reach 60, and a
# per-element relative one blows up at values near zero where the absolute
# difference is negligible. Measured on real frames, TF32 lands at 3.6e-3 of
# scale (seven times coarser than storage, so it survives into the cache) and
# TF32-off at 3.1e-6 (well under, so it does not).
FP16_RESOLUTION = 2 ** -11


@pytest.fixture(scope="module")
def images():
    torch.manual_seed(0)
    from mfstnet.encoders import EncoderConfig

    enc = EncoderConfig()
    return torch.randn(2, 3, enc.image_size, enc.image_size)


def encode(device: str, images, *, tf32: bool):
    from mfstnet.encoders import CNNBranch, EncoderConfig, ViTBranch

    torch.backends.cudnn.allow_tf32 = tf32
    torch.backends.cuda.matmul.allow_tf32 = tf32
    enc = EncoderConfig()
    cnn = CNNBranch(enc).to(device).eval()
    vit = ViTBranch(enc).to(device).eval()
    with torch.no_grad():
        return (cnn(images.to(device)).float().cpu(),
                vit(images.to(device)).float().cpu())


def relative_to_scale(reference, other) -> float:
    """Worst difference, as a fraction of the reference tensor's magnitude."""
    return ((reference - other).abs().max()
            / reference.abs().max().clamp(min=1e-12)).item()


def test_tf32_puts_the_gpu_beyond_fp16_of_the_cpu(images):
    """The defect, stated as a measurement. If this ever stops holding, the
    guard in build_cache is unnecessary — but that must be checked, not
    assumed."""
    cnn_cpu, vit_cpu = encode("cpu", images, tf32=False)
    cnn_gpu, vit_gpu = encode("cuda", images, tf32=True)

    worst = max(relative_to_scale(cnn_cpu, cnn_gpu),
                relative_to_scale(vit_cpu, vit_gpu))
    assert worst > FP16_RESOLUTION, (
        f"TF32 now agrees with the CPU to {worst:.2e} of scale, inside fp16's "
        f"{FP16_RESOLUTION:.2e}; the build_cache guard may no longer be needed"
    )


def test_without_tf32_the_two_devices_agree_inside_storage_precision(images):
    cnn_cpu, vit_cpu = encode("cpu", images, tf32=False)
    cnn_gpu, vit_gpu = encode("cuda", images, tf32=False)

    assert relative_to_scale(cnn_cpu, cnn_gpu) < FP16_RESOLUTION
    assert relative_to_scale(vit_cpu, vit_gpu) < FP16_RESOLUTION


def test_the_difference_survives_fp16_storage_with_tf32_on(images):
    """Stored as fp16 the TF32 gap is still there, which is what makes it a
    corpus problem rather than a rounding curiosity."""
    cnn_cpu, _ = encode("cpu", images, tf32=False)
    cnn_gpu, _ = encode("cuda", images, tf32=True)

    stored_cpu = cnn_cpu.to(torch.float16).float()
    stored_gpu = cnn_gpu.to(torch.float16).float()
    assert relative_to_scale(stored_cpu, stored_gpu) > FP16_RESOLUTION


def test_build_cache_turns_tf32_off():
    """Pinned as source, because the setting is global and a later import could
    switch it back on without any test noticing."""
    source = (Path(__file__).resolve().parent.parent
              / "scripts" / "build_cache.py").read_text(encoding="utf-8")
    assert "torch.backends.cudnn.allow_tf32 = False" in source
    assert "torch.backends.cuda.matmul.allow_tf32 = False" in source
