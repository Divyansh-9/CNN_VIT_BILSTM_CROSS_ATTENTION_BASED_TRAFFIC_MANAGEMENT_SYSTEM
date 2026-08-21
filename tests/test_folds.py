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
