"""The observation contract must be hashed, recorded, and enforced (P52).

`traffic_env` already refuses to build if `spec.yaml`'s `dim` disagrees with its
own `STATE_DIM`. That catches a length change. The change that costs more keeps
the length: swap two entries in the index map, or halve a divisor, and every
shape still matches while index 11 stops meaning what it meant when the policy
learned to read it.

These pin the digest's *sensitivity* -- what it must notice -- rather than its
value, because the value changes legitimately whenever the contract is amended
and a test asserting a literal digest would just be updated in the same commit
as the mistake it was meant to catch.
"""

from __future__ import annotations

import copy

import pytest

from simulation.contract import (
    assert_contract_matches,
    contract_digest,
    contract_fields,
)


@pytest.fixture
def spec():
    import yaml

    from simulation.contract import SPEC

    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def test_the_live_spec_hashes(spec):
    assert len(contract_digest(spec)) == 16


def test_the_digest_is_stable_across_calls(spec):
    assert contract_digest(spec) == contract_digest(spec)


def test_key_order_does_not_change_the_digest(spec):
    """PyYAML mapping order must not leak into a reproducibility artifact."""
    shuffled = copy.deepcopy(spec)
    state = shuffled["ppo_state"]
    state["index_map"] = dict(reversed(list(state["index_map"].items())))
    state["normalisers"] = dict(reversed(list(state["normalisers"].items())))
    assert contract_digest(shuffled) == contract_digest(spec)


def test_permuting_two_indices_changes_the_digest(spec):
    """The silent case. Same length, same dtype, different world."""
    moved = copy.deepcopy(spec)
    index = moved["ppo_state"]["index_map"]
    index["mfst_pred_N"], index["mfst_pred_S"] = (
        index["mfst_pred_S"], index["mfst_pred_N"])
    assert contract_digest(moved) != contract_digest(spec)


def test_changing_a_normaliser_changes_the_digest(spec):
    """`count / 50` and `count / 200` are different features at one index, and
    PRD §13.1 marks the divisors as due for revision at W10."""
    tuned = copy.deepcopy(spec)
    tuned["ppo_state"]["normalisers"]["count_divisor"] *= 4
    assert contract_digest(tuned) != contract_digest(spec)


def test_changing_the_fallback_operation_changes_the_digest(spec):
    """Which slots read "absent" without a forecast, and what the age reads, is
    part of what those numbers mean (ADR-020 as amended)."""
    changed = copy.deepcopy(spec)
    changed["ppo_state"]["forecast_unavailable"]["class_slots"] = [11, 12]
    assert contract_digest(changed) != contract_digest(spec)
    aged = copy.deepcopy(spec)
    aged["ppo_state"]["forecast_unavailable"]["age_value"] = 0.0
    assert contract_digest(aged) != contract_digest(spec)


def test_the_amended_layout_has_a_new_digest(spec):
    """P97a: the pre-ADR-020 checkpoint recorded 24ad1c994e844238. The amended
    layout must not share it, or that checkpoint would load against a state it
    never saw."""
    assert contract_digest(spec) != "24ad1c994e844238"


def test_changing_the_dimension_changes_the_digest(spec):
    grown = copy.deepcopy(spec)
    grown["ppo_state"]["dim"] += 1
    assert contract_digest(grown) != contract_digest(spec)


def test_an_unrelated_spec_section_does_not_change_the_digest(spec):
    """Only what decides the meaning of a state number is hashed. Hashing more
    would make the digest churn on edits that cannot invalidate a policy, and a
    guard that cries wolf gets bypassed."""
    other = copy.deepcopy(spec)
    other.setdefault("signal", {})["irrelevant_knob"] = 1234
    assert contract_digest(other) == contract_digest(spec)


def test_a_matching_digest_passes():
    assert_contract_matches(contract_digest(), what="a checkpoint")


def test_a_mismatched_digest_refuses_and_prints_both():
    with pytest.raises(SystemExit) as caught:
        assert_contract_matches("0" * 16, what="ppo_no-forecast_seed42.zip")
    message = str(caught.value)
    assert "0000000000000000" in message and contract_digest() in message


def test_an_absent_digest_refuses_rather_than_being_waved_through():
    """Every checkpoint written before P52 is in this state, which is exactly
    the condition that lets a policy be scored against a state it never saw."""
    with pytest.raises(SystemExit) as caught:
        assert_contract_matches(None, what="an old checkpoint")
    assert "records no observation contract" in str(caught.value)


def test_the_fields_hashed_are_the_ones_that_carry_meaning(spec):
    fields = contract_fields(spec)
    assert set(fields) == {
        "dim", "index_map", "normalisers", "forecast_unavailable"}


# ---------------------------------------------------------------------------
# assert_compatible: one call, because two checks are one an eval path forgets.


def write_checkpoint(tmp_path, *, digest=..., action_space="keep_or_switch"):
    import json

    from simulation.contract import contract_digest

    checkpoint = tmp_path / "ppo_no-forecast_saturated_seed42.zip"
    checkpoint.write_bytes(b"weights")
    payload = {"action_space": action_space,
               "observation_contract":
                   contract_digest() if digest is ... else digest}
    (tmp_path / (checkpoint.name + ".provenance.json")).write_text(
        json.dumps(payload), encoding="utf-8")
    return checkpoint


def test_a_matching_checkpoint_is_accepted(tmp_path):
    from simulation.contract import assert_compatible

    got = assert_compatible(write_checkpoint(tmp_path),
                            action_space="keep_or_switch")
    assert got["action_space"] == "keep_or_switch"


def test_the_wrong_action_space_refuses(tmp_path):
    """The digest passes and the observation length is right. ADR-015 keeps the
    action space out of the hash deliberately, so this is the level it has to
    be caught at instead."""
    from simulation.contract import assert_compatible

    with pytest.raises(SystemExit) as caught:
        assert_compatible(write_checkpoint(tmp_path, action_space="phase_duration"),
                          action_space="keep_or_switch")
    message = str(caught.value)
    assert "phase_duration" in message and "keep_or_switch" in message


def test_a_stale_observation_contract_refuses_before_the_action_space(tmp_path):
    from simulation.contract import assert_compatible

    with pytest.raises(SystemExit) as caught:
        assert_compatible(write_checkpoint(tmp_path, digest="0" * 16),
                          action_space="keep_or_switch")
    assert "observation contract" in str(caught.value)


def test_a_checkpoint_with_no_sidecar_at_all_refuses(tmp_path):
    from simulation.contract import assert_compatible

    orphan = tmp_path / "ppo_orphan_seed42.zip"
    orphan.write_bytes(b"weights")
    with pytest.raises(SystemExit):
        assert_compatible(orphan, action_space="keep_or_switch")


def test_train_ppo_writes_the_digest_it_trained_against():
    """The sidecar is only worth reading if the trainer fills it in."""
    import pathlib

    source = pathlib.Path("scripts/train_ppo.py").read_text(encoding="utf-8")
    assert '"observation_contract": contract_digest()' in source


def test_the_screen_checks_before_it_loads():
    """`assert_compatible` is only worth having if a load path calls it.

    `screen_action_space.py` resumes: it skips seeds an earlier run finished, so
    the checkpoint it loads was not necessarily written by the process about to
    score it. That is the case the guard exists for, and a guard nothing calls
    is documentation.
    """
    import pathlib

    source = pathlib.Path("scripts/screen_action_space.py").read_text(
        encoding="utf-8")
    assert "assert_compatible(" in source
    assert source.index("assert_compatible(") < source.index("PPO.load(")
