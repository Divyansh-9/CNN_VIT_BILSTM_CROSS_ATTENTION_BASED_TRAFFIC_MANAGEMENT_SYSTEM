"""ADR-014 Panel A: the dashboard's evidence comes from committed files, unchanged.

The numbers in `/evidence` must be the numbers in the committed result files,
read and never retyped, and each must carry the commit that produced it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import server.app as server  # noqa: E402

RESULTS = Path("experiments/results/bellevue_pilot")

# V3: Bellevue-derived files are absent from the sanitised public tree; the tests
# that read them skip there, and run everywhere the files exist.
needs_bellevue = pytest.mark.skipif(not RESULTS.exists(),
                                     reason="Bellevue-derived file absent (public tree)")


@pytest.fixture
def evidence():
    return TestClient(server.app).get("/evidence").json()


@needs_bellevue
def test_p105_numbers_are_the_committed_ones(evidence):
    p105 = json.loads((RESULTS / "p105_results.json").read_text(encoding="utf-8"))
    study = next(s for s in evidence["studies"] if s["id"] == "P105")
    mae, f1 = study["rows"]
    assert mae["values"] == {"ridge": round(p105["pooled"]["ridge"]["mae"], 4),
                             "persistence": round(p105["pooled"]["persistence"]["mae"], 4)}
    assert mae["ci95"] == p105["primary"]["persistence - ridge, count MAE"]["ci95"]
    assert mae["significant"] is True and f1["significant"] is False
    assert mae["difference_of"] == "persistence − ridge" and f1["difference_of"] == "ridge − persistence"
    assert mae["positive_favours"] == f1["positive_favours"] == "ridge"
    assert study["scope"]["windows"] == p105["windows"] and study["scope"]["blocks"] == p105["blocks"]
    assert study["scope"]["excluded_cameras"] == ["116th_NE12th"]


@needs_bellevue
def test_p103_difference_is_reported_in_the_direction_of_its_label(evidence):
    p103 = json.loads((RESULTS / "p103_results.json").read_text(encoding="utf-8"))
    (row,) = next(s for s in evidence["studies"] if s["id"] == "P103")["rows"]
    primary = p103["primary"]["C1-L - persistence"]
    assert row["difference"] == -primary["point"]                    # persistence − C1-L
    assert row["ci95"] == [-primary["ci95"][1], -primary["ci95"][0]]


@needs_bellevue
def test_every_study_names_its_file_and_commit_and_is_labelled_historical(evidence):
    assert "Not a live performance guarantee" in evidence["label"]
    assert any("P97a" in limit for limit in evidence["limitations"])
    for study in evidence["studies"]:
        assert study["file"].startswith("experiments/results/")
        assert study["commit"] and study["date"]


def test_the_limitations_state_the_encoding_as_it_is_since_p110():
    # Read from the constant, so it holds without the Bellevue results present.
    # D2 fixed the same stale sentence in the dashboard's banner; this one is
    # shown in the Results region and must not say the opposite.
    text = " ".join(server.EVIDENCE_LIMITS)
    assert "0.0 means an approach has no forecast" in text
    assert "LOW is 1/3" in text
    assert "0.0 = LOW" not in text and "same value as LOW" not in text
    assert "P97a Part 2" in text


def test_without_git_the_commit_comes_from_the_build_time_map(tmp_path, monkeypatch):
    # A container has no history (D15): the map written at image build answers.
    import subprocess

    def no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    target = Path("experiments/results/bellevue_pilot/p105_results.json")
    commits = tmp_path / "commits.json"
    commits.write_text(json.dumps({target.as_posix(): {"commit": "0c97ccb", "date": "2026-10-16"}}),
                       encoding="utf-8")
    monkeypatch.setenv(server.EVIDENCE_COMMITS_ENV, str(commits))
    assert server.committed_at(target) == {"file": target.as_posix(), "commit": "0c97ccb",
                                           "date": "2026-10-16"}
    # A file the map does not name, an unreadable map, and no map at all are
    # each "uncommitted", never a guess.
    assert server.committed_at(Path("experiments/results/other.json"))["commit"] == "uncommitted"
    commits.write_text("not json", encoding="utf-8")
    assert server.committed_at(target)["commit"] == "uncommitted"
    monkeypatch.delenv(server.EVIDENCE_COMMITS_ENV)
    assert server.committed_at(target)["commit"] == "uncommitted"


def test_the_evidence_endpoint_is_read_only():
    client = TestClient(server.app)
    assert client.post("/evidence").status_code == 405


# D34: the signal study comes from its committed file, unchanged, and the
# intersections from their heartbeats alone.
needs_ceiling = pytest.mark.skipif(not server.SIGNAL_STUDY.exists(), reason="ceiling stats absent (public tree)")


@needs_ceiling
def test_signal_study_numbers_are_the_committed_numbers():
    stats = json.loads(server.SIGNAL_STUDY.read_text(encoding="utf-8"))
    study = server.signal_study()
    assert study["seeds"] == len(stats["primary_evaluation_seeds"])
    assert study["reading"] == stats["decision"]["reading"]
    assert [a["mean"] for a in study["arms"]] == sorted(a["mean"] for a in study["arms"])
    named = {a["name"]: a for a in study["arms"]}
    source = stats["arms"]["webster_split_clamped_s600_lost0"]
    assert named["Webster split, clamped"]["mean"] == round(source["mean_total_delay_s"], 2)
    assert named["Webster split, clamped"]["ci95"] == [round(v, 2) for v in source["ci95"]]
    assert len(study["arms"]) == len(stats["arms"])
    assert study["commit"]


def test_sites_lists_only_what_has_reported_and_marks_silence(monkeypatch, tmp_path):
    from contracts.mqtt import Heartbeat, Mode

    monkeypatch.setattr(server, "DATABASE", tmp_path / "s.db")
    with TestClient(server.app) as client:
        assert client.get("/sites").json() == {"sites": []}
        beat = Heartbeat(edge_status="online", mode=Mode.NORMAL, mfstnet_active=False, ppo_active=False,
                         source={"kind": "replay", "session": "0123456789ab", "label": "clip", "position_s": 1.0, "duration_s": 9.0})
        server.store_heartbeat("a", beat.encode())
        site = client.get("/sites").json()["sites"][0]
        assert (site["id"], site["kind"], site["label"], site["stale"]) == ("a", "replay", "clip", False)
        monkeypatch.setattr(server.time, "time", lambda real=server.time.time: real() + 60)
        assert client.get("/sites").json()["sites"][0]["stale"] is True


def test_signal_study_is_absent_when_its_file_is(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "SIGNAL_STUDY", tmp_path / "none.json")
    assert server.signal_study() is None
