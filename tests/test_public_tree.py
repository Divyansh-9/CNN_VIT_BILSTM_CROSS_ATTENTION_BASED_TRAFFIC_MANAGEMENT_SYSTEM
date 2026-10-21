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
    "scripts/synopsis_content.py", "scripts/build_synopsis_pptx.py", "tests/test_deck_geometry.py",
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
    assert manifest["passed"] and manifest["kept"] == 2
    assert {d["path"] for d in manifest["excluded"]} == {
        "experiments/results/bellevue_pilot/a.json", "data/lanes/p.jpg",
        "experiments/results/loco/fold0.csv"}
    # P136: corpus-derived results are now excluded, not merely flagged.
    assert {r["path"] for r in manifest["review_required"]} == {"docs/notes.md"}
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


@pytest.mark.parametrize("path,content,category", [
    ("scripts/fetch_bellevue.py", b"x", "dataset-specific material"),
    ("scripts/p105_eval.py", b"ROOT = 'experiments/results/bellevue_pilot'", "dataset-specific material"),
    ("experiments/results/loco/fold0.csv", b"a,b", "corpus-derived results"),
    ("docs/note.md", b"The Bellevue licence is unresolved", "licence reference"),
    ("docs/report.md", b"P105 ridge MAE 0.748 against 0.972", "aggregate results"),
    ("docs/other.md", b"see the Bellevue cameras", "mention only"),
])
def test_review_categories_are_restrictive_first(path, content, category):
    from scripts.build_public_tree import review_category

    assert review_category(path, content) == category


@pytest.mark.parametrize("path", [
    "experiments/results/loco/fold0/x.csv", "experiments/results/baselines_loco/a.csv",
    "scripts/p105_eval.py", "scripts/p99b_compare.py", "scripts/fetch_bellevue.py",
    "scripts/v1_label_page.py",
])
def test_the_owners_disposition_excludes_corpus_results_and_pipeline_scripts(path):
    assert excluded(path) and "P136" in excluded(path)


@pytest.mark.parametrize("path", ["server/app.py", "simulation/count_forecasts.py", "BUILD-LOG.md"])
def test_core_code_and_records_stay_in_and_are_flagged_not_dropped(path):
    from scripts.build_public_tree import disposition

    assert excluded(path) is None
    assert disposition(path, "dataset-specific material").startswith("kept")


def test_the_simulation_version_preflight_names_every_mismatch():
    """P137: an unpinned SUMO once changed a committed result; drift must fail loudly."""
    from importlib import metadata

    from scripts.check_sim_versions import PACKAGES, mismatches, pins

    pinned = pins("eclipse-sumo==1.27.1  # pinned\nsumo-data==1.27.1\ntraci==1.27.1\n"
                  "sumolib==1.27.1\ngymnasium==1.3.0\nstable_baselines3==2.9.0\n")
    exact = {**pinned}
    assert mismatches(pinned, lambda p: exact[p]) == []
    drifted = {**exact, "eclipse-sumo": "1.28.0"}
    assert mismatches(pinned, lambda p: drifted[p]) == [
        "eclipse-sumo: installed 1.28.0, requirements.txt pins 1.27.1"]
    # D4: eclipse-sumo pulls sumo-data in unversioned; a clean install drew 1.28.0.
    data_drift = {**exact, "sumo-data": "1.28.0"}
    assert mismatches(pinned, lambda p: data_drift[p]) == [
        "sumo-data: installed 1.28.0, requirements.txt pins 1.27.1"]

    def missing(p):
        raise metadata.PackageNotFoundError(p)

    assert len(mismatches(pinned, missing)) == len(PACKAGES)
    assert mismatches({}, lambda p: "x")[0].endswith("not pinned in requirements.txt")
