"""Overfit a handful of sequences to near-zero loss (S26, PRD §2.4).

This is the cheapest decisive test in the model track and it runs before any
real training. A network that cannot memorise ten examples has a defect —
a detached tensor, a frozen parameter that should train, a reshape that scrambles
the batch, a loss reading the wrong axis. Finding that here costs a minute.
Finding it after a 14-hour Colab run costs the run.

It deliberately fits **random** features to **random** labels. There is no signal
to generalise from, so the only way the loss can fall is memorisation, which is
exactly the capacity-and-gradient property under test. High accuracy here says
nothing about the task and is not a result — §14 metrics come from real data.

    python scripts/overfit_check.py                    # config E, Phase 1's endpoint
    python scripts/overfit_check.py --config G --steps 400
    python scripts/overfit_check.py --all              # every ablation config

Exit status is 0 only if the configs under test reached the threshold, so this
works as a pre-training gate in CI or a Makefile.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.geometry import Polygon  # noqa: E402
from mfstnet.metrics import evaluate  # noqa: E402
from mfstnet.model import ABLATION_CONFIGS, MFSTNet, ablation_config  # noqa: E402
from mfstnet.temporal import lane_masks  # noqa: E402
from scripts.seed import set_seed  # noqa: E402

# A plausible four-approach layout. Only the geometry matters here — the lanes
# must be disjoint and each must cover at least one grid cell.
# PRD §8.2. Not a free parameter to tune here — a training script that invents a
# number the specification already fixes is a defect (NFR-16), and this one bit:
# at the 1e-3 I first wrote, config F stalled at loss 0.41 and stayed there for
# 900 steps, which reads exactly like a broken graph. See BUILD-LOG S26.
PRD_LR = 1e-4

DEMO_LANES: tuple[Polygon, ...] = (
    Polygon("north", ((0.30, 0.00), (0.70, 0.00), (0.70, 0.45), (0.30, 0.45))),
    Polygon("south", ((0.30, 0.55), (0.70, 0.55), (0.70, 1.00), (0.30, 1.00))),
    Polygon("east", ((0.72, 0.30), (1.00, 0.30), (1.00, 0.70), (0.72, 0.70))),
    Polygon("west", ((0.00, 0.30), (0.28, 0.30), (0.28, 0.70), (0.00, 0.70))),
)


def run_overfit(
    config_name: str,
    *,
    n_sequences: int = 10,
    timesteps: int = 12,
    steps: int = 300,
    lr: float = PRD_LR,
    seed: int = 42,
    grid: int = 7,
    device: str = "cpu",
    verbose: bool = True,
) -> dict:
    """Fit `n_sequences` random samples and report whether the loss collapsed.

    `timesteps` is 12 rather than the PRD's T=60 on purpose: this measures
    gradient flow, not temporal modelling, and a shorter sequence makes it a
    minute rather than five. The shape logic is identical at either length.
    """
    set_seed(seed)

    cfg = ablation_config(config_name)
    masks = lane_masks(DEMO_LANES, grid)
    model = MFSTNet(cfg, masks).to(device)

    d, n_lanes = cfg.encoder.d_model, cfg.n_lanes
    shape = (n_sequences, timesteps, d, grid, grid)
    cnn = torch.randn(shape, device=device) if cfg.fusion.use_cnn else None
    vit = torch.randn(shape, device=device) if cfg.fusion.use_vit else None
    targets = torch.randint(0, cfg.n_classes, (n_sequences, n_lanes), device=device)

    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    model.train()

    started = time.perf_counter()
    first_loss = float("nan")
    loss_value = float("nan")

    for step in range(steps):
        optimiser.zero_grad(set_to_none=True)
        out = model(cnn, vit)
        loss = F.cross_entropy(
            out.logits.reshape(-1, cfg.n_classes), targets.reshape(-1)
        )
        loss.backward()
        optimiser.step()

        loss_value = float(loss.item())
        if step == 0:
            first_loss = loss_value
        if verbose and (step % max(1, steps // 6) == 0 or step == steps - 1):
            print(f"    step {step:4d}  loss {loss_value:.5f}")

    model.eval()
    with torch.no_grad():
        out = model(cnn, vit)
        final_loss = float(
            F.cross_entropy(
                out.logits.reshape(-1, cfg.n_classes), targets.reshape(-1)
            ).item()
        )
        predictions = out.predictions

    report = evaluate(targets.reshape(-1).tolist(), predictions.reshape(-1).tolist())

    return {
        "config": config_name,
        "n_sequences": n_sequences,
        "timesteps": timesteps,
        "steps": steps,
        "lr": lr,
        "seed": seed,
        "trainable_params": model.trainable_parameters,
        "initial_loss": round(first_loss, 5),
        "final_loss": round(final_loss, 6),
        "accuracy": round(report.accuracy, 4),
        "macro_f1": round(report.macro_f1, 4),
        "seconds": round(time.perf_counter() - started, 1),
        "gate_mean": (
            None if out.gate_mean is None else round(float(out.gate_mean.mean()), 4)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default="E", help="ablation config (default E)")
    parser.add_argument("--all", action="store_true", help="run every config A-H")
    parser.add_argument("--sequences", type=int, default=10)
    parser.add_argument("--timesteps", type=int, default=12)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--lr", type=float, default=PRD_LR, help="PRD §8.2 value")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--loss-threshold", type=float, default=0.05,
        help="pass if the final loss falls below this (default 0.05)",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("experiments/results/overfit_check.csv"),
        help="CSV of results; written by this script, never transcribed (NFR-09)",
    )
    args = parser.parse_args(argv)

    names = list(ABLATION_CONFIGS) if args.all else [args.config.upper()]
    rows: list[dict] = []
    failures: list[str] = []

    for name in names:
        print(f"\n  config {name}")
        row = run_overfit(
            name,
            n_sequences=args.sequences,
            timesteps=args.timesteps,
            steps=args.steps,
            lr=args.lr,
            seed=args.seed,
        )
        rows.append(row)

        passed = row["final_loss"] < args.loss_threshold
        verdict = "PASS" if passed else "FAIL"
        print(
            f"    {verdict}  loss {row['initial_loss']:.4f} -> {row['final_loss']:.6f}"
            f"   accuracy {row['accuracy']:.2f}"
            f"   {row['trainable_params']:,} params   {row['seconds']}s"
        )
        if not passed:
            failures.append(name)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  wrote {args.out}")

    if failures:
        print(
            f"\n  FAILED: {', '.join(failures)} did not reach loss < "
            f"{args.loss_threshold}.\n"
            f"  Do not start real training. A model that cannot memorise "
            f"{args.sequences} samples has a defect in the graph, not a\n"
            f"  hyperparameter problem — check for detached tensors, a reshape "
            f"that scrambles the batch axis, or a\n"
            f"  parameter that should be trainable and is not."
        )
        return 1

    print("  all configs memorised the sample. The graph trains; proceed to §14.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
