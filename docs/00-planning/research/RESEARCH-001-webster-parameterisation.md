# Research 001 — Webster Baseline Parameterisation

| | |
|---|---|
| **Date** | 2026-08-10 |
| **Question** | How should a Webster baseline be parameterised for a heterogeneous Indian intersection in SUMO so the PPO comparison is defensible, and what do comparable RL signal-control papers do? |
| **Evidence mode** | **Strict** — every claim carries a checkable source |
| **Run status** | **Partial.** Two of three research angles failed; see Validation |

---

## Summary

**We cannot yet answer the main question, and this report does not pretend otherwise.**

The question has two halves. The half about *what our own project already forces* is answered
thoroughly: the repository fixes twenty-seven constraints that bind how any Webster controller can be
built and judged, and three of them are decisions the team can and should make this week.

The half about *what value to use and what published work does* is unanswered. Both agents assigned
to search the literature stopped early when the session hit its usage limit, returning no sources at
all. Since strict evidence rules forbid answering a prior-art question from memory, that half stays
open.

What this report gives you is therefore narrower than asked but still useful: the complete set of
constraints Webster must satisfy, three decisions that need no external evidence, and a precise list
of what to search for when the literature angle is re-run.

**Confidence: Low** on the parameterisation recommendation (no external evidence gathered).
**Confidence: High** on the constraint inventory and the three interim decisions (all traced to
file and line in this repository).

---

## Research Results

### The repository already constrains Webster more tightly than anyone had noticed

Webster's cycle length cannot be whatever the formula returns. Minimum green is 10 s and maximum
green is 90 s (A1), and every conflicting phase transition needs at least 3 s of all-red (A2). With
two phases, that confines any admissible cycle to **26 s at the low end and 186 s at the high end**.
Whatever Webster's optimum-cycle formula produces must be clamped into that window, and no document
currently says what to do when the optimum falls outside it.

### One constraint is currently self-contradictory, and it lands on Webster first

The reward function penalises any lane waiting more than 180 s (A3). But the timing rules above
permit a legal cycle of 186 s. A Webster controller that legally grants both phases maximum green
therefore triggers a starvation penalty while breaking no rule (A10).

This matters more for Webster than for the learned controller. A long fixed cycle is exactly what
Webster produces under heavy demand, so the baseline is the method most likely to sit in the
contradictory zone — and it would be scored badly for doing what it is designed to do.

### Webster carries two jobs that no document reconciles

It is the benchmark the headline claim is measured against (A6, A14), and it is the controller that
takes over on the edge device when the network drops for more than ten seconds (A7, A13). Nothing
states whether these share an implementation, share parameters, or differ deliberately (A12).

The edge role adds a constraint the benchmark role does not have: the fallback activates *because*
the network is down, so it cannot receive parameters at that moment. They must be embedded when the
device is deployed.

### The demand data is calibrated; the signal timing is not

Simulated arrival rates must match dataset-derived counts within 15% (A8). That fixes how much
traffic arrives. It says nothing about saturation flow, lost time, or cycle length — the inputs
Webster actually needs. The project has calibrated the demand and left the controller unparameterised.

### Changing the traffic model changes the baseline's foundations

The decision to model heterogeneous, non-lane-disciplined traffic through a sublane model and mixed
vehicle types (A9) alters what a "lane" means for queue measurement, and with it the assumptions
underpinning any standard saturation-flow figure. Whatever parameterisation is chosen must be chosen
*after* that traffic model is settled, or it will be tuned for a simulation that is no longer running.

### What could not be established

No evidence was gathered on saturation flow values for mixed traffic, on passenger-car-unit
equivalence for two- and three-wheelers, or on how published reinforcement-learning signal-control
work configures its classical baselines. Those were the questions the two failed angles owned. **No
claim about them appears in this report**, because none could be sourced.

---

## Options to Consider

Four shapes of answer exist. Only one can currently be assessed on evidence.

### O1 — Measure saturation flow inside the simulator, then apply Webster's formula

Run a single approach at saturated demand under the final heterogeneous configuration, measure the
discharge rate directly, and feed the measured value into Webster's cycle formula.

