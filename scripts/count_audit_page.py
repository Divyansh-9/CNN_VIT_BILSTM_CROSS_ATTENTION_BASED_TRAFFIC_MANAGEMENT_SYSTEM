"""Build a blind hand-count page for P99b: dawn, glare and dusk frames.

    python scripts/count_audit_page.py

Implements the frame selection in
`experiments/results/bellevue_pilot/PREREGISTRATION_P99b.md`. Writes the
selection to `p99b_frames.json` (committed) and a self-contained counting page
to `data/_bellevue/audit/count_audit_p99b.html` (footage, so not committed and
not published: the licence is unresolved). The page shows no detector output.

Each pixel is tinted by the lane the corpus assigns it to: the nearest of the
three P97 centres within 0.25, in normalised coordinates, exactly as
`mfstnet.corpus.lanes.assign_to_lane` measures it.
"""

from __future__ import annotations

import base64
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
SOURCE = Path("data/_bellevue/p98")
PAGE = Path("data/_bellevue/audit/count_audit_p99b.html")
TEMPLATE = Path("data/_bellevue/audit/count_audit_2.html")
LANES = Path("data/_bellevue/lanes_reviewed_3lane/Bellevue_NE8th_2017-09-11_15-08_to_17-08.json")
HOURS = ("2017-09-11_06-08-29", "2017-09-11_07-08-31",
         "2017-09-11_08-08-31", "2017-09-10_19-08-24")
SAMPLES, BINS, STRIDE = 1800, 15, 60
COLOURS = {"lane_0": (230, 120, 40), "lane_1": (40, 140, 255), "lane_2": (200, 60, 200)}  # BGR


def select() -> list[dict]:
    rng = random.Random(2028)
    width = SAMPLES // BINS
    frames = [{"clip": f"Bellevue_Bellevue_NE8th__{hour}", "sample": b * width + rng.randrange(width)}
              for hour in HOURS for b in range(BINS)]
    random.Random(2029).shuffle(frames)
    return frames


def tinted(frame, lanes):
    import numpy as np

    h, w = frame.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    nx, ny = xs / w, ys / h
    best = np.full((h, w), np.inf)
    owner = np.full((h, w), -1)
    for i, lane in enumerate(lanes):
        cx, cy = lane["centre"]
        d = np.hypot(nx - cx, ny - cy)
        closer = d < best
        best[closer], owner[closer] = d[closer], i
    owner[best > 0.25] = -1
    out = frame.astype(np.float32)
    for i, lane in enumerate(lanes):
        mask = owner == i
        out[mask] = 0.72 * out[mask] + 0.28 * np.array(COLOURS[lane["name"]], np.float32)
    return out.clip(0, 255).astype(np.uint8)


def main() -> int:
    import cv2

    from mfstnet.corpus.video import iter_sampled_frames

    frames = select()
    (ROOT / "p99b_frames.json").write_text(json.dumps(
        {"protocol": "PREREGISTRATION_P99b.md", "seed": 2028, "order_seed": 2029,
         "frames": frames}, indent=1), encoding="utf-8")
    lanes = json.loads(LANES.read_text(encoding="utf-8"))["lanes"]
    assert [lane["name"] for lane in lanes] == list(COLOURS)

    wanted: dict[str, set[int]] = {}
    for f in frames:
        wanted.setdefault(f["clip"], set()).add(f["sample"])
    images = {}
    for clip, samples in wanted.items():
        for index, frame in enumerate(iter_sampled_frames(SOURCE / f"{clip}.mp4", STRIDE,
                                                          limit=max(samples) + 1)):
            if index in samples:
                ok, jpeg = cv2.imencode(".jpg", tinted(frame, lanes),
                                        [cv2.IMWRITE_JPEG_QUALITY, 88])
                images[(clip, index)] = base64.b64encode(jpeg.tobytes()).decode()
    payload = [{"sample": f"{f['clip'][-19:]}#{f['sample']}",
                "img": images[(f["clip"], f["sample"])]} for f in frames]

    html = TEMPLATE.read_text(encoding="utf-8")
    head, rest = html.split("const FRAMES=", 1)
    tail = rest[rest.index(";\n") + 1:]
    head = (head.replace("<title>Bellevue count audit, part 2</title>",
                         "<title>Bellevue count audit, P99b</title>")
                .replace("hand count, 40 more frames (part 2)",
                         "hand count, 60 dawn / glare / dusk frames (P99b)"))
    # Three lanes: south is gone, and east is magenta as on the earlier pages.
    head = head.replace(
        '  <div class="lane"><span><b style="background:#3cbe3c"></b>South (green)</span>'
        '<input id="S" type="number" min="0" inputmode="numeric"></div>\n', "")
    tail = (tail.replace('"WNSE"', '"WNE"')
                .replace("lane_0:s.W,lane_1:s.N,lane_2:s.S,lane_3:s.E",
                         "lane_0:s.W,lane_1:s.N,lane_2:s.E")
                .replace("Enter a count for all four lanes", "Enter a count for all three lanes")
                .replace('protocol:"AUDIT_PROTOCOL.md (expansion)"',
                         'protocol:"PREREGISTRATION_P99b.md"'))
    script = f"const FRAMES={json.dumps(payload)};\nconst KEY=\"p99b_counts\";\n"
    if "const KEY" in tail.split("let i=0")[0]:
        tail = tail.split("\n", 1)[1]
    PAGE.write_text(head + script + tail, encoding="utf-8")
    print(f"  {len(payload)} frames -> {PAGE} ({PAGE.stat().st_size / 1e6:.1f} MB)")
    print(f"  selection -> {ROOT / 'p99b_frames.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
