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

# Reported for diagnosis only — see the note in `probe` for why it must not be
# used to admit a clip.
MAX_DIRECTIONALITY = 0.25     # net displacement as a share of total path length


def printable(text: str, width: int = 40) -> str:
    """ASCII-safe filename for the console.

    Real footage filenames carry Devanagari and Bengali punctuation — a Dhaka
    clip named with a danda (U+0964) crashed the first run of this script on a
    cp1252 console, *after* eleven minutes of scanning. Losing a whole scan to a
    print statement is an expensive way to learn that output encoding is not a
    detail. The CSV is written UTF-8 and keeps the real name.
    """
    return text.encode("ascii", "replace").decode()[:width]



# Cumulative drift, as a share of frame width. THIS is the physically meaningful
# quantity, and the per-second jitter figure above is not.
#
# A lane occupies roughly 15% of frame width. A polygon edge that wanders by more
# than a few percent of the frame stops describing the approach it was drawn on,
# so the tolerance is expressed against the frame rather than in raw pixels — a
# 2 px threshold means something different at 640 and at 3840.
MAX_DRIFT_FRACTION = 0.02      # 2% of width: ~38 px at 1920, ~13% of a lane

# Phase correlation returns a peak response even for unrelated images. Below this
# the answer is noise dressed as a measurement.
MIN_CORRELATION = 0.08


def background(handle, t0: float, fps: float, *, span: float = 12.0, k: int = 20):
    """Median of `k` frames over `span` seconds: moving traffic disappears.

    Correlating raw frames minutes apart does not measure camera drift. Dense
    traffic rearranges completely, so the correlation peak is noise — measured at
    a confidence of 0.009 on real footage, while returning a confident-looking
    694 px. The median over a window removes the vehicles and leaves buildings,
    kerbs and road markings, which are what the camera is actually pointed at.
    """
    import cv2
    import numpy as np

    frames = []
    for i in range(k):
        handle.set(cv2.CAP_PROP_POS_FRAMES, int((t0 + i * span / k) * fps))
        ok, frame = handle.read()
        if ok:
            frames.append(cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY))
    if not frames:
        return None
    return np.median(np.stack(frames), axis=0).astype(np.float32)


