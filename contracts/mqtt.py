"""MQTT topic and payload contract (PRD §17.1, amendment A26).

Edge, server and dashboard are built by three owners in three different weeks
and only meet during Weeks 17–19 integration — which PRD §2.5.1 already flags as
where trouble appears. Every defect below is a fifteen-minute fix now and a
half-day of cross-owner debugging then, with no schedule slack left.

**QoS is a property of the topic, not an argument.** This is the structural fix.
A publish helper that accepts a QoS parameter lets three people pass three
different values; here the level is attached to the topic and cannot be
overridden. Emergency is QoS 2 because a duplicate fires a spurious preemption
and a loss risks a life — that is not a tuning decision.

Closes the six defects from TRIAGE-001:

    D1  "MED" on the wire against "MEDIUM" in PRD §14.1     -> one spelling, enforced
    D2  "types": {...} literally unspecified                -> the eight §12.2 classes
    D3  no operating-mode field for the five SRS modes      -> Mode on the heartbeat
    D4  "source" enum showed one of four values             -> CommandSource, all four
    D5  no schema version on any payload                    -> SCHEMA_VERSION on all
    D6  string->int mapping for the PPO state unspecified   -> to_state_value()
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "SCHEMA_VERSION",
    "QoS",
    "Topic",
    "Mode",
    "CommandSource",
    "CongestionClass",
    "VEHICLE_CLASSES",
    "VehicleCount",
    "EmergencyDetect",
    "SignalCommand",
    "CongestionPrediction",
    "Heartbeat",
    "ContractError",
    "decode",
    "INTERSECTION_ID",
    "check_intersection_id",
    "SOURCE_KINDS",
    "ForecastCheck",
]

SCHEMA_VERSION = 2
# v2 (ADR-026): no free text crosses the edge boundary. `model` is a pattern,
# prediction keys are approaches, emergency `type` is a closed set, and
# `gate_value` may be None for a config with no gate rather than a made-up 0.5.

#: `config@first-12-hex-of-the-graph's-sha256` — what `VerifiedGraph.model_id`
#: produces — or `persistence@first-12-hex-of-the-frozen-spec's-sha256`, what
#: `edge.persistence` produces (P104, additive: every earlier id still matches).
#: A pattern rather than a string, so the field cannot carry anything else at
#: any length (NFR-13).
MODEL_ID = re.compile(r"^(?:[A-H]|persistence)@[0-9a-f]{12}$")
#: `ridge@first-12-hex-of-the-frozen-spec's-sha256` — what
#: `edge.count_forecast` produces (ADR-027). A count forecaster gets its own
#: pattern, so a count model can never be presented as a class forecaster.
COUNT_MODEL_ID = re.compile(r"^ridge@[0-9a-f]{12}$")
#: The largest 60 s mean count a lane region can plausibly hold. Measured lanes
#: average 0.2–11 vehicles; a value beyond this is a fault, not traffic.
MAX_LANE_COUNT = 200.0
APPROACHES = ("N", "S", "E", "W")
#: An intersection id: a short code such as `j1` or `int01`. It travels outside
#: every payload — in the URL path, in the MQTT topic and in the `/observation`
#: body — so the payload cap never applied to it, and before P142 it was stored
#: and echoed at any length. The character class is the dashboard's own
#: (`intersectionFromUrl`); `fullmatch`, so a trailing newline cannot pass.
INTERSECTION_ID = re.compile(r"[A-Za-z0-9_-]{1,32}")


def check_intersection_id(value: Any) -> str:
    """`value`, if it is a valid intersection id; otherwise a ContractError that
    does not quote it — it would come back in an HTTP body or a log (P142)."""
    if not isinstance(value, str) or not INTERSECTION_ID.fullmatch(value):
        raise ContractError("intersection id must be 1 to 32 characters from "
                            "A-Z, a-z, 0-9, '_' and '-'")
    return value


#: A lane name, as the per-lane topics carry it (`lane_0`). Like the
#: intersection id it travels outside every payload, in the topic, so it gets
#: the same character class and bound before anything stores it (D21).
LANE = INTERSECTION_ID


def check_lane(value: Any) -> str:
    """`value`, if it is a valid lane name; otherwise a ContractError that does
    not quote it, for the reason `check_intersection_id` gives."""
    if not isinstance(value, str) or not LANE.fullmatch(value):
        raise ContractError("lane must be 1 to 32 characters from "
                            "A-Z, a-z, 0-9, '_' and '-'")
    return value
#: PRD §17 names "ambulance" and nothing else. Extending the set is a contract
#: diff, which is the point of having one.
EMERGENCY_TYPES = ("ambulance",)
"""D5. Bumped on any breaking payload change.

