"""Leave-one-camera-out folds, for when there are too few cameras to split once.

`assign_splits` divides cameras into train/val/test by hashing each camera id.
That is deterministic and reproducible, which is what it was written for, and
with enough cameras it is fine. With **seven** it is a lottery, and the corpus
built on 2026-08-21 drew badly:

* `test` was **one** camera, and it was the M6 Motorway — a UK motorway, the
  least representative clip in a project whose subject is unstructured Indian
  traffic. Every headline generalisation number would have been measured there.
* `val` was **one** camera that contains no HIGH window at all, so validation
  macro F1 was structurally capped: macro F1 scores an absent class 0 by
  convention (P31), and early stopping would have selected on a two-class
  problem while reporting a three-class one.
* Renaming a video file changes its hash, and therefore changes which camera is
  the test set, and therefore changes the headline number. Nothing about that
  is visible in a result CSV.

Leave-one-camera-out removes the lottery rather than re-rolling it. With N
cameras there are N folds; camera `i` is the test set in fold `i` and the
validation set in fold `i-1`, so **every camera is tested exactly once and
validated exactly once**, and the reported figure is a mean over folds with a
confidence interval (NFR-10) instead of one draw.

It does not create data. Twenty-eight independent segments stay twenty-eight
(P45), and a mean over seven folds of one test camera each is still a small
sample — it is simply an honest one, and it uses every camera instead of five.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

__all__ = ["Fold", "eligible_for_test", "leave_one_camera_out"]

MINIMUM_CAMERAS = 3

# Windows a camera must contribute before it can serve as a fold's test set.
# Ten is not a magic number and it is not enough for a tight interval either --
# it is the point below which a per-class F1 cannot move by less than a tenth,
# so a difference between two ablation configs would be quantisation, not
# signal. It is declared here so it appears in one place and in the manifest.
MINIMUM_TEST_SEQUENCES = 10


@dataclass(frozen=True)
class Fold:
    """One camera-disjoint partition. `index` is the fold's position, 0-based."""

    index: int
    train: tuple[str, ...]
    val: str
    test: str

    def split_of(self, camera: str) -> str:
        if camera == self.test:
            return "test"
        if camera == self.val:
            return "val"
        if camera in self.train:
            return "train"
        raise KeyError(
            f"{camera!r} is in no partition of fold {self.index}. Every camera "
            f"in the corpus must land somewhere, or its windows are silently "
            f"dropped from training and from evaluation alike."
        )


def eligible_for_test(
    sequences_per_camera: dict[str, int],
    *,
    minimum: int = MINIMUM_TEST_SEQUENCES,
) -> tuple[list[str], list[str]]:
    """Split cameras into those that can be tested and those that cannot.

    Returns `(eligible, always_train)`, both sorted. A camera with too few
    windows is not discarded -- it stays in training in every fold. Dropping it
    would throw away real data to avoid a reporting problem; keeping it out of
    `test` and `val` fixes the reporting problem and keeps the data.
    """
    eligible = sorted(c for c, n in sequences_per_camera.items() if n >= minimum)
    always_train = sorted(c for c, n in sequences_per_camera.items() if n < minimum)
    return eligible, always_train


def leave_one_camera_out(
    cameras: Iterable[str],
    *,
    always_train: Iterable[str] = (),
) -> list[Fold]:
    """One fold per camera, each with a disjoint train, val and test.

    Cameras are sorted first, so the folds do not depend on the order clips
    happened to be read off disk (NFR-07).

    Fold `i` tests camera `i` and validates camera `i+1` (cyclically). Pairing
    validation with the *next* camera rather than drawing it randomly keeps the
    assignment reproducible and keeps validation camera-disjoint from both the
    other partitions -- selecting a checkpoint on a camera that is also in the
    training set is the leak the whole scheme exists to prevent.

    Cameras named in `always_train` never rotate: they appear in `train` in
    every fold and are never tested or validated. `eligible_for_test` computes
    that set from window counts.
    """
    held = sorted(set(always_train))
    unique = [c for c in sorted(set(cameras)) if c not in held]
    if len(unique) < MINIMUM_CAMERAS:
        raise ValueError(
            f"leave-one-camera-out needs at least {MINIMUM_CAMERAS} cameras "
            f"(train, val and test must each be non-empty and disjoint); got "
            f"{len(unique)}"
            + (f" after holding {len(held)} out as always-train" if held else "")
            + ". With fewer, split one camera's timeline instead: "
            "assign_splits_temporal."
        )

    n = len(unique)
    folds = []
    for i, test in enumerate(unique):
        val = unique[(i + 1) % n]
        train = tuple(sorted(
            [c for c in unique if c not in (test, val)] + held))
        folds.append(Fold(index=i, train=train, val=val, test=test))
    return folds
