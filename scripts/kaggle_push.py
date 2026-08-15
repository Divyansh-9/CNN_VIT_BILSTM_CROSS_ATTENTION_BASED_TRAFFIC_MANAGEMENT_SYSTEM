"""Push the dataset and training notebook to Kaggle (S11, ADR-013 rev 2).

    python scripts/kaggle_push.py --check      # credentials + what would happen
    python scripts/kaggle_push.py --dataset    # upload data/idd_yolo (959 MB)
    python scripts/kaggle_push.py --kernel     # push the notebook

**Why the API rather than clicking through the browser.** A browser session is
not reproducible, breaks whenever Kaggle changes its UI, and leaves no record of
what was uploaded. This is one command, it is versioned in the repository, and it
can be re-run by anyone from a clean machine — which is NFR-08, not a preference.

**Credentials — three ways, and the first is easiest.** The Kaggle CLI has moved
past the old `kaggle.json` convention:

    kaggle auth login              OAuth in a browser, cached locally. No file
                                   to manage, and nothing secret on disk to leak
    KAGGLE_API_TOKEN=...           environment variable
    ~/.kaggle/access_token         token file
    ~/.kaggle/kaggle.json          the legacy pair, still honoured

Whichever is used, **this script never reads, prints or commits a credential** —
it only checks that one is present. `kaggle auth login` is recommended precisely
because it leaves no secret in the repository's blast radius.

**Nothing here deletes anything on Kaggle.** Dataset and kernel pushes create a
new *version*; previous versions stay visible in the Kaggle UI, so the run
history is auditable rather than overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path("kaggle/detector_training")
DATA = Path("data/idd_yolo")
KAGGLE_DIR = Path.home() / ".kaggle"
CREDENTIAL_PATHS = (KAGGLE_DIR / "kaggle.json", KAGGLE_DIR / "access_token")


def credentials_present() -> tuple[bool, str]:
    """Any of the four accepted mechanisms. Never reads the contents."""
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True, "KAGGLE_API_TOKEN environment variable"
    for path in CREDENTIAL_PATHS:
        if path.exists():
            return True, str(path)
    # OAuth caches under a platform directory that varies; probe the CLI rather
    # than guessing a path that would be wrong on some machines.
    try:
        probe = subprocess.run(
            [sys.executable, "-m", "kaggle", "datasets", "list", "-m"],
            capture_output=True, text=True, timeout=60,
        )
        if probe.returncode == 0:
            return True, "cached OAuth session (kaggle auth login)"
    except Exception:                                        # noqa: BLE001
        pass
    return False, ""


def check() -> int:
    ok = True

    present, how = credentials_present()
    if present:
        print(f"  credentials  OK  ({how})")
    else:
        ok = False
        print("  credentials  MISSING")
        print("     Easiest, and leaves no secret on disk:")
        print("         python -m kaggle auth login")
        print("     Or generate a token at https://www.kaggle.com/settings/api")
        print("     and save it to ~/.kaggle/access_token")

    try:
        import kaggle  # noqa: F401
        print("  kaggle api   OK")
    except ImportError:
        ok = False
        print("  kaggle api   MISSING — pip install kaggle")
    except OSError:
        print("  kaggle api   installed (not authenticated yet — expected)")

    if DATA.exists():
        images = sum(1 for _ in DATA.rglob("*.jpg"))
        size = sum(p.stat().st_size for p in DATA.rglob("*")) / 1e9
        print(f"  dataset      OK  {images:,} images, {size:.2f} GB")
    else:
        ok = False
        print(f"  dataset      MISSING  {DATA}")
        print("     Build it: python scripts/prepare_idd.py --count 8000 --copy-images")

    for name in ("dataset-metadata.json", "kernel-metadata.json",
                 "s11_train_detector.ipynb"):
        path = HERE / name
        print(f"  {name:<28} {'OK' if path.exists() else 'MISSING'}")
        ok &= path.exists()

    if ok:
        kernel = json.loads((HERE / "kernel-metadata.json").read_text(encoding="utf-8"))
        dataset = json.loads((HERE / "dataset-metadata.json").read_text(encoding="utf-8"))
        print(f"\n  would create dataset  {dataset['id']}")
        print(f"  would create notebook {kernel['id']}")
        print(f"  notebook title        {kernel['title']}")
        print(f"  gpu {kernel['enable_gpu']}   private {kernel['is_private']}")
    return 0 if ok else 1


def run(command: list[str], cwd: Path | None = None) -> int:
    print("  $ " + " ".join(command))
    result = subprocess.run(command, cwd=cwd)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dataset", action="store_true")
    parser.add_argument("--kernel", action="store_true")
    parser.add_argument("--message", default="S11 detector bootstrap")
    args = parser.parse_args(argv)

    if not (args.dataset or args.kernel):
        return check()

    present, _ = credentials_present()
    if not present:
        print("not authenticated — run --check for the one-time setup", file=sys.stderr)
        return 2

    python = sys.executable
    if args.dataset:
        # Metadata must sit beside the files Kaggle uploads.
        target = DATA / "dataset-metadata.json"
        target.write_text(
            (HERE / "dataset-metadata.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        listing = subprocess.run(
            [python, "-m", "kaggle", "datasets", "list", "-m"],
            capture_output=True, text=True,
        )
        exists = "indiatrafficnet-bootstrap-idd-yolo" in (listing.stdout or "")
        verb = ["version", "-m", args.message, "-d"] if exists else ["create", "-r", "zip"]
        code = run([python, "-m", "kaggle", "datasets", *verb, "-p", str(DATA)])
        if code:
            return code
        print("  dataset pushed. A NEW VERSION — earlier ones stay on Kaggle.")

    if args.kernel:
        code = run([python, "-m", "kaggle", "kernels", "push", "-p", str(HERE)])
        if code:
            return code
        kernel = json.loads((HERE / "kernel-metadata.json").read_text(encoding="utf-8"))
        print(f"  notebook pushed: https://www.kaggle.com/code/{kernel['id']}")
        print("  Open it, confirm the GPU is on, and Run All.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
