"""Raw result CSVs are graded deliverables (NFR-09/10), and `--out` defaults to
the real one — so a short plumbing run aimed at the default overwrites a
finished ablation with two epochs of noise. It happened during P26.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.train_mfstnet import guard_results


def write_results(path: Path, epochs: list[int]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["config", "epochs_run", "macro_f1"])
        writer.writeheader()
        for i, e in enumerate(epochs):
            writer.writerow({"config": f"C{i}", "epochs_run": e, "macro_f1": 0.5})
    return path


def test_a_short_run_will_not_overwrite_a_long_one(tmp_path):
    out = write_results(tmp_path / "ablation.csv", [100, 100])
    with pytest.raises(SystemExit, match="graded deliverables"):
        guard_results(out, 2, force=False)


def test_an_equal_run_is_allowed(tmp_path):
    """Re-running the same ablation is the normal way to replace it."""
    out = write_results(tmp_path / "ablation.csv", [100])
    guard_results(out, 100, force=False)


def test_a_longer_run_is_allowed(tmp_path):
    out = write_results(tmp_path / "ablation.csv", [50])
    guard_results(out, 100, force=False)


def test_force_overrides(tmp_path):
    out = write_results(tmp_path / "ablation.csv", [100])
    guard_results(out, 2, force=True)


def test_a_missing_file_is_fine(tmp_path):
    guard_results(tmp_path / "nothing.csv", 2, force=False)


def test_the_longest_recorded_run_is_what_counts(tmp_path):
    """A mixed file still protects its longest run."""
    out = write_results(tmp_path / "ablation.csv", [2, 100, 2])
    with pytest.raises(SystemExit, match="100 epochs"):
        guard_results(out, 5, force=False)


def test_an_unreadable_file_does_not_block_the_run(tmp_path):
    """This guard protects results; it does not become a new way to fail."""
    out = tmp_path / "ablation.csv"
    out.write_text("not,a,valid\ncsv for this", encoding="utf-8")
    guard_results(out, 2, force=False)


def test_a_file_without_the_column_does_not_block(tmp_path):
    out = tmp_path / "ablation.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["config", "macro_f1"])
        writer.writeheader()
        writer.writerow({"config": "A", "macro_f1": 0.9})
    guard_results(out, 2, force=False)
