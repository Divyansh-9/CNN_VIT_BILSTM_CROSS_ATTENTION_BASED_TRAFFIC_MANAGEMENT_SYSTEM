"""Every third-party import must be pinned in requirements.txt (NFR-08).

P18 found six packages the code imported and `requirements.txt` did not list.
All six were **lazy imports inside functions**, which is why the gap survived:
nothing fails at startup, so nothing fails until the day someone reproduces the
project on a clean machine — which is the exact scenario NFR-08 is graded on.

A one-off audit does not hold. The next lazy import reopens the gap, and it
reopens silently. This test is the audit made permanent: it walks the AST of
every source file, resolves each top-level import, and fails on anything
third-party that `requirements.txt` does not pin.

It reads the source rather than the installed environment on purpose. A test
that checked `pip list` would pass on the developer's machine — the one place
the answer is already known — and say nothing about a clean checkout.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCE_DIRS = (
    "mfstnet", "scripts", "simulation", "tests", "detection",
    "server", "edge", "contracts", "indiatrafficnet", "experiments",
)

# Distribution name on PyPI -> module name it installs. Only needed where they
# differ; a pinned line reads as the distribution, an import reads as the module.
DISTRIBUTION_TO_MODULE = {
    "opencv-python-headless": "cv2",
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
    "python-dotenv": "dotenv",
    "paho-mqtt": "paho",
    "pytest-cov": "pytest_cov",
    "stable-baselines3": "stable_baselines3",
    "yt-dlp": "yt_dlp",
    "imageio-ffmpeg": "imageio_ffmpeg",
    "huggingface-hub": "huggingface_hub",
}

# The eclipse-sumo wheel installs several top-level modules under one pin.
BUNDLED = {"eclipse-sumo": {"sumo", "sumolib", "traci", "libsumo"}}

# torch and torchvision are installed from the PyTorch CUDA index before
# requirements.txt is applied, and requirements.txt says so at the top. Pinning
# them there would pull the CPU-only wheel — the defect that comment records.
INSTALLED_SEPARATELY = {"torch", "torchvision"}


def local_top_level_names() -> set[str]:
    """Top-level modules and packages that live in this repository.

    Derived from the filesystem rather than hardcoded: a hardcoded list goes
    stale the first time a directory is added, and it goes stale by making this
    test pass when it should fail.
    """
    names = {p.name for p in ROOT.iterdir() if p.is_dir()
             and not p.name.startswith((".", "_"))}
    names |= {p.stem for p in ROOT.glob("*.py")}
    return names


def imported_modules() -> dict[str, set[str]]:
    """Top-level module name -> the files that import it."""
    found: dict[str, set[str]] = {}
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for file in base.rglob("*.py"):
            if "__pycache__" in file.parts:
                continue
            try:
                tree = ast.parse(file.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
                pytest.fail(f"{file} does not parse")
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        found.setdefault(name.name.split(".")[0], set()).add(
                            str(file.relative_to(ROOT)))
                elif isinstance(node, ast.ImportFrom):
                    # level > 0 is a relative import, which is always local.
                    if node.level == 0 and node.module:
                        found.setdefault(node.module.split(".")[0], set()).add(
                            str(file.relative_to(ROOT)))
    return found


def pinned_modules() -> set[str]:
    """Module names reachable from the pins in requirements.txt."""
    modules: set[str] = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        distribution = re.split(r"[><=!\[;]", line)[0].strip()
        modules |= BUNDLED.get(distribution, set())
        modules.add(DISTRIBUTION_TO_MODULE.get(
            distribution, distribution.replace("-", "_")))
    return modules


def third_party_imports() -> dict[str, set[str]]:
    stdlib = set(sys.stdlib_module_names)
    local = local_top_level_names()
    return {module: files for module, files in imported_modules().items()
            if module not in stdlib and module not in local}


def test_requirements_txt_exists_and_pins_something():
    assert (ROOT / "requirements.txt").exists(), "NFR-08 requires this file"
    assert len(pinned_modules()) > 10


def test_every_imported_package_is_pinned():
    """The check P18 ran by hand, run on every commit instead."""
    pinned = pinned_modules() | INSTALLED_SEPARATELY
    unpinned = {module: files for module, files
                in third_party_imports().items() if module not in pinned}

    if unpinned:
        detail = "\n".join(
            f"  {module:<22} imported by {', '.join(sorted(files)[:3])}"
            for module, files in sorted(unpinned.items()))
        pytest.fail(
            f"{len(unpinned)} package(s) imported but not pinned in "
            f"requirements.txt:\n{detail}\n\n"
            f"A clean-machine reproduction fails on these (NFR-08). Add the "
            f"pinned line in the same commit as the import. If a name here is "
            f"a local module, it belongs in the repository root so this test "
            f"can see it; if the distribution name differs from the module "
            f"name, add it to DISTRIBUTION_TO_MODULE."
        )


def test_lazy_imports_are_covered_too():
    """The six P18 found were all inside functions, not at module top level.

    `ast.walk` descends into function bodies, so they are caught. This asserts
    that property directly, because a future refactor to top-level-only
    scanning would reintroduce exactly the gap P18 closed and every other test
    here would still pass.
    """
    imports = imported_modules()
    assert "yt_dlp" in imports, "lazy import inside a function was not detected"
    assert any("capture_stream" in f for f in imports["yt_dlp"])


def test_torch_is_documented_as_installed_separately():
    """torch is deliberately absent from the pins. That is only defensible
    while the file explains why — otherwise it reads as the same defect P18
    found, and someone will 'fix' it by adding a pin that installs the
    CPU-only wheel."""
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "download.pytorch.org" in text
    assert "torch==" in text, "the exact install command must be in the file"


# ------------------------------------------- the file against reality (P30) --

def requirement_lines() -> list[tuple[str, str, str]]:
    """`(distribution, operator, version)` for every active requirement."""
    out = []
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*([=<>!~]+)\s*(\S+)", line)
        assert match, f"unparseable requirement line: {raw!r}"
        out.append((match.group(1), match.group(3), match.group(4)))
    return out


def test_every_requirement_is_pinned_not_ranged():
    """The file's own first paragraph: "Versions are PINNED, not ranged. A range
    that resolves differently in November than it did in August breaks
    reproducibility silently."

    On 2026-08-20 that paragraph sat above 21 ranged lines out of 35. A stated
    rule nobody checks is a comment, and NFR-08 is graded.
    """
    ranged = [f"{name}{op}{version}"
              for name, op, version in requirement_lines() if op != "=="]
    assert not ranged, (
        f"{len(ranged)} requirement(s) use a range rather than a pin: "
        f"{', '.join(ranged)}. The header of requirements.txt forbids this."
    )


def test_no_package_is_listed_twice():
    """xgboost was listed twice, identically, on consecutive lines."""
    names = [name.lower() for name, _, _ in requirement_lines()]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    assert not duplicated, f"listed more than once: {', '.join(duplicated)}"


def test_pins_match_what_is_installed():
    """The direction the original audit missed.

    P18 checked imports against requirements and called NFR-08 met. It never
    checked requirements against the environment — and every one of the seven
    pinned-and-installed packages disagreed with its pin: stable-baselines3
    declared ==2.3.2 against 2.9.0 installed, SUMO ==1.19.0 against 1.27.1.
    A clean machine would have built a different stack from this one, which is
    precisely what the requirement forbids.

    Skips anything not installed here, so the test still means something in CI
    and on a partial checkout. `test_every_imported_package_is_pinned` is what
    catches a missing dependency; this catches a lying one.
    """
    from importlib.metadata import PackageNotFoundError, version as installed_version

    wrong = []
    for name, op, declared in requirement_lines():
        if op != "==":
            continue                      # the ranged test above owns this
        try:
            actual = installed_version(name)
        except PackageNotFoundError:
            continue                      # not installed here; nothing to compare
        # A local build carries a platform suffix the pin will not have.
        if actual.split("+")[0] != declared.split("+")[0]:
            wrong.append(f"{name}: pinned {declared}, installed {actual}")

    assert not wrong, (
        f"{len(wrong)} pin(s) do not match the installed environment:\n  "
        + "\n  ".join(wrong)
        + "\nA pin nobody has run is a guess. Update the pin, or install the "
          "version the pin names."
    )
