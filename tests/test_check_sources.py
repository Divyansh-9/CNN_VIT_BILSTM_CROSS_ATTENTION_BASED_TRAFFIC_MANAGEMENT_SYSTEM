"""The source register's gate (data/sources.json, scripts/check_sources.py).

The gate exists to refuse things, so the refusals are what is pinned. The
committed register must also pass, because a register that fails its own
check is a register nobody is reading.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import check_sources as S  # noqa: E402

T = {"span_s": 120, "stride_s": 30, "min_continuous_s": 390,
     "min_support": 10, "min_cameras": 4}

GOOD = {"partition": "real_india", "licence_resolved": True,
        "viewpoint": "elevated", "fixed_camera": True,
        "determined_by": "frame", "continuous_s": 3600, "high_support": 40}


def test_the_committed_register_passes_its_own_gate():
    sources = json.loads(S.SOURCES.read_text(encoding="utf-8"))["sources"]
    assert S.violations(sources, S.thresholds()) == []


def test_thresholds_are_read_from_their_records_not_chosen():
    t = S.thresholds()
    assert t["min_continuous_s"] == t["span_s"] + (S.MIN_WINDOWS - 1) * t["stride_s"]
    assert t["min_support"] == 10 and t["min_cameras"] == 4


def test_a_source_meeting_every_criterion_passes_the_forecaster_gate():
    assert S.forecaster_gate(GOOD, T) == []


def test_stills_cannot_feed_the_forecaster():
    """BMD-45's case: right country, right viewpoint, right licence, no
    continuous footage."""
    missing = S.forecaster_gate({**GOOD, "continuous_s": 0}, T)
    assert any("390 s" in m for m in missing)


def test_publicly_viewable_is_not_a_resolved_licence():
    missing = S.forecaster_gate({**GOOD, "licence_resolved": False}, T)
    assert any("licence" in m for m in missing)


def test_unknown_high_support_blocks_acceptance():
    """A camera with no HIGH window cannot score the class the controller
    acts on, and an unlabelled one has not shown it can."""
    assert S.forecaster_gate({**GOOD, "high_support": None}, T)
    assert S.forecaster_gate({**GOOD, "high_support": 3}, T)


def test_accepting_a_source_that_fails_its_gate_is_a_violation():
    register = {"x": {**GOOD, "continuous_s": 60,
                      "roles": {"forecaster": "accepted"}}}
    assert any("accepted for forecaster" in v for v in S.violations(register, T))


def test_synthetic_data_can_never_hold_an_evaluated_role():
    register = {"sim": {"partition": "synthetic_sumo", "licence_resolved": True,
                        "roles": {"forecaster": "candidate"}}}
    assert any("synthetic" in v for v in S.violations(register, T))


def test_a_rejection_must_say_why():
    register = {"x": {**GOOD, "roles": {"forecaster": "rejected"}}}
    assert any("no reason" in v for v in S.violations(register, T))


def test_partition_is_derived_and_unknown_counts_toward_nothing():
    from mfstnet.corpus.composition import CameraRegistry
    registry = CameraRegistry({
        "target_domain": {"country": ["India"], "traffic_type": ["mixed"]},
        "cameras": {
            "delhi": {"country": "India", "traffic_type": "mixed"},
            "expressway": {"country": "India", "traffic_type": "structured"},
            "m6": {"country": "United Kingdom", "traffic_type": "structured"},
            "video1": {"country": "unknown", "traffic_type": "unknown"},
        }})
    assert S.camera_partition(registry, "delhi") == "real_india"
    assert S.camera_partition(registry, "expressway") == "real_external"
    assert S.camera_partition(registry, "m6") == "real_external"
    assert S.camera_partition(registry, "video1") == "unknown"
    assert S.camera_partition(registry, "never_declared") == "unknown"
