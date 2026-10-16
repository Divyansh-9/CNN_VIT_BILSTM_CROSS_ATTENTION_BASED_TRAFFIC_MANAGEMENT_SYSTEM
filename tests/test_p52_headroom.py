"""P114's headroom numbers rest on `pairs`: the realised class 60-75 s on, never later."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.p52_headroom import pairs  # noqa: E402


def row(step, n):
    return {"step": step, "phase": 0, "counts": {a: n for a in "NSEW"},
            "queues": {a: 0 for a in "NSEW"}}


def test_pairs_with_the_first_decision_at_least_60_s_on():
    got = pairs([row(0, 2), row(30, 9), row(64, 20), row(100, 2)], low_max=4, med_max=15)
    first = [p for p in got if p["lead_s"] == 64]
    assert len(first) == 4                                    # one per approach
    assert {(p["now"], p["future"]) for p in first} == {(0, 2)}   # LOW now, HIGH realised


def test_a_gap_over_75_s_is_not_paired():
    assert pairs([row(0, 2), row(80, 20)], low_max=4, med_max=15) == []


def test_features_are_only_what_the_policy_already_sees():
    (p, *_) = pairs([row(0, 7), row(60, 7)], low_max=4, med_max=15)
    assert len(p["features"]) == 13        # 4 counts, 4 queues, phase, approach one-hot
    assert p["now"] == p["future"] == 1
