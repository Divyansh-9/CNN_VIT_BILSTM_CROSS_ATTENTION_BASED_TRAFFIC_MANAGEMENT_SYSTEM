"""Push the dataset and training notebook to Kaggle (S11, ADR-013 rev 2).

    python scripts/kaggle_push.py --check      # credentials + what would happen
    python scripts/kaggle_push.py --dataset    # upload data/idd_yolo (959 MB)
    python scripts/kaggle_push.py --kernel     # push the notebook

    python scripts/kaggle_push.py --kernel --dir kaggle/joint_training   # S14

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

**`kernels push` cannot choose the GPU, and the default is unusable.**
`kernel-metadata.json` has `enable_gpu` but no field for the accelerator *type*,
and `machine_shape: "Gpu"` does not select one either. A pushed kernel lands on
a **P100**, which is `sm_60`; current PyTorch builds start at `sm_70`, so the
card is not slow — it cannot run at all.

Measured twice now, most recently on S16: version 1 failed after 23.9 s with
`INCOMPATIBLE GPU sm_60`. The first cell of every training notebook checks the
architecture against `torch.cuda.get_arch_list()` and exits immediately, which
is the difference between losing twenty seconds and losing an hour of the
thirty-hour weekly quota.

**After pushing, the accelerator must be set to GPU T4 x2 in the notebook
editor** (Session options -> Accelerator), and a confirmation dialog has to be
accepted. Then Save Version -> Save & Run All. There is no API route to it.

**Nothing here deletes anything on Kaggle.** Dataset and kernel pushes create a
new *version*; previous versions stay visible in the Kaggle UI, so the run
history is auditable rather than overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_KERNEL_DIR = Path("kaggle/detector_training")
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


def check(here: Path = DEFAULT_KERNEL_DIR) -> int:
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

    print(f"\n  kernel dir   {here}")
    metadata = here / "kernel-metadata.json"
    if not metadata.exists():
        print(f"  kernel-metadata.json         MISSING in {here}")
        return 1
    kernel = json.loads(metadata.read_text(encoding="utf-8"))

    notebook = here / kernel["code_file"]
    print(f"  {kernel['code_file']:<28} {'OK' if notebook.exists() else 'MISSING'}")
    ok &= notebook.exists()

    # Kaggle derives the kernel slug from the TITLE. A title that slugifies to
    # anything else creates a SECOND notebook instead of versioning this one,
    # which is how a run history quietly forks. Cost six versions to learn once.
    slug = re.sub(r"[^a-z0-9]+", "-", kernel["title"].lower()).strip("-")
    expected = kernel["id"].split("/")[-1]
    if slug != expected:
        ok = False
        print(f"  TITLE SLUG MISMATCH  {slug!r} != {expected!r}")
        print("     Kaggle would create a NEW notebook, not a new version.")

    print(f"\n  would push notebook   {kernel['id']}")
    print(f"  notebook title        {kernel['title']}")
    print(f"  gpu {kernel['enable_gpu']}   private {kernel['is_private']}")
    print(f"  datasets              {kernel.get('dataset_sources') or 'none'}")
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
    parser.add_argument("--dir", type=Path, default=DEFAULT_KERNEL_DIR,
                        help="notebook directory (kaggle/joint_training for S14)")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="dataset directory to push. Defaults to data/idd_yolo. "
                             "Must already contain its own dataset-metadata.json "
                             "— the slug lives with the data, not in this script")
    args = parser.parse_args(argv)

    if not (args.dataset or args.kernel):
        return check(args.dir)

    present, _ = credentials_present()
    if not present:
        print("not authenticated — run --check for the one-time setup", file=sys.stderr)
        return 2

    python = sys.executable
    if args.dataset:
        data_dir = args.data_dir or DATA
        # Metadata must sit beside the files Kaggle uploads. A directory that
        # brought its own is pushed as-is; only the legacy IDD path inherits
        # the template, because its slug predates this option.
        target = data_dir / "dataset-metadata.json"
        if not target.is_file():
            if data_dir != DATA:
                raise SystemExit(
                    f"{target} is missing. A dataset directory carries its own "
                    f"slug and title so that pushing the wrong one is not a "
                    f"silent overwrite of somebody else's dataset."
                )
            target.write_text(
                (DEFAULT_KERNEL_DIR / "dataset-metadata.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        slug = json.loads(target.read_text(encoding="utf-8"))["id"].split("/")[-1]
        listing = subprocess.run(
            [python, "-m", "kaggle", "datasets", "list", "-m"],
            capture_output=True, text=True,
        )
        exists = slug in (listing.stdout or "")
        verb = ["version", "-m", args.message, "-d"] if exists else ["create", "-r", "zip"]
        print(f"  {'new version of' if exists else 'creating'} {slug} from {data_dir}")
        code = run([python, "-m", "kaggle", "datasets", *verb, "-p", str(data_dir)])
        if code:
            return code
        print("  dataset pushed. A NEW VERSION — earlier ones stay on Kaggle.")

    if args.kernel:
        code = run([python, "-m", "kaggle", "kernels", "push", "-p", str(args.dir)])
        if code:
            return code
        kernel = json.loads(
            (args.dir / "kernel-metadata.json").read_text(encoding="utf-8")
        )
        print(f"  notebook pushed: https://www.kaggle.com/code/{kernel['id']}")
        print("  Open it, confirm the GPU is on, and Run All.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
