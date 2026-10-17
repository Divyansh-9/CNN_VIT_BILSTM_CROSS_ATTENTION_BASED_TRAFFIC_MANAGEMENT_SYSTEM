"""V3-4: the public-tree builder excludes every restricted file and proves it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_public_tree import build, excluded, needs_review  # noqa: E402


@pytest.mark.parametrize("path", [
    "experiments/results/bellevue_pilot/p105_ridge_v1.json",
    "experiments/results/bellevue_pilot/deep/nested.csv",
    "experiments/results/v1/v1_sample_manifest.json",
    "data/corpus/counts.csv", "data/corpus/detections.csv",
    "data/lanes/cam_preview.jpg", "data/lanes_k4/x/y.png", "data/clip.mp4",
    "docs/demo/MFSTNet-Synopsis-Report.docx",
])
def test_restricted_files_are_excluded_with_a_reason(path):
    assert excluded(path)


@pytest.mark.parametrize("path", [
    "simulation/runner.py", "data/cameras.json", "data/lanes/cam.json",
    "experiments/results/ceiling/ceiling_runs.csv", "experiments/results/v1/COUNTING_INSTRUCTIONS.md",
    "docs/00-planning/PRD.md", "LICENSE",
])
def test_ordinary_files_are_kept(path):
    assert excluded(path) is None


def test_build_drops_restricted_files_flags_mentions_and_rescans(tmp_path):
    files = [("simulation/runner.py", b"x = 1\n"),
             ("experiments/results/bellevue_pilot/a.json", b"{}"),
             ("data/lanes/p.jpg", b"\xff\xd8"),
             ("docs/notes.md", b"Bellevue aggregate 0.224"),
             ("experiments/results/loco/fold0.csv", b"a,b\n")]
    manifest = build(files, tmp_path / "out")
    assert manifest["passed"] and manifest["kept"] == 3
    assert {d["path"] for d in manifest["excluded"]} == {
        "experiments/results/bellevue_pilot/a.json", "data/lanes/p.jpg"}
    assert {r["path"] for r in manifest["review_required"]} == {
        "docs/notes.md", "experiments/results/loco/fold0.csv"}
    assert not (tmp_path / "out/experiments/results/bellevue_pilot").exists()
    saved = json.loads((tmp_path / "out/PUBLIC_TREE_MANIFEST.json").read_text(encoding="utf-8"))
    assert saved["note"].startswith("does not resolve licensing")


def test_build_refuses_a_non_empty_directory(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out/old.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="not empty"):
        build([], tmp_path / "out")


def test_review_flags_only_text_mentions():
    assert needs_review("docs/a.md", b"see Bellevue")
    assert needs_review("models/blob.bin", b"Bellevue") is None