Three consumers built weeks apart have no other way to detect a producer/consumer
mismatch. Without this, every other mismatch presents as malformed data rather
than as a version error, and the debugging starts in the wrong place.
"""

VEHICLE_CLASSES = (
    "car", "motorcycle", "auto-rickshaw", "e-rickshaw",
    "bus", "truck", "pedestrian", "cattle",
)
"""D2. Exactly the eight classes of PRD §12.2 — no extras, no merges."""


class ContractError(ValueError):
    """A payload violates the contract."""


class QoS(int, Enum):
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2


class Topic(Enum):
    """Topic templates with their QoS bound in.

    `qos` is read from the topic, never passed by a caller. Three owners cannot
    then choose three different levels for the same topic.
    """

    VEHICLE_COUNT = ("stms/{id}/{lane}/vehicle_count", QoS.AT_LEAST_ONCE)
    EMERGENCY = ("stms/{id}/{lane}/emergency/detect", QoS.EXACTLY_ONCE)
    SIGNAL_COMMAND = ("stms/{id}/signal/command", QoS.AT_LEAST_ONCE)
    PREDICTION = ("stms/{id}/congestion/prediction", QoS.AT_MOST_ONCE)
    # ADR-027: the next-minute count, on its own topic so it can never be
    # merged with or mistaken for the congestion class. QoS as for predictions.
    COUNT_FORECAST = ("stms/{id}/count/forecast", QoS.AT_MOST_ONCE)
    HEARTBEAT = ("stms/{id}/system/heartbeat", QoS.AT_MOST_ONCE)
    # D26: an earlier forecast beside what the counts then showed (ADR-014 §2).
    # Its own topic, so the forecast payloads and their consumers are unchanged
    # and a check can never be a prerequisite for a forecast.
    FORECAST_CHECK = ("stms/{id}/forecast/check", QoS.AT_MOST_ONCE)

    def __init__(self, template: str, qos: QoS) -> None:
        self._template = template
        self._qos = qos

    # Read-only properties, not plain attributes. An Enum member accepts
    # attribute assignment, so `Topic.EMERGENCY.qos = QoS.AT_MOST_ONCE` would
    # otherwise succeed and silently downgrade emergency delivery **process
    # wide** — every subsequent publish in that process, including ones written
    # by someone who never touched the line. The contract test caught exactly
    # this: it set the attribute, and a later assertion then read QoS 0 for
    # emergency.

    @property
    def template(self) -> str:
        return self._template

    @property
    def qos(self) -> QoS:
        return self._qos

    def render(self, intersection_id: str, lane: str | None = None) -> str:
        if "{lane}" in self.template:
            if lane is None:
                raise ContractError(f"{self.name} is per-lane and needs a lane")
            return self.template.format(id=intersection_id, lane=lane)
        if lane is not None:
            raise ContractError(f"{self.name} is not per-lane; got lane={lane!r}")
        return self.template.format(id=intersection_id)


class CongestionClass(str, Enum):
    """D1. One spelling. PRD §14.1 says MEDIUM, so the wire says MEDIUM."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    def to_state_value(self) -> float:
        """D6. Class to the value at PPO state indices 11–14.

        ADR-020 as amended (P97a): LOW, MEDIUM, HIGH → 1/3, 2/3, 1, so that
        0.0 is left to mean "no forecast" and no class can produce it. It must
        equal `spec.yaml`'s `forecast_class_value`, and a test checks they do.
        """
        return {"LOW": 1 / 3, "MEDIUM": 2 / 3, "HIGH": 1.0}[self.value]