**For:** needs no external authority. It is self-consistent with the project's own calibration
requirement (A8) and its reproducibility rules, and it automatically reflects the sublane traffic
model rather than assuming a figure derived from lane-disciplined traffic (A9).

**Against:** it measures the *simulator's* saturation flow, not the real world's. That makes the
comparison internally fair but does not make the simulation realistic. It also produces a number
nobody can check against published values without the literature angle.

**Evidence:** codebase (A8, A9, A1, A2). The procedure is grounded in this project's requirements,
not in an external claim.

### O2 — Adopt a parameterisation protocol from published RL signal-control work

**Cannot be assessed.** This was the question the RL-benchmarking angle owned, and it returned
nothing. Whether such a protocol exists, and what it prescribes, is unknown.

**Evidence:** none gathered.

### O3 — Use a standard highway-capacity default saturation flow

**Cannot be assessed.** The specific default value and whether it holds for filtering two- and
three-wheelers require sources that were not gathered.

One thing *is* established: this project's own decision record already flags that lane-discipline
assumptions fail under its chosen traffic model (A9). That is a reason to check the default, not a
reason to reject it — the check needs evidence this run did not produce.

**Evidence:** none gathered for the option itself; A9 is codebase evidence that it needs scrutiny.

### O4 — Search over cycle length within the permitted bounds and report the search

Rather than asserting a saturation flow, evaluate Webster-style fixed-time control across a range of
cycle lengths inside the 26–186 s window, pick the best-performing configuration on the shared
demand, and publish the search alongside the result.

**For:** it directly answers the objection the whole question exists to prevent — that the baseline
was weak because nobody tuned it. A reported search is checkable in a way an asserted value is not.
It fits the existing protocol, which already runs every method over the same thirty seeds on the same
demand (A4, A5).

**Against:** a searched cycle is no longer strictly Webster's analytical method. Calling it "Webster"
would be inaccurate; it is optimised fixed-time control, and the paper must say so. It also costs
extra simulation runs.

**Evidence:** codebase for the bounds and the protocol (A1, A2, A4, A5). Whether reviewers in this
field expect a tuned baseline is precisely what the failed angle was to establish.

---

## Recommendation

**On the core question — no clear winner.** Choosing between O1, O2, O3 and O4 requires knowing what
saturation flow applies to heterogeneous traffic and what comparable published work does. Neither was
established. Strict evidence rules do not permit a recommendation resting on reasoning alone, and
recommending a value from memory is the exact failure this project's own records repeatedly warn
against.

**What would settle it.** Re-run the two failed angles against these specific targets:

1. Empirically measured saturation flow rates for mixed, non-lane-disciplined traffic, and whether
   standard highway-capacity defaults are reported as valid for such streams.
2. Passenger-car-unit equivalence factors for motorcycles and three-wheelers under filtering
   behaviour.
3. How IntelliLight, PressLight, CoLight, FRAP, MPLight and the RESCO benchmark configure their
   fixed-time and Webster baselines, and whether each reports the procedure.
4. Any published critique arguing that reinforcement-learning gains in this field are overstated
   because classical baselines were left untuned.

Item 3 is the decisive one. If published work routinely tunes its classical baseline, O4 becomes the
defensible answer; if it routinely asserts a textbook value, O3 does.

### Three decisions that need no further evidence

These follow from the repository's own numbers and can be made this week.

**Clamp the cycle, and record the rule.** Webster's optimum must be truncated into the 26–186 s
window implied by A1 and A2. Decide now whether truncation is silent or logged, and write it down —
a baseline that silently violates its own timing rules is not a baseline.

**Resolve the starvation contradiction before parameterising anything.** The 180 s penalty against a
186 s legal cycle (A3, A10) must be settled first, because it determines whether a long Webster cycle
is legal behaviour or penalised behaviour. Parameterising before that decision means parameterising
against an undefined target.

**State explicitly whether the benchmark and the fallback are the same controller.** Either answer is
acceptable; leaving it unstated is not (A7, A12, A13). If they differ, the difference belongs in the
paper's limitations, because the fallback's real-world behaviour is then not what the benchmark
measured.

