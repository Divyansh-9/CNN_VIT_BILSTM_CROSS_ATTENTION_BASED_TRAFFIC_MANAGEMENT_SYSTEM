"""Encode corpus frames into cached frozen-backbone features (ADR-005, S16).

    python scripts/build_cache.py --corpus data/corpus --clips D:/footage
    python scripts/build_cache.py --corpus data/corpus --clips D:/footage --limit 2

The backbones are frozen, so their outputs are identical every epoch and on every
ablation config. Computing them once collapses what ADR-005 estimated at 60-90
hours of repeated encoding into a single pass, and it is the only reason the
seven-config ablation fits the compute budget at all.

**What is cached is the RAW branch output, not the projected features.** The
projection is a `ProjectionAdapter` and it TRAINS (ADR-005 was corrected on this
once already). Caching projected features would freeze a layer that is supposed
to learn, and the ablation would silently compare eight models sharing one fixed
projection.

**A cache is invalidated by any change to backbone, resize or normalisation.**
`FeatureCache` stores a `PreprocessingSpec` and raises on a mismatch at load
rather than warning, because a stale cache produces results that look normal and
are wrong.

**Frames are sampled at `step_s`, matching the corpus.** The corpus manifest
records the sampling used to build the counts; encoding at a different rate would
give features and labels different time bases, and the model would train on a
misalignment nothing downstream could detect.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def clip_frames(path: Path, indices: list[int], stride: int, size: int):
    """Read the sampled frames of one clip as a normalised tensor batch."""
    import cv2
    import numpy as np
    import torch

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    capture = cv2.VideoCapture(str(path))
    frames = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index * stride)
        ok, frame = capture.read()
        if not ok:
            break
        frame = cv2.resize(frame, (size, size), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        frames.append(torch.from_numpy(((rgb - mean) / std).transpose(2, 0, 1)))
    capture.release()
    return torch.stack(frames) if frames else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--clips", type=Path, required=True,
                        help="directory holding the source videos")
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--source-id", default="corpus")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--limit", type=int, help="first N clips, for a smoke run")
    parser.add_argument(
        "--device", default="auto",
        help="auto|cpu|cuda. Defaulted to cpu until P32, which meant the "
             "backbones ran on the CPU unless someone remembered the flag — "
             "and forgetting it cost hours without looking like an error")
    args = parser.parse_args(argv)

    import torch

    from mfstnet.cache import FeatureCache, PreprocessingSpec
    from mfstnet.encoders import CNNBranch, EncoderConfig, ViTBranch

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    with (args.corpus / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    clips = sorted({row["clip_id"] for row in rows})
    if args.limit:
        clips = clips[: args.limit]

    step_s = manifest["step_s"]
    spec = PreprocessingSpec()
    encoder = EncoderConfig()
    cache = FeatureCache(args.cache, spec)
    cache.init()

    print(f"  {len(clips)} clip(s), step {step_s}s, image {spec.image_size}px")
    print(f"  cnn {spec.cnn}  vit {spec.vit}  dtype {spec.dtype}")

    from scripts.device import resolve_device

    device = resolve_device(args.device)
    print(f"  device {device}")

    # TF32 OFF for the cache, deliberately (P33).
    #
    # `torch.backends.cudnn.allow_tf32` defaults to True, giving convolutions a
    # 10-bit mantissa. Measured on this ResNet-50 + DINOv2 pair, that puts the
    # GPU's features up to 3.8e-2 away from the CPU's — far above the fp16 the
    # cache stores them in, so a CPU-built and a GPU-built cache are genuinely
    # different data. `preprocessing_hash` does not include the device, so they
    # look interchangeable and can be mixed clip by clip: the model would then
    # see a device artifact correlated with the clip, and clips are what the
    # splits are cut on.
    #
    # With TF32 off the gap is 6.5e-5, below fp16 storage precision, and the
    # cache is device-independent as ADR-005 assumes. It costs 4% on a one-time
    # build (163 ms -> 170 ms per 32-frame batch), which is not a trade worth
    # thinking about twice.
    #
    # Training is free to use TF32; it is written once and read many times, and
    # this is the "written once" half.
    if device.startswith("cuda"):
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
    cnn_branch = CNNBranch(encoder).to(device).eval()
    vit_branch = ViTBranch(encoder).to(device).eval()

    sources = {p.stem: p for p in args.clips.rglob("*.mp4")}
    missing = [c for c in clips if c not in sources]
    if missing:
        raise SystemExit(
            f"{len(missing)} clip(s) in the corpus have no video under "
            f"{args.clips}: {missing[:3]}"
        )

    for position, clip_id in enumerate(clips, 1):
        if cache.has(args.source_id, clip_id):
            print(f"  [{position}/{len(clips)}] {clip_id[:44]:<46} cached")
            continue

        # The window with the highest label index fixes how many frames matter.
        highest = max(int(r["label_index"]) for r in rows if r["clip_id"] == clip_id)
        indices = list(range(highest + 1))

        import cv2

        probe = cv2.VideoCapture(str(sources[clip_id]))
        fps = probe.get(cv2.CAP_PROP_FPS) or 25.0
        probe.release()
        stride = max(1, int(round(fps * step_s)))

        images = clip_frames(sources[clip_id], indices, stride, spec.image_size)
        if images is None or len(images) <= highest:
            raise SystemExit(
                f"{clip_id}: read {0 if images is None else len(images)} frames "
                f"but the corpus references index {highest}. The video and the "
                f"corpus disagree — rebuild the corpus from this video."
            )

        cnn_maps, vit_maps = [], []
        with torch.no_grad():
            for start in range(0, len(images), args.batch):
                chunk = images[start:start + args.batch].to(device)
                cnn_maps.append(cnn_branch(chunk).to(torch.float16).cpu())
                vit_maps.append(vit_branch(chunk).to(torch.float16).cpu())
        cnn = torch.cat(cnn_maps)
        vit = torch.cat(vit_maps)

        cache.write_clip(args.source_id, clip_id, indices, cnn, vit)
        print(f"  [{position}/{len(clips)}] {clip_id[:44]:<46} "
              f"{len(indices):>4} frames  cnn {tuple(cnn.shape[1:])}  "
              f"vit {tuple(vit.shape[1:])}")

    print(f"\n  wrote {args.cache}")
    total = sum(p.stat().st_size for p in args.cache.rglob("*") if p.is_file())
    print(f"  {total / 1e9:.2f} GB on disk")
    print("  A cache is invalidated by any change to backbone, resize or")
    print("  normalisation. The loader RAISES on a mismatch rather than warning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
