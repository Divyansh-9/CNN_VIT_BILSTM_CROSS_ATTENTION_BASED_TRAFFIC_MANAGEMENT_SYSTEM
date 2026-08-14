"""Bind the Python defaults to `mfstnet/configs/spec.yaml` (NFR-16).

`test_spec_invariants.py` checks that spec.yaml is internally consistent — that
its derived numbers actually add up. It cannot check the thing that matters more:
whether the **code** agrees with it.

That gap is real and it is the A15 shape of defect. The window arithmetic was
stated correctly in three documents and still never added up, because nothing
executed it. Here the values happened to agree when this file was written; they
agreed by care, not by construction, and the next edit to either side could have
diverged in silence.

So: every number the specification fixes and the code also holds is asserted
equal here. If you change one, this fails, and the fix is to change the other —
or to amend the PRD and log it in PRD-CHANGELOG, never to edit this test.

This file runs in **both** CI jobs. The fast job executes the checks that need
only pyyaml and the standard library; the model job runs the whole file with
torch present, so the dimension and backbone checks genuinely execute rather
than skipping. A check that skips in every job is not a check — that mistake is
what left amendment A24 unguarded once already.

    python -m pytest tests/test_spec_matches_code.py -q
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

SPEC_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "mfstnet" / "configs" / "spec.yaml"
)


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


# --------------------------------- pure standard library: runs in BOTH jobs --

def test_seed_matches(spec):
    """NFR-07. A `set_seed()` defaulting to anything but the specified seed
    would make every 'seed 42' claim in the report false.

    Read from the source rather than imported: `scripts/seed.py` pulls in numpy
    and torch, and this assertion needs neither.
    """
    import re

    source = (SPEC_PATH.parent.parent.parent / "scripts" / "seed.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r"^DEFAULT_SEED\s*=\s*(\d+)", source, re.MULTILINE)
    assert match, "DEFAULT_SEED not found in scripts/seed.py"
    assert int(match.group(1)) == spec["seed"]


def test_congestion_thresholds_match(spec):
    """PRD §14.1. These decide every label in the corpus — the single most
    load-bearing pair of numbers in the project."""
    from mfstnet.corpus.labels import CongestionClass, label_from_count

    low_max, med_max = spec["congestion"]["low_max"], spec["congestion"]["med_max"]

    assert label_from_count(low_max) is CongestionClass.LOW
    assert label_from_count(low_max + 1) is CongestionClass.MEDIUM
    assert label_from_count(med_max) is CongestionClass.MEDIUM
    assert label_from_count(med_max + 1) is CongestionClass.HIGH


def test_class_names_and_count_match(spec):
    from mfstnet.corpus.labels import CongestionClass

    assert [c.name for c in CongestionClass] == spec["congestion"]["classes"]
    assert len(CongestionClass) == spec["model"]["n_classes"]


def test_window_geometry_matches(spec):
    """A15. The defect that started all of this: the label must fall OUTSIDE
    the observation window, and a 5-minute clip yields zero sequences."""
    from mfstnet.corpus.windows import WindowGeometry

    geom = WindowGeometry()
    seq = spec["sequence"]

    assert geom.T == seq["T"]
    assert geom.step_s == seq["step_s"]
    assert geom.horizon_s == seq["horizon_s"]
    assert geom.stride_s == seq["stride_s"]
    assert geom.observation_span_s == (seq["T"] - 1) * seq["step_s"]
    assert geom.label_offset_s == geom.observation_span_s + seq["horizon_s"]
    assert geom.min_clip_s <= seq["min_clip_s"]


def test_lane_count_matches(spec):
    pytest.importorskip("torch")
    from mfstnet.model import MFSTNetConfig

    assert MFSTNetConfig().n_lanes == len(spec["lanes"])


def test_ablation_config_names_match(spec):
    """§14.4 has eight rows. A config present in one place and not the other
    means the table in the paper describes a run that did not happen."""
    pytest.importorskip("torch")
    from mfstnet.model import ABLATION_CONFIGS

    assert list(ABLATION_CONFIGS) == spec["ablation"]["configs"]


def test_five_seeds_are_specified(spec):
    """A23. A two-point macro-F1 gap between configs is meaningless without
    seed variance — and config F proved it during S26, passing at seeds 1-3 and
    failing at 42 for reasons that had nothing to do with the architecture."""
    assert len(spec["ablation"]["seeds"]) == 5
    assert spec["seed"] in spec["ablation"]["seeds"]


def test_cache_policy_is_raise_not_warn(spec):
    """SOW R20. If this ever reads 'warn', the control is gone."""
    assert spec["cache"]["on_hash_mismatch"] == "raise"


def test_grid_and_d_model_are_absent_from_the_cache_key(spec):
    """They belong to the trainable adapter downstream of the cache. Keeping
    them out is what lets the G=7 vs G=14 question be re-run for free."""
    pytest.importorskip("torch")
    from dataclasses import fields

    from mfstnet.cache import PreprocessingSpec

    names = {f.name for f in fields(PreprocessingSpec)}
    assert "grid" not in names and "d_model" not in names


# ------------------------------- needs torch: executed by the MODEL job --

def test_model_dimensions_match(spec):
    pytest.importorskip("torch")
    from mfstnet.encoders import EncoderConfig
    from mfstnet.fusion import FusionConfig
    from mfstnet.model import MFSTNetConfig
    from mfstnet.temporal import TemporalConfig

    model = spec["model"]
    assert EncoderConfig().d_model == model["d_model"]
    assert EncoderConfig().grid == spec["fusion"]["grid"]
    assert TemporalConfig().hidden == model["bilstm_hidden"]
    assert TemporalConfig().layers == model["bilstm_layers"]
    assert TemporalConfig().attn_layers == model["temporal_attn_layers"]
    assert TemporalConfig().attn_heads == model["temporal_attn_heads"]
    assert FusionConfig().n_heads == model["cross_attn_heads"]
    assert MFSTNetConfig().head_hidden == model["head_hidden"]
    assert MFSTNetConfig().n_classes == model["n_classes"]


def test_bidirectional_hidden_doubles_to_d_model(spec):
    """2x128 = 256 is a constraint, not a coincidence, and the code raises if
    someone edits one number without the other."""
    assert 2 * spec["model"]["bilstm_hidden"] == spec["model"]["d_model"]


def test_cache_dtype_matches(spec):
    pytest.importorskip("torch")
    from mfstnet.cache import PreprocessingSpec

    assert PreprocessingSpec().dtype == spec["cache"]["dtype"]


def test_vit_resize_mode_matches(spec):
    """A different interpolation gives different features from identical
    inputs, so this is part of `preprocessing_hash` and must not drift."""
    pytest.importorskip("torch")
    from mfstnet.cache import PreprocessingSpec

    assert PreprocessingSpec().resize_mode == spec["fusion"]["vit_resize"]


def test_the_overfit_check_uses_the_specified_learning_rate(spec):
    """The S26 incident, encoded. `overfit_check.py` invented 1e-3, config F
    stalled at loss 0.41 for 900 steps, and it read exactly like a broken
    graph. A training script that invents a number the specification fixes is
    a defect (NFR-16) — so the number is now asserted, not trusted."""
    pytest.importorskip("torch")
    from scripts.overfit_check import PRD_LR

    assert PRD_LR == spec["training"]["lr"]


def test_backbone_arms_are_buildable_names(spec):
    """ADR-007 lists three arms. A typo in the table would surface as a
    KeyError halfway through an ablation run, hours in."""
    pytest.importorskip("torch")
    from mfstnet.encoders import _CNN_CHANNELS, _VIT_CHANNELS, EncoderConfig

    for name, arm in spec["ablation"]["backbone_arms"].items():
        assert arm["cnn"] in _CNN_CHANNELS, f"{name}: unknown CNN {arm['cnn']!r}"
        assert arm["vit"] in _VIT_CHANNELS, f"{name}: unknown ViT {arm['vit']!r}"
        # Constructing the config exercises the channel lookup, which is what
        # would actually raise mid-ablation.
        cfg = EncoderConfig(cnn=arm["cnn"], vit=arm["vit"])
        assert cfg.cnn_channels > 0 and cfg.vit_channels > 0


def test_the_default_arm_is_what_the_code_defaults_to(spec):
    """BB-2 is the default per A12. If spec.yaml and the dataclass disagree on
    which arm is default, every unlabelled result is ambiguous."""
    pytest.importorskip("torch")
    from mfstnet.encoders import EncoderConfig

    bb2 = spec["ablation"]["backbone_arms"]["BB-2"]
    assert (EncoderConfig().cnn, EncoderConfig().vit) == (bb2["cnn"], bb2["vit"])


def test_ppo_config_matches_the_prd(spec):
    """PRD §13.1. These live in simulation/configs/ppo_config.yaml because the
    three ADR-009 arms differ only by config (NFR-16)."""
    import pathlib

    config = yaml.safe_load(
        pathlib.Path("simulation/configs/ppo_config.yaml").read_text(encoding="utf-8")
    )
    ppo = config["ppo"]
    assert ppo["learning_rate"] == 3e-4
    assert ppo["n_steps"] == 2048
    assert ppo["batch_size"] == 64
    assert ppo["gamma"] == 0.99
    assert ppo["gae_lambda"] == 0.95
    assert ppo["clip_range"] == 0.2
    assert ppo["ent_coef"] == 0.01
    assert ppo["total_timesteps"] == 500_000
    assert config["seed"] == spec["seed"]


def test_the_benchmark_declares_thirty_seeds_and_bootstrap(spec):
    """FR-R07 / NFR-10. A mean without a CI is not a result."""
    import pathlib

    config = yaml.safe_load(
        pathlib.Path("simulation/configs/ppo_config.yaml").read_text(encoding="utf-8")
    )["benchmark"]
    assert config["seeds"] == 30
    assert config["bootstrap_resamples"] == 10_000
    assert config["alpha"] == 0.05


def test_the_no_forecast_arm_exists_and_is_the_floor():
    """ADR-009. Any claim that the forecast helps is measured against this arm,
    so it must be present and must not use MFSTNet."""
    import pathlib

    arms = yaml.safe_load(
        pathlib.Path("simulation/configs/ppo_config.yaml").read_text(encoding="utf-8")
    )["arms"]
    assert arms["no-forecast"]["use_mfstnet"] is False
    assert set(arms) == {"no-forecast", "surrogate", "mfstnet"}
