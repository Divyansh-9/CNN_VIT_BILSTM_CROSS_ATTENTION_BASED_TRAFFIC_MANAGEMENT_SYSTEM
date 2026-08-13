"""Locate the SUMO binaries, wherever they came from (S32).

SUMO can arrive three ways and the project must not care which:

* `pip install eclipse-sumo` — binaries ship **inside the wheel**, at
  `site-packages/sumo/bin/`, and are **not** placed on PATH. This is the ₹0
  route and the one CI uses.
* a system install — binaries on PATH, `SUMO_HOME` usually set.
* a manual unpack — `SUMO_HOME` set, PATH not.

`traci` and `sumolib` need `SUMO_HOME` to find their data files, so this module
sets it as a side effect of finding the binaries. Leaving that to a README step
is how a teammate loses an afternoon to an error message that says nothing about
an environment variable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

__all__ = ["SumoNotFound", "sumo_home", "sumo_binary", "sumo_version", "ensure_sumo_home"]


class SumoNotFound(RuntimeError):
    """SUMO is not installed anywhere this module knows to look."""


@lru_cache(maxsize=1)
def sumo_home() -> Path:
    """The SUMO installation root. Checks the pip wheel before PATH.

    The wheel is checked first deliberately: if someone has both, the pip one is
    the version pinned in `requirements.txt`, and a mismatched system SUMO is
    exactly the kind of difference that makes a result irreproducible on another
    machine (NFR-08).
    """
    try:
        import sumo  # the eclipse-sumo wheel

        root = Path(sumo.__file__).parent
        if (root / "bin").is_dir():
            return root
    except ImportError:
        pass

    if (env := os.environ.get("SUMO_HOME")) and Path(env).is_dir():
        return Path(env)

    if found := shutil.which("sumo"):
        # .../bin/sumo -> the root is its grandparent
        return Path(found).resolve().parent.parent

    raise SumoNotFound(
        "SUMO not found. Install it into the project's environment with:\n"
        "    pip install eclipse-sumo traci sumolib\n"
        "That ships the binaries inside the wheel and needs no system package "
        "and no administrator rights, which is why it is the documented route."
    )


def ensure_sumo_home() -> Path:
    """Set `SUMO_HOME` in this process if it is not already correct.

    `traci` and `sumolib` read it at import time for their data files, so this
    must run before they are used.
    """
    root = sumo_home()
    if os.environ.get("SUMO_HOME") != str(root):
        os.environ["SUMO_HOME"] = str(root)
    return root


def sumo_binary(name: str = "sumo") -> Path:
    """Absolute path to `sumo`, `sumo-gui`, `netconvert`, ...

    Returned as a path rather than a bare name so callers never depend on PATH.
    """
    root = ensure_sumo_home()
    for candidate in (root / "bin" / name, root / "bin" / f"{name}.exe"):
        if candidate.exists():
            return candidate

    if found := shutil.which(name):
        return Path(found)

    available = sorted(
        p.stem for p in (root / "bin").glob("*")
        if p.suffix in ("", ".exe") and p.is_file()
    )
    raise SumoNotFound(
        f"{name!r} not found under {root / 'bin'}. Available: {available[:12]}"
    )


def sumo_version() -> str:
    """Recorded in the experiment record — a SUMO upgrade can move results."""
    out = subprocess.run(
        [str(sumo_binary("sumo")), "--version"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.splitlines()[0].strip()
