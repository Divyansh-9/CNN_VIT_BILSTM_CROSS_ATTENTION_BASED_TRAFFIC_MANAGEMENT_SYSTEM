"""The decode benchmark's stream probe (P89)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark_decode import parse_probe  # noqa: E402

BANNER = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mp4':
  Metadata:
    title           : Video: Incredible traffic Sound in Dhaka [4K ASMR]
  Duration: 00:05:00.03, start: 0.000000, bitrate: 16104 kb/s
  Stream #0:0[0x1](und): Video: av1 (libaom-av1) (Main) (av01 / 0x31307661), yuv420p(tv, bt709), 3840x2160 [SAR 1:1 DAR 16:9], 15842 kb/s, 29.97 fps, 29.97 tbr, 30k tbn (default)
"""


def test_the_stream_line_wins_over_a_title_that_says_video():
    """The corpus's 4K clip has "Video:" in its title metadata, and the first
    version of the probe parsed the title and crashed."""
    assert parse_probe(BANNER) == {"width": 3840, "height": 2160,
                                   "fps": 29.97, "codec": "av1"}


def test_a_1080p_h264_stream():
    line = ("  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), "
            "yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], "
            "6000 kb/s, 29.97 fps, 29.97 tbr, 30k tbn (default)\n")
    assert parse_probe(line)["codec"] == "h264"
    assert parse_probe(line)["width"] == 1920
