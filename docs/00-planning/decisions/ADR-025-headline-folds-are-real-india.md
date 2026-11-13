# ADR-025 — The headline evaluation is scored on Indian cameras only

**Status:** Proposed · **Date:** 2026-10-15 · **Amends [ADR-019](ADR-019-leave-one-camera-out-evaluation.md)'s fold set; scopes three claims in [CLAIMS.yaml](../CLAIMS.yaml); implements [P86](../PRD-CHANGELOG.md), approved in principle by the project owner 2026-10-15**

## Context

[P86](../PRD-CHANGELOG.md) found that the `domain` claim cannot pass while the
British motorway and the Dhaka cameras stay leave-one-camera-out folds, because
`evaluation_contains_target_domain` fails if **any** fold's test camera is off
target. [P85](../PRD-CHANGELOG.md) had already decided those cameras are worth
keeping, as the project's only external-domain test. Both decisions are right;
they need different evaluations.

The project owner approved the resolution **in principle** on 2026-10-15: the
headline is scored on eligible `real_india` cameras, and `real_external` is
reported separately. The approval covers the protocol. It does not say the
Indian-domain requirement is met — today **no** fold qualifies.

Implementing the approval turned up two traps.

**1. The vacuous pass.** Scoped to Indian folds, "every fold's test camera is on
target" is true over **zero** folds, and zero is what the corpus holds. A
naive scope change would turn `domain` green with no Indian data.

**2. The half-scoped protocol.** `camera_count` and `class_coverage` also run
over every fold. `camera_count` passes today on three Bangladeshi cameras and a
British motorway. Scoping only `domain` would print an Indian headline beside a
green camera count that contains none of its cameras.

## Decision

**1. Three partitions, three evaluations.** Partitions come from
`data/cameras.json` and `data/sources.json`, never from a filename
([P58](../PRD-CHANGELOG.md)).

| Evaluation | Test cameras | Reported as |
|---|---|---|
| **Headline** | fold-eligible `real_india` only | the paper's result |
| **External** | each `real_external` camera, separately | per camera, then an unweighted mean labelled *external* |
| **Synthetic** | none | never an evaluation; pretraining only, under [ADR-024](ADR-024-synthetic-data-generates-conditions-not-pixels.md) |

**2. Every evaluation claim is scoped together.** `domain`, `class_coverage` and
`camera_count` carry `scope: headline`. `viewpoint` and `releasable` describe
the whole corpus and stay unscoped.

**3. An empty scope fails.** A claim whose scope holds no fold fails with "a
claim over an empty set is not evidence". This is implemented in `run()` in
`scripts/check_claims.py`, not in each check, so a future check cannot forget it.

**4. The thresholds do not move.** ADR-019's ten windows per test camera — 390 s
of continuous footage at the manifest's window and stride — `minimum_support: 10`
per class per fold, and `minimum_cameras: 4` all apply to the headline unchanged.
Overlapping windows from one camera never stand in for a second camera.

**5. Validation cameras come from `real_india` too.** ADR-019 assigns each fold a
validation camera, which drives early stopping and checkpoint selection. If it
could be the motorway, the headline model would be chosen by performance on the
wrong domain. Gulrajani and Lopez-Paz found model selection mattered more than
method across the domain-generalisation literature (Progress Report §2.12). With
four Indian cameras, each headline fold tests on one, validates on another and
trains on the rest.

**6. Training composition is pre-registered here, before any Indian result
exists.** Two defensible options; the choice must be made before results, so it
is not made after.

| | (a) Indian-only training | (b) all real cameras except the fold's test and val |
|---|---|---|
| headline claim | "trained and tested on Indian cameras" — clean | "tested on Indian cameras", trained on a mix |
| training data | less | more |
| external arm | **reuses the headline models**: no external camera was trained on, so no leak and no extra runs | needs extra runs — each external camera must be held out of training before it can be tested |

**Chosen by the project owner on 2026-10-15: (a) as the headline, (b) as a
declared secondary experiment.** Indian training cameras, Indian validation
cameras for checkpoint selection, held-out Indian test cameras. In (b) each
external test camera is held out of training and of checkpoint selection, and
the comparison reports whether foreign data helps or hurts. Recorded here before
any Indian result exists, which is the point of recording it.

**The split is viable at the threshold, verified rather than assumed.**
Leave-one-camera-out gives fold *i* test camera *i* and validation camera *i+1*.
At four cameras every fold has a distinct test, validation and training set,
with **two** training cameras each, which clears `MINIMUM_CAMERAS = 3` in
`mfstnet/corpus/folds.py`. Every camera validates exactly once, so the
per-class support `class_coverage` requires of test cameras is by construction
also met by every validation camera. No threshold changes. Four is the floor and
it is thin: the six-viewpoint campus ask (S19) gives four training cameras per
fold. `tests/test_folds.py` pins both properties.

**7. Existing results are relabelled, not discarded.** The committed A–H
leave-one-camera-out suite is cross-camera evidence from heterogeneous South
Asian traffic plus one structured-traffic camera. It stays in the record as
exactly that — the synopsis already says so — and it is never the Indian
headline.

## How the change lands

The checker is ready; `CLAIMS.yaml` is not edited until this ADR is signed.

```bash
python scripts/check_claims.py                      # the claims of record
python scripts/check_claims.py --protocol headline  # this ADR, previewed
```

On 2026-10-15, under the preview, `domain`, `class_coverage` **and**
`camera_count` all fail with an empty headline scope. That is the honest
state: `camera_count` passes today only because it counts external cameras.

Accepting this ADR is a three-line diff to `CLAIMS.yaml` (`scope: headline` on
the three evaluation claims). The data side is already built and runs today:

```bash
python scripts/resplit_corpus.py ... --domain foreign   # mode 1, the development baseline
python scripts/resplit_corpus.py ... --domain india     # the headline; refuses an empty domain
python scripts/resplit_corpus.py ... --domain mixed     # default; byte-identical to every committed fold
python scripts/train_mfstnet.py ... --save-checkpoint DIR
python scripts/train_mfstnet.py ... --init-from PT      # mode 2, fine-tuning
```

`foreign` and `india` are disjoint, and a camera whose properties were never
inspected is in neither. That keeps the foreign baseline clean of Indian
footage, so mode 3's question — does foreign pretraining help India — is not
answered by a model that has already seen India.

## Consequences

**Gained.** A headline that answers the question the paper asks. An external
result that is kept and labelled rather than averaged in. And a claims gate that
cannot pass on an empty set or on a half-scoped protocol.

**Cost.** Three claims are red under this protocol where today one of them is
green. That is not a regression in evidence. It is the current evidence read
against the right question.

**Unchanged.** Every claim of record, until signature. The collection blocker
is unchanged too: the headline needs four licensed Indian fixed cameras with
390 s of continuous footage each and ten instances of every class. Campus
recording (S19) is still the only route identified that could supply them.

## Acceptance

Unaccepted. P86 is approved **in principle** by the project owner. Per
[ADR-006](ADR-006-curate-then-collect-dataset.md) and
[ADR-008](ADR-008-prototype-descoping.md), that signature is not a faculty-guide
signature. Decision 6 is the open choice.
