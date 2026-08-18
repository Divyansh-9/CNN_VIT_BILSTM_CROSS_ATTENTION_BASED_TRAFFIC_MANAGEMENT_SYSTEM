"""Writing result CSVs without destroying the ones already there.

Every experiment script in this project takes `--regime` and writes a fixed
filename in `"w"` mode. That combination means the second regime silently
deletes the first, and the deleted rows are a graded reproducibility artifact
(NFR-09) that costs tens of minutes of simulation to regenerate.

The hazard was found in `benchmark.py`, but it was never specific to it —
`webster_sweep.py` and `screen_action_space.py` have the same shape. So the fix
lives here rather than in one script, and the next experiment that takes a
`--regime` gets it by using this module.

Result CSVs are written by the script that produced them and never transcribed
(NFR-09/10). Nothing here edits values; it only decides which rows survive.
"""

from __future__ import annotations

import csv
from pathlib import Path

__all__ = ["merge_by_key", "write_rows"]


def merge_by_key(
    path: Path,
    rows: list[dict],
    value: str,
    *,
    key: str = "regime",
    quiet: bool = False,
) -> Path:
    """Replace rows where `row[key] == value`; leave every other value alone.

    Replacing rather than appending is deliberate. Re-running an experiment must
    supersede the previous run of it, not leave two contradictory copies in one
    file for a reader to choose between — and the reader in question is a
    examiner reading a committed CSV, with no way to tell which is current.

    A file whose rows lack `key` is refused rather than merged. It predates the
    distinction, so combining it with keyed rows produces a table where some
    rows are attributable and others are not, which is worse than either input.
    """
    if not rows:
        raise ValueError(f"refusing to write {path} with no rows")

    existing: list[dict] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            on_disk = list(csv.DictReader(handle))
        if on_disk and any(not row.get(key) for row in on_disk):
            raise SystemExit(
                f"{path} has rows with no '{key}'. Refusing to merge — the file "
                f"predates {key} tracking, and mixing it with keyed rows would "
                f"produce a table nobody can attribute. Move it aside first."
            )
        existing = [row for row in on_disk if row[key] != value]

    combined = existing + [dict(row) for row in rows]
    write_rows(path, combined, order_from=rows[0])

    kept = sorted({row[key] for row in existing})
    if kept and not quiet:
        print(f"  {path.name}: kept {len(existing)} row(s) from "
              f"{', '.join(kept)}; replaced {value}")
    return path


def write_rows(path: Path, rows: list[dict], *, order_from: dict | None = None) -> Path:
    """Write `rows` as CSV, keeping a stable column order.

    Columns are taken from `order_from` first so a file's leading columns do not
    reshuffle between runs — a diff that reorders every column hides the one
    value that actually changed. Fields present on only some rows are appended
    in sorted order and blank-filled, because Webster contributes `clamp_rate`
    and the classical controllers do not.
    """
    if not rows:
        raise ValueError(f"refusing to write {path} with no rows")

    fields = list(order_from or rows[0])
    fields += sorted({k for row in rows for k in row} - set(fields))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path
