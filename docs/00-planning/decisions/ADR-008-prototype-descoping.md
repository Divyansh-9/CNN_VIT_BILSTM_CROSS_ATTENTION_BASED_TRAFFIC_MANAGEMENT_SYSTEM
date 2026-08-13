# ADR-008 — Prototype Descoping

| | |
|---|---|
| **Status** | **Accepted 2026-08-13** |
| **Approved by** | Project owner. **Not a faculty-guide signature** - if the guide later reviews scope, this is the record of who decided and when |
| **Date** | 2026-08-08 |
| **Affects** | FR-UI01..FR-UI10, NFR-06, NFR-11, NFR-12, M8, M9, M10; PRD §11, §16 |
| **Evidence** | [FEASIBILITY-AUDIT §2, §3.2, §3.3, §5.2](../FEASIBILITY-AUDIT.md) |

## Context

The prototype and dashboard together account for roughly **310 of ~1,200 estimated person-hours** —
about a quarter of the project — against a realistic team capacity of ~715 hours.

Their contribution to the assessed outcomes is disproportionately small. PRD §2.5.2 lists what
faculty actually check: measurable claims, a genuine dataset, an honest ablation, reproducible code,
defensible design choices. PRD §2.5.3 lists what distinction requires, and names "a working hardware
prototype (even a 4-camera Jetson tabletop setup)" — *a working prototype*, not a production
observability stack.

Meanwhile the experiments — which §2.5.4 identifies as the actual research and the most common thing
teams underdeliver — are scheduled after this work.

## Decision

Reduce the prototype to what demonstrates the system and evidences the results. Keep everything that
carries research or safety weight.

| Component | Current | Proposed | Reasoning |
|---|---|---|---|
| Time-series store | PostgreSQL + TimescaleDB | **SQLite + Parquet** | Identical query surface at this data volume. Removes a service, a schema migration path, and a container. Parquet files are also directly loadable in the analysis notebooks |
| Dashboard auth | JWT, 24h expiry (NFR-12) | **Single shared password over local network** | A bench demo on a LAN. NFR-12's intent — unauthenticated users cannot control signals — is met |
| MQTT auth | Username/password (NFR-11) | **Unchanged** | Already trivial; `allow_anonymous false` is one config line |
| Dashboard pages | 4 (Live, Analytics, Benchmark, Events) | **2 — Live, and Results** | Analytics folds into Results. FR-UI06/UI07 (benchmark and ablation tables) keep full weight; FR-UI05 (gate tracker) moves to Results; the event log becomes a panel on Live |
| Uptime evaluation | 4 hours ≥95% (NFR-06, M10) | **1 hour ≥95%** | A 4-hour run surfaces nothing a 1-hour run misses at this complexity, and costs a supervised afternoon per attempt |
| Edge fallbacks (FR-A06) | Two paths, fault-injected | **Unchanged** | Required behaviour, genuinely interesting, and cheap to test |
| Emergency preemption (FR-A05) | 10/10 within 3s | **Unchanged** | Highest-value capability; also the most demo-friendly |
| Safety invariants (FR-A03/A04) | Enforced | **Unchanged** | Non-negotiable |

Estimated saving: **~140 person-hours**, redirected to experiments and the paper.

### What explicitly does not change

Every requirement that produces evidence or protects safety stays. The two fallback paths, the
emergency preemption timing, the min/max green and all-red constraints, the MQTT QoS contract, and
the benchmark and ablation tables are all untouched. This is a reduction in *infrastructure*, not in
system behaviour.

## Consequences

**Positive.** ~140 hours return to the work that is graded and published. The demo becomes easier to
rehearse and more reliable on demo day — fewer services means fewer things that fail in front of an
examiner. SQLite and Parquet remove a Docker service and make the analysis notebooks read the same
files the dashboard does, which incidentally strengthens the NFR-09 reproducibility story.

**Negative.** The stack is less impressive as a résumé line. "PostgreSQL + TimescaleDB + JWT" reads
better on a CV than "SQLite". This is a real cost and worth weighing — but a completed project with a
strong ablation reads better than an incomplete one with a good database.

**Negative.** Requirements marked Must Have in PRD §9 are being reduced. FR-UI03, FR-UI04, and
FR-UI08 are absorbed rather than deleted; NFR-06 and NFR-12 are weakened. The RTM must be updated and
the variation recorded, or the traceability story breaks.

**Negative.** If the guide declines, the team must either find the 140 hours or descope elsewhere —
and the only remaining candidates are the experiments, which is the wrong answer. Have the
alternative ready: the conditional scope in SOW §2.3 (Phase 2 gating, temporal attention) goes first.

## How to take this to the guide

Bring [FEASIBILITY-AUDIT.md](../FEASIBILITY-AUDIT.md) and lead with the arithmetic, not the request.

> "We estimated the work at ~1,200 person-hours against ~715 realistic hours. Here is the breakdown.
> We would rather deliver a rigorous subset than an incomplete whole. These are the reductions we
> propose and here is what we are protecting — the ablation, the statistics, the dataset, and the
> safety behaviour. May we record a scope variation?"

Do this in **Week 1 or 2**. A team that brings honest arithmetic early looks disciplined. The same
team explaining a missing dashboard in Week 18 does not.

## Alternatives considered

**Keep everything, work harder.** Rejected — 1.6–1.8× overcommitment is not closed by effort, and the
thing that gets dropped under pressure is always the last-scheduled item, which here is the paper.

**Drop the prototype entirely, simulation only.** Saves ~310 hours. Rejected: PRD §2.5.3 names a
working prototype among distinction requirements, and a live demo is disproportionately persuasive in
a viva.

**Keep four pages, cut the backend instead.** Rejected — the backend carries FR-A01–A06, which
includes the fallback behaviour that is genuinely interesting. Cutting evidence and safety to keep
UI polish inverts the priorities.
