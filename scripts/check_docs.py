"""Documentation integrity checks. Standard library only, so CI needs no install.

    python scripts/check_docs.py

Three checks:

1. Every relative markdown link resolves.
2. No withdrawn claim reappears outside the archive and the register.
3. Every ADR is referenced from DOCUMENT-REGISTER.md.

These are the mechanical half of keeping the suite honest. The half that needs
judgement -- does this document still say the right thing -- is the wave-gate
reconciliation in DOCUMENT-REGISTER.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)#]+?)(?:#[^)]*)?\)")

# Files exempt from the link check, with the reason.
LINK_EXEMPT = {
    # Links are written relative to docs/90-manual/weekly/, where the template
    # gets copied -- not relative to the template's own location.
    "docs/templates/weekly-status.md",
}

# Claims that were wrong and have been corrected. If one reappears in a live
# document, someone has resurrected a stale draft.
# (regex, human-readable correction)
WITHDRAWN = [
    (r"400\s*frames\s*/\s*day", "annotation velocity -- wrong ~3x; measure it (Manual 1.2)"),
    (r"trained on SUMO sequences", "MFSTNet trains on auto-labelled real video (PRD 8.6)"),
    (r"unfreeze_epoch:\s*30", "replaced by the LoRA experiment (PRD A12)"),
    (r"500 sequences spot-checked", "verification concentrated on the test split (PRD A9)"),
]

# Paths exempt wholesale: the archive (superseded by definition) and this file.
WITHDRAWN_ALLOWED = (
    "docs/99-archive/",
    "scripts/check_docs.py",
)

# Everywhere else, a withdrawn claim is acceptable only when it is being
# CORRECTED rather than asserted. A blanket per-file allowlist would let a
# genuine regression through, so instead require a correction marker within
# CONTEXT_LINES of the occurrence.
CORRECTION_MARKERS = re.compile(
    r"withdraw|retire|replac|supersed|instead|rather than|no longer|reclassif|"
    r"wrong|incorrect|correct|amendment|deprecat|do not|removed|is false|"
    r"defect|problem|overfit|predicts|not viable|context\b|ADR-|A9|A12",
    re.IGNORECASE,
)
# ADRs and the changelog quote prior state at length before correcting it, so
# the window has to be generous. It is still bounded -- a claim asserted in a
# document with no correction anywhere near it is what we are hunting.
CONTEXT_LINES = 8

failures: list[str] = []


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def markdown_files() -> list[Path]:
    return [
        p
        for p in ROOT.rglob("*.md")
        if ".git" not in p.parts and "node_modules" not in p.parts
    ]


def check_links(files: list[Path]) -> None:
    for md in files:
        if rel(md) in LINK_EXEMPT:
            continue
        for m in LINK.finditer(md.read_text(encoding="utf-8", errors="replace")):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().exists():
                failures.append(f"broken link  {rel(md)} -> {target}")


def check_withdrawn(files: list[Path]) -> None:
    """Flag a withdrawn claim only where it is asserted, not where it is corrected."""
    for md in files:
        r = rel(md)
        if r.startswith(WITHDRAWN_ALLOWED):
            continue
        lines = md.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            for pattern, correction in WITHDRAWN:
                if not re.search(pattern, line, re.IGNORECASE):
                    continue
                lo = max(0, i - CONTEXT_LINES)
                hi = min(len(lines), i + CONTEXT_LINES + 1)
                context = "\n".join(lines[lo:hi])
                if CORRECTION_MARKERS.search(context):
                    continue  # quoted while being corrected -- fine
                failures.append(
                    f"withdrawn claim asserted  {r}:{i + 1}: /{pattern}/ -- {correction}"
                )


def check_adrs_registered() -> None:
    adr_dir = ROOT / "docs" / "00-planning" / "decisions"
    register = ROOT / "docs" / "DOCUMENT-REGISTER.md"
    if not register.exists():
        failures.append("missing  docs/DOCUMENT-REGISTER.md")
        return
    listed = register.read_text(encoding="utf-8", errors="replace")
    for adr in sorted(adr_dir.glob("ADR-*.md")):
        if adr.name not in listed:
            failures.append(f"unregistered ADR  {adr.name} absent from DOCUMENT-REGISTER.md")


def main() -> int:
    files = markdown_files()
    check_links(files)
    check_withdrawn(files)
    check_adrs_registered()

    print(f"checked {len(files)} markdown files")
    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("links resolve, no withdrawn claims resurrected, all ADRs registered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
