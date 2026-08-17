"""Fetch the Bellevue Traffic Video Dataset reproducibly (ADR-016 Phase 1).

    python scripts/fetch_bellevue.py --list
    python scripts/fetch_bellevue.py --per-camera 6      # the recommended start
    python scripts/fetch_bellevue.py --all               # all 115 files

115 hourly files across five pole-mounted intersection cameras, City of Bellevue,
Washington, September 2017. Released by the city for research.

**Why a script rather than clicking five Drive links.** NFR-08: the corpus must be
rebuildable from a clean machine. A manually assembled download is not a corpus,
it is a folder nobody else can reproduce — and which file went into which split
becomes unanswerable six weeks later.

**Download a subset first, and all five cameras.** Camera count, not file count,
is what limits this dataset: splits must be cut **by camera**, because clips from
one camera share a background and a model can learn the scene instead of the
traffic. Five cameras means roughly a 3/1/1 split, so every camera matters and a
sixth file from a camera you already have adds far less than a first file from
one you do not.

**Nothing here is published.** `data/dev_footage/` is gitignored and ADR-013 and
P10 rule out republishing frames. Derived counts and labels may be published;
the video may not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Pinned from the dataset's own README. Recorded here so the set of sources is a
# committed fact rather than something re-found by hand each time.
CAMERAS = {
    "116th_NE12th": "16coOR8PlNzvmUm1vsaYJVF_bAOQGySa8",
    "150th_Eastgate": "1cR1VwoAvEjFLRaUzeYph-bxx4LoM6pOH",
    "150th_Newport": "1irB6XKu2iM3BSJ2AEYH4kJl9nfG9j-yy",
    "150th_SE38th": "1IN6kwywddO3B3uHyC5S18vqf0KEWToJ_",
    "NE8th": "17bn7l7Qm5s-r5DYoFQPhviFZ0jWY9qk5",
}
ROOT = Path("data/dev_footage/bellevue")


def listing(camera: str, folder_id: str) -> list:
    import gdown

    return gdown.download_folder(
        f"https://drive.google.com/drive/folders/{folder_id}",
        skip_download=True, quiet=True, use_cookies=False,
    ) or []


def spread(files: list, take: int) -> list:
    """Pick `take` files spread across the day, not the first `take`.

    The filenames carry an hour stamp, and taking the first N gives N consecutive
    small hours — every one of them empty. Congestion variety comes from time of
    day, so the sample must span it.
    """
    ordered = sorted(files, key=lambda f: Path(f.path).name)
    if take >= len(ordered):
        return ordered
    stride = len(ordered) / take
    return [ordered[int(i * stride)] for i in range(take)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--per-camera", type=int, default=6,
                        help="files per camera, spread across the day")
    parser.add_argument("--all", action="store_true", help="every file (~115)")
    parser.add_argument("--cameras", nargs="*", default=list(CAMERAS),
                        help="subset of camera names; default is all five")
    parser.add_argument("--list", action="store_true",
                        help="show what would be fetched and stop")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    try:
        import gdown
    except ImportError:
        raise SystemExit("pip install gdown")

    unknown = set(args.cameras) - set(CAMERAS)
    if unknown:
        raise SystemExit(f"unknown camera(s) {sorted(unknown)}; "
                         f"expected from {sorted(CAMERAS)}")

    planned = []
    for camera in args.cameras:
        files = listing(camera, CAMERAS[camera])
        chosen = files if args.all else spread(files, args.per_camera)
        planned.append((camera, len(files), chosen))
        print(f"  {camera:<16} {len(chosen):>3} of {len(files):>3} files")

    total = sum(len(c) for _, _, c in planned)
    print(f"\n  {total} file(s) from {len(planned)} camera(s)")
    if args.list:
        for camera, _, chosen in planned:
            for handle in chosen:
                print(f"    {camera}/{Path(handle.path).name}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    fetched = skipped = failed = 0
    for camera, _, chosen in planned:
        directory = args.out / camera
        directory.mkdir(parents=True, exist_ok=True)
        for handle in chosen:
            name = Path(handle.path).name
            target = directory / name
            if target.exists() and target.stat().st_size > 0:
                skipped += 1
                continue
            try:
                gdown.download(id=handle.id, output=str(target), quiet=True)
                fetched += 1
                print(f"    {camera}/{name}  {target.stat().st_size / 1e6:.0f} MB")
            except Exception as error:                   # noqa: BLE001
                failed += 1
                print(f"    FAILED {camera}/{name}: {error}")

    print(f"\n  fetched {fetched}, already present {skipped}, failed {failed}")
    print(f"  in {args.out}")
    print("\n  Next, and do this BEFORE fetching more:")
    print("    python scripts/check_recording.py <one file>   # confirms it is usable")
    print("  Camera count limits this dataset, not file count. Splits are cut by")
    print("  CAMERA — clips from one camera share a background, and a model that")
    print("  learns the scene instead of the traffic will score well and mean")
    print("  nothing. Five cameras is roughly a 3/1/1 split, so a first file from")
    print("  a new camera is worth more than a seventh from one you have.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
