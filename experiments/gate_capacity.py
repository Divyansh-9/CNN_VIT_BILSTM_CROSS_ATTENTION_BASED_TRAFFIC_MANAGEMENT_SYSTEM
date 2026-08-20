"""Can the gate learn to be input-dependent at all? (P36, FR-M04, P16)

The gate is a research artifact, not an implementation detail: it is logged,
tracked on the dashboard (FR-UI05), and analysed in the paper. So the first
question about it is not "what value does it take" but **"can it take more than
one value"**.

On the pilot corpus it could not, in practice. Across every run it sat at
`mean ~0.54, std ~0.005` — one number for every spatial location and every
timestep, which is a learned scalar blend rather than a gate.

Measuring why gave the mechanism. `z_a` and `z_b` are nearly orthogonal
(cosine -0.004), so they do carry different information, but their magnitude is
small: **std 0.035**. The gate is `sigmoid(Linear([z_a; z_b]))`, so its
pre-activation has std 0.023, and the sigmoid's slope at zero is 0.25 — giving
a gate std of 0.006, which is what is observed. To reach saturation the
Linear's weights would have to grow by roughly two orders of magnitude, and
weight decay pulls the other way.

That is a statement about the architecture, not about the data. This script
asks the empirical question the statement provokes: **given a task that can
only be solved by gating, does the gate learn to gate?**

    python experiments/gate_capacity.py

The task is built so that neither branch alone can win. A per-sample cue
decides which branch carries the label; the other carries noise. A constant
gate is then capped near chance, and only an input-dependent one can do better.
Config F (bidirectional, no gate) is trained on the same data as the control:
if F matches G, the gate contributed nothing.

**This is a diagnostic, not a result for the paper.** It runs on synthetic
tensors and answers a question about capacity.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS = Path("experiments/results/gate_capacity.csv")


def make_task(n: int, cfg, *, timesteps: int, generator):
    """Half the samples carry the label in the CNN branch, half in the ViT.

    The cue is which branch holds a coherent signal; the other holds noise. A
    single fixed blend cannot recover both, so the ceiling for a constant gate
    is well below the ceiling for a gate that reads its input.
    """
    import torch

    grid = cfg.encoder.grid
    labels = torch.randint(0, cfg.n_classes, (n,), generator=generator)
    from_cnn = torch.zeros(n, dtype=torch.bool)
    from_cnn[: n // 2] = True

    cnn = torch.randn(n, timesteps, cfg.encoder.cnn_channels, grid, grid,
                      generator=generator)
    vit = torch.randn(n, timesteps, cfg.encoder.vit_channels, grid, grid,
                      generator=generator)

    # The signal is a constant offset on a class-specific channel, strong
    # enough to be separable and confined to the branch that owns the sample.
    for i in range(n):
        channel = int(labels[i])
        if from_cnn[i]:
            cnn[i, :, channel] += 6.0
        else:
            vit[i, :, channel] += 6.0
    return cnn, vit, labels, from_cnn


def run(name: str, *, n: int, timesteps: int, steps: int, lr: float,
        seed: int, device: str) -> dict:
    import torch

    from mfstnet.model import MFSTNet, ablation_config
    from scripts.seed import set_seed

    set_seed(seed)
    cfg = dataclasses.replace(ablation_config(name), n_lanes=1)
    grid = cfg.encoder.grid
    masks = torch.ones(1, grid, grid) / (grid * grid)

    generator = torch.Generator().manual_seed(seed)
    cnn, vit, labels, from_cnn = make_task(n, cfg, timesteps=timesteps,
                                           generator=generator)
    cnn, vit = cnn.to(device), vit.to(device)
    labels = labels.to(device)

    model = MFSTNet(cfg, masks).to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = torch.nn.CrossEntropyLoss()

    first_gate = last_gate = None
    for step in range(steps):
        model.train()
        out = model(cnn, vit)
        loss = criterion(out.logits.reshape(-1, cfg.n_classes), labels)
        optimiser.zero_grad()
        loss.backward()
        optimiser.step()
        if out.gate is not None:
            stats = (out.gate.mean().item(), out.gate.std().item())
            first_gate = first_gate or stats
            last_gate = stats

    model.eval()
    with torch.no_grad():
        out = model(cnn, vit)
        predicted = out.logits.reshape(-1, cfg.n_classes).argmax(-1)
        accuracy = (predicted == labels).float().mean().item()
        row = {"config": name, "seed": seed, "steps": steps,
               "final_loss": round(float(loss), 6),
               "accuracy": round(accuracy, 4)}
        if out.gate is not None:
            gate = out.gate.reshape(len(labels), -1).mean(dim=-1)
            row["gate_mean"] = round(out.gate.mean().item(), 5)
            row["gate_std"] = round(out.gate.std().item(), 6)
            row["gate_std_at_start"] = round(first_gate[1], 6)
            # The question the whole script exists for: does the gate take a
            # different value depending on which branch holds the signal?
            row["gate_when_cnn_carries"] = round(gate[from_cnn].mean().item(), 5)
            row["gate_when_vit_carries"] = round(gate[~from_cnn].mean().item(), 5)
            row["gate_separation"] = round(
                abs(gate[from_cnn].mean() - gate[~from_cnn].mean()).item(), 6)
        else:
            for key in ("gate_mean", "gate_std", "gate_std_at_start",
                        "gate_when_cnn_carries", "gate_when_vit_carries",
                        "gate_separation"):
                row[key] = ""
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sequences", type=int, default=64)
    parser.add_argument("--timesteps", type=int, default=8)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    from scripts.device import resolve_device

    device = resolve_device(args.device)
    print(f"  device {device}, {args.sequences} sequences, {args.steps} steps")
    print("  task: half the samples carry the label in CNN, half in ViT\n")

    rows = []
    for name in ("F", "G"):
        row = run(name, n=args.sequences, timesteps=args.timesteps,
                  steps=args.steps, lr=args.lr, seed=args.seed, device=device)
        rows.append(row)
        gate = (f"gate {row['gate_mean']} +/- {row['gate_std']}"
                if row["gate_std"] != "" else "no gate")
        print(f"  {name}: accuracy {row['accuracy']:.3f}  "
              f"loss {row['final_loss']:.4f}  {gate}")
        if row["gate_separation"] != "":
            print(f"     gate when CNN carries {row['gate_when_cnn_carries']}, "
                  f"when ViT carries {row['gate_when_vit_carries']}  "
                  f"(separation {row['gate_separation']})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  wrote {args.out}")
    print("  Diagnostic only — synthetic tensors, not a result for the paper.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
