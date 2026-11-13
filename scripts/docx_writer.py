"""A dependency-free WordprocessingML writer.

`python-docx` is not pinned in `requirements.txt`, and this repository's rule is
that a dependency is pinned in the same commit as its first import. Rather than
add a wheel for one document, this module writes the `.docx` package directly:
the format is a zip of XML parts, and the subset needed for an academic report
— styled paragraphs, bordered tables, inline images, page-number and
cross-reference fields, a footer — is small enough to build honestly.

It is deliberately not a general-purpose library. It exposes exactly what
`scripts/build_synopsis.py` needs to hit the formatting the Department's
synopsis format and guidelines prescribe: A4, Times New Roman, 12 pt justified
body at 1.5-line spacing, chapter/section/subsection heading sizes, 10 pt bold
captions, and consistent page numbering.

Sizes are given in **half-points** (Word's own unit: 24 = 12 pt) and lengths in
**twips** (1/1440 inch), so the numbers in the caller read the same as the
numbers in the guideline.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# -- units -----------------------------------------------------------------
TWIPS_PER_INCH = 1440
EMU_PER_INCH = 914400

#: 1.5-line spacing, as Word encodes it (240 twips = single).
LINE_ONE_HALF = 360
LINE_SINGLE = 240

DEFAULT_FONT = "Times New Roman"


def inches(value: float) -> int:
    return int(round(value * TWIPS_PER_INCH))


def emu(value: float) -> int:
    return int(round(value * EMU_PER_INCH))


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# ==========================================================================
#  runs
# ==========================================================================

@dataclass
class Run:
    """One stretch of uniformly formatted text."""

    text: str = ""
    bold: bool = False
    italic: bool = False
    size: int = 24
    font: str = DEFAULT_FONT
    caps: bool = False
    subscript: bool = False
    superscript: bool = False
    #: Field code, e.g. ``PAGE`` or ``PAGEREF ch1 \\h``. When set, ``text`` is
    #: the placeholder Word shows until fields are refreshed.
    field: str | None = None
    #: Insert a line break (not a paragraph break) before this run's text.
    break_before: bool = False

    def xml(self) -> str:
        props = [f'<w:rFonts w:ascii="{esc(self.font)}" w:hAnsi="{esc(self.font)}"'
                 f' w:eastAsia="{esc(self.font)}" w:cs="{esc(self.font)}"/>']
        if self.bold:
            props.append("<w:b/><w:bCs/>")
        if self.italic:
            props.append("<w:i/><w:iCs/>")
        if self.caps:
            props.append("<w:caps/>")
        if self.subscript:
            props.append('<w:vertAlign w:val="subscript"/>')
        if self.superscript:
            props.append('<w:vertAlign w:val="superscript"/>')
        props.append(f'<w:sz w:val="{self.size}"/><w:szCs w:val="{self.size}"/>')
        rpr = "<w:rPr>" + "".join(props) + "</w:rPr>"

        if self.field is not None:
            return (
                f'<w:r>{rpr}<w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r>{rpr}<w:instrText xml:space="preserve"> {esc(self.field)} </w:instrText></w:r>'
                f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r>'
                f'<w:r>{rpr}<w:t>{esc(self.text)}</w:t></w:r>'
                f'<w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>'
            )

        body = "<w:br/>" if self.break_before else ""
        # Tabs are written as real tab characters by the caller; split them out
        # so Word advances to the next tab stop instead of printing nothing.
        for index, chunk in enumerate(self.text.split("\t")):
            if index:
                body += "<w:tab/>"
            if chunk:
                body += f'<w:t xml:space="preserve">{esc(chunk)}</w:t>'
        return f"<w:r>{rpr}{body}</w:r>"


def text_run(text: str, **kwargs) -> Run:
    return Run(text=text, **kwargs)


# ==========================================================================
#  paragraphs
# ==========================================================================

@dataclass
class Para:
    """One paragraph, with the properties the guideline actually constrains."""

    runs: list[Run] = field(default_factory=list)
    align: str = "both"          # both | left | center | right
    line: int = LINE_ONE_HALF
    before: int = 0              # twips of space before
    after: int = 120             # twips of space after
    indent_left: int = 0
    indent_first: int = 0
    indent_hanging: int = 0
    keep_next: bool = False
    page_break_before: bool = False
    bookmark: str | None = None
    outline_level: int | None = None   # 0 = chapter, 1 = section, ...
    numbering: tuple[int, int] | None = None   # (numId, ilvl)
    tabs: tuple = ()             # int (left tab) or (pos, val, leader)
    border_bottom: bool = False

    def xml(self, bookmark_id: int = 0) -> str:
        props: list[str] = []
        if self.page_break_before:
            props.append("<w:pageBreakBefore/>")
        if self.keep_next:
            props.append("<w:keepNext/>")
        if self.numbering is not None:
            num_id, ilvl = self.numbering
            props.append(f'<w:numPr><w:ilvl w:val="{ilvl}"/>'
                         f'<w:numId w:val="{num_id}"/></w:numPr>')
        if self.border_bottom:
            props.append('<w:pBdr><w:bottom w:val="single" w:sz="6"'
                         ' w:space="4" w:color="808080"/></w:pBdr>')
        if self.tabs:
            stops = ""
            for stop in self.tabs:
                if isinstance(stop, tuple):
                    pos, val, leader = stop
                    stops += (f'<w:tab w:val="{val}" w:leader="{leader}"'
                              f' w:pos="{pos}"/>')
                else:
                    stops += f'<w:tab w:val="left" w:pos="{stop}"/>'
            props.append(f"<w:tabs>{stops}</w:tabs>")
        spacing = (f'<w:spacing w:line="{self.line}" w:lineRule="auto"'
                   f' w:before="{self.before}" w:after="{self.after}"/>')
        props.append(spacing)
        if self.indent_left or self.indent_first or self.indent_hanging:
            bits = f'w:left="{self.indent_left}"'
            if self.indent_first:
                bits += f' w:firstLine="{self.indent_first}"'
            if self.indent_hanging:
                bits += f' w:hanging="{self.indent_hanging}"'
            props.append(f"<w:ind {bits}/>")
        props.append(f'<w:jc w:val="{self.align}"/>')
        if self.outline_level is not None:
            props.append(f'<w:outlineLvl w:val="{self.outline_level}"/>')

        inner = "".join(run.xml() for run in self.runs)
        if self.bookmark:
            inner = (f'<w:bookmarkStart w:id="{bookmark_id}"'
                     f' w:name="{esc(self.bookmark)}"/>{inner}'
                     f'<w:bookmarkEnd w:id="{bookmark_id}"/>')
        return f"<w:p><w:pPr>{''.join(props)}</w:pPr>{inner}</w:p>"


@dataclass
class Image:
    """An inline image, sized in inches, wrapped in its own paragraph."""

    rel_id: str
    width_in: float
    height_in: float
    align: str = "center"
    after: int = 120
    name: str = "Picture"

    def xml(self, doc_pr_id: int = 1) -> str:
        cx, cy = emu(self.width_in), emu(self.height_in)
        drawing = (
            f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{doc_pr_id}" name="{esc(self.name)}"/>'
            f"<a:graphic><a:graphicData"
            f' uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f"<pic:pic><pic:nvPicPr>"
            f'<pic:cNvPr id="{doc_pr_id}" name="{esc(self.name)}"/><pic:cNvPicPr/>'
            f"</pic:nvPicPr><pic:blipFill>"
            f'<a:blip r:embed="{self.rel_id}"/><a:stretch><a:fillRect/></a:stretch>'
            f"</pic:blipFill><pic:spPr>"
            f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f"</pic:spPr></pic:pic></a:graphicData></a:graphic>"
            f"</wp:inline></w:drawing>"
        )
        return (f'<w:p><w:pPr><w:spacing w:line="{LINE_SINGLE}" w:lineRule="auto"'
                f' w:after="{self.after}"/><w:jc w:val="{self.align}"/></w:pPr>'
                f"<w:r>{drawing}</w:r></w:p>")


@dataclass
class Cell:
    paras: list[Para]
    width: int
    shaded: bool = False
    valign: str = "center"
    span: int = 1
    #: Draw a border around this cell alone. Block diagrams are built from a
    #: borderless table whose nodes are boxed cells and whose arrows are not,
    #: which is the only way to get a diagram out of a table without shipping
    #: a rendered image.
    boxed: bool = False
    fill: str | None = None

    def xml(self) -> str:
        props = [f'<w:tcW w:w="{self.width}" w:type="dxa"/>']
        if self.span > 1:
            props.append(f'<w:gridSpan w:val="{self.span}"/>')
        if self.boxed:
            props.append("<w:tcBorders>" + "".join(
                f'<w:{side} w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
                for side in ("top", "left", "bottom", "right")
            ) + "</w:tcBorders>")
        fill = self.fill or ("EDEDED" if self.shaded else None)
        if fill:
            props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>')
        props.append(f'<w:vAlign w:val="{self.valign}"/>')
        body = "".join(p.xml() for p in self.paras) or "<w:p/>"
        return f"<w:tc><w:tcPr>{''.join(props)}</w:tcPr>{body}</w:tc>"


@dataclass
class Table:
    rows: list[list[Cell]]
    widths: list[int]
    borders: bool = True
    header_rows: int = 1
    align: str = "center"
    #: Keep each row on one page. Word's default is to break a row across a
    #: page boundary, which in a comparative table orphans the tail of a row's
    #: cells at the top of the next page with no serial number beside them —
    #: so the reader cannot tell which work they belong to. Costs some
    #: whitespace at the foot of a page and is worth it.
    cant_split: bool = False

    def xml(self) -> str:
        if self.borders:
            edge = '<w:{0} w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            border_xml = "<w:tblBorders>" + "".join(
                edge.format(side) for side in
                ("top", "left", "bottom", "right", "insideH", "insideV")
            ) + "</w:tblBorders>"
        else:
            border_xml = "<w:tblBorders>" + "".join(
                f'<w:{side} w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                for side in ("top", "left", "bottom", "right", "insideH", "insideV")
            ) + "</w:tblBorders>"
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in self.widths)
        props = (f'<w:tblPr><w:tblW w:w="{sum(self.widths)}" w:type="dxa"/>'
                 f'<w:jc w:val="{self.align}"/>{border_xml}'
                 f'<w:tblLayout w:type="fixed"/>'
                 f'<w:tblCellMar>'
                 f'<w:top w:w="60" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
                 f'<w:bottom w:w="60" w:type="dxa"/><w:right w:w="90" w:type="dxa"/>'
                 f"</w:tblCellMar></w:tblPr>")
        body = ""
        for index, row in enumerate(self.rows):
            row_props = "<w:trPr>"
            if self.cant_split:
                row_props += "<w:cantSplit/>"
            if index < self.header_rows:
                row_props += "<w:tblHeader/>"
            row_props += "</w:trPr>"
            body += ("<w:tr>" + row_props
                     + "".join(cell.xml() for cell in row) + "</w:tr>")
        return f"<w:tbl>{props}<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"


# ==========================================================================
#  the package
# ==========================================================================

@dataclass
class SectionBreak:
    """Ends the current section, so the next one can have a different page.

    A seven-column comparative table does not read in portrait: the Department
    margins leave 6.02 in of content width, and seven prose columns inside that
    set at about eight words a line. Landscape A4 gives 9.44 in for the same
    table. Word expresses this by hanging a `sectPr` on the **last paragraph of
    the section being ended** — so this block is emitted *after* the content it
    applies to, and the geometry it carries describes that content, not what
    follows. Getting that backwards silently rotates the wrong pages.

    The body's own trailing `sectPr` describes the final section, which is why
    `Document` still writes one and why a document with no `SectionBreak` is
    unchanged by this class existing.
    """

    landscape: bool = False
    page_width: int = 11906           # A4 short edge, 210 mm
    page_height: int = 16838          # A4 long edge, 297 mm
    margin_left: int = inches(1.25)
    margin_right: int = inches(1.0)
    margin_top: int = inches(0.75)
    margin_bottom: int = inches(0.75)

    def sect_pr(self, first: bool = False) -> str:
        width, height = self.page_width, self.page_height
        orient = ""
        if self.landscape:
            width, height = height, width
            orient = ' w:orient="landscape"'
        # Only the first section states where numbering starts; the rest
        # inherit it and so continue. See `Document._document_xml`.
        start = '<w:pgNumType w:start="1"/>' if first else ""
        return (
            f'<w:sectPr><w:footerReference w:type="default" r:id="rId4"/>'
            f'<w:pgSz w:w="{width}" w:h="{height}"{orient}/>'
            f'<w:pgMar w:top="{self.margin_top}" w:right="{self.margin_right}"'
            f' w:bottom="{self.margin_bottom}" w:left="{self.margin_left}"'
            f' w:header="709" w:footer="709" w:gutter="0"/>'
            f'{start}<w:cols w:space="708"/></w:sectPr>'
        )

    def xml(self, first: bool = False) -> str:
        return (f'<w:p><w:pPr>{self.sect_pr(first)}'
                f'<w:spacing w:line="{LINE_SINGLE}" w:lineRule="auto"'
                f' w:after="0"/></w:pPr></w:p>')


NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ' xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpeg" ContentType="image/jpeg"/>
<Default Extension="jpg" ContentType="image/jpeg"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

_SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/>
<w:updateFields w:val="true"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""

_NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0">
  <w:multiLevelType w:val="hybridMultilevel"/>
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#8226;"/>
    <w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>
  <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#9702;"/>
    <w:lvlJc w:val="left"/><w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:hint="default"/></w:rPr></w:lvl>
</w:abstractNum>
<w:abstractNum w:abstractNumId="1">
  <w:multiLevelType w:val="hybridMultilevel"/>
  <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>
    <w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def _styles(font: str, size: int, line: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
  <w:rFonts w:ascii="{esc(font)}" w:hAnsi="{esc(font)}" w:eastAsia="{esc(font)}" w:cs="{esc(font)}"/>
  <w:sz w:val="{size}"/><w:szCs w:val="{size}"/><w:lang w:val="en-IN"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr>
  <w:spacing w:line="{line}" w:lineRule="auto" w:after="120"/>
  <w:jc w:val="both"/>
</w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
  <w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:outlineLvl w:val="0"/></w:pPr>
  <w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
  <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
  <w:pPr><w:outlineLvl w:val="1"/></w:pPr>
  <w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style>
</w:styles>"""


