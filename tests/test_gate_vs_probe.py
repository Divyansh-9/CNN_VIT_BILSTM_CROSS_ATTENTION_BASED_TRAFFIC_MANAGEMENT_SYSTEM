"""ADR-022 Q1, tested before the data it will run on exists.

A pre-registration that leaves the analysis to be written afterwards has left
the analysis free. These pin the three things ADR-022 fixed in advance: the
aggregation ORDER, the power calculation, and the refusal to call an
underpowered null "equivalent".
"""

from __future__ import annotations

import csv

import pytest

from scripts.gate_vs_probe import MATERIAL, compare, minimum_detectable


def write_run(tmp_path, fold, seed, config, macro_f1):
    path = tmp_path / f"fold{fold}_seed{seed}_{config}.csv"
    row = {"config": config, "fold": fold, "seed": seed, "macro_f1": macro_f1}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def build(tmp_path, per_fold):
    """per_fold: {fold: (list of G scores, list of H scores)}."""
    for fold, (gs, hs) in per_fold.items():
        for seed, value in enumerate(gs):
            write_run(tmp_path, fold, seed, "G", value)
        for seed, value in enumerate(hs):
            write_run(tmp_path, fold, seed, "H", value)


# ------------------------------------------------------- aggregation order --


def test_seeds_are_averaged_within_a_fold_before_differencing(tmp_path):
    """Step 1 then step 2. Differencing per seed and pooling would give the
    same mean here but a different variance, which is the whole point."""
    build(tmp_path, {"0": ([0.40, 0.60], [0.30, 0.50])})
    result = compare(tmp_path, "G", "H")
    assert result["n_folds"] == 1
    assert result["mean_difference"] == pytest.approx(0.10, abs=1e-9)


def test_one_number_per_fold_reaches_the_fold_level_statistic(tmp_path):
    build(tmp_path, {"0": ([0.5, 0.5], [0.4, 0.4]),
                     "1": ([0.7, 0.7], [0.5, 0.5])})
    result = compare(tmp_path, "G", "H")
    assert result["n_folds"] == 2
    assert "0:+0.1000" in result["difference_per_fold"]
    assert "1:+0.2000" in result["difference_per_fold"]


def test_only_folds_holding_both_configs_are_compared(tmp_path):
    """A fold with G but no H is not a paired observation."""
    build(tmp_path, {"0": ([0.5], [0.4])})
    write_run(tmp_path, "1", 0, "G", 0.9)
    assert compare(tmp_path, "G", "H")["n_folds"] == 1


def test_no_shared_fold_refuses(tmp_path):
    write_run(tmp_path, "0", 0, "G", 0.5)
    write_run(tmp_path, "1", 0, "H", 0.5)
    with pytest.raises(SystemExit):
        compare(tmp_path, "G", "H")


def test_prediction_files_are_not_read_as_runs(tmp_path):
    """P59's per-window files match `fold*.csv` and carry a `config` column."""
    build(tmp_path, {"0": ([0.5], [0.4]), "1": ([0.5], [0.4])})
    noise = tmp_path / "fold0_seed0_G_G.predictions.csv"
    with noise.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["config", "fold", "macro_f1"])
        writer.writeheader()
        for _ in range(140):
            writer.writerow({"config": "G", "fold": "0", "macro_f1": 0.0})
    assert compare(tmp_path, "G", "H")["mean_difference"] == pytest.approx(0.1)


# ------------------------------------------------------------------ power --


def test_the_minimum_detectable_difference_matches_adr_022():
    """ADR-022 quotes 1.591 x sd at n=4 and 2.484 x sd at n=3."""
    assert minimum_detectable(1.0, 4) == pytest.approx(1.591, abs=1e-3)
    assert minimum_detectable(1.0, 3) == pytest.approx(2.484, abs=1e-3)


def test_fewer_folds_need_a_larger_difference():
    assert minimum_detectable(0.185, 3) > minimum_detectable(0.185, 4)


# ---------------------------------------------------------------- verdicts --


def test_a_null_result_is_reported_as_cannot_distinguish(tmp_path):
    """Never 'equivalent'. This design cannot support that in either
    direction."""
    build(tmp_path, {"0": ([0.50], [0.48]), "1": ([0.40], [0.55]),
                     "2": ([0.70], [0.60]), "3": ([0.30], [0.42])})
    result = compare(tmp_path, "G", "H")
    assert result["verdict"] == "CANNOT DISTINGUISH"
    assert result["material"] is False


def test_a_large_consistent_gap_is_material(tmp_path):
    build(tmp_path, {"0": ([0.80], [0.50]), "1": ([0.82], [0.51]),
                     "2": ([0.79], [0.49]), "3": ([0.81], [0.52])})
    result = compare(tmp_path, "G", "H")
    assert result["verdict"] == "MATERIAL"
    assert result["mean_difference"] >= MATERIAL


def test_a_tiny_but_consistent_gap_is_separated_and_not_material(tmp_path):
    """The case the threshold exists for: at this n, a significant result on a
    0.02 gap is a small-sample artifact before it is a finding."""
    build(tmp_path, {"0": ([0.500], [0.480]), "1": ([0.502], [0.482]),
                     "2": ([0.499], [0.479]), "3": ([0.501], [0.481])})
    result = compare(tmp_path, "G", "H")
    assert result["interval_excludes_zero"] is True
    assert result["verdict"] == "SEPARATED BUT NOT MATERIAL"


def test_the_threshold_is_the_one_adr_022_pre_registered():
    assert MATERIAL == 0.05
