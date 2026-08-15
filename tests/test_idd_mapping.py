"""Tests for the IDD class mapping and converter (S08–S09, DATASETS §6).

Pure standard library plus pyyaml, so these run in the fast CI job. They guard
decisions rather than code: the `rider` convention, the drop-don't-merge rule,
and the class index order are all things that can be changed in one line and
would silently corrupt every count downstream.

    python -m pytest tests/test_idd_mapping.py -q
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

MAPPING_PATH = pathlib.Path("indiatrafficnet/class_mapping.yaml")


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8"))


def test_the_eight_prd_classes_are_present_and_ordered(spec):
    """PRD §12.2 / FR-D03. **Order is the YOLO class index**, so reordering this
    list silently relabels every annotation ever exported."""
    assert spec["target_classes"] == [
        "car", "motorcycle", "auto_rickshaw", "e_rickshaw",
        "bus", "truck", "pedestrian", "cattle",
    ]


def test_auto_rickshaw_and_cattle_have_idd_sources(spec):
    """The two India-specific classes IDD actually carries, and the reason it
    beats every foreign dataset assessed (DATASETS §4.4)."""
    assert spec["mapping"]["autorickshaw"] == "auto_rickshaw"
    assert spec["mapping"]["animal"] == "cattle"


def test_rider_is_dropped_and_the_reason_is_recorded(spec):
    """DATASETS §6.1. A motorcyclist is a `rider` ON a `motorcycle`; counting
    both inflates every count by roughly the two-wheeler share (~30% per PRD
    §12.2) and biases every congestion label the §8.6 pipeline derives.

    This is one line to change and catastrophic to change by accident.
    """
    assert "rider" in spec["mapping"], "the decision must be explicit, not absent"
    assert spec["mapping"]["rider"] is None


def test_unlike_classes_are_dropped_not_merged(spec):
    """Merging teaches the detector a category that does not exist in our label
    space. `vehicle fallback` holds carts, tractors and trailers — mapping it to
    `car` would be worse than dropping it."""
    for label in ("bicycle", "vehicle fallback", "traffic sign", "traffic light"):
        assert spec["mapping"][label] is None


def test_every_mapping_target_is_a_declared_class(spec):
    targets = set(spec["target_classes"])
    for source, target in spec["mapping"].items():
        assert target is None or target in targets, f"{source} -> unknown {target}"


def test_e_rickshaw_is_declared_absent_with_its_consequence(spec):
    """It has no IDD source. Recording that keeps a bootstrap-era miss a known,
    bounded error rather than a silent one — and it is why self-collection is
    still required for the detector, not only for the corpus."""
    assert "e_rickshaw" in spec["absent_from_idd"]
    assert spec["absent_from_idd"]["e_rickshaw"].strip()


def test_sampling_is_seeded_and_stratified(spec):
    """IDD is a car-mounted rig; deployment is an elevated fixed camera
    (DATASETS §2). Camera position is recorded per image, so stratifying costs
    nothing."""
    sampling = spec["sampling"]
    assert sampling["strategy"] == "stratified_by_camera_position"
    assert sampling["seed"] == 42
    assert sampling["weights"]["sideLeft"] > sampling["weights"]["frontNear"], (
        "side views are nearer the deployment geometry than forward dashcam"
    )


def test_the_sampling_weights_are_labelled_a_prior_not_a_measurement(spec):
    """S12 tests them. If the mAP gap turns out negligible the weights go to 1.0
    and the claim is withdrawn — so the note must survive edits."""
    assert "prior" in spec["sampling"]["note"].lower()


# --------------------------------------------------------------- converter --

def test_detection_split_is_70_15_15_not_the_mfstnet_60_20_20():
    """FR-D05 for detection, PRD §8.4 for MFSTNet. Different numbers, different
    purposes — an easy conflation to make exactly once."""
    from scripts.prepare_idd import SPLITS

    assert SPLITS == {"train": 0.70, "val": 0.15, "test": 0.15}
    assert sum(SPLITS.values()) == pytest.approx(1.0)


def test_loader_rejects_a_mapping_that_targets_an_undeclared_class(tmp_path):
    from scripts.prepare_idd import load_mapping

    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "target_classes: [car]\n"
        "mapping: {car: car, bus: bus}\n"
        "sampling: {weights: {}, seed: 42}\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="not in target_classes"):
        load_mapping(bad)


def test_a_missing_mapping_file_refuses_rather_than_defaulting(tmp_path):
    """Falling back to a built-in mapping would put the authority back in code,
    which is what DATASETS §6 forbids."""
    from scripts.prepare_idd import load_mapping

    with pytest.raises(SystemExit, match="must not be inlined"):
        load_mapping(tmp_path / "absent.yaml")
