"""One frame, prepared for the frozen backbones — shared by the cache and the edge.

The feature cache (`scripts/build_cache.py`) and the deployed edge node
(`edge/forecaster.py`) must turn a frame into the same tensor, bit for bit, or
the model is served an input space it was never trained on and nothing raises.
A hash cannot guard this on its own: `PreprocessingSpec.resize_mode` says
`"bilinear"` while the cache has always resized with `cv2.INTER_AREA` (P88), so
the hash certifies a label, not the computation. Keeping the computation in one
function is what actually keeps the two sides equal.
"""

from __future__ import annotations

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def preprocess_frame(frame_bgr, size: int):
    """BGR uint8 frame -> normalised CHW float32 tensor, as the cache built it."""
    import cv2
    import numpy as np
    import torch

    mean = np.array(IMAGENET_MEAN, dtype=np.float32)
    std = np.array(IMAGENET_STD, dtype=np.float32)
    frame = cv2.resize(frame_bgr, (size, size), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return torch.from_numpy(((rgb - mean) / std).transpose(2, 0, 1))
