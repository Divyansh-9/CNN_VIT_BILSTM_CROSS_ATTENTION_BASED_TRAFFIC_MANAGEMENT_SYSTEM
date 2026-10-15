"""Leave-one-camera-out has to be disjoint, complete and reproducible."""

from __future__ import annotations

import pytest

from mfstnet.corpus.folds import MINIMUM_CAMERAS, leave_one_camera_out

CAMERAS = ["m6", "dhaka_a", "dhaka_b", "mumbai", "pov", "south_ext", "video1"]


def test_one_fold_per_camera():
    assert len(leave_one_camera_out(CAMERAS)) == len(CAMERAS)


def test_every_camera_is_tested_exactly_once():
    """The whole point: no camera decides the headline number by itself."""
    tested = [f.test for f in leave_one_camera_out(CAMERAS)]
    assert sorted(tested) == sorted(CAMERAS)


def test_every_camera_is_validated_exactly_once():
    validated = [f.val for f in leave_one_camera_out(CAMERAS)]
    assert sorted(validated) == sorted(CAMERAS)


def test_partitions_are_disjoint_and_complete():
    for fold in leave_one_camera_out(CAMERAS):
        members = list(fold.train) + [fold.val, fold.test]
        assert len(members) == len(set(members)), f"fold {fold.index} overlaps"
        assert set(members) == set(CAMERAS), f"fold {fold.index} drops a camera"


def test_validation_camera_is_never_in_training():
    """Selecting a checkpoint on a camera the model trained on is the leak."""
    for fold in leave_one_camera_out(CAMERAS):
        assert fold.val not in fold.train
        assert fold.test not in fold.train


def test_order_on_disk_does_not_change_the_folds():
    """NFR-07. Reading clips in a different order must give the same folds."""
    a = leave_one_camera_out(CAMERAS)
    b = leave_one_camera_out(list(reversed(CAMERAS)))
    assert a == b


def test_duplicate_camera_ids_collapse():
    folds = leave_one_camera_out(CAMERAS + [CAMERAS[0]])
    assert len(folds) == len(CAMERAS)


def test_split_of_agrees_with_the_partition():
    for fold in leave_one_camera_out(CAMERAS):
        assert fold.split_of(fold.test) == "test"
        assert fold.split_of(fold.val) == "val"
        for camera in fold.train:
            assert fold.split_of(camera) == "train"


def test_unknown_camera_raises_rather_than_defaulting_to_train():
    """A camera silently falling into `train` would leak it into every fold."""
    fold = leave_one_camera_out(CAMERAS)[0]
    with pytest.raises(KeyError):
        fold.split_of("a_camera_that_is_not_in_the_corpus")


@pytest.mark.parametrize("n", [0, 1, 2])
def test_too_few_cameras_refuses(n):
    with pytest.raises(ValueError) as caught:
        leave_one_camera_out(CAMERAS[:n])
    assert str(MINIMUM_CAMERAS) in str(caught.value)


def test_three_cameras_is_the_degenerate_but_legal_case():
    folds = leave_one_camera_out(["a", "b", "c"])
    assert all(len(f.train) == 1 for f in folds)


# --------------------------------------------------------------------------
#  ADR-025: the Indian headline at its minimum size
# --------------------------------------------------------------------------

def test_four_cameras_give_a_valid_three_way_split_with_two_training_cameras():
    """The headline's floor is four cameras (`camera_count`). That has to be a
    workable leave-one-camera-out design, not merely a count: every fold needs
    a distinct test, validation and training set. At four, each fold trains
    on two cameras — legal, and thin, which is why the campus ask is six."""
    from mfstnet.corpus.folds import leave_one_camera_out

    cameras = ["in_a", "in_b", "in_c", "in_d"]
    folds = leave_one_camera_out(cameras)
    assert len(folds) == 4
    for fold in folds:
        assert len(fold.train) == 2
        assert fold.test != fold.val
        assert fold.test not in fold.train and fold.val not in fold.train
    assert sorted(f.test for f in folds) == cameras
    assert sorted(f.val for f in folds) == cameras


def test_every_camera_validates_once_so_class_support_covers_validation_too():
    """Each camera is the validation camera of exactly one fold. A camera with
    no HIGH window would make that fold select its checkpoint on a two-class
    problem — so the per-camera class requirement that `class_coverage`
    applies to test cameras is, by construction, also a validation
    requirement. No separate threshold is needed."""
    from collections import Counter

    from mfstnet.corpus.folds import leave_one_camera_out

    folds = leave_one_camera_out(["a", "b", "c", "d", "e", "f"])
    assert Counter(f.val for f in folds) == Counter("abcdef")
    assert all(len(f.train) == 4 for f in folds)
