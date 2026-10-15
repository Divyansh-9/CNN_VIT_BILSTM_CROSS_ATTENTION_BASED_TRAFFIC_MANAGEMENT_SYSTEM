"""The lane-discipline pilot's gates and its paired-demand guarantee (ADR-024).

The pilot's value is entirely in refusing things, so the refusals are what is
pinned here. Nothing below starts SUMO: these are the pure functions that
decide whether a run is comparable and whether a manipulation happened.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import discipline_pilot as D  # noqa: E402


def row(discipline: float, seed: int, lateral: float, *,
        arrived: float = 0.92) -> D.Row:
    return D.Row(discipline=discipline, seed=seed, regime="saturated",
                 lateral_mean_m=lateral, mean_wait_s=14.0, mean_queue=9.0,
                 throughput=690, arrived_fraction=arrived)


# --------------------------------------------------------------------------
#  identical demand across conditions
# --------------------------------------------------------------------------

def test_demand_is_identical_for_the_same_seed():
    """The whole comparison is paired, so this is load-bearing rather than
    cosmetic: the same seed must yield byte-identical traffic."""
    assert D.fixed_demand("saturated", 42, 600) == D.fixed_demand(
        "saturated", 42, 600)


def test_demand_differs_between_seeds():
    assert D.fixed_demand("saturated", 42, 600) != D.fixed_demand(
        "saturated", 1, 600)


def test_demand_carries_no_lateral_entry_position():
    """`departPosLat` is part of the intervention and lives on the vType, so a
    shared demand file must not pin it — otherwise the conditions differ in
    their input and the pairing is broken."""
    assert "departPosLat" not in D.fixed_demand("saturated", 42, 600)


def test_demand_is_expanded_to_explicit_vehicles():
    """A `<flow>` is expanded by SUMO from its own random stream, which two
    conditions consume differently. Explicit vehicles remove the question."""
    text = D.fixed_demand("saturated", 42, 600)
    assert "<flow " not in text
    assert text.count("<vehicle ") > 100


# --------------------------------------------------------------------------
#  the discipline parameter
# --------------------------------------------------------------------------

def test_vtypes_are_centred_only_at_full_discipline():
    assert 'latAlignment="arbitrary"' in D.vtypes_xml(0.0)
    assert 'latAlignment="center"' in D.vtypes_xml(1.0)


def test_vtypes_reject_a_discipline_outside_the_unit_interval():
    with pytest.raises(ValueError, match=r"must be in \[0, 1\]"):
        D.vtypes_xml(1.5)


def test_lcsublane_is_not_driven_to_zero():
    """A vehicle with no lateral eagerness cannot steer back to the centre its
    `latAlignment` asks for. The first pilot set it to 0 at full discipline and
    measured a 1.04x separation because of exactly that."""
    for line in D.vtypes_xml(1.0).splitlines():
        if "lcSublane=" in line:
            value = float(line.split('lcSublane="')[1].split('"')[0])
            assert value > 0.0, line


def test_the_heavy_vehicles_are_untouched_by_the_intervention():
    """Varying vehicles that never filtered would confound the manipulation
    with a change to classes it does not describe."""
    for discipline in (0.0, 1.0):
        text = D.vtypes_xml(discipline)
        heavy = [l for l in text.splitlines() if 'id="bus"' in l or 'id="truck"' in l]
        assert heavy and not any("latAlignment" in line for line in heavy)


# --------------------------------------------------------------------------
#  the gates
# --------------------------------------------------------------------------

def test_a_separated_monotone_run_passes():
    rows = [row(0.0, s, 0.48) for s in (42, 1, 7)]
    rows += [row(1.0, s, 0.0) for s in (42, 1, 7)]
    passed, notes = D.verdict(rows)
    assert passed, notes


def test_an_unseparated_run_fails():
    """The measured first attempt: monotone, but 0.504 against 0.482 m."""
    rows = [row(0.0, s, 0.504) for s in (42, 1, 7)]
    rows += [row(1.0, s, 0.482) for s in (42, 1, 7)]
    passed, notes = D.verdict(rows)
    assert not passed
    assert any("NOT separated" in note for note in notes)


def test_a_non_monotone_run_fails():
    rows = [row(0.0, s, 0.48) for s in (42, 1)]
    rows += [row(1.0, s, 0.52) for s in (42, 1)]
    passed, notes = D.verdict(rows)
    assert not passed
    assert any("NOT monotone" in note for note in notes)


def test_a_gridlocked_run_is_disqualified_not_compared():
    """With `--time-to-teleport -1` a gridlocked vehicle never leaves, so mean
    delay is computed over the lucky ones and can FALL as conditions worsen.
    Completion is the gate that catches it."""
    rows = [row(0.0, 42, 0.48, arrived=0.50), row(1.0, 42, 0.0)]
    assert rows[0].disqualified and not rows[1].disqualified
    passed, notes = D.verdict(rows)
    assert not passed
    assert any("survivorship" in note for note in notes)


def test_the_separation_gate_is_absolute_not_a_ratio():
    """The disciplined arm measures exactly 0.0 m, and a ratio against zero is
    not a number."""
    assert D.MIN_SEPARATION_M > 0
    rows = [row(0.0, 42, D.MIN_SEPARATION_M + 0.01), row(1.0, 42, 0.0)]
    assert D.verdict(rows)[0]