class Mode(str, Enum):
    """D3. The five operating modes of SRS §2.3, in precedence order.

    The dashboard cannot show which mode is active without this, and FR-UI01 and
    FR-UI08 both need it. Heartbeat carries it: absence of a heartbeat is already
    the failure signal, so mode rides on the message that proves liveness.
    """

    PREEMPT = "M-PREEMPT"
    MANUAL = "M-MANUAL"
    LOCAL = "M-LOCAL"
    NO_PREDICT = "M-NO-PREDICT"
    NORMAL = "M-NORMAL"


class CommandSource(str, Enum):
    """D4. All four sources FR-UI08 requires in the event log."""

    PPO_AGENT = "ppo_agent"
    WEBSTER_FALLBACK = "webster_fallback"
    EMERGENCY = "emergency"
    MANUAL = "manual"


# ---------------------------------------------------------------- payloads --

#: NFR-13, enforced by size rather than by intent. Every payload here is a
#: handful of scalars and is a few hundred bytes; one frame as a JPEG is tens of
#: kilobytes, and one frame's DINOv2 feature map is about 200 KB. A cap two
#: orders of magnitude below either means a free-text field — `model`, `type`,
#: `edge_status` — cannot carry an image or a feature map off the edge, whatever
#: a future caller puts in it. Checked on encode (the edge) and on decode (the
#: server), so neither side relies on the other.
MAX_PAYLOAD_BYTES = 4096


def _bounded(topic: str, text: str | bytes) -> None:
    size = len(text.encode("utf-8") if isinstance(text, str) else text)
    if size > MAX_PAYLOAD_BYTES:
        raise ContractError(
            f"{topic}: payload is {size} bytes, over the {MAX_PAYLOAD_BYTES}-byte "
            f"cap. Only counts and predictions leave the edge (NFR-13); nothing "
            f"this size is either.")


