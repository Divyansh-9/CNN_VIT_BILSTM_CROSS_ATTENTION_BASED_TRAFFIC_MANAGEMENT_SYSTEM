"""The corpus auditor has to be able to fail (P40).

An auditor that passes on good data proves nothing on its own — the question is
whether it catches a corpus that is wrong. So each check is exercised against a
corpus mutated to break exactly that invariant, and the audit must reject it.

The mutation that matters most is the first: `label shifted by one`. A15 puts
the label 60 s after the last observed frame, and an off-by-one there makes
every label in the corpus wrong while nothing else looks unusual — same row
count, same class balance, same loss curve.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.audit_corpus import main

T, STEP_S, HORIZON_S, STRIDE_S = 4, 2, 4, 2
LANES = ["lane_0", "lane_1"]
LABEL_OFFSET = (T - 1) + HORIZON_S // STEP_S


def build(tmp_path: Path, *, samples: int = 16) -> Path:
    """A small corpus that passes every check, as the fixture to mutate."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    counts = []
    for clip, base in (("cam_a", 1), ("cam_b", 9)):
        for sample in range(samples):
            counts.append({"clip_id": clip, "sample": sample,
                           "t_s": sample * STEP_S,
                           "count_lane_0": base, "count_lane_1": base + 1,
                           "unassigned": 0})
    write(corpus / "counts.csv", counts)

    sequences = []
    for clip, split in (("cam_a", "train"), ("cam_b", "test")):
        start = 0
        while start + LABEL_OFFSET < samples:
            entry = {"clip_id": clip, "split": split, "start_index": start,
                     "label_index": start + LABEL_OFFSET}
            for lane in LANES:
                base = 1 if clip == "cam_a" else 9
                count = base if lane == "lane_0" else base + 1
                entry["label_" + lane] = ("LOW" if count <= 3
                                          else "MEDIUM" if count <= 8 else "HIGH")
            sequences.append(entry)
            start += STRIDE_S // STEP_S
    write(corpus / "sequences.csv", sequences)

    (corpus / "manifest.json").write_text(json.dumps({
        "lanes": LANES, "T": T, "step_s": STEP_S, "horizon_s": HORIZON_S,
        "stride_s": STRIDE_S, "low_max": 3, "med_max": 8,
        "conf": 0.45, "imgsz": 992, "detector": "synthetic",
        "clips": ["cam_a", "cam_b"], "auto_labelled": True,
        "lane_centres_by_clip": {
            clip: {"lanes": [{"name": lane, "centre": [0.3, 0.5]}
                             for lane in LANES], "max_radius": 0.3}
            for clip in ("cam_a", "cam_b")},
    }, indent=2), encoding="utf-8")
    return corpus


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def manifest_of(corpus: Path) -> dict:
    return json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))


def put_manifest(corpus: Path, record: dict) -> None:
    (corpus / "manifest.json").write_text(json.dumps(record, indent=2),
                                          encoding="utf-8")


