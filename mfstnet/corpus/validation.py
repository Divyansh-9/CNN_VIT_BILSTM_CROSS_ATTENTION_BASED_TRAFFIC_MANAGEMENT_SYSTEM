"""Corpus validation gates — stage S6 of the pipeline (HLD).

Runs after the corpus is built and before anything trains on it. Every check
here answers a question that is cheap now and expensive later.

**Severity is two-valued and the distinction is load-bearing.** BLOCKING stops
the run; ADVISORY is reported and does not. A gate that fires on everything gets
switched off, and then the checks that mattered go with it. So: only conditions
that make a *result invalid* block. Conditions that make a result *weak* advise.

    BLOCKING   degenerate class · clip leakage · unverified test split ·
               degenerate task (nothing transitions)
    ADVISORY   thin test split · high unassigned rate · imbalanced splits

Two of these are not in the original WI-14 list and were added because they can
invalidate results the others would pass:

**Transition rate (PRD A17).** If congestion almost never changes class within
the 60-second horizon, a last-value baseline sits near the ceiling and *no model
can be ranked against another*. A corpus can have a perfect class balance and
still be unlearnable. This is the single most valuable check in the file.

**Effective sample size (PRD A19).** The bootstrap resamples **clips**, not
sequences, so the effective *n* behind every confidence interval is the number
of test clips. Ten thousand sequences drawn from five clips give intervals that
look tight and are not.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .labels import CongestionClass

__all__ = [
    "Severity",
    "GateResult",
    "CorpusReport",
    "SequenceRecord",
    "CorpusValidationError",
    "validate_corpus",
]

LANES = ("N", "S", "E", "W")

# Thresholds. Config values, not literals — recalibration is expected (P1).
MIN_CLASS_SHARE = 0.05          # HLD S6: any class below this fails
MIN_TRANSITION_RATE = 0.05      # PRD A17: below this the task cannot rank models
MIN_TEST_CLIPS = 10             # PRD A19: effective n for the cluster bootstrap
MAX_UNASSIGNED_RATE = 0.15      # HLD S3: above this the lane polygons are wrong


class Severity(Enum):
    BLOCKING = "BLOCKING"
    ADVISORY = "ADVISORY"


class CorpusValidationError(RuntimeError):
    """One or more blocking gates failed."""


@dataclass(frozen=True)
class SequenceRecord:
    """One row of the sequence manifest, as far as validation cares.

    `labels_now` is the class at the **last observed frame** — what a last-value
    baseline would predict. Storing it costs nothing at build time (S4 already
    has the counts) and buys two things: the transition-rate gate below, and the
    Naive baseline of PRD §14.3 for free.
    """

    seq_id: str
    clip_id: str
    split: str
    labels: tuple[int, ...]          # at t_label, per lane
    labels_now: tuple[int, ...]      # at t_end, per lane
    density_band: str = "medium"
    label_origin: str = "auto"       # auto | verified

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.labels_now):
            raise ValueError(f"{self.seq_id}: labels and labels_now differ in length")
        if self.split not in ("train", "val", "test"):
            raise ValueError(f"{self.seq_id}: unknown split {self.split!r}")

    @property
    def transitions(self) -> int:
        """Lanes whose class changes over the horizon."""
        return sum(1 for a, b in zip(self.labels_now, self.labels) if a != b)


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    severity: Severity
    detail: str

    def __str__(self) -> str:
        mark = "PASS" if self.passed else self.severity.value
        return f"[{mark:8s}] {self.name}: {self.detail}"


@dataclass
class CorpusReport:
    gates: list[GateResult] = field(default_factory=list)

    @property
    def blocking_failures(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed and g.severity is Severity.BLOCKING]

    @property
    def advisories(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed and g.severity is Severity.ADVISORY]

    @property
    def ok(self) -> bool:
        return not self.blocking_failures

    def raise_if_blocking(self) -> None:
        """Call this before training. Do not make it optional.

        Raises:
            CorpusValidationError: listing every blocking failure.
        """
        if self.ok:
            return
        lines = "\n".join(f"  - {g.name}: {g.detail}" for g in self.blocking_failures)
        raise CorpusValidationError(
            f"{len(self.blocking_failures)} blocking gate(s) failed:\n{lines}"
        )

    def __str__(self) -> str:
        return "\n".join(str(g) for g in self.gates)


# ------------------------------------------------------------------ gates --

def _class_histogram(records: Sequence[SequenceRecord]) -> Counter[int]:
    hist: Counter[int] = Counter()
    for r in records:
        hist.update(r.labels)
    return hist


def check_class_distribution(
    records: Sequence[SequenceRecord], min_share: float = MIN_CLASS_SHARE
) -> GateResult:
    """No congestion class may be vanishingly rare.

    A degenerate class makes macro F1 ≥ 0.80 unreachable and makes every
    per-class figure for that class meaningless. Printing the histogram matters
    as much as the verdict — the fix is usually a threshold change (P1), and the
    person deciding needs the shape of the data.
    """
    hist = _class_histogram(records)
    total = sum(hist.values())
    if not total:
        return GateResult("class_distribution", False, Severity.BLOCKING, "corpus is empty")

    shares = {c: hist.get(int(c), 0) / total for c in CongestionClass}
    shown = " · ".join(f"{c.label} {hist.get(int(c), 0)} ({shares[c]:.1%})" for c in CongestionClass)
    rare = [c.label for c in CongestionClass if shares[c] < min_share]

    if rare:
        return GateResult(
            "class_distribution", False, Severity.BLOCKING,
            f"{', '.join(rare)} below {min_share:.0%} — {shown}. "
            f"Recalibrate the §14.1 thresholds (pending item P1) before training; "
            f"a class this rare cannot be learned or measured.",
        )
    return GateResult("class_distribution", True, Severity.ADVISORY, shown)


def check_transition_rate(
    records: Sequence[SequenceRecord], min_rate: float = MIN_TRANSITION_RATE
) -> GateResult:
    """The task must actually require prediction (PRD A17).

    If the class at t+60s almost always equals the class now, a last-value
    baseline sits near the ceiling and every model ties. The corpus can be
    perfectly balanced and still unable to separate any two methods.
    """
    lane_obs = sum(len(r.labels) for r in records)
    if not lane_obs:
        return GateResult("transition_rate", False, Severity.BLOCKING, "corpus is empty")

    transitions = sum(r.transitions for r in records)
    rate = transitions / lane_obs
    detail = f"{transitions} of {lane_obs} lane-windows change class ({rate:.1%})"

    if rate < min_rate:
        return GateResult(
            "transition_rate", False, Severity.BLOCKING,
            f"{detail} — below {min_rate:.0%}. A last-value baseline would score "
            f"~{1 - rate:.0%} and NO model could be ranked against another. Revisit "
            f"the horizon or the class boundaries before building on this corpus.",
        )
    return GateResult("transition_rate", True, Severity.ADVISORY, detail)


def check_split_disjoint(records: Sequence[SequenceRecord]) -> GateResult:
    """No clip may appear in more than one split.

    Sequences from one clip overlap by up to 54 of 60 frames, so a straddling
    clip is test-set contamination. Blocking, always — this one inflates a
    metric rather than breaking a run, which is why it must not be a warning.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    for r in records:
        seen[r.clip_id].add(r.split)
    offenders = {c: sorted(s) for c, s in seen.items() if len(s) > 1}

    if offenders:
        detail = "; ".join(f"{c} in {s}" for c, s in sorted(offenders.items())[:5])
        return GateResult(
            "split_disjoint", False, Severity.BLOCKING,
            f"{len(offenders)} clip(s) span multiple splits: {detail}",
        )
    return GateResult("split_disjoint", True, Severity.ADVISORY, f"{len(seen)} clips, all disjoint")


