"""Week-2 pilot: count distribution and transition rate from one video.

    python scripts/pilot_counts.py path/to/video.mp4

Answers the two questions that can change the project, before any corpus is
built. Full reasoning in `mfstnet/corpus/pilot.py`.

Needs a working environment (S05): torch, ultralytics, opencv. It downloads
`yolov8n.pt` on first run — a COCO-pretrained model, which is deliberate. This
pilot measures the *traffic*, not our detector, so a general model is the right
instrument and no fine-tuning is needed.

**The video does not need to be perfect.** Ten to fifteen minutes from a window
or balcony overlooking any road is enough. It is never published and never
trained on — it is a measurement instrument (`kind: dev`).

Writes `experiments/results/pilot_counts.csv` and prints the verdicts. Commit
both: the measurement replaces the largest guess in the project.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mfstnet.corpus.pilot import analyse_counts  # noqa: E402
from mfstnet.corpus.windows import WindowGeometry  # noqa: E402

SAMPLE_EVERY_S = 5          # PRD §8.2
CONF_THRESHOLD = 0.25
VEHICLE_COCO = {"car", "motorcycle", "bus", "truck", "bicycle"}


def extract_counts(video_path: Path, roi: tuple[float, float, float, float] | None) -> list[int]:
    """Count vehicles every 5 seconds. Returns one count per sampled frame."""
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            f"missing dependency: {exc.name}\n"
            f"Run scripts/check_env.py — this needs the S05 environment.\n"
            f"  py -3.11 -m venv .venv\n"
            f"  .\\.venv\\Scripts\\Activate.ps1\n"
            f"  pip install torch==2.3.1 torchvision==0.18.1 "
            f"--index-url https://download.pytorch.org/whl/cu121\n"
            f"  pip install -r requirements.txt"
        ) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps * SAMPLE_EVERY_S)))
    print(f"  video     {video_path.name}")
    print(f"  fps       {fps:.1f}, {total} frames, {total / fps / 60:.1f} min")
    print(f"  sampling  every {step} frames ({SAMPLE_EVERY_S}s)")

    model = YOLO("yolov8n.pt")
    counts: list[int] = []
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            res = model(frame, conf=CONF_THRESHOLD, verbose=False)[0]
            n = 0
            h, w = frame.shape[:2]
            for box in res.boxes:
                if model.names[int(box.cls)] not in VEHICLE_COCO:
                    continue
                if roi is not None:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
                    if not (roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3]):
                        continue
                n += 1
            counts.append(n)
            if len(counts) % 20 == 0:
                print(f"  ... {len(counts)} samples, last count {n}")
        idx += 1

    cap.release()
    return counts


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    video = Path(sys.argv[1])
    if not video.exists():
        raise SystemExit(f"no such file: {video}")

    # Optional region of interest, normalised: x1 y1 x2 y2. Without it the whole
    # frame is counted, which is fine for a pilot — this measures whether the
    # thresholds fit the traffic, not per-lane accuracy.
    roi = tuple(float(a) for a in sys.argv[2:6]) if len(sys.argv) >= 6 else None  # type: ignore[assignment]

    print("=" * 72)
    print("WEEK-2 PILOT  ·  count distribution and transition rate")
    print("=" * 72)

    counts = extract_counts(video, roi)  # type: ignore[arg-type]
    g = WindowGeometry()

    print(f"\n  sampled   {len(counts)} frames")
    if len(counts) < g.min_frames:
        raise SystemExit(
            f"\nToo short. One prediction window needs {g.min_frames} samples "
            f"({g.min_clip_s}s of video); this gave {len(counts)}.\n"
            f"Record at least {g.min_clip_s // 60 + 1} minutes — 12+ is better."
        )

    result = analyse_counts(counts)
    print("\n" + "=" * 72)
    print(result.report())
    print("=" * 72)

    out = Path("experiments/results/pilot_counts.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["frame_index", "time_s", "count"])
        for i, c in enumerate(counts):
            w.writerow([i, i * SAMPLE_EVERY_S, c])
    print(f"\nraw counts written to {out}  — commit this (NFR-09)")

    if not (result.thresholds_usable and result.task_is_learnable):
        print("\nAt least one verdict FAILED. Do not build a corpus yet.")
        print("Record the numbers in BUILD-LOG S06 and decide before continuing.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
