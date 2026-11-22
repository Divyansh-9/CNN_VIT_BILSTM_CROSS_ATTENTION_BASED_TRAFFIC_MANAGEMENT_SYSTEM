"""Advisory phase scheduling for a simulated, exclusive-phase controller."""

from collections import Counter, deque
from dataclasses import dataclass
from math import ceil
from pathlib import Path
import json
import os

from scripts.video_traffic import WINDOW_S


@dataclass(frozen=True)
class Phase:
    name: str
    approaches: tuple
    minimum: int
    maximum: int
    pedestrian: bool = False


def signal_config(camera, approaches, policy, raw=None):
    """Default to exclusive single approaches. Grouped movements require explicit approval."""
    if raw is None:
        path = os.environ.get("STMS_SIGNAL_CONFIG")
        raw = json.loads(Path(path).read_text(encoding="utf-8")).get(camera, {}) if path else {}
    if not isinstance(raw, dict):
        raise ValueError("Expected a signal configuration object")
    def seconds(key, default, low, high):
        value = raw.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Invalid {key} for this simulation")
        return value

    yellow = seconds("yellow_s", policy.yellow, 3, 10)
    red = seconds("all_red_s", policy.all_red, 1, 10)
    maximum_wait = seconds("max_red_s", 240, 30, 1200)
    refresh = seconds("refresh_s", 4, 2, 10)
    compatible = {frozenset(pair) for pair in raw.get("compatible", []) if len(pair) == 2}
    rows = raw.get("phases", [{"name": a, "approaches": [a]} for a in approaches])
    if not rows or len(rows) > len(approaches) + 2:
        raise ValueError("Invalid number of signal phases")
    # A phase appears once per round. The worst wait spans the tail of one round
    # and the head of the next. Bound every slot to make that worst case feasible.
    slot_budget = maximum_wait // (2 * len(rows) - 1) - yellow - red
    phases, covered = [], set()
    for row in rows:
        name = row["name"].strip()
        members = tuple(row.get("approaches", ()))
        pedestrian = row.get("pedestrian", False)
        minimum = row.get("min_green_s", policy.greens[0])
        maximum = row.get("max_green_s", policy.greens[-1])
        if (not name or len(name) > 60 or any(p.name == name for p in phases)
                or type(pedestrian) is not bool or bool(members) == pedestrian
                or len(members) != len(set(members)) or covered.intersection(members)
                or not set(members) <= set(approaches)):
            raise ValueError("Phases must uniquely cover configured approaches or be exclusive pedestrian phases")
        if any(frozenset((a, b)) not in compatible for i, a in enumerate(members) for b in members[i+1:]):
            raise ValueError(f"Unverified compatible movements in phase {name}")
        if pedestrian:
            walk, clearance = row.get("walk_s"), row.get("pedestrian_clearance_s")
            if any(type(s) is not int or s <= 0 for s in (walk, clearance)):
                raise ValueError("Pedestrian phases need explicit walk and clearance intervals")
            minimum = maximum = walk + clearance
        if (type(minimum) is not int or type(maximum) is not int
                or not 5 <= minimum <= min(maximum, slot_budget) <= maximum <= 180):
            raise ValueError("Phase duration or maximum red limit is infeasible")
        phases.append(Phase(name, members, minimum, min(maximum, slot_budget), pedestrian))
        covered.update(members)
    if covered != set(approaches):
        raise ValueError("Signal phases must cover every mapped approach")
    return tuple(phases), yellow, red, refresh, maximum_wait


