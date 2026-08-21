"""A filename must not be able to kill a run (P50).

The footage this project uses is Indian and Bangladeshi, so its filenames carry
Devanagari, Bengali and emoji. On a cp1252 console Python raises when asked to
print any of them, and a cache build died after four of seven clips inside a
progress line -- after the work it was describing had already succeeded.

The control test is the important half: it shows the failure is real and that
`use_utf8` is what prevents it, rather than the character having become
printable for some unrelated reason.
"""

from __future__ import annotations

import os
import subprocess
import sys

DANDA = "Pov_Thursday Traffic From Footover bridge। Cloudy Seen।.mp4"
EMOJI = "🎧 Incredible traffic Sound in Dhaka, Bangladesh। Rampura.mp4"


def run_printing(name: str, *, configure: bool) -> subprocess.CompletedProcess:
    setup = ("import sys; sys.path.insert(0, '.'); "
             "from scripts.console import use_utf8; use_utf8(); "
             if configure else "")
    environment = dict(os.environ, PYTHONIOENCODING="cp1252")
    return subprocess.run(
        [sys.executable, "-c", setup + f"print({name!r})"],
        capture_output=True, text=True, encoding="utf-8", env=environment,
    )


def test_devanagari_danda_kills_an_unconfigured_script():
    """The control. Without the fix this is a crash, not a mangled character."""
    result = run_printing(DANDA, configure=False)
    assert result.returncode != 0
    assert "UnicodeEncodeError" in result.stderr


def test_use_utf8_lets_the_same_name_print():
    result = run_printing(DANDA, configure=True)
    assert result.returncode == 0, result.stderr
    assert "Footover" in result.stdout


def test_emoji_in_a_clip_name_prints_too():
    result = run_printing(EMOJI, configure=True)
    assert result.returncode == 0, result.stderr


def test_use_utf8_is_idempotent():
    from scripts.console import use_utf8

    use_utf8()
    use_utf8()


def test_use_utf8_survives_a_stream_with_no_reconfigure(monkeypatch):
    """Under pytest's capture, stdout may be a plain buffer. Never raise."""
    import io

    from scripts import console

    monkeypatch.setattr(console.sys, "stdout", io.StringIO())
    monkeypatch.setattr(console.sys, "stderr", io.StringIO())
    console.use_utf8()


def test_every_script_that_prints_clip_names_configures_the_console():
    """The fix is only worth anything if the unattended scripts carry it."""
    import pathlib

    required = ("build_cache.py", "build_corpus.py", "audit_corpus.py",
                "resplit_corpus.py", "corpus_yield.py", "relabel_corpus.py",
                "train_mfstnet.py", "survey_all.py", "triage_footage.py")
    missing = [name for name in required
               if "use_utf8()" not in
               (pathlib.Path("scripts") / name).read_text(encoding="utf-8")]
    assert not missing, f"these can still die on a filename: {missing}"
