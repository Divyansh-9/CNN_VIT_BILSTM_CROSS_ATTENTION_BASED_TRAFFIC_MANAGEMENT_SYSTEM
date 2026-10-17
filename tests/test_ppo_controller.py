"""A benchmarked policy must be decoded the way it was trained (S38).

The action space and the observation layout are both contracts between training
and evaluation, and both fail silently when broken: the policy loads, the
episode runs, the CSV fills, and every number is about a different experiment.

The first version of `PPOController` got the action decoding wrong — it invented
a green ladder from `action // 2` on a two-action space, so every green would
have been 10s while the environment used its decision interval. Nothing would
have raised.
"""

from __future__ import annotations

import pytest

pytest.importorskip("stable_baselines3")

from simulation.ppo_controller import discover_checkpoints  # noqa: E402

NS, EW = 0, 1


class Decoder:
    """`_interpret` without loading a checkpoint, so the arithmetic is testable
    on its own."""

    def __init__(self, action_space, greens=(10, 20, 30, 45, 60, 90),
                 decision_interval_s=5):
        from simulation.ppo_controller import PPOController

        self.action_space = action_space
        self.greens = list(greens)
        self.decision_interval_s = decision_interval_s
        self._interpret = PPOController._interpret.__get__(self)


# ------------------------------------------------------- keep_or_switch --


def test_keep_or_switch_action_zero_keeps_the_phase():
    assert Decoder("keep_or_switch")._interpret(0, NS) == (NS, 5)


def test_keep_or_switch_action_one_switches():
    assert Decoder("keep_or_switch")._interpret(1, NS) == (EW, 5)
    assert Decoder("keep_or_switch")._interpret(1, EW) == (NS, 5)


def test_keep_or_switch_green_is_the_decision_interval_not_the_ladder():
    """The bug this test exists for. `Discrete(2)` carries no duration, and
    decoding one from `action // 2` yields the ladder's smallest every time."""
    decoder = Decoder("keep_or_switch", decision_interval_s=7)
    assert decoder._interpret(0, NS)[1] == 7
    assert decoder._interpret(1, NS)[1] == 7
    assert decoder._interpret(1, NS)[1] != decoder.greens[0]


# -------------------------------------------------------- phase_duration --


@pytest.mark.parametrize("action,expected", [
    (0, (NS, 10)), (5, (NS, 90)), (6, (EW, 10)), (11, (EW, 90))])
def test_phase_duration_matches_the_environment(action, expected):
    """`traffic_env.step`: phase = action // len(greens),
    green = greens[action % len(greens)]. Same arithmetic, written twice, so a
    test is the only thing keeping them equal."""
    assert Decoder("phase_duration")._interpret(action, NS) == expected


def test_phase_duration_ignores_the_current_phase():
    """It names the target phase outright, unlike keep_or_switch."""
    decoder = Decoder("phase_duration")
    assert decoder._interpret(0, NS) == decoder._interpret(0, EW)


# ------------------------------------------------------------- discovery --


def test_discovery_does_not_recurse_into_the_archive(tmp_path):
    """P74 archived twelve checkpoints of unknown training length precisely so a
    benchmark could not pick them up. Recursing would undo that in one line."""
    (tmp_path / "good.zip").write_bytes(b"x")
    archive = tmp_path / "_pre_p47"
    archive.mkdir()
    (archive / "unknown.zip").write_bytes(b"x")
    found = [p.name for p in discover_checkpoints(tmp_path)]
    assert found == ["good.zip"]


# ---------------------------------------------------------- integration --


def test_the_real_checkpoint_loads_and_decides():
    found = discover_checkpoints()
    if not found:
        pytest.skip("no PPO checkpoint on disk")
    from simulation.ppo_controller import PPOController

    controller = PPOController(found[0], action_space="keep_or_switch")
    phase, green = controller.decide({
        "counts": {"N": 12, "S": 3, "E": 20, "W": 1},
        "queues": {"N": 8, "S": 1, "E": 15, "W": 0},
        "waits": {}, "phase": NS, "step": 5, "green_elapsed": 5})
    assert phase in (NS, EW)
    assert green == controller.decision_interval_s


def test_the_observation_is_built_from_the_spec_not_a_literal():
    found = discover_checkpoints()
    if not found:
        pytest.skip("no PPO checkpoint on disk")
    from simulation.ppo_controller import PPOController

    controller = PPOController(found[0], action_space="keep_or_switch")
    vector = controller.observe({
        "counts": {"N": 50, "S": 0, "E": 0, "W": 0},
        "queues": {"N": 0, "S": 0, "E": 0, "W": 0},
        "waits": {}, "phase": NS, "step": 0, "green_elapsed": 0})
    assert len(vector) == controller.dim
    assert vector[controller.index["count_N"]] == pytest.approx(1.0)
    assert vector[controller.index["phase_NS"]] == 1.0
    # P53: forecast indices are zeroed for the no-forecast arm.
    for approach in ("N", "S", "E", "W"):
        assert vector[controller.index[f"mfst_pred_{approach}"]] == 0.0


def test_keep_or_switch_phase_remaining_matches_the_environment():
    """P120: index 10 is built as TrafficSignalEnv builds it, and never silently 0."""
    found = discover_checkpoints()
    if not found:
        pytest.skip("no PPO checkpoint on disk")
    from simulation.ppo_controller import PPOController

    controller = PPOController(found[0], action_space="keep_or_switch")
    base = {"counts": {a: 1 for a in "NSEW"}, "queues": {a: 0 for a in "NSEW"},
            "waits": {}, "phase": NS}
    div = controller.norm["phase_remaining_divisor"]
    at = lambda step, g: controller.observe({**base, "step": step, "green_elapsed": g})[  # noqa: E731
        controller.index["phase_remaining"]]
    assert at(0, 0) == pytest.approx(10 / div)          # the environment's reset value
    assert at(25, 15) == pytest.approx(75 / div)
    assert at(200, 90) == 0.0
    with pytest.raises(ValueError):
        controller.observe({**base, "step": 5})         # elapsed missing: refused


def test_the_benchmark_now_offers_a_ppo_arm():
    """The docstring promised this before the code did."""
    found = discover_checkpoints()
    if not found:
        pytest.skip("no PPO checkpoint on disk")
    from scripts.benchmark import controllers

    assert any("forecast" in name for name in controllers())
