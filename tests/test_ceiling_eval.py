"""P128: the ceiling's decision rule, proved on synthetic data before any result exists."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ceiling_eval import BASELINES, EVAL_SEEDS, PPO_ARMS, TRAINING_SEEDS, analyse  # noqa: E402


def rows(delay: dict, *, arrived=0.95, starvation=None, transfer=0.95, noise=0.5,
         replicate_shift=None):
    """One row per arm x policy x evaluation seed, with the given mean delays."""
    rng = random.Random(1)
    out = []
    for seed in EVAL_SEEDS:
        base = 40 + rng.gauss(0, 3)                      # shared per-seed traffic
        for arm in PPO_ARMS:
            for policy in TRAINING_SEEDS:
                shift = (replicate_shift or {}).get((arm, policy), 0.0)
                out.append({"arm": arm, "policy": str(policy), "eval_seed": seed,
                            "mean_total_delay_s": base + delay[arm] + shift + rng.gauss(0, noise),
                            "arrived_fraction": arrived if arm == "oracle" else 0.95,
                            "starvation_events": (starvation or {}).get(arm, 0),
                            "acc_oracle_realised": transfer if arm != "no-forecast" else ""})
        for arm in BASELINES:
            out.append({"arm": arm, "policy": arm, "eval_seed": seed,
                        "mean_total_delay_s": base + delay.get(arm, 0.0) + rng.gauss(0, noise),
                        "arrived_fraction": 0.95, "starvation_events": 0})
    return out


def test_oracle_beating_both_clears_the_ceiling():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3}))["decision"]
    assert d["cleared"] and d["reading"].startswith("forecast information adds control value")
    assert any("upper bound" in q for q in d["qualifiers"])


def test_beating_no_forecast_only_is_an_input_channel_not_foresight():
    d = analyse(rows({"no-forecast": 0, "persistence": -3, "oracle": -3}))["decision"]
    assert not d["cleared"] and d["reading"].startswith("a forecast input channel helps")


def test_beating_neither_is_no_demonstrated_benefit():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": 0}))["decision"]
    assert not d["cleared"] and d["reading"].startswith("no demonstrated control benefit")


def test_a_significant_but_small_effect_does_not_count():
    # A huge n would make a tiny difference significant; d >= 0.5 is still required.
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -0.15}, noise=0.5))["decision"]
    assert not d["cleared"]


def test_the_operational_gate_can_block_a_delay_win():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3}, arrived=0.80))["decision"]
    assert not d["cleared"] and "operational gate fails" in d["reading"]


def test_more_starvation_blocks_the_ceiling():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3},
                     starvation={"oracle": 3, "no-forecast": 0}))["decision"]
    assert not d["cleared"]


def test_a_reversing_replicate_is_reported_as_fragile():
    from scripts.ceiling_eval import decide

    win = {"holm_significant": True, "mean_diff": -3.0, "d": -1.2, "p": 1e-6}
    d = decide({"oracle_vs_no_forecast": dict(win), "oracle_vs_persistence": dict(win)},
               {"passed": True}, 0.95,
               {"42": {"vs_no_forecast": -4.0, "vs_persistence": -4.0},
                "1": {"vs_no_forecast": -4.0, "vs_persistence": -4.0},
                "7": {"vs_no_forecast": +1.0, "vs_persistence": -1.0}})
    assert d["cleared"] and any(q.startswith("fragile") for q in d["qualifiers"])


def test_weak_oracle_transfer_is_qualified():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3}, transfer=0.7))["decision"]
    assert any(q.startswith("oracle transfer weak") for q in d["qualifiers"])


def test_harm_is_named():
    d = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": +3}))["decision"]
    assert not d["cleared"] and any("WORSE" in q for q in d["qualifiers"])


def test_a_missing_episode_breaks_the_pairing_rather_than_being_dropped():
    data = [r for r in rows({"no-forecast": 0, "persistence": 0, "oracle": -3})
            if not (r["arm"] == "oracle" and r["eval_seed"] == 8)]
    with pytest.raises(ValueError, match="pairing is broken"):
        analyse(data)


def test_every_baseline_and_both_primary_tests_are_reported():
    result = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3}))
    assert set(result["primary"]) == {"oracle_vs_no_forecast", "oracle_vs_persistence"}
    assert all("holm_significant" in e for e in result["primary"].values())
    assert len(result["secondary_descriptive_unadjusted"]) == len(PPO_ARMS) * len(BASELINES)
    assert set(result["arms"]) == set(PPO_ARMS) | set(BASELINES)


def test_the_primary_analysis_uses_exactly_the_28_uncontaminated_seeds():
    """P128 Amendment 1: {0..29} minus {1, 7}; the statistics are computed on 28 pairs."""
    from scripts.ceiling_eval import PRIMARY_SEEDS

    assert set(PRIMARY_SEEDS) == set(range(30)) - {1, 7}
    result = analyse(rows({"no-forecast": 0, "persistence": 0, "oracle": -3}))
    assert result["primary_evaluation_seeds"] == list(PRIMARY_SEEDS)
    assert all(e["n"] == 28 for e in result["primary"].values())
    sens = result["sensitivity_all_30_seeds_CONTAMINATED"]
    assert all(e["n"] == 30 for e in sens["primary"].values()) and "Secondary" in sens["note"]


def test_the_contaminated_seeds_cannot_carry_the_decision():
    """A large oracle gain on seeds 1 and 7 alone must not clear the ceiling."""
    data = rows({"no-forecast": 0, "persistence": 0, "oracle": 0})
    for r in data:
        if r["arm"] == "oracle" and r["eval_seed"] in (1, 7):
            r["mean_total_delay_s"] -= 60.0
    result = analyse(data)
    assert not result["decision"]["cleared"]
    assert result["decision"]["reading"].startswith("no demonstrated control benefit")
