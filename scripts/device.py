"""Which device to run on, decided once and the same way everywhere (P32).

Three scripts build tensors and models — `build_cache.py`, `overfit_check.py`
and `train_mfstnet.py` — and before this they disagreed. `build_cache` had a
`--device` flag defaulting to `cpu`, `overfit_check` had a `device` parameter
with no way to set it, and `train_mfstnet` had no device handling at all. On a
machine with an idle RTX 4050 every one of them ran on the CPU, correctly and
slowly, with nothing looking wrong.

`auto` is the default because the alternative is a flag that has to be
remembered on every invocation, and the failure mode of forgetting it is silent.
"""

from __future__ import annotations

__all__ = ["resolve_device", "move"]


def resolve_device(requested: str = "auto") -> str:
    """`auto` means use the GPU when torch can see one.

    An explicit value is taken literally, including `cuda:1`, so a deliberate
    CPU run for comparison stays possible.
    """
    import torch

    if requested != "auto":
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


def move(batch, device: str, cast=None):
    """Batch tensors onto `device`, tolerating a disabled branch (`None`).

    Ablation configs A and B run one branch only and the other arrives as
    `None`; `None.to(device)` would end the run on the first config.

    `cast` widens AFTER the transfer. The cache stores fp16 and the model wants
    fp32, and doing that widening on the CPU means stacking and shipping twice
    the bytes — measured at half an epoch on this corpus. Widening fp16 to
    fp32 is exact, so where it happens cannot change a result (P35).
    """
    out = []
    for x in batch:
        if x is None:
            out.append(None)
            continue
        x = x.to(device, non_blocking=True)
        if cast is not None and x.is_floating_point() and x.dtype != cast:
            x = x.to(cast)
        out.append(x)
    return tuple(out)
