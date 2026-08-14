"""Run one SUMO episode under a controller and measure it (S34, FR-R08).

One runner serves every method the benchmark compares — fixed-time, Webster, and
later PPO — because a comparison in which each arm has its own measurement code
is a comparison of measurement code. The controller is the only thing that
varies, and it varies through a two-method protocol.

Metrics follow PRD §14.3: mean wait, mean queue, throughput, and the clamp and
starvation diagnostics ADR-011/ADR-012 require to be reported *beside* the
headline number rather than instead of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .sumo_tools import ensure_sumo_home, sumo_binary

__all__ = ["Controller", "EpisodeResult", "run_episode", "lane_ids", "APPROACHES"]

APPROACHES = ("N", "S", "E", "W")
NS, EW = 0, 1          # phase indices into the generated program


def lane_ids(lanes_per_approach: int = 2) -> dict[str, list[str]]:
    """Inbound lane ids per approach.

    Derived from the edge naming the network generator fixes, because the 16-dim
    PPO state vector indexes by lane (PRD §13.1, FR-M14) and a mismatch here
    silently permutes the state.
    """
    return {
        approach: [f"{approach}2C_{i}" for i in range(lanes_per_approach)]
        for approach in APPROACHES
    }


class Controller(Protocol):
    """Every benchmarked method implements exactly this.

    `decide` returns `(phase_index, green_seconds)`. The runner enforces min and
    max green and inserts yellow and all-red, so **no controller can produce an
    unsafe program** — including a PPO agent that has learned to. Safety is an
    actuation property, not something a policy is trusted to have learned
    (PRD §9.6).
    """

    name: str

    def reset(self) -> None: ...

    def decide(self, observation: dict) -> tuple[int, int]: ...


@dataclass
class EpisodeResult:
    method: str
    seed: int
    regime: str
    steps: int
    mean_wait_s: float
    mean_queue: float
    throughput: int
    max_wait_s: float
    starvation_events: int
    phase_switches: int
    arrived_fraction: float
    extra: dict = field(default_factory=dict)

    def as_row(self) -> dict:
        row = {
            "method": self.method,
            "seed": self.seed,
            "regime": self.regime,
            "steps": self.steps,
            "mean_wait_s": round(self.mean_wait_s, 3),
            "mean_queue": round(self.mean_queue, 3),
            "throughput": self.throughput,
            "max_wait_s": round(self.max_wait_s, 1),
            "starvation_events": self.starvation_events,
            "phase_switches": self.phase_switches,
            "arrived_fraction": round(self.arrived_fraction, 4),
        }
        row.update(self.extra)
        return row


def run_episode(
    controller: Controller,
    *,
    net_dir: Path = Path("simulation/networks"),
    regime: str = "saturated",
    seed: int = 42,
    duration_s: int = 1800,
    yellow_s: int = 3,
    all_red_s: int = 3,
    min_green_s: int = 10,
    max_green_s: int = 90,
    starvation_s: int = 180,
    lateral_resolution: float | None = 0.8,
    collect_lateral: bool = False,
) -> EpisodeResult:
    """Run one episode. Returns metrics; writes nothing.

    `lateral_resolution=None` disables the sublane model, which is the (b) arm of
    ADR-010's declared comparison — the same demand under lane-disciplined SUMO,
    reported so the heterogeneity claim is evidenced rather than asserted.
    """
    ensure_sumo_home()
    import tempfile
    import xml.etree.ElementTree as ET

    import traci

    handle = tempfile.NamedTemporaryFile(
        suffix=".tripinfo.xml", delete=False, mode="w"
    )
    handle.close()
    tripinfo = Path(handle.name)

    command = [
        str(sumo_binary("sumo")),
        "-n", str(net_dir / "intersection.net.xml"),
        "-r", str(net_dir / f"demand_{regime}.rou.xml"),
        "-a", str(net_dir / "vtypes.add.xml"),
        "--seed", str(seed),
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "-1",
        "--waiting-time-memory", str(duration_s),
        # Per-vehicle trip records. The headline metric MUST come from here.
        # `traci.lane.getWaitingTime` returns the SUM of waiting times of the
        # vehicles on a lane, so aggregating it produces a number that scales
        # with occupancy and is not a per-vehicle wait at all — it looks like a
        # mean and is not one.
        "--tripinfo-output", str(tripinfo),
    ]
    if lateral_resolution:
        command += ["--lateral-resolution", str(lateral_resolution)]

    lanes = lane_ids()

    controller.reset()
    traci.start(command)

    wait_total = 0.0
    queue_total = 0.0
    samples = 0
    max_wait = 0.0
    phase_switches = 0
    starvation_events = 0
    departed = arrived = 0
    red_since = {approach: 0 for approach in APPROACHES}
    lateral_spread: dict[str, list[float]] = {}

    try:
        step = 0
        current_phase = NS
        traci.trafficlight.setPhase("C", current_phase * 3)
        remaining = min_green_s

        while step < duration_s:
            counts, queues, waits = {}, {}, {}
            for approach, group in lanes.items():
                counts[approach] = sum(
                    traci.lane.getLastStepVehicleNumber(l) for l in group
                )
                queues[approach] = sum(
                    traci.lane.getLastStepHaltingNumber(l) for l in group
                )
                # Lane waiting time is a SUM over vehicles, used here only as a
                # relative signal for the controller and for starvation
                # detection. It is deliberately NOT the reported wait metric.
                waits[approach] = sum(
                    traci.lane.getWaitingTime(l) for l in group
                )

            if remaining <= 0:
                phase, green = controller.decide({
                    "counts": counts, "queues": queues, "waits": waits,
                    "phase": current_phase, "step": step,
                })
                # Clamping happens HERE, not in the controller. A policy that
                # has learned to request a 300 s green is still a policy that
                # gets 90 (PRD §9.6).
                green = max(min_green_s, min(max_green_s, int(green)))

                if phase != current_phase:
                    phase_switches += 1
                    gone, done = _run_interphase(
                        traci, current_phase, yellow_s, all_red_s
                    )
                    departed += gone
                    arrived += done
                    step += yellow_s + all_red_s
                    current_phase = phase
                    traci.trafficlight.setPhase("C", current_phase * 3)
                remaining = green

            traci.simulationStep()
            step += 1
            remaining -= 1

            departed += traci.simulation.getDepartedNumber()
            arrived += traci.simulation.getArrivedNumber()

            served = ("N", "S") if current_phase == NS else ("E", "W")
            for approach in APPROACHES:
                if approach in served:
                    red_since[approach] = 0
                else:
                    red_since[approach] += 1
                    if red_since[approach] == starvation_s:
                        starvation_events += 1

            wait_total += sum(waits.values())
            queue_total += sum(queues.values())
            max_wait = max(max_wait, max(waits.values(), default=0.0))
            samples += 1

            if collect_lateral and step % 10 == 0:
                for vehicle in traci.vehicle.getIDList():
                    kind = traci.vehicle.getTypeID(vehicle).split("@")[0]
                    lateral_spread.setdefault(kind, []).append(
                        abs(traci.vehicle.getLateralLanePosition(vehicle))
                    )
    finally:
        traci.close()

    trips = _read_tripinfo(tripinfo, ET)
    tripinfo.unlink(missing_ok=True)

    extra = {}
    if collect_lateral:
        for kind, values in sorted(lateral_spread.items()):
            extra[f"lat_mean_{kind}"] = round(sum(values) / len(values), 4)
            extra[f"lat_n_{kind}"] = len(values)

    return EpisodeResult(
        method=controller.name,
        seed=seed,
        regime=regime,
        steps=samples,
        mean_wait_s=trips["mean_wait_s"],
        mean_queue=queue_total / samples if samples else 0.0,
        throughput=len(trips["waits"]),
        max_wait_s=trips["max_wait_s"],
        starvation_events=starvation_events,
        phase_switches=phase_switches,
        arrived_fraction=arrived / departed if departed else 0.0,
        extra=extra,
    )


def _read_tripinfo(path: Path, ET) -> dict:
    """Per-vehicle waiting time for every COMPLETED trip.

    Completed only, and that is a bias worth stating rather than hiding: under
    oversaturation the vehicles still stuck in a queue when the episode ends are
    the ones that waited longest, and they are absent from this average. So mean
    wait **understates** congestion exactly when congestion is worst, which is
    why `arrived_fraction` is reported beside it. A method that looks good on
    mean wait while completing 70% of trips has not done well.
    """
    if not path.exists() or path.stat().st_size == 0:
        return {"mean_wait_s": 0.0, "max_wait_s": 0.0, "waits": [], "mean_duration_s": 0.0}

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        # SUMO writes the closing tag on clean shutdown; a truncated file after
        # an abnormal exit is recoverable and better than losing the episode.
        text = path.read_text(encoding="utf-8").rstrip()
        root = ET.fromstring(text + "</tripinfos>")

    waits = [float(t.get("waitingTime", 0.0)) for t in root.findall("tripinfo")]
    durations = [float(t.get("duration", 0.0)) for t in root.findall("tripinfo")]
    return {
        "mean_wait_s": sum(waits) / len(waits) if waits else 0.0,
        "max_wait_s": max(waits) if waits else 0.0,
        "mean_duration_s": sum(durations) / len(durations) if durations else 0.0,
        "waits": waits,
    }


def _run_interphase(
    traci, phase: int, yellow_s: int, all_red_s: int
) -> tuple[int, int]:
    """Yellow then all-red, always, between any two greens (FR-A04).

    Returns the departures and arrivals that happened during the interphase.

    Returning them is not bookkeeping pedantry. The first version stepped the
    simulation here and counted nothing, so every yellow and all-red was
    invisible to both counters — and because arrivals and departures are not
    missed at the same rate, `arrived_fraction` came out as **1.02**. A
    completion ratio above 1 is impossible, which is the only reason the
    omission was noticed at all.
    """
    departed = arrived = 0
    traci.trafficlight.setPhase("C", phase * 3 + 1)      # yellow
    for _ in range(yellow_s + all_red_s):
        if _ == yellow_s:
            traci.trafficlight.setPhase("C", phase * 3 + 2)   # all-red
        traci.simulationStep()
        departed += traci.simulation.getDepartedNumber()
        arrived += traci.simulation.getArrivedNumber()
    return departed, arrived
