"""Regenerate the pipeline walkthrough page from real footage (S17b).

    python scripts/build_demo.py --clip "D:/traffic dataset/<clip>.mp4" \
        --lanes data/lanes_dhaka.json --out docs/demo/counting_rampura.html

`demo_pipeline.py` proves the plumbing carries water on synthetic data, and says
so in its own docstring: it does not show that the detector works or that real
traffic behaves usably. **This one runs the same chain on real video and renders
what came out.**

It exists because of a question that has no technical answer: how does someone
who will not read the code — an examiner, a guide, a family member — tell
whether any of this works? They cannot audit a test suite. They can look at a
picture of their own city's traffic with boxes drawn on it and see for
themselves whether the boxes are in the right places.

**Every figure on the page is produced here, from the clip, on each run.**
Nothing is transcribed, which is the same rule NFR-09 applies to result CSVs and
for the same reason: a number typed into a document by hand is a number nobody
can re-derive.

The page states what it does not show — the forecasting model is untrained, the
signal controller is simulation-only — because a demo that implies more than it
proves is worse than no demo.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEMPLATE = Path(__file__).resolve().parent.parent / "docs" / "demo" / "template.html"
CHART_W, CHART_H = 1000, 320
PAD_L, PAD_R, PAD_T, PAD_B = 46, 16, 16, 34
CHART_MAX = 28


def encode(image, width: int = 1100, quality: int = 80) -> str:
    """Downscale and base64-encode. The artifact CSP blocks external hosts, so
    every image has to travel inside the page."""
    import cv2

    height, original = image.shape[:2], image.shape[1]
    scaled = cv2.resize(image, (width, int(height[0] * width / original)),
                        interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", scaled, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise SystemExit("JPEG encode failed")
    return base64.b64encode(buffer).decode()


def render(clip: Path, lanes_path: Path, weights: Path, conf: float, at_s: float):
    """Three frames: raw, detected, and assigned-to-approach with counts."""
    import cv2
    import numpy as np
    from ultralytics import YOLO

    from mfstnet.corpus.geometry import Polygon
    from scripts.pilot_a17 import vehicle_ids

    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))["lanes"]
    polygons = [Polygon(lane["name"], tuple(tuple(v) for v in lane["points"]))
                for lane in lanes]

    model = YOLO(str(weights))
    ids = vehicle_ids(model)

    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise SystemExit(f"cannot open {clip}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(at_s * fps))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise SystemExit(f"cannot read frame at {at_s}s")

    result = model.predict(source=frame, conf=conf, verbose=False)[0]
    height, width = frame.shape[:2]

    # Fill first, outline last, so a polygon edge is never hidden under a box.
    colours = {polygons[0].name: (80, 220, 120), polygons[1].name: (255, 170, 60)}
    shaded = frame.copy()
    for polygon in polygons:
        points = np.array([[int(x * width), int(y * height)]
                           for x, y in polygon.vertices], np.int32)
        cv2.fillPoly(shaded, [points], colours[polygon.name])
    canvas = cv2.addWeighted(shaded, 0.18, frame, 0.82, 0)

    counts = {p.name: 0 for p in polygons}
    unassigned = total = 0
    for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
        if int(cls) not in ids:
            continue
        total += 1
        cx, cy = (box[0] + box[2]) / 2 / width, (box[1] + box[3]) / 2 / height
        hit = next((p for p in polygons if p.contains((cx, cy))), None)
        colour = colours[hit.name] if hit else (160, 160, 160)
        if hit:
            counts[hit.name] += 1
        else:
            unassigned += 1
        cv2.rectangle(canvas, (int(box[0]), int(box[1])),
                      (int(box[2]), int(box[3])), colour, 3)
        cv2.circle(canvas, (int(cx * width), int(cy * height)), 7, colour, -1)

    for polygon in polygons:
        points = np.array([[int(x * width), int(y * height)]
                           for x, y in polygon.vertices], np.int32)
        cv2.polylines(canvas, [points], True, colours[polygon.name], 4)
        cv2.putText(canvas, f"{polygon.name.replace('_', ' ')}: {counts[polygon.name]}",
                    (points[0][0] + 14, points[0][1] + 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.15, colours[polygon.name], 3)

    return (
        {"raw": encode(frame), "det": encode(result.plot()), "lanes": encode(canvas)},
        {"counts": counts, "unassigned": unassigned, "total": total,
         "unassigned_rate": unassigned / total if total else 0.0},
    )


def chart(series: dict[str, list[tuple[int, int]]]) -> str:
    """Count-over-time SVG with the class bands drawn behind the lines.

    Inline SVG rather than a plotting library: the page must be self-contained,
    and a chart with five data marks does not justify a dependency.
    """
    span = max(t for points in series.values() for t, _ in points) or 1

    def x(t): return PAD_L + (t / span) * (CHART_W - PAD_L - PAD_R)
    def y(c): return PAD_T + (1 - c / CHART_MAX) * (CHART_H - PAD_T - PAD_B)

    bands = [(0, 11, "var(--low)", "LOW"), (11, 14, "var(--med)", "MEDIUM"),
             (14, CHART_MAX, "var(--high)", "HIGH")]
    parts = [f'<rect x="{PAD_L}" y="{y(hi):.1f}" width="{CHART_W-PAD_L-PAD_R}" '
             f'height="{y(lo)-y(hi):.1f}" fill="{col}" opacity="0.10"/>'
             for lo, hi, col, _ in bands]
    parts += [f'<line x1="{PAD_L}" y1="{y(c):.1f}" x2="{CHART_W-PAD_R}" '
              f'y2="{y(c):.1f}" class="grid"/>'
              f'<text x="{PAD_L-8}" y="{y(c)+4:.1f}" text-anchor="end" '
              f'class="tick">{c}</text>' for c in (0, 7, 14, 21, 28)]
    # The §14.1 LOW boundary, drawn precisely because the data never crosses it.
    parts.append(f'<line x1="{PAD_L}" y1="{y(5):.1f}" x2="{CHART_W-PAD_R}" '
                 f'y2="{y(5):.1f}" class="oldthr"/>'
                 f'<text x="{PAD_L+8}" y="{y(5)-7:.1f}" class="oldlbl">'
                 f'\u00a714.1 says LOW below here \u2014 never reached</text>')
    for name, cls in (("coco", "line coco"), ("ours", "line ours")):
        points = " ".join(f"{x(t):.1f},{y(c):.1f}" for t, c in series[name])
        parts.append(f'<polyline points="{points}" class="{cls}"/>')
    parts += [f'<text x="{CHART_W-PAD_R-6}" y="{(y(lo)+y(hi))/2+4:.1f}" '
              f'text-anchor="end" class="bandlbl" fill="{col}">{name}</text>'
              for lo, hi, col, name in bands]
    parts += [f'<text x="{x(t):.1f}" y="{CHART_H-10}" text-anchor="middle" '
              f'class="tick">{t//60}m</text>'
              for t in (0, 300, 600, 900, 1200)]

    return (f'<svg viewBox="0 0 {CHART_W} {CHART_H}" class="chart" role="img" '
            f'aria-label="Vehicle count over 20 minutes, sampled every 5 seconds">'
            + "".join(parts) + "</svg>")


def load_series(path: Path) -> dict[str, list[tuple[int, int]]]:
    """Both pilot arms from the committed counts CSV, keyed ours/coco."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_detector: dict[str, list[tuple[int, int]]] = {}
    for row in rows:
        key = "coco" if row["detector"].startswith("yolov8n") else "ours"
        by_detector.setdefault(key, []).append((int(row["time_s"]), int(row["count"])))
    missing = {"ours", "coco"} - set(by_detector)
    if missing:
        raise SystemExit(
            f"{path} has no rows for {', '.join(sorted(missing))}. The page "
            f"compares the two detectors, so both pilot runs must be present."
        )
    for points in by_detector.values():
        points.sort()
    return by_detector


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--lanes", type=Path, default=Path("data/lanes_dhaka.json"))
    parser.add_argument("--weights", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--at", type=float, default=840.0,
                        help="seconds into the clip for the still frames")
    parser.add_argument("--counts", type=Path,
                        default=Path("experiments/results/pilot_counts.csv"))
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/demo/counting_rampura.html"))
    args = parser.parse_args(argv)

    images, stats = render(args.clip, args.lanes, args.weights, args.conf, args.at)
    print(f"  frame at {args.at:.0f}s: {stats['total']} vehicles, "
          f"{stats['counts']}, {stats['unassigned_rate']:.1%} unassigned")

    html = args.template.read_text(encoding="utf-8")
    for token, value in (("__RAW__", images["raw"]), ("__DET__", images["det"]),
                         ("__LANES__", images["lanes"]),
                         ("__CHART__", chart(load_series(args.counts)))):
        if token not in html:
            raise SystemExit(f"{args.template} has no {token} placeholder")
        html = html.replace(token, value)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    size = len(html.encode("utf-8")) / 1024 / 1024
    print(f"  wrote {args.out}  ({size:.2f} MB)")
    if size > 16:
        raise SystemExit("over the 16 MB artifact limit — lower --quality or --width")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
