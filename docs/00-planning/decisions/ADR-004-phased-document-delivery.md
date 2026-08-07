# ADR-004 — Full Separate SDLC Documents, Delivered in Waves

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-08-07 |
| **Deciders** | Project team |
| **Affects** | All of `docs/` |

## Context

The project is assessed under a full-SDLC rubric that names its artifacts individually: SOW, BRD and
PRD in planning; SRS, FRD, NFR and RTM in requirements analysis; SAD, HLD and LLD in design; STP,
STD, STR and UAT in testing; TIM and SOP in deployment.

Two tensions pull against simply writing all sixteen now.

**Redundancy.** In standard practice FRD and NFR are sections *of* an SRS, and HLD and LLD are
sections of an SAD. Writing them as separate files guarantees overlapping content, and overlapping
content drifts out of sync the moment a requirement changes.

**Truthfulness.** STR is a Software Test *Report* — it records results of tests that were actually
run. UAT records acceptance actually granted. TIM is a transition and implementation plan for a
system that exists. Written in Week 1, all three are fiction, and would need wholesale rewriting
rather than revision.

## Decision

**All sixteen artifacts exist as individual files**, because the rubric names them individually and
an examiner looking for `STD.md` should find `STD.md`.

**Redundancy is eliminated by reference, not by merging.** Requirement IDs are defined once — the
PRD's existing `FR-*` and `NFR-*` IDs are reused verbatim — and every other document cites IDs
rather than restating requirements in prose. The RTM is the single join table. A requirement change
touches one document; the RTM shows what else is affected.

**Documents are written in four waves**, gated on the PRD §18 phases rather than written upfront:

| Wave | Gate | Documents |
|---|---|---|
| 1 | Week 0–1, before any code | SOW, BRD, SRS, FRD, NFR, RTM, PRD-CHANGELOG, ADRs, Execution Manual |
| 2 | ~Week 5, before implementation hardens | SAD, HLD, LLD |
| 3 | ~Week 11, before benchmarking | STP, STD, UAT |
| 4 | ~Week 16, after results exist | STR, TIM, SOP |

Wave gates appear as explicit entries in the weekly plan (W05, W11, W16), so they are triggered by
schedule rather than by spare time.

## Consequences

**Positive.** Every document is truthful when reviewed. Wave 1 lands before code begins, which is
when a requirements baseline is actually worth something. The ID spine means the suite functions as
an engineering instrument rather than a submission binder — and the RTM, in particular, cannot be
convincingly reconstructed after the fact, which is exactly why examiners probe it.

**Negative.** The suite is incomplete until Week 16, so a mid-semester review will find Waves 3–4
missing. This is defensible — pointing at the wave table shows deliberate sequencing rather than
neglect — but it must be explained rather than discovered. The wave table is reproduced in
`docs/README.md` for that reason.

**Negative.** Discipline is required: an unwritten Wave 4 in Week 19 under submission pressure is a
real failure mode. Tying the gates to milestones rather than to available time is the mitigation,
and it is the same mitigation PRD §2.5.4 applies to the experiments.

## Alternatives considered

**All sixteen upfront.** Complete binder immediately, useful for an early review. Rejected: the test
and deployment documents would describe a system that does not exist, and would be rewritten
entirely.

**Six consolidated documents** (FRD/NFR/RTM folded into SRS, HLD/LLD into SAD, STD/STR/UAT into
STP). Substantially less redundancy and easier to keep synchronised — this is what industry usually
does. Rejected because it risks not matching a rubric that names each artifact explicitly, and the
cost of that mismatch falls entirely on the team's grade.
