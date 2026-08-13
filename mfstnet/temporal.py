"""Temporal modelling and the per-lane congestion head (PRD §8.1 Stages 3–4).

Two things here are amendments rather than the original design, and both matter.

**Per-lane ROI pooling (A8).** §8.1 originally pooled the fused map globally and
then applied one shared head four times. Same input, same weights, four
applications — four *identical* predictions, guaranteed by arithmetic. Pooling
each lane over its own region of the map is what makes four different answers
possible, and it is why the feature cache must keep spatial structure.

**Config H, the linear probe (A22).** Every other ablation config contains the
BiLSTM, so none of them answers the cheapest question a reviewer asks of a
frozen-backbone model: does the temporal machinery do anything? H replaces it
with a mean over time. If H approaches G, the architecture is unjustified — and
that is a result, not a failure to hide.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

import torch
import torch.nn as nn

from .corpus.geometry import Polygon

__all__ = ["TemporalConfig", "lane_masks", "LanePool", "TemporalEncoder", "CongestionHead"]

Pooling = Literal["last", "mean", "attention"]


@dataclass(frozen=True)
class TemporalConfig:
    d_model: int = 256
    hidden: int = 128            # PRD §8.2 — bidirectional, so 2x128 = 256 out
    layers: int = 2
    dropout: float = 0.2
    use_bilstm: bool = True      # False = config H, the linear probe
    use_temporal_attn: bool = False   # Phase 2
    attn_heads: int = 4
    attn_layers: int = 2
    pooling: Pooling = "attention"


def lane_masks(
    polygons: Sequence[Polygon], grid: int, *, min_cells: int = 1
) -> torch.Tensor:
    """Build `[n_lanes, grid, grid]` weights by testing each cell's centre.

    Returns normalised weights, so pooling is a weighted mean and lanes covering
    different numbers of cells stay comparable.

    A lane that captures fewer than `min_cells` cells raises rather than
    returning zeros: at G=7 a small approach may cover two or three cells, and a
    lane covering none would silently pool nothing and predict from noise.
    """
    masks = torch.zeros(len(polygons), grid, grid)
    for i, poly in enumerate(polygons):
        for r in range(grid):
            for c in range(grid):
                cx, cy = (c + 0.5) / grid, (r + 0.5) / grid
                if poly.contains((cx, cy)):
                    masks[i, r, c] = 1.0
        covered = int(masks[i].sum().item())
        if covered < min_cells:
            raise ValueError(
                f"lane {poly.name!r} covers {covered} of {grid * grid} grid cells. "
                f"Raise the grid (config `fusion.grid`) or redraw the polygon — "
                f"pooling an empty region predicts from noise."
            )
        masks[i] /= masks[i].sum()
    return masks


class LanePool(nn.Module):
    """Pool a fused map into one vector per lane (amendment A8)."""

    def __init__(self, masks: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer("masks", masks)          # [L, G, G], moves with .to()

    @property
    def n_lanes(self) -> int:
        return int(self.masks.shape[0])

    def forward(self, maps: torch.Tensor) -> torch.Tensor:
        """`[B, T, D, G, G]` -> `[B, T, L, D]`."""
        if maps.dim() != 5:
            raise ValueError(f"expected [B, T, D, G, G], got {tuple(maps.shape)}")
        return torch.einsum("btdhw,lhw->btld", maps, self.masks)


class _SinusoidalPE(nn.Module):
    def __init__(self, d: int, max_len: int = 512) -> None:
        super().__init__()
        pe = torch.zeros(max_len, d)
        pos = torch.arange(max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() * (-math.log(10000.0) / d))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class TemporalEncoder(nn.Module):
    """`[N, T, D]` -> `[N, D]`, one sequence per (batch item, lane).

    Lanes share weights: the same "how does a queue build" model applies to every
    approach, and sharing keeps the parameter count honest. Lane identity comes
    from the ROI pooling upstream, not from separate heads.
    """

    def __init__(self, cfg: TemporalConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or TemporalConfig()
        d = self.cfg.d_model

        if self.cfg.use_bilstm:
            if 2 * self.cfg.hidden != d:
                raise ValueError(
                    f"bidirectional hidden 2x{self.cfg.hidden} must equal d_model {d}"
                )
            self.rnn = nn.LSTM(
                d, self.cfg.hidden, self.cfg.layers,
                batch_first=True, bidirectional=True,
                dropout=self.cfg.dropout if self.cfg.layers > 1 else 0.0,
            )

        if self.cfg.use_temporal_attn:
            self.pe = _SinusoidalPE(d)
            layer = nn.TransformerEncoderLayer(
                d, self.cfg.attn_heads, dim_feedforward=2 * d,
                dropout=0.1, batch_first=True,
            )
            self.attn = nn.TransformerEncoder(layer, self.cfg.attn_layers)

        if self.cfg.pooling == "attention":
            self.pool_score = nn.Linear(d, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        cfg = self.cfg
        h_n: torch.Tensor | None = None
        if cfg.use_bilstm:
            x, (h_n, _) = self.rnn(x)
        if cfg.use_temporal_attn:
            x = self.attn(self.pe(x))
            h_n = None            # the sequence has been rewritten; h_n is stale

        if cfg.pooling == "last":
            return self._last(x, h_n)
        if cfg.pooling == "mean":
            return x.mean(dim=1)
        weights = torch.softmax(self.pool_score(x), dim=1)
        return (weights * x).sum(dim=1)

    @staticmethod
    def _last(x: torch.Tensor, h_n: torch.Tensor | None) -> torch.Tensor:
        """"Last hidden state" for a *bidirectional* LSTM is `h_n`, not `x[:, -1]`.

        The obvious `x[:, -1, :]` is wrong here and wrong quietly. It is the
        concatenation of the forward direction at t=T — which has seen the whole
        sequence — with the **backward** direction at t=T, which has seen one
        frame and whose previous hidden state is still zero. So the backward half
        contributes almost nothing, and its recurrent matrix `weight_hh_reverse`
        in the final layer never enters the graph at all: it receives exactly
        zero gradient for the entire run. Half the "bidirectional" is decorative.

        `h_n` holds each direction's *own* final state — forward at t=T, backward
        at t=1 — which is the summary both halves actually computed. Caught by
        the all-parameters-have-gradients test, not by the loss curve: the model
        still trains, just with a dead module and an overstated architecture.
        """
        if h_n is None:
            return x[:, -1, :]
        return torch.cat([h_n[-2], h_n[-1]], dim=-1)   # last layer, both directions


class CongestionHead(nn.Module):
    """Shared per-lane classifier (PRD §8.1 Stage 4). `[N, D]` -> `[N, 3]`."""

    def __init__(self, d_model: int = 256, hidden: int = 128,
                 n_classes: int = 3, dropout: float = 0.1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, hidden), nn.ReLU(),
            nn.Dropout(dropout), nn.Linear(hidden, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
