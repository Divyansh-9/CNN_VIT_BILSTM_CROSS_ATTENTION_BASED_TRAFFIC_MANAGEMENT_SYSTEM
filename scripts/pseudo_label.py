"""Distil ITD-x into our YOLOv8s by pseudo-labelling real deployment footage.

    python scripts/pseudo_label.py --clip "D:/traffic dataset/<clip>.mp4" \
        --out data/pseudo/dhaka --every 15 --max-frames 4000

**The idea this implements, and the one it replaces.** Using ITD as a starting
point and fine-tuning ours from it is not possible: ITD is a YOLOv8x-class model
and ours is a YOLOv8s. Measured, `0.0%` of our parameters have a
shape-compatible counterpart in theirs — 355 tensors against 1015, channel
widths of 256 where theirs are 768. There is nothing to transfer.

What *is* possible is the thing that idea was reaching for. A large accurate
teacher can hand its knowledge to a small fast student, and the practical form
here is **hard-label distillation**: run the teacher offline over unlabelled
video, keep its detections as labels, and train the student on them. The student
keeps its own architecture and therefore its own latency — 12.5 fps against the
teacher's 0.8 — while learning from a detector that finds 11-27% more vehicles.

**The part that makes this better than a straight accuracy trade.** The frames
we pseudo-label are *our actual deployment footage* — fixed elevated cameras,
the exact domain A31 identified as the gap. Our detector was trained on IDD
(largely dashcam) and BMD-45 (elevated stills). This is self-training on the
target domain at zero annotation cost, which is a domain-adaptation win the
teacher's raw accuracy does not by itself provide.

## The class trap, and why this script is not a one-liner

ITD has **no `e_rickshaw` and no `cattle`**. Pseudo-labelling naively would
teach our student that e-rickshaws are auto-rickshaws and that cattle are
nothing — actively destroying two India-specific classes the project added on
purpose (PRD §5).

So labels are **merged, not copied**: ITD supplies the six classes it knows, our
own detector supplies `e_rickshaw` and `cattle` only, and its boxes are dropped
where they duplicate an ITD box by IoU. Neither model is trusted outside what it
was trained to see.

## This must be measured before it is adopted

Pseudo-labels inherit the teacher's errors. ITD detects *more*, and without
ground truth "more" is not "better" — it could be over-detection, in which case
this teaches the student to hallucinate. The acceptance criteria are
pre-registered in the ADR and evaluated on **real labelled test splits**, never
on pseudo-labels.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ITD class name -> our class name. `bicycle` has no counterpart in our label
# set and is dropped rather than folded into something it is not.
ITD_TO_OURS = {
    "two wheeler": "motorcycle",
    "autorickshaw": "auto_rickshaw",
    "car": "car",
    "bus": "bus",
    "LCV": "truck",
    "truck": "truck",
    "pedestrain": "pedestrian",      # their spelling
}

# Only these come from our own detector. Everything else it might say is
# ignored — the teacher is better at the classes they share, which is the whole
# reason for doing this.
OURS_ONLY = ("e_rickshaw", "cattle")

# Classes both models can see AND that occupy carriageway space. Used for the
# disagreement score, which exists to rank frames for human verification of the
# corpus — where only vehicles matter.
SHARED_VEHICLES = frozenset(set(ITD_TO_OURS.values()) - {"pedestrian"})


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / union if union > 0 else 0.0


def to_yolo(box, width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    return (((x1 + x2) / 2 / width), ((y1 + y2) / 2 / height),
            ((x2 - x1) / width), ((y2 - y1) / height))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--teacher", type=Path,
                        default=Path("models/external/best_xl_ITD_v1.2.pt"))
    parser.add_argument("--student", type=Path,
                        default=Path("models/detector/s14_yolov8s_joint_best.pt"))
    parser.add_argument("--teacher-conf", type=float, default=0.45)
    parser.add_argument("--ours-conf", type=float, default=0.55,
                        help="higher: our model only contributes classes the "
                             "teacher cannot see, so it must be confident")
    parser.add_argument("--teacher-imgsz", type=int, default=992)
    parser.add_argument("--every", type=int, default=15,
                        help="sample every Nth frame; consecutive frames are "
                             "near-duplicates and inflate the set without "
                             "adding information")
    parser.add_argument("--max-frames", type=int, default=4000)
    parser.add_argument("--min-boxes", type=int, default=2,
                        help="skip near-empty frames — they teach little and "
                             "shift the background/foreground balance")
    parser.add_argument("--max-box-area", type=float, default=0.05,
                        help="reject boxes covering more than this fraction of "
                             "the frame. NOT cosmetic — see the note below")
    args = parser.parse_args(argv)

    # Why --max-box-area exists, measured rather than assumed. On 12 sampled
    # frames of elevated Dhaka footage the teacher's box areas were:
    #
    #   car            median 0.0074   p95 0.0250
    #   auto_rickshaw  median 0.0059   p95 0.0236
    #   truck          median 0.1304   p95 0.2273
    #   bus            median 0.1174   p95 0.1806
    #
    # A truck is two to three times a car's footprint, not eighteen. Every
    # truck and bus box was oversized, and one rendered as a red rectangle over
    # a quarter of the frame covering a tree and an empty road.
    #
    # A giant false box is far worse in training than a missed one: it dominates
    # the regression loss and teaches the student that vehicles can be enormous.
    # Filtering is therefore part of the method, not tidying — and the count it
    # removes is printed so the filter cannot silently do too much.

    import cv2
    from ultralytics import YOLO

    # No vehicle_ids here on purpose: this script maps ITD's taxonomy to ours
    # explicitly through ITD_TO_OURS, which is why P24's inclusion-list defect
    # never reached the pseudo-labels. An unused import kept "for parity" made
    # that audit harder than it should have been, so it is gone.

    teacher = YOLO(str(args.teacher))
    student = YOLO(str(args.student))
    ours_names = {name: index for index, name in student.names.items()}

    missing = sorted(set(ITD_TO_OURS.values()) | set(OURS_ONLY) - set(ours_names))
    missing = [m for m in missing if m not in ours_names]
    if missing:
        raise SystemExit(f"student has no class(es) {missing}; refusing to write "
                         f"labels it cannot represent")

    images = args.out / "images"
    labels = args.out / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(args.clip))
    if not capture.isOpened():
        raise SystemExit(f"cannot open {args.clip}")

    kept = index = 0
    tally: dict[str, int] = {}
    added_by_us = 0
    rejected: dict[str, int] = {}
    disagreements: list[dict] = []
    while kept < args.max_frames:
        ok, frame = capture.read()
        if not ok:
            break
        if index % args.every:
            index += 1
            continue
        index += 1
        height, width = frame.shape[:2]

        result = teacher.predict(source=frame, conf=args.teacher_conf,
                                 imgsz=args.teacher_imgsz, verbose=False)[0]
        rows: list[str] = []
        taken: list[tuple] = []
        taken_names: list[str] = []
        for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
            name = ITD_TO_OURS.get(teacher.names[int(cls)])
            if name is None:
                continue
            cx, cy, bw, bh = to_yolo(box, width, height)
            if bw * bh > args.max_box_area:
                rejected[name] = rejected.get(name, 0) + 1
                continue
            rows.append(f"{ours_names[name]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            taken.append(tuple(box))
            taken_names.append(name)
            tally[name] = tally.get(name, 0) + 1

        # Run the student at the TEACHER's threshold, then filter. Predicting at
        # `ours_conf` directly would make the disagreement score below partly a
        # measurement of the gap between two thresholds rather than of two
        # models conflicting — which it was, until the pilot showed a median
        # disagreement of 0.600 that mostly evaporated once both models were
        # read at the same confidence.
        mine = student.predict(source=frame, conf=args.teacher_conf, verbose=False)[0]
        for box, cls, score in zip(mine.boxes.xyxy.tolist(),
                                   mine.boxes.cls.tolist(),
                                   mine.boxes.conf.tolist()):
            name = student.names[int(cls)]
            if name not in OURS_ONLY or score < args.ours_conf:
                continue
            if any(iou(tuple(box), other) > 0.5 for other in taken):
                continue          # the teacher already called this something
            cx, cy, bw, bh = to_yolo(box, width, height)
            if bw * bh > args.max_box_area:
                rejected[name] = rejected.get(name, 0) + 1
                continue
            rows.append(f"{ours_names[name]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            tally[name] = tally.get(name, 0) + 1
            added_by_us += 1

        if len(rows) < args.min_boxes:
            continue

        stem = f"{args.clip.stem[:28].replace(' ', '_')}_{index:07d}"
        cv2.imwrite(str(images / f"{stem}.jpg"), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        (labels / f"{stem}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")

        # Free by-product of a pass that already ran both models: where do they
        # disagree? A9/A32 requires the test split to be human-verified, and
        # verification time is the scarcest resource in the project — the
        # feasibility audit put annotation at 3x the original estimate.
        #
        # Two independently trained detectors (different group, different data)
        # disagreeing is a much better predictor of a hard frame than random
        # sampling. Ranking by this sends the human where the models conflict.
        # Running the teacher a second time to get it would cost 1.2 s/frame.
        # Vehicles only. `pedestrian` is 38% of the teacher's boxes and a class
        # our detector rarely fires on, so including it made the score mostly a
        # measurement of pedestrian recall — median 0.520 — when what a corpus
        # label depends on is the vehicle count. Pedestrians carry 0 PCU
        # (ADR-017) and never enter a congestion label.
        teacher_shared = sum(1 for name in taken_names if name != "pedestrian")
        student_shared = sum(
            1 for cls in mine.boxes.cls.tolist()
            if student.names[int(cls)] in SHARED_VEHICLES)
        denominator = max(teacher_shared, student_shared, 1)
        disagreements.append({
            "frame": stem,
            "time_s": round(index / (capture.get(cv2.CAP_PROP_FPS) or 25.0), 1),
            "teacher_boxes": teacher_shared,
            "student_boxes": student_shared,
            "count_gap": abs(teacher_shared - student_shared),
            "disagreement": round(
                abs(teacher_shared - student_shared) / denominator, 4),
        })

        kept += 1
        if kept % 100 == 0:
            print(f"  {kept} frames labelled", flush=True)

    capture.release()
    total = sum(tally.values())
    print(f"\n  {kept} frames, {total} boxes")
    for name, number in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {name:<16}{number:>7}  {number/total:>6.1%}")
    if rejected:
        dropped = sum(rejected.values())
        print(f"\n  REJECTED {dropped} box(es) over {args.max_box_area:.0%} "
              f"of frame area:")
        for name, number in sorted(rejected.items(), key=lambda kv: -kv[1]):
            print(f"    {name:<16}{number:>7}")
        if dropped > 0.10 * (total + dropped):
            print("    More than 10% of boxes rejected. Either --max-box-area "
                  "is too tight for this view, or the teacher is out of domain "
                  "here. LOOK AT A LABELLED FRAME before training on this.")

    print(f"\n  contributed by our detector (teacher-blind classes): {added_by_us}")
    if added_by_us == 0:
        print("  NOTE: no e_rickshaw or cattle found. On footage containing "
              "them this merge is what protects those classes; here it was a "
              "no-op and the labels are the teacher's alone.")
    if disagreements:
        import csv

        disagreements.sort(key=lambda row: -row["disagreement"])
        target = args.out / "disagreement.csv"
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(disagreements[0]))
            writer.writeheader()
            writer.writerows(disagreements)
        top = disagreements[:max(1, len(disagreements) // 10)]
        print(f"\n  disagreement ranking -> {target.name}")
        print(f"    median {disagreements[len(disagreements)//2]['disagreement']:.3f}"
              f"   worst {disagreements[0]['disagreement']:.3f}"
              f"   (frame {disagreements[0]['frame'][-7:]}, "
              f"teacher {disagreements[0]['teacher_boxes']} vs "
              f"student {disagreements[0]['student_boxes']})")
        print(f"    verify the top {len(top)} frames first (A32) — that is where "
              f"two independently trained detectors conflict")

    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
