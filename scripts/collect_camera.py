"""Collect a frame series from a public traffic camera (prepares S06).

    python scripts/collect_camera.py --probe                 # measure refresh rate
    python scripts/collect_camera.py --minutes 40 --out data/raw/pilot_cam

Polls a camera that serves a still JPEG and saves time-stamped frames. This is a
better instrument for the pilot than downloading video: the frames arrive already
spaced in time, which is exactly what PRD §8.2 samples, so nothing is decoded or
resampled.

**Duplicate detection is the point.** If the camera refreshes more slowly than the
poll interval, repeated polls return the *same* image. Counting those as separate
samples would report a transition rate near zero and "prove" the task is
degenerate when the only degenerate thing is the sampling. Frames are hashed, and
`--probe` measures the real refresh rate before any long collection starts.

**Honest scope.** These are US highway cameras. Lane-disciplined, no
auto-rickshaws. They answer *does the method work* and give a first read on how
fast congestion class changes; they do **not** answer whether the §14.1
thresholds fit Indian traffic. That needs Indian footage. Collected data is
`kind: dev` and never trains a reported model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

CAMERAS = {
    "penndot_d6_122": "http://www.dot35.state.pa.us/public/Districts/District6/WebCams/D6Cam122.jpg",
    "penndot_d6_100": "http://www.dot35.state.pa.us/public/Districts/District6/WebCams/D6Cam100.jpg",
    "penndot_d6_101": "http://www.dot35.state.pa.us/public/Districts/District6/WebCams/D6Cam101.jpg",
}
UA = {"User-Agent": "Mozilla/5.0 (research pilot; polite polling)"}


def fetch(url: str, timeout: float = 15.0) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        return data if data[:2] == b"\xff\xd8" else None
    except Exception:
        return None


def probe(url: str, seconds: int = 90, interval: float = 3.0) -> float | None:
    """Measure the real refresh interval by watching when the image hash changes."""
    print(f"probing for {seconds}s at {interval}s intervals...")
    seen: list[tuple[float, str]] = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        data = fetch(url)
        if data:
            h = hashlib.md5(data).hexdigest()[:12]
            if not seen or seen[-1][1] != h:
                seen.append((time.time() - t0, h))
                print(f"  t={seen[-1][0]:6.1f}s  new frame  {h}")
        time.sleep(interval)

    if len(seen) < 3:
        print(f"\nonly {len(seen)} distinct frame(s) in {seconds}s — refresh is slower "
              f"than this probe can measure. Try --probe-seconds 300.")
        return None

    gaps = [b[0] - a[0] for a, b in zip(seen, seen[1:])]
    est = sum(gaps) / len(gaps)
    print(f"\n{len(seen)} distinct frames · gaps {[round(g, 1) for g in gaps]}")
    print(f"estimated refresh: ~{est:.0f}s")
    return est


def collect(url: str, out: Path, minutes: float, interval: float) -> int:
    """Poll until `minutes` elapse, saving only frames whose content changed."""
    out.mkdir(parents=True, exist_ok=True)
    meta: list[dict] = []
    seen: set[str] = set()
    t0 = time.time()
    deadline = t0 + minutes * 60
    polls = dupes = 0

    while time.time() < deadline:
        polls += 1
        data = fetch(url)
        if data:
            h = hashlib.md5(data).hexdigest()[:12]
            if h in seen:
                dupes += 1
            else:
                seen.add(h)
                idx = len(meta)
                (out / f"{idx:05d}.jpg").write_bytes(data)
                meta.append({"index": idx, "t": round(time.time() - t0, 2),
                             "md5": h, "bytes": len(data)})
                if idx % 10 == 0:
                    print(f"  {idx:4d} frames · t={meta[-1]['t']:7.1f}s · "
                          f"{dupes} duplicate polls skipped")
        time.sleep(interval)

    (out / "manifest.json").write_text(
        json.dumps({"url": url, "kind": "dev", "poll_interval_s": interval,
                    "polls": polls, "duplicates": dupes, "frames": meta}, indent=2),
        encoding="utf-8")

    if meta:
        span = meta[-1]["t"] - meta[0]["t"]
        spacing = span / (len(meta) - 1) if len(meta) > 1 else 0
        print(f"\n{len(meta)} distinct frames over {span / 60:.1f} min")
        print(f"actual spacing ~{spacing:.0f}s  ({dupes} of {polls} polls were duplicates)")
    return len(meta)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default="penndot_d6_122", choices=sorted(CAMERAS))
    ap.add_argument("--url", help="override with any JPEG-serving camera")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--probe-seconds", type=int, default=90)
    ap.add_argument("--minutes", type=float, default=40.0)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--out", default="data/raw/pilot_cam")
    a = ap.parse_args()

    url = a.url or CAMERAS[a.camera]
    print(f"camera: {url}\n")

    if a.probe:
        return 0 if probe(url, a.probe_seconds) else 1

    n = collect(url, Path(a.out), a.minutes, a.interval)
    if n < 72:
        print(f"\nOnly {n} frames — one prediction window needs 72. Collect longer.")
        return 1
    print(f"\nReady. Next: python scripts/pilot_counts.py --frames {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
