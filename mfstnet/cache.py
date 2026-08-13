"""The frozen-feature cache (S27, ADR-005, HLD §7).

Frozen backbones emit the same features every epoch, so computing them every
epoch is pure waste — and worse than waste here, because at batch 32 x T=60 an
uncached step pushes 1,920 frames through both backbones, which does not fit in
6 GB and is tight even on a T4. Cached, the 60–90 hour ablation collapses to
hours, and one cache serves all eight configs.

    key    (source_id, clip_id, frame_idx, preprocessing_hash)
    value  cnn [2048, 7, 7] fp16 · vit [384, 16, 16] fp16

**Only the frozen half is ever stored.** The 1x1 projections that align the two
branches are trainable and live in `MFSTNet`. Caching them would bake a
randomly-initialised adapter in on the first run, where it could never train
again — and nothing would notice, because the loss would still fall.

**A hash mismatch raises. It never warns.** SOW risk R20 rates this Low
likelihood and High impact for a specific reason: a stale cache does not crash
or produce obvious garbage. It produces a perfectly normal-looking training run
whose numbers are wrong, and the results reach a paper before anyone asks. A
warning in a log nobody reads is not a control.

fp16 halves the footprint and costs nothing that matters: these are backbone
activations feeding a 1x1 convolution, not accumulated gradients.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import torch

from .encoders import EncoderConfig

__all__ = [
    "PreprocessingSpec",
    "CacheManifest",
    "CacheMismatchError",
    "FeatureCache",
]

CACHE_FORMAT_VERSION = 1


class CacheMismatchError(RuntimeError):
    """The cache on disk was not built by the current preprocessing."""


@dataclass(frozen=True)
class PreprocessingSpec:
    """Everything that changes what a cached feature *means*.

    ADR-005 names three invalidating changes — backbone, resize, normalisation —
    and all three are fields here. `image_size` is separate from `resize_mode`
    because a different resize *interpolation* produces different features from
    identical inputs, which is exactly the kind of change that slips through a
    review unnoticed.

    Note what is deliberately **absent**: `grid` and `d_model`. Both belong to
    the trainable adapter, downstream of the cache, so changing G does not
    invalidate a single cached tensor. That is the whole benefit of drawing the
    boundary where we did — the G=7 versus G=14 question the Week-2 pilots
    decide can be re-run without recomputing features.
    """

    cnn: str = "resnet50"
    vit: str = "vit_small_patch14_dinov2"
    image_size: int = 224
    resize_mode: str = "bilinear"
    normalization: str = "imagenet"
    dtype: str = "float16"
    format_version: int = CACHE_FORMAT_VERSION

    @classmethod
    def from_encoder(cls, cfg: EncoderConfig, **overrides) -> "PreprocessingSpec":
        return cls(
            cnn=cfg.cnn, vit=cfg.vit, image_size=cfg.image_size, **overrides
        )

    @property
    def hash(self) -> str:
        """Stable 16-hex digest. Sorted keys, so field order cannot change it."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _git_commit() -> str:
    """Recorded alongside the hash per SOW R20. Best-effort — a cache built
    outside a checkout is still usable, it is just less traceable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@dataclass
class CacheManifest:
    preprocessing_hash: str
    spec: dict
    git_commit: str = field(default_factory=_git_commit)
    clips: dict[str, dict] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "CacheManifest":
        raw = json.loads(text)
        return cls(**raw)


class FeatureCache:
    """One directory, one preprocessing spec, one file per clip.

    Per clip rather than per frame because the corpus reads whole clips and a
    12,000-frame cache of individual files is slow on every filesystem and
    pathological on Windows.
    """

    MANIFEST = "manifest.json"

    def __init__(self, root: str | Path, spec: PreprocessingSpec | None = None) -> None:
        self.root = Path(root)
        self.spec = spec or PreprocessingSpec()
        self._manifest: CacheManifest | None = None

    # ------------------------------------------------------------- manifest --

    @property
    def manifest_path(self) -> Path:
        return self.root / self.MANIFEST

    def load_manifest(self) -> CacheManifest:
        """Read the manifest and **verify the hash**, raising on mismatch."""
        if self._manifest is not None:
            return self._manifest
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"no cache manifest at {self.manifest_path}. Build the cache "
                f"before training; an absent cache is not an empty one."
            )
        manifest = CacheManifest.from_json(
            self.manifest_path.read_text(encoding="utf-8")
        )
        self._assert_compatible(manifest)
        self._manifest = manifest
        return manifest

    def _assert_compatible(self, manifest: CacheManifest) -> None:
        if manifest.preprocessing_hash == self.spec.hash:
            return

        differences = [
            f"    {key}: cache {manifest.spec.get(key)!r} != current {value!r}"
            for key, value in asdict(self.spec).items()
            if manifest.spec.get(key) != value
        ]
        raise CacheMismatchError(
            f"cache at {self.root} was built with preprocessing "
            f"{manifest.preprocessing_hash}, but the current configuration hashes "
            f"to {self.spec.hash}.\n"
            + ("\n".join(differences) or "    (no field differs — format change?)")
            + f"\n  Built at git commit {manifest.git_commit}.\n"
            f"  This raises rather than warning because a stale cache does not "
            f"fail visibly: it trains normally and the numbers are wrong "
            f"(ADR-005, SOW R20). Rebuild the cache."
        )

    def init(self) -> CacheManifest:
        """Create the directory and manifest, or return the existing verified one."""
        if self.manifest_path.exists():
            return self.load_manifest()
        self.root.mkdir(parents=True, exist_ok=True)
        manifest = CacheManifest(
            preprocessing_hash=self.spec.hash, spec=asdict(self.spec)
        )
        self.manifest_path.write_text(manifest.to_json(), encoding="utf-8")
        self._manifest = manifest
        return manifest

    # ----------------------------------------------------------------- io --

    def clip_path(self, source_id: str, clip_id: str) -> Path:
        return self.root / f"{source_id}__{clip_id}.pt"

    def has(self, source_id: str, clip_id: str) -> bool:
        return self.clip_path(source_id, clip_id).exists()

    def write_clip(
        self,
        source_id: str,
        clip_id: str,
        frame_indices: list[int],
        cnn: torch.Tensor | None,
        vit: torch.Tensor | None,
    ) -> Path:
        """Store one clip's frozen features. `cnn` is `[N, C, h, w]`, as is `vit`.

        Both may be None only if the corresponding branch is genuinely unused;
        storing neither would produce a file that cannot serve any config.
        """
        if cnn is None and vit is None:
            raise ValueError(
                f"clip {clip_id!r} has neither branch — nothing to cache"
            )
        for name, tensor in (("cnn", cnn), ("vit", vit)):
            if tensor is not None and tensor.shape[0] != len(frame_indices):
                raise ValueError(
                    f"{name} has {tensor.shape[0]} frames but {len(frame_indices)} "
                    f"frame indices were given for clip {clip_id!r}"
                )

        manifest = self.init()
        payload = {
            "frame_indices": list(frame_indices),
            "preprocessing_hash": self.spec.hash,
            "cnn": None if cnn is None else cnn.detach().to(torch.float16).cpu(),
            "vit": None if vit is None else vit.detach().to(torch.float16).cpu(),
        }
        path = self.clip_path(source_id, clip_id)
        torch.save(payload, path)

        manifest.clips[f"{source_id}/{clip_id}"] = {
            "frames": len(frame_indices),
            "file": path.name,
        }
        self.manifest_path.write_text(manifest.to_json(), encoding="utf-8")
        return path

    def read_clip(
        self, source_id: str, clip_id: str, *, dtype: torch.dtype = torch.float32
    ) -> tuple[list[int], torch.Tensor | None, torch.Tensor | None]:
        """Load one clip, verifying the manifest **and** the per-file hash.

        Both are checked because they fail differently: the manifest catches a
        cache built by a different configuration, the per-file hash catches a
        single file copied in from somewhere else.
        """
        self.load_manifest()
        path = self.clip_path(source_id, clip_id)
        if not path.exists():
            raise FileNotFoundError(f"no cached features for {source_id}/{clip_id}")

        payload = torch.load(path, map_location="cpu", weights_only=True)
        stored = payload.get("preprocessing_hash")
        if stored != self.spec.hash:
            raise CacheMismatchError(
                f"{path.name} was written with preprocessing {stored}, but the "
                f"current configuration hashes to {self.spec.hash}. A single "
                f"stale file in an otherwise valid cache is exactly the case "
                f"that trains without complaint and reports wrong numbers."
            )
        return (
            payload["frame_indices"],
            None if payload["cnn"] is None else payload["cnn"].to(dtype),
            None if payload["vit"] is None else payload["vit"].to(dtype),
        )

    def read_window(
        self,
        source_id: str,
        clip_id: str,
        start: int,
        length: int,
        *,
        dtype: torch.dtype = torch.float32,
    ) -> tuple[torch.Tensor | None, torch.Tensor | None]:
        """One training sequence: `[1, T, C, h, w]` per branch, ready for `MFSTNet`.

        Windows overlap heavily — consecutive sequences share 54 of 60 frames —
        which is the second reason to cache per clip rather than per sequence.
        Storing sequences would write those shared frames ten times over, and it
        is also how clip-level splits get violated by accident.
        """
        indices, cnn, vit = self.read_clip(source_id, clip_id, dtype=dtype)
        available = len(indices)
        if start < 0 or start + length > available:
            raise IndexError(
                f"window [{start}, {start + length}) does not fit clip "
                f"{clip_id!r}, which has {available} cached frames. Never pad or "
                f"truncate a window — drop the sequence (HLD §8)."
            )
        window = slice(start, start + length)
        return (
            None if cnn is None else cnn[window].unsqueeze(0),
            None if vit is None else vit[window].unsqueeze(0),
        )

    def estimate_bytes(self, n_frames: int) -> int:
        """Planning aid. fp16, both branches, at the spec's geometry."""
        cfg = EncoderConfig(cnn=self.spec.cnn, vit=self.spec.vit,
                            image_size=self.spec.image_size)
        cnn_grid = 7
        vit_grid = self.spec.image_size // (14 if "patch14" in self.spec.vit else 16)
        per_frame = 2 * (
            cfg.cnn_channels * cnn_grid * cnn_grid
            + cfg.vit_channels * vit_grid * vit_grid
        )
        return per_frame * n_frames
