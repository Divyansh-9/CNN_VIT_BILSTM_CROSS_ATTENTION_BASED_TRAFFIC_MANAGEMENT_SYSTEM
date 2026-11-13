"""Check a generated synopsis `.docx` against the Department's guideline.

Reads the *artefact*, not the source. Every rule below is verified against the
XML Word will actually open, because a correct constant that no paragraph
happens to use passes a source review and fails a submission.

    python scripts/check_synopsis.py
    python scripts/check_synopsis.py docs/demo/MFSTNet-Synopsis-Phase1.docx

Exits 1 if any rule fails. Stdlib only, so it runs anywhere `check_docs.py`
runs — including a CI job with no third-party packages installed.

The rules, and the guideline clause each comes from:

* §2  page size A4, margins left 1.25 in and right/top/bottom 1 in / 0.75 in
* §2  body Times New Roman 12 pt, justified, 1.5 line spacing
* §3  chapter number 16 pt bold left; chapter title 18 pt bold centred;
      section 14 pt bold left; subsection 12 pt bold left
* §4  the prescribed chapter order
* §8  figures and tables numbered chapter-wise, captions 10 pt bold, and
      **every one of them referred to in the text**
* §9  equations numbered chapter-wise in decimal form and referred to in text
* §9  every citation has a reference entry and every entry is cited
* §10 the identity fields appear on the document

The figure, table, equation and citation rules are the ones that catch real
defects; the formatting rules are cheap and catch a regression in the renderer.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts import synopsis_content as C  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Guideline §4. The Phase I proposal splits "Problem Statement & Objectives"
#: and adds no chapter, so one order serves both documents.
REQUIRED_ORDER = (
    "ABSTRACT", "INTRODUCTION", "LITERATURE REVIEW",
    "PROBLEM STATEMENT & OBJECTIVES", "PROPOSED METHODOLOGY",
    "HARDWARE AND SOFTWARE REQUIREMENTS", "EXPECTED OUTCOMES", "CONCLUSION",
    "REFERENCES",
)

#: Permitted on the title page only, because the Department's own format file
#: uses it there. Anywhere else it is a defect.
COVER_FONT = "Bookman Old Style"

A4 = (11906, 16838)
MARGINS = {"left": 1800, "right": 1440, "top": 1080, "bottom": 1080}

#: The document default, in half-points. A run whose size equals the default
#: carries no `w:sz` of its own, so an absent size means 12 pt rather than
#: unknown — reading it as unknown would fail every 12 pt subsection heading.
DEFAULT_SIZE = 24

#: A caption is `Fig. 4.1<two spaces>Title` or `Table 4.1<two spaces>Title`.
#: The two spaces are what separates a caption from a sentence that opens
#: "Table 4.1 lists the hardware" — which is the in-text reference the
#: guideline requires, not a second caption.
CAPTION_RE = re.compile(r"^(Fig\.|Table) (\d+\.\d+)  \S")


class Paragraph:
    """One body-level paragraph, with the properties the guideline names."""

    __slots__ = ("text", "size", "bold", "align", "has_tab", "index")

    def __init__(self, element, index: int) -> None:
        self.index = index
        # Join the <w:t> runs with the empty string, never with a space: Word
        # splits a single word across runs freely, and joining with a space
        # turns "[11]" into "[ 11 ]" and loses the citation.
        self.text = "".join(node.text or ""
                            for node in element.iter(W + "t")).strip()
        self.has_tab = element.find(f".//{W}tab") is not None

        sizes = {node.get(W + "val")
                 for node in element.iter(W + "sz")}
        self.size = int(sorted(sizes)[0]) if sizes else DEFAULT_SIZE
        run_props = element.findall(f"{W}r/{W}rPr")
        self.bold = bool(run_props) and all(
            props.find(W + "b") is not None for props in run_props)
        justification = element.find(f"{W}pPr/{W}jc")
        self.align = justification.get(W + "val") if justification is not None else None

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Para {self.index} {self.size} {self.text[:40]!r}>"


class Report:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.failures: list[str] = []
        self.passes = 0

    def check(self, condition: bool, rule: str, detail: str = "") -> bool:
        if condition:
            self.passes += 1
        else:
            self.failures.append(rule + (f"  —  {detail}" if detail else ""))
        return condition

    def emit(self) -> int:
        name = self.path.name
        if not self.failures:
            print(f"  PASS  {name}  ({self.passes} rules)")
            return 0
        print(f"  FAIL  {name}  ({len(self.failures)} of "
              f"{self.passes + len(self.failures)} rules)")
        for failure in self.failures:
            print(f"          {failure}")
        return 1


def load(path: Path) -> tuple[ElementTree.Element, dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        parts = {name: archive.read(name).decode("utf-8")
                 for name in archive.namelist() if name.endswith(".xml")}
    return ElementTree.fromstring(parts["word/document.xml"]), parts


# --------------------------------------------------------------------------
#  the rules
# --------------------------------------------------------------------------

def check_page(document: ElementTree.Element, parts: dict[str, str],
               report: Report) -> None:
    sections = document.findall(f".//{W}sectPr")
    report.check(len(sections) == 1, "§2 exactly one section",
                 f"found {len(sections)}")
    if not sections:
        return
    size = sections[0].find(W + "pgSz")
    report.check(size is not None
                 and (int(size.get(W + "w")), int(size.get(W + "h"))) == A4,
                 "§2 page size is A4",
                 f"{size.get(W + 'w')}x{size.get(W + 'h')} twips"
                 if size is not None else "no pgSz")
    margin = sections[0].find(W + "pgMar")
    for edge, expected in MARGINS.items():
        actual = int(margin.get(W + edge)) if margin is not None else None
        report.check(actual == expected, f"§2 {edge} margin is {expected} twips",
                     f"got {actual}")


def check_defaults(parts: dict[str, str], report: Report) -> None:
    styles = parts.get("word/styles.xml", "")
    report.check('w:ascii="Times New Roman"' in styles,
                 "§2 default font is Times New Roman")
    report.check('<w:sz w:val="24"/>' in styles, "§2 default size is 12 pt")
    report.check('w:line="360" w:lineRule="auto"' in styles,
                 "§2 default line spacing is 1.5")
    report.check('<w:jc w:val="both"/>' in styles, "§2 body text is justified")


def check_fonts(parts: dict[str, str], report: Report) -> None:
    used = set(re.findall(r'w:ascii="([^"]+)"', parts["word/document.xml"]))
    unexpected = used - {"Times New Roman", COVER_FONT}
    report.check(not unexpected, "§2 no font other than Times New Roman "
                                 f"(and {COVER_FONT} on the cover)",
                 ", ".join(sorted(unexpected)))


def check_headings(paragraphs: list[Paragraph],
                   by_index: dict[int, Paragraph], report: Report) -> None:
    chapters = [p for p in paragraphs if re.fullmatch(r"CHAPTER \d+", p.text)]
    report.check(bool(chapters), "§3 chapter numbers present")
    report.check(all(p.size == 32 and p.bold and p.align in (None, "left")
                     for p in chapters),
                 "§3 chapter number is 16 pt bold, left aligned",
                 ", ".join(f"{p.text}: sz {p.size} bold {p.bold} "
                           f"align {p.align}"
                           for p in chapters
                           if not (p.size == 32 and p.bold
                                   and p.align in (None, "left"))))

    # The chapter title is the paragraph immediately after the number, by body
    # position — which is why paragraphs carry their body index rather than a
    # position in this filtered list.
    titles = [by_index[p.index + 1] for p in chapters
              if p.index + 1 in by_index]
    report.check(len(titles) == len(chapters),
                 "§3 every chapter number is followed by a title")
    report.check(all(p.size == 36 and p.bold and p.align == "center"
                     for p in titles),
                 "§3 chapter title is 18 pt bold, centred",
                 ", ".join(f"{p.text}: sz {p.size} align {p.align}"
                           for p in titles
                           if not (p.size == 36 and p.bold
                                   and p.align == "center")))

    sections = [p for p in paragraphs
                if re.match(r"^\d+\.\d+  \S", p.text) and p.bold]
    report.check(bool(sections), "§3 numbered sections present")
    report.check(all(p.size == 28 and p.align in (None, "left")
                     for p in sections),
                 "§3 section heading is 14 pt bold, left aligned",
                 ", ".join(f"{p.text[:30]}: sz {p.size}" for p in sections
                           if p.size != 28))

    subsections = [p for p in paragraphs
                   if re.match(r"^\d+\.\d+\.\d+  \S", p.text) and p.bold]
    report.check(all(p.size == 24 and p.align in (None, "left")
                     for p in subsections),
                 "§3 subsection heading is 12 pt bold, left aligned",
                 ", ".join(f"{p.text[:30]}: sz {p.size}" for p in subsections
                           if p.size != 24))


def check_order(paragraphs: list[Paragraph], report: Report) -> None:
    headings = [p.text for p in paragraphs if p.size == 36 and p.bold]
    order = [h for h in headings if h in REQUIRED_ORDER]
    report.check(order == list(REQUIRED_ORDER), "§4 prescribed chapter order",
                 " | ".join(order))


def check_captions(paragraphs: list[Paragraph], report: Report) -> None:
    captions = [p for p in paragraphs if CAPTION_RE.match(p.text)]
    report.check(bool(captions), "§8 numbered figures and tables present")
    report.check(all(p.size == 20 and p.bold for p in captions),
                 "§8 captions are 10 pt bold",
                 ", ".join(f"{p.text[:24]}: sz {p.size}" for p in captions
                           if not (p.size == 20 and p.bold)))

    caption_indices = {p.index for p in captions}
    prose = [p for p in paragraphs if p.index not in caption_indices]
    for caption in captions:
        kind, number = CAPTION_RE.match(caption.text).groups()
        word = "Figure" if kind == "Fig." else "Table"
        pattern = re.compile(rf"\b{word} {re.escape(number)}\b")
        report.check(any(pattern.search(p.text) for p in prose),
                     f"§8 {word} {number} is referred to in the text",
                     "captioned but never cited")


def check_equations(paragraphs: list[Paragraph], report: Report) -> None:
    equations = [p for p in paragraphs
                 if p.has_tab and re.search(r"\(\d+\.\d+\)$", p.text)]
    if not equations:
        return
    equation_indices = {p.index for p in equations}
    prose = [p for p in paragraphs if p.index not in equation_indices]
    for eq in equations:
        number = re.search(r"\((\d+\.\d+)\)$", eq.text).group(1)
        # A compound reference — "equations (4.2) and (4.3)" — is correct
        # style, and the second number in it carries no "equation" word of its
        # own. The requirement is that the number appears in the text, so that
        # is what is checked.
        pattern = re.compile(rf"\({re.escape(number)}\)")
        report.check(any(pattern.search(p.text) for p in prose),
                     f"§9 equation ({number}) is referred to in the text",
                     "numbered but never cited")


def check_citations(paragraphs: list[Paragraph], report: Report,
                    references: tuple[str, ...]) -> None:
    entries = set(range(1, len(references) + 1))

    listing = {p.index for p in paragraphs
               if re.match(r"^\[\d+\]", p.text)}
    cited: set[int] = set()
    for para in paragraphs:
        if para.index in listing:
            continue
        cited.update(int(n) for n in re.findall(r"\[(\d+)\]", para.text))

    report.check(cited <= entries, "§9 every citation has a reference entry",
                 f"cited but undefined: {sorted(cited - entries)}")
    report.check(entries <= cited, "§9 every reference entry is cited",
                 f"defined but never cited: {sorted(entries - cited)}")
    report.check(len(listing) == len(references),
                 f"§9 all {len(references)} reference entries are listed",
                 f"found {len(listing)}")


def check_identity(paragraphs: list[Paragraph], report: Report) -> None:
    text = "\n".join(p.text for p in paragraphs)
    for member in C.TEAM:
        report.check(member.name in text and member.roll in text,
                     f"§10 {member.name} and roll {member.roll} appear")
    report.check(C.MENTOR_NAME in text, "§10 mentor name appears")
    report.check(C.TEAM_ID in text, "§10 Project Team ID appears")


def check_fields(parts: dict[str, str], report: Report) -> None:
    footers = [xml for name, xml in parts.items()
               if name.startswith("word/footer")]
    report.check(any("PAGE" in xml for xml in footers),
                 "§2 footer carries a real page-number field")
    report.check("PAGEREF" in parts["word/document.xml"],
                 "§4 table of contents uses PAGEREF fields")


# --------------------------------------------------------------------------

def check(path: Path, references: tuple[str, ...]) -> int:
    document, parts = load(path)
    body = document.find(W + "body")
    # `index` is the position among body-level children, not among paragraphs,
    # so that a chapter number can find the title paragraph after it even when
    # a table sits between two paragraphs elsewhere.
    paragraphs = [Paragraph(element, index)
                  for index, element in enumerate(body)
                  if element.tag == W + "p"]
    by_index = {p.index: p for p in paragraphs}

    report = Report(path)
    check_page(document, parts, report)
    check_defaults(parts, report)
    check_fonts(parts, report)
    check_headings(paragraphs, by_index, report)
    check_order(paragraphs, report)
    check_captions(paragraphs, report)
    check_equations(paragraphs, report)
    check_citations(paragraphs, report, references)
    check_identity(paragraphs, report)
    check_fields(parts, report)
    return report.emit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("paths", nargs="*", type=Path,
                        help="documents to check; defaults to both synopses")
    args = parser.parse_args(argv)

    from scripts import synopsis_phase1_content as P

    default = [
        (C.ROOT / "docs" / "demo" / "MFSTNet-Synopsis-Report.docx",
         C.REFERENCES),
        (C.ROOT / "docs" / "demo" / "MFSTNet-Synopsis-Phase1.docx",
         P.REFERENCES),
    ]
    if args.paths:
        lookup = {path.name: refs for path, refs in default}
        targets = [(path, lookup.get(path.name, C.REFERENCES))
                   for path in args.paths]
    else:
        targets = default

    print()
    status = 0
    for path, references in targets:
        if not path.is_file():
            print(f"  SKIP  {path.name}  —  not built")
            continue
        status |= check(path, references)
    print()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
