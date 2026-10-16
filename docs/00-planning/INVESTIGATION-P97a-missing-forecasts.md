# P97a investigation — a missing forecast reads as LOW in the controller's state

**Date:** 2026-10-16 · **Status:** investigation complete; **decision pending
with the project owner** · **No code changed by this investigation.**
Related: [ADR-020](decisions/ADR-020-forecast-staleness-channel.md) (Proposed, not
implemented), [ADR-021](decisions/ADR-021-forecast-quality-as-a-swept-variable.md),
[ADR-027](decisions/ADR-027-forecasting-roles.md), P52, P53, P97a in the
[changelog](PRD-CHANGELOG.md).

## The defect, stated exactly

The policy's state carries one congestion class per approach at indices 11–14,
encoded `{LOW, MEDIUM, HIGH} → {0.0, 0.5, 1.0}` (`mfst_pred_divisor: 2`).
When a forecast is unavailable, the same indices are set to **0.0**. So
**"no forecast" and "forecast says LOW" are the same number.**

At the moment the forecast has failed, the policy is told every affected
approach is clear: the most optimistic value the encoding can express. ADR-020
identified this on 2026-08-21. Nothing has implemented a fix since.

## Where the 0.0 is produced, and who consumes it

| location | what it does with a missing forecast | consumed by |
|---|---|---|
| `mfstnet/configs/spec.yaml:30-53` | `dim: 16`; `mfst_pred_divisor: 2`; `zero_when_mfstnet_unavailable: [11, 12, 13, 14]`. **The spec mandates the zero** | everything below, via `simulation/contract.py` (P53 digest) |
| `contracts/mqtt.py` `CongestionPrediction.to_state_values` | an approach absent from the payload becomes **0.0**, documented as FR-A06 | the server's two prediction responses |
| `server/app.py` `POST /prediction/{id}`, `GET /prediction/{id}/latest` | **publish `state_11_14`**, with 0.0 for an absent approach (seen live in P107: `[1.0, 0.0, 0.5, 0.0]` with S absent) | **no code consumer.** The dashboard deliberately ignores it, but any future client could adopt it |
| `simulation/envs/traffic_env.py:309-315` | indices 11–14 stay 0.0; `use_mfstnet=True` raises `NotImplementedError` | PPO training (all arms) |
| `simulation/ppo_controller.py` `observe()` | 11–14 always 0.0 (the `no-forecast` arm's world) | `scripts/benchmark.py` PPO arm |
| `server/app.py` `propose()` | **reads no forecast**: a counts-only placeholder policy | `POST /observation` |
| `server/app.py` `Counts.forecast`, `.forecast_age_s` | **declared, read by nothing** | none |
| tests | `test_mqtt_contract.py:187-197`, `test_ppo_controller.py:125` and `test_mqtt_live.py:174` **pin** the 0.0 (the last one says so: "S, indistinguishable from LOW") | CI |

## Current risk status: latent, and exposed in one place

- **No live path feeds a forecast into any controller.** The server's policy
  is a counts-only placeholder. The trained PPO controller always sees 0.0 at
  11–14. The environment refuses live forecasts. ADR-027 states that neither
  prototype forecast feeds the policy. So today, the defect cannot change a
  signal decision.
- **It becomes live the moment anyone connects a forecast** through
  `to_state_values()`, or through the `forecast` field that is already on
  `Counts`. The path is half-built, and a natural next step would complete it
  with the defect intact.
- **It is already exposed as data:** `state_11_14` in the server's responses
  publishes the ambiguous encoding to any client.

## What has changed since ADR-020 was written

1. **There is now a full PPO checkpoint.** ADR-020 argued its fix was cheap
   because "zero final PPO checkpoints exist today." One does now:
   `ppo_no-forecast_saturated_keep_or_switch_seed42.zip`, 500,000 steps on CPU,
   observation contract `24ad1c994e844238`. Changing the state layout makes it
   refuse to load (the P53 mechanism, working as intended). It is the
   no-forecast arm, so its 11–14 were always 0.0. Under ADR-020's reserved-zero
   encoding those values would mean "absent" and stay 0.0. **Only the added age
   channel breaks it.**
2. **Absence is now per approach, not only per message.** ADR-020 assumed the
   four classes come from one MFSTNet pass and share one timestamp. Under
   ADR-027, an approach can be absent on its own: a camera that cannot see it
   (NE 8th's south approach, P96; Newport lane_2 behind the signal housing,
   P103) is never in the payload. ADR-020's **reserved zero** handles that per
   approach. Its **single shared age** still correctly covers staleness,
   because one payload has one timestamp.
3. **The forecast at 11–14 is no longer MFSTNet's.** The prototype's class
   forecast is persistence v1 (ADR-027). The index names `mfst_pred_*`
   describe a source, not a role.
4. **Training a forecast-aware policy is blocked anyway.** The `surrogate`
   arm is not implemented (P52), and ADR-021 says the perfect-forecast ceiling
   should run first. No forecast-aware PPO policy can exist until those land,
   so the encoding can be fixed **before** any checkpoint depends on it, as
   long as it is fixed first.

## Options

| | what | invalidates | fixes absent | fixes stale | effort |
|---|---|---|---|---|---|
| **A. API hygiene now** | `state_11_14` reports `null` for an absent approach (or is removed); `to_state_values` gains an explicit, named policy for absence, refusing rather than silently zero-filling | nothing (no code consumer) | in the API | no | small |
| **B. ADR-020 as written** | classes `{1,2,3}/3`, 0.0 reserved for absent; index 16 `forecast_age = min(age, 10)/10`, 1.0 when absent; `dim: 17` | the one no-forecast checkpoint (retrain about 500k CPU steps) | yes, per approach | yes | medium |
| **C. Fallback switching** | a forecast-aware policy runs only when every required forecast is present and fresh; otherwise the controller switches to the **no-forecast policy** (the existing checkpoint, trained on 0.0) or to Webster | nothing | by never encoding it | by switching on age | medium; partial absence (a permanently unseen approach) means the forecast-aware policy never runs at that junction |
| **D. B + C** | B's encoding, so absence is never ambiguous in any state, and C's switch as the safety net when a forecast is missing or stale beyond a bound | as B | yes | yes, twice | medium-large |

## Recommendation

1. **Now: Option A.** It is small and invalidates nothing. It removes the
   only place the ambiguous encoding is exposed today, and makes
   `to_state_values` refuse to zero-fill implicitly, so the half-built path
   cannot be completed with the defect intact.
2. **Before any forecast-aware PPO is trained: Option D.**
   - **Accept ADR-020's encoding** (reserved zero, plus the age channel),
     amended for ADR-027: absence is per approach, and indices 11–14 are named
     for their role, not for MFSTNet.
   - **Make the fallback switch the safety rule.** A forecast that is absent,
     or older than the 10 s PRD §7.2 bound, never drives a forecast-aware
     policy. The controller runs the no-forecast policy instead, so missing
     data never silently becomes a traffic observation.
   - **Retrain the one no-forecast checkpoint** under the new contract. It is
     the fallback policy, so it must exist under the same layout.

   This must precede P52's surrogate arm and ADR-021's ceiling run, which are
   the first things that would train against forecasts.
3. **Keep the controller disconnected from signal timing** until the
   evaluation below passes. The rule matches ADR-027's.

## Evaluation to pre-register before implementing Option D

1. **Contract tests:**
   - an absent approach can never encode as a valid class;
   - the age channel is 1.0 when absent, 0.0 when fresh, and monotone in
     between;
   - the P53 digest changes;
   - every old checkpoint refuses to load.
2. **Propagation tests:** a forecast missing or stale at the edge reaches the
   policy's state as absent or stale, through MQTT → server → controller, and
   never as LOW. This is end to end, as P107 did for display.
3. **Fallback tests:** with a forecast absent or stale beyond 10 s, the
   decision is made by the no-forecast policy or Webster, and the switch is
   logged with its reason.
4. **Behaviour in simulation, pre-registered:** run the existing benchmark
   (30 seeds) with forecast dropout and staleness injected at fixed rates.
   - **Safety criterion:** the controller with the fallback is **never
     significantly worse** than the no-forecast policy alone on delay and
     starvation (paired, Holm), at every dropout rate.
   - **This shows safety, not benefit.** Benefit is ADR-021's ceiling
     question.

## Decision needed from the project owner

- **Approve Option A now?** It is small, invalidates nothing, and removes the
  current exposure.
- **Accept Option D as the plan** to be pre-registered and implemented before
  any forecast-aware PPO training, including retraining the one no-forecast
  checkpoint?
- **ADR-020 status:** amend it for ADR-027 (per-approach absence,
  role-neutral index names) and move it to Accepted, or write a new ADR that
  supersedes it.
