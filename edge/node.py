"""The edge node: capture, count, publish, and fall back on its own (S40).

    python -m edge.node --source "clip.mp4" --lanes data/lanes_reviewed/x.json

**No frame ever leaves this process** (NFR-13). Frames are read, counted, and
dropped. The only things published are a per-lane count and a heartbeat, and
`contracts/mqtt.py` is the only place a payload shape is defined — this module
constructs those types rather than dictionaries, so a malformed publish is a
`ContractError` here rather than a puzzle at the far end.

**The transport is an interface, not a broker.** `Transport` has two methods,
and `RecordingTransport` implements them into a list. The consequence is that
FR-A06's fallback behaviour — the thing that actually matters about this file —
is testable without Mosquitto, a network, or a sleep. A fallback that can only
be exercised by unplugging something is a fallback nobody exercises.

**FR-A06 is decided here, on the edge, and that is the point.** When the link to
the server drops, the node stops waiting for commands and runs a locally
embedded Webster cycle. It cannot ask the server whether the server is reachable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from contracts.mqtt import (CongestionPrediction, Heartbeat, Mode, Topic,
                            VehicleCount)

__all__ = ["Transport", "RecordingTransport", "EdgeNode", "LocalWebster"]

DEFAULT_TIMEOUT_S = 10.0        # FR-A06


class Transport(Protocol):
    """What the node needs from a link. Two methods, so a fake is three lines."""

    def publish(self, topic: str, payload: str, qos: int) -> None: ...

    def connected(self) -> bool: ...


@dataclass
class RecordingTransport:
    """A transport that records instead of sending.

    Not a test double bolted on afterwards — it is how the fallback is tested at
    all. `up` is flipped directly to simulate a dropped link, which is the one
    condition FR-A06 exists for and the one hardest to produce with a real
    broker.
    """

    up: bool = True
    sent: list[tuple[str, str, int]] = field(default_factory=list)

    def publish(self, topic: str, payload: str, qos: int) -> None:
        if not self.up:
            raise ConnectionError("link down")
        self.sent.append((topic, payload, qos))

    def connected(self) -> bool:
        return self.up

    def topics(self) -> list[str]:
        return [topic for topic, _, _ in self.sent]


@dataclass
class LocalWebster:
    """The cycle the node runs when it is on its own (FR-A06).

    Deliberately fixed-time rather than a re-derived Webster: the node has lost
    its link, so it has no measured saturation flow to solve with and no way to
    know whether its own counts are still being consumed. A known, safe,
    unsurprising cycle is the right behaviour for a degraded mode — and it is
    what the PRD's Webster reduces to when nothing is being optimised.
    """

    green_s: int = 30
    phase: str = "NS"

    def step(self) -> tuple[str, int]:
        self.phase = "EW" if self.phase == "NS" else "NS"
        return self.phase, self.green_s


@dataclass
class EdgeNode:
    """Counts in, publishes out, falls back when the link goes.

    `last_ack` is the only piece of link state kept. It is updated when a
    publish succeeds, and FR-A06's timeout is measured against it — so a node
    that cannot publish notices, which is the case a heartbeat sent *by* the
    node could never cover.
    """

    intersection_id: str
    transport: Transport
    timeout_s: float = DEFAULT_TIMEOUT_S
    webster: LocalWebster = field(default_factory=LocalWebster)
    last_ack: float = field(default_factory=time.time)
    mode: Mode = Mode.NORMAL       # LOCAL once FR-A06 fires
    # True once a prediction has been published (ADR-026). Reported in the
    # heartbeat from what the node has DONE, not from configuration, so a
    # forecaster that is loaded but never produced output does not read as
    # active on the dashboard.
    forecasting: bool = False

    def publish_counts(self, lane: str, types: dict[str, int], fps: float,
                       now: float | None = None) -> bool:
        """One lane's counts. Returns whether the link took it.

        The payload is a `VehicleCount`, so a per-class breakdown that does not
        sum to the total raises here rather than reaching a consumer that
        cannot tell which number to trust.
        """
        now = time.time() if now is None else now
        payload = VehicleCount(count=sum(types.values()), types=types, fps=fps)
        topic = Topic.VEHICLE_COUNT.render(self.intersection_id, lane)
        try:
            self.transport.publish(topic, payload.encode(),
                                   Topic.VEHICLE_COUNT.qos)
        except (ConnectionError, OSError):
            return False
        self.last_ack = now
        return True

    def publish_prediction(self, prediction: CongestionPrediction,
                           now: float | None = None) -> bool:
        """This junction's forecast: MFSTNet's (ADR-026) or persistence's
        (P104). Returns whether the link took it. QoS comes from the topic,
        never from the caller."""
        now = time.time() if now is None else now
        topic = Topic.PREDICTION.render(self.intersection_id)
        try:
            self.transport.publish(topic, prediction.encode(),
                                   Topic.PREDICTION.qos)
        except (ConnectionError, OSError):
            return False
        self.last_ack = now
        # `mfstnet_active` must mean MFSTNet: a persistence forecast (P104)
        # is published like any other, but it is not the model running.
        if not prediction.model.startswith("persistence@"):
            self.forecasting = True
        return True

    def publish_heartbeat(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        payload = Heartbeat(
            edge_status="degraded" if self.degraded(now) else "online",
            mode=self.mode,
            # ADR-026 moved MFSTNet here from the server (NFR-13: its input
            # is frames). The policy stays on the server, so PPO is never
            # active on the edge.
            mfstnet_active=self.forecasting,
            ppo_active=False)
        topic = Topic.HEARTBEAT.render(self.intersection_id)
        try:
            self.transport.publish(topic, payload.encode(), Topic.HEARTBEAT.qos)
        except (ConnectionError, OSError):
            return False
        return True

    def seconds_since_ack(self, now: float | None = None) -> float:
        return (time.time() if now is None else now) - self.last_ack

    def degraded(self, now: float | None = None) -> bool:
        """FR-A06: has the link been silent longer than the timeout?"""
        return self.seconds_since_ack(now) > self.timeout_s

    def tick(self, lane_counts: dict[str, dict[str, int]], fps: float,
             now: float | None = None) -> dict:
        """One cycle: publish what was counted, and decide who is driving.

        Returns what the node did, including `mode`, so a caller — or a test —
        can see the transition rather than infer it.
        """
        now = time.time() if now is None else now
        delivered = [lane for lane, types in lane_counts.items()
                     if self.publish_counts(lane, types, fps, now)]
        self.publish_heartbeat(now)

        if self.degraded(now):
            self.mode = Mode.LOCAL
            phase, green = self.webster.step()
            return {"mode": self.mode, "delivered": delivered,
                    "phase": phase, "green_s": green,
                    "reason": (f"FR-A06: no successful publish for "
                               f"{self.seconds_since_ack(now):.1f}s, over the "
                               f"{self.timeout_s:.0f}s timeout; running the "
                               f"locally embedded cycle")}

        self.mode = Mode.NORMAL
        return {"mode": self.mode, "delivered": delivered,
                "phase": None, "green_s": None,
                "reason": "link healthy; the server is driving"}
