"""Build both synopsis deliverables from one command.

The Department's guideline requires the project title, Project Team ID, student
names, roll numbers and Project Mentor name to be identical across the
synopsis, the presentation and the project records (§1), and makes verifying
that a final submission check (§10). Building the report and the deck from one
entry point is what makes that mechanical rather than a proofreading task:
both renderers read their identity from `scripts/synopsis_content.py` and their
numbers from the committed CSVs under `experiments/results/`.

    python scripts/build_synopsis.py --which all --pdf

`--pdf` drives real PowerPoint and real Word over COM, so it is Windows-only
and silently skipped elsewhere rather than approximated by a second renderer —
an approximate PDF of a submitted document is worse than no PDF.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts import build_phase1_progress_docx as progress1_builder  # noqa: E402
from scripts import build_phase1_progress_pptx as progress1_deck  # noqa: E402
from scripts import build_synopsis_docx as docx_builder  # noqa: E402
from scripts import build_synopsis_phase1_docx as phase1_builder  # noqa: E402
from scripts import build_synopsis_phase1_pptx as phase1_deck  # noqa: E402
from scripts import build_synopsis_pptx as pptx_builder  # noqa: E402
from scripts import phase1_progress_content as progress_content  # noqa: E402
from scripts import synopsis_content as C  # noqa: E402
from scripts.build_review_pptx import export_pdf  # noqa: E402

OUT_DIR = C.ROOT / "docs" / "demo"
DOCX_PATH = OUT_DIR / "MFSTNet-Synopsis-Report.docx"
PPTX_PATH = OUT_DIR / "MFSTNet-Synopsis-Presentation.pptx"

#: The Phase I proposal. A separate document rather than a mode of the progress
#: report: it is submitted at a different point in the project and must not
#: quote a result, so its renderer has no access to `load_facts()` at all. The
#: deck is built from the same content module for the same reason.
PHASE1_PATH = OUT_DIR / "MFSTNet-Synopsis-Phase1.docx"
PHASE1_PPTX_PATH = OUT_DIR / "MFSTNet-Synopsis-Phase1-Presentation.pptx"

#: Phase-I Progress Report – 1. A third deliverable answering a *different*
#: Department guideline: five sections, a comparative table of 25-30 papers,
#: and no methodology, requirements or results chapter at all. Like the
#: proposal it cannot quote a measurement, and for the same structural reason —
#: its content module has no import path to `load_facts()`.
PROGRESS1_PATH = OUT_DIR / "MFSTNet-Phase1-Progress-Report-1.docx"
PROGRESS1_PPTX_PATH = (OUT_DIR
                       / "MFSTNet-Phase1-Progress-Report-1-Presentation.pptx")


def export_docx_pdf(docx_path: Path) -> Path | None:
    """Export the report to PDF using Word itself.

    Word is the only renderer that resolves the document's own field codes, so
    it is the only one whose page numbers in the table of contents will match
    the pages they point at. A LibreOffice or reportlab pass would produce a
    plausible PDF with a table of contents that lies.
    """
    if sys.platform != "win32":
        print("  PDF export skipped: needs Word on Windows")
        return None

    pdf_path = docx_path.with_suffix(".pdf")
    script = f"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {{
    $doc = $word.Documents.Open('{docx_path}', $false, $true)
    $doc.Fields.Update() | Out-Null
    foreach ($story in $doc.StoryRanges) {{ $story.Fields.Update() | Out-Null }}
    $doc.ExportAsFixedFormat('{pdf_path}', 17)
    $doc.Close(0)
}} finally {{
    $word.Quit()
}}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script_path)],
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"  PDF export skipped: {error}")
        return None
    finally:
        script_path.unlink(missing_ok=True)

    if result.returncode != 0 or not pdf_path.is_file():
        first_line = (result.stderr or result.stdout).strip().splitlines()
        print("  PDF export failed: "
              + (first_line[0] if first_line else "no output"))
        return None
    return pdf_path


def report(path: Path, note: str = "") -> None:
    size = path.stat().st_size / 1024
    # `--out-dir` may point outside the repository — a scratch directory is the
    # way to build a verification copy while the real one is open in Word — so
    # the relative path is a nicety, not something to fail the build over.
    try:
        shown = path.relative_to(C.ROOT)
    except ValueError:
        shown = path
    print(f"  wrote {shown}  ({size:.0f} KB{note})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--which",
                        choices=("docx", "pptx", "phase1", "progress1", "all"),
                        default="all", help="which deliverable to build")
    parser.add_argument("--pdf", action="store_true",
                        help="also export PDFs, driving Word and PowerPoint")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    print(f"\n  {C.TITLE_SHORT} synopsis  ·  Project Team ID {C.TEAM_ID}")
    print(f"  team: {C.AUTHORS}")
    print(f"  mentor: {C.MENTOR_NAME}\n")

    # The Phase I proposal quotes no result, so its build must not depend on
    # the result files existing or parsing. Load them only for the documents
    # that actually read them.
    if args.which in ("docx", "pptx", "all"):
        facts = C.load_facts()
        best_config, best_f1 = facts.best_vision
        best_model, best_counts = facts.best_counts

        print(f"  facts read from committed CSVs:")
        print(f"    best vision config      {best_config} at "
              f"{C.fmt(best_f1)} macro-F1 over {facts.n_folds} folds "
              f"× {facts.n_seeds} seeds")
        print(f"    best count baseline     {best_model} at {C.fmt(best_counts)}")
        print(f"    control improvement     "
              f"{float(facts.control['improvement_percent']):.2f}% vs Webster over "
              f"{facts.control['n_pairs']} paired seeds")
        print(f"    gate vs probe verdict   {facts.gate['verdict']}\n")

    if args.which in ("docx", "all"):
        path = docx_builder.build(args.out_dir / DOCX_PATH.name)
        report(path)
        if args.pdf:
            pdf = export_docx_pdf(path)
            if pdf:
                report(pdf)

    if args.which in ("phase1", "all"):
        path = phase1_builder.build(args.out_dir / PHASE1_PATH.name)
        report(path, ", proposal — no measured results by construction")
        if args.pdf:
            pdf = export_docx_pdf(path)
            if pdf:
                report(pdf)

        path = phase1_deck.build(args.out_dir / PHASE1_PPTX_PATH.name)
        report(path, f", {phase1_deck.TOTAL} slides")
        if args.pdf:
            pdf = export_pdf(path)
            if pdf:
                report(pdf)

    if args.which in ("progress1", "all"):
        path = progress1_builder.build(args.out_dir / PROGRESS1_PATH.name)
        report(path, f", {len(progress_content.SURVEY_TABLE)} papers compared "
                     f"— no measured results by construction")
        if args.pdf:
            pdf = export_docx_pdf(path)
            if pdf:
                report(pdf)

        path = progress1_deck.build(args.out_dir / PROGRESS1_PPTX_PATH.name)
        report(path, f", {progress1_deck.TOTAL} slides")
        if args.pdf:
            pdf = export_pdf(path)
            if pdf:
                report(pdf)

    if args.which in ("pptx", "all"):
        path = pptx_builder.build(args.out_dir / PPTX_PATH.name)
        report(path, f", {pptx_builder.TOTAL} slides")
        if args.pdf:
            pdf = export_pdf(path)
            if pdf:
                report(pdf)

    if C.TEAM_ID.endswith("XXX"):
        print("\n  NOTE  the Project Team ID is still the guideline's own "
              "example placeholder.")
        print("        Guideline §10 makes verifying it on every document a "
              "submission check —")
        print("        set TEAM_ID in scripts/synopsis_content.py once the "
              "Department allots it,")
        print("        then rebuild. Both documents pick it up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
