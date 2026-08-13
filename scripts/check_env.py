"""Pre-flight environment check. Run this BEFORE `pip install -r requirements.txt`.

Uses only the standard library for the checks that must work on a bare
interpreter, so it runs before anything is installed.

    python scripts/check_env.py

Exists because the failures it catches are the confusing kind -- a wrong Python
version surfaces as "no matching distribution found for torch==2.3.1", which
sends people hunting for a network problem.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# torch 2.3.1 publishes wheels for CPython 3.8-3.12 only.
MIN_PY = (3, 10)
MAX_PY = (3, 14)   # torch 2.13 supports 3.14 (corrected 2026-08-13)
RECOMMENDED = "3.11 or 3.14"

OK, WARN, FAIL = "  OK  ", " WARN ", " FAIL "
_problems: list[str] = []


def report(status: str, name: str, detail: str = "") -> None:
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if status is FAIL:
        _problems.append(name)


def check_python() -> None:
    v = sys.version_info
    got = f"{v.major}.{v.minor}.{v.micro}"
    if MIN_PY <= (v.major, v.minor) <= MAX_PY:
        report(OK, "Python version", got)
        return
    report(
        FAIL,
        "Python version",
        f"{got} -- need {MIN_PY[0]}.{MIN_PY[1]}-{MAX_PY[0]}.{MAX_PY[1]} "
        f"(recommended {RECOMMENDED}). PyTorch 2.3.1 publishes no wheels for "
        f"{v.major}.{v.minor}; pip will report 'no matching distribution' and "
        f"the cause will not be obvious. Install Python {RECOMMENDED} and build "
        f"the venv with it: py -{RECOMMENDED} -m venv .venv",
    )


def check_venv() -> None:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if in_venv:
        report(OK, "Virtual environment", sys.prefix)
    else:
        report(
            WARN,
            "Virtual environment",
            "not active -- installing into the system interpreter makes "
            "NFR-08 clean-machine reproduction unverifiable",
        )


def check_torch() -> None:
    try:
        import torch
    except ImportError:
        report(WARN, "PyTorch", "not installed yet (expected before setup)")
        return

    report(OK, "PyTorch", torch.__version__)
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        report(OK, "CUDA", f"{name}, {vram:.1f} GB")
        if vram < 7:
            report(
                WARN,
                "VRAM",
                f"{vram:.1f} GB -- uncached MFSTNet at batch 32 x T=60 pushes "
                "1,920 frames through both backbones and will not fit. Use the "
                "feature cache (ADR-005); it is the intended path anyway",
            )
        if torch.cuda.is_bf16_supported():
            report(OK, "bf16", "supported -- use it (ADR-007 §4)")
    else:
        report(
            WARN,
            "CUDA",
            "unavailable -- CPU-only torch wheel? Reinstall from "
            "--index-url https://download.pytorch.org/whl/cu121",
        )


def check_packages() -> None:
    for mod, label in [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("ultralytics", "Ultralytics"),
        ("stable_baselines3", "Stable-Baselines3"),
        ("traci", "TraCI"),
        ("onnxruntime", "ONNX Runtime"),
        ("shapely", "Shapely"),
    ]:
        try:
            m = __import__(mod)
            report(OK, label, getattr(m, "__version__", "installed"))
        except ImportError:
            report(WARN, label, "not installed")


def check_git_lfs() -> None:
    if shutil.which("git-lfs") or shutil.which("git"):
        try:
            out = subprocess.run(
                ["git", "lfs", "version"], capture_output=True, text=True, timeout=10
            )
            if out.returncode == 0:
                report(OK, "Git LFS", out.stdout.strip().split(";")[0])
                return
        except (OSError, subprocess.SubprocessError):
            pass
    report(FAIL, "Git LFS", "not available -- model weights cannot be committed")


def check_disk() -> None:
    free = shutil.disk_usage(Path.cwd()).free / 1024**3
    # IDD ~23 GB + converted subset ~4 GB + feature cache ~3 GB + frames + slack
    if free >= 60:
        report(OK, "Free disk", f"{free:.0f} GB")
    elif free >= 40:
        report(WARN, "Free disk", f"{free:.0f} GB -- tight; IDD alone is 22.8 GB")
    else:
        report(FAIL, "Free disk", f"{free:.0f} GB -- need ~60 GB for IDD + cache")


def main() -> int:
    print("MFSTNet environment pre-flight\n" + "-" * 34)
    check_python()
    check_venv()
    check_git_lfs()
    check_disk()
    check_torch()
    check_packages()
    print("-" * 34)
    if _problems:
        print(f"BLOCKED by: {', '.join(_problems)}")
        print("Fix these before continuing with Execution Manual Part 0.")
        return 1
    print("No blockers. Continue with Execution Manual Part 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