def registry_for(tmp_path, corpus, *, country="India", traffic="mixed"):
    """A camera registry declaring whatever the synthetic corpus contains.

    P58's check compares the test split against the claimed domain, so a
    corpus fixture has to say what its cameras are. Pointing the audit at a
    temp registry exercises the real path rather than disabling it.
    """
    import csv as _csv
    import json as _json

    with (corpus / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        cameras = sorted({row["clip_id"] for row in _csv.DictReader(handle)})
    path = tmp_path / "cameras.json"
    path.write_text(_json.dumps({
        "target_domain": {"country": [country], "traffic_type": [traffic]},
        "cameras": {c: {"country": country, "traffic_type": traffic,
                        "viewpoint": "elevated", "determined_by": "fixture"}
                    for c in cameras},
    }), encoding="utf-8")
    return path

def test_a_sound_corpus_passes(tmp_path, capsys):
    corpus = build(tmp_path)
    assert main(["--corpus", str(corpus),
                 "--cameras", str(registry_for(tmp_path, corpus))]) == 0
    assert "FAIL" not in capsys.readouterr().out


def test_a_corpus_whose_test_split_is_off_target_fails(tmp_path, capsys):
    """P58. The M6 Motorway passed every existing gate and made a project about
    unstructured Indian traffic 41% British."""
    corpus = build(tmp_path)
    cameras = registry_for(tmp_path, corpus, country="United Kingdom",
                           traffic="structured")
    import json as _json
    payload = _json.loads(cameras.read_text(encoding="utf-8"))
    payload["target_domain"] = {"country": ["India"], "traffic_type": ["mixed"]}
    cameras.write_text(_json.dumps(payload), encoding="utf-8")
    assert main(["--corpus", str(corpus), "--cameras", str(cameras)]) == 1
    assert "claimed domain" in capsys.readouterr().out


def test_an_absent_registry_warns_rather_than_passing(tmp_path, capsys):
    """A silent skip is a hole; a pass would be a lie."""
    corpus = build(tmp_path)
    assert main(["--corpus", str(corpus),
                 "--cameras", str(tmp_path / "nothing.json")]) == 0
    assert "composition unchecked" in capsys.readouterr().out


# ------------------------------------------------------------- mutations --

def shift_label(corpus):
    rows = read(corpus / "sequences.csv")
    rows[0]["label_index"] = str(int(rows[0]["label_index"]) + 1)
    write(corpus / "sequences.csv", rows)


def flip_label(corpus):
    rows = read(corpus / "sequences.csv")
    rows[0]["label_lane_0"] = "HIGH" if rows[0]["label_lane_0"] != "HIGH" else "LOW"
    write(corpus / "sequences.csv", rows)


def straddle_split(corpus):
    rows = read(corpus / "sequences.csv")
    for row in rows:
        if row["clip_id"] == rows[0]["clip_id"] and row is not rows[0]:
            row["split"] = "val"
            break
    write(corpus / "sequences.csv", rows)


def label_past_the_end(corpus):
    rows = read(corpus / "sequences.csv")
    rows[0]["label_index"] = "999999"
    write(corpus / "sequences.csv", rows)


def drop_geometry(corpus):
    record = manifest_of(corpus)
    record["lane_centres_by_clip"].pop("cam_b")
    put_manifest(corpus, record)


def ragged_lane_count(corpus):
    record = manifest_of(corpus)
    record["lane_centres_by_clip"]["cam_a"]["lanes"].pop()
    put_manifest(corpus, record)


def delete_a_count_row(corpus):
    rows = read(corpus / "counts.csv")
    write(corpus / "counts.csv", [r for i, r in enumerate(rows) if i != 3])


@pytest.mark.parametrize("mutate,expected", [
    pytest.param(shift_label, "label_index ==", id="label-shifted-by-one"),
    pytest.param(flip_label, "re-derives from counts", id="label-flipped"),
    pytest.param(straddle_split, "more than one split", id="clip-in-two-splits"),
    pytest.param(label_past_the_end, "label_index ==", id="label-past-the-end"),
    pytest.param(drop_geometry, "own lane geometry", id="geometry-missing"),
    pytest.param(ragged_lane_count, "same lane count", id="ragged-lane-count"),
    pytest.param(delete_a_count_row, "contiguous", id="count-row-deleted"),
])
def test_the_audit_rejects_a_broken_corpus(tmp_path, capsys, mutate, expected):
    corpus = build(tmp_path)
    mutate(corpus)

    assert main(["--corpus", str(corpus)]) == 1
    output = capsys.readouterr().out
    failing = [line for line in output.splitlines() if "FAIL" in line]
    assert failing, output
    assert any(expected in line for line in failing), failing


def test_an_off_by_one_label_is_otherwise_invisible(tmp_path):
    """Why the first mutation is the one that matters. A shifted label leaves
    the row count, the split sizes and the class balance untouched — there is
    nothing else to notice it by."""
    import collections

    corpus = build(tmp_path)
    before = read(corpus / "sequences.csv")
    shift_label(corpus)
    after = read(corpus / "sequences.csv")

    assert len(before) == len(after)
    assert (collections.Counter(r["split"] for r in before)
            == collections.Counter(r["split"] for r in after))
    assert (collections.Counter(r["label_lane_0"] for r in before)
            == collections.Counter(r["label_lane_0"] for r in after))


# -- P46: the corpus-level gates run here, not only on synthetic data ------
#
# `validate_corpus` holds the gates that decide whether a corpus can carry a
# result — split balance, effective sample size, transition rate. Its only
# caller was `demo_pipeline.py`, so a real corpus never met them and the one
# that trains the model got the weaker check. These pin the wiring.


def test_the_audit_reports_split_balance(tmp_path, capsys):
    main(["--corpus", str(build(tmp_path))])
    out = capsys.readouterr().out
    assert "split_balance" in out


def test_the_audit_reports_effective_sample_size(tmp_path, capsys):
    """The fixture's test split is one clip. Effective n is 1, not the
    sequence count, and the auditor has to say so — a confidence interval
    over one clip is the failure this gate exists to name."""
    main(["--corpus", str(build(tmp_path))])
    out = capsys.readouterr().out
    assert "effective_sample_size" in out
    assert "1 clip(s)" in out


def test_the_audit_reports_the_transition_rate(tmp_path, capsys):
    """PRD A17: if congestion never changes class over the horizon, a
    last-value baseline sits at the ceiling and no model can be ranked."""
    main(["--corpus", str(build(tmp_path))])
    out = capsys.readouterr().out
    assert "transition_rate" in out


def test_the_gates_are_advisory_and_do_not_fail_a_sound_corpus(tmp_path):
    """A skewed split does not make results wrong, it makes them
    unrepresentative. Blocking on it would stop work that should continue
    with a caveat attached."""
    corpus = build(tmp_path)
    assert main(["--corpus", str(corpus),
                 "--cameras", str(registry_for(tmp_path, corpus))]) == 0