def check_test_split_verified(records: Sequence[SequenceRecord]) -> GateResult:
    """The test split must carry human-verified labels (PRD A9).

    Labels come from the detector, and three §14.3 baselines also consume
    detector counts — their errors correlate with the label errors and score as
    correct, while MFSTNet's independent errors score as wrong. Reporting against
    auto-labelled test data biases the comparison against our own model.
    """
    test = [r for r in records if r.split == "test"]
    if not test:
        return GateResult("test_split_verified", False, Severity.BLOCKING, "test split is empty")

    unverified = sum(1 for r in test if r.label_origin != "verified")
    if unverified:
        return GateResult(
            "test_split_verified", False, Severity.BLOCKING,
            f"{unverified} of {len(test)} test sequences are still label_origin='auto'. "
            f"Reporting against auto-labelled test data biases the §14.3 comparison "
            f"AGAINST MFSTNet (A9/A11).",
        )
    return GateResult("test_split_verified", True, Severity.ADVISORY,
                      f"all {len(test)} test sequences verified")


def check_effective_sample_size(
    records: Sequence[SequenceRecord], min_clips: int = MIN_TEST_CLIPS
) -> GateResult:
    """Effective n for the cluster bootstrap is the CLIP count (PRD A19).

    Advisory rather than blocking: a thin test split does not make results wrong,
    it makes the intervals wider than they will appear if anyone forgets to
    resample at clip level. Report it beside the results.
    """
    clips = {r.clip_id for r in records if r.split == "test"}
    n = len(clips)
    detail = f"test split draws on {n} clip(s) — this is the effective n, not the sequence count"

    if n < min_clips:
        return GateResult(
            "effective_sample_size", False, Severity.ADVISORY,
            f"{detail}. Below {min_clips}, a two-point F1 difference cannot be "
            f"separated however many sequences those clips contain. State n beside "
            f"every confidence interval.",
        )
    return GateResult("effective_sample_size", True, Severity.ADVISORY, detail)


