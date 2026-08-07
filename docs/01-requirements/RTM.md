# Requirements Traceability Matrix (RTM)

| | |
|---|---|
| **Project** | MFSTNet — CNN-ViT-BiLSTM Cross-Attention Adaptive Traffic Management System |
| **Document** | RTM v1.0 |
| **Date** | 2026-08-07 |
| **Related** | [BRD](../00-planning/BRD.md) · [PRD §9/§10](../00-planning/PRD.md) · [FRD](FRD.md) · [NFR](NFR.md) · [SOW §5](../00-planning/SOW.md) |

---

## 1. Purpose

This is the join table across the traceability spine.

```
BR-xx  →  FR-xx / NFR-xx  →  DES-xx  →  TC-xx  →  M-xx
BRD       PRD §9/§10          Wave 2      Wave 3    SOW §5
```

It answers three questions that no other document can:

- **Forward:** if BR-10 changes, what breaks? (§3)
- **Backward:** does every requirement serve a stated business need, or is it scope creep? (§4)
- **Coverage:** is any requirement untested, or any business need unimplemented? (§5)

**Maintenance.** The RTM is reviewed at every weekly status (SOW §3.1) and updated at each wave gate.
An RTM updated once at the end is worthless — and obviously so to an examiner, which is why it is
one of the artifacts probed hardest.

### 1.1 Column status

`DES-xx` and `TC-xx` are forward references. DES IDs are assigned in Wave 2 (SAD/HLD/LLD, ~Week 5);
TC IDs are reserved in the [FRD](FRD.md) now and defined in Wave 3 (STD, ~Week 11). Cells marked
**W2** or **W3** are scheduled, not forgotten — see [ADR-004](../00-planning/decisions/ADR-004-phased-document-delivery.md).

---

## 2. Requirement inventory

| Class | Count | Source |
|---|---|---|
| Business requirements (BR) | 23 | BRD §5 |
| Functional requirements (FR) | 55 | PRD §9 |
| Non-functional requirements (NFR) | 16 | PRD §10 (13) + NFR.md §6 (3) |
| Milestones (M) | 11 | PRD §18.2 / SOW §5 |

---

## 3. Forward trace — BR → FR/NFR → TC → M

