"""V1 — build a blind labelling page for the pilot or the main set.

    python scripts/v1_label_page.py --set pilot
    python scripts/v1_label_page.py --set main --per-stratum N     # only after the V1 freeze

**What the page shows:**
- every labelled frame of every lane-moment in the set, **shuffled together**,
  so the 15 frames of one moment are never shown in sequence;
- the target lane's region tinted, using the nearest-centre-within-0.25 rule
  `mfstnet.corpus.lanes.assign_to_lane` applies to detections, with the rest
  of the frame dimmed;
- an opaque item id;
- the counting instructions;
- a count box, and an export button that downloads JSON.

**It never shows a detector count, a forecast, or a frame's place in time.**
`build_payload` receives no counts at all, and a test checks the page holds
none.

**Where things are written.** The page embeds footage, so it is written under
`data/v1/`, which is gitignored and never committed or published (the licence
is unresolved). The id-to-moment key goes beside it in `data/v1/`, kept from
the labellers. **Only ids leave `data/`.**
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

MANIFEST = Path("experiments/results/v1/v1_sample_manifest.json")
INSTRUCTIONS = Path("experiments/results/v1/COUNTING_INSTRUCTIONS.md")
FOOTAGE = Path("data/_bellevue/p105")
LANES_DIR = Path("data/_bellevue/p105/lanes_per_file")
OUT_DIR = Path("data/v1")
STEP_S, MAX_RADIUS, MAX_WIDTH = 2, 0.25, 960
ORDER_SEED = 20261018


def item_id(moment: str, sample: int) -> str:
    return hashlib.sha256(f"v1|{moment}|{sample}".encode()).hexdigest()[:10]


def items_for(moments: list[dict]) -> list[dict]:
    """Every (moment, labelled sample), shuffled so one moment's frames are scattered."""
    items = [{"id": item_id(m["id"], s), "moment": m["id"], "clip": m["clip"],
              "lane": m["lane"], "sample": s}
             for m in moments for s in m["labelled_samples"]]
    random.Random(ORDER_SEED).shuffle(items)
    return items


def highlight(frame, centres: list[dict], lane: str):
    """Tint the target lane's region; dim everything else."""
    import numpy as np

    h, w = frame.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    nx, ny = xs / w, ys / h
    best, owner = np.full((h, w), np.inf), np.full((h, w), "", dtype=object)
    for c in centres:
        d = np.hypot(nx - c["centre"][0], ny - c["centre"][1])
        closer = d < best
        best[closer] = d[closer]
        owner[closer] = c["name"]
    region = (owner == lane) & (best <= MAX_RADIUS)
    out = frame.astype(np.float32) * 0.35
    out[region] = frame[region].astype(np.float32) * 0.7 + np.array([40, 200, 255], np.float32) * 0.3
    return out.clip(0, 255).astype("uint8")


