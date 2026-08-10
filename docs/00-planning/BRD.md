# Business Requirements Document (BRD)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | BRD v1.0 |
| **Date** | 2026-08-07 |
| **Audience** | Faculty guide, project coordinator, external examiner, conference reviewers |
| **Related** | [SOW](SOW.md) · [PRD](PRD.md) · [SRS](../01-requirements/SRS.md) · [RTM](../01-requirements/RTM.md) |

---

## 1. Purpose of this document

The BRD states **why** the system is being built and what business outcome each capability serves.
It sits above the PRD, which states *what* is built, and above the SRS, which states *how the system
shall behave*.

Its practical function in this project is to anchor the traceability spine. Every functional
requirement in the PRD must serve a business requirement here, and the [RTM](../01-requirements/RTM.md)
enforces that. A functional requirement tracing to no business requirement is scope creep; a business
requirement tracing to no functional requirement is an unmet need.

## 2. Background and problem context

Indian urban intersections are controlled predominantly by fixed-time signal plans whose timings are
set once and rarely revised. Those plans assume a lane-disciplined, homogeneous vehicle mix. Indian
traffic is neither: two- and three-wheelers filter between lanes, auto-rickshaws and e-rickshaws
occupy a size and acceleration class that Western-trained detectors do not model, and non-vehicular
obstructions including cattle are routine.

Three consequences follow.

**Signal timings do not match demand.** A fixed plan gives the same green to an empty approach as to
a saturated one, so queues persist on one arm while another discharges early.

**Off-the-shelf perception under-performs.** Detection models trained on COCO or similar corpora have
no auto-rickshaw, e-rickshaw, or cattle class, so the vehicle counts that any adaptive controller
would depend on are systematically wrong in exactly the conditions that matter most.

**Control is reactive rather than anticipatory.** Even demand-responsive controllers act on the queue
that has already formed. A controller that knew a queue was about to form could begin discharging
before saturation.

The academic context adds a second problem class. This is a 20-week, 3–4 member, zero-budget
final-year project assessed on demonstrable rigour, and PRD §2.5.4 identifies the dominant failure
mode explicitly: teams over-invest in architecture and under-deliver experiments. Reproducibility and
honest reporting are therefore business requirements in their own right, not engineering hygiene.

## 3. Stakeholders

| Stakeholder | Interest | Primary success signal |
|---|---|---|
| Faculty guide | Rigour, measurable claims, defensible design decisions | Every claim quantified with a statistical test (PRD §2.5.2) |
| External examiner | Genuine contribution, reproducibility, viva defence | Working demo + reproducible results from a clean machine |
| Conference reviewers (ITSC / CVIP) | Novelty, honest ablation, statistical validity | Accepted or constructively reviewed paper |
| Project team | Distinction grade, employable portfolio, publication | M1–M11 accepted |
| Research community | Reusable dataset for Indian traffic perception | IndiaTrafficNet downloads and citations |
| Traffic authority *(indirect, non-participating)* | Evidence that adaptive control is viable locally | Simulated wait-time reduction with confidence intervals |

> The traffic authority is a **notional** stakeholder. No municipal body is engaged, and no
> deployment to live infrastructure is in scope (SOW §2.2). Requirements are framed against their
> plausible needs so the work generalises, not because a deployment is planned.

## 4. Business objectives

| ID | Objective | Measure of success |
|---|---|---|
| BO-1 | Demonstrate that RL-based adaptive control outperforms fixed-time and Webster control under Indian traffic conditions | ≥20% wait reduction vs. Fixed, ≥10% vs. Webster, p<0.05 over 30 runs |
| BO-2 | Demonstrate that multimodal CNN-ViT fusion improves congestion prediction over single-modality baselines | Macro F1 ≥ 0.80, with ablation isolating each component's contribution |
| BO-3 | Contribute a reusable, publicly licensed dataset for Indian traffic perception | 12,000+ frames, 8 classes, CC BY 4.0, publicly hosted. *If [ADR-006](decisions/ADR-006-curate-then-collect-dataset.md) is approved:* a harmonised 8-class benchmark with datasheet and splits, plus ≥1,500 anonymised fixed-camera campus frames |
| BO-4 | Produce a submissible conference paper | Submission receipt from ITSC or CVIP |
| BO-5 | Achieve full reproducibility of every reported result | Clean-machine reproduction from committed code, configs, and seeds |
| BO-6 | Deliver a working physical demonstration of the end-to-end pipeline | 4-hour continuous run at ≥95% uptime |

## 5. Business requirements

Each BR states a need in outcome terms. The **Traced to** column is the authoritative BR→FR mapping;
the [RTM](../01-requirements/RTM.md) extends it through design, test, and milestone.

### 5.1 Perception and data

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-01** | The system must recognise the vehicle classes that actually occupy Indian intersections, including auto-rickshaw, e-rickshaw, and cattle | Counts feed every downstream decision; a detector blind to 20% of the vehicle mix corrupts control and prediction alike | Must | FR-D01–FR-D04, FR-D08, FR-P02 |
| **BR-02** | Perception accuracy must be demonstrably better than a general-purpose baseline on Indian conditions | A contribution claim requires a measured comparison, not an assertion (BO-2, PRD §2.5.2) | Must | FR-D09, FR-D08 |
| **BR-03** | The dataset underpinning perception must be publicly reusable by other researchers | BO-3; a dataset used once and discarded is not a contribution | Must | FR-D06, FR-D07 |
| **BR-04** | Data collection and its known biases must be documented, including what conditions are absent | Undocumented bias invalidates downstream claims and fails reviewer scrutiny | Must | FR-D07, FR-D02, FR-D05 |

