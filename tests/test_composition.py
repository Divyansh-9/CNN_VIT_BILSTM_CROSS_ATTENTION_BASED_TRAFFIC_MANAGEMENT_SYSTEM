"""The evaluation set must contain the domain the paper claims (P58).

P45's density gate and P17's unassigned-rate gate select for *usability*. A
British motorway is long, clean and dense, so it passed both and became 41% of
the evaluation corpus for a project about unstructured Indian traffic. Nothing
asked what it was.

The check these cover has one escape hatch and it is deliberate: to make it
pass, either change the corpus or **change the declared claim** in
`data/cameras.json`. Both are version-controlled and both are visible in a diff.
There is no flag that silences it, because a flag would be used.
"""

from __future__ import annotations

from collections import Counter

import pytest

from mfstnet.corpus.composition import CameraRegistry, compose

INDIA_MIXED = {
    "target_domain": {"country": ["India"], "traffic_type": ["mixed"]},
    "cameras": {
        "delhi": {"country": "India", "traffic_type": "mixed",
                  "viewpoint": "elevated"},
        "mumbai": {"country": "India", "traffic_type": "mixed",
                   "viewpoint": "elevated"},
        "m6": {"country": "United Kingdom", "traffic_type": "structured",
               "viewpoint": "elevated"},
        "dhaka": {"country": "Bangladesh", "traffic_type": "mixed",
                  "viewpoint": "elevated"},
        "mystery": {"country": "unknown", "traffic_type": "unknown",
                    "viewpoint": "unknown"},
    },
}


@pytest.fixture
def registry():
    return CameraRegistry(INDIA_MIXED)


def test_an_on_target_camera_is_recognised(registry):
    assert registry.is_on_target("delhi") is True


def test_the_wrong_country_is_off_target(registry):
    assert registry.is_on_target("m6") is False


def test_the_right_country_with_the_wrong_traffic_type_is_off_target():
    """Geography alone is not the claim. A structured Indian expressway is as
    far from the premise as a British one."""
    payload = {**INDIA_MIXED, "cameras": {
        **INDIA_MIXED["cameras"],
        "expressway": {"country": "India", "traffic_type": "structured",
                       "viewpoint": "elevated"}}}
    assert CameraRegistry(payload).is_on_target("expressway") is False


def test_unknown_is_neither_on_nor_off_target(registry):
    """A distinct third answer on purpose. An unknown camera is not evidence
    for the claim and not evidence against it; folding it into either is the
    guess this module exists to prevent."""
    assert registry.is_on_target("mystery") is None


def test_an_undeclared_camera_is_undetermined_not_assumed(registry):
    assert registry.is_on_target("never_seen_before") is None


def test_a_test_split_with_no_on_target_camera_fails_the_claim(registry):
    composition = compose(registry, Counter({"m6": 252}))
    assert composition.matches_claim is False


def test_one_on_target_camera_is_enough_to_satisfy_it(registry):
    composition = compose(registry, Counter({"m6": 252, "delhi": 40}))
    assert composition.matches_claim is True
    assert composition.on_target == ("delhi",)
    assert composition.off_target == ("m6",)


def test_dominance_is_measured_in_windows_not_cameras(registry):
    """Three Bangladeshi cameras and one British one is three-to-one by camera
    and closer to even by window, and the second is what the model saw."""
    composition = compose(registry, Counter({"m6": 252, "dhaka": 140}))
    country, share = composition.dominant_country()
    assert country == "United Kingdom"
    assert share == pytest.approx(252 / 392)


def test_unknown_cameras_do_not_count_toward_the_claim(registry):
    """The failure mode an assumed attribution would create: a corpus that
    satisfies the check without containing the domain."""
    composition = compose(registry, Counter({"mystery": 500}))
    assert composition.matches_claim is False
    assert composition.unknown == ("mystery",)


def test_missing_reports_cameras_absent_from_the_registry(registry):
    assert registry.missing(["delhi", "ghost"]) == ["ghost"]


def test_widening_the_declared_claim_is_the_escape_hatch():
    """The only way to pass without changing the corpus, and it is a diff.

    If the guide re-frames the paper as South Asian unstructured traffic, Dhaka
    becomes on-target and the M6 still does not — which is exactly right.
    """
    widened = {**INDIA_MIXED,
               "target_domain": {"country": ["India", "Bangladesh"],
                                 "traffic_type": ["mixed"]}}
    registry = CameraRegistry(widened)
    assert registry.is_on_target("dhaka") is True
    assert registry.is_on_target("m6") is False


def test_the_live_registry_covers_every_corpus_camera():
    """A camera in the corpus but not the registry is unauditable."""
    import csv
    import pathlib

    corpus = pathlib.Path("data/corpus/sequences.csv")
    if not corpus.is_file():
        pytest.skip("no corpus built")
    with corpus.open(encoding="utf-8", newline="") as handle:
        cameras = {row["clip_id"] for row in csv.DictReader(handle)}
    missing = CameraRegistry.load().missing(cameras)
    assert not missing, f"cameras with nothing declared about them: {missing}"


def test_the_live_registry_records_how_each_camera_was_determined():
    """'frame' means the footage was looked at. 'filename' means it was not,
    and those entries are provisional — the distinction has to survive."""
    registry = CameraRegistry.load()
    undocumented = [name for name, entry in registry.cameras.items()
                    if "determined_by" not in entry]
    assert not undocumented, undocumented
