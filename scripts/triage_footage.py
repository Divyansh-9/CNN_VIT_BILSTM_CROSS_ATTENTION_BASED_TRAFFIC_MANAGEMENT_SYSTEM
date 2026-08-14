"""Triage candidate footage against every S06 criterion (ADR-015 Decision 5).

`capture_stream.py --check` tests duration and whether the scene moves. That is
necessary and **not sufficient**, and the gap is dangerous in a specific way:

    a static camera on a dead street  -> few distinct frames -> correctly rejected
    a HANDHELD camera on a busy street -> many distinct frames -> WRONGLY ACCEPTED

Both fail, for opposite reasons, and only one was being caught. A panning or
handheld shot changes every pixel every frame, so it sails through a
distinct-frame test — and it is unusable, because lane polygons are defined in
normalised image coordinates against a **fixed** frame. If the camera drifts, a
polygon that meant "north approach" at t=0 means something else by t=300, and
every count derived from it is wrong without anything raising.

So this measures camera motion directly, by phase correlation between frames
sampled a second apart. A tripod gives a global shift of roughly zero pixels; a
handheld shot gives several, and a pan gives tens.

    python scripts/triage_footage.py "D:/traffic dataset"
    python scripts/triage_footage.py <dir> --contact-sheet out/

The four criteria (DATASETS §4.6): a **signalised** intersection, **mixed**
traffic, a **stationary** camera, and **>= 360 s**. This script decides 3 and 4
mechanically and extracts a frame so a human can decide 1 and 2 in one glance.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIN_USABLE_S = 360          # A15
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}

# Median global shift, in pixels, between frames one second apart.
# A tripod sits near 0. Anything above this is drifting enough that a lane
# polygon drawn at t=0 no longer means the same region later.
MAX_CAMERA_SHIFT_PX = 2.0


def printable(text: str, width: int = 40) -> str:
    """ASCII-safe filename for the console.

    Real footage filenames carry Devanagari and Bengali punctuation — a Dhaka
    clip named with a danda (U+0964) crashed the first run of this script on a
    cp1252 console, *after* eleven minutes of scanning. Losing a whole scan to a
    print statement is an expensive way to learn that output encoding is not a
    detail. The CSV is written UTF-8 and keeps the real name.
    """
    return text.encode("ascii", "replace").decode()[:width]


def probe(path: Path, *, samples: int = 24) -> dict:
    import hashlib

    import cv2
    import numpy as np

    handle = cv2.VideoCapture(str(path))
    fps = handle.get(cv2.CAP_PROP_FPS) or 0.0
    frames = int(handle.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(handle.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(handle.get(cv2.CAP_PROP_FRAME_HEIGHT))
    seconds = frames / fps if fps else 0.0

    hashes: set[str] = set()
    shifts: list[float] = []
    step = max(1, frames // samples) if frames else 1

    for index in range(0, max(frames - int(fps or 25) - 1, 1), step):
        handle.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok_a, frame_a = handle.read()
        if not ok_a:
            continue
        hashes.add(hashlib.md5(cv2.resize(frame_a, (64, 64)).tobytes()).hexdigest())

        # One second later: long enough that a handheld wobble shows, short
        # enough that vehicles have not rearranged the whole scene.
        handle.set(cv2.CAP_PROP_POS_FRAMES, index + int(fps or 25))
        ok_b, frame_b = handle.read()
        if not ok_b:
            continue

        small_a = cv2.cvtColor(cv2.resize(frame_a, (320, 180)), cv2.COLOR_BGR2GRAY)
        small_b = cv2.cvtColor(cv2.resize(frame_b, (320, 180)), cv2.COLOR_BGR2GRAY)
        (dx, dy), _ = cv2.phaseCorrelate(
            np.float32(small_a), np.float32(small_b)
        )
        # Report in source pixels, not the downscaled ones.
        shifts.append(float(np.hypot(dx, dy)) * (width / 320.0))

    handle.release()

    shifts.sort()
    median_shift = shifts[len(shifts) // 2] if shifts else float("nan")
    long_enough = seconds >= MIN_USABLE_S
    scene_moves = len(hashes) > samples // 2
    camera_fixed = median_shift == median_shift and median_shift <= MAX_CAMERA_SHIFT_PX

    return {
        "file": path.name,
        "seconds": round(seconds, 1),
        "resolution": f"{width}x{height}",
        "fps": round(fps, 1),
        "distinct": len(hashes),
        "camera_shift_px": round(median_shift, 2),
        "long_enough": long_enough,
        "scene_moves": scene_moves,
        "camera_fixed": camera_fixed,
        "mechanically_ok": long_enough and scene_moves and camera_fixed,
    }


def verdict(row: dict) -> str:
    if row["mechanically_ok"]:
        return "CANDIDATE"
    reasons = []
    if not row["long_enough"]:
        reasons.append(f"{row['seconds']:.0f}s<{MIN_USABLE_S}")
    if not row["camera_fixed"]:
        reasons.append(f"camera moves {row['camera_shift_px']}px")
    if not row["scene_moves"]:
        reasons.append("static scene")
    return "reject: " + ", ".join(reasons)


def contact_sheet(path: Path, out_dir: Path, *, at_fraction: float = 0.35) -> Path:
    """One representative frame, so a human can judge signal and vehicle mix."""
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    handle = cv2.VideoCapture(str(path))
    frames = int(handle.get(cv2.CAP_PROP_FRAME_COUNT))
    handle.set(cv2.CAP_PROP_POS_FRAMES, int(frames * at_fraction))
    ok, frame = handle.read()
    handle.release()
    if not ok:
        raise RuntimeError(f"could not read a frame from {path.name}")

    height, width = frame.shape[:2]
    if width > 960:
        frame = cv2.resize(frame, (960, int(height * 960 / width)))
    target = out_dir / (path.stem[:60].replace(" ", "_") + ".jpg")
    cv2.imwrite(str(target), frame)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--contact-sheet", type=Path,
                        help="also write one representative frame per video")
    parser.add_argument("--csv", type=Path, default=Path("experiments/results/footage_triage.csv"))
    args = parser.parse_args(argv)

    videos = sorted(
        p for p in args.directory.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES
    )
    if not videos:
        raise SystemExit(f"no video files under {args.directory}")

    rows = []
    print(f"{'sec':>7} {'shift':>7} {'dist':>5}  {'verdict':<34} file")
    for video in videos:
        try:
            row = probe(video)
        except Exception as error:                       # noqa: BLE001
            print(
                f"{'ERR':>7} {'-':>7} {'-':>5}  "
                f"{printable(str(error), 32):<34} {printable(video.name)}"
            )
            continue
        rows.append(row)
        print(
            f"{row['seconds']:>7.0f} {row['camera_shift_px']:>7.2f} "
            f"{row['distinct']:>5}  {verdict(row):<34} {printable(video.name)}"
        )
        if args.contact_sheet:
            try:
                contact_sheet(video, args.contact_sheet)
            except Exception:                            # noqa: BLE001
                pass

    if rows:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n  wrote {args.csv}")

    passing = [r for r in rows if r["mechanically_ok"]]
    print(f"  {len(passing)} of {len(rows)} pass duration + stationary camera + motion")
    if passing:
        print(
            "\n  These still need a HUMAN check of the two criteria a script "
            "cannot judge (DATASETS §4.6):\n"
            "    1. is a signalised intersection in frame?\n"
            "    2. is the traffic mixed — three-wheelers visible?"
        )
    return 0 if passing else 1


if __name__ == "__main__":
    raise SystemExit(main())
