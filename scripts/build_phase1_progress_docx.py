"""Build the **Phase-I Progress Report – 1** as a real `.docx`.

The Department's *Guidelines for Major Project Phase-I Progress Report – 1*
prescribe five sections and no others, so this renderer has five section
functions and no more. It is a separate document from the Phase I synopsis
rather than a mode of it: the synopsis is an inception proposal with a
methodology chapter and a hardware chapter, and this report has neither — it
establishes the problem, surveys the literature in depth, tabulates 25-30
papers comparatively, names the research gap, and stops.

Formatting follows the shared *Major Project Synopsis Format* file, so the
front matter, fonts, margins and heading levels come from
`scripts/build_synopsis_docx.py` and are not re-specified here. One deliberate
departure: **Section 3's table is set on landscape pages.** Seven prose columns
do not read in the 6.02 in the portrait margins leave, and a comparative table
nobody can read does not satisfy a guideline that asks for critical analysis.
`docx_writer.SectionBreak` exists for this.

    python scripts/build_synopsis.py --which progress1 --pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts import build_synopsis_docx as D  # noqa: E402
from scripts import phase1_progress_content as P  # noqa: E402
from scripts.docx_writer import (Cell, Document, LINE_ONE_HALF,  # noqa: E402
                                 LINE_SINGLE, Para, Run, SectionBreak, Table,
                                 inches)

BODY = D.BODY
WIDTH = D.WIDTH

#: A4 long edge minus the same left and right margins the portrait pages use.
#: The guideline fixes the margins, not the orientation, so rotating the page
#: keeps every constrained measurement and buys 3.42 in of table width.
LANDSCAPE_WIDTH = 16838 - inches(1.25) - inches(1.0)

#: Column fractions for the seven prescribed columns, summing to 1. Set from
#: the content: the serial number needs almost nothing, the three analytical
#: columns the guideline cares most about get the most room, and the title
#: column gets enough that a title is readable rather than hyphenated to death.
TABLE_FRACTIONS = (0.035, 0.105, 0.195, 0.165, 0.145, 0.185, 0.17)


def widths_for(total: int, *fractions: float) -> list[int]:
    """Column widths in twips that sum to exactly `total`.

    The last column absorbs the rounding. A fixed-layout table whose columns
    sum to more than the page width is silently rescaled by Word, which undoes
    the point of choosing the fractions.
    """
    widths = [int(total * fraction) for fraction in fractions[:-1]]
    return widths + [total - sum(widths)]


def para(text: str, *, bold: bool = False, size: int = 18,
         align: str = "left") -> Para:
    """A table-cell paragraph at the table's own size.

    9 pt, which is smaller than the 12 pt the guideline fixes for *body* text.
    Thirty rows of seven analytical columns do not fit at 12 pt on any page
    size, and the guideline's own specimen table is a table rather than prose.
    """
    return Para([Run(text, size=size, bold=bold)], align=align,
                line=LINE_SINGLE, before=20, after=20)


# ==========================================================================
#  1 — Introduction
# ==========================================================================

def introduction(doc: Document) -> None:
    D.chapter(doc, "1", "Introduction")

    D.section(doc, "1.1", "Background of the Project")
    for text in P.BACKGROUND:
        D.body(doc, text)

    D.section(doc, "1.2", "Problem Statement")
    for text in P.PROBLEM_STATEMENT:
        D.body(doc, text)

    D.section(doc, "1.3", "Motivation")
    for text in P.MOTIVATION:
        D.body(doc, text)

    D.section(doc, "1.4", "Existing Scenario")
    for text in P.EXISTING_SCENARIO:
        D.body(doc, text)
    D.body(doc, "The limitation each approach carries is stated against it "
                "below, because a limitation recorded apart from the approach "
                "it belongs to is easy to agree with and impossible to act on.")
    for approach, limit in P.EXISTING_LIMITS:
        D.labelled(doc, approach + ".", limit)

    D.section(doc, "1.5", "Need for the Proposed Work")
    for text in P.NEED:
        D.body(doc, text)

    D.section(doc, "1.6", "Project Objectives")
    D.body(doc, "The project has six objectives. Each is stated as something "
                "that will be built or established, and each is measurable in "
                "the sense that its absence would be visible.")
    for index, (objective, detail) in enumerate(P.OBJECTIVES, start=1):
        D.labelled(doc, f"O{index}.  {objective}.", detail)

    D.section(doc, "1.7", "Scope of the Project")
    D.subsection(doc, "1.7.1", "Within scope")
    D.bullets(doc, P.IN_SCOPE)
    D.subsection(doc, "1.7.2", "Outside scope")
    D.body(doc, "Stated explicitly, because an unstated exclusion reads as an "
                "unmet expectation at evaluation time.")
    D.bullets(doc, P.OUT_OF_SCOPE)

    D.section(doc, "1.8", "Proposed Approach")
    D.body(doc, "The approach is sketched here in outline; the detailed design "
                "belongs to the design documents that follow this report. "
                "Seven stages, each producing an artefact the next one "
                "consumes.")
    for stage, detail in P.APPROACH_STAGES:
        D.labelled(doc, stage + ".", detail)
    for text in P.APPROACH_CLOSING:
        D.body(doc, text)

    D.section(doc, "1.9", "Expected Outcome")
    D.body(doc, "What will exist at the end of the project, and what will be "
                "known. No figure is quoted: this report is written before the "
                "measurements, and a target stated here as though it were a "
                "result would be exactly the overclaim the project's own "
                "reporting rules forbid.")
    for outcome, detail in P.EXPECTED_OUTCOME:
        D.labelled(doc, outcome + ".", detail)


# ==========================================================================
#  2 — Literature Survey
# ==========================================================================

def literature_survey(doc: Document) -> None:
    D.chapter(doc, "2", "Literature Survey")

    D.body(doc,
           "The survey is organised by what each strand of work settles rather "
           "than by publication date, because the question this report has to "
           "answer is not what exists but what is left. Fourteen subsections "
           "follow: the task-level prior art first, then the forecasting "
           "paradigm this project departs from, then density estimation and "
           "detection, then the representation and fusion mechanisms it "
           "assembles — every one of which is published and is cited as "
           "such — then the control literature, the data situation and what "
           "can be done about it, how transfer and imbalance are measured, "
           "and the signal-timing ground the baseline stands on.")
    D.body(doc,
           "Each citation in this report points at a record that was "
           "retrieved and checked rather than recalled. The reference list is "
           "generated from a committed file of verified bibliographic records, "
           "and a citation whose record is missing fails the build rather than "
           "printing a number that points at nothing.")

    for index, (_theme, title, paragraphs) in enumerate(P.SURVEY_SECTIONS,
                                                        start=1):
        D.section(doc, f"2.{index}", title)
        for text in paragraphs:
            D.body(doc, P.render(text))


# ==========================================================================
#  3 — Literature Survey Table
# ==========================================================================

def survey_table(doc: Document) -> None:
    D.chapter(doc, "3", "Literature Survey Table")

    D.body(doc,
           f"Table 3.1 compares the {len(P.SURVEY_TABLE)} works that bear "
           "most directly on this project. The author, year and title columns "
           "are generated from the verified bibliographic record, so a wrong "
           "citation cannot be introduced by editing the table. The "
           "methodology, setup, findings and limitation columns state each "
           "work's method and the assumption it makes — which is what "
           "determines whether its result is available at an "
           "un-instrumented Indian junction — rather than restating its "
           "reported numbers out of their experimental context.")
    D.body(doc,
           "Four further works cited in Section 2 are deliberately absent "
           "from the table: a mobile hybrid backbone and a second "
           "cross-modality encoder, each a near-duplicate of a row already "
           "present, and the simulator and reinforcement-learning library, "
           "which are tools rather than research results. All four remain in "
           "the references.")
    D.body(doc,
           "The table is set on landscape pages so that seven analytical "
           "columns are legible. The page margins are unchanged.")

    # The table's own section starts here. `SectionBreak` ends the section it
    # follows, so the portrait break goes *before* the table and the landscape
    # break *after* it.
    doc.add(SectionBreak(landscape=False))

    widths = widths_for(LANDSCAPE_WIDTH, *TABLE_FRACTIONS)
    header = ("S. No.", "Author(s) & Year", "Research Paper Title",
              "Methodology / Technique Used", "Dataset / Experimental Setup",
              "Key Findings", "Limitations / Research Gap")

    D.caption(doc, "Table 3.1  Comparative analysis of "
                   f"{len(P.SURVEY_TABLE)} works related to the project",
              above=True)

    grid = [[Cell([para(text, bold=True, align="center")], width, shaded=True)
             for text, width in zip(header, widths)]]

    for index, (key, method, setup, findings, limits) in enumerate(
            P.SURVEY_TABLE, start=1):
        work = P.WORKS[key]
        authors = f"{work.authors_ieee}, {work.year}"
        row = (str(index), authors, work.title, method, setup, findings, limits)
        aligns = ("center", "left", "left", "left", "left", "left", "left")
        grid.append([Cell([para(text, align=align)], width)
                     for text, width, align in zip(row, widths, aligns)])

    doc.add(Table(grid, widths, header_rows=1, cant_split=True))

    doc.add(SectionBreak(landscape=True))

    D.body(doc,
           "Read down the final column, the table says something the "
           "individual rows do not. The limitations are not scattered: they "
           "concentrate on four assumptions — that sensing infrastructure "
           "exists, that a scene-level or link-level output is enough, that "
           "the present can stand in for the near future, and that traffic is "
           "lane-disciplined. Section 4 takes those four and states the gap "
           "they leave.")


# ==========================================================================
#  4 — Research Gap
# ==========================================================================

def research_gap(doc: Document) -> None:
    D.chapter(doc, "4", "Research Gap")

    D.body(doc,
           "The gap below is derived from Section 2 and Section 3 rather than "
           "asserted. Every claim about what is missing carries the citation "
           "of the work that establishes what is present, because a research "
           "gap stated without that is indistinguishable from an incomplete "
           "survey.")

    heading, text = P.GAP_WHAT_IS_DONE
    D.section(doc, "4.1", heading)
    D.body(doc, P.render(text))

    D.section(doc, "4.2", "What limitations exist in existing approaches")
    for lead, detail in P.GAP_LIMITS:
        D.labelled(doc, lead + ".", P.render(detail))

    D.section(doc, "4.3", "What problems remain unresolved")
    for text in P.GAP_UNRESOLVED:
        D.body(doc, P.render(text))

    D.section(doc, "4.4", "What has not been adequately addressed")
    for lead, detail in P.GAP_UNADDRESSED:
        D.labelled(doc, lead + ".", P.render(detail))

    D.section(doc, "4.5",
              "How the proposed project addresses the identified gap")
    for lead, detail in P.GAP_HOW_WE_ADDRESS:
        D.labelled(doc, lead + ".", P.render(detail))

    D.section(doc, "4.6", "The gap, stated once")
    for text in P.GAP_CLOSING:
        D.body(doc, P.render(text))


# ==========================================================================
#  References
# ==========================================================================

def references(doc: Document) -> None:
    D.front_heading(doc, "REFERENCES")
    doc.add(Para([Run(
        "Every entry below was retrieved from a bibliographic index — "
        "OpenAlex, or arXiv for the two preprints OpenAlex does not hold at "
        "their year of publication — and its title, authors, year, venue and "
        "digital object identifier recorded in a committed file. None is "
        "reproduced from memory, and every entry is cited in the text above.",
        size=20, italic=True)], align="both", after=200))
    for index, text in P.reference_list():
        doc.add(Para([Run(f"[{index}]\t{text}", size=BODY)], align="both",
                     after=100, indent_left=560, indent_hanging=560,
                     tabs=(560,)))


# ==========================================================================
#  build
# ==========================================================================

def build(out_path: Path) -> Path:
    doc = Document(
        font="Times New Roman", size=BODY, line=LINE_ONE_HALF,
        margin_left=inches(1.25), margin_right=inches(1.0),
        margin_top=inches(0.75), margin_bottom=inches(0.75),
        title=f"{P.TITLE} — {P.SUBTITLE}", authors=P.AUTHORS,
    )

    D.title_page(doc, subtitle=P.SUBTITLE, month=P.SUBMISSION_MONTH,
                 kind="A Progress Report")
    D.certificate(doc, kind="Phase-I progress report")
    D.declaration(doc, kind="Phase-I progress report")
    D.table_of_contents(doc, P.TOC_ENTRIES)
    introduction(doc)
    literature_survey(doc)
    survey_table(doc)
    research_gap(doc)
    references(doc)

    doc.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=(
        Path(__file__).resolve().parent.parent / "docs" / "demo"
        / "MFSTNet-Phase1-Progress-Report-1.docx"))
    args = parser.parse_args(argv)
    path = build(args.out)
    print(f"  wrote {path}  ({path.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
