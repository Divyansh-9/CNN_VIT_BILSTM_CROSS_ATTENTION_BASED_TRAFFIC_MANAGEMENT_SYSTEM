"""Week-2 pilot: count distribution and transition rate from one video.

    python scripts/pilot_counts.py path/to/video.mp4

Answers the two questions that can change the project, before any corpus is
built. Full reasoning in `mfstnet/corpus/pilot.py`.

    python scripts/pilot_counts.py clip.mp4 --weights models/detector/s14_yolov8s_joint_best.pt --conf 0.45

Needs a working environment (S05): torch, ultralytics, opencv. Defaults to COCO
`yolov8n`, downloaded on first run.

**Run it with our detector too, and compare.** COCO has no auto-rickshaw class,
so on South Asian traffic it is not a neutral instrument — it undercounts the
vehicles this project exists for, and the count distribution is what §14.1's
thresholds are judged against. COCO is the conservative floor; the gap between
the two is itself a measurement.

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
# Resolved by EXCLUSION, across three vocabularies (COCO, ours, ITD), because
# inclusion lists silently miscount when a model names things differently.
#
# The previous rule keyed on `"car" in names and "auto_rickshaw" not in names`
# and fell back to a fixed COCO list. ITD satisfies that test — it has `car` and
# spells the three-wheeler `autorickshaw` — so it would have been counted with
# the COCO list, missing `two wheeler` and `autorickshaw` entirely. On footage
# that is 45% two-wheelers and 21% auto-rickshaws that is not a small error; it
# would have dropped two thirds of the traffic and reported the remainder as a
# count distribution.
#
# Anything occupying carriageway space is a vehicle, cattle included. People and
# street furniture are not.
NON_VEHICLE = {
    "person", "pedestrian", "pedestrain",     # ITD's spelling of the last
    "rider",                                  # merged into motorcycle (ADR S09)
    "traffic_light", "traffic light", "traffic_sign", "traffic sign",
    "stop sign", "parking meter", "bench", "bird", "cat", "dog",
}


def extract_counts(
    video_path: Path,
    roi: tuple[float, float, float, float] | None,
    *,
    weights: str = "yolov8n.pt",
    conf: float = CONF_THRESHOLD,
    imgsz: int = 640,
) -> list[int]:
    """Count vehicles every 5 seconds. Returns one count per sampled frame.

    **On the choice of detector.** This script originally hardcoded COCO
    `yolov8n`, on the reasoning that the pilot measures the traffic rather than
    our detector, so a general model is the right instrument.

    That reasoning does not survive contact with South Asian traffic. COCO has
    **no auto-rickshaw class**, and on the elevated Dhaka footage the fine-tuned
    detector finds auto-rickshaws in most frames. An instrument blind to a major
    vehicle class does not measure the traffic neutrally — it undercounts
    exactly the traffic this project exists for, and the count distribution it
    reports is what §14.1's thresholds get judged against.

    So the detector is now a parameter. Run it both ways: COCO is the
    conservative floor, and the gap between them is itself a measurement.
    """
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

    model = YOLO(weights)
    # COCO names differ from ours; resolve the vehicle set from the model that
    # is actually loaded rather than assuming one vocabulary.
    names = set(model.names.values())
    wanted = names - NON_VEHICLE
    if not wanted:
        raise SystemExit(f"{weights} exposes no vehicle classes: {sorted(names)}")
    print(f"  detector  {weights}")
    print(f"  counting  {len(wanted)} classes at conf {conf}, imgsz {imgsz}: "
          f"{', '.join(sorted(wanted))}")
    ignored = sorted(names & NON_VEHICLE)
    if ignored:
        print(f"  ignoring  {', '.join(ignored)}")
    counts: list[int] = []
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            res = model(frame, conf=conf, imgsz=imgsz, verbose=False)[0]
            n = 0
            h, w = frame.shape[:2]
            for box in res.boxes:
                if model.names[int(box.cls)] not in wanted:
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
    # `--help` before the existence check: this is the script someone runs at
    # Week 2 with footage in hand, and "no such file: --help" is a bad first
    # impression of a tool whose job is to be trusted.
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(sys.argv) > 1 else 2

    argv = list(sys.argv[1:])
    weights, conf, imgsz = "yolov8n.pt", CONF_THRESHOLD, 640
    for flag, cast in (("--weights", str), ("--conf", float), ("--imgsz", int)):
        if flag in argv:
            i = argv.index(flag)
            value = cast(argv[i + 1])
            argv = argv[:i] + argv[i + 2:]
            if flag == "--weights":
                weights = value
            elif flag == "--conf":
                conf = value
            else:
                imgsz = value

    video = Path(argv[0])
    if not video.exists():
        raise SystemExit(f"no such file: {video}")

    # Optional region of interest, normalised: x1 y1 x2 y2. Without it the whole
    # frame is counted, which is fine for a pilot — this measures whether the
    # thresholds fit the traffic, not per-lane accuracy.
    roi = tuple(float(a) for a in argv[1:5]) if len(argv) >= 5 else None  # type: ignore[assignment]

    print("=" * 72)
    print("WEEK-2 PILOT  ·  count distribution and transition rate")
    print("=" * 72)

    counts = extract_counts(video, roi, weights=weights, conf=conf, imgsz=imgsz)  # type: ignore[arg-type]
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

    # Keyed on video+detector so a second pilot adds to this file instead of
    # deleting the first — the same hazard P19 found in the benchmark.
    from experiments.results_io import merge_by_key

    run_id = f"{video.stem[:40]}|{Path(weights).stem}"
    out = Path("experiments/results/pilot_counts.csv")
    merge_by_key(out, [
        {"run": run_id, "video": video.name, "detector": Path(weights).name,
         "conf": conf, "imgsz": imgsz, "frame_index": i, "time_s": i * SAMPLE_EVERY_S, "count": c}
        for i, c in enumerate(counts)
    ], run_id, key="run")
    print(f"\nraw counts written to {out}  — commit this (NFR-09)")

    if not (result.thresholds_usable and result.task_is_learnable):
        print("\nAt least one verdict FAILED. Do not build a corpus yet.")
        print("Record the numbers in BUILD-LOG S06 and decide before continuing.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
