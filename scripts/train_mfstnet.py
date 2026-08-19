"""Train MFSTNet and run the §14.4 ablation (S20, PRD §8.4, NFR-15/16).

    python scripts/train_mfstnet.py --corpus data/corpus --config G
    python scripts/train_mfstnet.py --corpus data/corpus --ablation

CLAUDE.md: *"The ablation study (configs A-G, §14.4) is what makes this
publishable."* It did not exist. `overfit_check.py` fits random features to
random labels to prove the graph can learn at all — a defect test, explicitly not
a result — and `train_ppo.py` trains the controller. Nothing trained the model
the project is named after.

**Every hyperparameter is read from `spec.yaml`.** §8.4 fixes AdamW at
`lr=1e-4 wd=1e-4`, cosine annealing, 100 epochs, patience 15, batch 32,
CrossEntropyLoss with inverse-frequency class weights. A literal here that
duplicates a config value is a defect (CLAUDE.md, NFR-16).

**Configs differ by flag, never by code** (NFR-15). `--ablation` walks every
config through one code path, so a difference between two rows is a difference
between two configurations and nothing else.

**Four things are reported that an accuracy column would hide:**

* **Per-class support beside every per-class metric.** An F1 computed from nine
  examples swings wildly and means very little.
* **Gate statistics** (P16). The gate is the narrowed novelty claim and has never
  been shown to move off its 0.5 initialisation. Its standard deviation is a
  column, so the number cannot quietly stay at 0.5 through to the paper.
* **Which labels were used** (A32). Congestion labels are a deterministic
  function of the count, so count-sequence baselines observe the label-generating
  variable directly. The headline belongs on the human-verified split and every
  row records which it used.
* **Ordinal error** — `ordinal_mae`, `off_by_two_rate`, `qwk`. LOW/MEDIUM/HIGH is
  ordered, and confusing LOW with HIGH is a worse mistake than confusing LOW with
  MEDIUM. Plain accuracy treats them identically.

**The cache is verified, not trusted.** `mfstnet.cache` raises on a
preprocessing-hash mismatch rather than warning (ADR-005), because a stale cache
produces results that look normal and are wrong.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS = Path("experiments/results/ablation.csv")
CLASSES = ("LOW", "MEDIUM", "HIGH")


def load_corpus(root: Path) -> tuple[list[dict], dict]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    with (root / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{root}/sequences.csv is empty")
    return rows, manifest


def class_weights(labels, n_classes: int):
    """Inverse frequency (PRD §8.4).

    An absent class gets weight 0, not infinity. It cannot be learned either way,
    and a division by zero surfaces as NaN loss twenty minutes into a run rather
    than as a message now.
    """
    import torch

    counts = [sum(1 for y in labels if y == c) for c in range(n_classes)]
    total = sum(counts)
    weights = [(total / (n_classes * c)) if c else 0.0 for c in counts]
    absent = [CLASSES[i] for i, c in enumerate(counts) if c == 0]
    if absent:
        print(f"    absent from train: {absent} — weight 0, metrics undefined")
    return torch.tensor(weights, dtype=torch.float32), counts


class Windows:
    """Sequences -> (cnn, vit, labels), reading windows from the feature cache."""

    def __init__(self, rows, cache, lanes, source_id: str, T: int):
        self.rows, self.cache, self.lanes = rows, cache, lanes
        self.source_id, self.T = source_id, T

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index):
        import torch

        row = self.rows[index]
        cnn, vit = self.cache.read_window(
            self.source_id, row["clip_id"], int(row["start_index"]), self.T
        )
        # read_window returns [1, T, C, h, w]; the model wants [T, C, h, w] per
        # item so the batch collate produces [B, T, C, h, w]. Squeezing here
        # rather than in the model keeps the cache's shape contract intact.
        if cnn is not None and cnn.dim() == 5 and cnn.shape[0] == 1:
            cnn = cnn.squeeze(0)
        if vit is not None and vit.dim() == 5 and vit.shape[0] == 1:
            vit = vit.squeeze(0)
        labels = torch.tensor(
            [CLASSES.index(row[f"label_{lane}"]) for lane in self.lanes],
            dtype=torch.long,
        )
        return cnn, vit, labels


def batches(dataset, size: int, *, shuffle: bool, generator=None):
    import torch

    order = (
        torch.randperm(len(dataset), generator=generator).tolist()
        if shuffle else list(range(len(dataset)))
    )
    for start in range(0, len(order), size):
        chunk = [dataset[i] for i in order[start:start + size]]
        cnn = torch.stack([c for c, _, _ in chunk]) if chunk[0][0] is not None else None
        vit = torch.stack([v for _, v, _ in chunk]) if chunk[0][1] is not None else None
        yield cnn, vit, torch.stack([y for _, _, y in chunk])


def gate_stats(output) -> dict:
    """P16 — recorded every run so a constant 0.5 cannot pass unnoticed."""
    gate = getattr(output, "gate", None)
    if gate is None:
        return {"gate_mean": "", "gate_std": "", "gate_range": ""}
    flat = gate.detach().flatten().float()
    return {
        "gate_mean": round(float(flat.mean()), 5),
        "gate_std": round(float(flat.std()), 6),
        "gate_range": round(float(flat.max() - flat.min()), 6),
    }


def feed(model, cnn, vit):
    """Pass only the branches this config enables.

    `MFSTNet._check_inputs` REFUSES features for a disabled branch rather than
    ignoring them, because silently ignoring them would make the ablation table
    describe a model that was not run. Config A has no ViT, config B no CNN.
    """
    return model(
        cnn if model.cfg.fusion.use_cnn else None,
        vit if model.cfg.fusion.use_vit else None,
    )


def evaluate_split(model, dataset, size: int, lanes):
    """Predictions flattened across lanes — every lane is a labelled example."""
    import torch

    from mfstnet.metrics import evaluate

    model.eval()
    true, pred, last = [], [], None
    with torch.no_grad():
        for cnn, vit, y in batches(dataset, size, shuffle=False):
            out = feed(model, cnn, vit)
            last = out
            true.extend(y.reshape(-1).tolist())
            pred.extend(out.logits.reshape(-1, len(CLASSES)).argmax(-1).tolist())
    return evaluate(true, pred, CLASSES), last


def train_one(name, config, *, train_set, val_set, test_set, lanes, spec,
              epochs: int, seed: int):
    """`config.n_lanes` comes from the CORPUS, not from the ablation default.

    A junction has four approaches and a motorway two; the lane count is a
    property of the camera being watched (P17), so a config carrying a hardcoded
    4 would refuse every two-lane corpus. `dataclasses.replace` keeps the
    ablation flags untouched and changes only the count.
    """
    import dataclasses
    import torch

    from mfstnet.model import MFSTNet
    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.temporal import lane_masks, lane_masks_from_centres
    from scripts.seed import set_seed

    t = spec["training"]
    set_seed(seed)                      # NFR-07, before the model is built

    masks = (lane_masks_from_centres(lanes, spec.get("grid", 7))
             if isinstance(lanes, LaneCentres)
             else lane_masks(lanes, spec.get("grid", 7)))
    # P17: the lane count comes from the corpus, never from a config
    # default. Either representation answers it.
    n_lanes = (len(lanes.names) if isinstance(lanes, LaneCentres)
               else len(lanes))
    config = dataclasses.replace(config, n_lanes=n_lanes)
    model = MFSTNet(config, masks)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)

    labels = [y for _, _, ys in (train_set[i] for i in range(len(train_set)))
              for y in ys.tolist()]
    weights, counts = class_weights(labels, len(CLASSES))
    criterion = torch.nn.CrossEntropyLoss(weight=weights)

    generator = torch.Generator().manual_seed(seed)
    best, best_state, stale = float("inf"), None, 0
    started = time.perf_counter()

    for epoch in range(epochs):
        model.train()
        total = 0.0
        for cnn, vit, y in batches(train_set, t["batch_size"], shuffle=True,
                                   generator=generator):
            out = feed(model, cnn, vit)
            loss = criterion(out.logits.reshape(-1, len(CLASSES)), y.reshape(-1))
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total += float(loss)
        scheduler.step()

        val_report, _ = evaluate_split(model, val_set, t["batch_size"], lanes)
        # Early stopping on val LOSS proxy: 1 - macro F1. Accuracy would let a
        # model that predicts the majority class look like it is improving on an
        # imbalanced corpus, which this one is.
        score = 1.0 - val_report.macro_f1
        if score < best - 1e-6:
            best, stale = score, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= t["patience"]:
                print(f"    early stop at epoch {epoch} "
                      f"(patience {t['patience']})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    report, last = evaluate_split(model, test_set, t["batch_size"], lanes)

    row = {
        "config": name,
        "seed": seed,
        "epochs_run": epoch + 1,
        "trainable_params": sum(p.numel() for p in model.parameters()
                                if p.requires_grad),
        "accuracy": round(report.accuracy, 4),
        "macro_f1": round(report.macro_f1, 4),
        "weighted_f1": round(report.weighted_f1, 4),
        "ordinal_mae": round(report.ordinal_mae, 4),
        "off_by_two_rate": round(report.off_by_two_rate, 4),
        "qwk": round(report.qwk, 4),
        "n": report.n,
        "seconds": round(time.perf_counter() - started, 1),
    }
    for label, metrics in zip(CLASSES, report.per_class):
        row[f"precision_{label.lower()}"] = round(metrics.precision, 4)
        row[f"recall_{label.lower()}"] = round(metrics.recall, 4)
        row[f"f1_{label.lower()}"] = round(metrics.f1, 4)
        row[f"support_{label.lower()}"] = metrics.support
    for index, label in enumerate(CLASSES):
        row[f"train_count_{label.lower()}"] = counts[index]
    row.update(gate_stats(last))
    return row, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--config", default="G")
    parser.add_argument("--ablation", action="store_true",
                        help="every config through one code path (§14.4)")
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--source-id", default="corpus")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    import yaml

    from mfstnet.cache import FeatureCache
    from mfstnet.metrics import format_confusion_matrix
    from mfstnet.model import ablation_config, iter_ablation_configs
    from mfstnet.temporal import Polygon

    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    training = spec["training"]
    epochs = args.epochs or training["epochs"]

    rows_in, manifest = load_corpus(args.corpus)
    auto = manifest.get("auto_labelled", True)
    lane_names = manifest["lanes"]
    T = manifest["T"]

    print(f"  corpus {args.corpus}: {len(rows_in)} sequences, "
          f"{len(lane_names)} lane(s), T={T}")
    print(f"  labels: {'AUTO-LABELLED' if auto else 'HUMAN-VERIFIED'}"
          + ("  (A32 — NOT the headline split)" if auto else ""))
    print(f"  §8.4: lr={training['lr']} wd={training['weight_decay']} "
          f"epochs={epochs} patience={training['patience']} "
          f"batch={training['batch_size']}")

    if not args.cache.exists():
        raise SystemExit(
            f"\nno feature cache at {args.cache}. The backbones are frozen, so "
            f"their outputs are\ncomputed once and reused (ADR-005). Build the "
            f"cache first — and note that it is\ninvalidated by any change to "
            f"backbone, resize or normalisation, which the loader\nraises on "
            f"rather than warning about."
        )

    cache = FeatureCache(args.cache)
    cache.load_manifest()               # raises on a preprocessing-hash mismatch

    # Geometry for A8's per-lane ROI pooling, in whichever representation the
    # corpus was built with. Centres are the current one (P23); polygons remain
    # readable so a corpus built earlier still trains.
    lanes = tuple(
        Polygon(entry["name"], tuple(tuple(v) for v in entry["points"]))
        for entry in manifest.get("polygons", [])
    ) or None
    centres = manifest.get("lane_centres")
    if lanes is None and centres:
        from mfstnet.corpus.lanes import LaneCentres

        lanes = LaneCentres(
            names=tuple(e["name"] for e in centres),
            centres=tuple(tuple(e["centre"]) for e in centres),
            max_radius=float(manifest.get("max_radius", 0.25)),
        )
    if lanes is None:
        raise SystemExit(
            "the corpus manifest carries no lane geometry. ROI pooling (A8) "
            "needs a region per lane, and a corpus built without one cannot "
            "train. Rebuild with --lanes-dir from "
            "scripts/import_lane_centres.py."
        )

    split = {
        name: Windows([r for r in rows_in if r["split"] == name],
                      cache, lane_names, args.source_id, T)
        for name in ("train", "val", "test")
    }
    for name, dataset in split.items():
        if not len(dataset):
            raise SystemExit(f"the {name} split is empty — refusing to train")

    # iter_ablation_configs yields MFSTNetConfig, which carries its own name —
    # pairing it here keeps one code path for both branches (NFR-15).
    configs = (
        [(c.name, c) for c in iter_ablation_configs()] if args.ablation
        else [(args.config, ablation_config(args.config))]
    )

    rows = []
    for name, config in configs:
        print(f"\n  === config {name} ===")
        row, report = train_one(
            name, config, train_set=split["train"], val_set=split["val"],
            test_set=split["test"], lanes=lanes, spec=spec,
            epochs=epochs, seed=args.seed,
        )
        row["labels"] = "auto" if auto else "human_verified"
        row["corpus"] = str(args.corpus)
        rows.append(row)
        print(f"    macro-F1 {row['macro_f1']}  QWK {row['qwk']}  "
              f"gate std {row['gate_std'] or '—'}")
        print(format_confusion_matrix(report.confusion, CLASSES))

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n  wrote {args.out}")
    if auto:
        print("  AUTO-LABELLED (A32): count-sequence baselines observe the "
              "label-generating\n  variable directly, so this table cannot be "
              "the headline comparison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