def build_payload(items: list[dict], frame_for) -> list[dict]:
    """Page entries: an opaque id, the target lane and an image. No counts, no time."""
    import cv2

    payload = []
    for it in items:
        frame, centres = frame_for(it["clip"], it["sample"])
        image = highlight(frame, centres, it["lane"])
        if image.shape[1] > MAX_WIDTH:                 # 109 MB at 720p; vehicles stay countable
            scale = MAX_WIDTH / image.shape[1]
            image = cv2.resize(image, (MAX_WIDTH, round(image.shape[0] * scale)),
                               interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        payload.append({"id": it["id"], "img": base64.b64encode(jpeg.tobytes()).decode()})
    return payload


def footage_frames(items: list[dict]):
    """Decode only the frames the set needs, forward, one pass per clip."""
    import cv2

    from mfstnet.corpus.video import iter_sampled_frames

    wanted: dict[str, set[int]] = {}
    for it in items:
        wanted.setdefault(it["clip"], set()).add(it["sample"])
    cache = {}
    for clip, samples in wanted.items():
        path = FOOTAGE / f"{clip}.mp4"
        fps = cv2.VideoCapture(str(path)).get(cv2.CAP_PROP_FPS)
        stride = max(1, round(fps * STEP_S))
        for index, frame in enumerate(iter_sampled_frames(path, stride, limit=max(samples) + 1)):
            if index in samples:
                cache[(clip, index)] = frame
    centres = {clip: json.loads((LANES_DIR / f"{clip}.json").read_text(encoding="utf-8"))["lanes"]
               for clip in wanted}

    def frame_for(clip, sample):
        return cache[(clip, sample)], centres[clip]

    return frame_for


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>V1 counting</title>
<style>body{{font:15px system-ui;margin:16px;background:#111;color:#eee}}img{{max-width:100%}}
.bar{{display:flex;gap:8px;align-items:center;margin:8px 0}}input{{width:5em;font-size:18px}}
details{{margin:8px 0}}pre{{white-space:pre-wrap}}</style></head><body>
<h3>V1 blind count &middot; set: {set_name}</h3>
<details><summary>Counting instructions (read before starting)</summary><pre>{instructions}</pre></details>
<div class="bar">Labeller: <input id="who" style="width:12em"> <span id="pos"></span></div>
<img id="img" alt="frame"><div class="bar">Vehicles in the highlighted region:
<input id="n" type="number" min="-1" inputmode="numeric"> <button id="next">Next</button>
<button id="back">Back</button> <button id="export">Export</button></div>
<script>const ITEMS={items};const KEY="v1_{set_name}_counts";
let s=JSON.parse(localStorage.getItem(KEY)||"{{}}");let i=0;
function show(){{const it=ITEMS[i];document.getElementById("img").src="data:image/jpeg;base64,"+it.img;
document.getElementById("n").value=(it.id in s)?s[it.id]:"";document.getElementById("pos").textContent=(i+1)+" / "+ITEMS.length;
document.getElementById("n").focus();}}
document.getElementById("next").onclick=()=>{{const v=document.getElementById("n").value;if(v===""){{alert("Enter a count, or -1 if unusable");return;}}
s[ITEMS[i].id]=parseInt(v,10);localStorage.setItem(KEY,JSON.stringify(s));if(i<ITEMS.length-1){{i++;show();}}}};
document.getElementById("back").onclick=()=>{{if(i>0){{i--;show();}}}};
document.getElementById("export").onclick=()=>{{const who=document.getElementById("who").value.trim();
if(!who){{alert("Enter your name first");return;}}const blob=new Blob([JSON.stringify({{set:"{set_name}",labeller:who,counts:s}})],{{type:"application/json"}});
const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="v1_{set_name}_"+who+".json";a.click();}};
show();</script></body></html>"""


def render(set_name: str, payload: list[dict], instructions: str) -> str:
    return PAGE.format(set_name=set_name, instructions=html.escape(instructions),
                       items=json.dumps(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", choices=("pilot", "main"), required=True)
    parser.add_argument("--per-stratum", type=int)
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.set == "pilot":
        moments = manifest["pilot"]
    else:
        if not Path("experiments/results/v1/PREREGISTRATION_V1.md").exists() or not args.per_stratum:
            raise SystemExit("the main set needs the frozen V1 pre-registration and --per-stratum")
        moments = [m for items in manifest["reserve"].values() for m in items[:args.per_stratum]]
    items = items_for(moments)
    payload = build_payload(items, footage_frames(items))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page = OUT_DIR / f"v1_{args.set}_page.html"
    page.write_text(render(args.set, payload, INSTRUCTIONS.read_text(encoding="utf-8")),
                    encoding="utf-8")
    key = OUT_DIR / f"v1_{args.set}_key.json"
    key.write_text(json.dumps({"items": items}, indent=1), encoding="utf-8")
    print(f"  {len(moments)} lane-moments, {len(items)} frames -> {page} "
          f"({page.stat().st_size / 1e6:.1f} MB); key -> {key} (keep from labellers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
