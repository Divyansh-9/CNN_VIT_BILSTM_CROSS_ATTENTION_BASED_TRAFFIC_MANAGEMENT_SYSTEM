"""The Phase-I Progress Report's references, and the guards around them.

The guideline behind this report asks for 25-30 papers in a comparative table
and warns against unreliable sources. This project's own
`docs/00-planning/BIBLIOGRAPHY.md` recorded that most of its entries were, at
one point, "named from general knowledge, not retrieved", and set the rule that
nothing in that state enters a reference list. A thirty-row table is where that
rule breaks first, so the reference list is generated from
`data/references.json` — filled by `scripts/verify_references.py` from OpenAlex
and arXiv, and never from memory.

These tests pin the arithmetic that decides whether a fetched record *is* the
work that was asked for, the invariants of the generated list, and the two
rendering guards that were added after a rendered slide showed what the source
could not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("pptx", reason="the deck builders need python-pptx")

from scripts import phase1_progress_content as P  # noqa: E402
from scripts import verify_references as V  # noqa: E402


# --------------------------------------------------------------------------
#  matching a fetched record against what was asked for
# --------------------------------------------------------------------------

def test_an_exact_title_matches():
    assert V.title_matches("Attention Is All You Need",
                           "Attention Is All You Need")


def test_a_different_paper_on_the_same_topic_is_rejected():
    """The measured failure. The expected DCRNN title shares six of its nine
    significant words with a different 2018 traffic-forecasting paper, and an
    earlier threshold accepted it — so the reference list named Cui et al. as
    the authors of Li et al.'s work."""
    expected = ("Diffusion Convolutional Recurrent Neural Network: "
                "Data-Driven Traffic Forecasting")
    other = ("Traffic Graph Convolutional Recurrent Neural Network: A Deep "
             "Learning Framework for Network-Scale Traffic Learning and "
             "Forecasting")
    assert not V.title_matches(expected, other)


def test_a_record_stored_under_only_its_short_name_matches():
    """OpenAlex holds some conference papers under just their name."""
    assert V.title_matches(
        "PressLight: Learning Max Pressure Control to Coordinate Traffic "
        "Signals in Arterial Network", "PressLight")


def test_a_short_name_that_is_not_in_the_expectation_is_rejected():
    assert not V.title_matches("CoLight: Learning Network-level Cooperation "
                               "for Traffic Signal Control", "FRAP")


def test_the_identifying_first_word_must_appear():
    """"Conformer" carries the identity; the rest of the title is generic."""
    assert not V.title_matches(
        "Conformer: Local Features Coupling Global Representations for "
        "Visual Recognition",
        "Local Features Coupling Global Representations for Recognition")


def test_pick_prefers_a_published_venue_over_the_preprint():
    work = {"title": "CrossViT: Cross-Attention Multi-Scale Vision "
                     "Transformer for Image Classification", "year": 2021}
    preprint = {"display_name": work["title"], "publication_year": 2021,
                "primary_location": {"source": {"display_name": "arXiv",
                                                "type": "repository"}}}
    published = {"display_name": work["title"], "publication_year": 2021,
                 "primary_location": {"source": {
                     "display_name": "IEEE/CVF International Conference on "
                                     "Computer Vision (ICCV)",
                     "type": "conference"}}}
    chosen, why = V.pick([preprint, published], work)
    assert why == ""
    assert chosen is published


def test_pick_prefers_the_expected_year_over_one_inside_the_slack():
    """OpenAlex holds a duplicate of "Attention Is All You Need" dated 2025."""
    work = {"title": "Attention Is All You Need", "year": 2017}
    near = {"display_name": work["title"], "publication_year": 2018,
            "primary_location": None}
    exact = {"display_name": work["title"], "publication_year": 2017,
             "primary_location": None}
    chosen, _why = V.pick([near, exact], work)
    assert chosen is exact


def test_pick_reports_what_it_found_when_nothing_qualifies():
    work = {"title": "Diffusion Convolutional Recurrent Neural Network: "
                     "Data-Driven Traffic Forecasting", "year": 2018}
    chosen, why = V.pick([{"display_name": "Something else entirely",
                           "publication_year": 2018,
                           "primary_location": None}], work)
    assert chosen is None
    assert "Something else entirely" in why


def test_every_declared_work_is_recorded():
    """`--check` would catch this against the network; this catches it without
    one, which is what lets it run in CI."""
    declared = {work["key"] for work in V.WORKS}
    recorded = set(P.WORKS)
    assert declared == recorded


# --------------------------------------------------------------------------
#  the generated reference list
# --------------------------------------------------------------------------

def test_the_table_holds_the_number_of_papers_the_guideline_requires():
    assert P.TABLE_MIN <= len(P.SURVEY_TABLE) <= P.TABLE_MAX


