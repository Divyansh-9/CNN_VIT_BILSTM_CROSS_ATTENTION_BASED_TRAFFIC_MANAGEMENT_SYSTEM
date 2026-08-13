"""Tests for the SUMO network generator (S32, amendment A27).

Split by cost. The pure-arithmetic checks bind `NetworkSpec` to `spec.yaml` and
run everywhere; the ones that shell out to `netconvert` are skipped when SUMO is
absent, and run for real in CI.

    python -m pytest tests/test_sumo_network.py -q
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

from scripts.build_sumo_network import (  # noqa: E402
    NetworkSpec,
    green_phases,
    nodes_xml,
    edges_xml,
    vtypes_xml,
)

SPEC_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "mfstnet" / "configs" / "spec.yaml"
)


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def has_sumo() -> bool:
    try:
        from simulation.sumo_tools import sumo_binary

        sumo_binary("netconvert")
        return True
    except Exception:
        return False


needs_sumo = pytest.mark.skipif(not has_sumo(), reason="SUMO not installed")


# ------------------------------------------------- bound to the spec --

def test_signal_timings_match_the_spec(spec):
    """The network is the *implementation* of the signal spec. If it drifts,
    the Webster baseline and the PPO action space describe an intersection that
    is not the one being simulated."""
    net, sig = NetworkSpec(), spec["signal"]

    assert net.min_green_s == sig["min_green_s"]
    assert net.max_green_s == sig["max_green_s"]
    assert net.yellow_s == sig["yellow_s"]
    assert net.all_red_s == sig["all_red_s"]


def test_worst_red_matches_the_spec_and_is_99(spec):
    """A27. This was 96 s while `spec.yaml` had no yellow interval at all.

    An approach is red for the other phase's green **and its yellow**, plus both
    all-reds. Its own yellow does not count — traffic still discharges then.
    """
    assert NetworkSpec().worst_red_s == 99
    sig = spec["signal"]
    assert NetworkSpec().worst_red_s == (
        sig["max_green_s"] + sig["yellow_s"] + 2 * sig["all_red_s"]
    )


def test_worst_red_stays_below_the_starvation_threshold(spec):
    """FR-R04's penalty must not fire on legal operation. 99 < 180 — but the
    margin shrank by 3 s when yellow was added, so it is asserted rather than
    assumed."""
    assert NetworkSpec().worst_red_s < spec["signal"]["starvation_s"]


def test_max_cycle_matches_the_spec_clamp_ceiling(spec):
    """ADR-011 clamps Webster's computed cycle into [min, max]. A ceiling below
    the cycle the network can actually produce would clamp *every* cycle and
    make the reported clamp rate meaningless."""
    assert NetworkSpec().max_cycle_s == spec["signal"]["max_cycle_s"] == 192


def test_approach_width_stays_above_the_irc_validity_floor():
    """ADR-012's sweep uses S = k x W, and IRC:SP-41-1994 states 525W is valid
    only above 5.5 m. Below that a different formula applies and the sweep
    would silently compare two of them."""
    assert NetworkSpec().approach_width_m > 5.5


def test_lateral_resolution_is_set():
    """ADR-010. Without it the simulation is lane-disciplined, which is not the
    traffic this project is about."""
    assert NetworkSpec().lateral_resolution_m > 0


# ------------------------------------------------------ generated XML --

def test_all_four_approaches_are_generated():
    nodes = nodes_xml(NetworkSpec())
    for approach in ("N", "S", "E", "W"):
        assert f'id="{approach}"' in nodes
    assert 'type="traffic_light"' in nodes


def test_edge_ids_follow_the_state_vector_convention():
    """Lane ids derive from these, and the 16-dim PPO state indexes by lane
    (PRD §13.1, FR-M14). Renaming an edge silently reorders the state vector."""
    edges = edges_xml(NetworkSpec())
    for approach in ("N", "S", "E", "W"):
        assert f'id="{approach}2C"' in edges     # inbound
        assert f'id="C2{approach}"' in edges     # outbound


def test_vtype_distribution_sums_to_one():
    """A distribution that does not sum to 1 is renormalised silently by SUMO,
    so the mix would differ from PRD §12.2 with nothing to show for it."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(vtypes_xml())
    dist = root.find(".//vTypeDistribution")
    total = sum(float(v.get("probability")) for v in dist.findall("vType"))
    assert total == pytest.approx(1.0)


def test_two_wheelers_can_filter():
    """The defining behaviour of the modelled traffic. Without `latAlignment`
    and `lcSublane` the vehicle mix is cosmetic — different lengths queueing in
    single file."""
    xml = vtypes_xml()
    assert 'id="motorcycle"' in xml
    assert 'latAlignment="arbitrary"' in xml
    assert "lcSublane" in xml


def test_pedestrians_and_cattle_are_absent_and_that_is_deliberate():
    """PRD §12.2 lists 8 detection classes; two are not SUMO vehicles. Saying so
    in the file beats a silent omission a reader has to notice."""
    xml = vtypes_xml()
    assert 'id="pedestrian"' not in xml and 'id="cattle"' not in xml
    assert "out of scope" in xml


# --------------------------------------------------- needs netconvert --

@needs_sumo
def test_netconvert_produces_a_usable_network(tmp_path):
    from scripts.build_sumo_network import build

    info = build(NetworkSpec(), tmp_path)
    assert info["net"].exists()
    assert info["links"] > 0


@needs_sumo
def test_exactly_two_green_phases(tmp_path):
    """PRD §13.1's action space is 12 discrete = 2 phases x 6 durations. A third
    phase — netconvert adds a protected-left stage by default — makes the action
    space wrong and every trained checkpoint invalid."""
    from scripts.build_sumo_network import build

    info = build(NetworkSpec(), tmp_path)
    assert len(green_phases(info["program"])) == 2


@needs_sumo
def test_every_green_is_separated_by_yellow_and_all_red(tmp_path):
    """FR-A04. A green following a green with no clearance is a collision."""
    from scripts.build_sumo_network import build

    program = build(NetworkSpec(), tmp_path)["program"]
    kinds = [
        "green" if ("G" in s or "g" in s) else ("yellow" if "y" in s else "red")
        for _, s in program
    ]
    assert kinds == ["green", "yellow", "red", "green", "yellow", "red"]


@needs_sumo
def test_the_network_is_regenerated_identically(tmp_path):
    """NFR-08. The committed network must be reproducible from the script, or
    it is a hand-edited artifact nobody can verify."""
    from scripts.build_sumo_network import build

    # Same output directory both times. Two different directories would differ
    # only in the input paths netconvert records in its header, which is not the
    # property under test.
    out = tmp_path / "net"
    first = build(NetworkSpec(), out)["net"].read_text(encoding="utf-8")
    second = build(NetworkSpec(), out)["net"].read_text(encoding="utf-8")
    assert first == second
