"""P105 — the lane-placement page for 116th NE12th, from its calibration hour only.

    python scripts/p105_lane_page.py

The same page as P103 (`scripts/p103_lane_page.py`): two frames of the Sun
19:08 calibration hour, at 25% and 75%, with no detector run and no test hour
shown. Eastgate, Newport and SE38th are not offered, because P105 Amendment 1
freezes their P103 lanes. Writes `data/_bellevue/p105/place_lanes_p105.html`,
footage, not committed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p103_lane_page import PAGE, frame_at  # noqa: E402

CALIBRATION = Path("data/_bellevue/p105/Bellevue_116th_NE12th__2017-09-10_19-08-25.mp4")
OUT = Path("data/_bellevue/p105/place_lanes_p105.html")


def main() -> int:
    if not CALIBRATION.is_file():
        raise SystemExit(f"{CALIBRATION} is not downloaded yet")
    cams = [{"camera": "116th_NE12th", "clip": CALIBRATION.name,
             "frames": [frame_at(CALIBRATION, 0.25), frame_at(CALIBRATION, 0.75)]}]
    page = (PAGE.replace("__CAMS__", json.dumps(cams))
                .replace("Place P103 lanes", "Place P105 lanes")
                .replace("Place lanes: Eastgate, Newport, SE38th (P103)",
                         "Place lanes: 116th NE12th (P105)")
                .replace("(Sun 18:08)", "(Sun 19:08)")
                .replace("lane_centres_p103.json", "lane_centres_p105.json")
                .replace("data/_bellevue/p103/", "data/_bellevue/p105/"))
    OUT.write_text(page, encoding="utf-8")
    print(f"  wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB): 116th_NE12th, calibration hour only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
