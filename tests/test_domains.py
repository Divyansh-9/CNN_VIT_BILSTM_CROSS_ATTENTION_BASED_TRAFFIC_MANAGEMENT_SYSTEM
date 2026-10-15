"""Domain selection for training (ADR-025): foreign, india, mixed.

The domains decide which cameras a model has ever seen. That is what makes
"does foreign pretraining help India" answerable — so the property pinned
here is disjointness, and that `mixed` keeps the folds every committed result
was produced on.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.composition import CameraRegistry  # noqa: E402
from scripts.resplit_corpus import DOMAINS  # noqa: E402

REGISTRY = CameraRegistry({
    "target_domain": {"country": ["India"], "traffic_type": ["mixed"],
                      "viewpoint": ["elevated"]},
    "cameras": {
        "delhi": {"country": "India", "traffic_type": "mixed",
                  "viewpoint": "elevated"},
        "m6": {"country": "United Kingdom", "traffic_type": "structured",
               "viewpoint": "elevated"},
        "mumbai_unseen": {"country": "India", "traffic_type": "mixed",
                          "viewpoint": "unknown"},
    }})


def admitted(domain: str) -> set[str]:
    allowed = DOMAINS[domain]
    return {c for c in REGISTRY.cameras
            if allowed is None or REGISTRY.partition(c) in allowed}


def test_foreign_and_india_are_disjoint():
    assert DOMAINS["foreign"].isdisjoint(DOMAINS["india"])
    assert admitted("foreign").isdisjoint(admitted("india"))


def test_mixed_admits_everything_so_committed_folds_are_unchanged():
    assert DOMAINS["mixed"] is None
    assert admitted("mixed") == set(REGISTRY.cameras)


def test_an_uninspected_indian_camera_is_in_no_domain_but_mixed():
    """Its viewpoint was never looked at. It is not evidence for the Indian
    headline, and it must not leak into the foreign baseline either — a model
    that has seen it is no longer a clean foreign-only model."""
    assert REGISTRY.partition("mumbai_unseen") == "unknown"
    assert "mumbai_unseen" not in admitted("india")
    assert "mumbai_unseen" not in admitted("foreign")
    assert "mumbai_unseen" in admitted("mixed")


def test_partitions_match_the_claims_scope():
    """`partition` and the headline claim scope ask the same question, so a
    camera cannot train as Indian and be scored as foreign or the reverse."""
    for camera in REGISTRY.cameras:
        on_target = REGISTRY.is_on_target(camera) is True
        assert (REGISTRY.partition(camera) == "real_india") == on_target
