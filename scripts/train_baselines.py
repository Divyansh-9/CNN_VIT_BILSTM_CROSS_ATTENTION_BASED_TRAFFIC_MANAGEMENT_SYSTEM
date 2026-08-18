"""Count-sequence baselines for MFSTNet (PRD §14.3, P13, A32).

    python scripts/train_baselines.py --corpus data/corpus

§14.3 names baselines that consume **count sequences** rather than pixels:
`Naive` last-value, `LSTM`, `GRU`, and — added by P13 from Saxena et al.
(IEEE TITS 26(6) 2025, which reaches 92.5% on a three-class congestion task) —
gradient-boosted trees.

**These are not weak baselines and must not be treated as such.** A32: congestion
labels are a deterministic function of the vehicle count, so a count-sequence
model observes **the exact variable the label is computed from**, while MFSTNet
observes pixels and has to recover the count before extrapolating. On
auto-labelled data these should win by construction.

That is why the headline comparison belongs on the human-verified split, where a
human judging congestion is not applying a count threshold — they see queue
length, stopped versus moving, spatial bunching. Present in pixels, absent from
a count.

**Naive matters more than it looks.** Over a 60 s horizon on a signal this
autocorrelated, "the same as now" is strong. A project that omits it can report a
win it never earned, and running it costs nothing.

**Run these BEFORE MFSTNet trains.** If last-value already scores well on
human-verified labels, that number reframes the contribution — and Week 3 is a
far better time to learn it than Week 14.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CLASSES = ("LOW", "MEDIUM", "HIGH")
RESULTS = Path("experiments/results/baselines_mfstnet.csv")


def load(corpus: Path):
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    with (corpus / "sequences.csv").open(encoding="utf-8") as handle:
        sequences = list(csv.DictReader(handle))
    with (corpus / "counts.csv").open(encoding="utf-8") as handle:
        counts = list(csv.DictReader(handle))
    series: dict[str, dict[str, list[int]]] = {}
    for row in counts:
        clip = series.setdefault(row["clip_id"], {})
        for lane in manifest["lanes"]:
            clip.setdefault(lane, []).append(int(row["count_" + lane]))
    return sequences, series, manifest


def windows(sequences, series, manifest):
    """(count window, label) per lane. One example per lane per sequence."""
    timesteps, lanes = manifest["T"], manifest["lanes"]
    features, targets, splits = [], [], []
    for row in sequences:
        start = int(row["start_index"])
        for lane in lanes:
            counts = series[row["clip_id"]][lane]
            if start + timesteps > len(counts):
                continue
            features.append([float(c) for c in counts[start:start + timesteps]])
            targets.append(CLASSES.index(row["label_" + lane]))
            splits.append(row["split"])
    return features, targets, splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    import torch

    from mfstnet.corpus.labels import label_from_count
    from mfstnet.metrics import evaluate
    from scripts.seed import set_seed

    sequences, series, manifest = load(args.corpus)
    features, targets, splits = windows(sequences, series, manifest)
    auto = manifest.get("auto_labelled", True)

    index = {name: [i for i, s in enumerate(splits) if s == name]
             for name in ("train", "val", "test")}
    print("  {} examples over {} lane(s), T={}".format(
        len(features), len(manifest["lanes"]), manifest["T"]))
    print("  labels: {}{}".format(
        "AUTO-LABELLED" if auto else "HUMAN-VERIFIED",
        "  (A32 - NOT the headline split)" if auto else ""))
    for name, rows in index.items():
        print("    {:<6} {:>5}".format(name, len(rows)))
    if not index["test"]:
        raise SystemExit("empty test split — refusing to report")

    out_rows = []

    def record(name, predictions, note=""):
        report = evaluate([targets[i] for i in index["test"]], predictions, CLASSES)
        row = {
            "model": name, "seed": args.seed, "n": report.n,
            "accuracy": round(report.accuracy, 4),
            "macro_f1": round(report.macro_f1, 4),
            "weighted_f1": round(report.weighted_f1, 4),
            "ordinal_mae": round(report.ordinal_mae, 4),
            "off_by_two_rate": round(report.off_by_two_rate, 4),
            "qwk": round(report.qwk, 4),
            "labels": "auto" if auto else "human_verified",
            "note": note,
        }
        for label, metrics in zip(CLASSES, report.per_class):
            row["f1_" + label.lower()] = round(metrics.f1, 4)
            row["support_" + label.lower()] = metrics.support
        out_rows.append(row)
        print("  {:<22} macro-F1 {:.4f}  QWK {:>7.4f}  acc {:.4f}".format(
            name, row["macro_f1"], row["qwk"], row["accuracy"]))

    # Naive: no training, no seed, and no excuse for omitting it. It applies the
    # SAME §14.1 thresholds to the last observed count, so it is the honest
    # floor — whatever a model achieves must beat assuming nothing changes.
    record("naive_last_value",
           [label_from_count(int(round(features[i][-1]))).value
            for i in index["test"]],
           "PRD 14.3 lower bound")

    try:
        import xgboost

        # The NATIVE API, not XGBClassifier. The sklearn wrapper imports
        # scikit-learn at construction, so on an environment where sklearn is
        # missing it raises ImportError from INSIDE the try — and this baseline
        # silently reports SKIPPED while looking like xgboost was absent. That
        # actually happened. The native API depends on nothing but xgboost, so
        # the baseline runs wherever xgboost imports.
        train = xgboost.DMatrix(
            [features[i] for i in index["train"]],
            label=[targets[i] for i in index["train"]])
        test = xgboost.DMatrix([features[i] for i in index["test"]])
        booster = xgboost.train(
            {"objective": "multi:softmax", "num_class": len(CLASSES),
             "max_depth": 4, "eta": 0.1, "seed": args.seed, "verbosity": 0},
            train, num_boost_round=200)
        record("xgboost_counts", [int(v) for v in booster.predict(test)],
               "P13, after Saxena et al. TITS 2025")
    except ImportError:
        print("  xgboost_counts         SKIPPED - pip install xgboost")

    for kind in ("lstm", "gru"):
        set_seed(args.seed)
        cell = (torch.nn.LSTM if kind == "lstm" else torch.nn.GRU)(
            input_size=1, hidden_size=64, num_layers=2, batch_first=True)
        head = torch.nn.Linear(64, len(CLASSES))
        optimiser = torch.optim.AdamW(
            list(cell.parameters()) + list(head.parameters()), lr=1e-3)

        counts = [sum(1 for i in index["train"] if targets[i] == c)
                  for c in range(len(CLASSES))]
        total = sum(counts)
        weights = torch.tensor(
            [(total / (len(CLASSES) * c)) if c else 0.0 for c in counts],
            dtype=torch.float32)
        criterion = torch.nn.CrossEntropyLoss(weight=weights)

        train_x = torch.tensor([features[i] for i in index["train"]]).unsqueeze(-1)
        train_y = torch.tensor([targets[i] for i in index["train"]])
        for _ in range(args.epochs):
            output, _ = cell(train_x)
            loss = criterion(head(output[:, -1]), train_y)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()

        with torch.no_grad():
            test_x = torch.tensor([features[i] for i in index["test"]]).unsqueeze(-1)
            output, _ = cell(test_x)
            record(kind + "_counts", head(output[:, -1]).argmax(-1).tolist(),
                   "PRD 14.3")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    print("\n  wrote " + str(args.out))
    if auto:
        print("  A32: these models observe the variable the label is computed")
        print("  from. On auto-labelled data they should win BY CONSTRUCTION,")
        print("  so this table cannot be the headline comparison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
