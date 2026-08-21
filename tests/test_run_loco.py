"""The fold aggregate must be generated from the fold CSVs, and say what it is.

`run_loco.py` is the script whose output gets quoted, so the two things that
matter are that the summary is computed from the per-fold files rather than
typed (NFR-09/10) and that it carries enough context to stop a fold mean being
read as if it were thirty seeds.
"""

from __future__ import annotations

import csv

import pytest

from scripts.run_loco import AGGREGATED, summarise


def write_fold(tmp_path, index, macro_f1, *, config="G", seed=42, **extra):
    path = tmp_path / f"fold{index}_seed{seed}.csv"
    row = {"config": config, "fold": index, "seed": seed, "macro_f1": macro_f1,
           "weighted_f1": macro_f1, "accuracy": macro_f1, "qwk": macro_f1,
           "ordinal_mae": 0.1, "off_by_two_rate": 0.0,
           "gate_mean": 0.5, "gate_std": 0.01}
    row.update(extra)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return path


def test_summary_averages_across_folds(tmp_path):
    files = [write_fold(tmp_path, i, v)
             for i, v in enumerate((0.40, 0.50, 0.60, 0.70))]
    summary = summarise(files, tmp_path / "summary.csv")
    assert len(summary) == 1
    assert summary[0]["n_folds"] == 4
    assert summary[0]["macro_f1_mean"] == pytest.approx(0.55, abs=1e-9)


def test_every_aggregated_field_gets_a_mean_and_an_interval(tmp_path):
    files = [write_fold(tmp_path, i, 0.5) for i in range(3)]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    for field in AGGREGATED:
        assert f"{field}_mean" in entry
        assert f"{field}_lo" in entry and f"{field}_hi" in entry


def test_the_interval_brackets_the_mean(tmp_path):
    files = [write_fold(tmp_path, i, v)
             for i, v in enumerate((0.30, 0.55, 0.62, 0.81))]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    assert entry["macro_f1_lo"] <= entry["macro_f1_mean"] <= entry["macro_f1_hi"]


def test_per_run_scores_survive_into_the_summary(tmp_path):
    """A mean of 0.61 over folds of 0.83 and 0.39 is not four folds of 0.61,
    and at n=4 the interval alone does not separate them."""
    files = [write_fold(tmp_path, i, v) for i, v in enumerate((0.83, 0.39))]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    assert "0/42:0.83" in entry["macro_f1_by_run"]
    assert "1/42:0.39" in entry["macro_f1_by_run"]


def test_seed_spread_is_measured_within_a_fold_not_across_folds(tmp_path):
    """P54. Config E moved 0.242 on one fold across three seeds while config B
    moved 0.039, and at seed 42 the two were identical to four decimals. Fold-to-
    fold movement is a different quantity and must not be folded into this one."""
    files = [write_fold(tmp_path, 0, 0.20, seed=1),
             write_fold(tmp_path, 0, 0.45, seed=2),
             write_fold(tmp_path, 1, 0.80, seed=1),
             write_fold(tmp_path, 1, 0.85, seed=2)]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    # (0.45-0.20) and (0.85-0.80), averaged -> 0.15. Not 0.65, the full range.
    assert entry["macro_f1_seed_spread"] == pytest.approx(0.15, abs=1e-9)
    assert entry["n_folds"] == 2 and entry["n_seeds"] == 2
    assert entry["n_runs"] == 4


def test_one_seed_per_fold_leaves_the_spread_blank(tmp_path):
    """Blank, never 0.0. A single seed has not measured a spread of zero — it
    has not measured one at all, and 0.0 would read as 'this config is stable'."""
    files = [write_fold(tmp_path, i, 0.5) for i in range(3)]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    assert entry["macro_f1_seed_spread"] == ""


def test_configs_are_kept_apart(tmp_path):
    files = [write_fold(tmp_path, 0, 0.5, config="A"),
             write_fold(tmp_path, 1, 0.9, config="H")]
    summary = summarise(files, tmp_path / "summary.csv")
    assert [e["config"] for e in summary] == ["A", "H"]
    assert all(e["n_folds"] == 1 for e in summary)


def test_a_blank_metric_does_not_become_zero(tmp_path):
    """`gate_std` is empty for configs with no gate. Averaging '' as 0 would
    report a gate that does not exist as a perfectly stable one."""
    files = [write_fold(tmp_path, i, 0.5, gate_std="") for i in range(3)]
    entry = summarise(files, tmp_path / "summary.csv")[0]
    assert entry["gate_std_mean"] == ""


def test_the_summary_file_is_written_and_reads_back(tmp_path):
    files = [write_fold(tmp_path, i, 0.5) for i in range(2)]
    out = tmp_path / "nested" / "summary.csv"
    summarise(files, out)
    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1 and rows[0]["config"] == "G"


def test_empty_input_refuses_rather_than_writing_an_empty_summary(tmp_path):
    path = tmp_path / "fold0.csv"
    path.write_text("config,fold,macro_f1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        summarise([path], tmp_path / "summary.csv")
