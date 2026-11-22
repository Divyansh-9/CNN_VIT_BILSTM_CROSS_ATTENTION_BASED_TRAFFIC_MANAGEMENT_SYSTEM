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
from statistics import fmean
from pathlib import Path
from typing import Callable, Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edge.classes import load_video_mapping  # noqa: E402
from edge.count_forecast import RidgeCountForecaster  # noqa: E402
from edge.persistence import WINDOW, PersistenceForecaster, classify  # noqa: E402
from edge.profile import CameraProfile, ProfileError  # noqa: E402
from edge.run import PILOT, clip_duration  # noqa: E402
from edge.samples import STEP_S  # noqa: E402
from mfstnet.corpus.counting import Detection, count_frame  # noqa: E402
from mfstnet.corpus.lanes import LaneCentres, assign_to_lane  # noqa: E402
from mfstnet.corpus.pcu import ASSUMED, pcu_of  # noqa: E402
from scripts.console import use_utf8  # noqa: E402
from scripts.tracked_video import TrackedVideo, detector_settings, policy_settings  # noqa: E402
from scripts.recording_profile import WHOLE_FRAME, load_recording_profile  # noqa: E402
from scripts.video_traffic import WINDOW_S, summarize  # noqa: E402

KIND = "stms-video-analysis"
SCHEMA = 2
MIN_S = 2.0                      # shorter recordings still show counts; forecasts warm up normally
RIDGE_SPEC = PILOT / "p105_ridge_v1.json"
VIDEO_RIDGE_WEIGHT = 0.7


def blended_video_count(ridge_count, history_mean):
    """Dampen large swings in the 60-second mean occupancy forecast."""
    return round(VIDEO_RIDGE_WEIGHT * ridge_count + (1 - VIDEO_RIDGE_WEIGHT) * history_mean, 4)


def progress_line(ts: float, duration: float) -> str:
    """What the workbench reads (D40): how far through the video, of how long."""
    return f"PROGRESS {ts:.1f} {duration:.1f}"


def pcu_table(names: Iterable[str]) -> dict:
    """D35: PCU for the detector's own class names, through the project's one class
    mapping. A class with no decided PCU is left out, so the page says Not available
    rather than guessing, and an analysis never fails over a display value."""
    mapping = load_video_mapping()
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


class SampleAnalyzer:
    def __init__(self, profile, ridge_spec, min_confidence):
        self.lanes = LaneCentres(names=tuple(name for name, _ in profile.lanes),
                        centres=tuple(centre for _, centre in profile.lanes),
                        max_radius=profile.max_radius)
        whole = profile.camera_id == WHOLE_FRAME
        self.persistence = None if whole else PersistenceForecaster(profile.spec_path, profile.spec_key, profile.lane_map)
        self.ridge = None if whole else RidgeCountForecaster(ridge_spec, profile.lane_map)
        self.min_confidence = min_confidence

    def step(self, ts, detections):
        counted = count_frame(detections, self.lanes, min_confidence=self.min_confidence)
        totals = {lane: int(n) for lane, n in counted.per_lane.items()}
        level = self.persistence.step(totals, ts) if self.persistence else None
        number = self.ridge.step(totals, ts) if self.ridge else None
        forecast = {
            approach: blended_video_count(number.counts[approach], fmean(self.ridge.buffer.series(lane)))
            for lane, approach in self.ridge.lane_to_approach.items()
        } if number else None
        return {
            "t": ts, "counts": totals,
            "boxes": [[round(d.x1, 4), round(d.y1, 4), round(d.x2, 4), round(d.y2, 4)] for d in detections],
            # D35: parallel to boxes. The lane is the one this detection was counted in.
            "detections": [[d.cls, round(d.confidence, 3),
                            assign_to_lane(d.centroid, self.lanes) if d.confidence >= self.min_confidence else None]
                           for d in detections],
            "level": {a: c.value for a, c in level.predictions.items()} if level else None,
            "number": forecast,
            "then": None}


def analyse(frames: Iterable[tuple[float, object]], detector: Callable[[object], list[Detection]],
            profile: CameraProfile, *, ridge_spec: Path, min_confidence: float, clip: str,
            duration_s: float | None, on_sample: Callable[[float], None] | None = None, on_frame=None) -> dict:
    """Frames in, one analysis out. Both sources use the same per-sample models."""
    analyzer = SampleAnalyzer(profile, ridge_spec, min_confidence)
    samples: list[dict] = []
    seen_classes: set[str] = set()
    for ts, frame in frames:
        detections = detector(frame)
        del frame
        samples.append(analyzer.step(ts, detections))
        seen_classes.update(d.cls for d in detections)
        if on_sample:
            on_sample(ts)
        if on_frame:
            on_frame(analyzer, samples, seen_classes)
    persistence = analyzer.persistence
    # What each forecast's next 60 s then showed: the mean of the following 30
    # samples, classed by the same limits. The same target as edge/check.py.
    for k, sample in enumerate(samples):
        after = samples[k + 1:k + 1 + WINDOW]
        if persistence and len(after) == WINDOW:
            means = {lane: sum(s["counts"][lane] for s in after) / WINDOW for lane in profile.lane_map}
            sample["then"] = {profile.lane_map[lane]: {"level": classify(m, persistence.low, persistence.med).value,
                                                       "number": round(m, 4)}
                              for lane, m in means.items()}
    return analysis_result(profile, analyzer, clip, duration_s, samples, seen_classes)


