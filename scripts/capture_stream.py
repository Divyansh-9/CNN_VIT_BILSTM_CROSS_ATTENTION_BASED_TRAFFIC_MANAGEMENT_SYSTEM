"""Capture a segment of a public traffic stream for the Week-2 pilots (S06).

S06 has been blocked on footage longer than every source tried: stock sites give
10–30 s clips, PennDOT cameras produced **one distinct frame in 100 s**, the
Ultralytics demo is 2.1 s with no vehicles, and UA-DETRAC needs registration.
This removes the *tooling* half of that blocker — a public stream can now be
captured to disk in one command.

    python scripts/capture_stream.py <url> --seconds 420
    python scripts/capture_stream.py --search "india traffic junction cctv"

**The minimum is 360 s and it is not negotiable** (amendment A15). A T=60 window
at 5 s spacing spans 295 s, and the label sits 60 s past its end, so a clip
shorter than 355 s yields **zero** sequences. `--seconds 420` leaves margin for
the encoder trimming the tail.

**Every capture is a DEV source.** `mfstnet.corpus.sources.assert_usable_for_reporting`
raises on it, so nothing captured this way can reach a reported number. It exists
to answer the two Week-2 questions — do the §14.1 thresholds fit real traffic, and
does the class change often enough to be learnable (A17) — before anyone commits
to collecting 12,000 frames.

**Nothing captured here is ever published.** ADR-013 and pending item P10 rule
that out: raw frames of an Indian street contain identifiable faces and plates,
and India's DPDP Rules reach full enforcement in May 2027. Derived counts and
annotations may be published; frames may not. `data/dev_footage/` is gitignored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("data/dev_footage")
MIN_USABLE_S = 360          # A15 — below this a clip yields zero sequences


def ffmpeg_path() -> str:
    """A bundled ffmpeg, so this works without a system install."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as error:
        raise SystemExit(
            "need ffmpeg: pip install imageio-ffmpeg yt-dlp"
        ) from error


def search(query: str, *, limit: int = 20, min_seconds: int = MIN_USABLE_S) -> list[dict]:
    """Find candidates long enough to be usable — **including live streams**.

    The live case is the one that matters and the first version of this function
    silently excluded it. A live entry reports `duration: None`, and the filter
    was `duration >= min_seconds`, so **every continuous stream was dropped** —
    the search could not find the only kind of source that solves the problem.
    It returned short recorded clips and looked like it was working.

    A live stream has no end, so it can supply as many minutes as A15 requires in
    one capture. That makes `is_live` the strongest signal here, not a special
    case: live entries sort first and are reported with unbounded length.
    """
    import yt_dlp

    options = {"quiet": True, "extract_flat": True, "skip_download": True}
    found: dict[str, dict] = {}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        for entry in info.get("entries", []) or []:
            live = bool(entry.get("is_live")) or entry.get("live_status") in (
                "is_live", "post_live"
            )
            duration = entry.get("duration") or 0
            if not (live or duration >= min_seconds) or entry["id"] in found:
                continue
            found[entry["id"]] = {
                "id": entry["id"],
                "seconds": duration,
                "live": live,
                "title": (entry.get("title") or "").encode("ascii", "replace").decode(),
            }
    # Live first, then longest recorded.
    return sorted(found.values(), key=lambda e: (not e["live"], -e["seconds"]))


