"""Dual-path spatial encoders with grid alignment (PRD §8.1 Stage 1, amendment A24).

Two frozen backbones look at the same frame and notice different things — the CNN
local texture and vehicle shape, the ViT the layout of the scene. Stage 2 then
lets each query the other.

**Grid alignment is not a convenience, it is what makes Stage 2 executable.** A
cross-attention layer returns one output per *query*, so `CrossAttn(Q=CNN, KV=ViT)`
carries the CNN's token count and `CrossAttn(Q=ViT, KV=CNN)` carries the ViT's. At
224×224 that is 49 against 257 — and the gate `g·Z_A + (1−g)·Z_B` is elementwise,
so it cannot run. The defect predates the DINOv2 switch: with the original
supervised ViT it was 49 against 197.

Both branches are therefore projected onto a shared **G×G** grid before Stage 2.
That also gives per-lane ROI pooling (A8) the spatial map it needs — a flat
sequence of 257 tokens is not one until it is reshaped.

`G` comes from config and is never hardcoded. Attention cost scales with `(G²)²`,
and cross-attention is *trainable*, so it runs every epoch and is **not** covered
by the ADR-005 feature cache:

    G=7   ->  49 tokens ->  1.2 G MAC per batch of 32 x T=60   (default)
    G=14  -> 196 tokens -> 18.9 G MAC                          (16x)
    G=16  -> 256 tokens -> 32.2 G MAC                          (27x)

G=7 is what a 6 GB card affords. Its cost is ROI granularity: a lane covering a
quarter of the frame gets ~12 of 49 cells, a small approach two or three. Raise G
if the Week-2 pilots show lanes occupying a small share of the frame.

**Where the projection lives matters, and it is not here.** Each branch is
*purely frozen*: it emits its backbone's raw map at the backbone's own geometry
(`[B, 2048, 7, 7]` for ResNet-50, `[B, 384, 16, 16]` for DINOv2). The 1x1
projection to `d_model` and the resize to `G` are a separate `ProjectionAdapter`
owned by the trainable model.

That split is what makes ADR-005's cache correct rather than merely fast. The
cache stores exactly what the frozen backbones produce. If it stored the
projected map instead, a randomly-initialised adapter would be baked into the
cache on the first run and could never train again — the loss would still fall,
nothing would raise, and the reported "trainable projections" would be a fiction.
Caching may only ever capture the part of the graph that does not learn.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = [
    "EncoderConfig",
    "CNNBranch",
    "ViTBranch",
    "ProjectionAdapter",
    "DualPathEncoder",
]


@dataclass(frozen=True)
class EncoderConfig:
    """Defaults reproduce PRD §8.2 as amended by A12 and A24."""

    d_model: int = 256
    grid: int = 7                          # G — see module docstring
    cnn: str = "resnet50"                  # resnet50 | convnext_tiny
    vit: str = "vit_small_patch14_dinov2"  # A12 default; vit_small_patch16_224 = arm BB-1
    image_size: int = 224
    pretrained: bool = True
    frozen: bool = True                    # ADR-005: the feature cache requires this

    @property
    def tokens(self) -> int:
        return self.grid * self.grid

    @property
    def cnn_channels(self) -> int:
        """Channels a CNN cache entry holds. Part of `preprocessing_hash`."""
        try:
            return _CNN_CHANNELS[self.cnn]
        except KeyError:
            raise ValueError(f"unknown CNN backbone {self.cnn!r}") from None

    @property
    def vit_channels(self) -> int:
        try:
            return _VIT_CHANNELS[self.vit]
        except KeyError:
            raise ValueError(f"unknown ViT backbone {self.vit!r}") from None


# Declared rather than discovered, so a cache can be sized and validated without
# instantiating 45 M parameters of backbone. Asserted against the real modules in
# `test_encoders.py` — a table that drifts from the models is worse than none.
_CNN_CHANNELS = {"resnet50": 2048, "convnext_tiny": 768}
_VIT_CHANNELS = {"vit_small_patch14_dinov2": 384, "vit_small_patch16_224": 384}


class ProjectionAdapter(nn.Module):
    """Resize to `G` and project to `d_model`. **The trainable half.**

    Deliberately separate from the branches so the frozen path and the learned
    path cannot be confused, and so the ADR-005 cache can store the frozen half
    alone. A 1x1 convolution rather than a Linear over flattened tokens: both are
    the same arithmetic, but only one keeps the spatial map that per-lane ROI
    pooling (A8) needs. A flat sequence of tokens is not a map.
    """

    def __init__(self, in_channels: int, d_model: int, grid: int) -> None:
        super().__init__()
        self.grid = grid
        self.project = nn.Conv2d(in_channels, d_model, kernel_size=1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        """`[B, C, h, w]` -> `[B, D, G, G]`."""
        if feats.shape[-2:] != (self.grid, self.grid):
            feats = F.interpolate(
                feats, size=(self.grid, self.grid),
                mode="bilinear", align_corners=False,
            )
        return self.project(feats)


class CNNBranch(nn.Module):
    """ResNet-50 (or ConvNeXt-T), frozen, to its **raw** `[B, C, h, w]` map.

    No projection and no resize: this is the cacheable half. `out_channels`
    reports what a cache entry will hold.
    """

    def __init__(self, cfg: EncoderConfig) -> None:
        super().__init__()
        self.cfg = cfg

        if cfg.cnn == "resnet50":
            from torchvision.models import ResNet50_Weights, resnet50
            weights = ResNet50_Weights.IMAGENET1K_V2 if cfg.pretrained else None
            net = resnet50(weights=weights)
            self.backbone = nn.Sequential(*list(net.children())[:-2])  # drop pool + fc
            channels = 2048
        elif cfg.cnn == "convnext_tiny":
            from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny
            weights = ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if cfg.pretrained else None
            self.backbone = convnext_tiny(weights=weights).features
            channels = 768
        else:
            raise ValueError(f"unknown CNN backbone {cfg.cnn!r}")

        self.out_channels = channels
        if cfg.frozen:
            for p in self.backbone.parameters():
                p.requires_grad_(False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """`[B, 3, H, W]` -> the backbone's own map, `[B, C, h, w]`."""
        if self.cfg.frozen:
            with torch.no_grad():
                return self.backbone(x)
        return self.backbone(x)


