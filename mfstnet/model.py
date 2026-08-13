"""MFSTNet assembled, and the eight ablation configs (PRD §8.1, §14.4).

The forward pass consumes **cached backbone features**, not images. That is not
an optimisation detail, it is ADR-005's architecture: the backbones are frozen,
so they emit identical features every epoch, and at batch 32 x T=60 an uncached
step pushes 1,920 frames through both of them — which does not fit in 6 GB and
is tight even on a T4. One cache serves all eight configs. `encode_clip()` is
the only place images are touched.

Shapes end to end, with B batch, T timesteps, D d_model, G grid, L lanes:

    cached maps       [B, T, 2048, 7, 7] and [B, T, 384, 16, 16]   raw + frozen
    adapters          [B*T, G², D]             trainable 1x1 + resize to G
    fusion            [B*T, G², D]             cross-attention over space
    lane pooling      [B, T, L, D]             per-lane ROI (amendment A8)
    temporal          [B*L, T, D] -> [B*L, D]  lanes share weights
    head              [B, L, 3]                LOW / MEDIUM / HIGH at t+60s

Two things this file refuses to do quietly:

* **The gate is returned, never discarded.** BR-07, FR-M04 and FR-UI05 depend on
  it, and §14.2's density hypothesis is tested against it.
* **Config H is a real config**, not a footnote. If the linear probe approaches
  the full model, the architecture is unjustified and that is the result (BR-19).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterator

import torch
import torch.nn as nn

from .encoders import DualPathEncoder, EncoderConfig, ProjectionAdapter
from .fusion import CrossAttentionFusion, FusionConfig
from .temporal import CongestionHead, LanePool, TemporalConfig, TemporalEncoder

__all__ = ["MFSTNetConfig", "MFSTNetOutput", "MFSTNet", "ABLATION_CONFIGS", "ablation_config"]


@dataclass(frozen=True)
class MFSTNetConfig:
    name: str = "G"
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    temporal: TemporalConfig = field(default_factory=TemporalConfig)
    n_lanes: int = 4
    n_classes: int = 3
    head_hidden: int = 128       # 0 = a bare Linear, which is what config H means

    def __post_init__(self) -> None:
        d = self.encoder.d_model
        if not (self.fusion.d_model == self.temporal.d_model == d):
            raise ValueError(
                f"d_model disagrees across stages: encoder {d}, fusion "
                f"{self.fusion.d_model}, temporal {self.temporal.d_model}"
            )


@dataclass
class MFSTNetOutput:
    """`logits` is `[B, L, n_classes]`. `gate` is `[B, T, G², 1]` or None."""

    logits: torch.Tensor
    gate: torch.Tensor | None = None

    @property
    def predictions(self) -> torch.Tensor:
        return self.logits.argmax(dim=-1)

    @property
    def gate_mean(self) -> torch.Tensor | None:
        """Scalar per batch item. Logged per FR-M04 and tracked on the dashboard.

        Note this is *not* the PPO state feature — amendment A16 removed
        `mfst_gate_mean` from the state vector, because SUMO has no camera and so
        no analogue for it. It stays a research and monitoring output.
        """
        return None if self.gate is None else self.gate.mean(dim=(1, 2, 3))


class MFSTNet(nn.Module):
    """Fusion, temporal modelling and the per-lane head over cached features.

    The backbones are deliberately **not** owned here. They are frozen, they run
    once into the cache, and keeping them out means the ablation harness can
    build all eight configs without loading 45 M parameters eight times.
    """

    def __init__(self, cfg: MFSTNetConfig, lane_masks: torch.Tensor) -> None:
        super().__init__()
        if lane_masks.shape[0] != cfg.n_lanes:
            raise ValueError(
                f"config declares {cfg.n_lanes} lanes but {lane_masks.shape[0]} "
                f"masks were supplied"
            )
        grid = cfg.encoder.grid
        if tuple(lane_masks.shape[1:]) != (grid, grid):
            raise ValueError(
                f"lane masks are {tuple(lane_masks.shape[1:])} but the encoder "
                f"grid is {grid}x{grid}"
            )

        self.cfg = cfg
        # The trainable adapters live HERE, not in the encoder, because the cache
        # stores raw frozen output. Caching a projected map would bake a
        # randomly-initialised adapter in permanently — silently, and with a loss
        # curve that still falls. See `encoders.ProjectionAdapter`.
        enc = cfg.encoder
        self.adapt_cnn = (
            ProjectionAdapter(enc.cnn_channels, enc.d_model, enc.grid)
            if cfg.fusion.use_cnn else None
        )
        self.adapt_vit = (
            ProjectionAdapter(enc.vit_channels, enc.d_model, enc.grid)
            if cfg.fusion.use_vit else None
        )
        self.fusion = CrossAttentionFusion(cfg.fusion)
        self.lane_pool = LanePool(lane_masks)
        self.temporal = TemporalEncoder(cfg.temporal)
        self.head = (
            nn.Linear(cfg.encoder.d_model, cfg.n_classes)
            if cfg.head_hidden == 0
            else CongestionHead(cfg.encoder.d_model, cfg.head_hidden, cfg.n_classes)
        )

    # ------------------------------------------------------------------ api --

    def forward(
        self, cnn_maps: torch.Tensor | None, vit_maps: torch.Tensor | None
    ) -> MFSTNetOutput:
        """Raw cached maps `[B, T, C, h, w]` -> per-lane logits `[B, L, classes]`.

        The two branches arrive at *different* shapes — that is the A24 defect in
        its natural state. Alignment happens in the adapters, inside this model,
        because they train.

        A branch the config disables may be passed as None; passing a tensor for
        a disabled branch raises rather than silently ignoring it, because a
        config that reads one way and computes another invalidates the ablation.
        """
        cnn_maps, vit_maps = self._check_inputs(cnn_maps, vit_maps)
        present = cnn_maps if cnn_maps is not None else vit_maps
        assert present is not None
        b, t = present.shape[:2]
        d, g = self.cfg.encoder.d_model, self.cfg.encoder.grid

        # Fusion is spatial and time-invariant, so time folds into the batch. The
        # adapters run here, on the way out of the cache — they are trainable and
        # so cannot have run on the way in.
        flat_cnn = _adapt(cnn_maps, self.adapt_cnn)
        flat_vit = _adapt(vit_maps, self.adapt_vit)
        fused, gate = self.fusion(flat_cnn, flat_vit)            # [B*T, G², D]

        maps = fused.transpose(1, 2).reshape(b, t, d, g, g)
        lanes = self.lane_pool(maps)                             # [B, T, L, D]

        # One sequence per (item, lane); lanes share temporal weights.
        seqs = lanes.permute(0, 2, 1, 3).reshape(b * self.cfg.n_lanes, t, d)
        pooled = self.temporal(seqs)                             # [B*L, D]
        logits = self.head(pooled).reshape(b, self.cfg.n_lanes, self.cfg.n_classes)

        return MFSTNetOutput(
            logits=logits,
            gate=None if gate is None else gate.reshape(b, t, g * g, 1),
        )

    @torch.no_grad()
    def encode_clip(
        self, frames: torch.Tensor, encoder: DualPathEncoder, *, chunk: int = 32
    ) -> tuple[torch.Tensor | None, torch.Tensor | None]:
        """`[T, 3, H, W]` -> the cached maps this model consumes, `[1, T, D, G, G]`.

        Chunked because the whole point of the cache is that T frames through two
        backbones does not fit at once. Disabled branches return None so config A
        never pays for the ViT.
        """
        cnn_out: list[torch.Tensor] = []
        vit_out: list[torch.Tensor] = []
        for start in range(0, frames.shape[0], chunk):
            batch = frames[start : start + chunk]
            # `.cnn` / `.vit`, never `.adapt_*` — only the frozen half is cacheable.
            if self.cfg.fusion.use_cnn:
                cnn_out.append(encoder.cnn(batch))
            if self.cfg.fusion.use_vit:
                vit_out.append(encoder.vit(batch))
        return (
            torch.cat(cnn_out).unsqueeze(0) if cnn_out else None,
            torch.cat(vit_out).unsqueeze(0) if vit_out else None,
        )

    @property
    def trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # -------------------------------------------------------------- internal --

    def _check_inputs(
        self, cnn_maps: torch.Tensor | None, vit_maps: torch.Tensor | None
    ) -> tuple[torch.Tensor | None, torch.Tensor | None]:
        for name, tensor, enabled in (
            ("CNN", cnn_maps, self.cfg.fusion.use_cnn),
            ("ViT", vit_maps, self.cfg.fusion.use_vit),
        ):
            if enabled and tensor is None:
                raise ValueError(
                    f"config {self.cfg.name!r} enables the {name} branch but no "
                    f"{name} features were passed"
                )
            if not enabled and tensor is not None:
                raise ValueError(
                    f"config {self.cfg.name!r} disables the {name} branch, but "
                    f"{name} features were passed. Silently ignoring them would "
                    f"make the ablation table describe a model that was not run."
                )
            if tensor is not None and tensor.dim() != 5:
                raise ValueError(
                    f"expected {name} features [B, T, C, h, w], got "
                    f"{tuple(tensor.shape)}"
                )

        # The two branches legitimately differ in shape here — 2048x7x7 against
        # 384x16x16 — so they are checked against the config, not against each
        # other. Channel count is the part of the geometry that identifies the
        # backbone, and a mismatch means the cache was written by a different one.
        enc = self.cfg.encoder
        for name, tensor, expected in (
            ("CNN", cnn_maps, enc.cnn_channels),
            ("ViT", vit_maps, enc.vit_channels),
        ):
            if tensor is not None and tensor.shape[2] != expected:
                raise ValueError(
                    f"{name} cache has {tensor.shape[2]} channels, but "
                    f"{enc.cnn if name == 'CNN' else enc.vit!r} produces "
                    f"{expected}. This cache was written by a different backbone "
                    f"— a preprocessing_hash mismatch (ADR-005). Rebuild it; do "
                    f"not train on it."
                )
        if cnn_maps is not None and vit_maps is not None:
            if cnn_maps.shape[:2] != vit_maps.shape[:2]:
                raise ValueError(
                    f"branch caches cover different batches or lengths: "
                    f"{tuple(cnn_maps.shape[:2])} vs {tuple(vit_maps.shape[:2])}"
                )
        return cnn_maps, vit_maps


def _adapt(
    maps: torch.Tensor | None, adapter: ProjectionAdapter | None
) -> torch.Tensor | None:
    """Raw cached `[B, T, C, h, w]` -> aligned `[B*T, G², D]`.

    Time folds into the batch because the adapter is a 1x1 convolution and knows
    nothing about time.
    """
    if maps is None or adapter is None:
        return None
    b, t, c, h, w = maps.shape
    projected = adapter(maps.reshape(b * t, c, h, w))       # [B*T, D, G, G]
    return projected.flatten(2).transpose(1, 2)


# ---------------------------------------------------------- ablation configs --

def ablation_config(name: str, base: MFSTNetConfig | None = None) -> MFSTNetConfig:
    """Build one of the eight PRD §14.4 configs.

    Every difference between configs is expressed here as data. NFR-15 requires
    the whole table to run with no code edit between rows, so if a config ever
    needs a branch in the model, the design has gone wrong.
    """
    key = name.strip().upper()
    if key not in _ABLATION_SPECS:
        raise ValueError(
            f"unknown ablation config {name!r}; expected one of "
            f"{sorted(_ABLATION_SPECS)}"
        )
    base = base or MFSTNetConfig()
    fusion_kw, temporal_kw, head_hidden = _ABLATION_SPECS[key]
    return replace(
        base,
        name=key,
        fusion=replace(base.fusion, **fusion_kw),
        temporal=replace(base.temporal, **temporal_kw),
        head_hidden=head_hidden,
    )


# (fusion overrides, temporal overrides, head hidden width)
_ABLATION_SPECS: dict[str, tuple[dict, dict, int]] = {
    # A — CNN only
    "A": ({"mode": "none", "use_cnn": True, "use_vit": False, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": False, "pooling": "last"}, 128),
    # B — ViT only
    "B": ({"mode": "none", "use_cnn": False, "use_vit": True, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": False, "pooling": "last"}, 128),
    # C — naive fusion (concatenate and project)
    "C": ({"mode": "concat", "use_cnn": True, "use_vit": True, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": False, "pooling": "last"}, 128),
    # D — one direction of cross-attention (CNN queries ViT)
    "D": ({"mode": "unidirectional", "use_cnn": True, "use_vit": True, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": False, "pooling": "last"}, 128),
    # E — bidirectional, averaged rather than gated. Phase 1's endpoint.
    "E": ({"mode": "bidirectional", "use_cnn": True, "use_vit": True, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": False, "pooling": "last"}, 128),
    # F — E plus temporal self-attention and attention pooling
    "F": ({"mode": "bidirectional", "use_cnn": True, "use_vit": True, "use_gate": False},
          {"use_bilstm": True, "use_temporal_attn": True, "pooling": "attention"}, 128),
    # G — full MFSTNet: F plus the gate
    "G": ({"mode": "bidirectional", "use_cnn": True, "use_vit": True, "use_gate": True},
          {"use_bilstm": True, "use_temporal_attn": True, "pooling": "attention"}, 128),
    # H — linear probe (A22). No fusion, no recurrence, no attention: pool the
    # lane over time with a mean and classify. The floor every frozen-backbone
    # paper is expected to report.
    "H": ({"mode": "concat", "use_cnn": True, "use_vit": True, "use_gate": False},
          {"use_bilstm": False, "use_temporal_attn": False, "pooling": "mean"}, 0),
}

ABLATION_CONFIGS: tuple[str, ...] = tuple(_ABLATION_SPECS)


def iter_ablation_configs(
    base: MFSTNetConfig | None = None,
) -> Iterator[MFSTNetConfig]:
    for name in ABLATION_CONFIGS:
        yield ablation_config(name, base)