def test_every_table_row_resolves_to_a_verified_record():
    for key, *_ in P.SURVEY_TABLE:
        assert key in P.WORKS, key


def test_every_reference_is_cited_and_every_citation_resolves():
    order = set(key for key in P._reference_order())
    cited = P.cited_keys()
    assert cited - order == set(), f"cited but not in the list: {cited - order}"
    assert order - cited == set(), f"listed but never cited: {order - cited}"


def test_citation_numbers_are_stable_across_calls():
    """The table's row order and the reference numbering are generated from the
    same order, so an unstable order would silently decouple them."""
    assert P.cite("peng2021") == P.cite("peng2021")
    assert P.reference_list() == P.reference_list()


def test_an_unknown_citation_key_raises():
    with pytest.raises(KeyError, match="is in no reference list"):
        P.cite("nosuchwork2031")


def test_render_substitutes_every_placeholder():
    rendered = P.render("As shown by {peng2021} and {lu2019}.")
    assert "{" not in rendered
    assert P.cite("peng2021") in rendered


def test_no_prose_block_still_holds_an_unrendered_placeholder():
    """Every `{key}` must be reachable by `cited_keys()`, which means every
    prose block is listed in `_NARRATIVE_BLOCKS`. A block added and not listed
    would print `{key}` into a submitted document."""
    for block in P._NARRATIVE_BLOCKS():
        assert "{" not in P.render(block)


def test_author_initials_handle_both_name_orders():
    """OpenAlex returns "Hanxiao Liu" for one record and "Dai, Zihang" for the
    next. Guessing wrong puts a given name where a surname belongs."""
    assert V and P._initialise("Hanxiao Liu") == "H. Liu"
    assert P._initialise("Dai, Zihang") == "Z. Dai"
    assert P._initialise("Jean-Baptiste Alayrac") == "J. Alayrac"


def test_ieee_entries_abbreviate_past_three_authors():
    entry = P.WORKS["peng2021"].ieee
    assert "et al." in entry
    assert entry.endswith(".")


def test_a_duplicated_venue_is_collapsed_and_a_slash_venue_is_not():
    """OpenAlex writes some venues twice either side of a dash. A first version
    of the collapse also split on "/" and turned "IEEE/CVF International
    Conference on Computer Vision (ICCV)" into "IEEE"."""
    assert P.WORKS["he2016"].venue_clean.count("Pattern Recognition") == 1
    assert P.WORKS["chen2021"].venue_clean.startswith("IEEE/CVF")


def test_the_slide_sampler_cannot_name_a_paper_the_table_does_not():
    table = {key for key, *_ in P.SURVEY_TABLE}
    for key, *_ in P.SURVEY_TABLE_SLIDE:
        assert key in table, key


def test_every_theme_has_a_short_label():
    for work in P.WORKS.values():
        assert work.theme in P.THEME_LABELS, work.theme


# --------------------------------------------------------------------------
#  rendering guards
# --------------------------------------------------------------------------

def test_content_refuses_a_headline_given_as_a_string():
    """A bare string is subscriptable, so `headline[0]` and `headline[1]` take
    its first two characters: "Four settled bodies of work" rendered as "Fo"
    on every slide of the first build of this deck."""
    from scripts.build_review_pptx import Deck

    with pytest.raises(TypeError, match="must be a sequence"):
        Deck().content(1, "SECTION", "Four settled bodies of work")


def test_content_accepts_one_and_two_part_headlines():
    from scripts.build_review_pptx import Deck

    deck = Deck()
    deck.content(1, "SECTION", ("One part only",))
    deck.content(2, "SECTION", ("Plain ", "accented"))
    assert len(deck.slides) == 2


def test_an_over_long_table_cell_is_refused_not_truncated():
    """`Deck.table` draws each cell into a fixed box, so an over-long cell
    overruns the rule beneath it. Shortening it with an ellipsis — which an
    earlier version did — trades a collision for text that reads as a
    rendering fault, so the builder raises and the fix is a shorter string."""
    from pptx.util import Inches

    from scripts import build_phase1_progress_pptx as deck_builder

    with pytest.raises(ValueError, match="fit on one line"):
        deck_builder.cell("x" * 400, Inches(2.0))

    assert deck_builder.cell("short", Inches(2.0)) == "short"


def test_the_deck_and_the_report_build(tmp_path):
    """Written to `tmp_path`: the committed artefacts are produced by
    `scripts/build_synopsis.py`, and a test that overwrote them would make a
    passing suite a source of deliverables."""
    from scripts import build_phase1_progress_docx as report_builder
    from scripts import build_phase1_progress_pptx as deck_builder

    report = report_builder.build(tmp_path / "report.docx")
    deck = deck_builder.build(tmp_path / "deck.pptx")
    assert report.is_file() and report.stat().st_size > 0
    assert deck.is_file() and deck.stat().st_size > 0
