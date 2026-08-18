# Results voided by P15 — the controller never reached the simulation

Every CSV listed here was produced before `traci.trafficlight.setPhaseDuration()`
was added. `setPhase()` alone does not hold a phase: SUMO's own program keeps
advancing underneath it, so the light ran the built-in program throughout and
the controller label on each row describes an intention rather than a behaviour.

| file | status |
|---|---|
| `action_space_screen.csv` | **regenerated** post-P15 (commit `95d00d7`) — current, citable |
| `baselines.csv` | **superseded**, see below — do not regenerate |

They are kept rather than deleted: they are the evidence for P15, and the
headline they produced — fixed 31.09 s vs Webster 29.32 s, p = 0.225 — is now
explained rather than merely unconfirmed. Two methods that were secretly the
same program should fail to differ significantly.

**Do not cite any number from `baselines.csv`.**

## `baselines.csv` is superseded, not merely void (2026-08-18)

It was a single-seed regime characterisation — 2 controllers × 3 regimes × seed
42 — written to choose which demand regime the real benchmark would run in. It
has had **no producing script since S38**, so "regenerate it" was never an
instruction anyone could follow.

`benchmark_runs.csv` now covers **3 controllers × 3 regimes × 30 seeds**, all
post-P15, with paired statistics in `benchmark_stats.csv`. That is strictly more
than `baselines.csv` ever held, on every axis. The file stays as P15 evidence
and nothing else.

The choice it originally made — benchmark at `saturated` — turns out to matter
more than a screening decision should, because the controller ranking is not
stable across regimes. See the three-regime result in the PRD changelog.
