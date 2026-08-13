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
]

SCHEMA_VERSION = 1
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
    HEARTBEAT = ("stms/{id}/system/heartbeat", QoS.AT_MOST_ONCE)

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
        """D6. Class to the normalised value at PPO state indices 11–14.

        PRD §13.1 divides by 2 so the highest class maps to 1.0. Defined once,
        here, because the mapping crosses a process boundary — the dashboard and
        the PPO adapter both consume the same string.
        """
        return {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0}[self.value]


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

@dataclass(frozen=True)
class _Payload:
    def encode(self) -> str:
        d = {k: (v.value if isinstance(v, Enum) else v) for k, v in asdict(self).items()}
        d["v"] = SCHEMA_VERSION
        return json.dumps(d, separators=(",", ":"))


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
    gate_value: float
    model: str
    horizon_sec: int = 60
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if set(self.predictions) != set(self.confidences):
            raise ContractError("predictions and confidences must cover the same lanes")
        for lane, cls in self.predictions.items():
            if not isinstance(cls, CongestionClass):
                raise ContractError(
                    f"lane {lane}: prediction must be a CongestionClass, got {cls!r}. "
                    f"D1 — the wire spelling is MEDIUM, never MED."
                )
        if not 0.0 <= self.gate_value <= 1.0:
            raise ContractError(f"gate_value must be in [0, 1], got {self.gate_value}")

    def to_state_values(self, lanes: tuple[str, ...] = ("N", "S", "E", "W")) -> list[float]:
        """D6. PPO state indices 11–14, in lane order.

        A missing lane yields 0.0 — the same value FR-A06 requires when MFSTNet
        is unavailable. **Never shorten the list**: the vector's dimensionality is
        a contract, and changing it invalidates every trained checkpoint.
        """
        return [
            self.predictions[l].to_state_value() if l in self.predictions else 0.0
            for l in lanes
        ]

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
        return json.dumps(d, separators=(",", ":"))


@dataclass(frozen=True)
class Heartbeat(_Payload):
    edge_status: str
    mode: Mode
    mfstnet_active: bool
    ppo_active: bool
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.edge_status not in ("online", "degraded"):
            raise ContractError(f"unknown edge_status {self.edge_status!r}")
        if not isinstance(self.mode, Mode):
            raise ContractError(
                f"mode must be a Mode, got {self.mode!r}. D3 — the dashboard cannot "
                f"display the active mode without it (FR-UI01, FR-UI08)."
            )


_PAYLOAD_FOR = {
    Topic.VEHICLE_COUNT: VehicleCount,
    Topic.EMERGENCY: EmergencyDetect,
    Topic.SIGNAL_COMMAND: SignalCommand,
    Topic.PREDICTION: CongestionPrediction,
    Topic.HEARTBEAT: Heartbeat,
}


def decode(topic: Topic, raw: str | bytes) -> Any:
    """Parse and validate a payload, checking the schema version first.

    Raises:
        ContractError: on a version mismatch or any validation failure.
    """
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{topic.name}: payload is not valid JSON — {exc}") from exc

    version = data.pop("v", None)
    if version is None:
        raise ContractError(
            f"{topic.name}: payload carries no 'v' field. Producer predates schema "
            f"v{SCHEMA_VERSION} — upgrade it rather than guessing the shape."
        )
    if version != SCHEMA_VERSION:
        raise ContractError(
            f"{topic.name}: payload is schema v{version}, this consumer speaks "
            f"v{SCHEMA_VERSION}. Version mismatch, not malformed data — fix the "
            f"producer or the consumer, do not coerce."
        )

    cls = _PAYLOAD_FOR[topic]
    if cls is CongestionPrediction:
        data["predictions"] = {k: CongestionClass(v) for k, v in data["predictions"].items()}
    elif cls is Heartbeat:
        data["mode"] = Mode(data["mode"])
    elif cls is SignalCommand:
        data["source"] = CommandSource(data["source"])

    try:
        return cls(**data)
    except TypeError as exc:
        raise ContractError(f"{topic.name}: payload does not match the schema — {exc}") from exc
