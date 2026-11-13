"""P100 — build the two hour-held-out training corpora, and stop if a check fails.

    python scripts/p100_corpus.py

Implements the fold split of
`experiments/results/bellevue_pilot/PREREGISTRATION_P100.md` over the P99
windows (`data/corpus_p99`, every window already wholly inside one 10-minute
block). Writes `data/corpus_p100_{A,B}_trainval`: a fold's training and
validation windows, from its training hours only. **No window of a test hour
is in either.** The test windows are read later, only by `p100_eval.py`, from
`data/corpus_p99`.

Stops before writing unless the support of every fold and split equals the
pre-registered table exactly and no test hour reaches a training corpus.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

SOURCE = Path("data/corpus_p99")
LANES = ("lane_0", "lane_1", "lane_2")
CLASSES = ("LOW", "MEDIUM", "HIGH")
FOLDS = {"A": 1, "B": 0}                 # fold -> parity of the TEST hours
EXPECTED = {
    ("A", "train"): (191, 1044, 340), ("A", "val"): (22, 212, 81), ("A", "test"): (62, 1123, 396),
    ("B", "train"): (57, 919, 335), ("B", "val"): (5, 204, 61), ("B", "test"): (213, 1256, 421),
}


def load():
    with (SOURCE / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    return rows, manifest


def assign(rows):
    """{fold: {split: [rows]}} by the pre-registered rule."""
    hours = sorted({r["hour"] for r in rows})
    out = {}
    for fold, parity in FOLDS.items():
        test_hours = {h for i, h in enumerate(hours) if i % 2 == parity}
        parts = {"train": [], "val": [], "test": []}
        for r in rows:
            i = hours.index(r["hour"])
            block = int(r["block"].split("#")[1])
            split = ("test" if r["hour"] in test_hours
                     else "val" if block == (i + 1) % 6 else "train")
            parts[split].append({**r, "split": split})
        out[fold] = parts
    return out, hours


def main() -> int:
    rows, manifest = load()
    folds, hours = assign(rows)

    table = {(f, s): tuple(Counter(r[f"label_{l}"] for r in parts[s] for l in LANES)[c]
                           for c in CLASSES)
             for f, parts in folds.items() for s in parts}
    for key, expected in EXPECTED.items():
        print(f"  fold {key[0]} {key[1]:<5} LOW/MEDIUM/HIGH {table[key]}  pre-registered {expected}")
    if table != EXPECTED:
        raise SystemExit("support differs from PREREGISTRATION_P100.md — STOP, nothing written")

    for fold, parts in folds.items():
        test_hours = {r["hour"] for r in parts["test"]}
        trainval = parts["train"] + parts["val"]
        leaked = {r["hour"] for r in trainval} & test_hours
        if leaked:
            raise SystemExit(f"fold {fold}: test hour(s) {sorted(leaked)} in training — STOP")
        root = Path(f"data/corpus_p100_{fold}_trainval")
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        fields = list(trainval[0])
        with (root / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(trainval)
        shutil.copyfile(SOURCE / "counts.csv", root / "counts.csv")
        (root / "manifest.json").write_text(json.dumps({
            **manifest, "fold": fold, "folds_total": 2, "split_mode": "p100_hours",
            "split_protocol": "PREREGISTRATION_P100.md: two folds interleaved by hour; "
                              "validation is block (i+1)%6 of each training hour",
            "test_hours": sorted(test_hours),
            "support": {s: dict(zip(CLASSES, table[(fold, s)])) for s in ("train", "val", "test")},
            "contents": "training hours only; train and val; no window of a test hour",
        }, indent=2), encoding="utf-8")
        print(f"  fold {fold}: wrote {root} ({len(trainval)} windows; test hours "
              f"{', '.join(h[5:13] for h in sorted(test_hours))} held out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
