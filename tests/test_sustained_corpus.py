"""The sustained-level target is exactly what P94 pre-registered."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sustained_corpus import build  # noqa: E402


def source(tmp: Path, n: int = 3600) -> tuple[Path, list[int]]:
    root = tmp / "src"
    root.mkdir()
    series = [(k * 7) % 13 for k in range(n)]
    with (root / "counts.csv").open("w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["clip_id", "sample", "t_s", "count_lane_0"])
        for k, v in enumerate(series):
            w.writerow(["cam", k, 2 * k, v])
    (root / "manifest.json").write_text(json.dumps({
        "lanes": ["lane_0"], "T": 60, "step_s": 2, "stride_s": 30,
        "split_mode": "temporal", "low_max": 4, "med_max": 15,
        "thresholds_by_clip": {"cam": {"low_max": 2, "med_max": 8}}}))
    return root, series


def test_the_label_is_the_class_of_the_raw_future_mean(tmp_path):
    root, c = source(tmp_path)
    rows, _ = build(root, 30)
    for r in rows:
        e = r["start_index"] + 59
        mean = sum(c[e + 1:e + 31]) / 30
        expected = "LOW" if mean <= 2 else ("MEDIUM" if mean <= 8 else "HIGH")
        assert r["label_lane_0"] == expected
        assert r["label_index"] == e + 30


def test_the_whole_future_window_stays_inside_its_split(tmp_path):
    root, _ = source(tmp_path)
    for future in (30, 60):
        rows, _ = build(root, future)
        span = {}
        for r in rows:
            span.setdefault(r["split"], []).append((r["start_index"], r["label_index"]))
        for a, b in (("train", "val"), ("val", "test")):
            assert max(t for _, t in span[a]) < min(s for s, _ in span[b])


def test_thresholds_are_frozen_from_the_source(tmp_path):
    root, _ = source(tmp_path)
    _, manifest = build(root, 60)
    assert manifest["thresholds_by_clip"]["cam"] == {"low_max": 2, "med_max": 8}
    assert manifest["future_samples"] == 60
