"""Re-deriving a corpus under new lane centres, without the detector (P28).

`counts.csv` is lane-dependent, so before this a hand-placed centre could only
be revised by running the detector over every clip again -- hours for a change
that is a few clicks. Lane placement is done by eye over a heatmap and will not
be right first time, so that cost decided whether it got revised at all.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.relane_corpus import main, read_detections


def write_detections(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["clip_id", "sample", "cls", "confidence",
                        "x1", "y1", "x2", "y2"],
        )
        writer.writeheader()
        writer.writerows(rows)


def detection(clip: str, sample: int, cx: float, cy: float) -> dict:
    return {"clip_id": clip, "sample": sample, "cls": "car", "confidence": 0.9,
            "x1": cx - 0.01, "y1": cy - 0.01, "x2": cx + 0.01, "y2": cy + 0.01}


def build_corpus_dir(tmp_path: Path, *, samples: int) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    rows = []
    for clip, hot in (("cam_a", 0.25), ("cam_b", 0.75)):
        for sample in range(samples):
            for k in range(8):
                rows.append(detection(clip, sample, hot, 0.4 + 0.02 * k))
    write_detections(corpus / "detections.csv", rows)
    (corpus / "manifest.json").write_text(json.dumps({
        "lanes": ["lane_0", "lane_1"], "T": 4, "step_s": 2,
        "horizon_s": 4, "stride_s": 2, "conf": 0.45, "imgsz": 992,
        "detector": "synthetic", "low_max": 3, "med_max": 6,
        "splits": {"cam_a": "train", "cam_b": "test"},
        "clips": ["cam_a", "cam_b"], "split_mode": "clip", "auto_labelled": True,
    }, indent=2), encoding="utf-8")
    return corpus


def write_lanes(directory: Path, a: tuple, b: tuple, *, radius: float = 0.3,
                clips=("cam_a", "cam_b")) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        (directory / f"{clip}.json").write_text(json.dumps({
            "clip": clip, "reviewed": True, "max_radius": radius,
            "lanes": [{"name": "lane_0", "centre": list(a)},
                      {"name": "lane_1", "centre": list(b)}],
        }), encoding="utf-8")
    return directory


def test_detections_round_trip_through_the_csv(tmp_path):
    path = tmp_path / "detections.csv"
    write_detections(path, [detection("cam_a", 0, 0.5, 0.5),
                            detection("cam_a", 0, 0.6, 0.5),
                            detection("cam_a", 1, 0.5, 0.5),
                            detection("cam_b", 0, 0.5, 0.5)])
    parsed = read_detections(path)

    assert set(parsed) == {"cam_a", "cam_b"}
    assert len(parsed["cam_a"][0]) == 2
    assert len(parsed["cam_a"][1]) == 1
    assert parsed["cam_a"][0][0].centroid == pytest.approx((0.5, 0.5))


def test_moving_a_centre_changes_the_counts(tmp_path):
    """The point of the script. If these agreed it would be doing nothing."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    good = write_lanes(tmp_path / "good", (0.25, 0.5), (0.75, 0.5))
    bad = write_lanes(tmp_path / "bad", (0.02, 0.02), (0.98, 0.98))

    main(["--corpus", str(corpus), "--lanes-dir", str(good),
          "--out", str(tmp_path / "out_good")])
    main(["--corpus", str(corpus), "--lanes-dir", str(bad),
          "--out", str(tmp_path / "out_bad")])

    def unassigned(where: Path) -> int:
        rows = list(csv.DictReader((where / "counts.csv").open(encoding="utf-8")))
        return sum(int(r["unassigned"]) for r in rows)

    assert unassigned(tmp_path / "out_good") == 0
    assert unassigned(tmp_path / "out_bad") > 0


def test_the_source_detections_are_never_modified(tmp_path):
    """Re-deriving must be repeatable from the same input, any number of times."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    before = (corpus / "detections.csv").read_bytes()
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5))

    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out1")])
    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out2")])

    assert (corpus / "detections.csv").read_bytes() == before
    assert ((tmp_path / "out1" / "counts.csv").read_text(encoding="utf-8")
            == (tmp_path / "out2" / "counts.csv").read_text(encoding="utf-8"))


def test_splits_are_carried_over_not_recomputed(tmp_path):
    """A lane change must be the ONLY difference between two corpora — a clip
    moving between train and test would make them incomparable."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5))
    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out")])

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["splits"] == {"cam_a": "train", "cam_b": "test"}
    rows = list(csv.DictReader((tmp_path / "out" / "sequences.csv").open(encoding="utf-8")))
    assert {r["clip_id"]: r["split"] for r in rows} == {"cam_a": "train", "cam_b": "test"}


def test_per_camera_geometry_reaches_the_manifest(tmp_path):
    """P26 — training reads this to build one mask set per camera."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    lanes = tmp_path / "lanes"
    lanes.mkdir()
    for clip, (a, b) in (("cam_a", ((0.2, 0.5), (0.8, 0.5))),
                         ("cam_b", ((0.3, 0.2), (0.7, 0.9)))):
        (lanes / f"{clip}.json").write_text(json.dumps({
            "clip": clip, "reviewed": True, "max_radius": 0.4,
            "lanes": [{"name": "lane_0", "centre": list(a)},
                      {"name": "lane_1", "centre": list(b)}],
        }), encoding="utf-8")

    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out")])

    geometry = json.loads(
        (tmp_path / "out" / "manifest.json").read_text(encoding="utf-8")
    )["lane_centres_by_clip"]
    assert set(geometry) == {"cam_a", "cam_b"}
    assert geometry["cam_a"]["lanes"] != geometry["cam_b"]["lanes"]


def test_a_corpus_without_detections_is_refused(tmp_path):
    """Corpora built before P28 stored only per-lane counts."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manifest.json").write_text("{}", encoding="utf-8")
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5))

    with pytest.raises(SystemExit, match="detections.csv not found"):
        main(["--corpus", str(corpus), "--lanes-dir", str(lanes)])


