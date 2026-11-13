"""The rules a signal command must satisfy before it leaves the server.

FR-A03 (min 10 s / max 90 s green), FR-A04 (all-red >= 3 s), FR-A05 (emergency
preemption within 3 s) and FR-A06 (Webster fallback within 10 s of an MQTT
dropout) are **Must Have** requirements about *actuation*, not about learning.
So they live here, in a module with no HTTP and no model in it, and the API
layer calls into them.

**Why not inside the policy.** `simulation/controllers.py` already states the
principle for the simulator: "safety clamping, yellow and all-red live in the
runner, so no controller -- learned or otherwise -- can produce an unsafe
program." The deployed path needs the same guarantee for the same reason, and a
PPO policy is exactly the kind of component that will eventually request a
2-second green because a reward surface said so.

**Why a separate module from the app.** A rule that can only be exercised by
starting a web server is a rule that gets tested once. Everything here is a
plain function over plain data, so the FR-A0x behaviours can be tested directly
and the API is left with routing.

`NFR-13`: nothing in this module accepts or returns a frame. Counts and
predictions only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["SafetyLimits", "Decision", "SignalGuard"]

NS, EW = "NS", "EW"
OPPOSITE = {NS: EW, EW: NS}


@dataclass(frozen=True)
class SafetyLimits:
    """PRD §9.6 and FR-A03..A06. Values, not literals scattered in handlers."""

    min_green_s: int = 10          # FR-A03
    max_green_s: int = 90          # FR-A03
    all_red_s: int = 3             # FR-A04
    emergency_response_s: int = 3  # FR-A05
    mqtt_timeout_s: int = 10       # FR-A06


@dataclass(frozen=True)
class Decision:
    """What the server tells the edge node to do, and why.

    `reason` is not decoration. When a signal does something surprising, the
    question is always which rule fired, and an answer reconstructed afterwards
    from logs is a guess. It travels with the command.
    """

    phase: str
    green_s: int
    all_red_s: int
    source: str                    # policy | webster | emergency | hold
    reason: str
    clamped: bool = False


@dataclass
class SignalGuard:
    """Applies the actuation rules to whatever the policy proposed.

    Holds only the state the rules need: which phase is green, how long it has
    been, and when a forecast and a heartbeat were last seen.
    """

    limits: SafetyLimits = field(default_factory=SafetyLimits)
    phase: str = NS
    elapsed_s: float = 0.0

    def clamp(self, green_s: float) -> tuple[int, bool]:
        """FR-A03. Returns the permitted green and whether it was changed."""
        bounded = max(self.limits.min_green_s,
                      min(self.limits.max_green_s, int(round(green_s))))
        return bounded, bounded != int(round(green_s))

    def decide(
        self,
        *,
        proposed_phase: str,
        proposed_green_s: float,
        emergency_approach: str | None = None,
        seconds_since_heartbeat: float = 0.0,
        webster_green_s: float | None = None,
    ) -> Decision:
        """One decision, with every rule applied in priority order.

        The order is the requirement order and it is not arbitrary:

        1. **Emergency (FR-A05)** outranks everything, including the minimum
           green. A minimum-green rule that delays an ambulance is a rule
           applied to the wrong thing.
        2. **Fallback (FR-A06)** — if the heartbeat is older than the timeout,
           the policy's proposal is not trusted and Webster runs instead.
        3. **Minimum green (FR-A03)** — a switch requested before the minimum
           has elapsed is held, not honoured.
        4. **Clamp (FR-A03)** — whatever survives is bounded.
        """
        limits = self.limits

        if emergency_approach is not None:
            phase = NS if emergency_approach.upper() in ("N", "S") else EW
            return Decision(
                phase=phase,
                green_s=limits.min_green_s,
                all_red_s=(limits.all_red_s if phase != self.phase else 0),
                source="emergency",
                reason=(f"FR-A05: emergency on approach "
                        f"{emergency_approach.upper()} preempts the policy; "
                        f"cleared within {limits.emergency_response_s}s"),
            )

        if seconds_since_heartbeat > limits.mqtt_timeout_s:
            green = (webster_green_s if webster_green_s is not None
                     else limits.min_green_s * 2)
            bounded, clamped = self.clamp(green)
            return Decision(
                phase=OPPOSITE[self.phase],
                green_s=bounded,
                all_red_s=limits.all_red_s,
                source="webster",
                reason=(f"FR-A06: no heartbeat for "
                        f"{seconds_since_heartbeat:.1f}s, over the "
                        f"{limits.mqtt_timeout_s}s timeout; policy output is "
                        f"not trusted"),
                clamped=clamped,
            )

        wants_switch = proposed_phase != self.phase
        if wants_switch and self.elapsed_s < limits.min_green_s:
            remaining = limits.min_green_s - self.elapsed_s
            return Decision(
                phase=self.phase,
                green_s=int(round(remaining)),
                all_red_s=0,
                source="hold",
                reason=(f"FR-A03: switch requested after {self.elapsed_s:.0f}s, "
                        f"below the {limits.min_green_s}s minimum green"),
                clamped=True,
            )

        bounded, clamped = self.clamp(proposed_green_s)
        return Decision(
            phase=proposed_phase,
            green_s=bounded,
            all_red_s=limits.all_red_s if wants_switch else 0,
            source="policy",
            reason=("policy proposal within limits" if not clamped else
                    f"FR-A03: policy proposed {proposed_green_s:.0f}s, "
                    f"clamped to [{limits.min_green_s}, {limits.max_green_s}]"),
            clamped=clamped,
        )

    def apply(self, decision: Decision) -> None:
        """Advance the guard's own state after a decision is actuated."""
        if decision.phase != self.phase:
            self.phase = decision.phase
            self.elapsed_s = 0.0
        else:
            self.elapsed_s += decision.green_s