def check_unassigned_rate(
    unassigned_by_clip: Mapping[str, float], max_rate: float = MAX_UNASSIGNED_RATE
) -> GateResult:
    """Detections falling in no lane polygon (HLD S3).

    Some are correct — a vehicle crossing the middle of the junction belongs to
    no approach. A high rate means the polygons are drawn wrong, and it is the
    only early signal available before labels are compared to anything.
    """
    if not unassigned_by_clip:
        return GateResult("unassigned_rate", True, Severity.ADVISORY, "not measured")

    worst = sorted(unassigned_by_clip.items(), key=lambda kv: -kv[1])
    mean = sum(unassigned_by_clip.values()) / len(unassigned_by_clip)
    over = [(c, r) for c, r in worst if r > max_rate]

    if over:
        detail = ", ".join(f"{c} {r:.1%}" for c, r in over[:4])
        return GateResult(
            "unassigned_rate", False, Severity.ADVISORY,
            f"{len(over)} clip(s) above {max_rate:.0%}: {detail}. Re-draw the lane "
            f"polygons — counts from these clips are missing vehicles.",
        )
    return GateResult("unassigned_rate", True, Severity.ADVISORY,
                      f"mean {mean:.1%}, worst {worst[0][0]} {worst[0][1]:.1%}")


def check_split_balance(
    records: Sequence[SequenceRecord],
    target: tuple[float, float, float] = (0.60, 0.20, 0.20),
    max_deviation: float = 0.10,
) -> GateResult:
    """Sequences per split, against the intended ratio.

    An earlier version of this gate returned `passed=True` unconditionally — it
    reported the numbers and flagged nothing. The end-to-end demo then produced a
    **58/4/38** split from 24 clips and the gate said PASS. A check that cannot
    fail is decoration, so it now flags real deviation.

    Advisory, not blocking: a skewed split does not make results wrong, it makes
    early stopping unreliable (a 4% validation split is noise) and the test split
    unrepresentative.

    The cause is upstream and worth understanding: splits are assigned by hashing
    the **clip** id, and hash assignment is lumpy at small clip counts. Below ~60
    source clips this gate will fire routinely, and the fix is more clips rather
    than a different splitter.
    """
    counts = Counter(r.split for r in records)
    total = sum(counts.values())
    if not total:
        return GateResult("split_balance", False, Severity.ADVISORY, "corpus is empty")

    shares = {s: counts.get(s, 0) / total for s in ("train", "val", "test")}
    detail = " · ".join(f"{s} {counts.get(s, 0)} ({shares[s]:.0%})"
                        for s in ("train", "val", "test"))

    worst = max(
        (abs(shares[s] - t), s) for s, t in zip(("train", "val", "test"), target)
    )
    if worst[0] > max_deviation:
        return GateResult(
            "split_balance", False, Severity.ADVISORY,
            f"{detail} — '{worst[1]}' is {worst[0]:.0%} off target. Hash-based clip "
            f"assignment is lumpy below ~60 source clips; collect more clips rather "
            f"than reaching for a different splitter.",
        )
    return GateResult("split_balance", True, Severity.ADVISORY, detail)


# ----------------------------------------------------------- orchestration --

def validate_corpus(
    records: Iterable[SequenceRecord],
    unassigned_by_clip: Mapping[str, float] | None = None,
    *,
    require_verified_test: bool = True,
) -> CorpusReport:
    """Run every gate and return the report.

    Args:
        records: the sequence manifest.
        unassigned_by_clip: per-clip rate of detections matching no lane.
        require_verified_test: set False only while developing against a dev
            corpus, where human verification does not apply. **Never** for a
            reported run — the dev-corpus guard in `sources` covers that case.

    Returns:
        A report. Call `raise_if_blocking()` before training.
    """
    recs = list(records)
    report = CorpusReport()
    report.gates.append(check_class_distribution(recs))
    report.gates.append(check_transition_rate(recs))
    report.gates.append(check_split_disjoint(recs))
    report.gates.append(check_effective_sample_size(recs))
    report.gates.append(check_split_balance(recs))
    report.gates.append(check_unassigned_rate(unassigned_by_clip or {}))
    if require_verified_test:
        report.gates.append(check_test_split_verified(recs))
    return report