def _footer(font: str) -> str:
    page = Run(text="1", field="PAGE", font=font, size=20)
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f"<w:ftr {NS}>"
            f'<w:p><w:pPr><w:spacing w:line="{LINE_SINGLE}" w:lineRule="auto"'
            f' w:after="0"/><w:jc w:val="center"/></w:pPr>{page.xml()}</w:p>'
            f"</w:ftr>")


def _core(title: str, authors: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>{esc(title)}</dc:title><dc:creator>{esc(authors)}</dc:creator>
</cp:coreProperties>"""

_APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>scripts/build_synopsis.py</Application>
</Properties>"""


@dataclass
class Document:
    """Accumulates block-level content, then writes the `.docx` package."""

    font: str = DEFAULT_FONT
    size: int = 24
    line: int = LINE_ONE_HALF
    margin_left: int = inches(1.25)
    margin_right: int = inches(1.0)
    margin_top: int = inches(0.75)
    margin_bottom: int = inches(0.75)
    page_width: int = 11906           # A4, 210 mm
    page_height: int = 16838          # A4, 297 mm
    title: str = ""
    authors: str = ""

    _blocks: list[object] = field(default_factory=list, init=False)
    _images: dict[str, tuple[str, bytes]] = field(default_factory=dict, init=False)
    _next_image: int = field(default=100, init=False)

    # -- content ----------------------------------------------------------
    def add(self, block) -> None:
        self._blocks.append(block)

    def add_image(self, data: bytes, extension: str, width_in: float,
                  height_in: float, align: str = "center",
                  name: str = "Picture") -> None:
        rel = f"rId{self._next_image}"
        self._next_image += 1
        filename = f"image{len(self._images) + 1}.{extension}"
        self._images[rel] = (filename, data)
        self.add(Image(rel_id=rel, width_in=width_in, height_in=height_in,
                       align=align, name=name))

    @property
    def content_width(self) -> int:
        return self.page_width - self.margin_left - self.margin_right

    # -- output -----------------------------------------------------------
    def _document_xml(self) -> str:
        parts: list[str] = []
        bookmark_id = 1
        picture_id = 1
        # `w:pgNumType w:start="1"` belongs to the FIRST section only. Every
        # later section inherits continuous numbering by saying nothing; one
        # that repeats the start restarts the count, so in a document with a
        # landscape table in the middle the pages after it begin again at 1.
        # That is what shipped, and it is only visible past the table.
        seen_section = False
        for block in self._blocks:
            if isinstance(block, Para):
                parts.append(block.xml(bookmark_id))
                bookmark_id += 1
            elif isinstance(block, Image):
                parts.append(block.xml(picture_id))
                picture_id += 1
            elif isinstance(block, SectionBreak):
                parts.append(block.xml(first=not seen_section))
                seen_section = True
            else:
                parts.append(block.xml())
        start = "" if seen_section else '<w:pgNumType w:start="1"/>'
        sect = (
            f'<w:sectPr><w:footerReference w:type="default" r:id="rId4"/>'
            f'<w:pgSz w:w="{self.page_width}" w:h="{self.page_height}"/>'
            f'<w:pgMar w:top="{self.margin_top}" w:right="{self.margin_right}"'
            f' w:bottom="{self.margin_bottom}" w:left="{self.margin_left}"'
            f' w:header="709" w:footer="709" w:gutter="0"/>'
            f'{start}<w:cols w:space="708"/></w:sectPr>'
        )
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f"<w:document {NS}><w:body>{''.join(parts)}{sect}</w:body></w:document>")

    def _document_rels(self) -> str:
        base = (
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/settings" Target="settings.xml"/>'
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        )
        for rel, (filename, _data) in self._images.items():
            base += (f'<Relationship Id="{rel}" Type="http://schemas.openxmlformats.org/'
                     f'officeDocument/2006/relationships/image" Target="media/{filename}"/>')
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
                f'2006/relationships">{base}</Relationships>')

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as pkg:
            pkg.writestr("[Content_Types].xml", _CONTENT_TYPES)
            pkg.writestr("_rels/.rels", _ROOT_RELS)
            pkg.writestr("word/document.xml", self._document_xml())
            pkg.writestr("word/_rels/document.xml.rels", self._document_rels())
            pkg.writestr("word/styles.xml", _styles(self.font, self.size, self.line))
            pkg.writestr("word/numbering.xml", _NUMBERING)
            pkg.writestr("word/settings.xml", _SETTINGS)
            pkg.writestr("word/footer1.xml", _footer(self.font))
            pkg.writestr("docProps/core.xml", _core(self.title, self.authors))
            pkg.writestr("docProps/app.xml", _APP)
            for filename, data in self._images.values():
                pkg.writestr(f"word/media/{filename}", data)
