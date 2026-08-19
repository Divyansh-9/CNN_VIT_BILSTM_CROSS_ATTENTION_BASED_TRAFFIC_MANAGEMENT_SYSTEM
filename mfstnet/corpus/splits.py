"""Train/val/test assignment, cut by source clip (PRD §8.6).

Splits are assigned **by clip, never by sequence**. At a 30-second stride,
consecutive sequences share 54 of their 60 frames; if some land in train and
others in test, the model has effectively seen the test set. PRD §2.5.1 predicts
exactly this failure around Week 11-12, where it presents as suspiciously good
validation accuracy rather than as an error.

Assignment is deterministic given a seed, so a corpus rebuild reproduces the
same partition (NFR-07). It hashes the clip identifier rather than shuffling a
list, so adding a new clip does not reshuffle the existing ones.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Iterable, Mapping, Sequence as Seq

__all__ = ["assign_splits", "assert_no_clip_leakage", "LeakageError"]

SPLIT_NAMES = ("train", "val", "test")


class LeakageError(AssertionError):
    """A clip's sequences appear in more than one split."""


def _clip_fraction(clip_id: str, seed: int) -> float:
    """Stable value in [0, 1) derived from the clip id and seed.

    Hashing rather than shuffling keeps assignments stable as clips are added:
    a clip's split depends only on its own id, so a corpus rebuilt after new
    footage arrives does not silently move earlier clips between splits.
    """
    digest = hashlib.sha256(f"{seed}:{clip_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def assign_splits(
    clip_ids: Iterable[str],
    ratios: Seq[float] = (0.60, 0.20, 0.20),
    seed: int = 42,
) -> dict[str, str]:
    """Assign each clip to train, val or test.

    Args:
        clip_ids: source clip identifiers. Duplicates are collapsed.
        ratios: train, val, test. Must sum to 1. PRD §8.4 uses 60/20/20 for
            MFSTNet; detection uses 70/15/15 (FR-D05) -- different numbers,
            different units, do not unify them.
        seed: NFR-07.

    Returns:
        clip_id -> split name.

    Raises:
        ValueError: if ratios are malformed, or a split would be empty. An empty
            test split is not a corner case to tolerate: it means every reported
            metric would be computed on nothing.
    """
    if len(ratios) != 3:
        raise ValueError(f"expected 3 ratios (train, val, test), got {len(ratios)}")
    if any(r < 0 for r in ratios):
        raise ValueError(f"ratios must be non-negative, got {ratios}")
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError(f"ratios must sum to 1.0, got {sum(ratios)}")

    unique = sorted(set(clip_ids))
    if not unique:
        raise ValueError("no clips to split")

    train_hi = ratios[0]
    val_hi = ratios[0] + ratios[1]

    assignment: dict[str, str] = {}
    for clip_id in unique:
        f = _clip_fraction(clip_id, seed)
        if f < train_hi:
            assignment[clip_id] = "train"
        elif f < val_hi:
            assignment[clip_id] = "val"
        else:
            assignment[clip_id] = "test"

    empty = [s for s in SPLIT_NAMES if not any(v == s for v in assignment.values())]
    if empty:
        if len(unique) < len(SPLIT_NAMES):
            raise ValueError(
                f"split(s) {empty} are empty with {len(unique)} clip(s). Three "
                f"splits need at least three, and an empty test split means "
                f"every reported metric is computed on nothing."
            )
        # Hashing gives a property worth having: a clip keeps its split as other
        # clips are added, so a corpus can grow without reshuffling. It cannot
        # guarantee coverage — measured with 4 cameras, all four hashed into
        # train and both val and test came out empty.
        #
        # So fall back to hash ORDER plus a quota. Still deterministic, still
        # seeded, non-empty by construction, and it gives up only the stability
        # under additions — which is the lesser loss against a corpus that
        # cannot be built at all.
        ordered = sorted(unique, key=lambda c: _clip_fraction(c, seed))
        n_train = max(1, int(ratios[0] * len(ordered)))
        n_val = max(1, int(ratios[1] * len(ordered)))
        n_train = min(n_train, len(ordered) - 2)
        n_val = min(n_val, len(ordered) - n_train - 1)
        assignment = {}
        for position, clip_id in enumerate(ordered):
            assignment[clip_id] = ("train" if position < n_train else
                                   "val" if position < n_train + n_val else "test")

    return assignment