def test_a_clip_without_reviewed_lanes_is_refused(tmp_path):
    """P17 — counting one camera through another's lanes counts the wrong
    region, and every label built on it is arbitrary."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5),
                        clips=("cam_a",))          # cam_b left out

    with pytest.raises(SystemExit, match="no reviewed lanes"):
        main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
              "--out", str(tmp_path / "out")])


def test_thresholds_can_be_changed_in_the_same_pass(tmp_path):
    """Relabelling and relaning both derive from the same source, so there is
    no reason to force two passes."""
    corpus = build_corpus_dir(tmp_path, samples=12)
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5))
    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--low-max", "1", "--med-max", "2", "--out", str(tmp_path / "out")])

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert (manifest["low_max"], manifest["med_max"]) == (1, 2)

    # Each camera's traffic sits over exactly one centre, so per sequence one
    # lane sees 8 and the other 0. Under low_max=1/med_max=2 that is HIGH and
    # LOW, and MEDIUM cannot occur — which is what pins the thresholds as
    # having been applied.
    rows = list(csv.DictReader((tmp_path / "out" / "sequences.csv").open(encoding="utf-8")))
    labels = [{r["label_lane_0"], r["label_lane_1"]} for r in rows]
    assert all(pair == {"HIGH", "LOW"} for pair in labels)


def test_frames_with_no_detections_are_not_dropped(tmp_path):
    """A frame the detector found nothing in writes no rows, so iterating the
    CSV's keys skips it. That frame is not missing data -- it is zero traffic,
    a LOW label -- and compacting the series is worse than losing it: window
    position i stops meaning sample i, so every label is read from the wrong
    moment. Measured on the real corpus, 119 of 1046 samples on one camera.
    """
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    rows = []
    for sample in range(10):
        if sample in (3, 4, 7):            # the detector saw nothing here
            continue
        for _ in range(6):
            rows.append(detection("cam_a", sample, 0.25, 0.5))
    write_detections(corpus / "detections.csv", rows)
    (corpus / "manifest.json").write_text(json.dumps({
        "lanes": ["lane_0", "lane_1"], "T": 3, "step_s": 2, "horizon_s": 2,
        "stride_s": 2, "conf": 0.45, "imgsz": 992, "detector": "synthetic",
        "low_max": 3, "med_max": 6, "splits": {"cam_a": "train"},
        "clips": ["cam_a"], "split_mode": "clip", "auto_labelled": True,
        "samples_per_clip": {"cam_a": 10},
    }, indent=2), encoding="utf-8")
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5),
                        clips=("cam_a",))

    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out")])

    counts = list(csv.DictReader((tmp_path / "out" / "counts.csv").open(encoding="utf-8")))
    assert len(counts) == 10
    assert [int(r["sample"]) for r in counts] == list(range(10))

    # The empty frames are present and count zero, and t_s still matches the
    # sample index -- which is what the window arithmetic depends on.
    empty = {int(r["sample"]): r for r in counts if int(r["sample"]) in (3, 4, 7)}
    assert len(empty) == 3
    for sample, row in empty.items():
        assert int(row["count_lane_0"]) == 0
        assert int(row["count_lane_1"]) == 0
        assert float(row["t_s"]) == sample * 2


def test_a_corpus_without_samples_per_clip_still_works(tmp_path):
    """Corpora built between P28 and this fix. Interior gaps are recoverable
    from the highest index; trailing ones are not, and it says so."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    rows = [detection("cam_a", s, 0.25, 0.5) for s in range(10) if s != 4]
    write_detections(corpus / "detections.csv", rows)
    (corpus / "manifest.json").write_text(json.dumps({
        "lanes": ["lane_0", "lane_1"], "T": 3, "step_s": 2, "horizon_s": 2,
        "stride_s": 2, "conf": 0.45, "imgsz": 992, "detector": "synthetic",
        "low_max": 3, "med_max": 6, "splits": {"cam_a": "train"},
        "clips": ["cam_a"], "split_mode": "clip", "auto_labelled": True,
    }, indent=2), encoding="utf-8")
    lanes = write_lanes(tmp_path / "lanes", (0.25, 0.5), (0.75, 0.5),
                        clips=("cam_a",))

    main(["--corpus", str(corpus), "--lanes-dir", str(lanes),
          "--out", str(tmp_path / "out")])

    counts = list(csv.DictReader((tmp_path / "out" / "counts.csv").open(encoding="utf-8")))
    assert [int(r["sample"]) for r in counts] == list(range(10))   # gap recovered


def test_reading_detections_does_not_grow_the_mapping(tmp_path):
    """`samples.get(index, [])` on a defaultdict inserts the missing key, so a
    lookup during the count loop would quietly extend what it is reading."""
    path = tmp_path / "detections.csv"
    write_detections(path, [detection("cam_a", 0, 0.5, 0.5)])
    parsed = read_detections(path)
    before = len(parsed["cam_a"])
    parsed["cam_a"].get(99, [])
    assert len(parsed["cam_a"]) == before