def analysis_result(profile, analyzer, clip, duration_s, samples, seen_classes):
    persistence = analyzer.persistence
    return {
        "kind": KIND, "schema": SCHEMA, "camera": profile.camera_id, "clip": clip,
        "step_s": STEP_S, "duration_s": duration_s if duration_s is not None else len(samples) * STEP_S,
        "lanes": [{"name": name, "centre": list(centre), "approach": profile.lane_map[name]}
                  for name, centre in profile.lanes],
        "min_confidence": analyzer.min_confidence,
        "pcu": pcu_table(seen_classes),
        "limits": {"low": persistence.low, "med": persistence.med} if persistence else {"low": 3, "med": 6},
        "known_limits": list(profile.limitations),
        "directions_verified": profile.directions_verified,
        "models": {"level": persistence.model_id if persistence else None,
                   "number": f"video-blend-70/30:{analyzer.ridge.model_id}" if analyzer.ridge else None},
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
    ap.add_argument("--monitor", action="store_true", help="publish analyzed samples while decoding")
    args = ap.parse_args(argv)

    if not args.video.is_file():
        print(f"no such video: {args.video}", file=sys.stderr)
        return 1
    if args.out.exists() and not args.force:
        print(f"{args.out} exists; pass --force to replace it", file=sys.stderr)
        return 1
    try:
        profile = load_recording_profile(args.profile)
    except ProfileError as error:
        print(f"profile refused: {error}", file=sys.stderr)
        return 1
    duration = clip_duration(str(args.video))
    if duration is None or duration < MIN_S:
        print(f"the recording needs at least {MIN_S:g} seconds of readable video; this one reads as {duration}", file=sys.stderr)
        return 1
    calibrated_on = None if profile.camera_id == WHOLE_FRAME else profile.calibrated_on
    if calibrated_on and calibrated_on in args.video.stem:
        print("note: this is the hour this camera's limits were calibrated on, so its levels flatter it")

    weights, conf, imgsz = detector_settings()
    video = TrackedVideo(args.video, profile, weights, imgsz, policy_settings())
    shown = {"at": -60.0}
    sent = {"crossings": 0, "alerts": set()}

    def progress(ts: float) -> None:
        if args.progress:
            print(progress_line(ts, duration), flush=True)
        if ts - shown["at"] >= 60:
            shown["at"] = ts
            print(f"  {ts / 60:5.1f} of {duration / 60:.1f} min", flush=True)

    def publish(analyzer, samples, seen_classes):
        sample = samples[-1]
        sample["track_ids"] = video.track_ids[-1]
        video.signal_sample(sample)
        watermark = sample["t"]
        crossing = video.crossings
        alerts = crossing.alerts
        if (watermark + STEP_S) % WINDOW_S == 0:
            prefix = {"samples": samples, "step_s": STEP_S, "duration_s": min(duration, watermark + STEP_S),
                      "lanes": [{"name": name, "approach": approach} for name, approach in profile.lane_map.items()]}
            alerts = summarize(prefix, crossing, video.policy, legacy_signal_advice=False)["alerts"]
        unseen = [event for event in alerts if event["id"] not in sent["alerts"]]
        update = {"sample": sample, "crossings": crossing.events[sent["crossings"]:], "alerts": unseen,
                  "processing": video.processing()}
        sent["crossings"] = len(crossing.events)
        sent["alerts"].update(event["id"] for event in unseen)
        if len(samples) == 1:
            head = analysis_result(profile, analyzer, args.video.stem, round(duration, 2), [], seen_classes)
            traffic = summarize({**head, "samples": samples}, crossing, video.policy, legacy_signal_advice=False)
            head["traffic"] = {**traffic, "crossings": [], "alerts": []}
            if video.signal_problem:
                head["traffic"]["signal_problem"] = video.signal_problem
            update["head"] = head
        print("MONITOR " + json.dumps(update, separators=(",", ":")), flush=True)

    result = analyse(video.frames(), lambda detections: detections, profile, ridge_spec=RIDGE_SPEC,
                     min_confidence=conf, clip=args.video.stem, duration_s=round(duration, 2),
                     on_sample=progress, on_frame=publish if args.monitor else None)
    if not result["samples"] or video.last_media_t < duration - max(3, duration * .01):
        print("The recording ended before its expected duration; use a complete or repaired file", file=sys.stderr)
        return 1
    video.finish(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out}: {len(result['samples'])} samples. Open it on the dashboard's Analyze a video page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
