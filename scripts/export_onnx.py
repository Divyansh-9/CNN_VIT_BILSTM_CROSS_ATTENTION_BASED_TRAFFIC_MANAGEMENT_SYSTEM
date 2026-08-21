"""Export MFSTNet to ONNX and measure server-CPU latency (S31, PRD §16).

    python scripts/export_onnx.py --config G
    python scripts/export_onnx.py --all --out models/onnx

PRD's latency budget for MFSTNet is **150 ms on server CPU via ONNX Runtime**.
This exports the graph, checks it against PyTorch on the same input, times it,
and writes `experiments/results/onnx_latency.csv`.

**What the exported graph covers, and what it does not.** `MFSTNet` deliberately
does not own the backbones (ADR-005): they are frozen, they run once into the
feature cache, and keeping them out is what lets the ablation build eight
configs without loading 45 M parameters eight times. So the graph exported here
takes *cached feature maps* and the 150 ms budget, measured against it, is a
budget for the head alone.

At deployment there is no cache. A server handed a 60-frame window has to run
ResNet-50 and DINOv2 over all 60 frames before this graph can start, and that
cost is not optional or amortised. **Both numbers are measured and both are
written to the CSV** — `head_ms` and `backbone_ms` — because reporting only the
first would satisfy the budget by leaving out most of the work. ADR-003 already
requires every latency figure to name its measurement host; this requires it to
name its scope too.

**Lane geometry is baked in, not an input.** `MFSTNet` accepts optional
per-sample masks so one training batch can span cameras (P26). A deployed edge
node watches one junction, so the export uses the construction masks and the
graph has no mask input. Re-export when the geometry changes -- which is also
what P23 requires of anything downstream of a lane centre.

**INT8 is not applied here.** ADR-007 puts quantisation at export time, but an
INT8 graph must be calibrated on real feature windows and validated against the
fp32 one on the test split, not spot-checked on random tensors. That belongs
with a trained checkpoint; this writes the fp32 graph the calibration will
start from.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

RESULTS = Path("experiments/results/onnx_latency.csv")
OUT_DIR = Path("models/onnx")
BUDGET_MS = 150.0            # PRD §16, server CPU
WARMUP = 3
REPEATS = 20


class ExportWrapper:
    """Deferred so `--help` does not import torch. Built by `build_wrapper`."""


def build_wrapper(model, *, use_cnn: bool, use_vit: bool):
    """An `nn.Module` returning tensors, because ONNX cannot export a dataclass.

    A branch the config disables is left out of the signature entirely rather
    than passed as `None`: ONNX has no null, and a zero tensor for a disabled
    branch would export a graph that computes something the config says it does
    not.
    """
    import torch.nn as nn

    class Wrapped(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.inner = model

        if use_cnn and use_vit:
            def forward(self, cnn_maps, vit_maps):
                out = self.inner(cnn_maps, vit_maps)
                return ((out.logits,) if out.gate is None
                        else (out.logits, out.gate))
        elif use_cnn:
            def forward(self, cnn_maps):
                return (self.inner(cnn_maps, None).logits,)
        else:
            def forward(self, vit_maps):
                return (self.inner(None, vit_maps).logits,)

    return Wrapped().eval()


def sample_inputs(config, *, batch: int, timesteps: int):
    """Random feature maps shaped like the cache writes them.

    Random is correct for a *latency* and *graph parity* measurement -- neither
    depends on the values -- and is wrong for anything about accuracy, which is
    why nothing here reports a metric.
    """
    import torch

    enc = config.encoder
    made = {}
    if config.fusion.use_cnn:
        made["cnn_maps"] = torch.randn(batch, timesteps, enc.cnn_channels, 7, 7)
    if config.fusion.use_vit:
        made["vit_maps"] = torch.randn(batch, timesteps, enc.vit_channels, 16, 16)
    return made


def backbone_latency(timesteps: int, *, repeats: int = 3) -> float:
    """Milliseconds to run both frozen backbones over one T-frame window, CPU.

    This is the cost the cache hides. It is measured once per invocation rather
    than per config, because the backbones are the same in every config that
    uses them.
    """
    import torch

    from mfstnet.encoders import CNNBranch, EncoderConfig, ViTBranch

    enc = EncoderConfig()
    cnn = CNNBranch(enc).eval()
    vit = ViTBranch(enc).eval()
    frames = torch.randn(timesteps, 3, enc.image_size, enc.image_size)

    with torch.no_grad():
        cnn(frames[:2]), vit(frames[:2])            # warm up
        started = time.perf_counter()
        for _ in range(repeats):
            cnn(frames)
            vit(frames)
        elapsed = time.perf_counter() - started
    return elapsed / repeats * 1000.0


def export_one(name: str, *, out_dir: Path, batch: int, timesteps: int,
               opset: int) -> dict:
    import numpy as np
    import onnxruntime
    import torch

    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks_from_centres
    from mfstnet.corpus.lanes import LaneCentres
    from scripts.seed import set_seed

    set_seed(42)                                    # NFR-07
    config = ablation_config(name)
    # Four evenly spaced centres. The geometry is baked into the graph, so a
    # real export takes the corpus manifest's centres; this default exists so
    # the harness can be exercised before a camera is chosen.
    centres = LaneCentres(
        names=tuple(f"lane_{i}" for i in range(config.n_lanes)),
        centres=tuple((0.2 + 0.2 * i, 0.5) for i in range(config.n_lanes)),
        max_radius=0.25,
    )
    masks = lane_masks_from_centres(centres, config.encoder.grid)
    model = MFSTNet(config, masks).eval()
    wrapper = build_wrapper(model, use_cnn=config.fusion.use_cnn,
                            use_vit=config.fusion.use_vit)

    made = sample_inputs(config, batch=batch, timesteps=timesteps)
    names = list(made)
    args = tuple(made[n] for n in names)

    with torch.no_grad():
        reference = wrapper(*args)
    outputs = ["logits"] + (["gate"] if len(reference) > 1 else [])

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"mfstnet_{name}.onnx"
    torch.onnx.export(
        wrapper, args, str(path),
        input_names=names, output_names=outputs,
        # Batch is dynamic; T is not. A window is exactly T observations by
        # A15's arithmetic, and a graph that accepts a shorter one would accept
        # a window whose label sits at the wrong horizon.
        dynamic_axes={n: {0: "batch"} for n in names + outputs},
        opset_version=opset, do_constant_folding=True,
    )

    session = onnxruntime.InferenceSession(
        str(path), providers=["CPUExecutionProvider"])
    feed = {n: made[n].numpy() for n in names}

    got = session.run(None, feed)
    drift = max(float(np.abs(a - b.detach().numpy()).max())
                for a, b in zip(got, reference))

    for _ in range(WARMUP):
        session.run(None, feed)
    timings = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        session.run(None, feed)
        timings.append((time.perf_counter() - started) * 1000.0)
    timings.sort()

    return {
        "config": name,
        "batch": batch,
        "timesteps": timesteps,
        "opset": opset,
        "parameters": sum(p.numel() for p in model.parameters()),
        "exposes_gate": "gate" in outputs,
        "onnx_vs_torch_max_abs": f"{drift:.3e}",
        "head_ms_mean": round(statistics.fmean(timings), 2),
        "head_ms_p50": round(statistics.median(timings), 2),
        "head_ms_p95": round(timings[int(0.95 * (len(timings) - 1))], 2),
        "size_mb": round(path.stat().st_size / 1e6, 2),
        "path": str(path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default="G")
    parser.add_argument("--all", action="store_true",
                        help="every ablation config, A-H")
    parser.add_argument("--batch", type=int, default=1,
                        help="a server predicts for one intersection at a time")
    parser.add_argument("--timesteps", type=int, default=60, help="T, PRD §8.2")
    parser.add_argument("--opset", type=int, default=18,
                        help="17 fails the version downgrade for "
                             "Resize and falls back noisily; 18 "
                             "exports clean")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--skip-backbones", action="store_true",
                        help="do not time ResNet-50 + DINOv2. The head number "
                             "alone is not the deployed cost and the CSV says "
                             "so; this exists for a quick graph check")
    args = parser.parse_args(argv)

    from mfstnet.model import iter_ablation_configs

    names = ([c.name for c in iter_ablation_configs()] if args.all
             else [args.config])

    backbone_ms = None
    if not args.skip_backbones:
        print(f"  timing ResNet-50 + DINOv2 over {args.timesteps} frames on CPU")
        backbone_ms = backbone_latency(args.timesteps)
        print(f"  backbones {backbone_ms:.0f} ms per window")
        print()

    rows = []
    print("  {:<8}{:>10}{:>12}{:>12}{:>14}".format(
        "config", "head ms", "p95 ms", "size MB", "vs torch"))
    for name in names:
        row = export_one(name, out_dir=args.out, batch=args.batch,
                         timesteps=args.timesteps, opset=args.opset)
        row["backbone_ms"] = "" if backbone_ms is None else round(backbone_ms, 1)
        row["total_ms"] = ("" if backbone_ms is None
                           else round(backbone_ms + row["head_ms_mean"], 1))
        row["budget_ms"] = BUDGET_MS
        row["within_budget_head_only"] = row["head_ms_mean"] <= BUDGET_MS
        row["within_budget_deployed"] = (
            "" if backbone_ms is None else row["total_ms"] <= BUDGET_MS)
        rows.append(row)
        print("  {:<8}{:>10.2f}{:>12.2f}{:>12.2f}{:>14}".format(
            name, row["head_ms_mean"], row["head_ms_p95"], row["size_mb"],
            row["onnx_vs_torch_max_abs"]))

    args.results.parent.mkdir(parents=True, exist_ok=True)
    with args.results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    from experiments.provenance import write_sidecar

    write_sidecar(args.results, device="cpu", scope="head_only_plus_backbones",
                  opset=args.opset, timesteps=args.timesteps)

    print()
    worst = max(rows, key=lambda r: r["head_ms_mean"])
    print(f"  budget {BUDGET_MS:.0f} ms (PRD §16, server CPU)")
    print(f"  slowest head: {worst['config']} at {worst['head_ms_mean']:.1f} ms")
    if backbone_ms is not None:
        print(f"  + backbones {backbone_ms:.0f} ms = "
              f"{backbone_ms + worst['head_ms_mean']:.0f} ms deployed")
        print("  The cache hides the backbones during training. A server has no")
        print("  cache, so the deployed figure is the one the budget is about.")
    print(f"  wrote {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