class ViTBranch(nn.Module):
    """DINOv2 ViT-S/14 (or supervised ViT-S/16), frozen, to `[B, C, 16, 16]`.

    The reshape is where the geometry bites. Patch-14 at 224 gives a 16×16 patch
    grid plus a CLS token — **257**, not 197. The CLS token carries no position,
    so it is dropped before the sequence is folded back into a grid; keeping it
    would make the token count non-square and the reshape impossible.
    """

    def __init__(self, cfg: EncoderConfig) -> None:
        super().__init__()
        import timm

        self.cfg = cfg
        self.backbone = timm.create_model(
            cfg.vit, pretrained=cfg.pretrained, num_classes=0,
            img_size=cfg.image_size,
        )
        if cfg.frozen:
            for p in self.backbone.parameters():
                p.requires_grad_(False)

        self.embed_dim: int = self.backbone.num_features
        patch = self.backbone.patch_embed.patch_size
        self.patch_size: int = patch[0] if isinstance(patch, (tuple, list)) else patch
        self.native_grid: int = cfg.image_size // self.patch_size
        self.num_prefix: int = getattr(self.backbone, "num_prefix_tokens", 1)
        self.out_channels: int = self.embed_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """`[B, 3, H, W]` -> the patch grid as a map, `[B, C, 16, 16]`."""
        if self.cfg.frozen:
            with torch.no_grad():
                tokens = self.backbone.forward_features(x)
        else:
            tokens = self.backbone.forward_features(x)

        patches = tokens[:, self.num_prefix:, :]          # drop CLS / register tokens
        b, n, c = patches.shape
        expected = self.native_grid**2
        if n != expected:
            raise RuntimeError(
                f"expected {expected} patch tokens for a {self.native_grid}x"
                f"{self.native_grid} grid, got {n}. Check img_size against the "
                f"model's patch size ({self.patch_size}) — the reshape below "
                f"assumes a square grid."
            )

        return patches.transpose(1, 2).reshape(
            b, c, self.native_grid, self.native_grid
        )


class DualPathEncoder(nn.Module):
    """Both frozen branches plus their adapters — the whole Stage 1 in one place.

    This is the **uncached** reference path: images in, aligned sequences out. It
    is what ONNX export traces and what the tests assert geometry against. The
    cached training path splits it in two, using `frozen_maps()` to fill the
    cache and `MFSTNet`'s own adapters to project on load.

    Equality of the two aligned maps is asserted rather than assumed, because the
    failure it guards is silent at write time and fatal at run time.
    """

    def __init__(self, cfg: EncoderConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or EncoderConfig()
        self.cnn = CNNBranch(self.cfg)
        self.vit = ViTBranch(self.cfg)
        self.adapt_cnn = ProjectionAdapter(
            self.cnn.out_channels, self.cfg.d_model, self.cfg.grid
        )
        self.adapt_vit = ProjectionAdapter(
            self.vit.out_channels, self.cfg.d_model, self.cfg.grid
        )

    def frozen_maps(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Raw backbone output — **exactly what the ADR-005 cache stores**.

        `[B, 2048, 7, 7]` and `[B, 384, 16, 16]` for the default pair. Nothing
        trainable has touched these, which is the property that makes caching
        them sound.
        """
        return self.cnn(x), self.vit(x)

    def forward_maps(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """`[B, 3, H, W]` -> two aligned `[B, D, G, G]` maps.

        ROI pooling needs a map, so this is the shape the model works in.
        """
        cnn_raw, vit_raw = self.frozen_maps(x)
        cnn_map = self.adapt_cnn(cnn_raw)
        vit_map = self.adapt_vit(vit_raw)

        if cnn_map.shape != vit_map.shape:
            raise RuntimeError(
                f"branch maps disagree: CNN {tuple(cnn_map.shape)} vs ViT "
                f"{tuple(vit_map.shape)}. This is the A24 defect — the gate is "
                f"elementwise and cannot combine them."
            )
        return cnn_map, vit_map

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """`[B, 3, H, W]` -> `(f_cnn, f_vit)`, each `[B, G², D]`."""
        cnn_map, vit_map = self.forward_maps(x)
        return (
            cnn_map.flatten(2).transpose(1, 2),
            vit_map.flatten(2).transpose(1, 2),
        )

    @property
    def trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
