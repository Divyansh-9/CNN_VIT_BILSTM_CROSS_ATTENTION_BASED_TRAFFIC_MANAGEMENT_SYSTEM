# P121 — pre-registration: tuning Webster on `pulsed`

**Committed before:**
- the tuning script runs;
- any Webster episode on `pulsed` exists.

**Why.** ADR-021 Amendment 1 (A1.6) compares PPO against **Webster's best**
configuration on the scenario it is evaluated on. ADR-012 forbids choosing a
saturation flow by assertion: the published range is swept, and the best
configuration that genuinely runs the method is the baseline. The existing
sweep was run on the constant `saturated` regime and selected by mean wait. It
does not transfer to `pulsed`.

## Search space (ADR-012, fixed now)

| parameter | values | source |
|---|---|---|
| saturation flow (pcu/h/m) | 525, 600, 660, 750, 900, 1050, 1283 | ADR-012 §1 |
| start-up lost time (s) | 0, 4 | ADR-012 §3: 4–5 s field value, with 0 s as an endpoint |

That gives **14 configurations**.

**Every other `Webster` parameter stays at its committed default.** That
includes:
- the 120 s observation window;
- the 32–192 s cycle clamps;
- the 10–90 s green bounds;
- the 3 s yellow and 3 s all-red.

## Episodes

- **Harness:** `run_episode` on `pulsed` (frozen hash `8267da50f659`), 1800 s,
  with the sublane model at 0.8 (ADR-010) and `total_delay=True`.
- **Tuning seeds: 400–419** (20). They are disjoint from:
  - the evaluation seeds 0–29;
  - qualification and requalification, 200–259;
  - design, 300–309;
  - every training episode (≥ 1,000,000).
- **The evaluation seeds are never used in tuning.**

## Selection rule (fixed now)

1. **Disqualify** any configuration that ADR-012's rules
   (`simulation.webster.disqualification`) reject on its means over the 20
   seeds:
   - clamp rate > 0.50, a fixed cycle wearing Webster's name;
   - arrived fraction < 0.85, survivorship.
2. **Among those left, select the lowest mean `mean_total_delay_s`**, ADR-021
   A1.5's primary outcome.
   - **Tune on what you are compared on.** ADR-012 selected by mean wait. Here
     Webster is compared on total delay, and tuning it on a different metric
     could hand PPO a detuned baseline.
   - **Exact ties** go to the lower saturation flow, then the lower lost time.
3. **If nothing qualifies,** that is the finding. It is reported, no "Webster's
   best" is claimed, and ADR-021's Webster comparison waits for an owner
   decision.

## Reported, not used for selection

- **All 14 rows:**
  - `mean_total_delay_s`;
  - `mean_wait_s`;
  - clamp rate;
  - arrived fraction;
  - starvation events;
  - throughput.
- **The configuration ADR-012's mean-wait rule would have selected,** so that
  the effect of the metric choice is visible.

## Procedure

- **Runs once.** `scripts/webster_tune.py` refuses to run if its result
  exists, or if this file is not committed unchanged.
- **The selected configuration is then fixed** for every ADR-021 evaluation on
  `pulsed`. No retuning after any PPO result is seen.
