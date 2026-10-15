"""Check the generated Phase-I Progress Report – 1 against its own guideline.

A separate checker from `scripts/check_synopsis.py`, because it answers a
separate document. The *Guidelines for Major Project Phase-I Progress Report –
1* prescribe five sections rather than nine, require a comparative table of
**25 to 30 papers**, and say nothing about methodology or results — so the
synopsis checker's chapter-order rule would fail this report correctly and its
single-section rule would fail it wrongly, the table being set landscape.

Everything the two documents genuinely share — the page geometry, the fonts,
the heading sizes, the citation arithmetic, the identity fields — is imported
rather than re-implemented, so a change to the Department's formatting is made
in one place.

    python scripts/check_progress_report.py
    python scripts/check_progress_report.py docs/demo/<file>.docx

Exits 1 if any rule fails. Stdlib only.

The rules, and the guideline clause each comes from:

* Format §2  A4, margins left 1.25 in, right 1 in, top/bottom 0.75 in — on
             every section, including the landscape one
* Format §3  heading sizes by level
* §1         the nine named parts of the Introduction, in the guideline's order
* §2-§5      the five prescribed sections, in order, and no others
* §3         the comparative table has 25-30 paper rows and the seven
             prescribed column headings
* §5         every citation resolves to a reference entry, and every entry is
             cited in the text
* §5         no reference is reproduced from memory: every indexed work in the
             document is present in the verified record
* Project    the report quotes no measured result
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts import phase1_progress_content as P  # noqa: E402
from scripts.check_synopsis import (A4, COVER_FONT, MARGINS,  # noqa: E402
                                    Paragraph, Report, check_captions,
                                    check_defaults, check_fonts,
                                    check_headings, check_identity, load)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

DEFAULT_PATH = (Path(__file__).resolve().parent.parent / "docs" / "demo"
                / "MFSTNet-Phase1-Progress-Report-1.docx")

#: The five prescribed sections. The guideline numbers four and leaves
#: References unnumbered, which is how the document sets them.
REQUIRED_ORDER = ("Introduction", "Literature Survey",
                  "Literature Survey Table", "Research Gap", "REFERENCES")

#: §1's nine named parts, in the guideline's order. Checked as an ordered list
#: rather than a set: the guideline presents them as a sequence that moves from
#: context to outcome, and a report that answers them out of order answers a
#: different question.
INTRO_PARTS = (
    "Background of the Project", "Problem Statement", "Motivation",
    "Existing Scenario", "Need for the Proposed Work", "Project Objectives",
    "Scope of the Project", "Proposed Approach", "Expected Outcome",
)

#: §3's recommended column headings, in its order.
TABLE_COLUMNS = (
    "S. No.", "Author(s) & Year", "Research Paper Title",
    "Methodology / Technique Used", "Dataset / Experimental Setup",
    "Key Findings", "Limitations / Research Gap",
)

#: A four-decimal number is how this project formats a measured result
#: (`synopsis_content.fmt` defaults to four places). Nothing legitimate in a
#: report written before any measurement needs that precision, so finding one
#: means a result has leaked in. Two- and three-decimal figures are left alone:
#: the passenger-car equivalents quoted from the literature are 0.24 and 0.78.
#:
#: The trailing exclusion is load-bearing. A DOI is `10.1177/0361198118777631`,
#: whose first seven characters are a number with four decimals followed by a
#: word boundary, so a rule written without it reports every reference in the
#: document as a leaked result.
RESULT_RE = re.compile(r"\b\d+\.\d{4}(?![\d/])")

#: A reference entry is not prose and is excluded from the prose rules: it
#: legitimately contains DOIs, page ranges and volume numbers.
ENTRY_RE = re.compile(r"^\[(\d+)\]")

#: A `{key}` that survived into the document means a prose block was added
#: without being passed through `render()`.
UNRENDERED_RE = re.compile(r"\{[a-z][a-z0-9]*\}")


def check_sections(document: ElementTree.Element, report: Report) -> None:
    """Page geometry on every section, not just the last one.

    The report has three: portrait, then landscape for the comparative table,
    then portrait again. The guideline fixes the margins and the paper, not the
    orientation, so each section must be A4 in one orientation or the other and
    must carry the prescribed margins — a landscape section that quietly
    changed a margin would be a real defect and is exactly what a rule written
    against only the final section would miss.
    """
    sections = document.findall(f".//{W}sectPr")
    report.check(len(sections) == 3, "§2 three sections: portrait, landscape "
                                     "table, portrait", f"found {len(sections)}")

    landscape = 0
    for index, section in enumerate(sections):
        size = section.find(W + "pgSz")
        if size is None:
            report.check(False, f"§2 section {index + 1} declares a page size")
            continue
        dimensions = (int(size.get(W + "w")), int(size.get(W + "h")))
        rotated = dimensions == (A4[1], A4[0])
        if rotated:
            landscape += 1
        report.check(dimensions == A4 or rotated,
                     f"§2 section {index + 1} is A4",
                     f"{dimensions[0]}x{dimensions[1]} twips")
        report.check(rotated == (size.get(W + "orient") == "landscape"),
                     f"§2 section {index + 1} orientation matches its page "
                     "size",
                     f"orient={size.get(W + 'orient')} size={dimensions}")

        margin = section.find(W + "pgMar")
        for edge, expected in MARGINS.items():
            actual = int(margin.get(W + edge)) if margin is not None else None
            report.check(actual == expected,
                         f"§2 section {index + 1} {edge} margin is "
                         f"{expected} twips", f"got {actual}")

    report.check(landscape == 1, "§2 exactly one landscape section",
                 f"found {landscape}")


def check_order(paragraphs: list[Paragraph], report: Report) -> None:
    headings = [p.text for p in paragraphs if p.size == 36 and p.bold]
    order = [h for h in headings if h in REQUIRED_ORDER]
    report.check(order == list(REQUIRED_ORDER),
                 "§2-§5 prescribed section order", " | ".join(order))

    # Nothing from the *synopsis* guideline may appear here. The two documents
    # are different submissions, and a methodology chapter in this one means
    # the wrong brief was answered.
    forbidden = {"PROPOSED METHODOLOGY", "HARDWARE AND SOFTWARE REQUIREMENTS",
                 "EXPECTED OUTCOMES", "CONCLUSION", "ABSTRACT"}
    present = sorted(forbidden & set(headings))
    report.check(not present,
                 "§1 no section outside the five the guideline prescribes",
                 ", ".join(present))


def check_intro_parts(paragraphs: list[Paragraph], report: Report) -> None:
    found = [re.sub(r"^1\.\d+  ", "", p.text) for p in paragraphs
             if re.match(r"^1\.\d+  \S", p.text) and p.bold]
    ordered = [name for name in found if name in INTRO_PARTS]
    report.check(ordered == list(INTRO_PARTS),
                 "§1 all nine named parts of the Introduction, in order",
                 " | ".join(ordered) or "none found")


def check_table(parts: dict[str, str], document: ElementTree.Element,
                report: Report) -> None:
    tables = document.findall(f".//{W}tbl")
    seven = [table for table in tables
             if len(table.findall(f"{W}tr")) > 10
             and len(table.find(f"{W}tr").findall(f"{W}tc")) == 7]
    if not report.check(len(seven) == 1,
                        "§3 one comparative table with seven columns",
                        f"found {len(seven)} candidates among "
                        f"{len(tables)} tables"):
        return

    table = seven[0]
    rows = table.findall(f"{W}tr")
    header = ["".join(node.text or "" for node in cell.iter(W + "t")).strip()
              for cell in rows[0].findall(f"{W}tc")]
    report.check(header == list(TABLE_COLUMNS),
                 "§3 the seven prescribed column headings, in order",
                 " | ".join(header))

    data_rows = len(rows) - 1
    report.check(P.TABLE_MIN <= data_rows <= P.TABLE_MAX,
                 f"§3 between {P.TABLE_MIN} and {P.TABLE_MAX} papers compared",
                 f"found {data_rows}")

    report.check(all(row.find(f"{W}trPr/{W}cantSplit") is not None
                     for row in rows),
                 "§3 no table row may break across a page",
                 "a split row orphans its tail with no serial number")

    # Every row must identify a work, and the serial numbers must run 1..n with
    # none repeated — a duplicated row is the kind of defect that survives
    # proofreading because each row reads correctly on its own.
    serials = []
    for row in rows[1:]:
        cells = row.findall(f"{W}tc")
        serials.append("".join(node.text or ""
                               for node in cells[0].iter(W + "t")).strip())
    report.check(serials == [str(n) for n in range(1, data_rows + 1)],
                 "§3 serial numbers run consecutively from 1",
                 ", ".join(serials[:8]) + " ...")


def check_references_are_verified(paragraphs: list[Paragraph],
                                  report: Report) -> None:
    """Every entry in the document's reference list is one this project checked.

    The guideline asks for authentic papers from reputed venues and warns
    against non-scholarly sources. This project's own bibliography records that
    most of its entries were, at one point, "named from general knowledge, not
    retrieved". The rule that resolves both is mechanical: the rendered list
    must equal the list generated from `data/references.json`, which
    `scripts/verify_references.py` fills from OpenAlex and arXiv and refuses to
    fill from memory.
    """
    listed = [p.text for p in paragraphs if ENTRY_RE.match(p.text)]
    expected = [f"[{number}] {text}" for number, text in P.reference_list()]
    report.check(len(listed) == len(expected),
                 f"§5 all {len(expected)} reference entries are listed",
                 f"found {len(listed)}")

    # Compare on the entry text with its number stripped and whitespace
    # normalised. `Paragraph.text` joins the `w:t` nodes and so drops the
    # `w:tab` that separates the number from the entry on the page — comparing
    # the raw strings would report all thirty-nine entries as differing, which
    # is what a first version of this rule did.
    def normalise(text: str) -> str:
        return re.sub(r"\s+", " ", ENTRY_RE.sub("", text)).strip()

    mismatched = [number for (number, _text), rendered, wanted
                  in zip(P.reference_list(), listed, expected)
                  if normalise(rendered) != normalise(wanted)]
    report.check(not mismatched,
                 "§5 every listed reference matches the verified record",
                 f"entries {mismatched} differ")

    doi_backed = sum(1 for work in P.WORKS.values() if work.doi)
    report.check(doi_backed >= len(P.WORKS) - 2,
                 "§5 all but at most two indexed works carry a DOI",
                 f"{len(P.WORKS) - doi_backed} without one")


def check_citations(paragraphs: list[Paragraph], report: Report) -> None:
    entries = set(range(1, len(P.reference_list()) + 1))
    listing = {p.index for p in paragraphs if ENTRY_RE.match(p.text)}
    cited: set[int] = set()
    for para in paragraphs:
        if para.index in listing:
            continue
        cited.update(int(n) for n in re.findall(r"\[(\d+)\]", para.text))

    report.check(cited <= entries, "§5 every citation has a reference entry",
                 f"cited but undefined: {sorted(cited - entries)}")
    report.check(entries <= cited, "§5 every reference entry is cited",
                 f"defined but never cited: {sorted(entries - cited)}")


def check_no_results(paragraphs: list[Paragraph], report: Report) -> None:
    offenders = [(p.index, RESULT_RE.findall(p.text)) for p in paragraphs
                 if not ENTRY_RE.match(p.text) and RESULT_RE.search(p.text)]
    report.check(not offenders,
                 "the report quotes no measured result",
                 "; ".join(f"para {index}: {found}"
                           for index, found in offenders[:4]))


def check_rendered(paragraphs: list[Paragraph], report: Report) -> None:
    offenders = [p.text[:60] for p in paragraphs
                 if UNRENDERED_RE.search(p.text)]
    report.check(not offenders,
                 "every prose block was passed through render()",
                 "; ".join(offenders[:3]))


def inspect(path: Path) -> int:
    document, parts = load(path)
    report = Report(path)

    body = document.find(f"{W}body")
    paragraphs = [Paragraph(element, index)
                  for index, element in enumerate(body)
                  if element.tag == W + "p"]
    by_index = {p.index: p for p in paragraphs}

    check_sections(document, report)
    check_defaults(parts, report)
    check_fonts(parts, report)
    check_headings(paragraphs, by_index, report)
    check_order(paragraphs, report)
    check_intro_parts(paragraphs, report)
    check_table(parts, document, report)
    check_captions(paragraphs, report)
    check_references_are_verified(paragraphs, report)
    check_citations(paragraphs, report)
    check_no_results(paragraphs, report)
    check_rendered(paragraphs, report)
    check_identity(paragraphs, report)

    return report.emit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="*", type=Path, default=None)
    args = parser.parse_args(argv)

    paths = args.paths or [DEFAULT_PATH]
    missing = [path for path in paths if not path.is_file()]
    for path in missing:
        print(f"  FAIL  {path} does not exist — run "
              "scripts/build_synopsis.py --which progress1 first")
    status = 1 if missing else 0
    for path in paths:
        if path.is_file():
            status |= inspect(path)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