### 5.2 Prediction

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-05** | The system must anticipate congestion before it saturates an approach, not merely report current queues | Anticipation is the difference between reactive and proactive control; 60s horizon matches signal cycle length | Must | FR-M08, FR-M01–FR-M05 |
| **BR-06** | Prediction quality must be attributable to specific architectural components | BO-2; an unattributed improvement is not a research finding (PRD §14.4) | Must | FR-M09, FR-M10, FR-M11 |
| **BR-07** | The basis on which the model weights local versus global visual evidence must be observable | The gate is a research artifact and an interpretability claim, not an internal detail (PRD §14.2) | Must | FR-M04, FR-UI05 |
| **BR-08** | Prediction must be fast enough to inform a live control decision | A prediction arriving after the decision is worthless | Must | FR-M12, FR-M13 |

### 5.3 Control and safety

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-09** | Signal timing must adapt to observed and predicted demand rather than a fixed plan | BO-1; the core problem statement (§2) | Must | FR-R01–FR-R05, FR-A01 |
| **BR-10** | Emergency vehicles must be given priority passage within a bounded time | Life-safety; the single highest-value capability to a traffic authority | Must | FR-P03, FR-P04, FR-A05 |
| **BR-11** | No approach may be starved of green indefinitely, whatever the optimiser prefers | An optimiser minimising mean wait will happily starve a minor arm; fairness is a hard requirement, not a tuning preference | Must | FR-R04, FR-A03 |
| **BR-12** | The intersection must remain safely controlled when any intelligent component fails | A degraded intersection is acceptable; an uncontrolled one is not | Must | FR-A06, FR-A04 |
| **BR-13** | Control benefit must be established with statistical evidence, not a single favourable run | BO-1; single-run comparisons are the most common flaw in student traffic-control work | Must | FR-R06, FR-R07, FR-R08 |

### 5.4 Operations and transparency

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-14** | An operator must be able to see current intersection state and why the system is acting as it is | Unexplained automation is not adopted; also the primary demo surface | Must | FR-UI01, FR-UI02, FR-UI08 |
| **BR-15** | Historical behaviour and prediction quality must be reviewable after the fact | Enables tuning, supports the paper, and lets an examiner inspect rather than trust | Must | FR-UI03, FR-UI04, FR-UI06, FR-UI07 |
| **BR-16** | An authorised operator must be able to take manual control | Regulatory reality and demo safety | Should | FR-UI09, FR-UI10 |

### 5.5 Research integrity

These carry equal weight to the functional requirements above. PRD §10 marks the corresponding NFRs
"Critical", and SOW §5.1 makes them part of the Definition of Done.

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-17** | Every reported result must be reproducible by a third party from committed artifacts | BO-5; irreproducible results are not evidence | Must | NFR-07, NFR-08 |
| **BR-18** | Raw per-run results must be published, not only aggregate summaries | Prevents both accidental and deliberate cherry-picking; lets a reviewer recompute the statistics | Must | NFR-09, NFR-10 |
| **BR-19** | Negative and marginal results must be reported and analysed, never dropped | PRD §2.5.5; a covered-up negative result is a failed project | Must | FR-M10, NFR-10 |
| **BR-20** | The system must not process or retain personally identifying imagery at runtime | Privacy obligation independent of deployment status; also a reviewer question | Must | NFR-13 |
| **BR-21** | System access must be authenticated | Prevents unauthorised signal control | Must | NFR-11, NFR-12 |

### 5.6 Project delivery

| ID | Business requirement | Rationale | Priority | Traced to |
|---|---|---|---|---|
| **BR-22** | The system must be demonstrable end to end on hardware the team already owns | SOW §8; a ₹0 budget is a hard constraint, not a preference | Must | ADR-003, NFR-01 |
| **BR-23** | Mandatory scope must be deliverable within 20 weeks by 3–4 part-time students | PRD §2.4 exists to enforce this | Must | PRD §2.4, SOW §2.3 |

## 6. Success criteria

The project succeeds if every BO in §4 is met and every Must-priority BR in §5 is satisfied.

Per PRD §2.5.3, **distinction level does not require the conditional scope** in SOW §2.3. BR-05
through BR-08 are satisfied by MFSTNet Phase 1; the gate (BR-07) is satisfied at Phase 2, and if
Phase 2 is not reached, BR-07 is formally descoped and reported as future work rather than left
silently unmet.

## 7. Out of scope

Per SOW §2.2. Two exclusions warrant explanation here because they will be asked about:

**No live deployment.** All control results are simulation-validated (SUMO), and the prototype is a
bench demonstration. Any claim about real-world wait-time reduction is a claim about the simulation,
and is worded as such throughout.

**No multi-intersection coordination.** Single-intersection optimisation is a well-posed problem with
established baselines (Fixed, Webster). Network coordination is a materially harder problem and would
consume the schedule that §2.5.4 allocates to experiments.

## 8. Assumptions and dependencies

Recorded in SOW §6 (A1–A6) and SOW §7 (C1–C6); not duplicated here.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial BRD. BR-01..BR-23 established as the root of the traceability spine |