| BR | Business requirement (abbrev.) | Requirements | Design | Test cases | Milestone |
|---|---|---|---|---|---|
| BR-01 | Recognise Indian vehicle classes | FR-D01, FR-D02, FR-D03, FR-D04, FR-D08, FR-P02 | W2 | TC-D01..04, TC-D08, TC-P02 | M1, M2, M8 |
| BR-02 | Beat a general-purpose baseline | FR-D08, FR-D09 | W2 | TC-D08, TC-D09 | M2 |
| BR-03 | Publicly reusable dataset | FR-D06, FR-D07 | — | TC-D06, TC-D07 | M1 |
| BR-04 | Document collection and bias | FR-D02, FR-D05, FR-D07 | — | TC-D02, TC-D05, TC-D07 | M1 |
| BR-05 | Anticipate congestion 60 s ahead | FR-M01, FR-M02, FR-M03, FR-M05, FR-M08 | W2 | TC-M01..03, TC-M05, TC-M08 | M4 |
| BR-06 | Attribute quality to components | FR-M09, FR-M10, FR-M11 | W2 | TC-M09..11 | M5 |
| BR-07 | Gate observable | FR-M04, FR-UI05 | W2 | TC-M04, TC-UI05 | M5, M9 |
| BR-08 | Prediction fast enough to act on | FR-M12, FR-M13, NFR-02 | W2 | TC-M12, TC-M13, TC-N02 | M5 |
| BR-09 | Adapt timing to demand | FR-R01..FR-R05, FR-S01..FR-S04, FR-A01 | W2 | TC-R01..05, TC-S01..04, TC-A01 | M3, M6, M10 |
| BR-10 | Emergency priority passage | FR-P03, FR-P04, FR-A05 | W2 | TC-P03, TC-P04, TC-A05 | M8 |
| BR-11 | No approach starved | FR-R04, FR-A03 | W2 | TC-R04, TC-A03 | M6, M10 |
| BR-12 | Safe under component failure | FR-A04, FR-A06 | W2 | TC-A04, TC-A06 | M10 |
| BR-13 | Statistical evidence of benefit | FR-R06, FR-R07, FR-R08 | — | TC-R06..08 | M7 |
| BR-14 | Operator sees state and rationale | FR-UI01, FR-UI02, FR-UI08 | W2 | TC-UI01, TC-UI02, TC-UI08 | M9 |
| BR-15 | History reviewable | FR-UI03, FR-UI04, FR-UI06, FR-UI07 | W2 | TC-UI03, TC-UI04, TC-UI06, TC-UI07 | M9 |
| BR-16 | Manual control available | FR-UI09, FR-UI10 | W2 | TC-UI09, TC-UI10 | M9 |
| BR-17 | Third-party reproducible | NFR-07, NFR-08, NFR-16 | — | TC-N07, TC-N08 | M5, M7 |
| BR-18 | Raw per-run results published | NFR-09, NFR-10 | — | TC-N09, TC-N10 | M5, M7 |
| BR-19 | Negative results reported | FR-M10, NFR-10, NFR-15 | W2 | TC-M10, TC-N10 | M5 |
| BR-20 | No PII at runtime | NFR-13 | W2 | TC-N13 | M8 |
| BR-21 | Authenticated access | NFR-11, NFR-12 | W2 | TC-N11, TC-N12 | M9 |
| BR-22 | Demonstrable on owned hardware | FR-P01, NFR-01, NFR-14 | W2 | TC-P01, TC-N01 | M8 |
| BR-23 | Deliverable in 20 weeks | PRD §2.4 build order; SOW §2.3 conditional scope | — | Wave-gate review | All |

---

## 4. Backward trace — every requirement to a business need

An FR tracing to no BR is scope creep and should be challenged. All 55 FRs and 16 NFRs trace.

### 4.1 Functional

| Requirements | Serves |
|---|---|
| FR-D01, FR-D02, FR-D03, FR-D04 | BR-01, BR-04 |
| FR-D05 | BR-04 |
| FR-D06, FR-D07 | BR-03, BR-04 |
| FR-D08 | BR-01, BR-02 |
| FR-D09 | BR-02 |
| FR-S01, FR-S02, FR-S03, FR-S04 | BR-09, BR-13 |
| FR-R01, FR-R02, FR-R03, FR-R05 | BR-09 |
| FR-R04 | BR-09, BR-11 |
| FR-R06, FR-R07, FR-R08 | BR-13 |
| FR-M01, FR-M02, FR-M03, FR-M05, FR-M08 | BR-05 |
| FR-M04 | BR-07 |
| FR-M06, FR-M07 | BR-05, BR-06 *(conditional scope)* |
| FR-M09, FR-M10, FR-M11 | BR-06, BR-19 |
| FR-M12, FR-M13 | BR-08 |
| FR-M14 | BR-05, BR-09 |
| FR-P01 | BR-22 |
| FR-P02 | BR-01 |
| FR-P03, FR-P04 | BR-10 |
| FR-A01 | BR-09 |
| FR-A02 | BR-09, BR-12 |
| FR-A03 | BR-11 |
| FR-A04 | BR-12 |
| FR-A05 | BR-10 |
| FR-A06 | BR-12 |
| FR-UI01, FR-UI02, FR-UI08 | BR-14 |
| FR-UI03, FR-UI04, FR-UI06, FR-UI07 | BR-15 |
| FR-UI05 | BR-07, BR-15 |
| FR-UI09, FR-UI10 | BR-16 |

### 4.2 Non-functional