def measure_drift(path: Path) -> dict:
    """Largest confident background-to-background displacement across the clip."""
    import cv2
    import numpy as np

    handle = cv2.VideoCapture(str(path))
    fps = handle.get(cv2.CAP_PROP_FPS) or 25.0
    frames = int(handle.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(handle.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
    seconds = frames / fps if fps else 0.0

    if seconds < 40:
        handle.release()
        return {"drift_px": float("nan"), "drift_fraction": float("nan"),
                "drift_confident": False}

    scale = width / 320.0
    reference = background(handle, 5.0, fps)
    worst, confident = 0.0, False
    if reference is not None:
        for fraction in (0.25, 0.5, 0.75, 0.95):
            moment = seconds * fraction
            if moment + 12 > seconds:
                continue
            other = background(handle, moment, fps)
            if other is None:
                continue
            (dx, dy), response = cv2.phaseCorrelate(reference, other)
            if response >= MIN_CORRELATION:
                confident = True
                worst = max(worst, float(np.hypot(dx, dy)) * scale)
    handle.release()

    return {
        "drift_px": round(worst, 1),
        "drift_fraction": round(worst / width, 4),
        "drift_confident": confident,
    }


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
    vectors: list[tuple[float, float]] = []
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
        scale = width / 320.0
        shifts.append(float(np.hypot(dx, dy)) * scale)
        vectors.append((dx * scale, dy * scale))

    handle.release()

    ordered = sorted(shifts)
    median_shift = ordered[len(ordered) // 2] if ordered else float("nan")

    # Jitter or drift? The magnitude alone cannot tell them apart, and they have
    # opposite consequences.
    #
    #   a footbridge flexing as a bus passes  -> the camera returns to where it
    #       started, so the displacement VECTORS cancel. Stabilisable.
    #   a hand-held walk or a slow pan        -> the vectors accumulate. The
    #       scene genuinely leaves the frame, and no amount of stabilisation
    #       recovers a lane polygon that has slid off its approach.
    #
    # So: compare the length of the SUM of vectors against the sum of their
    # lengths. Near 0 means oscillation; near 1 means the camera is going
    # somewhere. Treating those alike rejects footage that is merely shaky.
    path_length = sum(shifts)
    net = (sum(v[0] for v in vectors), sum(v[1] for v in vectors))
    net_length = float(np.hypot(*net)) if vectors else 0.0
    directionality = net_length / path_length if path_length > 1e-6 else 0.0

    drift = measure_drift(path)
    drifts_too_far = (
        drift["drift_confident"] and drift["drift_fraction"] > MAX_DRIFT_FRACTION
    )

    long_enough = seconds >= MIN_USABLE_S
    scene_moves = len(hashes) > samples // 2
    steady = (
        median_shift == median_shift
        and median_shift <= MAX_CAMERA_SHIFT_PX
        and not drifts_too_far
    )
    # `directionality` is REPORTED, never used to pass a clip. It distinguishes
    # a consistent pan from non-directional motion, and that is all it does.
    #
    # It was briefly used to mark low-directionality clips "stabilisable". That
    # was wrong and the measurement said so: correcting a 60 s segment of the
    # 8.19 px / 0.076 clip moved its median shift from 5.78 px to 7.39 px — no
    # improvement at all.
    #
    # The reasoning error is worth keeping. Low directionality does not mean the
    # camera oscillates about a fixed point; a RANDOM WALK also scores near zero,
    # because net displacement grows as sqrt(n) while path length grows as n. So
    # it rules out a pan and proves nothing about recoverability. A wandering
    # handheld shot looks identical to a vibrating tripod by this statistic.
    stabilisable = False

    return {
        "file": path.name,
        "seconds": round(seconds, 1),
        "resolution": f"{width}x{height}",
        "fps": round(fps, 1),
        "distinct": len(hashes),
        "camera_shift_px": round(median_shift, 2),
        "directionality": round(directionality, 3),
        "long_enough": long_enough,
        "scene_moves": scene_moves,
        "camera_fixed": steady,
        **drift,
        "stabilisable": stabilisable,
        "mechanically_ok": long_enough and scene_moves and steady,
    }


def verdict(row: dict) -> str:
    if row["mechanically_ok"]:
        return "CANDIDATE"
    reasons = []
    if not row["long_enough"]:
        reasons.append(f"{row['seconds']:.0f}s<{MIN_USABLE_S}")
    if not row["camera_fixed"]:
        if row.get("drift_confident") and row.get("drift_fraction", 0) > MAX_DRIFT_FRACTION:
            reasons.append(
                f"drifts {row['drift_px']}px "
                f"({row['drift_fraction'] * 100:.1f}% of frame)"
            )
        else:
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
    parser.add_argument(
        "--rescan", action="store_true",
        help="re-probe files already in the CSV (default: skip them)",
    )
    args = parser.parse_args(argv)

    videos = sorted(
        p for p in args.directory.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES
    )
    if not videos:
        raise SystemExit(f"no video files under {args.directory}")

    # Incremental by default. Probing seeks through the whole file, so a 13 GB
    # library costs ~20 minutes; re-paying that to assess ten new clips is waste,
    # and waste that discourages running the check at all.
    previous: dict[str, dict] = {}
    if args.csv.exists() and not args.rescan:
        with args.csv.open(encoding="utf-8") as handle:
            previous = {row["file"]: row for row in csv.DictReader(handle)}

    fresh = [v for v in videos if v.name not in previous]
    if previous:
        print(
            f"  {len(previous)} already triaged, {len(fresh)} new "
            f"(use --rescan to redo everything)\n"
        )

    rows = []
    print(f"{'sec':>7} {'shift':>7} {'dist':>5}  {'verdict':<34} file")
    for video in fresh:
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

    # Merge new results over the retained ones so the CSV always describes the
    # whole library, not just this run.
    merged = list(previous.values()) + rows
    if merged:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        fields = sorted({k for row in merged for k in row})
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in merged:
                writer.writerow({k: row.get(k, "") for k in fields})
        print(f"\n  wrote {args.csv} ({len(merged)} files)")

    def passes(row: dict) -> bool:
        # Rows read back from CSV carry strings, not booleans.
        value = row.get("mechanically_ok")
        return value is True or value == "True"

    passing = [r for r in merged if passes(r)]
    print(f"  {len(passing)} of {len(merged)} pass duration + stationary camera + motion")
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
