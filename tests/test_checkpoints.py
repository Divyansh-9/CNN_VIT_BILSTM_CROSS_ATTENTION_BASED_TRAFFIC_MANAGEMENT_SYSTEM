"""Checkpoints from train_mfstnet.py (ADR-025).

Before these existed, every run evaluated its best state and discarded it. The
properties pinned here are the ones that make a checkpoint usable as evidence:
it records where it came from, it records what it started from, and it will
not be silently replaced.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.train_mfstnet import save_checkpoint  # noqa: E402

MANIFEST = {"fold": 0, "domain": "foreign",
            "fold_test_camera": "dhaka_a", "fold_val_camera": "m6",
            "domain_excluded": ["mumbai"],
            "camera_partitions": {"dhaka_a": "real_external",
                                  "m6": "real_external"}}
ROW = {"epochs_run": 3, "macro_f1": 0.5}
STATE = {"head.weight": torch.ones(3, 2)}


def args(tmp_path, *, init_from=None, force=False):
    return SimpleNamespace(seed=42, corpus=tmp_path / "corpus",
                           save_checkpoint=tmp_path / "ckpt",
                           init_from=init_from, force=force)


def save(tmp_path, **kwargs):
    return save_checkpoint(args(tmp_path, **kwargs), "H", STATE, ROW, MANIFEST,
                           "hash123", ["l0", "l1"], "cpu")


def test_a_checkpoint_records_domain_cameras_and_mode(tmp_path):
    path = save(tmp_path)
    assert path.name == "mfstnet_H_seed42_fold0.pt"
    meta = torch.load(path, weights_only=True)["meta"]
    assert meta["mode"] == "from_scratch"
    assert meta["domain"] == "foreign"
    assert (meta["test_camera"], meta["val_camera"]) == ("dhaka_a", "m6")
    assert meta["excluded_cameras"] == ["mumbai"]
    assert meta["preprocessing_hash"] == "hash123"


def test_the_sidecar_carries_the_file_hash(tmp_path):
    path = save(tmp_path)
    sidecar = json.loads(path.with_suffix(".provenance.json")
                         .read_text(encoding="utf-8"))
    assert sidecar["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_fine_tuned_checkpoint_names_its_parent_by_content(tmp_path):
    parent = save(tmp_path)
    child_args = args(tmp_path / "child", init_from=parent)
    child = save_checkpoint(child_args, "H", STATE, ROW, MANIFEST, "hash123",
                            ["l0", "l1"], "cpu")
    meta = torch.load(child, weights_only=True)["meta"]
    assert meta["mode"] == "fine_tune"
    assert meta["init_from_sha256"] == hashlib.sha256(
        parent.read_bytes()).hexdigest()


def test_an_existing_checkpoint_is_not_overwritten_without_force(tmp_path):
    save(tmp_path)
    with pytest.raises(SystemExit, match="evidence"):
        save(tmp_path)
    save(tmp_path, force=True)


def test_a_no_test_checkpoint_never_claims_a_test_score(tmp_path):
    # P99: under --no-test the scored split is validation. A checkpoint that
    # stored that score as `test_macro_f1` would read as a test result.
    run = args(tmp_path)
    run.no_test, run.class_weights = True, "none"
    path = save_checkpoint(run, "H", STATE, ROW, MANIFEST, "hash123",
                           ["l0", "l1"], "cpu")
    meta = torch.load(path, weights_only=True)["meta"]
    assert meta["test_macro_f1"] == ""
    assert (meta["evaluated_on"], meta["class_weights"]) == ("val", "none")


def test_an_older_caller_still_records_test_and_inverse(tmp_path):
    meta = torch.load(save(tmp_path), weights_only=True)["meta"]
    assert meta["test_macro_f1"] == 0.5
    assert (meta["evaluated_on"], meta["class_weights"]) == ("test", "inverse")