def capture(url: str, *, seconds: int = 420, out: Path = OUT,
            max_height: int = 720) -> Path:
    import yt_dlp

    out.mkdir(parents=True, exist_ok=True)
    template = str(out / "capture_%(id)s.mp4")

    options = {
        "format": f"best[height<={max_height}]/best",
        "outtmpl": template,
        "ffmpeg_location": ffmpeg_path(),
        "external_downloader": "ffmpeg",
        "external_downloader_args": {"ffmpeg_i": ["-t", str(seconds)]},
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
    return out / f"capture_{info['id']}.mp4"


def inspect(path: Path) -> dict:
    """Duration, resolution, and **how many sampled frames actually differ**.

    The distinct-frame count is the check that matters. A PennDOT camera passed
    every other test and delivered one distinct frame in 100 seconds — footage
    that would have "proved" the task degenerate. A source that does not move is
    worse than no source.
    """
    import hashlib

    import cv2

    capture_handle = cv2.VideoCapture(str(path))
    fps = capture_handle.get(cv2.CAP_PROP_FPS) or 0.0
    frames = int(capture_handle.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture_handle.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture_handle.get(cv2.CAP_PROP_FRAME_HEIGHT))

    hashes = set()
    samples = 40
    for i in range(0, max(frames, 1), max(1, frames // samples)):
        capture_handle.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = capture_handle.read()
        if ok:
            hashes.add(hashlib.md5(cv2.resize(frame, (64, 64)).tobytes()).hexdigest())
    capture_handle.release()

    seconds = frames / fps if fps else 0.0
    return {
        "path": path,
        "seconds": round(seconds, 1),
        "resolution": f"{width}x{height}",
        "fps": round(fps, 1),
        "frames": frames,
        "distinct_sampled": len(hashes),
        "usable": seconds >= MIN_USABLE_S and len(hashes) > samples // 2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("url", nargs="?")
    parser.add_argument("--search", help="find candidates long enough to use")
    parser.add_argument(
        "--check", type=Path,
        help="check a file you recorded yourself (phone, tripod) — same bar",
    )
    parser.add_argument("--seconds", type=int, default=420)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    if args.search:
        results = search(args.search)
        if not results:
            print(f"  no candidate at least {MIN_USABLE_S}s long. Widen the query.")
            return 1
        for entry in results[:15]:
            length = "LIVE" if entry["live"] else f"{entry['seconds'] // 60:>3}m"
            print(f"  {length:>5}  {entry['id']}  {entry['title'][:58]}")
        return 0

    if args.check:
        # Self-capture is the P0 sourcing track (ADR-015 Decision 5): the PRD
        # specifies IndiaTrafficNet as self-collected, so a phone on a tripod is
        # the plan rather than the fallback. This applies exactly the same bar a
        # downloaded stream has to clear.
        if not args.check.exists():
            raise SystemExit(f"no such file: {args.check}")
        report = inspect(args.check)
        for key, value in report.items():
            print(f"  {key:18} {value}")
        if report["usable"]:
            print(
                "\n  USABLE. Move it into data/dev_footage/ and run:"
                "\n      python scripts/pilot_counts.py <file>"
            )
            return 0
        reasons = []
        if report["seconds"] < MIN_USABLE_S:
            reasons.append(
                f"only {report['seconds']}s — needs >= {MIN_USABLE_S}s "
                f"(A15: a T=60 window spans 295s and its label sits 60s past "
                f"the end, so a shorter clip yields ZERO sequences)"
            )
        if report["distinct_sampled"] <= 20:
            reasons.append(
                f"only {report['distinct_sampled']}/40 sampled frames differ — "
                f"the camera or the scene is not moving"
            )
        print("\n  NOT USABLE:")
        for reason in reasons:
            print(f"    - {reason}")
        print(
            "\n  Record again in ONE continuous take with the phone fixed in "
            "place. Do not stitch clips\n  together: that fabricates the temporal "
            "structure the pilot exists to measure."
        )
        return 1

    if not args.url:
        parser.error("give a URL, --search to find one, or --check a file you recorded")

    path = capture(args.url, seconds=args.seconds, out=args.out)
    report = inspect(path)
    for key, value in report.items():
        print(f"  {key:18} {value}")

    if not report["usable"]:
        print(
            f"\n  NOT USABLE. A clip must be >= {MIN_USABLE_S}s (A15: a T=60 window "
            f"spans 295s and its label sits 60s past the end, so anything shorter\n"
            f"  yields ZERO sequences) and must actually move — a static feed would "
            f"'prove' the task degenerate.\n"
            f"  Do NOT concatenate short clips: that fabricates the temporal "
            f"structure the pilot exists to measure."
        )
        return 1

    print("\n  usable as a DEV source. It can answer the Week-2 questions; it can "
          "never appear in a reported number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
