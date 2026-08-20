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
from scripts.device import move, resolve_device  # noqa: E402

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

    def __init__(self, rows, cache, lanes, source_id: str, T: int,
                 masks_by_clip=None):
        self.rows, self.cache, self.lanes = rows, cache, lanes
        self.source_id, self.T = source_id, T
        # P26: a lane lives in one camera's image plane, so each window must be
        # pooled through its OWN camera's masks. None means a single-camera
        # corpus, where the model's construction-time masks are already right.
        self.masks_by_clip = masks_by_clip

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index):
        import torch

        row = self.rows[index]
        # fp16 out of the cache and fp16 through the collate. The widening to
        # fp32 happens on the device, after the transfer — see `move` (P35).
        cnn, vit = self.cache.read_window(
            self.source_id, row["clip_id"], int(row["start_index"]), self.T,
            dtype=torch.float16,
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
        masks = (None if self.masks_by_clip is None
                 else self.masks_by_clip[row["clip_id"]])
        return cnn, vit, labels, masks


def batches(dataset, size: int, *, shuffle: bool, generator=None):
    import torch

    order = (
        torch.randperm(len(dataset), generator=generator).tolist()
        if shuffle else list(range(len(dataset)))
    )
    for start in range(0, len(order), size):
        chunk = [dataset[i] for i in order[start:start + size]]
        cnn = torch.stack([c for c, _, _, _ in chunk]) if chunk[0][0] is not None else None
        vit = torch.stack([v for _, v, _, _ in chunk]) if chunk[0][1] is not None else None
        masks = (torch.stack([m for _, _, _, m in chunk])
                 if chunk[0][3] is not None else None)
        yield cnn, vit, torch.stack([y for _, _, y, _ in chunk]), masks


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


def guard_results(out: Path, epochs: int, *, force: bool) -> None:
    """Refuse to overwrite results from a longer run than the one about to start.

    The check is `epochs_run`, not a timestamp, because the failure it prevents
    is specifically a short verification run aimed at the default path. A
    longer or equal run is a legitimate replacement and passes.
    """
    if force or not out.is_file():
        return
    try:
        with out.open(newline="", encoding="utf-8") as handle:
            recorded = [int(r["epochs_run"]) for r in csv.DictReader(handle)
                        if r.get("epochs_run", "").strip().isdigit()]
    except (OSError, ValueError, KeyError):
        return                                  # unreadable is not this guard's job
    if recorded and max(recorded) > epochs:
        raise SystemExit(
            f"{out} holds a run of {max(recorded)} epochs and this one is "
            f"{epochs}. Raw result CSVs are graded deliverables (NFR-09/10), "
            f"so a short check will not overwrite a longer run. Send it "
            f"somewhere else with --out, or pass --force if replacing it is "
            f"what you mean."
        )


def feed(model, cnn, vit, masks=None):
    """Pass only the branches this config enables.

    `MFSTNet._check_inputs` REFUSES features for a disabled branch rather than
    ignoring them, because silently ignoring them would make the ablation table
    describe a model that was not run. Config A has no ViT, config B no CNN.
    """
    return model(
        cnn if model.cfg.fusion.use_cnn else None,
        vit if model.cfg.fusion.use_vit else None,
        lane_masks=masks,
    )


def evaluate_split(model, dataset, size: int, lanes, device: str = "cpu"):
    """Predictions flattened across lanes — every lane is a labelled example."""
    import torch

    from mfstnet.metrics import evaluate

    model.eval()
    true, pred, last = [], [], None
    with torch.no_grad():
        for cnn, vit, y, masks in batches(dataset, size, shuffle=False):
            cnn, vit, masks = move((cnn, vit, masks), device, cast=torch.float32)
            out = feed(model, cnn, vit, masks)
            last = out
            true.extend(y.reshape(-1).tolist())      # labels stay on the CPU
            pred.extend(out.logits.reshape(-1, len(CLASSES)).argmax(-1).tolist())
    return evaluate(true, pred, CLASSES), last


def train_one(name, config, *, train_set, val_set, test_set, lanes, spec,
              epochs: int, seed: int, device: str = "cpu"):
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
    # The construction-time masks are a registered buffer, so `.to()` carries
    # them. Per-sample masks arrive with the batch and are moved there.
    model = MFSTNet(config, masks).to(device)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=t["lr"], weight_decay=t["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)

    labels = [y for _, _, ys, _ in (train_set[i] for i in range(len(train_set)))
              for y in ys.tolist()]
    weights, counts = class_weights(labels, len(CLASSES))
    criterion = torch.nn.CrossEntropyLoss(weight=weights.to(device))

    generator = torch.Generator().manual_seed(seed)
    best, best_state, stale = float("inf"), None, 0
    started = time.perf_counter()

    for epoch in range(epochs):
        model.train()
        total = 0.0
        for cnn, vit, y, masks in batches(train_set, t["batch_size"], shuffle=True,
                                          generator=generator):
            cnn, vit, masks, y = move((cnn, vit, masks, y), device,
                                      cast=torch.float32)
            out = feed(model, cnn, vit, masks)
            loss = criterion(out.logits.reshape(-1, len(CLASSES)), y.reshape(-1))
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total += float(loss)
        scheduler.step()

        val_report, _ = evaluate_split(model, val_set, t["batch_size"], lanes,
                                       device)
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
    report, last = evaluate_split(model, test_set, t["batch_size"], lanes,
                                  device)

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
        # ADR-003 requires every latency figure to state its measurement host.
        # The same applies to a trained metric: seeded runs are reproducible on
        # one device and NOT bitwise equal across devices — the same config and
        # seed gave gate_mean 0.53895 on CPU and 0.54268 on CUDA. A results row
        # that does not say which produced it cannot be compared with another.
        "device": device,
        # Beside the number it qualifies. A zero-support class costs a third of
        # macro F1 and nothing else in the row says so, which is how a column
        # of identical scores reads as a comparison instead of an artifact of
        # the split (P31). This row duplicates `EvaluationReport.as_row` rather
        # than calling it, so the field has to be added in both places.
        "warnings": " | ".join(report.warnings),
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
    parser.add_argument(
        "--device", default="auto",
        help="auto|cpu|cuda. 'auto' uses the GPU when torch can see one; a "
             "CUDA build of torch is necessary but not sufficient, because "
             "nothing moved the model or the batches before P32")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite results recorded from a longer run than this one")
    args = parser.parse_args(argv)

    import yaml

    from mfstnet.cache import FeatureCache
    from mfstnet.metrics import format_confusion_matrix
    from mfstnet.model import ablation_config, iter_ablation_configs
    from mfstnet.temporal import Polygon

    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml").read_text(encoding="utf-8"))
    training = spec["training"]
    epochs = args.epochs or training["epochs"]

    # NFR-09/10 make the raw result CSVs graded deliverables, and `--out`
    # defaults to the real one — so a two-epoch plumbing check aimed at the
    # default silently destroys a finished ablation. Refuse when the file on
    # disk came from a longer run than this one.
    guard_results(args.out, epochs, force=args.force)

    device = resolve_device(args.device)

    rows_in, manifest = load_corpus(args.corpus)
    auto = manifest.get("auto_labelled", True)
    lane_names = manifest["lanes"]
    T = manifest["T"]

    print(f"  corpus {args.corpus}: {len(rows_in)} sequences, "
          f"{len(lane_names)} lane(s), T={T}")
    print(f"  device {device}" + ("" if device != "cpu" else
          "  (torch sees no GPU; check scripts/check_env.py)"))
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

    # P26. One set of centres describes ONE camera, so a corpus spanning
    # cameras needs a mask set per camera. Pooling every camera through the
    # first one's lanes does not fail loudly — the shapes agree and the loss
    # still falls — it just measures the wrong region for every camera but one.
    per_clip = manifest.get("lane_centres_by_clip") or {}
    masks_by_clip = None
    if per_clip:
        from mfstnet.corpus.lanes import LaneCentres
        from mfstnet.temporal import lane_masks_from_centres

        grid = spec.get("grid", 7)
        masks_by_clip = {
            clip_id: lane_masks_from_centres(
                LaneCentres(
                    names=tuple(e["name"] for e in entry["lanes"]),
                    centres=tuple(tuple(e["centre"]) for e in entry["lanes"]),
                    max_radius=float(entry.get("max_radius", 0.25)),
                ),
                grid,
            )
            for clip_id, entry in per_clip.items()
        }
        widths = {int(m.shape[0]) for m in masks_by_clip.values()}
        if len(widths) > 1:
            raise SystemExit(
                f"the corpus mixes cameras with {sorted(widths)} lanes. The "
                f"per-lane head is one fixed width, so a corpus cannot span "
                f"lane counts — rebuild with the same count on every camera."
            )
        missing = {r["clip_id"] for r in rows_in} - set(masks_by_clip)
        if missing:
            raise SystemExit(
                f"{len(missing)} clip(s) have sequences but no lane geometry, "
                f"e.g. {sorted(missing)[0][:50]}. Every window must be pooled "
                f"through its own camera's lanes (P26)."
            )
        print(f"  per-camera ROI geometry for {len(masks_by_clip)} camera(s)")

    split = {
        name: Windows([r for r in rows_in if r["split"] == name],
                      cache, lane_names, args.source_id, T,
                      masks_by_clip=masks_by_clip)
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
            name, config, device=device,
            train_set=split["train"], val_set=split["val"],
            test_set=split["test"], lanes=lanes, spec=spec,
            epochs=epochs, seed=args.seed,
        )
        row["labels"] = "auto" if auto else "human_verified"
        row["corpus"] = str(args.corpus)
        rows.append(row)
        print(f"    macro-F1 {row['macro_f1']}  QWK {row['qwk']}  "
              f"gate std {row['gate_std'] or '—'}")
        for warning in report.warnings:
            print(f"    WARNING  {warning}")
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
