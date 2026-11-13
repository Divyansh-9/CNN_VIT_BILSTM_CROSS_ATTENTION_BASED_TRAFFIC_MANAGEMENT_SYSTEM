"""The density gate on corpus yield.

Triage (`scripts/triage_footage.py`) admits a clip on length, a steady camera,
and a moving scene. None of those is a statement that the road carries traffic,
and on the surveyed footage the two run in opposite directions: the longest
clip that passes triage averages 7.1 detections per frame and the densest
averages 66.6 in a third of the duration.

A camera whose *mean* frame sits below PRD §14.1's MEDIUM→HIGH boundary of 15
vehicles cannot show sustained HIGH congestion. Calibrating thresholds per
camera does not rescue it — percentiles will manufacture a HIGH class out of an
empty road, and every label in it is noise. So the gate is on the raw rate, not
on anything downstream of it.

These pin the gate itself and the arithmetic that feeds it.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.corpus_yield import main


def survey(tmp_path: Path, entries: list[dict]) -> Path:
    """A survey_summary.json with only the fields corpus_yield reads."""
    path = tmp_path / "survey_summary.json"
    rows = [
        {
            "camera": e["camera"],
            "camera_id": e.get("camera_id", e["camera"]),
            "clip": e.get("clip", e["camera"] + ".mp4"),
            "seconds": e.get("seconds", 1200.0),
            "detections": e["detections"],
            "unassigned_rate": e.get("unassigned_rate", 0.0),
        }
        for e in entries
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def run(tmp_path: Path, entries: list[dict], *extra: str) -> list[dict]:
    out = tmp_path / "yield.csv"
    main(["--survey", str(survey(tmp_path, entries)), "--out", str(out), *extra])
    with out.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_a_thin_camera_fails_the_gate_however_long_it_is(tmp_path):
    """3600 s of empty motorway is still empty. This is the real case:
    `Highway sounds...` is the longest clip surveyed and the emptiest."""
    rows = run(tmp_path, [
        {"camera": "empty", "seconds": 3601.8, "detections": 426},
    ])
    assert rows[0]["dense_enough"] == "False"
    assert rows[0]["clears_gate"] == "False"
    assert float(rows[0]["detections_per_frame"]) == 7.1


def test_a_dense_camera_clears_it_on_a_third_of_the_duration(tmp_path):
    """`South Extension` is 264 s and 66.6 detections/frame — the clip triage
    rejects on length and the corpus most wants."""
    rows = run(tmp_path, [
        {"camera": "dense", "seconds": 264.0, "detections": 3998},
    ])
    assert rows[0]["dense_enough"] == "True"
    assert rows[0]["clears_gate"] == "True"


def test_the_boundary_is_inclusive_at_the_prd_threshold(tmp_path):
    """15.0 detections/frame is PRD §14.1's MEDIUM→HIGH boundary and passes;
    a single detection less does not."""
    at = run(tmp_path, [{"camera": "at", "detections": 15 * 60}])
    below = run(tmp_path, [{"camera": "below", "detections": 15 * 60 - 1}])
    assert at[0]["dense_enough"] == "True"
    assert below[0]["dense_enough"] == "False"


def test_density_and_unassigned_are_separate_reasons(tmp_path):
    """A camera can be dense and still fail P17's gate. Merging the two would
    report `THIN` for a camera whose lanes are simply in the wrong place, and
    P25 says that one is fixable with a few clicks."""
    rows = run(tmp_path, [
        {"camera": "misplaced", "detections": 4000, "unassigned_rate": 0.94},
    ])
    assert rows[0]["dense_enough"] == "True"
    assert rows[0]["clears_gate"] == "False"


def test_the_rate_uses_the_frame_count_the_survey_actually_sampled(tmp_path):
    """`detections` is a total, not a rate. Reading it as a rate would admit
    every camera; dividing by the wrong count would admit or reject all of
    them together."""
    rows = run(tmp_path, [{"camera": "c", "detections": 600}],
               "--survey-frames", "120")
    assert float(rows[0]["detections_per_frame"]) == 5.0
    assert rows[0]["dense_enough"] == "False"


def test_thin_cameras_are_excluded_from_the_yield_totals(tmp_path):
    """The point of the gate is the headline number. A thin camera that still
    counted toward independent segments would overstate the corpus."""
    rows = run(tmp_path, [
        {"camera": "thin", "seconds": 3600.0, "detections": 60},
        {"camera": "dense", "seconds": 3600.0, "detections": 3600},
    ])
    by_camera = {r["camera"]: r for r in rows}
    assert by_camera["thin"]["clears_gate"] == "False"
    assert by_camera["dense"]["clears_gate"] == "True"
    # Both are long enough to yield segments; only one should be counted.
    assert int(by_camera["thin"]["independent_step2"]) > 0