def assert_no_clip_leakage(
    sequence_clip_ids: Iterable[str],
    sequence_splits: Iterable[str],
) -> None:
    """Raise if any clip's sequences span more than one split.

    Call this at corpus load, every time -- not once during development. This is
    an assertion rather than a warning by deliberate choice: leakage does not
    announce itself, it inflates a metric, and a warning in a log nobody reads is
    indistinguishable from no check at all.

    Raises:
        LeakageError: naming the offending clips and the splits they span.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    for clip_id, split in zip(sequence_clip_ids, sequence_splits):
        seen[clip_id].add(split)

    offenders = {c: sorted(s) for c, s in seen.items() if len(s) > 1}
    if offenders:
        detail = "; ".join(f"{c} in {s}" for c, s in sorted(offenders.items()))
        raise LeakageError(
            f"{len(offenders)} clip(s) span multiple splits: {detail}. Sequences "
            f"from one clip overlap by up to 54 of 60 frames, so this is test-set "
            f"contamination, not a rounding artifact."
        )


def split_counts(assignment: Mapping[str, str]) -> dict[str, int]:
    """Clips per split. For the calibration report and the weekly status."""
    counts = {name: 0 for name in SPLIT_NAMES}
    for split in assignment.values():
        counts[split] += 1
    return counts


def ratio_deviation(
    assignment: Mapping[str, str], ratios: Seq[float] = (0.60, 0.20, 0.20)
) -> dict[str, float]:
    """How far each split's actual share sits from its target.

    Hash-based assignment converges on the target ratios only as clip count
    grows. With few clips it is lumpy: 40 clips at 60/20/20 lands near
    62/25/13, leaving a test split of five.

    That matters more here than the numbers suggest. Under PRD amendment A19 the
    bootstrap resamples **clips**, not sequences, so the effective sample size
    for every reported confidence interval is the number of test clips -- not
    the number of test sequences. Five clips is far too few to separate a
    two-point F1 difference, however many sequences they contain.

    Check this at S6 and report it. If the test split holds fewer than roughly
    ten clips, say so beside the results rather than quoting an interval that
    looks tighter than the evidence supports.
    """
    total = len(assignment)
    if total == 0:
        raise ValueError("no clips assigned")
    counts = split_counts(assignment)
    return {
        name: counts[name] / total - target
        for name, target in zip(SPLIT_NAMES, ratios)
    }


def assign_splits_temporal(
    start_indices: Seq[int],
    *,
    window_frames: int,
    ratios: Seq[float] = (0.60, 0.20, 0.20),
) -> list[str | None]:
    """Split ONE camera's timeline by time, with a gap. `None` means discard.

    `assign_splits` divides by source clip and refuses to run on a single clip,
    which is correct: hash-assigning one clip leaves two splits empty, and an
    empty test split means every reported metric is computed on nothing.

    But a single continuous recording is the deployment shape — one junction,
    one fixed camera — and it can still be split honestly, by time rather than
    by clip. The catch is that consecutive windows overlap: at T=60, step 5 s
    and stride 30 s, neighbouring windows share 11 of their 12 half-minutes. A
    naive time split therefore puts almost the same frames either side of the
    boundary.

    **So windows within one full window-length of a boundary are discarded**,
    not reassigned. That costs data and buys the only thing that matters here:
    a test window cannot share a single frame with a training window.

    Returns a split name per input index, or None for a discarded buffer window.
    """
    if len(ratios) != 3 or abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError(f"ratios must be 3 values summing to 1.0, got {ratios}")
    if window_frames <= 0:
        raise ValueError(f"window_frames must be positive, got {window_frames}")
    if not start_indices:
        raise ValueError("no sequences to split")

    ordered = sorted(start_indices)
    span = ordered[-1] - ordered[0] + window_frames
    train_end = ordered[0] + span * ratios[0]
    val_end = train_end + span * ratios[1]

    out: list[str | None] = []
    for start in start_indices:
        end = start + window_frames
        if end <= train_end - window_frames:
            out.append("train")
        elif start >= train_end + window_frames and end <= val_end - window_frames:
            out.append("val")
        elif start >= val_end + window_frames:
            out.append("test")
        else:
            out.append(None)          # buffer: would straddle a boundary

    for name in SPLIT_NAMES:
        if not any(v == name for v in out):
            kept = sum(1 for v in out if v is not None)
            raise ValueError(
                f"temporal split leaves {name!r} empty: {len(start_indices)} "
                f"window(s), {kept} survived the buffers. One window spans "
                f"{window_frames} frames and each boundary costs one on either "
                f"side, so a short recording cannot yield three disjoint "
                f"splits. Record longer, or add another camera."
            )
    return out
