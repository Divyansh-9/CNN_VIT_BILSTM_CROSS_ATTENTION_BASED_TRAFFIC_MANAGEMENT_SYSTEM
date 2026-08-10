"""Deterministic seeding for every RNG this project touches.

NFR-07 is marked Critical and cannot be retrofitted: seeds not set during a run
cannot be recovered afterwards. Call `set_seed()` before building any model.

Verify determinism (TC-N07) by running one epoch twice and comparing losses:

    python scripts/train_mfstnet.py --config mfstnet/configs/smoke.yaml --epochs 1
    python scripts/train_mfstnet.py --config mfstnet/configs/smoke.yaml --epochs 1

Epoch-1 loss must match to 1e-6. If it does not, seeding is incomplete --
find the unseeded source rather than lowering the tolerance.
"""

from __future__ import annotations

import os
import random

import numpy as np
import torch

DEFAULT_SEED = 42  # PRD §8.4 and §13.1 both specify 42


def set_seed(seed: int = DEFAULT_SEED, *, deterministic: bool = True) -> int:
    """Seed Python, NumPy and PyTorch (CPU + CUDA).

    Args:
        seed: the seed. Defaults to the PRD's 42.
        deterministic: force deterministic cuDNN kernels. Costs some speed and
            is what makes two runs comparable. Only disable for a throughput
            benchmark, never for a reported result.

    Returns:
        The seed, so callers can record it in the experiment record.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    return seed


def seed_worker(worker_id: int) -> None:
    """Per-worker seeding for DataLoader.

    Without this, each worker inherits a different torch seed and any
    augmentation or shuffling inside the dataset becomes non-reproducible --
    a common and easily missed hole in an otherwise seeded pipeline.

        DataLoader(..., worker_init_fn=seed_worker, generator=make_generator())
    """
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def make_generator(seed: int = DEFAULT_SEED) -> torch.Generator:
    """Generator for DataLoader shuffling. Pair with `seed_worker`."""
    g = torch.Generator()
    g.manual_seed(seed)
    return g


# Stable-Baselines3 seeds through its own API, not through this module.
# Both of the following are required (FR-R01, NFR-07):
#
#     model = PPO("MlpPolicy", env, seed=42, ...)
#     env.reset(seed=42)
#
# Setting only torch.manual_seed leaves SB3's action sampling unseeded.


if __name__ == "__main__":
    s = set_seed()
    print(f"seeded with {s}")
    print("torch  :", torch.randn(3).tolist())
    print("numpy  :", np.random.randn(3).tolist())
    print("python :", [random.random() for _ in range(3)])
    print("\nRun twice -- all three lines must be identical.")
