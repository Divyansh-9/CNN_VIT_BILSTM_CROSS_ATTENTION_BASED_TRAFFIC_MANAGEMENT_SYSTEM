"""The benchmark result files must survive a second regime being run.

`benchmark.py` wrote `benchmark_runs.csv` in `"w"` mode under a fixed name. A
routine `--regime light` after `--regime saturated` therefore deleted 90
committed rows and printed nothing about it. Those rows are a graded
reproducibility artifact (NFR-09) and are expensive to regenerate.

The tests below pin the behaviour that replaces it: re-running a regime
supersedes that regime and only that regime.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark import merge_by_regime


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row(method: str, seed: int, regime: str, wait: float) -> dict:
    return {"method": method, "seed": seed, "regime": regime, "mean_wait_s": wait}


def test_new_file_is_written_as_is(tmp_path):
    path = tmp_path / "runs.csv"
    merge_by_regime(path, [row("fixed", 0, "saturated", 31.0)], "saturated")
    assert len(read(path)) == 1


def test_second_regime_does_not_destroy_the_first(tmp_path):
    """The exact scenario that would have wiped the committed benchmark."""
    path = tmp_path / "runs.csv"
    merge_by_regime(path, [row("fixed", s, "saturated", 31.0) for s in range(30)],
                    "saturated")
    merge_by_regime(path, [row("fixed", s, "light", 10.0) for s in range(30)],
                    "light")

    rows = read(path)
    assert len(rows) == 60
    assert sum(1 for r in rows if r["regime"] == "saturated") == 30
    assert sum(1 for r in rows if r["regime"] == "light") == 30


def test_rerunning_a_regime_replaces_it_rather_than_duplicating(tmp_path):
    """A re-run supersedes. Two copies of one experiment in one file is worse
    than either copy alone, because a reader cannot tell which is current."""
    path = tmp_path / "runs.csv"
    merge_by_regime(path, [row("fixed", 0, "saturated", 31.0)], "saturated")
    merge_by_regime(path, [row("fixed", 0, "light", 10.0)], "light")
    merge_by_regime(path, [row("fixed", 0, "saturated", 29.5)], "saturated")

    rows = read(path)
    assert len(rows) == 2
    saturated = [r for r in rows if r["regime"] == "saturated"]
    assert len(saturated) == 1
    assert saturated[0]["mean_wait_s"] == "29.5", "stale row survived the re-run"


def test_a_file_without_regime_is_refused_not_merged(tmp_path):
    """Silently merging pre-regime rows produces a table nobody can interpret,
    and the rows in it would be uncitable. Fail loudly instead."""
    path = tmp_path / "runs.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["method", "seed", "mean_wait_s"])
        writer.writeheader()
        writer.writerow({"method": "fixed", "seed": 0, "mean_wait_s": 31.0})

    with pytest.raises(SystemExit, match="no .regime."):
        merge_by_regime(path, [row("fixed", 0, "light", 10.0)], "light")


def test_columns_added_later_do_not_drop_earlier_rows(tmp_path):
    """Webster contributes `clamp_rate`; the classical controllers do not. A
    union of fields with a blank fill keeps both, where a strict writer would
    raise or silently truncate."""
    path = tmp_path / "runs.csv"
    merge_by_regime(path, [row("fixed", 0, "saturated", 31.0)], "saturated")

    webster = row("webster", 0, "light", 12.0)
    webster["clamp_rate"] = 0.12
    merge_by_regime(path, [webster], "light")

    rows = read(path)
    assert len(rows) == 2
    assert {r["method"] for r in rows} == {"fixed", "webster"}
    older = next(r for r in rows if r["method"] == "fixed")
    assert older["clamp_rate"] == "", "missing column must blank-fill, not drop"
    assert older["mean_wait_s"] == "31.0", "earlier row lost its measurement"


def test_shared_helper_is_what_benchmark_uses():
    """The hazard was never specific to benchmark.py — webster_sweep.py and
    screen_action_space.py have the same fixed-filename shape. One
    implementation means fixing it once."""
    from experiments.results_io import merge_by_key
    from scripts import benchmark, screen_action_space, webster_sweep

    assert benchmark.merge_by_regime.__module__ == "scripts.benchmark"
    for module in (webster_sweep, screen_action_space):
        assert module.merge_by_key is merge_by_key


def test_merging_on_a_non_regime_key(tmp_path):
    """`key` is a parameter because not every experiment is split by regime.
    A screen split by action space needs the same protection."""
    from experiments.results_io import merge_by_key

    path = tmp_path / "screen.csv"
    merge_by_key(path, [{"action_space": "phase_duration", "mean_wait_s": 25.9}],
                 "phase_duration", key="action_space")
    merge_by_key(path, [{"action_space": "keep_or_switch", "mean_wait_s": 12.7}],
                 "keep_or_switch", key="action_space")

    rows = read(path)
    assert len(rows) == 2
    assert {r["action_space"] for r in rows} == {"phase_duration", "keep_or_switch"}


def test_writing_no_rows_is_refused(tmp_path):
    """An experiment that produced nothing must not blank an existing file.
    Truncating on empty is how a crashed run destroys the run before it."""
    from experiments.results_io import merge_by_key

    path = tmp_path / "runs.csv"
    merge_by_key(path, [row("fixed", 0, "saturated", 31.0)], "saturated")
    with pytest.raises(ValueError, match="no rows"):
        merge_by_key(path, [], "light")
    assert len(read(path)) == 1, "existing rows lost on an empty write"
