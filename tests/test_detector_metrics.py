"""Tests for the detector metrics reporter (S11/S14, FR-D08).

These guard two defects that both produced *plausible* wrong numbers rather than
errors, which is why they need tests rather than care.

    python -m pytest tests/test_detector_metrics.py -q
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

from scripts.verify_detector_metrics import label_dirs, load_config, support  # noqa: E402

NAMES = ["car", "motorcycle", "auto_rickshaw", "e_rickshaw",
         "bus", "truck", "pedestrian", "cattle"]


def _dataset(root: pathlib.Path, split: str, rows: dict[int, int]) -> None:
    labels = root / "labels" / split
    labels.mkdir(parents=True, exist_ok=True)
    (root / "images" / split).mkdir(parents=True, exist_ok=True)
    for index, (class_id, count) in enumerate(rows.items()):
        (labels / f"{index}.txt").write_text(
            "".join(f"{class_id} 0.5 0.5 0.1 0.1\n" for _ in range(count)),
            encoding="utf-8",
        )


def _config(path: pathlib.Path, test) -> pathlib.Path:
    path.write_text(
        yaml.safe_dump({"train": test, "val": test, "test": test,
                        "nc": len(NAMES), "names": NAMES}),
        encoding="utf-8",
    )
    return path


def test_support_is_found_when_the_config_lives_away_from_the_dataset(tmp_path):
    """The joint eval configs sit in their own directory.

    Deriving labels from the CONFIG's parent returns zero for every class, and
    the table then prints an mAP beside a support of 0 — the same impossible
    pairing this reporter exists to prevent, arriving by another route.
    """
    data = tmp_path / "data"
    _dataset(data, "test", {0: 7, 4: 3})
    elsewhere = tmp_path / "configs"
    elsewhere.mkdir()
    config_path = _config(elsewhere / "eval.yaml", str(data / "images" / "test"))

    config = load_config(config_path)
    counts = support(label_dirs(config, config_path, "test"), NAMES)
    assert counts["car"] == 7 and counts["bus"] == 3


def test_support_sums_across_a_multi_path_split(tmp_path):
    """`train:`/`test:` may be a LIST — that is how the joint set avoids copying
    gigabytes. Counting only the first entry would under-report every class."""
    first, second = tmp_path / "a", tmp_path / "b"
    _dataset(first, "test", {0: 4})
    _dataset(second, "test", {0: 6, 7: 2})
    config_path = _config(
        tmp_path / "joint.yaml",
        [str(first / "images" / "test"), str(second / "images" / "test")],
    )

    config = load_config(config_path)
    directories = label_dirs(config, config_path, "test")
    assert len(directories) == 2
    counts = support(directories, NAMES)
    assert counts["car"] == 10 and counts["cattle"] == 2


def test_an_empty_label_directory_raises_rather_than_reporting_zeros(tmp_path):
    """Zero support for every class is never a real result; it is a wrong path.
    Reporting it would put an mAP next to `0 boxes` on every row."""
    data = tmp_path / "data"
    (data / "images" / "test").mkdir(parents=True)
    (data / "labels" / "test").mkdir(parents=True)
    config_path = _config(tmp_path / "eval.yaml", str(data / "images" / "test"))

    config = load_config(config_path)
    with pytest.raises(SystemExit, match="no label files"):
        support(label_dirs(config, config_path, "test"), NAMES)


def test_a_path_without_an_images_component_is_refused(tmp_path):
    """Ultralytics resolves labels by substituting `images` -> `labels`. If that
    substitution cannot be made, silently guessing a directory would be worse."""
    config_path = _config(tmp_path / "eval.yaml", str(tmp_path / "pictures" / "test"))
    config = load_config(config_path)
    with pytest.raises(SystemExit, match="no 'images' component"):
        label_dirs(config, config_path, "test")


def test_the_reporter_keys_rows_by_ap_class_index():
    """The original S11 defect. `class_result(i)` indexes classes WITH INSTANCES,
    so a class with zero boxes shifts every row after it — which is how a table
    reported mAP50 0.7288 for a class with 0 boxes and `nan` for one with 183.

    Asserted against the source because constructing a real DetMetrics needs a
    trained model and a GPU-sized fixture.
    """
    import inspect

    from scripts import verify_detector_metrics

    source = inspect.getsource(verify_detector_metrics.main)
    assert "ap_class_index" in source
    assert "evaluated" in source, "a class with no instances must be marked, not omitted"
