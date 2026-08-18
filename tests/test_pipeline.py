"""Tests for the corpus-to-training pipeline (S15-S20).

These guard the properties that P15, P16 and P17 all slipped through: things
relied on everywhere and asserted nowhere. Each one below corresponds to a defect
that was found by running the code rather than by reading it.

    python -m pytest tests/test_pipeline.py -q
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from mfstnet.corpus.geometry import Polygon  # noqa: E402


# ------------------------------------------------------- lane survey (P17) --

def test_clustering_is_deterministic_given_the_seed():
    """NFR-07. A survey that moves between runs makes every count irreproducible,
    and the polygons are an input to every label the corpus contains."""
    from scripts.survey_lanes import cluster

    points = [(0.1 + 0.01 * i, 0.6) for i in range(20)]
    points += [(0.8 + 0.01 * i, 0.6) for i in range(20)]

    first = cluster(points, 2, seed=42)
    second = cluster(points, 2, seed=42)
    assert [sorted(g) for g in first] == [sorted(g) for g in second]


def test_separated_clusters_produce_disjoint_lanes():
    """`corpus.geometry.assert_disjoint` forbids overlap, because a vehicle in a
    shared region is counted twice and the count is wrong before any threshold
    is applied."""
    from mfstnet.corpus.geometry import assert_disjoint
    from scripts.survey_lanes import cluster, extent

    left = [(0.05 + 0.01 * i, 0.5 + 0.01 * (i % 5)) for i in range(20)]
    right = [(0.75 + 0.01 * i, 0.5 + 0.01 * (i % 5)) for i in range(20)]
    groups = cluster(left + right, 2, seed=42)

    lanes = [Polygon(f"lane_{i}", extent(g)) for i, g in enumerate(groups) if g]
    assert len(lanes) == 2
    assert_disjoint(lanes)          # raises if they overlap


def test_surveying_more_lanes_than_detections_is_refused():
    from scripts.survey_lanes import cluster

    with pytest.raises(SystemExit, match="too few"):
        cluster([(0.5, 0.5)], 4)


# ------------------------------------------------- training harness (S20) --

def test_absent_class_gets_zero_weight_not_infinity():
    """Inverse frequency divides by the class count. A class with none present
    would divide by zero and surface as NaN loss twenty minutes into a run
    rather than as a message before it starts."""
    from scripts.train_mfstnet import class_weights

    weights, counts = class_weights([0, 0, 1, 1, 1], 3)
    assert counts == [2, 3, 0]
    assert float(weights[2]) == 0.0
    assert torch.isfinite(weights).all()
    assert float(weights[0]) > float(weights[1]), "rarer class must weigh more"


def test_the_feed_passes_only_the_branches_a_config_enables():
    """MFSTNet REFUSES features for a disabled branch — "silently ignoring them
    would make the ablation table describe a model that was not run". Config A
    has no ViT, config B no CNN, so the harness must respect the flags."""
    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks
    from scripts.train_mfstnet import feed

    quads = (
        Polygon("a", ((0.0, 0.0), (0.45, 0.0), (0.45, 1.0), (0.0, 1.0))),
        Polygon("b", ((0.55, 0.0), (1.0, 0.0), (1.0, 1.0), (0.55, 1.0))),
    )
    masks = lane_masks(quads, 7)
    cnn = torch.randn(2, 4, 2048, 7, 7)
    vit = torch.randn(2, 4, 384, 16, 16)

    import dataclasses

    for name in ("A", "B", "E"):
        config = dataclasses.replace(ablation_config(name), n_lanes=2)
        model = MFSTNet(config, masks).eval()
        with torch.no_grad():
            out = feed(model, cnn, vit)     # must not raise for any config
        assert out.logits.shape[:2] == (2, 2)


def test_the_lane_count_comes_from_the_corpus_not_the_config_default():
    """P17: lane count is a property of the camera. A junction has four
    approaches and a motorway two, so a config carrying a hardcoded 4 would
    refuse every two-lane corpus."""
    import dataclasses

    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks

    quads = (
        Polygon("a", ((0.0, 0.0), (0.45, 0.0), (0.45, 1.0), (0.0, 1.0))),
        Polygon("b", ((0.55, 0.0), (1.0, 0.0), (1.0, 1.0), (0.55, 1.0))),
    )
    masks = lane_masks(quads, 7)

    with pytest.raises(ValueError, match="lanes"):
        MFSTNet(ablation_config("E"), masks)        # default 4 against 2 masks

    model = MFSTNet(dataclasses.replace(ablation_config("E"), n_lanes=2), masks)
    assert model.cfg.n_lanes == 2


def test_gate_statistics_are_emitted_for_G_and_blank_otherwise(): 
    """P16. The gate is the narrowed novelty claim and has never been shown to
    move off 0.5. Its spread must reach the results CSV for every run, and the
    configs without a gate must report blank rather than a misleading zero."""
    import dataclasses

    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks
    from scripts.train_mfstnet import feed, gate_stats

    quads = (
        Polygon("a", ((0.0, 0.0), (0.45, 0.0), (0.45, 1.0), (0.0, 1.0))),
        Polygon("b", ((0.55, 0.0), (1.0, 0.0), (1.0, 1.0), (0.55, 1.0))),
    )
    masks = lane_masks(quads, 7)
    cnn = torch.randn(2, 4, 2048, 7, 7)
    vit = torch.randn(2, 4, 384, 16, 16)

    gated = MFSTNet(dataclasses.replace(ablation_config("G"), n_lanes=2), masks).eval()
    plain = MFSTNet(dataclasses.replace(ablation_config("E"), n_lanes=2), masks).eval()
    with torch.no_grad():
        gated_stats = gate_stats(feed(gated, cnn, vit))
        plain_stats = gate_stats(feed(plain, cnn, vit))

    assert gated_stats["gate_std"] != "", "config G must report its gate spread"
    assert plain_stats["gate_std"] == "", (
        "a config with no gate must report blank, not 0 — a zero would read as "
        "a measured constant gate rather than as an absent one"
    )


# ------------------------------------------------ corpus assembly (P17) --

def test_a_clip_whose_detections_miss_every_lane_is_rejected(tmp_path):
    """P17's gate. Counts through a mismatched polygon are not low counts, they
    are counts of the wrong region, and a balanced label distribution over
    meaningless counts is worse than an obviously broken one.

    Measured across 13 clips sharing one polygon set: 13.5% to 94% assigned.
    """
    from mfstnet.corpus.counting import Detection, count_frame

    lanes = (
        Polygon("left", ((0.0, 0.5), (0.45, 0.5), (0.45, 1.0), (0.0, 1.0))),
        Polygon("right", ((0.55, 0.5), (1.0, 0.5), (1.0, 1.0), (0.55, 1.0))),
    )
    # Vehicles along the TOP of the frame — a camera these polygons do not fit.
    detections = [
        Detection(cls="car", confidence=0.9,
                  x1=0.1 + 0.05 * i, y1=0.05, x2=0.14 + 0.05 * i, y2=0.12)
        for i in range(8)
    ]
    counts = count_frame(detections, lanes, min_confidence=0.45)

    assigned = sum(counts.per_lane.values())
    rate = counts.unassigned / max(assigned + counts.unassigned, 1)
    assert rate > 0.35, (
        "detections outside every lane must drive the unassigned rate above the "
        "35% gate build_corpus refuses at"
    )


def test_counts_inside_a_matching_lane_are_assigned():
    """The other half — the gate must not reject footage that fits."""
    from mfstnet.corpus.counting import Detection, count_frame

    lanes = (
        Polygon("left", ((0.0, 0.5), (0.45, 0.5), (0.45, 1.0), (0.0, 1.0))),
        Polygon("right", ((0.55, 0.5), (1.0, 0.5), (1.0, 1.0), (0.55, 1.0))),
    )
    detections = [
        Detection(cls="car", confidence=0.9, x1=0.10, y1=0.70, x2=0.18, y2=0.80),
        Detection(cls="car", confidence=0.9, x1=0.60, y1=0.70, x2=0.68, y2=0.80),
    ]
    counts = count_frame(detections, lanes, min_confidence=0.45)

    assert counts.unassigned == 0
    assert counts.per_lane["left"] == 1
    assert counts.per_lane["right"] == 1


def test_window_arithmetic_refuses_a_clip_that_is_one_sample_short():
    """A15. T observations at step_s spacing span (T-1)*step_s, and the label
    sits horizon_s past the last one — the off-by-one that names the amendment."""
    from mfstnet.corpus.windows import WindowGeometry, sequences_from_clip

    geometry = WindowGeometry(T=60, step_s=5, horizon_s=60, stride_s=30)
    need = geometry.min_frames

    assert sequences_from_clip("short", need - 1, geometry) == []
    assert len(sequences_from_clip("exact", need, geometry)) >= 1
