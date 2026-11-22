"""Measurements and advisory events for one local recording."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from math import dist, isfinite
from statistics import fmean

from scripts.recording_profile import WHOLE_FRAME


KINDS = ("car", "motorcycle", "bus", "truck")
LEVELS = ("Low", "Moderate", "High", "Severe")
WINDOW_S = 30
# Image-normalized clearance from the counting line. Both projected box edges
# must advance so a box resizing around a stopped vehicle cannot count it.
CROSSING_MARGIN = .01
CROSSING_WINDOW_S = 2


@dataclass(frozen=True)
class Policy:
    density: tuple[float, ...] = (3, 6, 10)
    lane_demand: tuple[float, ...] = (1, 3, 5)
    greens: tuple[int, ...] = (15, 30, 45, 60)
    previous_green: int = 30
    yellow: int = 4
    all_red: int = 2
    stopped_seconds: int = 20

    def __post_init__(self):
        for values in (self.density, self.lane_demand):
            if (len(values) != 3 or any(not isfinite(v) or v <= 0 for v in values)
                    or not values[0] < values[1] < values[2]):
                raise ValueError("Traffic thresholds must be three increasing positive numbers")
        if (len(self.greens) != 4 or any(type(v) is not int for v in self.greens)
                or not 5 <= self.greens[0] < self.greens[1] < self.greens[2] < self.greens[3] <= 180):
            raise ValueError("Green times must be four increasing whole seconds in the 5–180 range")
        for value, low, high in ((self.previous_green, 5, 180), (self.yellow, 3, 10),
                                 (self.all_red, 1, 10), (self.stopped_seconds, 5, 300)):
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Configured phase or stopped-vehicle duration is outside its demo range")


def alert(kind, t, severity, reason, **evidence):
    return {"id": f"{kind}:{t:g}:{evidence.get('track_id', evidence.get('approach', 'video'))}",
            "type": kind, "t": t, "severity": severity, "reason": reason, "evidence": evidence}


class Crossings:
    """Finite inbound count lines through the configured approach centres."""

    def __init__(self, profile, policy):
        self.policy = policy
        self.whole_frame = getattr(profile, "camera_id", None) == WHOLE_FRAME
        self.center = tuple(fmean(axis) for axis in zip(*(point for _, point in profile.lanes)))
        radii = [dist(self.center, point) for _, point in profile.lanes]
        self.core_radius = min(radii) * .45 if len(radii) >= 3 else 0
        self.lines = []
        for (lane, (x, y)), radius in zip(profile.lanes, radii):
            if radius < .04 or len(radii) < 2:
                continue
            nx, ny = (self.center[0] - x) / radius, (self.center[1] - y) / radius
            half = min(profile.max_radius / 2, radius * .55)
            self.lines.append({"lane": lane, "approach": profile.lane_map[lane], "center": (x, y),
                               "normal": (nx, ny), "half": half,
                               "endpoints": ((x - ny * half, y + nx * half), (x + ny * half, y - nx * half))})
        self.recent = {}
        self.upstream = {}
        self.stationary = {}
        self.counted = set()
        self.warned = set()
        self.events = []
        self.alerts = []
        self.next_cleanup = 5

    def observe(self, t, detections, ids, classes):
        if t >= self.next_cleanup:
            self.recent = {k: v for k, v in self.recent.items() if t - v[0] <= 1}
            self.upstream = {k: v for k, v in self.upstream.items() if k in self.recent}
            self.stationary = {k: v for k, v in self.stationary.items() if k in self.recent}
            self.next_cleanup = t + 5
        for detection, track_id in zip(detections, ids):
            if track_id is None or detection.confidence < .25:
                continue
            point = detection.centroid
            previous = self.recent.get(track_id)
            self.recent[track_id] = (t, point)
            continuous = previous is not None and t - previous[0] <= 1 and dist(point, previous[1]) <= .15
            if track_id not in self.counted:
                if self.whole_frame:
                    if continuous:
                        self.count(track_id, t, classes[detection.cls], "N", detection.confidence)
                else:
                    if not continuous:
                        self.upstream.pop(track_id, None)
                    self.cross(track_id, detection, t, classes[detection.cls])
            self.stop(track_id, point, t, continuous)

    @staticmethod
    def depth(detection, line):
        """Signed projection of the centre and the two extremal box edges."""
        x, y = line["center"]
        nx, ny = line["normal"]
        cx, cy = detection.centroid
        centre = (cx - x) * nx + (cy - y) * ny
        radius = (abs(nx) * (detection.x2 - detection.x1) + abs(ny) * (detection.y2 - detection.y1)) / 2
        return centre, centre - radius, centre + radius

    def cross(self, track_id, detection, t, vehicle):
        anchors = self.upstream.setdefault(track_id, {})
        point = detection.centroid
        for line in self.lines:
            approach = line["approach"]
            after, trailing, leading = self.depth(detection, line)
            if after <= -CROSSING_MARGIN:
                anchors[approach] = (t, detection)
                continue
            if after < CROSSING_MARGIN or approach not in anchors:
                continue
            seen_at, anchor = anchors[approach]
            if t - seen_at > CROSSING_WINDOW_S:
                anchors.pop(approach)
                continue
            before, old_trailing, old_leading = self.depth(anchor, line)
            if min(trailing - old_trailing, leading - old_leading) < CROSSING_MARGIN:
                continue
            previous = anchor.centroid
            x, y = line["center"]
            nx, ny = line["normal"]
            fraction = -before / (after - before)
            ix = previous[0] + fraction * (point[0] - previous[0])
            iy = previous[1] + fraction * (point[1] - previous[1])
            if abs((ix - x) * -ny + (iy - y) * nx) > line["half"]:
                anchors.pop(approach)
                continue
            self.count(track_id, t, vehicle, approach, detection.confidence)
            self.upstream.pop(track_id, None)
            return

    def count(self, track_id, t, vehicle, approach, confidence):
        self.counted.add(track_id)
        self.events.append({"track_id": track_id, "t": round(t, 3), "type": vehicle,
                            "approach": approach, "confidence": round(confidence, 3)})

    def stop(self, track_id, point, t, continuous):
        if not self.core_radius or dist(self.center, point) > self.core_radius:
            self.stationary.pop(track_id, None)
            return
        start, anchor = self.stationary.get(track_id, (t, point))
        if not continuous or dist(point, anchor) > .012:
            start, anchor = t, point
        self.stationary[track_id] = start, anchor
        if t - start >= self.policy.stopped_seconds and track_id not in self.warned:
            self.warned.add(track_id)
            duration = round(t - start, 1)
            self.alerts.append(alert("Possible stopped vehicle", round(t, 3), "Warning",
                                     f"Track stayed within 1.2% of its starting image position in the monitored intersection centre for {duration:g} s. Check the replay.",
                                     track_id=track_id, stationary_s=duration))


def level_index(value, cutoffs):
    return sum(value >= cutoff for cutoff in cutoffs)


def summarize(result, crossings, policy, *, legacy_signal_advice=True):
    """Summarize observed occupancy, inbound crossings and configurable advice."""
    windows, alerts = [], list(crossings.alerts)
    samples = result["samples"]
    duration = result["duration_s"]
    flow = Counter(int(event["t"] // WINDOW_S) for event in crossings.events)
    previous_level = -1
    warned = set()
    by_window = defaultdict(list)
    for sample in samples:
        by_window[int(sample["t"] // WINDOW_S)].append(sample)
    for i, batch in by_window.items():
        t, end = i * WINDOW_S, min((i + 1) * WINDOW_S, duration)
        averages = {lane["approach"]: round(fmean(s["counts"][lane["name"]] for s in batch), 3)
                    for lane in result["lanes"]}
        occupancy = round(sum(averages.values()), 3)
        level = level_index(occupancy, policy.density)
        recommendations = {} if crossings.whole_frame else {
            a: policy.greens[level_index(n, policy.lane_demand)] for a, n in averages.items()}
        windows.append({"t": t, "end": end, "visible": occupancy, "level": LEVELS[level],
                        "crossings": flow[i], "approaches": averages, "green": recommendations})
        if end - t < WINDOW_S or len(batch) < WINDOW_S / result["step_s"]:
            continue
        evidence_t = end - result["step_s"]
        if level >= 2 and (previous_level < 2 or level > previous_level):
            alerts.append(alert("Traffic congestion", evidence_t, "Critical" if level == 3 else "Warning",
                                f"{occupancy:g} vehicles in view on average over {WINDOW_S} s reached the {LEVELS[level].lower()} threshold ({policy.density[level - 1]:g}).",
                                window_start=t, visible=occupancy, threshold=policy.density[level - 1]))
        previous_level = level
        high = {a for a, green in recommendations.items() if legacy_signal_advice and green > policy.previous_green}
        for a in sorted(high - warned):
            alerts.append(alert("Signal timing warning", evidence_t, "Warning",
                                f"Approach {a} averaged {averages[a]:g} vehicles in view over {WINDOW_S} s. The demo rule recommends {recommendations[a]} s versus the configured {policy.previous_green} s.",
                                approach=a, window_start=t, demand=averages[a], green=recommendations[a]))
        warned = high
    by_type = Counter(e["type"] for e in crossings.events)
    return {"scope": "frame" if crossings.whole_frame else "approaches",
            "policy": asdict(policy), "lines": crossings.lines, "core": {"center": crossings.center, "radius": crossings.core_radius},
            "crossings": crossings.events, "by_type": {k: by_type[k] for k in KINDS},
            "average_visible": round(fmean(sum(sample["counts"].values()) for sample in samples), 3),
            "windows": windows, "alerts": sorted(alerts, key=lambda e: (e["t"], e["id"]))}
