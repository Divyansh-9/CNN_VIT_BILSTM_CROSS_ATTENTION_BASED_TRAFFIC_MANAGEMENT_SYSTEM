"""A paper claim is an assertion about the corpus, and must be checkable (P64).

P58 was found by looking at footage after the check had been skipped four times.
The value of a registry is that the fifth skip costs nothing — but only if the
asserted claims actually block, the aspirational ones actually do not, and
promoting one is visible.
"""

from __future__ import annotations

import csv

import pytest

from mfstnet.corpus.composition import CameraRegistry
from scripts.check_claims import CHECKS, run

REGISTRY = CameraRegistry({
    "target_domain": {"country": ["India"], "traffic_type": ["mixed"]},
    "cameras": {
        "delhi": {"country": "India", "traffic_type": "mixed",
                  "viewpoint": "elevated", "licence": "CC BY 4.0"},
        "m6": {"country": "United Kingdom", "traffic_type": "structured",
               "viewpoint": "elevated", "licence": "unresolved"},
        "dash": {"country": "India", "traffic_type": "mixed",
                 "viewpoint": "dashcam", "licence": "CC BY 4.0"},
    },
})


def rows_for(camera, labels):
    """One fold's sequences: `labels` is the test split's lane labels."""
    return [{"clip_id": camera, "split": "test",
             "label_lane_0": label, "label_lane_1": label}
            for label in labels]


def test_the_domain_check_fails_when_no_test_camera_is_on_target():
    check = CHECKS["evaluation_contains_target_domain"]
    passed, detail = check({}, REGISTRY, [("fold0", rows_for("m6", ["LOW"]))])
    assert passed is False
    assert "no on-target camera" in detail


def test_the_domain_check_passes_when_one_is():
    check = CHECKS["evaluation_contains_target_domain"]
    passed, _ = check({}, REGISTRY, [("fold0", rows_for("delhi", ["LOW"]))])
    assert passed is True


def test_a_dashcam_camera_fails_the_viewpoint_claim():
    """A31: dashcam-trained weights lose half their accuracy on a pole. A
    dashcam clip in the corpus is the wrong surface, not a lesser one."""
    passed, detail = CHECKS["every_camera_is_elevated"]({}, REGISTRY, [])
    assert passed is False and "dash" in detail


def test_an_undetermined_viewpoint_passes_but_says_so():
    registry = CameraRegistry({
        "target_domain": {},
        "cameras": {"a": {"viewpoint": "elevated"},
                    "b": {"viewpoint": "unknown"}}})
    passed, detail = CHECKS["every_camera_is_elevated"]({}, registry, [])
    assert passed is True
    assert "undetermined" in detail, (
        "passing silently would let an unchecked camera count toward the claim")


def test_a_thin_class_fails_the_coverage_claim():
    check = CHECKS["every_class_has_test_support"]
    folds = [("fold0", rows_for("delhi", ["LOW"] * 20 + ["MEDIUM"] * 20))]
    passed, detail = check({"minimum_support": 10}, REGISTRY, folds)
    assert passed is False
    assert "HIGH=0" in detail


def test_full_class_coverage_passes():
    check = CHECKS["every_class_has_test_support"]
    folds = [("fold0", rows_for("delhi",
                                ["LOW"] * 10 + ["MEDIUM"] * 10 + ["HIGH"] * 10))]
    passed, _ = check({"minimum_support": 10}, REGISTRY, folds)
    assert passed is True


def test_camera_count_counts_test_cameras_not_corpus_cameras():
    """The claim is about the evaluation. A camera that only ever trains is not
    part of what the paper says was covered."""
    check = CHECKS["enough_eligible_cameras"]
    folds = [("fold0", rows_for("delhi", ["LOW"])),
             ("fold1", rows_for("m6", ["LOW"]))]
    passed, detail = check({"minimum_cameras": 4}, REGISTRY, folds)
    assert passed is False and "2 camera(s)" in detail


def test_an_unresolved_licence_fails_the_release_claim():
    check = CHECKS["every_camera_licence_permits_release"]
    passed, detail = check({"allowed_licences": ["CC BY 4.0"]}, REGISTRY, [])
    assert passed is False and "unresolved" in detail


# ------------------------------------------------------- asserted vs note --


def test_an_asserted_claim_blocks_and_an_aspirational_one_does_not():
    claims = [
        {"id": "hard", "sentence": "x", "status": "asserted",
         "check": "enough_eligible_cameras", "minimum_cameras": 99},
        {"id": "soft", "sentence": "y", "status": "aspirational",
         "check": "enough_eligible_cameras", "minimum_cameras": 99},
    ]
    results = run(claims, REGISTRY, [("fold0", rows_for("delhi", ["LOW"]))])
    blocking = [r for r in results
                if r["status"] == "asserted" and not r["passed"]]
    assert [r["id"] for r in blocking] == ["hard"]


def test_an_unknown_checker_fails_rather_than_being_skipped():
    """A claim naming a checker that does not exist would otherwise pass by
    default, which is the quietest way for an assertion to stop asserting."""
    results = run([{"id": "typo", "sentence": "x", "status": "asserted",
                    "check": "no_such_check"}], REGISTRY, [])
    assert results[0]["passed"] is False
    assert "no checker named" in results[0]["detail"]


# ------------------------------------------------------------ live file --


def test_every_live_claim_names_a_checker_that_exists():
    import pathlib

    import yaml

    claims = yaml.safe_load(
        pathlib.Path("docs/00-planning/CLAIMS.yaml").read_text(encoding="utf-8"))
    missing = [c["id"] for c in claims["claims"] if c["check"] not in CHECKS]
    assert not missing, f"claims with no checker: {missing}"


def test_every_live_claim_declares_a_known_status():
    import pathlib

    import yaml

    claims = yaml.safe_load(
        pathlib.Path("docs/00-planning/CLAIMS.yaml").read_text(encoding="utf-8"))
    bad = [c["id"] for c in claims["claims"]
           if c.get("status") not in ("asserted", "aspirational")]
    assert not bad, bad