| Requirements | Serves |
|---|---|
| NFR-01 | BR-22 |
| NFR-02 | BR-08 |
| NFR-03, NFR-04, NFR-05 | BR-09, BR-14 |
| NFR-06 | BR-12 |
| NFR-07, NFR-08 | BR-17 |
| NFR-09, NFR-10 | BR-18, BR-19 |
| NFR-11, NFR-12 | BR-21 |
| NFR-13 | BR-20 |
| NFR-14 | BR-22 |
| NFR-15 | BR-06, BR-19 |
| NFR-16 | BR-17 |

**No orphans.** Every FR and NFR serves at least one BR; every BR is served by at least one
requirement.

---

## 5. Coverage analysis

### 5.1 By milestone

| Milestone | Requirements verified | Count | Due |
|---|---|---|---|
| M1 | FR-D01..FR-D07 | 7 | W8 |
| M2 | FR-D08, FR-D09 | 2 | W9 |
| M3 | FR-S01..FR-S04 | 4 | W10 |
| M4 | FR-M01, FR-M02, FR-M03, FR-M05, FR-M08 | 5 | W12 |
| M5 | FR-M04, FR-M06, FR-M07, FR-M09..FR-M13, NFR-02, NFR-07, NFR-09, NFR-10, NFR-15 | 13 | W14 |
| M6 | FR-R01..FR-R05, NFR-03 | 6 | W13 |
| M7 | FR-R06, FR-R07, FR-R08, NFR-09 | 4 | W14 |
| M8 | FR-P01..FR-P04, FR-A05, NFR-01, NFR-13, NFR-14 | 8 | W16 |
| M9 | FR-UI01..FR-UI10, NFR-05, NFR-11, NFR-12 | 13 | W17 |
| M10 | FR-A01..FR-A04, FR-A06, FR-M14, NFR-04, NFR-06 | 8 | W19 |
| M11 | — *(paper submission; verified by receipt)* | — | W20 |
| Continuous | NFR-08, NFR-16 | 2 | — |

### 5.2 Risk concentration

Two observations that should change how the schedule is worked:

**M5 and M9 each carry 13 requirements.** M5 (Week 14) sits at the intersection of the ablation, the
ONNX export, and three Critical reproducibility NFRs — and it follows M4 by only two weeks. M9
(Week 17) carries the entire dashboard plus authentication. Both are single points of schedule
failure. M9's UI work can start earlier than Week 14 against mocked data; doing so is the cheapest
available de-risking.

**M10 verifies the two fallback paths (FR-A06) at Week 19.** That is one week before submission, and
fault-injection testing typically finds real defects. Pull FR-A06 verification forward to Week 17
integration, when there is still time to fix what it finds.

### 5.3 Conditional-scope exposure

FR-M04, FR-M06, and FR-M07 are Phase 2 (PRD §2.4). If Phase 2 is not reached:

| Consequence | Handling |
|---|---|
| BR-07 (gate observable) unmet | Formally descoped in BRD §6, reported as future work |
| FR-UI05 has nothing to display | Gate tracker page shows "not applicable — Phase 1 model", not an empty chart |
| PPO state field `mfst_gate_mean` undefined | Fixed at 0.5, documented in the PRD; the field stays in the 17-dim vector so checkpoints remain valid |
| Ablation configs F, G unavailable | Report A–E; PRD §2.5.3 requires only A, B, C, D, G for distinction, so state which were completed and why |

The third row matters more than it looks. Removing `mfst_gate_mean` from the state vector would
change its dimensionality and invalidate every trained PPO checkpoint (FR-M14). Fixing the value
instead keeps the contract intact.

---

## 6. Change impact procedure

When any requirement changes:

1. Locate its row in §3 and §4.
2. Every DES, TC, and M in those rows is affected — update or re-run them.
3. If the change originates in the PRD, log it in [PRD-CHANGELOG](../00-planning/PRD-CHANGELOG.md).
4. If it adds or removes a requirement, update the counts in §2 and the coverage table in §5.1.
5. Record the change in the weekly status file.

---

## Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-07 | Initial RTM. 23 BR, 55 FR, 16 NFR, 11 M traced. No orphans |
