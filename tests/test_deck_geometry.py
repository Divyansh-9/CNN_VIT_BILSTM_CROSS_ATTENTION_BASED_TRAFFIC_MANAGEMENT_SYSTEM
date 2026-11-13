"""Panel geometry in the generated decks.

`Deck.panel` draws its box at the height it is handed and lays the rows out
from the top regardless of that height, so a height estimated by eye fails in
one direction only: the last row is clipped by the bottom border and the
footnote is drawn *outside* the box, over whatever comes next on the slide.

Two panels shipped that way — slides 3 and 13 of the Phase I deck — because
`panel_height` takes its `footnote` argument optionally, so a call that passed
the footnote to `panel` and not to `panel_height` reserved no room for it and
raised nothing. The defect was visible only in a rendered slide.

These tests pin the guard that turns that into a build failure, and then build
both synopsis decks, which is what makes every panel in them checked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("pptx", reason="the deck builders need python-pptx")

from pptx.util import Inches  # noqa: E402

from scripts.build_review_pptx import Deck, DEEP  # noqa: E402
from scripts.build_synopsis_pptx import panel_height  # noqa: E402

WIDTH = Inches(5.2)

ITEMS = [
    ("Camera-only", "no loops, no radar, no roadside sensors"),
    ("Fixed viewpoint", "per-lane regions stay valid across a window"),
    ("Sixty seconds ahead", "long enough to change a phase, short enough to hold"),
]

FOOTNOTE = ("Camera-only is a harder problem than sensor-fusion. It is chosen "
            "because it is the one that can actually be deployed on the "
            "junctions this targets.")


def blank() -> tuple[Deck, object]:
    deck = Deck()
    return deck, deck._blank(DEEP)


def test_panel_accepts_the_height_panel_height_computes():
    deck, slide = blank()
    height = panel_height(ITEMS, WIDTH, FOOTNOTE)
    deck.panel(slide, Inches(1), Inches(1), WIDTH, height,
               "Why this framing", ITEMS, footnote=FOOTNOTE)


def test_panel_refuses_a_footnote_whose_height_was_never_reserved():
    """The exact defect: sized without the footnote, drawn with it."""
    deck, slide = blank()
    height = panel_height(ITEMS, WIDTH)          # the missing third argument
    with pytest.raises(ValueError, match="too short for its content"):
        deck.panel(slide, Inches(1), Inches(1), WIDTH, height,
                   "Why this framing", ITEMS, footnote=FOOTNOTE)


def test_panel_refuses_a_box_too_short_for_its_rows():
    """The same failure without a footnote — rows clipped by the bottom border."""
    deck, slide = blank()
    with pytest.raises(ValueError, match="too short for its content"):
        deck.panel(slide, Inches(1), Inches(1), WIDTH, Inches(1.0),
                   "Why this framing", ITEMS)


def test_the_refusal_names_the_shortfall_and_the_fix():
    deck, slide = blank()
    with pytest.raises(ValueError) as error:
        deck.panel(slide, Inches(1), Inches(1), WIDTH,
                   panel_height(ITEMS, WIDTH), "Why this framing", ITEMS,
                   footnote=FOOTNOTE)
    message = str(error.value)
    assert "Why this framing" in message          # which panel
    assert "footnote" in message                  # what overflowed
    assert "panel_height(items, width, footnote)" in message   # how to fix it


def test_panel_height_refuses_a_detail_row_that_would_wrap():
    """No height fixes a wrapping detail row: `panel` advances a fixed 0.50 in
    per row, so the second line lands on the row below however tall the box
    is. Only shortening the string does."""
    items = [("Lead", "x" * 400)]
    with pytest.raises(ValueError, match="panel detail wraps"):
        panel_height(items, WIDTH)


@pytest.mark.parametrize("module_name", [
    "scripts.build_synopsis_phase1_pptx",
    "scripts.build_synopsis_pptx",
])
def test_the_synopsis_decks_build(tmp_path, module_name):
    """Every panel in both decks, checked by the guard above.

    Written to `tmp_path` rather than `docs/demo/`: the committed artefacts are
    produced by `scripts/build_synopsis.py`, and a test that overwrote them
    would make a passing suite a source of deliverables.
    """
    import importlib

    module = importlib.import_module(module_name)
    out = tmp_path / f"{module_name.rsplit('.', 1)[1]}.pptx"
    module.build(out)
    assert out.is_file() and out.stat().st_size > 0
