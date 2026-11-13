"""Analyze one recorded video, for the dashboard's Analyze a video page (D34).

    python scripts/analyze_video.py --video clip.mp4 --profile cameras/150th_Eastgate.json --out clip.analysis.json

It runs the deployed path's own parts over a whole recording, with no broker and
no server: the calibrated detector, `count_frame`, and the persistence and ridge
forecasters. So the page can jump anywhere in the video and stay in step with it,
which a replay in real time cannot.

**What is written is numbers.** Per 2 s sample: each lane's count, the boxes found
as normalised coordinates, the forecasts, and what the following 60 s then showed.
A frame is detected on and dropped (NFR-13), and the output names the clip by its
file name, never its folder.

**A camera needs a profile.** Its lanes and limits come from `cameras/`, because an
unknown video has no lanes and no calibrated levels (ADR-028). Which camera recorded
a video is declared by `--profile`, never inferred from its name.

**What it does not establish.** "Then" comes from the same detector's counts, so it
is not accuracy. A recording is not a live camera (S65), and nothing here drives a
signal (P97a).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edge.classes import load_itd_mapping  # noqa: E402
from edge.count_forecast import RidgeCountForecaster  # noqa: E402
from edge.persistence import WINDOW, PersistenceForecaster, classify  # noqa: E402
from edge.profile import CameraProfile, ProfileError, load_profile  # noqa: E402
from edge.run import COUNTING_FILE, PILOT, YoloDetector, clip_duration, file_frames, load_counting  # noqa: E402
from edge.samples import STEP_S  # noqa: E402
from mfstnet.corpus.counting import Detection, count_frame  # noqa: E402
from mfstnet.corpus.lanes import LaneCentres, assign_to_lane  # noqa: E402
from mfstnet.corpus.pcu import ASSUMED, pcu_of  # noqa: E402
from scripts.console import use_utf8  # noqa: E402

KIND = "stms-video-analysis"
SCHEMA = 2
MIN_S = 300.0                    # as demo_live: the forecasters need history first
RIDGE_SPEC = PILOT / "p105_ridge_v1.json"
PROGRESS_EVERY = 5               # samples between machine-readable progress lines (10 s of video)


def progress_line(ts: float, duration: float) -> str:
    """What the workbench reads (D40): how far through the video, of how long."""
    return f"PROGRESS {ts:.1f} {duration:.1f}"


def pcu_table(names: Iterable[str]) -> dict:
    """D35: PCU for the detector's own class names, through the project's one class
    mapping. A class with no decided PCU is left out, so the page says Not available
    rather than guessing, and an analysis never fails over a display value."""
    mapping = load_itd_mapping(spelling="dataset")
    weights, assumed = {}, []
    for name in sorted(set(names)):
        ours = mapping.get(name) or name
        try:
            weights[name] = pcu_of(ours)
        except KeyError:
            continue
        if ours in ASSUMED:
            assumed.append(name)
    return {"weights": weights, "assumed": assumed,
            "source": "Indo-HCM 2017, intermediate/two-lane urban (ADR-017, proposed, not signed off by the guide)"}


def analyse(frames: Iterable[tuple[float, object]], detector: Callable[[object], list[Detection]],
            profile: CameraProfile, *, ridge_spec: Path, min_confidence: float, clip: str,
            duration_s: float | None, on_sample: Callable[[float], None] | None = None) -> dict:
    """Frames in, one analysis out. Takes its parts as arguments, so it is
    testable with no video and no detector."""
    lanes = LaneCentres(names=tuple(name for name, _ in profile.lanes),
                        centres=tuple(centre for _, centre in profile.lanes),
                        max_radius=profile.max_radius)
    persistence = PersistenceForecaster(profile.spec_path, profile.spec_key, profile.lane_map)
    ridge = RidgeCountForecaster(ridge_spec, profile.lane_map)
    samples: list[dict] = []
    seen_classes: set[str] = set()
    for ts, frame in frames:
        detections = detector(frame)
        del frame                                # NFR-13: counted, then dropped
        counted = count_frame(detections, lanes, min_confidence=min_confidence)
        totals = {lane: int(n) for lane, n in counted.per_lane.items()}
        seen_classes.update(d.cls for d in detections)
        level = persistence.step(totals, ts)
        number = ridge.step(totals, ts)
        samples.append({
            "t": ts, "counts": totals,
            "boxes": [[round(d.x1, 4), round(d.y1, 4), round(d.x2, 4), round(d.y2, 4)] for d in detections],
            # D35: parallel to boxes. The lane is the one this detection was counted in.
            "detections": [[d.cls, round(d.confidence, 3),
                            assign_to_lane(d.centroid, lanes) if d.confidence >= min_confidence else None]
                           for d in detections],
            "level": {a: c.value for a, c in level.predictions.items()} if level else None,
            "number": dict(number.counts) if number else None,
            "then": None})
        if on_sample:
            on_sample(ts)
    # What each forecast's next 60 s then showed: the mean of the following 30
    # samples, classed by the same limits. The same target as edge/check.py.
    for k, sample in enumerate(samples):
        after = samples[k + 1:k + 1 + WINDOW]
        if len(after) == WINDOW:
            means = {lane: sum(s["counts"][lane] for s in after) / WINDOW for lane in profile.lane_map}
            sample["then"] = {profile.lane_map[lane]: {"level": classify(m, persistence.low, persistence.med).value,
                                                       "number": round(m, 4)}
                              for lane, m in means.items()}
    return {
        "kind": KIND, "schema": SCHEMA, "camera": profile.camera_id, "clip": clip,
        "step_s": STEP_S, "duration_s": duration_s if duration_s is not None else len(samples) * STEP_S,
        "lanes": [{"name": name, "centre": list(centre), "approach": profile.lane_map[name]}
                  for name, centre in profile.lanes],
        "min_confidence": min_confidence,
        "pcu": pcu_table(seen_classes),
        "limits": {"low": persistence.low, "med": persistence.med},
        "known_limits": list(profile.limitations),
        "directions_verified": profile.directions_verified,
        "models": {"level": persistence.model_id, "number": ridge.model_id},
        "samples": samples,
    }


def main(argv: list[str] | None = None) -> int:
    use_utf8()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True, help="the camera that recorded it, from cameras/")
    ap.add_argument("--out", type=Path, required=True, help="the results file the page opens")
    ap.add_argument("--force", action="store_true", help="replace an existing results file")
    ap.add_argument("--progress", action="store_true",
                    help="also print 'PROGRESS <t> <duration>' every 10 s of video, for the workbench (D40)")
    args = ap.parse_args(argv)

    if not args.video.is_file():
        print(f"no such video: {args.video}", file=sys.stderr)
        return 1
    if args.out.exists() and not args.force:
        print(f"{args.out} exists; pass --force to replace it", file=sys.stderr)
        return 1
    try:
        profile = load_profile(args.profile)
    except ProfileError as error:
        print(f"profile refused: {error}", file=sys.stderr)
        return 1
    duration = clip_duration(str(args.video))
    if duration is None or duration < MIN_S:
        print(f"the video must be at least {MIN_S / 60:.0f} minutes long, because the forecasts need "
              f"history first; this one reads as {duration}", file=sys.stderr)
        return 1
    calibrated_on = profile.calibrated_on
    if calibrated_on and calibrated_on in args.video.stem:
        print("note: this is the hour this camera's limits were calibrated on, so its levels flatter it")

    weights, conf, imgsz = load_counting(COUNTING_FILE)
    detector = YoloDetector(weights, conf, imgsz)
    shown = {"at": -60.0}

    def progress(ts: float) -> None:
        if args.progress and round(ts / STEP_S) % PROGRESS_EVERY == 0:
            print(progress_line(ts, duration), flush=True)
        if ts - shown["at"] >= 60:
            shown["at"] = ts
            print(f"  {ts / 60:5.1f} of {duration / 60:.1f} min", flush=True)

    result = analyse(file_frames(str(args.video)), detector, profile, ridge_spec=RIDGE_SPEC,
                     min_confidence=conf, clip=args.video.stem, duration_s=round(duration, 2),
                     on_sample=progress)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out}: {len(result['samples'])} samples. Open it on the dashboard's Analyze a video page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
