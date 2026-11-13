"""Pilot for the lane-discipline sweep (ADR-024).

The sweep's question is what lane indiscipline costs in delay, holding demand
and geometry fixed. Before that question can be asked, one thing has to be
established: **does the discipline parameter actually change how vehicles
behave?** A sweep over a knob that moves nothing produces a flat line and an
author who believes it means indiscipline is free.

So this is a manipulation check, not a result. It varies the discipline
parameter, measures the *behaviour* it is supposed to change, and reports
whether the change is monotone and separated. The effect on delay is recorded
alongside, and is explicitly not the point: three seeds at a short horizon
cannot estimate it, and the gate below says so.

    python scripts/discipline_pilot.py --seeds 42 1 7

Three design decisions that are not obvious, and that the sweep inherits.

**Demand is pre-expanded, not re-sampled.** Passing the same ``--seed`` to SUMO
under two different lateral configurations does *not* guarantee the same
vehicles: changing behaviour changes how the simulation consumes its random
stream, so departure times and type draws can diverge and the comparison stops
being paired. The flows are therefore expanded once into explicit ``<vehicle>``
elements — fixed id, type and departure — and that one file is handed to every
condition. Identical demand becomes a property of the input rather than a hope
about the generator.

**Completion is a gate, not a metric.** ``--time-to-teleport -1`` means a
gridlocked vehicle never leaves. Mean delay is then computed over the vehicles
that *finished*, which are the lucky ones, and it can **fall** as conditions get
worse. Throughput and `arrived_fraction` are what catch that, and a condition
below `MIN_ARRIVED` is reported as disqualified rather than compared.

**Delay per vehicle is the wrong headline for this project** and is reported
here only because the pilot reuses `run_episode` unchanged. ADR-017's whole
premise is that counting a bus and a two-wheeler alike measures the wrong
thing; the full sweep needs delay per passenger-car unit and per mode, which
needs `_read_tripinfo` to return per-type means. Recorded as owed, not done.
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts import build_sumo_demand as demand  # noqa: E402
from experiments.provenance import write_sidecar  # noqa: E402
from simulation.runner import run_episode  # noqa: E402
from simulation.webster import Webster  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NET_DIR = ROOT / "simulation" / "networks"
SCRATCH = ROOT / "data" / "_discipline"
OUT = ROOT / "experiments" / "results" / "discipline_pilot.csv"

#: The only Webster configuration that qualified under ADR-012 rev 2. Using
#: anything else would compare indiscipline against a baseline the project has
#: already disqualified.
WEBSTER_SATURATION = 750

#: The discipline levels the pilot checks. 0 is the stream the project targets;
#: 1 is lane-disciplined traffic of the kind the foreign benchmarks contain.
#: Three points is enough to see whether the knob moves anything and whether it
#: moves monotonically; the sweep refines the grid.
LEVELS = (0.0, 1.0)

#: Discipline is realised by the sublane model, not by the vehicle types.
#: Measured 2026-10-14 at 600 s, seed 42, saturated: with the sublane model
#: disabled the mean lateral offset is **exactly 0.0 m** and the vType
#: discipline attributes change nothing at all (d=0 and d=1 gave identical
#: 14.19 s wait, 0.882 arrived). With it enabled, varying those attributes
#: moved the offset 0.504 to 0.482 m — a 4% separation against a 50% gate.
#:
#: Sweeping --lateral-resolution instead does not rescue it: 0.2/0.4/0.8/1.6
#: gave offsets 0.5756/0.5066/0.5040/0.5453 m, which is not monotone, while
#: wait ranged 10.76 to 18.22 s at one seed. The delay spread across conditions
#: with near-identical lateral behaviour is larger than any plausible effect,
#: which is seed noise and is what the 30-seed protocol exists for.
#:
#: So the honest intervention is binary, and it is the one ADR-010 already
#: declares: the sublane model on against off.
SUBLANE_RESOLUTION = 0.8

#: Pre-registered gates. Declared here, before the runs, for the same reason
#: ADR-022 pre-registers its threshold: a criterion chosen after seeing the
#: numbers is not a criterion.
#:
#: `MIN_ARRIVED` — below this fraction of vehicles completing, the scenario has
#: gridlocked and its delay is a survivorship artefact, not a measurement.
MIN_ARRIVED = 0.85

#: `MIN_SEPARATION_M` — the mean lateral offset at d=0 must exceed that at d=1
#: by at least this many metres. An absolute gate rather than a ratio, because
#: the disciplined arm measures exactly 0.0 m and a ratio against zero is not a
#: number.
MIN_SEPARATION_M = 0.25

#: Vehicle types whose lateral behaviour the parameter is defined to control.
#: Cars, buses and trucks keep SUMO's defaults at every level — a bus does not
#: filter — so they are excluded from the separation check rather than diluting
#: it.
FILTERING_TYPES = ("motorcycle", "auto_rickshaw", "e_rickshaw")


def lerp(low: float, high: float, fraction: float) -> float:
    return low + (high - low) * fraction


def vtypes_xml(discipline: float) -> str:
    """The vehicle types at a given discipline level.

    Three attributes carry the behaviour, and they are the ones ADR-010 already
    set by hand for the heterogeneous case:

    ``latAlignment``  where in the lane a vehicle sits — ``arbitrary`` lets it
                      sit anywhere, ``center`` pins it to the lane centre.
    ``lcSublane``     eagerness to change lateral position for a speed gain.
    ``minGapLat``     lateral clearance kept from a neighbour; small values are
                      what permit two two-wheelers abreast in one lane.

    At ``discipline=0`` these reproduce `simulation/networks/vtypes.add.xml`
    exactly, so the sweep's lower end is the project's existing configuration
    rather than a new one.
    """
    if not 0.0 <= discipline <= 1.0:
        raise ValueError(f"discipline must be in [0, 1], got {discipline}")

    align = "center" if discipline >= 1.0 else "arbitrary"
    # Entering in lane IS discipline, so it belongs to the intervention. It is
    # set on the vType rather than on the vehicle because the demand file is
    # shared across conditions and must stay byte-identical.
    enter = "center" if discipline >= 0.5 else "random"
    rows = []
    for name, vclass, length, width, accel, decel, speed, sub0, gap0 in (
            ("motorcycle", "motorcycle", 2.0, 0.8, 3.0, 5.0, 16, 1.0, 0.2),
            ("auto_rickshaw", "passenger", 2.6, 1.4, 2.0, 4.0, 14, 0.8, 0.3),
            ("e_rickshaw", "passenger", 2.8, 1.4, 1.6, 4.0, 11, 0.8, 0.3)):
        rows.append(
            f'    <vType id="{name}" vClass="{vclass}" length="{length}" '
            f'width="{width}" accel="{accel}" decel="{decel}" '
            f'maxSpeed="{speed}" latAlignment="{align}" '
            f'departPosLat="{enter}" '
            # Not driven to zero: lcSublane is the willingness to move
            # laterally at all, and a vehicle with none cannot steer back to
            # the centre its latAlignment asks for. The first pilot set it to
            # 0 at full discipline and measured a 1.04x separation because of
            # exactly that.
            f'lcSublane="{lerp(sub0, 0.3, discipline):.3f}" '
            f'minGapLat="{lerp(gap0, 0.6, discipline):.3f}"/>')

    # Unchanged across levels: these never filtered, and varying them would
    # confound the intervention with a change to vehicles it does not describe.
    rows += [
        '    <vType id="car" vClass="passenger" length="4.3" width="1.8"'
        ' accel="2.6" decel="4.5" maxSpeed="20"/>',
        '    <vType id="bus" vClass="bus" length="12.0" width="2.5"'
        ' accel="1.2" decel="4.0" maxSpeed="16"/>',
        '    <vType id="truck" vClass="truck" length="7.1" width="2.4"'
        ' accel="1.3" decel="4.0" maxSpeed="16"/>',
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<!-- GENERATED by scripts/discipline_pilot.py at discipline="
        f"{discipline:.2f} — do not edit. ADR-024. -->\n"
        "<additional>\n" + "\n".join(rows) + "\n"
        '    <vTypeDistribution id="india_mix"\n'
        '        vTypes="car motorcycle auto_rickshaw e_rickshaw truck bus"\n'
        '        probabilities="0.38 0.33 0.16 0.05 0.05 0.03"/>\n'
        "</additional>\n")


def fixed_demand(regime: str, seed: int, duration_s: int) -> str:
    """Flows expanded into explicit vehicles, so every condition gets the same.

    SUMO expands a ``<flow>`` itself, drawing departure times and — through a
    ``vTypeDistribution`` — vehicle types from its own random stream. Two runs
    that differ in lateral behaviour consume that stream differently, so the
    same ``--seed`` does not imply the same traffic. Expanding here, once,
    removes the question.
    """
    import random

    regime_spec = demand.REGIMES[regime]
    rng = random.Random(seed)
    kinds = ["car", "motorcycle", "auto_rickshaw", "e_rickshaw", "truck", "bus"]
    weights = [0.38, 0.33, 0.16, 0.05, 0.05, 0.03]

    rows = ['<?xml version="1.0" encoding="UTF-8"?>',
            "<!-- GENERATED by scripts/discipline_pilot.py — do not edit.",
            f"     Pre-expanded so every discipline level sees identical",
            f"     demand. regime={regime} seed={seed} -->",
            "<routes>"]
    for origin in demand.APPROACHES:
        destinations = {"straight": demand.OPPOSITE[origin],
                        "right": demand.RIGHT_OF[origin],
                        "left": demand.LEFT_OF[origin]}
        for movement, destination in destinations.items():
            rows.append(f'    <route id="r_{origin}_{movement}" '
                        f'edges="{origin}2C C2{destination}"/>')
    rows.append("")

    vehicles = []
    for origin in demand.APPROACHES:
        for movement, share in demand.TURN_RATIOS.items():
            per_hour = regime_spec.veh_per_hour_per_approach * share
            count = int(round(per_hour * duration_s / 3600))
            for index in range(count):
                # Even spacing plus jitter: a deterministic stream that is not
                # a metronome. The jitter is drawn here, once, not by SUMO.
                base = (index + 0.5) * duration_s / max(count, 1)
                depart = max(0.0, base + rng.uniform(-0.4, 0.4)
                             * duration_s / max(count, 1))
                vehicles.append((depart, origin, movement, index,
                                 rng.choices(kinds, weights)[0]))

    for depart, origin, movement, index, kind in sorted(vehicles):
        rows.append(
            f'    <vehicle id="v_{origin}_{movement}_{index}" '
            f'type="{kind}" route="r_{origin}_{movement}" '
            f'depart="{depart:.2f}" departLane="free" '
            f'departSpeed="max"/>')
    rows.append("</routes>")
    return "\n".join(rows) + "\n"


def condition_dir(discipline: float, regime: str, demand_xml: str) -> Path:
    """A network directory for one condition: same network, same demand."""
    path = SCRATCH / f"d{discipline:.2f}"
    path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(NET_DIR / "intersection.net.xml", path / "intersection.net.xml")
    (path / "vtypes.add.xml").write_text(vtypes_xml(discipline), encoding="utf-8")
    (path / f"demand_{regime}.rou.xml").write_text(demand_xml, encoding="utf-8")
    return path


@dataclass
class Row:
    discipline: float
    seed: int
    regime: str
    lateral_mean_m: float
    mean_wait_s: float
    mean_queue: float
    throughput: int
    arrived_fraction: float

    @property
    def disqualified(self) -> bool:
        return self.arrived_fraction < MIN_ARRIVED


def lateral_mean(extra: dict) -> float:
    """Mean lateral offset across the types the parameter actually controls."""
    values = [extra[f"lat_mean_{kind}"] for kind in FILTERING_TYPES
              if f"lat_mean_{kind}" in extra]
    return round(statistics.mean(values), 4) if values else float("nan")


def pilot(seeds, regime: str, duration_s: int) -> list[Row]:
    rows: list[Row] = []
    for seed in seeds:
        demand_xml = fixed_demand(regime, seed, duration_s)
        for discipline in LEVELS:
            net = condition_dir(discipline, regime, demand_xml)
            result = run_episode(
                Webster(saturation_flow_per_metre=WEBSTER_SATURATION),
                net_dir=net, regime=regime, seed=seed,
                duration_s=duration_s, collect_lateral=True,
                lateral_resolution=None if discipline >= 1.0
                else SUBLANE_RESOLUTION)
            rows.append(Row(
                discipline=discipline, seed=seed, regime=regime,
                lateral_mean_m=lateral_mean(result.extra),
                mean_wait_s=round(result.mean_wait_s, 3),
                mean_queue=round(result.mean_queue, 3),
                throughput=result.throughput,
                arrived_fraction=round(result.arrived_fraction, 4)))
            last = rows[-1]
            flag = "  DISQUALIFIED" if last.disqualified else ""
            print(f"    d={discipline:.2f} seed={seed:<3} "
                  f"lateral={last.lateral_mean_m:.4f} m  "
                  f"wait={last.mean_wait_s:7.2f} s  "
                  f"arrived={last.arrived_fraction:.3f}{flag}")
    return rows


def verdict(rows: list[Row]) -> tuple[bool, list[str]]:
    """Does the parameter change behaviour, monotonically and separably?"""
    notes: list[str] = []
    by_level = {level: [r.lateral_mean_m for r in rows if r.discipline == level]
                for level in LEVELS}
    means = {level: statistics.mean(values) for level, values in by_level.items()
             if values}

    ordered = [means[level] for level in sorted(means, reverse=True)]
    monotone = all(a <= b for a, b in zip(ordered, ordered[1:]))
    notes.append(
        "lateral spread falls monotonically as discipline rises"
        if monotone else
        "lateral spread is NOT monotone in discipline — "
        f"{ {k: round(v, 4) for k, v in means.items()} }")

    low, high = means.get(0.0), means.get(1.0)
    separated = low is not None and high is not None and (low - high) >= MIN_SEPARATION_M
    if low is not None and high is not None:
        notes.append(
            f"d=0 spread {low:.4f} m against d=1 {high:.4f} m, "
            f"difference {low - high:.4f} m "
            f"(gate {MIN_SEPARATION_M} m) — "
            f"{'separated' if separated else 'NOT separated'}")

    bad = [r for r in rows if r.disqualified]
    if bad:
        notes.append(
            f"{len(bad)} of {len(rows)} runs below {MIN_ARRIVED:.0%} completion "
            "and disqualified; their delay is survivorship, not performance")
    else:
        notes.append(f"every run completed at or above {MIN_ARRIVED:.0%}")

    return monotone and separated and not bad, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 7])
    parser.add_argument("--regime", default="saturated",
                        choices=sorted(demand.REGIMES))
    parser.add_argument("--duration", type=int, default=900,
                        help="episode length in seconds; the pilot is short "
                             "on purpose and the sweep is not")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    print(f"\n  lane-discipline pilot  ·  regime {args.regime}  ·  "
          f"{args.duration} s  ·  seeds {args.seeds}")
    print(f"  manipulation check: does discipline change lateral behaviour?\n")

    rows = pilot(args.seeds, args.regime, args.duration)

    import csv
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["discipline", "seed", "regime", "lateral_mean_m",
                         "mean_wait_s", "mean_queue", "throughput",
                         "arrived_fraction", "disqualified"])
        for row in rows:
            writer.writerow([row.discipline, row.seed, row.regime,
                             row.lateral_mean_m, row.mean_wait_s,
                             row.mean_queue, row.throughput,
                             row.arrived_fraction, row.disqualified])

    # Provenance beside the result, per the project convention: device, config
    # and run length live in the sidecar and never as new CSV columns.
    from simulation.sumo_tools import sumo_version

    sidecar = write_sidecar(
        args.out, experiment="lane-discipline pilot (ADR-024)",
        sumo_version=sumo_version(), regime=args.regime,
        duration_s=args.duration, seeds=list(args.seeds),
        levels=list(LEVELS), sublane_resolution=SUBLANE_RESOLUTION,
        webster_saturation=WEBSTER_SATURATION, min_arrived=MIN_ARRIVED,
        min_separation_m=MIN_SEPARATION_M,
        demand="pre-expanded to explicit vehicles; identical across levels")

    passed, notes = verdict(rows)
    print(f"\n  wrote {args.out.relative_to(ROOT)}")
    print(f"  wrote {sidecar.relative_to(ROOT)}")
    for note in notes:
        print(f"    {note}")
    print(f"\n  {'PASS' if passed else 'FAIL'}  the discipline parameter "
          f"{'changes' if passed else 'does not demonstrably change'} "
          "vehicle behaviour.")
    if passed:
        print("  A two-arm capacity contrast may be built on it; the graded "
              "sweep may not,\n  because there is no gradient (ADR-024). "
              "Delay is NOT estimated here, and the\n  measured sign is a "
              "capacity effect in a simulator with no collision model —\n  "
              "never a case for or against lane discipline. These seeds "
              "does that.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