class AdaptiveSignal:
    """Update demand causally and lock each next phase as clearance begins."""

    def __init__(self, config, lanes, lined):
        self.phases, self.yellow, self.red, self.refresh, self.max_red = config
        self.lanes, self.lined = lanes, lined
        self.remaining = list(self.phases)
        self.last_end = {phase.name: 0 for phase in self.phases}
        self.recent = deque()
        self.crossing_cursor = 0
        self.measurements = {}
        self.last_prediction = -self.refresh
        self.since = None
        self.active = self.committed = None
        self.history = []

    def observe(self, sample, events):
        t = sample["t"]
        if self.since is None:
            self.since = t
        while self.crossing_cursor < len(events) and events[self.crossing_cursor]["t"] <= t:
            event = events[self.crossing_cursor]
            self.recent.append((event["t"], event["approach"]))
            self.crossing_cursor += 1
        while self.recent and self.recent[0][0] < t - 30:
            self.recent.popleft()
        counts = Counter(approach for _, approach in self.recent)
        span = min(30, t - self.since)
        latest = {approach: {
            "visible": sample["counts"].get(lane),
            "inbound_per_min": round(counts[approach] * 60 / span, 1)
            if span >= 10 and approach in self.lined else None,
        } for lane, approach in self.lanes.items()}
        self.advance(t)
        if t - self.last_prediction >= self.refresh:
            self.measurements = latest
            self.last_prediction = t
        if self.active is None:
            self.start(self.pick(t))
        return self.snapshot(t, latest)

    def candidates(self, pool, last, start):
        # Fill each round before serving a phase again. As red time builds, its
        # priority increases even when another approach has higher demand.
        def metrics(phase):
            rows = [self.measurements.get(a, {}) for a in phase.approaches]
            demand = sum(row.get("visible") or 0 for row in rows)
            inbound = sum(row.get("inbound_per_min") or 0 for row in rows)
            red_time = max(0, start - last[phase.name])
            return demand, inbound, red_time
        def priority(phase):
            demand, inbound, red_time = metrics(phase)
            return (red_time >= self.max_red / 2, demand + inbound / 12 + red_time / 20, red_time)
        phase = max(pool, key=priority)
        demand, inbound, red_time = metrics(phase)
        duration = min(phase.maximum, phase.minimum + ceil(2 * demand + inbound / 6))
        reason = ("Scheduled exclusive pedestrian service" if phase.pedestrian else
                  f"{demand:g} vehicles in view, {red_time:g} s of simulated red at start"
                  + (f", {inbound:g} measured inbound crossings/min" if inbound else ""))
        if red_time >= self.max_red / 2:
            reason += ". Long-red priority applied."
        return phase, duration, reason, demand, red_time

    def pick(self, start, pool=None, last=None):
        choices = self.remaining if pool is None else pool
        phase, green, reason, demand, wait = self.candidates(
            choices or self.phases, self.last_end if last is None else last, start)
        end = start + green
        return {"phase": phase.name, "approaches": phase.approaches, "pedestrian": phase.pedestrian,
                "start": start, "green_end": end, "yellow_end": end + self.yellow,
                "end": end + self.yellow + self.red, "green_s": green,
                "visible": demand, "red_wait_s": wait, "reason": reason}

    def start(self, row):
        if not self.remaining:
            self.remaining = list(self.phases)
        self.remaining = [phase for phase in self.remaining if phase.name != row["phase"]]
        self.last_end[row["phase"]] = row["green_end"]
        self.active = row
        self.history.append(row)

    def advance(self, t):
        # Tick against media time, even when analysis runs faster than playback.
        while self.active is not None and t >= self.active["green_end"]:
            if self.committed is None:
                self.committed = self.pick(self.active["end"])
            if t < self.active["end"]:
                break
            self.start(self.committed)
            self.committed = None

    def snapshot(self, t, latest):
        current = self.active
        state = ("green" if t < current["green_end"] else
                 "yellow" if t < current["yellow_end"] else "all-red")
        boundary = current[{"green": "green_end", "yellow": "yellow_end", "all-red": "end"}[state]]
        pool, last, upcoming = self.remaining[:], self.last_end.copy(), []
        start = current["end"]
        for i in range(3):
            row = self.committed if i == 0 and self.committed else self.pick(start, pool, last)
            upcoming.append(row)
            pool = [phase for phase in (pool or self.phases) if phase.name != row["phase"]]
            last[row["phase"]], start = row["green_end"], row["end"]
        return {"source": "simulated", "state": state, "phase": current, "until": boundary,
                "upcoming": upcoming, "next_locked": self.committed is not None,
                "as_of": self.last_prediction, "measurements": latest}


def offline_schedule(config, lanes, lined, traffic, duration):
    """Optimize against the complete clip's window averages and measured flow."""
    controller = AdaptiveSignal(config, lanes, lined)
    windows = traffic["windows"]
    arrivals = Counter((int(e["t"] // WINDOW_S), e["approach"]) for e in traffic["crossings"])
    start, index = 0, 0
    while start < duration or len(controller.history) < len(controller.phases):
        while index + 1 < len(windows) and windows[index]["end"] <= start:
            index += 1
        window = windows[index]
        span = window["end"] - window["t"]
        controller.measurements = {a: {
            "visible": n, "inbound_per_min": arrivals[int(window["t"] // WINDOW_S), a] * 60 / span
            if span >= 10 and a in lined else None,
        } for a, n in window["approaches"].items()}
        row = controller.pick(start)
        controller.start(row)
        start = row["end"]
    return {"mode": "offline", "phases": controller.history, "max_red_s": controller.max_red,
            "coverage_s": duration}
