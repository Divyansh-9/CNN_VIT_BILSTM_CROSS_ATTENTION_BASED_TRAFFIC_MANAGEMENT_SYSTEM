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

What is covered:
- every checkpoint and its sidecar under `models/mfstnet/`;
- every exported graph under `models/onnx/`, **with its external `.onnx.data`
  weights file** (P90 — the graph file alone does not contain the weights);
- every PPO checkpoint and provenance sidecar under `models/ppo/` (P139).
  These include the checkpoints that the ceiling locks fingerprint;
- the trained detectors under `models/detector/`;
- the third-party weights under `models/external/`. The corpus pipeline
  depends on them, and an upstream download can disappear.

`pack` copies what the manifest lists, so a manifest written before a training
run silently leaves that run out, and `verify` then passes over the gap. That
happened once (P139). So:
- **`pack` and `check` refuse a stale manifest:** one that misses a file on
  disk, lists a file that is gone, or records a hash the file no longer has.
- **`manifest` refuses to drop a recorded artifact silently.** A file that has
  vanished is named with `--allow-removed`, or nothing is written.
- **`verify` also fails on a file in the copy that the manifest does not
  list,** and on a copy whose own manifest is not the committed one.
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
SOURCES = ("models/mfstnet", "models/onnx", "models/ppo", "models/detector",
           "models/external")
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


def write_manifest(allow_removed: frozenset[str] = frozenset()) -> int:
    files = artifacts()
    if not files:
        raise SystemExit("no artifacts under models/ to fingerprint")
    # A regenerated manifest describes the disk, so a file that vanished would
    # simply stop being listed and every later check would pass over it. A
    # recorded artifact leaves the manifest only when it is named (P139).
    if MANIFEST.is_file():
        current = {p.relative_to(ROOT).as_posix() for p in files}
        dropped = sorted(set(read_manifest(MANIFEST)) - current - allow_removed)
        if dropped:
            for name in dropped:
                print(f"  DROPPED   {name}")
            print(f"\n  FAIL  {len(dropped)} recorded artifact(s) are gone from disk. "
                  f"Restore them, or name each with --allow-removed. Nothing written.")
            return 1
    lines = ["# sha256 of every model artifact git does not hold "
             "(scripts/backup_models.py). Paths relative to the repository."]
    lines += [f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}" for p in files]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in files) / 2**20
    print(f"  {len(files)} file(s), {size:.0f} MB -> {MANIFEST.relative_to(ROOT)}")
    return 0


def stale(manifest: dict[str, str]) -> dict[str, list[str]]:
    """How the manifest disagrees with the artifacts on disk now (P139)."""
    on_disk = {p.relative_to(ROOT).as_posix(): p for p in artifacts()}
    return {
        "not in manifest": sorted(set(on_disk) - set(manifest)),
        "gone from disk": sorted(set(manifest) - set(on_disk)),
        "hash changed": sorted(n for n in set(on_disk) & set(manifest)
                               if sha256(on_disk[n]) != manifest[n]),
    }


def check() -> int:
    problems = stale(read_manifest(MANIFEST))
    for kind, names in problems.items():
        for name in names:
            print(f"  {kind.upper():16}  {name}")
    count = sum(len(names) for names in problems.values())
    if count:
        print(f"\n  FAIL  the manifest is stale: {count} disagreement(s). Run "
              f"`backup_models.py manifest` and commit it before packing.")
        return 1
    print(f"  PASS  the manifest covers every artifact under {', '.join(SOURCES)}")
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
    if check():
        return 1
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
    # A file in the copy that the manifest does not list is a copy of
    # something else, and the copy's own manifest must be the committed one.
    unexpected = sorted(
        p.relative_to(dest).as_posix() for source in SOURCES
        if (dest / source).is_dir() for p in (dest / source).rglob("*")
        if p.is_file() and p.relative_to(dest).as_posix() not in manifest)
    copied = dest / MANIFEST.name
    if not copied.is_file() or copied.read_bytes() != MANIFEST.read_bytes():
        unexpected.append(f"{MANIFEST.name} (absent or not the committed manifest)")
    if missing or wrong or unexpected:
        for name in missing:
            print(f"  MISSING     {name}")
        for name in wrong:
            print(f"  MISMATCH    {name}")
        for name in unexpected:
            print(f"  UNEXPECTED  {name}")
        print(f"\n  FAIL  {len(missing)} missing, {len(wrong)} not matching, "
              f"{len(unexpected)} unexpected, against the committed manifest")
        return 1
    print(f"  PASS  all {len(manifest)} file(s) at {dest} match the committed "
          f"manifest")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("--allow-removed", action="append", default=[],
                          metavar="PATH", help="a recorded artifact that may leave "
                          "the manifest; repeat for each")
    sub.add_parser("check")
    for name in ("pack", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "manifest":
        return write_manifest(frozenset(args.allow_removed))
    if args.command == "check":
        return check()
    if args.command == "pack":
        return pack(args.dest)
    return verify(args.dest)


if __name__ == "__main__":
    raise SystemExit(main())
