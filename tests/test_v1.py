"""V1: the sample is reproducible and disjoint; the labelling page is blind."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CORPUS = Path("data/corpus_p105")
needs_corpus = pytest.mark.skipif(not CORPUS.exists(), reason="needs the local P105 corpus")


@needs_corpus
def test_the_draw_is_reproducible_disjoint_and_non_overlapping():
    from scripts.v1_sample import GRID, candidates, draw

    a, b = draw(candidates()), draw(candidates())
    assert a == b
    pilot = {m["id"] for m in a["pilot"]}
    reserve = {m["id"] for items in a["reserve"].values() for m in items}
    assert len(pilot) == 40 and not pilot & reserve
    by_lane: dict[tuple, list[int]] = {}
    for m in [*a["pilot"], *(m for items in a["reserve"].values() for m in items)]:
        by_lane.setdefault((m["clip"], m["lane"]), []).append(m["t"])
    for ts in by_lane.values():
        ts.sort()
        assert all(later - earlier >= GRID for earlier, later in zip(ts, ts[1:]))


def test_the_labelled_frames_are_the_fidelity_checks_k15_rule():
    from scripts.v1_sample import HORIZON, LABEL_OFFSETS

    t = 100
    window = list(range(t + 1, t + 1 + HORIZON))          # samples t+1 .. t+30
    assert [t + k for k in LABEL_OFFSETS] == window[1::2] and len(LABEL_OFFSETS) == 15


def _moments():
    return [{"id": f"clipA|lane_{k}|{100 + 90 * k}", "clip": "clipA", "lane": f"lane_{k % 2}",
             "t": 100 + 90 * k, "labelled_samples": [100 + 90 * k + o for o in range(2, 31, 2)]}
            for k in range(3)]


def test_items_cover_every_frame_in_a_seeded_shuffle():
    from scripts.v1_label_page import items_for

    items = items_for(_moments())
    assert len(items) == 45 and len({i["id"] for i in items}) == 45
    assert items == items_for(_moments())
    assert [i["sample"] for i in items] != sorted(i["sample"] for i in items)


def test_the_page_reveals_no_count_time_clip_or_moment():
    pytest.importorskip("cv2")
    import numpy as np

    from scripts.v1_label_page import build_payload, items_for, render

    centres = [{"name": "lane_0", "centre": [0.3, 0.5]}, {"name": "lane_1", "centre": [0.7, 0.5]}]
    payload = build_payload(items_for(_moments()),
                            lambda clip, s: (np.full((40, 60, 3), 120, np.uint8), centres))
    assert all(set(p) == {"id", "img"} for p in payload)
    page = render("pilot", payload, "instructions")
    for leak in ("clipA", "lane_0|", "|100", "count_lane", "t_s"):
        assert leak not in page


def test_the_main_set_refuses_before_the_v1_freeze(tmp_path, monkeypatch):
    from scripts import v1_label_page

    monkeypatch.chdir(tmp_path)
    (tmp_path / "experiments/results/v1").mkdir(parents=True)
    (tmp_path / "experiments/results/v1/v1_sample_manifest.json").write_text(
        json.dumps({"pilot": [], "reserve": {}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="pre-registration"):
        v1_label_page.main(["--set", "main", "--per-stratum", "5"])
