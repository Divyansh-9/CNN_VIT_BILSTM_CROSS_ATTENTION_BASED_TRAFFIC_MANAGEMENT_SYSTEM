"""Tests for the BMD-45 converter and its download gate (S13/S14, P14).

The gate exists because of a specific, expensive failure: an 8,000-image fetch
lost 4,996 downloads to throttling in 153 seconds, printed a warning, and let a
2.6-hour training run proceed on the remainder. Nothing complained until the
metrics step refused to report a support of zero.

    python -m pytest tests/test_bmd45_prep.py -q
"""

from __future__ import annotations

import pytest

yaml = pytest.importorskip("yaml")

from scripts.prepare_bmd45 import fetch_images, load_bmd_mapping, to_yolo  # noqa: E402


def test_coco_topleft_xywh_becomes_yolo_centre_normalised():
    """COCO stores absolute top-left xywh; YOLO wants normalised centre cxcywh.

    Getting this wrong produces plausible numbers and a broken dataset — which
    is why the converted labels were also rendered and looked at.
    """
    spec = {"index": {"car": 0}, "mapping": {"Sedan": "car"},
            "declared": {"Sedan"}, "targets": ["car"]}
    boxes = [{"category_id": 1, "bbox": [100.0, 200.0, 50.0, 40.0]}]

    lines, counts = to_yolo(boxes, 1000.0, 1000.0, spec, {1: "Sedan"})

    parts = lines[0].split()
    assert parts[0] == "0"
    assert float(parts[1]) == pytest.approx(0.125)   # (100 + 150) / 2 / 1000
    assert float(parts[2]) == pytest.approx(0.220)   # (200 + 240) / 2 / 1000
    assert float(parts[3]) == pytest.approx(0.050)
    assert float(parts[4]) == pytest.approx(0.040)
    assert counts["car"] == 1


def test_an_undeclared_category_is_surfaced_not_silently_dropped():
    """A category absent from `bmd45:` is a decision nobody has made yet. Silence
    is how a third of a dataset disappears without anyone noticing."""
    spec = {"index": {"car": 0}, "mapping": {"Sedan": "car"},
            "declared": {"Sedan"}, "targets": ["car"]}
    boxes = [{"category_id": 9, "bbox": [10.0, 10.0, 5.0, 5.0]}]

    lines, counts = to_yolo(boxes, 100.0, 100.0, spec, {9: "Hovercraft"})

    assert lines == []
    assert counts["UNDECLARED:Hovercraft"] == 1


def test_a_box_clipped_to_nothing_is_dropped_not_emitted_as_zero_area():
    spec = {"index": {"car": 0}, "mapping": {"Sedan": "car"},
            "declared": {"Sedan"}, "targets": ["car"]}
    boxes = [{"category_id": 1, "bbox": [99.7, 50.0, 40.0, 40.0]}]   # off the edge

    lines, _ = to_yolo(boxes, 100.0, 100.0, spec, {1: "Sedan"})
    assert lines == []


def test_a_high_failure_rate_aborts_rather_than_training_on_a_smaller_dataset(tmp_path):
    """THE regression test. Every fetch here fails, and the run must stop.

    Losing a couple of images is attrition. Losing half the dataset is a
    different dataset, and discovering that after a 2.6-hour training run is
    two and a half hours too late.
    """
    directory = tmp_path / "images" / "train"
    directory.mkdir(parents=True)
    # Unresolvable host, so every attempt fails without touching the network.
    pending = [(f"nonexistent-{i}.png", str(i), directory) for i in range(10)]

    with pytest.raises(SystemExit, match="ABORTING"):
        fetch_images(pending, long_edge=0, workers=2,
                     max_failure_rate=0.02, attempts=1)


def test_the_abort_message_names_the_fix(tmp_path):
    """An abort that does not say what to do next just moves the confusion."""
    directory = tmp_path / "images" / "train"
    directory.mkdir(parents=True)
    pending = [(f"nonexistent-{i}.png", str(i), directory) for i in range(4)]

    with pytest.raises(SystemExit) as caught:
        fetch_images(pending, long_edge=0, workers=2,
                     max_failure_rate=0.0, attempts=1)
    message = str(caught.value)
    assert "--workers" in message, "the remedy must be in the message"
    assert "resumes" in message, "that completed images are kept must be stated"


def test_tolerable_attrition_does_not_abort(tmp_path):
    """The gate must not be so tight that one flaky image kills an hour of work."""
    directory = tmp_path / "images" / "train"
    directory.mkdir(parents=True)
    for index in range(99):                       # pretend these already arrived
        (directory / f"{index}.jpg").write_bytes(b"x")
    pending = [(f"{i}.png", str(i), directory) for i in range(99)]
    pending.append(("nonexistent.png", "bad", directory))

    failures = fetch_images(pending, long_edge=0, workers=2,
                            max_failure_rate=0.02, attempts=1)
    assert len(failures) == 1


def test_the_mapping_comes_from_the_yaml_not_the_script():
    """DATASETS §6. A literal in the converter that duplicates the authority
    file is a defect, so the loader must be reading the real thing."""
    spec = load_bmd_mapping()
    assert spec["mapping"]["Three-wheeler"] == "auto_rickshaw"
    assert spec["seed"] == 42
