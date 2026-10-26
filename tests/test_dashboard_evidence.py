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


def test_the_evidence_endpoint_is_read_only():
    client = TestClient(server.app)
    assert client.post("/evidence").status_code == 405