**Evidence basis:** all three rest on corroborated codebase evidence — direct file-and-line
inspection of the governing documents. None rests on reasoning alone. None depends on the missing
literature.

---

## Validation

**The adversarial validation pass did not run.** The session usage limit that terminated the research
wave made a further agent dispatch unviable. No `V#` findings exist for this run.

This report is therefore **unvalidated**, and two known weaknesses follow directly from that:

- The options framing has not been challenged. A fifth option may exist that none of O1–O4 covers.
- The three interim decisions rest on a single codebase-exploration pass. The constraint inventory
  was thorough and traceable, but nobody has attacked it.

**Known limitations of this run, stated plainly:**

| Limitation | Consequence |
|---|---|
| Both web-facing angles returned zero artifacts | The prior-art half of the question is unanswered, not answered weakly |
| No adversarial validation | Options framing and interim decisions are unchallenged |
| No readability-editor pass | Prose is unaudited against the shared standard |
| Sources registry contains codebase entries only | Nothing here can be checked against external authority |

**Confidence reasoning.** High confidence on the constraint inventory, because every item resolves to
a file and line in this repository and the repository is the authority on its own requirements. Low
confidence on anything touching parameterisation values, because the evidence class needed for it was
not gathered at all — this is absence of evidence, not weak evidence.

**How to complete this run.** After the usage limit resets, re-run at `medium` with the four search
targets above. The codebase angle need not repeat; its findings are recorded here and remain valid
until the governing documents change.

---

## Sources

All entries are trust class **codebase**. Per the evidence rule, the repository is the current-state
anchor for claims about its own requirements, and each was verified by direct inspection.

| ID | Source | Location | Trust | What it establishes | Status |
|---|---|---|---|---|---|
| A1 | FR-A03 green bounds | `docs/00-planning/PRD.md:731` | codebase | Minimum green 10 s, maximum green 90 s | Corroborated |
| A2 | FR-A04 all-red | `docs/00-planning/PRD.md:732` | codebase | ≥3 s all-red between conflicting phases | Corroborated |
| A3 | Reward function | `docs/00-planning/PRD.md:927-934` | codebase | Starvation penalty applies above 180 s wait | Corroborated |
| A4 | Evaluation protocol | `docs/00-planning/PRD.md:949-960` | codebase | 30 seeds × 3600 s per method; paired t-test, bootstrap CI | Corroborated |
| A5 | FR-S04 shared environment | `docs/01-requirements/FRD.md:82` | codebase | All methods share network and demand per seed | Corroborated |
| A6 | RG3 headline criterion | `docs/00-planning/PRD.md:329` | codebase | PPO must beat Webster by ≥10% mean wait, p<0.05 | Corroborated |
| A7 | FR-A06 fallback | `docs/00-planning/PRD.md:734` | codebase | Webster fallback within 10 s of MQTT loss | Corroborated |
| A8 | FR-S02 demand calibration | `docs/01-requirements/FRD.md:81` | codebase | Arrival rates calibrated to dataset counts ±15% | Corroborated |
| A9 | ADR-010 traffic model | `docs/00-planning/decisions/ADR-010-sumo-heterogeneous-traffic.md` | codebase | Sublane model and heterogeneous vehicle types; lane-discipline assumptions no longer hold | Corroborated |
| A10 | Pending item P6 | `docs/00-planning/PRD-CHANGELOG.md:186` | codebase | 180 s starvation limit contradicts 186 s worst legal cycle | Corroborated |
| A11 | Pending item P8 | `docs/00-planning/PRD-CHANGELOG.md:188` | codebase | Webster parameterisation unspecified; due before Week 10 | Corroborated |
| A12 | TRIAGE-002 | `docs/00-planning/triage/TRIAGE-002-webster-parameterisation.md` | codebase | Two Webster roles, never reconciled | Corroborated |
| A13 | SRS M-LOCAL mode | `docs/01-requirements/SRS.md:222-223` | codebase | Webster must be resident on the edge node, not fetched | Corroborated |
| A14 | FR-R06 results file | `docs/01-requirements/FRD.md:99` | codebase | 30 Webster rows committed as permanent evidence | Corroborated |

**No web sources were retrieved.** The two open-web angles terminated before returning any artifact.
