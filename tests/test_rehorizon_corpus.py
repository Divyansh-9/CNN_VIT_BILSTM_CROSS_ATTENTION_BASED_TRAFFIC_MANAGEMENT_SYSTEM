"""Re-deriving a corpus at a new horizon changes the horizon and nothing else."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.rehorizon_corpus import rehorizon  # noqa: E402

LANES = ["lane_0", "lane_1"]


def source(tmp: Path, n: int = 3600) -> Path:
    root = tmp / "src"
    root.mkdir()
    with (root / "counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["clip_id", "sample", "t_s", "count_lane_0", "count_lane_1"])
        for k in range(n):
            writer.writerow(["cam", k, 2 * k, k % 13, (k // 7) % 11])
    (root / "manifest.json").write_text(json.dumps({
        "lanes": LANES, "T": 60, "step_s": 2, "horizon_s": 60, "stride_s": 30,
        "split_mode": "temporal", "low_max": 4, "med_max": 15,
        "thresholds_by_clip": {"cam": {"low_max": 2, "med_max": 8}}}))
    return root


def test_the_label_sits_exactly_one_horizon_after_the_window(tmp_path):
    rows, _ = rehorizon(source(tmp_path), 180)
    for r in rows:
        assert r["label_index"] == r["start_index"] + 59 + 180 // 2


def test_no_input_or_target_crosses_a_split_boundary(tmp_path):
    rows, _ = rehorizon(source(tmp_path), 180)
    span = {}
    for r in rows:
        span.setdefault(r["split"], []).append((r["start_index"], r["label_index"]))
    order = ["train", "val", "test"]
    for a, b in zip(order, order[1:]):
        assert max(t for _, t in span[a]) < min(s for s, _ in span[b])


def test_thresholds_are_frozen_from_the_source_not_recalibrated(tmp_path):
    _, manifest = rehorizon(source(tmp_path), 180)
    assert manifest["thresholds_by_clip"]["cam"] == {"low_max": 2, "med_max": 8}
    assert manifest["horizon_s"] == 180


def test_a_horizon_the_recording_cannot_split_is_refused(tmp_path):
    """Two hours cannot give 300 s windows three disjoint splits; the split
    refuses rather than return an empty validation set."""
    with pytest.raises(ValueError, match="empty"):
        rehorizon(source(tmp_path), 300)


def test_a_clip_mode_corpus_is_refused(tmp_path):
    root = source(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["split_mode"] = "clip"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="temporal"):
        rehorizon(root, 180)
