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


# Directories whose markdown belongs to somebody else. `.venv` joined this list
# when `pip install eclipse-sumo` landed SUMO's own documentation inside it and
# this checker started reporting broken links in third-party files — noise that
# would train a reader to ignore the output, which is the one thing a checker
# must never do.
VENDOR_DIRS = {".git", ".venv", "venv", "node_modules", "site-packages", "__pycache__"}


def markdown_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md") if VENDOR_DIRS.isdisjoint(p.parts)]


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


# Where each requirement family is DEFINED. Not one place, and CLAUDE.md said
# it was: NFR-14 to NFR-16 are introduced by NFR.md itself, which states as
# much, because they are constraints the PRD implies without ever writing down
# as verifiable requirements. A rule that does not match the repository is
# worse than no rule -- it invites a defect report against the documents.
DEFINITIONS = {
    "BR": ["docs/00-planning/BRD.md", "docs/01-requirements/BRS.md"],
    "FR": ["docs/00-planning/PRD.md", "docs/01-requirements/SRS.md"],
    "NFR": ["docs/00-planning/PRD.md", "docs/01-requirements/NFR.md"],
}
RTM_PATH = "docs/01-requirements/RTM.md"
REQUIREMENT = re.compile(r"\b((?:BR|NFR|FR)-[A-Z]?[0-9]{2})\b")


def defined_requirements() -> dict:
    """Every requirement id that some definition document actually declares."""
    found = {}
    for family, sources in DEFINITIONS.items():
        ids = set()
        for relative in sources:
            path = ROOT / relative
            if path.exists():
                ids |= {i for i in REQUIREMENT.findall(
                    path.read_text(encoding="utf-8", errors="replace"))
                    if i.startswith(family + "-")}
        found[family] = ids
    return found


def check_requirements_traceable(files: list[Path]) -> None:
    """Two directions, both of which have gone wrong in this repository.

    **Cited but undefined** is the one that bites a reader: a document leans on
    `NFR-16` and there is nowhere to look it up. It is also how a requirement
    gets invented in prose and then treated as governing.

    **Defined but absent from the RTM** is the one that bites the project: the
    RTM is the join table (BR -> FR/NFR -> DES -> TC -> M) and a requirement
    missing from it has no traceable test or milestone. It is a graded
    deliverable, and it went 12 days without an update while 15 ADRs landed.
    """
    defined = defined_requirements()
    every = set().union(*defined.values())
    if not every:
        failures.append("no requirement ids found in any definition document")
        return

    cited = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for identifier in REQUIREMENT.findall(text):
            cited.setdefault(identifier, set()).add(
                path.relative_to(ROOT).as_posix())

    for identifier in sorted(set(cited) - every):
        where = sorted(cited[identifier])[:2]
        failures.append(
            f"undefined requirement  {identifier} is cited in "
            f"{', '.join(where)} but no definition document declares it")

    rtm = ROOT / RTM_PATH
    if not rtm.exists():
        failures.append(f"missing  {RTM_PATH}")
        return
    traced = set(REQUIREMENT.findall(
        rtm.read_text(encoding="utf-8", errors="replace")))
    for identifier in sorted(every - traced):
        failures.append(
            f"untraced requirement  {identifier} is defined but absent from "
            f"{RTM_PATH}, so it has no test or milestone behind it")


AMENDS = re.compile(r"(?:Amends|Supersedes|Replaces).*PRD.*" + chr(167))


def check_amendments_land(files: list[Path]) -> None:
    """An ADR that amends a PRD section must be reachable FROM that section.

    CLAUDE.md's rule is "amend the PRD and log it in PRD-CHANGELOG -- never work
    around a PRD statement you believe is incorrect." The changelog half is easy
    to remember because it is where the work happens. The PRD half is easy to
    skip, and skipping it leaves the source of truth stating something two
    decisions have since replaced.

    That happened twice in one day: ADR-019 amended the split ratio and ADR-020
    the state layout, and the PRD mentioned neither. A reader of PRD 8.4 had no
    way to learn that leave-one-camera-out exists.

    The check is deliberately weak -- it asks only that the ADR's identifier
    appear somewhere in the PRD, not that the prose be correct. A stronger check
    would need to understand the amendment, and a check nobody can satisfy is a
    check that gets deleted.
    """
    prd = ROOT / "docs" / "00-planning" / "PRD.md"
    if not prd.exists():
        failures.append("missing  docs/00-planning/PRD.md")
        return
    text = prd.read_text(encoding="utf-8", errors="replace")
    adr_dir = ROOT / "docs" / "00-planning" / "decisions"
    for adr in sorted(adr_dir.glob("ADR-*.md")):
        head = adr.read_text(encoding="utf-8", errors="replace").split(chr(10))[:12]
        if not any(AMENDS.search(line) for line in head):
            continue
        identifier = adr.name[:7]
        if identifier not in text:
            failures.append(
                f"unlanded amendment  {adr.name} says it amends a PRD section, "
                f"but the PRD never mentions {identifier} -- a reader of that "
                f"section cannot learn the amendment exists")


def main() -> int:
    files = markdown_files()
    check_links(files)
    check_withdrawn(files)
    check_adrs_registered()
    check_requirements_traceable(files)
    check_amendments_land(files)

    print(f"checked {len(files)} markdown files")
    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("links resolve, no withdrawn claims resurrected, all ADRs "
          "registered, every requirement defined and traced, "
          "every PRD amendment reachable from the PRD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
