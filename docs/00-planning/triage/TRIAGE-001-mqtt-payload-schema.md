# Triage 001 — MQTT Payload Schema Defects

| | |
|---|---|
| **Date** | 2026-08-10 |
| **Reporter** | Internal review |
| **Issue type** | **Bug** — defect in the specification artifact |
| **Severity** | **Medium** |
| **Reproducibility** | **Always** — deterministic; inspect PRD §17.1 |

---

## Summary

PRD §17.1's MQTT payload schemas contain six under-specifications that will surface as integration
failures in Weeks 17–19, when three subsystems built by different owners in different weeks first
exchange messages.

## The original hypothesis was wrong — state that first

The issue was raised as *"payload schemas never verified against the A16 state-vector change; possible
contract mismatch."*

**There is no A16 mismatch.** A16 removed `mfst_gate_mean` from the **PPO state vector**, which is an
in-process Python array on the server. It did not touch the MQTT payload, and the payload's
`gate_value` field is consumed by the **dashboard** (FR-UI05, BR-07), which still needs it. The two
are independently correct.

One derived risk does follow: a reader who sees "A16 removed the gate" may delete `gate_value` from
the prediction payload as well, silently breaking FR-UI05. That warrants a note in the PRD, not a
schema change.

Verifying the hypothesis, however, surfaced six real defects that have nothing to do with A16.

## Reported behaviour

PRD §17.1 defines five topics with example payloads. Read against the requirements that consume them:

| # | Defect | Evidence | Consumer affected |
|---|---|---|---|
| **D1** | **Class name mismatch.** Payload emits `"MED"`; PRD §14.1 and §8.6 define the class as `MEDIUM` | `"predictions": {"N":"HIGH","S":"MED",...}` vs §14.1 `LOW / MEDIUM / HIGH` | Dashboard, PPO adapter, event log — each will guess independently |
| **D2** | **`types` is literally unspecified.** The schema shows `"types": {...}` | `{ "count": 12, "types": {...}, "fps": 12.4 }` | FR-P02 (per-lane counts), FR-UI01 (live display) |
| **D3** | **No operating-mode field.** SRS §2.3 defines five modes (M-NORMAL, M-NO-PREDICT, M-LOCAL, M-PREEMPT, M-MANUAL) with a precedence order; heartbeat carries only two booleans | `{"edge_status":"online","mfstnet_active":true,"ppo_active":true}` | FR-UI01, FR-UI08 — the dashboard cannot show which mode is active |
| **D4** | **`source` enum incomplete.** FR-UI08 requires the event log to record four sources; the schema shows one | `"source": "ppo_agent"` vs FR-UI08's `ppo_agent / webster_fallback / emergency / manual` | FR-UI08 |
| **D5** | **No schema version on any payload.** Three consumers built weeks apart, no runtime way to detect a producer/consumer mismatch | All five topics | All |
| **D6** | **String→int mapping unspecified.** Predictions arrive as strings; the PPO state needs `mfst_pred/2` numerics | `"HIGH"` → `2` → `1.0` is implied nowhere | FR-M14, FR-R02 |

A seventh observation, not a defect: `confidences` appears in the prediction payload with no declared
consumer in any FR. Either give it one or remove it — an unowned field is a field someone will
misuse.

## Expected behaviour

Each payload field has exactly one spelling, one type, one declared producer, and at least one
declared consumer traceable to an FR. A consumer receiving a payload from an incompatible producer
detects it rather than mis-parsing it.

## Missing information

None from a reporter — this is a static-artifact defect and all evidence is cited above. What is
missing is **decisions**, not facts:

1. Canonical class-label spelling: `MEDIUM` everywhere, or `MED` on the wire with a documented map?
2. The `types` object's exact keys — the eight PRD §12.2 classes, or a subset?
3. Whether the mode field goes on `heartbeat` (10 s) or a new retained `system/mode` topic — mode
   changes are events, and 10 s is slow for a preemption indicator.
4. Schema versioning mechanism — a `"v": 1` field on every payload is the cheapest option.

## Suspected areas

- `edge/` — publishes counts, emergency, heartbeat
- `server/` — publishes predictions and signal commands; hosts the PPO state adapter (D6)
- `dashboard/` — consumes predictions, heartbeat, event log
- PRD §17.1, SRS §3.1 — the contract documents themselves

## Why this matters more than it looks

The integration window is Weeks 17–19, and PRD §2.5.1 already predicts trouble there. Every defect
above is invisible until two subsystems meet, and each is a fifteen-minute fix **now** versus a
half-day of cross-owner debugging **then**, with no schedule slack left.

D5 is the compounding one: without a version field, every other mismatch presents as malformed data
rather than as a version error.

## Recommended next step

`/plan-a-feature` scoped to the MQTT contract.

**Deviation noted:** the triage rubric maps a Bug with sufficient evidence to `/investigate`. That
mapping assumes a running system to diagnose. No code exists; the investigation is complete and
recorded above. What remains is specifying the corrected contract, which is a feature-specification
task.

**Cheapest viable alternative:** skip the skill, apply the four decisions above as a PRD amendment,
and write the contract test in Week 7 as PLAN-01 already schedules. Roughly one hour.
