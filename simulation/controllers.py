"""Signal controllers under comparison (S34, PRD §14.3).

Each is a `Controller` from `runner.py`. They differ only in `decide`; safety
clamping, yellow and all-red live in the runner, so no controller — learned or
otherwise — can produce an unsafe program.

`Fixed` and `LongestQueue` are the two baselines every adaptive-signal paper is
expected to beat. Reporting only against fixed-time is the weakest possible
comparison: a queue-responsive rule is trivial to implement, so beating PPO
against fixed-time alone invites the obvious objection.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Fixed", "LongestQueue"]

NS, EW = 0, 1
NS_APPROACHES, EW_APPROACHES = ("N", "S"), ("E", "W")


@dataclass
class Fixed:
    """Fixed-time: alternate phases, same green every time.

    The floor. It ignores the observation entirely, which is the point — any
    method that cannot beat it is not adaptive in any useful sense.
    """

    green_s: int = 30
    name: str = "fixed"

    def reset(self) -> None:
        self._phase = EW      # so the first decide() switches to NS

    def decide(self, observation: dict) -> tuple[int, int]:
        self._phase = EW if self._phase == NS else NS
        return self._phase, self.green_s


@dataclass
class LongestQueue:
    """Serve whichever direction has the longer queue, for a proportional green.

    A genuinely competitive baseline and cheap to implement, which is exactly why
    it belongs in the comparison. It is also the one that exposes whether PPO has
    learned anything beyond "serve the busy direction".

    It can starve an approach when demand is lopsided — it has no memory of how
    long anyone has waited. That is a real property of the method, not a bug to
    patch out: the runner counts starvation events, and a baseline that starves
    is informative rather than embarrassing.
    """

    seconds_per_vehicle: float = 2.0
    min_green_s: int = 10
    max_green_s: int = 90
    name: str = "longest_queue"

    def reset(self) -> None:
        pass

    def decide(self, observation: dict) -> tuple[int, int]:
        queues = observation["queues"]
        ns = sum(queues[a] for a in NS_APPROACHES)
        ew = sum(queues[a] for a in EW_APPROACHES)

        phase = NS if ns >= ew else EW
        serving = ns if phase == NS else ew
        green = int(serving * self.seconds_per_vehicle)
        return phase, max(self.min_green_s, min(self.max_green_s, green))
