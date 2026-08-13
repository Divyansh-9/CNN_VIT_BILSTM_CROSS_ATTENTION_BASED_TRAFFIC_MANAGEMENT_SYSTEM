"""Cross-attention fusion between the two spatial branches (PRD §8.1 Stage 2).

Every mode here is a config value, because the ablation is what makes the work
publishable and NFR-15 requires configs A–H to run without a code edit:

    none            single branch only          configs A, B
    concat          concatenate and project     config C
    unidirectional  CNN queries ViT             config D
    bidirectional   both directions             configs E, F, G

`use_gate` is separate from the mode and belongs to **Phase 2**. PRD §2.4 forbids
building it before Phase 1 trains cleanly, so it defaults to off — config E is
bidirectional *without* the gate, and G is with it.

Both inputs must already be the same length. `encoders.DualPathEncoder` guarantees
that (amendment A24); natively they are 49 and 257 and the gate cannot combine
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch
import torch.nn as nn

__all__ = ["FusionConfig", "CrossAttentionFusion"]

FusionMode = Literal["none", "concat", "unidirectional", "bidirectional"]


@dataclass(frozen=True)
class FusionConfig:
    d_model: int = 256
    n_heads: int = 4
    dropout: float = 0.1
    mode: FusionMode = "bidirectional"
    use_gate: bool = False       # Phase 2 (PRD §2.4) — off until Phase 1 converges
    use_cnn: bool = True
    use_vit: bool = True

    def __post_init__(self) -> None:
        if not (self.use_cnn or self.use_vit):
            raise ValueError("at least one branch must be enabled")
        if self.mode != "none" and not (self.use_cnn and self.use_vit):
            raise ValueError(
                f"mode={self.mode!r} needs both branches; with one branch the only "
                f"valid mode is 'none' (ablation configs A and B)"
            )
        if self.use_gate and self.mode != "bidirectional":
            raise ValueError(
                f"the gate arbitrates between two cross-attention directions, so it "
                f"requires mode='bidirectional', not {self.mode!r}"
            )


class CrossAttentionFusion(nn.Module):
    """Fuse `[B, N, D]` and `[B, N, D]` into `[B, N, D]`.

    Also returns the gate value when gating is on. **The gate is an output, not
    an internal** — BR-07, FR-M04 and FR-UI05 all depend on it being visible, and
    §14.2's density hypothesis is tested against it. Discarding it here would
    quietly remove a research claim.
    """

    def __init__(self, cfg: FusionConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or FusionConfig()
        d = self.cfg.d_model

        if self.cfg.mode == "concat":
            self.merge = nn.Linear(2 * d, d)

        if self.cfg.mode in ("unidirectional", "bidirectional"):
            self.attn_a = nn.MultiheadAttention(
                d, self.cfg.n_heads, dropout=self.cfg.dropout, batch_first=True
            )
        if self.cfg.mode == "bidirectional":
            self.attn_b = nn.MultiheadAttention(
                d, self.cfg.n_heads, dropout=self.cfg.dropout, batch_first=True
            )

        if self.cfg.use_gate:
            self.gate = nn.Linear(2 * d, 1)

        self.norm = nn.LayerNorm(d)

    def forward(
        self, f_cnn: torch.Tensor | None, f_vit: torch.Tensor | None
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        """Returns `(fused, gate)`. `gate` is `[B, N, 1]` or None."""
        cfg = self.cfg

        if cfg.mode == "none":
            single = f_cnn if cfg.use_cnn else f_vit
            if single is None:
                raise ValueError("the enabled branch received no features")
            return self.norm(single), None

        if f_cnn is None or f_vit is None:
            raise ValueError(f"mode={cfg.mode!r} needs both branches")
        if f_cnn.shape != f_vit.shape:
            raise ValueError(
                f"branch shapes disagree: {tuple(f_cnn.shape)} vs {tuple(f_vit.shape)}. "
                f"Align them first — this is the A24 defect."
            )

        if cfg.mode == "concat":
            return self.norm(self.merge(torch.cat([f_cnn, f_vit], dim=-1))), None

        # "Local features ask: what global context is relevant?"
        z_a, _ = self.attn_a(query=f_cnn, key=f_vit, value=f_vit, need_weights=False)

        if cfg.mode == "unidirectional":
            return self.norm(z_a + f_cnn), None

        # "Global context asks: what local detail matters here?"
        z_b, _ = self.attn_b(query=f_vit, key=f_cnn, value=f_cnn, need_weights=False)

        if not cfg.use_gate:
            fused = 0.5 * (z_a + z_b)
            gate = None
        else:
            gate = torch.sigmoid(self.gate(torch.cat([z_a, z_b], dim=-1)))
            fused = gate * z_a + (1.0 - gate) * z_b

        return self.norm(fused + 0.5 * (f_cnn + f_vit)), gate
