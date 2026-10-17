# Memo — the forecast-for-control experiment returned a measured null

**To:** Ms Neha Pokhriyal (project guide) · **From:** Divyansh Uniyal, project owner
**Date:** 2026-10-17 · **Decision requested by:** 2026-10-24

**Summary:** the pre-registered test of whether traffic forecasts improve the
learned (PPO) signal controller did **not** demonstrate a benefit.

Under ADR-021 that result narrows what the project can claim for its RL
controller, and **that narrowing is your decision, not the project owner's.**
**Nothing citing this result has been written into any report** while your
decision is pending.

## What was tested

**The question.** In a simulated intersection whose traffic changes over
time, does giving the PPO controller a **perfect** 60-second congestion
forecast reduce delay? It was compared against:
- PPO with no forecast;
- PPO with a simple "same as now" (persistence) forecast.

A perfect forecast is an upper bound. If it does not help, no achievable
forecast is expected to help this controller.

**How it was protected against bias:**
- the scenario was qualified to have real forecasting headroom;
- every arm and baseline was frozen before training;
- the analysis was fixed in code before any result existed;
- every model was audited, and its file hash locked;
- the evaluation ran **once**, on 28 paired seeds (P115–P130).

## Result

**The official conclusion, as recorded in ADR-021:**

> Under the preregistered 28-seed primary evaluation, providing the tested PPO
> controller with a perfect 60-second congestion forecast did not demonstrate a
> reduction in mean total delay relative to either PPO without forecasts or PPO
> using persistence forecasts. Both point estimates favored the corresponding
> comparison policy, and neither comparison was statistically significant
> after Holm correction.
>
> The result is a **measured null for forecast benefit with the tested
> controller and experimental conditions**. It does not establish that traffic
> forecasts are inherently unhelpful.
>
> Interpretation is limited by weak oracle transfer (77.4% agreement against a
> preregistered 80% threshold), substantial variation across training seeds,
> and the fact that no-forecast PPO also underperformed the tested Webster
> baselines. The experiment therefore does not establish that forecast
> information cannot help a stronger controller.

| comparison (mean total delay) | difference | 95% CI |
|---|---|---|
| perfect forecast − no forecast | +5.41 s | −0.91 to +16.81 s |
| perfect forecast − persistence | +2.38 s | −6.35 to +15.38 s |

**Context:** with no forecast at all, PPO already trails a tuned Webster
controller by 3.9 s. It also trails a Webster variant with a clamped cycle
length and demand-proportional splits by 6.4 s, which is the best controller
measured.

## Decisions requested

1. **Narrow claim C1 (ADR-023).** C1 currently reads "a count-based congestion
   forecaster and RL signal controller". **Recommendation:** keep the
   forecaster half, which is supported by P104–P106. Report the RL half as
   this measured null, using the wording above. Do not claim the RL
   controller improves on Webster.
2. **The safety test (P97a Part 2).** Its preconditions are met, but the
   forecast benefit that motivated it was not shown. **Recommendation:**
   defer it. Run it only if you judge the narrower safety question worth
   answering on its own. If so, it needs a frozen protocol amendment first.
3. **One new study.** The proposal: a forecast-assisted version of the
   best-performing Webster controller, fed by next-minute **count** forecasts
   (the forecaster role already in the prototype, ADR-027).
   - **No learning is involved,** so the training-seed variance that
     weakened this test disappears.
   - **It asks whether forecasts help a controller that is already
     competitive.**
   - **It would be a new, separately pre-registered study,** on fresh seeds.
     It would not reanalyse this one.

   The plan is in
   [PLAN-2026-10-17-after-ceiling](PLAN-2026-10-17-after-ceiling.md).
   **Recommendation: approve it to the design stage only.** Its first gate
   checks, at no evaluation cost, whether forecasts would even change the
   controller's decisions.

**Not requested:** rerunning or reanalysing the completed experiment. Its
result is frozen.

## Addendum, same day: decision 3 resolved itself at its own gate

The owner approved the forecast-assisted Webster study for its design,
feasibility and power stages only. **It stopped at the power gate,** as its
pre-registration required (P132). No evaluation was run.

**Feasibility passed.** A perfect next-minute forecast changes 83% of the
controller's green splits.

**Power failed.** Resolving a 2% delay improvement would need 347 paired
seeds, against a pre-set maximum of 200. The paired SD is 4.55 s, because once
one green differs, the rest of the episode's traffic differs.

**The pilot, which is not evidence,** pointed the wrong way:
- +2.9 s delay with the perfect forecast;
- +2.8 s with the deployable ridge forecaster.

The ridge forecaster was also worse than persistence on simulated counts.

**Decision 3 therefore no longer needs your approval.** The study is closed.
**Decisions 1 and 2 still stand.** The finding strengthens the recommended C1
wording: in this simulation, neither a learned nor a classical controller has
shown a delay benefit from traffic forecasts.

**A wording correction to the addendum above (P133).** The 347-seed figure
holds **under the pilot's estimated variability and the pre-registered
statistical assumptions**. It does not show that the effect is too small to
resolve in general. The pilot's effects are exploratory, not confirmatory
evidence of harm.

**The overall conclusion, as recorded:**

> Across the tested simulation experiments, neither the learned PPO controller nor the classical Webster controller demonstrated a delay benefit from forecast inputs under the specified conditions. Forecasts changed controller decisions, but the proposed follow-up study failed its preregistered power gate. These findings do not establish that forecasts cannot improve traffic control under other controllers, scenarios, or better-calibrated forecasting systems.

**The forecast-for-control line is closed** under the current protocol.
**Decisions 1 and 2 remain with you.**

