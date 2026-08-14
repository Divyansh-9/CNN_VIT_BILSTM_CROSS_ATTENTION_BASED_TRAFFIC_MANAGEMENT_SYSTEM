"""Webster's method as a benchmark baseline (S35, ADR-011, ADR-012).

Webster's optimum cycle is

    C0 = (1.5 L + 5) / (1 - Y)

where `L` is total lost time per cycle and `Y` is the sum of critical flow
ratios `y = q / s`. Effective green is then split in proportion to `y`.

**Nothing here picks a saturation flow.** ADR-012 found the published values for
non-lane-disciplined traffic span 525–1283 PCU/h **per metre of approach width** —
a 2.4× range that reflects genuine differences in PCU convention and vehicle mix,
not noise to average away. Picking one value is indefensible in either direction:
choose the low end and Webster under-serves every approach, PPO wins easily, and
the win is an artifact of the baseline.

So the sweep is the baseline. `Webster` takes one value and `select_best` chooses
among the seven, because "PPO beat Webster's best across the published range"
survives the obvious objection and "we used 525W" does not.

**"Best-performing" alone turned out to be unsafe**, and running the sweep is what
showed it — see `select_best`. Two configurations can post the lowest wait while
not running Webster at all (fully clamped) or while having failed (a low wait
because the slowest vehicles never finished). Both disqualifications are enforced
in code and both were triggered by real data, not hypothesised.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Webster", "PCE", "critical_flow_ratio", "optimum_cycle",
    "Selection", "select_best",
]

NS, EW = 0, 1
NS_APPROACHES, EW_APPROACHES = ("N", "S"), ("E", "W")

# PRD §14.1 / spec.yaml. Two- and three-wheelers occupy far less of the discharge
# than a car, which is the entire reason a per-lane saturation flow is wrong here.
PCE = {
    "car": 1.00,
    "motorcycle": 0.24,
    "auto_rickshaw": 0.78,
    "e_rickshaw": 0.78,
    "truck": 3.00,
    "bus": 3.00,
}


def critical_flow_ratio(demand_pcu_per_hour: float, saturation_pcu_per_hour: float) -> float:
    """`y = q / s`, clamped below 1.

    Uncapped, an oversaturated approach drives `Y` past 1 and `1 - Y` negative,
    which makes the optimum cycle **negative** — a number that then gets clamped
    into range and silently looks reasonable. Capping at 0.95 keeps the formula
    in the regime it was derived for and lets the clamp counter tell the truth.
    """
    if saturation_pcu_per_hour <= 0:
        raise ValueError("saturation flow must be positive")
    return min(0.95, max(0.0, demand_pcu_per_hour / saturation_pcu_per_hour))


def optimum_cycle(total_y: float, lost_time_s: float) -> float:
    """Webster's C0. Returns infinity when Y >= 1 — the honest answer.

    At Y >= 1 demand exceeds capacity and no cycle length serves it; the caller
    clamps to `max_cycle_s` and counts the clamp. Returning a finite number here
    would hide that.
    """
    if total_y >= 1.0:
        return float("inf")
    return (1.5 * lost_time_s + 5.0) / (1.0 - total_y)


@dataclass
class Webster:
    """One Webster configuration: one saturation flow, one startup lost time.

    Re-times on every decision from observed counts, which is the *adaptive*
    reading of Webster and the stronger baseline. A fixed pre-timed Webster
    computed once from average demand would be easier to beat and less honest.
    """

    saturation_flow_per_metre: float = 660.0
    approach_width_m: float = 6.4          # 2 lanes x 3.2 m, from the generated network
    lost_time_startup_s: float = 4.0
    all_red_s: int = 3
    yellow_s: int = 3
    min_green_s: int = 10
    max_green_s: int = 90
    min_cycle_s: int = 32                  # A27-corrected: 2*(min_green+yellow+all_red)
    max_cycle_s: int = 192                 # A27-corrected: 2*(max_green+yellow+all_red)
    observation_window_s: int = 120

    name: str = "webster"
    clamps: int = field(default=0, init=False)
    decisions: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.name = f"webster_s{int(self.saturation_flow_per_metre)}"

    @property
    def saturation_pcu_per_hour(self) -> float:
        """Per-approach discharge. Width-based, per ADR-012."""
        return self.saturation_flow_per_metre * self.approach_width_m

    @property
    def clamp_rate(self) -> float:
        """Reported beside every result, never instead of it."""
        return self.clamps / self.decisions if self.decisions else 0.0

    def reset(self) -> None:
        self.clamps = 0
        self.decisions = 0
        self._phase = EW

    def decide(self, observation: dict) -> tuple[int, int]:
        counts = observation["counts"]

        # Counts are an instantaneous occupancy, so scale to an hourly rate over
        # the observation window. Crude, and stated as such — the alternative is
        # an induction-loop model the network does not have.
        scale = 3600.0 / self.observation_window_s
        ns_demand = sum(counts[a] for a in NS_APPROACHES) * scale
        ew_demand = sum(counts[a] for a in EW_APPROACHES) * scale

        y_ns = critical_flow_ratio(ns_demand, self.saturation_pcu_per_hour)
        y_ew = critical_flow_ratio(ew_demand, self.saturation_pcu_per_hour)
        total_y = min(0.95, y_ns + y_ew)

        lost_time = 2 * (self.lost_time_startup_s + self.all_red_s)
        cycle = optimum_cycle(total_y, lost_time)

        self.decisions += 1
        if cycle == float("inf") or cycle > self.max_cycle_s:
            cycle = float(self.max_cycle_s)
            self.clamps += 1
        elif cycle < self.min_cycle_s:
            cycle = float(self.min_cycle_s)
            self.clamps += 1

        effective_green = max(0.0, cycle - lost_time)

        # Alternate, then size this phase's green from its own flow ratio. Serving
        # whichever direction is busier would make this a queue-responsive rule
        # wearing Webster's name — the alternation is what makes it Webster.
        self._phase = EW if self._phase == NS else NS
        share = y_ns if self._phase == NS else y_ew
        green = effective_green * (share / total_y) if total_y > 0 else effective_green / 2

        return self._phase, int(max(self.min_green_s, min(self.max_green_s, green)))


# --------------------------------------------------------- selecting "best" --

@dataclass(frozen=True)
class Selection:
    """The chosen configuration, and every configuration that was disqualified."""

    best: dict | None
    rejected: list[tuple[dict, str]]
    rule: str

    def explain(self) -> str:
        lines = [f"rule: {self.rule}"]
        if self.best is None:
            lines.append("  NO configuration qualified — report the sweep, claim nothing")
        else:
            lines.append(
                f"  chosen: s={self.best['saturation_flow']} "
                f"wait={self.best['mean_wait_s']}s "
                f"clamp={self.best['clamp_rate']:.0%} "
                f"arrived={self.best['arrived_fraction']:.2f}"
            )
        for row, reason in self.rejected:
            lines.append(f"  rejected s={row['saturation_flow']}: {reason}")
        return "\n".join(lines)


def select_best(
    rows: list[dict],
    *,
    max_clamp_rate: float = 0.50,
    min_arrived_fraction: float = 0.85,
) -> Selection:
    """Best Webster configuration — with two disqualifications that matter.

    ADR-012 says to report the **best-performing** saturation flow. Running the
    sweep showed that rule is not safe on its own, in two distinct ways.

    **A fully-clamped Webster is not Webster.** At the capacity knee, s=1050 and
    s=1283 produced the lowest waits (13.7 s) at a **100% clamp rate** — every
    cycle hit a bound, so the method degenerated to a fixed 32 s cycle and the
    formula contributed nothing. Reporting that as "Webster's best" would put a
    fixed-time controller in the results table under Webster's name, and the
    comparison would be meaningless in the baseline's favour *and* against it:
    it is neither Webster nor a fair fixed-time.

    **A low mean wait can be survivorship.** In the oversaturated regime s=1050
    reported the *lowest* wait of the sweep, 63.2 s — while completing **55%** of
    trips against ~77% for every other configuration, with a mean queue of 211
    against ~85. Its wait looks good because the vehicles that waited longest
    never finished and so never entered the tripinfo average. This is exactly the
    bias `run_episode` documents, caught in the wild.

    So a configuration qualifies only if it is genuinely running the method and
    genuinely serving the traffic. If none qualifies, that is the finding: report
    the sweep and make no "Webster's best" claim at all.
    """
    qualified: list[dict] = []
    rejected: list[tuple[dict, str]] = []

    for row in rows:
        clamp = float(row.get("clamp_rate", 0.0))
        arrived = float(row.get("arrived_fraction", 1.0))
        if clamp > max_clamp_rate:
            rejected.append((
                row,
                f"clamp rate {clamp:.0%} > {max_clamp_rate:.0%} — the cycle formula "
                f"never decided anything; this is a fixed cycle wearing Webster's name",
            ))
        elif arrived < min_arrived_fraction:
            rejected.append((
                row,
                f"completed {arrived:.0%} of trips < {min_arrived_fraction:.0%} — its "
                f"mean wait excludes the vehicles that waited longest",
            ))
        else:
            qualified.append(row)

    best = min(qualified, key=lambda r: r["mean_wait_s"]) if qualified else None
    return Selection(
        best=best,
        rejected=rejected,
        rule=(
            f"lowest mean wait among configurations with clamp rate <= "
            f"{max_clamp_rate:.0%} and arrived fraction >= {min_arrived_fraction:.0%}"
        ),
    )
