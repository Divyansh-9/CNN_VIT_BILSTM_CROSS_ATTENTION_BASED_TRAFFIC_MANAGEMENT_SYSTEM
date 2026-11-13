"""Render each clip's burnt-in camera clock at its start, middle and end.

    python scripts/clock_sheet.py --out sheet.png CLIP [CLIP ...]

A file is continuous when the clock advances exactly as far as the file is
long. This crops the clock strip at 1 s, at the middle, and 2 s before the end
of each clip, and stacks the crops with each clip's duration beside them, so
the check is one look at one image rather than a guess from file size.
Reading the clock is left to a person, on purpose: this camera's overlay is
small and an OCR misread would pass a gap silently.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path: Path) -> float:
    text = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def frame_at(path: Path, t: float):
    import cv2
    import numpy as np

    raw = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss",
                          f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-f",
                          "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def main(argv: list[str] | None = None) -> int:
    import cv2
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("clips", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = []
    for clip in args.clips:
        d = duration(clip)
        crops = []
        for t in (1.0, d / 2, d - 2.0):
            frame = frame_at(clip, t)
            crop = frame[690:720, 0:420]
            crops.append(cv2.resize(crop, (420, 30)))
        label = np.full((30, 470, 3), 255, np.uint8)
        name = re.search(r"__(\S+)\.mp4", clip.name).group(1)
        cv2.putText(label, f"{name}  {d / 60:.2f} min", (6, 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        rows.append(np.hstack([label] + crops))
    cv2.imwrite(str(args.out), np.vstack(rows))
    print(f"wrote {args.out} ({len(rows)} clips: start | middle | end)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
