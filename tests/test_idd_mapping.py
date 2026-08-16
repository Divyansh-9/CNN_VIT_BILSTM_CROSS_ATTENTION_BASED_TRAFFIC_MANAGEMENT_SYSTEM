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


# ------------------------------- decisions with owners, not notes (S09b) --

def test_e_rickshaw_has_a_pre_registered_rule_not_just_a_note(spec):
    """P12. No public source assessed carries this class — not IDD, not the
    DataCluster sample — so the bootstrap error is total, not bounded. A note
    without an owner is how a defect survives to week 15."""
    p12 = spec["p12_e_rickshaw"]
    assert p12["status"] == "OPEN"
    assert p12["decide_by"]
    assert "1%" in p12["rule"], "the threshold must be explicit"
    assert p12["bias_note"], (
        "the cutoff must be fixed BEFORE the footage exists, for the same reason "
        "A28's statistic was"
    )


def test_s12_states_its_dependency_on_s06(spec):
    """S12 validates the viewpoint claim 'on real junction footage' — which is
    the same blocker the corpus track has. Left unstated, the detector track
    would appear to finish while S06 was still open."""
    dependency = spec["sampling"]["s12_dependency"]
    assert "S06" in dependency["blocked_on"]
    assert dependency["answerable_now"], (
        "the part that needs no new footage must be named, or the whole step "
        "looks blocked when most of it is not"
    )


def test_thin_class_gate_exists_and_exempts_a_known_absence():
    """The --smoke discipline from the PPO harness. A distribution surprise costs
    minutes at 2,000 images and a whole fine-tune to discover afterwards."""
    import inspect

    from scripts import prepare_idd

    source = inspect.getsource(prepare_idd.main)
    assert "min_boxes_per_class" in source
    assert 'name != "e_rickshaw"' in source, (
        "failing on a class known absent from IDD would be failing on a fact"
    )


# ------------------------------------------------ BMD-45 (S13, DATASETS) --

def test_bmd45_targets_are_all_declared_classes(spec):
    targets = set(spec["target_classes"])
    for source, target in spec["bmd45"]["mapping"].items():
        assert target is None or target in targets, f"{source} -> unknown {target}"


def test_bmd45_covers_every_class_in_the_published_taxonomy(spec):
    """All 13 annotated BMD-45 categories are decided explicitly.

    An omitted category is silently dropped by the converter, which is how a
    third of a dataset disappears without anyone noticing.
    """
    published = {
        "Hatchback", "Sedan", "SUV", "MUV", "Van", "Two-wheeler", "Three-wheeler",
        "Bus", "Mini-bus", "Tempo-traveller", "Truck", "LCV", "Bicycle",
    }
    assert set(spec["bmd45"]["mapping"]) == published


def test_bmd45_does_not_claim_the_three_classes_it_lacks(spec):
    """It is a VEHICLE dataset. Believing otherwise would drop IDD entirely and
    lose `pedestrian` and `cattle` with it."""
    for name in ("pedestrian", "cattle", "e_rickshaw"):
        assert name in spec["bmd45"]["absent"]
        assert spec["bmd45"]["absent"][name].strip()
        assert name not in set(spec["bmd45"]["mapping"].values())


def test_bmd45_does_not_close_p12(spec):
    """`Three-wheeler` is tempting to read as auto-rickshaw and be done. P12 asks
    whether OUR junction shows e-rickshaws, which Bengaluru data cannot answer."""
    assert spec["p12_e_rickshaw"]["status"] == "OPEN"
    caveat = spec["bmd45"]["three_wheeler_caveat"]
    assert "P12" in caveat and "conflate" in caveat.lower()


def test_joint_training_is_recorded_as_a_requirement_not_a_preference(spec):
    """Sequential fine-tuning ending on IDD un-teaches the viewpoint, which is
    the entire reason BMD-45 was adopted. One line to get wrong."""
    note = spec["bmd45"]["joint_training"]
    assert "not IDD after BMD-45" in note or "not sequential" in note.lower()
    assert "dashcam" in note.lower()


def test_the_licence_is_recorded_beside_the_source(spec):
    """ADR-013 Decision 4. DataCluster was rejected on exactly this field."""
    assert spec["bmd45"]["licence"] == "CC BY 4.0"
    assert spec["bmd45"]["source"].startswith("https://")
