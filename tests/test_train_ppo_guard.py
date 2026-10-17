"""P52 fail-closed: `train_ppo.py` refuses a forecast arm without a valid producer.

Every refusal below happens before an environment or a model is built. The
last test drives the audit wrapper with observations a broken producer would
emit, and requires it to stop training on the first one.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("stable_baselines3")

from scripts.train_ppo import ProducerRefused, build_producer, forecast_audit, load_config  # noqa: E402
from simulation.contract import contract_digest  # noqa: E402
from simulation.forecast_producer import NoForecast, Surrogate  # noqa: E402

CONFIG = load_config()


def world(tmp_path, *, sidecar=None, requal=None, lock=None):
    """A frozen policy file, its sidecar and a requalification record, all valid by default."""
    frozen = tmp_path / "frozen.zip"
    frozen.write_bytes(b"weights")
    side = {"arm": "no-forecast", "regime": "pulsed", "action_space": "keep_or_switch",
            "smoke": False, "timesteps": CONFIG["ppo"]["total_timesteps"],
            "observation_contract": contract_digest(),
            "lateral_resolution": CONFIG["env"]["lateral_resolution"]}
    side.update(sidecar or {})
    Path(str(frozen) + ".provenance.json").write_text(json.dumps(side), encoding="utf-8")
    record = {"passed": True, "frozen_policy_sha256": hashlib.sha256(b"weights").hexdigest()}
    record.update(requal or {})
    lock_path = tmp_path / "lock.json"
    lock_body = {"passed": True,
                 "replicates": {"42": {"checkpoint": str(frozen),
                                       "sha256": hashlib.sha256(b"weights").hexdigest()}},
                 "configs_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (Path("simulation/configs/ppo_config.yaml"),
                                              Path("mfstnet/configs/spec.yaml"))}}
    lock_body.update(lock or {})
    lock_path.write_text(json.dumps(lock_body), encoding="utf-8")
    record.setdefault("lock_sha256", hashlib.sha256(lock_path.read_bytes()).hexdigest())
    path = tmp_path / "requalification.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    config = copy.deepcopy(CONFIG)
    config["arms"]["surrogate"]["frozen_policy"] = str(frozen)
    config["arms"]["surrogate"]["requalification"] = str(path)
    config["arms"]["surrogate"]["lock"] = str(lock_path)
    return config


def build(config, arm="surrogate", quality=1.0, regime="pulsed", action_space="keep_or_switch"):
    return build_producer(config, arm, quality=quality, regime=regime,
                          action_space=action_space, episode_s=1800)


def test_the_valid_world_builds_a_surrogate(tmp_path):
    producer = build(world(tmp_path))
    assert isinstance(producer, Surrogate) and producer.q == 1.0
    assert producer.describe()["frozen_policy_sha256"] == hashlib.sha256(b"weights").hexdigest()


def test_no_forecast_builds_no_forecast_and_refuses_a_quality(tmp_path):
    assert isinstance(build(CONFIG, "no-forecast", quality=None, regime="saturated"), NoForecast)
    with pytest.raises(ProducerRefused):
        build(CONFIG, "no-forecast", quality=0.5)


@pytest.mark.parametrize("change", [
    dict(quality=None),                          # no quality given
    dict(quality=0.3),                           # off the pre-registered grid
    dict(regime="saturated"),                    # constant regime: no qualified headroom
    dict(action_space="phase_duration"),         # the surrogate is keep_or_switch only
    dict(arm="mfstnet"),                         # needs frames SUMO cannot give
    dict(arm="rush"),                            # unknown arm
])
def test_refused_arguments(tmp_path, change):
    with pytest.raises(ProducerRefused):
        build(world(tmp_path), **change)


@pytest.mark.parametrize("sidecar", [
    {"smoke": True}, {"timesteps": 3000}, {"arm": "surrogate"}, {"regime": "saturated"},
    {"lateral_resolution": None}, {"observation_contract": "24ad1c994e844238"},
])
def test_an_unfit_frozen_policy_is_refused(tmp_path, sidecar):
    with pytest.raises(ProducerRefused):
        build(world(tmp_path, sidecar=sidecar))


@pytest.mark.parametrize("requal", [{"passed": False}, {"frozen_policy_sha256": "0" * 64}])
def test_a_failed_or_mismatched_requalification_is_refused(tmp_path, requal):
    with pytest.raises(ProducerRefused):
        build(world(tmp_path, requal=requal))


@pytest.mark.parametrize("lock", [
    {"passed": False},                                            # the audit failed
    {"replicates": {"42": {"checkpoint": "x.zip", "sha256": "0" * 64}}},  # not this policy
    {"configs_sha256": {"mfstnet/configs/spec.yaml": "0" * 64}},  # a config changed since
])
def test_the_audit_lock_is_enforced(tmp_path, lock):
    with pytest.raises(ProducerRefused):
        build(world(tmp_path, lock=lock))


def test_a_requalification_against_a_different_lock_is_refused(tmp_path):
    with pytest.raises(ProducerRefused):
        build(world(tmp_path, requal={"lock_sha256": "0" * 64}))


def test_a_missing_frozen_policy_or_record_is_refused(tmp_path):
    config = world(tmp_path)
    Path(config["arms"]["surrogate"]["requalification"]).unlink()
    with pytest.raises(ProducerRefused):
        build(config)
    Path(config["arms"]["surrogate"]["frozen_policy"]).unlink()
    with pytest.raises(ProducerRefused):
        build(config)


import gymnasium as gym  # noqa: E402


class FakeEnv(gym.Env):
    """Emits a fixed 17-dim observation, as a broken or a working producer would."""

    def __init__(self, slots, age):
        self.obs = np.zeros(17, dtype=np.float32)
        self.obs[11:15], self.obs[16] = slots, age
        self.observation_space = gym.spaces.Box(0, np.inf, (17,), np.float32)
        self.action_space = gym.spaces.Discrete(2)

    def reset(self, **kwargs):
        return self.obs.copy(), {}

    def step(self, action):
        return self.obs.copy(), 0.0, False, False, {}


def test_the_audit_stops_a_surrogate_that_sends_absent_slots():
    surrogate = Surrogate(1.0, object(), low_max=4, med_max=15)
    with pytest.raises(RuntimeError):
        forecast_audit(FakeEnv([0.0] * 4, 1.0), surrogate).reset()


def test_the_audit_stops_a_no_forecast_arm_that_carries_a_forecast():
    with pytest.raises(RuntimeError):
        forecast_audit(FakeEnv([1 / 3] * 4, 0.0), NoForecast()).reset()


def test_the_audit_passes_valid_observations_and_counts_them():
    env = forecast_audit(FakeEnv([1 / 3, 2 / 3, 1.0, 2 / 3], 0.5),
                         Surrogate(1.0, object(), low_max=4, med_max=15))
    env.reset()
    env.step(0)
    assert env.checked == 2


def test_checkpoint_names_have_no_dot_and_differ_by_quality():
    """P128: q1.00 once made the guard, sidecar and weights land on the wrong names."""
    from scripts.train_ppo import checkpoint_zip

    names = {q: checkpoint_zip(Path("m"), "surrogate", "pulsed", "keep_or_switch", 42, q)
             for q in (0.0, 0.25, 0.5, 0.75, 1.0)}
    assert len(set(names.values())) == 5
    for path in names.values():
        assert path.suffix == ".zip" and path.name.count(".") == 1
    assert names[1.0].name == "ppo_surrogate-q100_pulsed_keep_or_switch_seed42.zip"
    assert checkpoint_zip(Path("m"), "no-forecast", "pulsed", "keep_or_switch", 42).name == \
        "ppo_no-forecast_pulsed_keep_or_switch_seed42.zip"           # the locked names stand


def test_the_evaluation_finds_checkpoints_by_the_training_name():
    from scripts.ceiling_eval import checkpoint
    from scripts.train_ppo import checkpoint_zip

    assert checkpoint("oracle", 7) == checkpoint_zip(Path("models/ppo"), "surrogate", "pulsed",
                                                     "keep_or_switch", 7, 1.0)
    assert checkpoint("no-forecast", 42).exists()                  # the locked replicate
