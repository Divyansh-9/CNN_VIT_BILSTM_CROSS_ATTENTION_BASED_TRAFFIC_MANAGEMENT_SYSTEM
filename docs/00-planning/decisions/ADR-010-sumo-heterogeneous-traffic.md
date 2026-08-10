# ADR-010 — Heterogeneous, Non-Lane-Disciplined Traffic in SUMO

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-10 |
| **Affects** | PRD §13.1 (reward), FR-S01, FR-S02, FR-S04, M3; RELATED-WORK claims C1 and C4 |
| **Cost** | ~+15–25 person-hours, previously unbudgeted |

## Context

The project's entire framing is **unstructured, heterogeneous, non-lane-disciplined Indian traffic**.
That premise justifies IndiaTrafficNet, the eight-class taxonomy, the auto-rickshaw and cattle
classes, and PRD §14.2's hypothesis that CNN detail and ViT context are complementary in dense
chaotic scenes.

SUMO's default car-following and lane-changing models assume the opposite: vehicles occupy discrete
lanes, maintain lane discipline, and change lanes discretely. The reward function in PRD §13.1 uses
`traci.lane.getLastStepHaltingNumber`, a **per-lane** measure that presupposes lane discipline.

So the vision half of the paper is trained on heterogeneous reality while the control half is
evaluated in a homogeneous lane-world. The two halves describe different traffic. An ITSC reviewer
asks about this in the first round, and there is no good answer available in Week 19.

Nothing in the suite currently addresses it. FR-S02 calibrates *arrival rates* from real counts —
that is traffic **volume**, not traffic **behaviour**. Matching volume while modelling behaviour
wrongly is arguably worse than not calibrating, because it looks calibrated.

## Decision

Model heterogeneity in SUMO at the level of effort the schedule can absorb, and declare the residual
gap explicitly.

### 1. Enable the sublane model

SUMO supports continuous lateral positioning via `--lateral-resolution`, which permits sub-lane
occupancy, lateral overtaking, and two-wheelers filtering alongside larger vehicles — the defining
behaviour of the traffic being modelled.

```xml
<!-- simulation/configs/intersection.sumocfg -->
<processing>
  <lateral-resolution value="0.8"/>
</processing>
```

### 2. Heterogeneous vehicle types

Replace the single default `vType` with the mix from PRD §12.2, with realistic dimensions,
acceleration, and lateral behaviour. Proportions come from IndiaTrafficNet class distribution, so
this is calibrated to the same data as FR-S02 rather than invented.

```xml
<vType id="motorcycle"    vClass="motorcycle" length="2.0" width="0.8"
       accel="3.0" decel="5.0" maxSpeed="16" latAlignment="arbitrary"
       lcSublane="1.0" minGapLat="0.2"/>
<vType id="auto_rickshaw" vClass="passenger"  length="2.6" width="1.4"
       accel="2.0" decel="4.0" maxSpeed="14" latAlignment="arbitrary"
       lcSublane="0.8" minGapLat="0.3"/>
<vType id="car"           length="4.3" width="1.8" accel="2.6" decel="4.5" maxSpeed="20"/>
<vType id="bus"           vClass="bus"   length="12.0" width="2.5" accel="1.2" decel="4.0"/>
<vType id="truck"         vClass="truck" length="7.1"  width="2.4" accel="1.3" decel="4.0"/>
```

Distribution proportions are a config value, not a literal in the network file (NFR-16), so a
recalibration after Week 8 is a config edit.

### 3. Reward measures stay lane-based, and that is stated

`getLastStepHaltingNumber` remains the queue term. Under the sublane model it still counts halting
vehicles assigned to a lane, so it is well-defined — but with filtering two-wheelers it undercounts
effective occupancy relative to what a camera sees.

Rather than invent a new measure, the reward is unchanged and the discrepancy is **documented as a
limitation**. Inventing an unvalidated congestion measure to fix a documented gap would be a larger
methodological risk than the gap itself.

### 4. Sensitivity check, not a full validation

Run the Fixed baseline under (a) default lane-disciplined SUMO and (b) the sublane heterogeneous
configuration. Report the delta in mean wait time.

This costs one afternoon and answers the reviewer's question with evidence: *"heterogeneity changes
baseline wait time by X%, and all methods were evaluated under the heterogeneous configuration."*
Without it, the answer is an assurance.

## Consequences

**Positive.** The two halves of the paper describe the same traffic. C1 and C4 become defensible
under questioning. The sensitivity check turns the most obvious reviewer objection into a reported
result, which is a much stronger position than a limitation paragraph alone.

**Negative — and this is real.** ~15–25 person-hours that the feasibility audit's 70-hour SUMO line
did not include, against a plan already over capacity. The audit's revised total moves from ~870 to
~890 hours. If ADR-006 and ADR-008 are declined, this is one of the first things to cut back to
"vTypes only, no sublane" — which is roughly 5 hours and still better than nothing.

**Negative.** The sublane model is slower to simulate. With 120 evaluation episodes plus three PPO
training arms (ADR-009), wall-clock matters. Measure the slowdown on one episode before committing to
the full protocol; if it exceeds ~2×, reduce `lateral-resolution` to 1.6 and record the change.

**Negative.** Calibrating five vehicle types against real proportions is more work than one, and
proportions come from IndiaTrafficNet, which under ADR-006 is smaller. Use the curated Part A
distribution for proportions and note the source.

## Alternatives considered

**Do nothing; declare the limitation.** Zero cost. Rejected as the sole response: the mismatch goes
to the heart of the framing, and "we know our simulator does not model the traffic our paper is
about" is a weak position when the fix is a configuration flag and five `vType` definitions.

**vTypes only, no sublane model.** ~5 hours. Captures size and acceleration heterogeneity but not
filtering or lateral overtaking. **Retained as the fallback** if capacity does not permit the full
change.

**Switch simulator (e.g. to a mesoscopic or agent-based tool with native disorder).** Rejected
outright — SUMO is what the comparable literature uses (PressLight, MPLight, RESCO), and
comparability is worth more than fidelity here. Changing simulators in Week 10 would also discard
every hour already spent.
