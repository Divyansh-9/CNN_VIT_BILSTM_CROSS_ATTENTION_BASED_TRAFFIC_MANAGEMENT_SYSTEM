"""Back up the model artifacts git does not hold, and verify any copy (S61, P90).

    python scripts/backup_models.py manifest            # write the committed fingerprints
    python scripts/backup_models.py pack --dest E:/stms-backup
    python scripts/backup_models.py verify --dest E:/stms-backup

`models/` is gitignored on purpose: ADR-013 publishes weights on Hugging Face,
not in git. Until they are published, the S61 checkpoints and the verified
ONNX graph exist on one laptop with one physical disk, and a disk failure
loses them. A fingerprint in the repository proves which file is the right
one; it cannot recover the file.

So this does three things. `manifest` writes the sha256 of every artifact to
`experiments/results/model_artifacts.sha256`, which IS committed. `pack`
copies the artifacts and the manifest to a destination — an external drive or a
synced cloud folder, never another partition of the same disk. `verify`
re-hashes a copy against the committed manifest, so a backup is checked rather
than assumed.

What is covered: every checkpoint and its sidecar under `models/mfstnet/`, and
every exported graph under `models/onnx/` **with its external `.onnx.data`
weights file** (P90 — the graph file alone does not contain the weights).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ("models/mfstnet", "models/onnx")
MANIFEST = ROOT / "experiments" / "results" / "model_artifacts.sha256"


def artifacts() -> list[Path]:
    found = []
    for source in SOURCES:
        base = ROOT / source
        if base.is_dir():
            found += sorted(p for p in base.rglob("*") if p.is_file())
    return found


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split("  ", 1)
            entries[name] = digest
    return entries


def write_manifest() -> int:
    files = artifacts()
    if not files:
        raise SystemExit("no artifacts under models/ to fingerprint")
    lines = ["# sha256 of every model artifact git does not hold "
             "(scripts/backup_models.py). Paths relative to the repository."]
    lines += [f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}" for p in files]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in files) / 2**20
    print(f"  {len(files)} file(s), {size:.0f} MB -> {MANIFEST.relative_to(ROOT)}")
    return 0


def same_physical_disk(dest: Path) -> bool:
    """True when the destination is on the repository's own drive letter.
    A conservative check: two partitions of one disk also defeat a backup,
    and that case is named in the warning below rather than detected."""
    return dest.resolve().drive.lower() == ROOT.resolve().drive.lower()


def pack(dest: Path) -> int:
    manifest = read_manifest(MANIFEST)
    if same_physical_disk(dest):
        raise SystemExit(
            f"{dest} is on the repository's own drive. A backup on the same "
            f"disk dies with it. Use an external drive or a synced cloud folder.")
    print(f"  NOTE  this laptop has one physical disk; C: and D: are partitions "
          f"of it. Neither is a backup destination for the other.")
    for name in manifest:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    shutil.copy2(MANIFEST, dest / MANIFEST.name)
    print(f"  copied {len(manifest)} file(s) to {dest}")
    return verify(dest)


def verify(dest: Path) -> int:
    manifest = read_manifest(MANIFEST)
    missing = [n for n in manifest if not (dest / n).is_file()]
    wrong = [n for n in manifest
             if (dest / n).is_file() and sha256(dest / n) != manifest[n]]
    if missing or wrong:
        for name in missing:
            print(f"  MISSING   {name}")
        for name in wrong:
            print(f"  MISMATCH  {name}")
        print(f"\n  FAIL  {len(missing)} missing, {len(wrong)} not matching the "
              f"committed manifest")
        return 1
    print(f"  PASS  all {len(manifest)} file(s) at {dest} match the committed "
          f"manifest")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("manifest")
    for name in ("pack", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "manifest":
        return write_manifest()
    if args.command == "pack":
        return pack(args.dest)
    return verify(args.dest)


if __name__ == "__main__":
    raise SystemExit(main())
