"""The S61 selection rule reads validation only, and applies the rule as written."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import select_checkpoint as S  # noqa: E402

CAMERAS = {"cameras": {
    "m6": {"traffic_type": "structured"},
    "dhaka_a": {"traffic_type": "mixed"},
    "dhaka_b": {"traffic_type": "mixed"},
    "pov": {"traffic_type": "mixed"},
}}
FOLDS = [  # (test, val, test windows)
    ("dhaka_a", "m6", 35), ("m6", "pov", 63),
    ("pov", "dhaka_b", 11), ("dhaka_b", "dhaka_a", 34),
]


def build(tmp: Path, runs: list[tuple]) -> dict:
    results, views, ckpt = tmp / "results", tmp / "views", tmp / "ckpt"
    for d in (results, views, ckpt):
        d.mkdir()
    for i, (test, val, n) in enumerate(FOLDS):
        fold = views / f"fold{i}"
        fold.mkdir()
        (fold / "manifest.json").write_text(json.dumps(
            {"fold": i, "fold_test_camera": test, "fold_val_camera": val}))
        with (fold / "sequences.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["clip_id", "split"])
            writer.writerows([[test, "test"]] * n + [[val, "val"]])
    for fold, seed, config, val_f1, test_f1 in runs:
        with (results / f"fold{fold}_seed{seed}_{config}.csv").open(
                "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "config", "seed", "fold", "val_macro_f1", "macro_f1"])
            writer.writeheader()
            writer.writerow({"config": config, "seed": seed, "fold": fold,
                             "val_macro_f1": val_f1, "macro_f1": test_f1})
        (ckpt / f"mfstnet_{config}_seed{seed}_fold{fold}.pt").write_bytes(b"x")
    cameras = tmp / "cameras.json"
    cameras.write_text(json.dumps(CAMERAS))
    S.main(["--results", str(results), "--views", str(views),
            "--checkpoints", str(ckpt), "--cameras", str(cameras)])
    return json.loads((results / "selection.json").read_text())


def test_selection_ignores_the_test_score(tmp_path):
    """Seed 1 has the best TEST score by far and the worse validation score.
    The rule must pick seed 42."""
    record = build(tmp_path, [
        (3, 42, "G", 0.60, 0.10), (3, 1, "G", 0.50, 0.99),
        (0, 42, "G", 0.40, 0.40),
    ])
    assert record["selected"]["seed"] == 42
    assert "macro_f1" not in record["columns_read"]


def test_the_fold_is_the_largest_with_mixed_test_and_validation(tmp_path):
    """Fold 0 validates on the motorway and fold 1 tests on it; folds 2 and 3
    qualify, and 3 has the larger test set."""
    record = build(tmp_path, [(f, 42, "G", 0.5, 0.5) for f in range(4)])
    assert record["fold"] == 3


def test_config_is_chosen_on_mean_validation(tmp_path):
    record = build(tmp_path, [
        (3, 42, "G", 0.40, 0.9), (0, 42, "G", 0.40, 0.9),
        (3, 42, "H", 0.55, 0.1), (0, 42, "H", 0.55, 0.1),
    ])
    assert record["selected"]["config"] == "H"


def test_ties_go_to_the_seed_listed_first(tmp_path):
    record = build(tmp_path, [(3, 7, "G", 0.5, 0.5), (3, 42, "G", 0.5, 0.5)])
    assert record["selected"]["seed"] == 42


def test_a_run_without_a_validation_score_cannot_be_selected(tmp_path):
    with pytest.raises(SystemExit, match="val_macro_f1"):
        build(tmp_path, [(3, 42, "G", "", 0.5)])
