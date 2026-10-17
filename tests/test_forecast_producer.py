"""P52 closed in code: the forecast producer, and arms that differ only where allowed."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.forecast_producer import NoForecast, Surrogate  # noqa: E402

LOW_MAX, MED_MAX = 4, 15
FORECAST_SLOTS = [11, 12, 13, 14, 16]


class StubOracle:
    def __init__(self, seconds=2000, seed=0):
        self.series = np.random.default_rng(seed).integers(0, 30, size=(seconds + 1, 4))

    def counts(self, seed):
        return self.series

    def describe(self):
        return {"oracle": "stub"}


def cls(n):
    return "LOW" if n <= LOW_MAX else ("MEDIUM" if n <= MED_MAX else "HIGH")


def surrogate(q, **kw):
    s = Surrogate(q, StubOracle(**kw), low_max=LOW_MAX, med_max=MED_MAX)
    s.reset(7)
    return s


NOW = {"N": 0, "S": 7, "E": 20, "W": 3}


def test_no_forecast_sends_no_message():
    assert NoForecast().message(0, NOW) == (None, None)


def test_the_oracle_ages_honestly_and_refreshes_past_ten_seconds():
    s = surrogate(1.0)
    series = s.oracle.series
    seen = [s.message(t, NOW) for t in (0, 5, 10, 15, 20)]
    assert [age for _, age in seen] == [0.0, 5.0, 10.0, 0.0, 5.0]
    assert seen[0][0] == {a: cls(series[60][k]) for k, a in enumerate("NSEW")}
    assert seen[1][0] == seen[0][0] == seen[2][0]            # carried, not recomputed
    assert seen[3][0] == {a: cls(series[75][k]) for k, a in enumerate("NSEW")}


def test_an_eleven_second_step_never_shows_a_stale_age():
    s = surrogate(1.0)
    ages = [s.message(t, NOW)[1] for t in (0, 5, 16, 21, 26, 37)]
    assert max(ages) <= 10.0


def test_quality_zero_is_persistence_made_at_the_refresh():
    s = surrogate(0.0)
    first, _ = s.message(0, NOW)
    assert first == {a: cls(n) for a, n in NOW.items()}
    later, age = s.message(5, {a: 29 for a in "NSEW"})       # counts moved; message did not
    assert later == first and age == 5.0


def test_the_corruption_is_seeded_and_delivers_its_share():
    def run(q):
        s = surrogate(q, seconds=200_000)
        msgs = [s.message(t, NOW)[0] for t in range(0, 199_000, 5)]
        return msgs, s.stats

    a, stats = run(0.5)
    b, _ = run(0.5)
    assert a == b
    assert abs(stats["informed_messages"] / stats["messages"] - 0.5) < 0.05


def test_a_surrogate_fails_closed():
    s = Surrogate(1.0, StubOracle(seconds=100), low_max=LOW_MAX, med_max=MED_MAX)
    with pytest.raises(RuntimeError):
        s.message(0, NOW)                                     # before reset
    s.reset(1)
    with pytest.raises(RuntimeError):
        s.message(50, NOW)                                    # the oracle cannot see 110 s
    with pytest.raises(ValueError):
        Surrogate(1.5, StubOracle(), low_max=LOW_MAX, med_max=MED_MAX)


# ------------------------------------------------------------ needs SUMO --

def rollout(forecast, seed=999, steps=80):
    pytest.importorskip("traci")
    from simulation.envs.traffic_env import TrafficSignalEnv

    env = TrafficSignalEnv(regime="pulsed", seed=seed, episode_s=600,
                           action_space="keep_or_switch", forecast=forecast)
    obs, _ = env.reset(seed=seed)
    out = [obs]
    try:
        for k in range(steps):
            obs, _, done, truncated, _ = env.step(1 if k % 4 == 3 else 0)
            out.append(obs)
            if done or truncated:
                break
    finally:
        env.close()
    return np.array(out)


def test_arms_differ_only_in_the_forecast_slots():
    plain = rollout(None)
    aware = rollout(Surrogate(1.0, StubOracle(), low_max=LOW_MAX, med_max=MED_MAX))
    assert plain.shape == aware.shape and plain.shape[1] == 17
    others = [i for i in range(17) if i not in FORECAST_SLOTS]
    assert np.array_equal(plain[:, others], aware[:, others])
    assert (plain[:, 11:15] == 0.0).all() and (plain[:, 16] == 1.0).all()
    def among(values, allowed):                               # float32 observations
        return (np.abs(values[..., None] - np.array(allowed)) < 1e-6).any(axis=-1).all()

    assert among(aware[:, 11:15], [1 / 3, 2 / 3, 1.0])         # a class, never absent
    assert among(aware[:, 16], [0.0, 0.5, 1.0])               # ages 0, 5, 10 s


def test_persistence_arm_reports_the_class_of_the_counts_it_was_made_from():
    aware = rollout(Surrogate(0.0, StubOracle(), low_max=LOW_MAX, med_max=MED_MAX))
    value = {"LOW": 1 / 3, "MEDIUM": 2 / 3, "HIGH": 1.0}
    fresh = aware[aware[:, 16] == 0.0]
    counts = np.rint(fresh[:, 0:4] * 50).astype(int)          # count_divisor 50
    want = np.vectorize(lambda n: value[cls(n)])(counts)
    assert np.allclose(fresh[:, 11:15], want)


def test_replay_oracle_is_cached_deterministic_and_writes_no_tripinfo(tmp_path):
    pytest.importorskip("traci")
    checkpoint = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
    if not checkpoint.exists():
        pytest.skip("needs a trained no-forecast checkpoint")
    from simulation.oracle import ReplayOracle

    before = set(Path("data/_tripinfo").glob("*.tripinfo.xml"))
    oracle = ReplayOracle(checkpoint, "pulsed", episode_s=120, lateral_resolution=0.8,
                          cache=tmp_path)
    first = oracle.counts(999)
    from simulation.oracle import OVERRUN_S

    assert first.shape[0] >= 120 + 60 + OVERRUN_S and first.shape[1] == 4
    assert len(list(tmp_path.glob("*.npy"))) == 1
    fresh = ReplayOracle(checkpoint, "pulsed", episode_s=120, lateral_resolution=0.8,
                         cache=tmp_path / "again").counts(999)
    assert np.array_equal(first, fresh)                       # deterministic replay
    assert np.array_equal(oracle.counts(999), first)          # and read back from cache
    assert oracle._env.write_tripinfo is False and oracle._env._tripinfo is None
    assert set(Path("data/_tripinfo").glob("*.tripinfo.xml")) <= before   # before any sweep
    oracle._env.close()


def test_the_oracle_answers_every_decision_of_an_episode_including_the_overrun(tmp_path):
    """A switch near the end runs its interphase past episode_s; the oracle must still answer."""
    pytest.importorskip("traci")
    checkpoint = Path("models/ppo/ppo_no-forecast_saturated_keep_or_switch_seed42.zip")
    if not checkpoint.exists():
        pytest.skip("needs a trained no-forecast checkpoint")
    from simulation.envs.traffic_env import TrafficSignalEnv
    from simulation.oracle import ReplayOracle

    oracle = ReplayOracle(checkpoint, "pulsed", episode_s=300, lateral_resolution=0.8,
                          cache=tmp_path)
    producer = Surrogate(1.0, oracle, low_max=LOW_MAX, med_max=MED_MAX)
    env = TrafficSignalEnv(regime="pulsed", seed=42, episode_s=300,
                           action_space="keep_or_switch", forecast=producer)
    env.reset(seed=42)
    try:
        done = False
        while not done:                                       # always switch: maximal overrun
            _, _, terminated, truncated, _ = env.step(1)
            done = terminated or truncated
        assert env._step_s > 300                              # the overrun really happened
    finally:
        env.close()
        oracle._env.close()
