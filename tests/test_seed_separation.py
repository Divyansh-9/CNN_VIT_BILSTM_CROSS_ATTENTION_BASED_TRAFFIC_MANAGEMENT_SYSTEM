"""P129: the demand a training run actually sees never touches a reserved seed.

This checks the SUMO seeds **actually used** by the real training construction
path (`train_ppo.build_model`), including SB3's seeded first reset. That reset
is what made episode 0 run on the training seed itself. A test of the
configured seed rule alone would have missed it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("traci")
pytest.importorskip("stable_baselines3")

from scripts.ceiling_eval import PRIMARY_SEEDS, TRAINING_SEEDS  # noqa: E402
from scripts.train_ppo import build_model, load_config  # noqa: E402
from simulation.forecast_producer import NoForecast  # noqa: E402

RESERVED = {
    "primary evaluation": set(PRIMARY_SEEDS),
    "qualification and requalification": set(range(200, 260)),
    "design": set(range(300, 310)),
    "Webster and fixed-cycle tuning": set(range(400, 420)),
}


@pytest.mark.parametrize("seed", TRAINING_SEEDS)
def test_actual_training_demand_seeds_avoid_every_reserved_set(seed):
    model, audited = build_model(load_config(), "no-forecast", regime="pulsed", seed=seed,
                                 episode_s=30, action_space="keep_or_switch",
                                 producer=NoForecast())
    vec = model.get_env()
    try:
        for _ in range(3):                                   # the first is SB3's seeded reset
            vec.reset()
        used = list(audited.unwrapped.run_seeds)
    finally:
        vec.close()
    assert used[0] == seed                                   # P129: episode 0 = training seed
    assert used[1:] == [1_000_000 + 10_000 * seed + e for e in (1, 2)]
    for name, reserved in RESERVED.items():
        assert not set(used) & reserved, f"training seed {seed} used {name} seeds"
