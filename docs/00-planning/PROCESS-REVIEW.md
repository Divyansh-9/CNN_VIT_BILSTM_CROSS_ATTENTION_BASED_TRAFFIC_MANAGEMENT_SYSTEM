# Process Review — Are We On Track?

| | |
|---|---|
| **Date** | 2026-08-10 (Week 1–2 of 20) |
| **Verdict** | **The artifacts are excellent. The process has stalled.** |

Deliberately one page. A ten-page document arguing there is too much documentation would answer
itself.

---

## The number that matters

| | |
|---|---|
| Documentation | **6,569 lines** across 36 files |
| Python | **383 lines** — all of it tooling (`seed`, `check_env`, `check_docs`, spec tests) |
| Model / detection / corpus / SUMO / dashboard code | **0 lines** |
| Elapsed | ~2 of 20 weeks |
| Commits | 12, across 3 days |

**17:1 documentation to code, and none of the code is the project.**

PRD §2.5.4 names the classic failure: *eight weeks on architecture, two on experiments*. We are
running a variant with a better alibi — planning is genuinely productive, it has found real defects,
and it produces a visible artifact every session. That is exactly what makes it hard to stop.

## What the planning actually bought

Not nothing. Reading the documents found seven defects that would each have cost days or weeks:

| Defect | Would have surfaced | Cost if found then |
|---|---|---|
| No MFSTNet training corpus specified | Week 10 | Weeks |
| Label inside the observation window (A15) | Week 12, as "great val, useless model" | The ablation |
| Corpus of size zero from 5-min clips | Week 9 | Re-collection |
| Global pooling → 4 identical lane predictions | Week 12, misdiagnosed as a training bug | Days |
| PPO forecast fields with no producer | Week 11, improvised under deadline | The C4 claim |
| Circular evaluation vs count baselines | Never — it would have shipped | The paper |
| Starvation threshold < worst legal cycle | Week 13, as reward noise | Days |

That is a real return. The problem is not that planning happened; it is that **planning has not
stopped**, and the last two review rounds have produced findings faster than the project can absorb
them.

## Three things that are now wrong

**1. The plan changes faster than it executes.** Ten ADRs, twenty-one PRD amendments, twenty-four
risks, eight pending items — and zero measurements taken. Every finding is real; none has been
tested against reality. The next class of defect only appears when something runs.

**2. Two load-bearing decisions have been "submit this week" for three sessions.** ADR-006 and
ADR-008 gate ~340 person-hours. Until they are signed the team is planning against two incompatible
futures, and every document carries a conditional branch. This is now the single biggest blocker, and
it is a twenty-minute conversation.

**3. Nobody on the team has read any of this.** All 6,569 lines were written in one voice across
three days. Documentation the team has not internalised is not documentation — it is a liability,
because it creates confidence without shared understanding, and the implementation will diverge from
it silently.

## What to do this week — in order

| # | Action | Effort | Why it is first |
|---|---|---|---|
| 1 | **Submit the [scope variation request](SCOPE-VARIATION-REQUEST.md)** | 20 min | Unblocks 340 h and removes every conditional branch from the plan |
| 2 | **Run the three Week-2 pilots** ([Manual §1.2](../90-manual/EXECUTION_MANUAL.md)) | 3 h | First contact with reality. Measurement 4 can invalidate the whole task design — better now than Week 12 |
| 3 | **Doc walkthrough — each owner presents their subsystem back to the group** | 90 min | Converts reading into understanding, and surfaces disagreement while it is still cheap |
| 4 | **PLAN-01 WI-04 onward — write the detector code** | rest of week | Ends the 17:1 ratio |
| 5 | Decide P6, P7, P8 | 1 h total | Small, blocking specific milestones |

**Stop writing planning documents after item 3.** Wave 2 (SAD/HLD/LLD) is scheduled for Week 5 and
should stay there. If a new defect is found, record it as a pending item and keep building.

## What is genuinely good — keep it

The build order (PRD §2.4). ADR discipline with rejected alternatives recorded. Feature caching —
still the highest-leverage decision in the project. The evaluation-integrity work: human-verified test
split, density stratification, cluster bootstrap. The withdrawn-claims register. The spec-invariant
tests, which caught a real contradiction on their first run.

That set is above the standard of most final-year projects and, in the evaluation-integrity part,
above some published work. It is worth defending in the viva.

## The honest bottom line

**Are we on the right track?** The direction is right and the map is unusually good. But a map is not
distance travelled, and the project is measured in Week 20 by what ran, not by what was specified.

The risk is no longer that the team builds the wrong thing. It is that the team spends its planning
surplus and starts building in Week 5 with fifteen weeks left and a plan that was already correct in
Week 2.

**Ship something this week.**