def _finite_number(value: Any) -> bool:
    """A real, finite number. `bool` is excluded although Python counts it as an
    int: `true` is not a probability, a count or a time (P141). A JSON integer
    too large for a float is not finite either; `math.isfinite` would raise
    OverflowError on it, which is not a ContractError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


#: `ts` is epoch seconds, so it is bounded above as well as below. Without the
#: upper bound a JSON integer of ~300 digits passed, and `encode` stored every
#: digit: about 128 chosen bytes per message (P141). 2100-01-01T00:00:00Z.
TS_MAX = 4_102_444_800


def _valid_ts(value: Any) -> bool:
    return _finite_number(value) and 0 < value < TS_MAX


def _not_an_int(value: Any) -> bool:
    """True unless `value` is an int proper: `60.0`, `"60"` and `True` all fail."""
    return isinstance(value, bool) or not isinstance(value, int)


@dataclass(frozen=True)
class _Payload:
    def encode(self) -> str:
        d = {k: (v.value if isinstance(v, Enum) else v) for k, v in asdict(self).items()}
        d["v"] = SCHEMA_VERSION
        text = json.dumps(d, separators=(",", ":"))
        _bounded(type(self).__name__, text)
        return text


@dataclass(frozen=True)
class VehicleCount(_Payload):
    count: int
    types: Mapping[str, int]
    fps: float
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ContractError(f"count must be non-negative, got {self.count}")
        unknown = set(self.types) - set(VEHICLE_CLASSES)
        if unknown:
            raise ContractError(
                f"unknown vehicle class(es) {sorted(unknown)}. The eight PRD §12.2 "
                f"classes are {list(VEHICLE_CLASSES)}"
            )
        if sum(self.types.values()) != self.count:
            raise ContractError(
                f"types sum to {sum(self.types.values())} but count is {self.count}. "
                f"A per-class breakdown that disagrees with the total is worse than "
                f"no breakdown — a consumer cannot tell which to trust."
            )


@dataclass(frozen=True)
class EmergencyDetect(_Payload):
    type: str
    confidence: float
    frame_count: int
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.type not in EMERGENCY_TYPES:
            raise ContractError(
                f"unknown emergency type {self.type!r}; expected one of "
                f"{list(EMERGENCY_TYPES)}")
        # FR-P04: confidence >= 0.75 AND >= 2 consecutive detections. The
        # conjunction is the contract — a single high-confidence frame is not
        # evidence, and a spurious preemption costs every other approach its green.
        if self.confidence < 0.75:
            raise ContractError(
                f"confidence {self.confidence} is below the FR-P04 threshold of 0.75"
            )
        if self.frame_count < 2:
            raise ContractError(
                f"frame_count {self.frame_count} is below the FR-P04 minimum of 2 "
                f"consecutive detections"
            )


@dataclass(frozen=True)
class SignalCommand(_Payload):
    phase: str
    duration: int
    source: CommandSource
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.phase not in ("NS_GREEN", "EW_GREEN", "ALL_RED"):
            raise ContractError(f"unknown phase {self.phase!r}")
        # FR-A03 bounds, enforced at the wire rather than trusted upstream. The
        # actuation layer rejects a violating command whatever the policy emitted.
        if self.phase != "ALL_RED" and not (10 <= self.duration <= 90):
            raise ContractError(
                f"green duration {self.duration}s violates FR-A03 bounds [10, 90]"
            )
        if not isinstance(self.source, CommandSource):
            raise ContractError(f"source must be a CommandSource, got {self.source!r}")


@dataclass(frozen=True)
class CongestionPrediction(_Payload):
    predictions: Mapping[str, CongestionClass]
    confidences: Mapping[str, float]
    # None for a config without a gate (A, B, H): an absent gate is not a gate
    # of 0.5, and the dashboard must not plot it as one (FR-UI05). Required,
    # not defaulted, so a producer states which case it is in.
    gate_value: float | None
    model: str
    horizon_sec: int = 60
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        # P141: every field is typed and bounded, because this payload crosses
        # the edge boundary and is stored; an unchecked field is a free-text
        # channel. No message quotes a submitted key or value — they become
        # HTTP 422 bodies — but each names the field and the rule.
        if set(self.predictions) != set(self.confidences):
            raise ContractError("predictions and confidences must cover the same lanes")
        if not all(isinstance(cls, CongestionClass) for cls in self.predictions.values()):
            raise ContractError(
                "every prediction must be a CongestionClass. "
                "D1 — the wire spelling is MEDIUM, never MED.")
        if set(self.predictions) - set(APPROACHES):
            raise ContractError(
                f"prediction keys must be approaches {list(APPROACHES)}. "
                f"Map keys are text too (NFR-13).")
        if not all(_finite_number(c) and 0.0 <= c <= 1.0 for c in self.confidences.values()):
            raise ContractError("confidences must be numbers in [0, 1], one per predicted "
                                "approach")
        if self.gate_value is not None and not (
                _finite_number(self.gate_value) and 0.0 <= self.gate_value <= 1.0):
            raise ContractError("gate_value must be a number in [0, 1], or None")
        if _not_an_int(self.horizon_sec) or self.horizon_sec != 60:
            raise ContractError("horizon_sec must be the integer 60, the PRD §8.2 horizon")
        if not _valid_ts(self.ts):
            raise ContractError("ts must be a positive, finite number of epoch seconds "
                                "before 2100")
        # fullmatch, not match: `$` also matches before a trailing newline (P141).
        if not isinstance(self.model, str) or not MODEL_ID.fullmatch(self.model):
            raise ContractError(
                f"model must be config@12-hex-digest or persistence@12-hex-digest. "
                f"It names the verified graph or the frozen "
                f"persistence spec, and nothing else.")

    def to_state_values(self, lanes: tuple[str, ...] = ("N", "S", "E", "W")) -> list[float]:
        """D6. PPO state indices 11–14, in lane order — **only if every lane is
        forecast**.

        P97a (Option A, P109): a missing lane used to become 0.0, which is
        also LOW, so "no forecast" and "forecast says clear" were the same
        number. It is now refused. A caller must handle absence explicitly:
        `to_state_values_or_none` for display, or the controller's own absence
        encoding (ADR-020 as amended), never an implicit zero.
        """
        missing = [l for l in lanes if l not in self.predictions]
        if missing:
            raise ContractError(
                f"no forecast for {missing}. A missing approach is not LOW, so it "
                f"has no state value; handle absence explicitly (P97a, ADR-020).")
        return [self.predictions[l].to_state_value() for l in lanes]

    def to_state_values_or_none(
            self, lanes: tuple[str, ...] = ("N", "S", "E", "W")) -> list[float | None]:
        """The same values, with `None` where an approach has no forecast. For
        display and APIs only, where absence must stay visible (P97a)."""
        return [self.predictions[l].to_state_value() if l in self.predictions else None
                for l in lanes]

    def encode(self) -> str:
        d = {
            "predictions": {k: v.value for k, v in self.predictions.items()},
            "confidences": dict(self.confidences),
            "gate_value": self.gate_value,
            "model": self.model,
            "horizon_sec": self.horizon_sec,
            "ts": self.ts,
            "v": SCHEMA_VERSION,
        }
        text = json.dumps(d, separators=(",", ":"))
        _bounded(type(self).__name__, text)
        return text


@dataclass(frozen=True)
class CountForecast(_Payload):
    """ADR-027: each approach's forecast mean vehicle count over the next 60 s.

    A point estimate from the frozen ridge model, not a congestion class and
    not a guarantee. An approach the edge cannot forecast is **absent**, never
    zero: zero vehicles is a forecast, a missing approach is not.
    """

    counts: Mapping[str, float]
    model: str
    horizon_sec: int = 60
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.counts:
            raise ContractError("a count forecast must cover at least one approach")
        # P141: as for CongestionPrediction, no message quotes a submitted key
        # or value, and `ts` is typed — it was the one field left unchecked.
        if set(self.counts) - set(APPROACHES):
            raise ContractError(
                f"count keys must be approaches {list(APPROACHES)}. "
                f"Map keys are text too (NFR-13).")
        if not all(_finite_number(v) and 0.0 <= v <= MAX_LANE_COUNT
                   for v in self.counts.values()):
            raise ContractError(
                f"every forecast count must be a finite number in "
                f"[0, {MAX_LANE_COUNT:.0f}]")
        if not isinstance(self.model, str) or not COUNT_MODEL_ID.fullmatch(self.model):
            raise ContractError(
                "model must be ridge@12-hex-digest. It names the frozen "
                "count-forecaster spec and nothing else.")
        if _not_an_int(self.horizon_sec) or self.horizon_sec != 60:
            raise ContractError("horizon_sec must be the integer 60 (P105's target)")
        if not _valid_ts(self.ts):
            raise ContractError("ts must be a positive, finite number of epoch seconds "
                                "before 2100")


#: D22: what the edge is counting from. A `camera` is a live stream; a `replay`
#: is a recorded clip, and the dashboard must never present one as live.
SOURCE_KINDS = ("camera", "replay")
SOURCE_KEYS = frozenset({"kind", "session", "label", "position_s", "duration_s"})
#: One edge run. A new session replaces the old one whatever its `ts`, so a
#: restart or a clock step cannot leave the last run's clip position showing.
SESSION = re.compile(r"[0-9a-f]{12}")


def _check_source(source: Any) -> None:
    """D22. No message quotes a submitted value (P141). The label is held to
    the lane pattern, so it is a short code and never free text (NFR-13)."""
    if not isinstance(source, Mapping) or set(source) != SOURCE_KEYS:
        raise ContractError("source must carry exactly kind, session, label, "
                            "position_s and duration_s")
    if source["kind"] not in SOURCE_KINDS:
        raise ContractError("source kind must be 'camera' or 'replay'")
    if not isinstance(source["session"], str) or not SESSION.fullmatch(source["session"]):
        raise ContractError("source session must be 12 lowercase hex digits")
    if not isinstance(source["label"], str) or not LANE.fullmatch(source["label"]):
        raise ContractError("source label must be 1 to 32 characters from "
                            "A-Z, a-z, 0-9, '_' and '-'")
    position, duration = source["position_s"], source["duration_s"]
    if source["kind"] == "camera":
        if position is not None or duration is not None:
            raise ContractError("a camera has no clip position or duration")
        return
    if not (_finite_number(position) and position >= 0):
        raise ContractError("a replay's position_s must be a finite number of seconds, "
                            "at least 0")
    if duration is not None and not (_finite_number(duration) and 0 < duration
                                     and position <= duration):
        raise ContractError("a replay's duration_s must be unknown (null) or a finite "
                            "number of seconds, positive and not before position_s")


def _check_lanes(lanes: Any) -> None:
    """D22. One lane per approach, as both frozen forecasters were fitted and
    refuse anything else (`edge.persistence`, `edge.count_forecast`)."""
    if not isinstance(lanes, Mapping) or not 1 <= len(lanes) <= len(APPROACHES):
        raise ContractError(f"lanes must map 1 to {len(APPROACHES)} lanes to approaches")
    for lane, approach in lanes.items():
        check_lane(lane)
        if approach not in APPROACHES:
            raise ContractError(f"each lane must map to one of {list(APPROACHES)}")
    if len(set(lanes.values())) != len(lanes):
        raise ContractError("lanes must map to distinct approaches: one lane per "
                            "approach, as the frozen forecasters were fitted")


@dataclass(frozen=True)
class Heartbeat(_Payload):
    """Liveness, and since D22 what the edge is counting from.

    `source` and `lanes` ride on the message that proves liveness, as `mode`
    does (D3): a stale heartbeat then makes the source stale too, and nothing
    can report a source for an edge that has stopped. They are separate
    fields because they are different facts: the source moves during a
    replay, the lane map is configuration fixed for the session. Both are
    optional, so a producer that does not send them still decodes; a consumer
    reads their absence as unknown, never as a live camera.
    """

    edge_status: str
    mode: Mode
    mfstnet_active: bool
    ppo_active: bool
    ts: float = field(default_factory=time.time)
    source: Mapping[str, Any] | None = None
    lanes: Mapping[str, str] | None = None
    # ADR-028: whether direction evidence matches this camera's active configuration.
    # Absent reads as False: N, S, E and W are labels until someone has looked.
    directions_verified: bool = False

    def __post_init__(self) -> None:
        if self.edge_status not in ("online", "degraded"):
            raise ContractError(f"unknown edge_status {self.edge_status!r}")
        if not isinstance(self.mode, Mode):
            raise ContractError(
                f"mode must be a Mode, got {self.mode!r}. D3 — the dashboard cannot "
                f"display the active mode without it (FR-UI01, FR-UI08)."
            )
        # D22: the server orders heartbeats within a session by `ts`.
        if not _valid_ts(self.ts):
            raise ContractError("ts must be a positive, finite number of epoch seconds "
                                "before 2100")
        if self.source is not None:
            _check_source(self.source)
        if self.lanes is not None:
            _check_lanes(self.lanes)
        if not isinstance(self.directions_verified, bool):
            raise ContractError("directions_verified must be true or false")


CLASS_NAMES = tuple(c.value for c in CongestionClass)
PAIR_KEYS = frozenset({"forecast", "observed"})


def _edge_time(value: Any) -> bool:
    """D26: an edge sample time. Not epoch seconds: video seconds for a replay,
    a monotonic clock for a camera, comparable only within one session."""
    return _finite_number(value) and 0 <= value < TS_MAX


@dataclass(frozen=True)
class ForecastCheck(_Payload):
    """D26, ADR-014 §2: one forecast beside what it forecast, once known.

    The forecast was made after sample `made_ts`, for the mean of the next 30
    samples; `checked_ts` is the 30th of them. The edge pairs them by sample
    count in one contiguous window of one session, so every pair compares the
    same quantity (the forecasters' raw per-lane totals) over the minute the
    forecast was about. One pair per message, never a rate: the denominator is
    counted where it is shown. An approach either side could not supply is
    absent, never zero (P97a). Not accuracy: both sides come from the same
    detector's counts.
    """

    session: str
    made_ts: float
    checked_ts: float
    classes: Mapping[str, Mapping[str, str]]
    counts: Mapping[str, Mapping[str, float]]
    class_model: str | None = None
    count_model: str | None = None
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.session, str) or not SESSION.fullmatch(self.session):
            raise ContractError("session must be 12 lowercase hex digits")
        if not (_edge_time(self.made_ts) and _edge_time(self.checked_ts)
                and self.checked_ts > self.made_ts):
            raise ContractError("made_ts and checked_ts must be edge sample times, "
                                "checked after made")
        if not self.classes and not self.counts:
            raise ContractError("a check must compare at least one approach")
        for name, pairs, valid in (("classes", self.classes, lambda v: v in CLASS_NAMES),
                                   ("counts", self.counts,
                                    lambda v: _finite_number(v) and 0 <= v <= MAX_LANE_COUNT)):
            if not isinstance(pairs, Mapping) or set(pairs) - set(APPROACHES):
                raise ContractError(f"{name} keys must be approaches {list(APPROACHES)}")
            for pair in pairs.values():
                if not isinstance(pair, Mapping) or set(pair) != PAIR_KEYS \
                        or not all(valid(v) for v in pair.values()):
                    raise ContractError(f"each of {name} must hold a valid forecast and "
                                        f"observed value, and nothing else")
        # The model that made each side, and only when that side is present.
        if (self.class_model is None) != (not self.classes) or (
                self.class_model is not None and not (
                    isinstance(self.class_model, str) and MODEL_ID.fullmatch(self.class_model))):
            raise ContractError("class_model must name the class forecaster when, and "
                                "only when, classes are compared")
        if (self.count_model is None) != (not self.counts) or (
                self.count_model is not None and not (
                    isinstance(self.count_model, str) and COUNT_MODEL_ID.fullmatch(self.count_model))):
            raise ContractError("count_model must name the count forecaster when, and "
                                "only when, counts are compared")
        if not _valid_ts(self.ts):
            raise ContractError("ts must be a positive, finite number of epoch seconds "
                                "before 2100")


_PAYLOAD_FOR = {
    Topic.VEHICLE_COUNT: VehicleCount,
    Topic.EMERGENCY: EmergencyDetect,
    Topic.SIGNAL_COMMAND: SignalCommand,
    Topic.PREDICTION: CongestionPrediction,
    Topic.COUNT_FORECAST: CountForecast,
    Topic.HEARTBEAT: Heartbeat,
    Topic.FORECAST_CHECK: ForecastCheck,
}


def decode(topic: Topic, raw: str | bytes) -> Any:
    """Parse and validate a payload, checking the schema version first.

    Raises:
        ContractError: on a version mismatch or any validation failure.
    """
    _bounded(topic.name, raw)
    try:
        data: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError(f"{topic.name}: payload is not valid UTF-8 JSON — "
                            f"{type(exc).__name__}") from exc
    # Valid JSON is not yet a payload: `[]` or `null` parse, and `.pop` on
    # them raised AttributeError before any refusal could run (P140).
    if not isinstance(data, dict):
        raise ContractError(f"{topic.name}: payload must be a JSON object, "
                            f"got {type(data).__name__}")

    version = data.pop("v", None)
    if version is None:
        raise ContractError(
            f"{topic.name}: payload carries no 'v' field. Producer predates schema "
            f"v{SCHEMA_VERSION} — upgrade it rather than guessing the shape."
        )
    if version != SCHEMA_VERSION:
        # The submitted version is not quoted: this message is an HTTP 422 body,
        # and a refusal must not repeat what the sender wrote (P141).
        raise ContractError(
            f"{topic.name}: payload is not schema v{SCHEMA_VERSION}, which this "
            f"consumer speaks. Version mismatch, not malformed data — fix the "
            f"producer or the consumer, do not coerce."
        )

    cls = _PAYLOAD_FOR[topic]
    # The enum conversions belong inside the refusal too (P140). Outside it, an
    # unknown class or a missing field raised ValueError or KeyError, which the
    # server answered with 500 and the MQTT ingest let escape into paho's thread.
    # ContractError is itself a ValueError, so one raised by a payload's own
    # validation passes through unchanged.
    try:
        if cls is CongestionPrediction:
            data["predictions"] = {k: CongestionClass(v) for k, v in data["predictions"].items()}
        elif cls is Heartbeat:
            data["mode"] = Mode(data["mode"])
        elif cls is SignalCommand:
            data["source"] = CommandSource(data["source"])
        return cls(**data)
    except ContractError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
        # OverflowError (P141): a JSON integer beyond float range raises it in
        # any float comparison or conversion, and it is not a ValueError.
        # The type only: the exception's own text can quote the offending
        # value, and this message reaches HTTP responses. `from exc` keeps the
        # detail for anyone debugging in-process.
        raise ContractError(f"{topic.name}: payload does not match the schema — "
                            f"{type(exc).__name__}") from exc
