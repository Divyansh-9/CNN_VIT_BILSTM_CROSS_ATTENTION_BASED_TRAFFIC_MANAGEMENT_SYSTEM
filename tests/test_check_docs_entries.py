"""check_docs.py: every D entry in the changelog has exactly one heading (D45)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_docs import d_entry_problems  # noqa: E402


def log(*headings: str) -> str:
    return "\n".join(f"{h}\n\nbody\n" for h in headings)


def test_a_complete_run_with_a_combined_heading_passes():
    assert d_entry_problems(log("## D3 — c (x)", "## D1–D2 — a and b (x)", "### D1 — a detail")) == []


def test_a_heading_replaced_by_the_next_entry_is_caught():
    """D45's first defect: D43's text inserted in place of D42's heading."""
    assert d_entry_problems(log("## D43 — new (x)", "## D41 — older (x)", "## D1–D40 — rest (x)")) == ["changelog  D42 has no heading"]


def test_entries_missing_from_a_split_commit_are_caught():
    """D45's second defect: CLAUDE.md said D1–D44 while the changelog stopped at D39."""
    problems = d_entry_problems(log("## D44 — newest (x)", "## D1–D39 — rest (x)"))
    assert problems == [f"changelog  D{n} has no heading" for n in range(40, 44)]


def test_a_duplicate_heading_is_caught():
    assert d_entry_problems(log("## D2 — b (x)", "## D2 — b again (x)", "## D1 — a (x)")) == ["changelog  D2 has 2 headings"]


def test_the_real_changelog_passes():
    text = (ROOT / "docs" / "00-planning" / "PRD-CHANGELOG.md").read_text(encoding="utf-8")
    assert d_entry_problems(text) == []


def test_a_changelog_that_stops_short_of_claude_md_is_caught():
    """D45's second defect, as it shipped: CLAUDE.md said D1–D44, the changelog stopped at D39."""
    from scripts.check_docs import d_range_problem

    shipped = log("## D39 — newest there (x)", "## D1–D38 — rest (x)")
    assert d_range_problem(shipped, "running to P143, with `D<n>` entries (D1–D44) for") == (
        "changelog  CLAUDE.md says D1–D44, but the changelog's newest D entry is D39")
    assert d_range_problem(shipped, "entries (D1–D39) for") is None


def test_the_real_changelog_matches_claude_md():
    from scripts.check_docs import d_range_problem

    text = (ROOT / "docs" / "00-planning" / "PRD-CHANGELOG.md").read_text(encoding="utf-8")
    assert d_range_problem(text, (ROOT / "CLAUDE.md").read_text(encoding="utf-8")) is None
