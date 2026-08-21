"""Print UTF-8 whatever the console claims it can render (P50).

A cache build died after four of seven clips with

    UnicodeEncodeError: 'charmap' codec can't encode character '\u0964'

on this filename:

    Pov_Thursday Traffic From Footover bridge। Cloudy Seen।.mp4

`।` is the Devanagari danda, and it is in the name because the footage is from
Dhaka. Python picks the console's own encoding for `sys.stdout`, which is
cp1252 on this machine, and cp1252 cannot represent it — so a **progress line**
raised and took twenty minutes of GPU work with it.

Nothing was wrong with the data. The clip decoded, both backbones ran, the
features were written; the process then died describing what it had just done.
A corpus of Indian and Bangladeshi traffic footage will keep containing
Devanagari, Bengali and emoji in filenames, so this cannot be handled by
renaming files.

`PYTHONIOENCODING=utf-8` fixes it too, and that is the trap: it fixes it for
whoever remembers, which is why the failure only appeared once a script ran
unattended. A script has to survive its own output without an environment
variable set for it.

`errors="replace"` rather than `strict`: a console that genuinely cannot render
a glyph should show `?` and keep going. Losing a run to an unprintable
character in a log line is never the right trade.
"""

from __future__ import annotations

import sys

__all__ = ["use_utf8"]


def use_utf8() -> None:
    """Make stdout and stderr UTF-8 tolerant. Idempotent, and never raises."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue  # a pipe or a captured buffer; nothing to do
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Detached or already-closed stream. Printing is not worth an
            # exception here either.
            pass
