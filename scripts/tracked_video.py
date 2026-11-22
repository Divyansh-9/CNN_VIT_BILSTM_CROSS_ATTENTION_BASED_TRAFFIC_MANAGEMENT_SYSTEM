"""Media-clock sampling and a fresh ByteTrack instance per recording."""

from __future__ import annotations

import json
import os
from math import isfinite
from pathlib import Path
from time import perf_counter, sleep

from edge.classes import MAPPING_FILE, load_video_mapping
from edge.run import COUNTING_FILE, load_counting
from mfstnet.corpus.counting import Detection
from scripts.adaptive_signal import AdaptiveSignal, offline_schedule, signal_config
from scripts.video_traffic import Crossings, KINDS, Policy, alert, summarize

LOCAL_CHECKPOINT = MAPPING_FILE.parent.parent / "data" / "bellevue-demo" / "yolo11s.pt"
PAUSE_FILE = os.environ.get("STMS_VIDEO_PAUSE_FILE")


def wait_for_worker():
    while PAUSE_FILE and os.path.exists(PAUSE_FILE):
        sleep(.2)


def detector_settings():
    override = os.environ.get("STMS_VIDEO_WEIGHTS")
    use_local = not override and os.environ.get("STMS_LOCAL_ANALYSIS") == "1" and LOCAL_CHECKPOINT.is_file()
    if use_local:
        override = str(LOCAL_CHECKPOINT)
    if override:
        conf = float(os.environ.get("STMS_VIDEO_CONF", ".30" if use_local else ".45"))
        if not isfinite(conf) or not .10 <= conf <= 1:
            raise ValueError("STMS_VIDEO_CONF must be between 0.10 and 1.00")
        size = int(os.environ.get("STMS_VIDEO_IMGSZ", "960" if use_local else "640"))
        if not 320 <= size <= 1280 or size % 32:
            raise ValueError("STMS_VIDEO_IMGSZ must be a multiple of 32 between 320 and 1280")
        return Path(override).resolve(), conf, size
    return load_counting(COUNTING_FILE)


def policy_settings():
    path = os.environ.get("STMS_VIDEO_POLICY")
    return Policy(**json.loads(Path(path).read_text(encoding="utf-8"))) if path else Policy()


class TrackedVideo:
    def __init__(self, path, profile, weights, size, policy, *, worker_threads=None):
        wait_for_worker()
        import cv2
        import torch
        from ultralytics import YOLO
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import IterableSimpleNamespace, YAML
        from ultralytics.utils.checks import check_yaml

        if not weights.is_file():
            raise ValueError(f"Missing detector weights: {weights.name}")
        threads = worker_threads or int(os.environ.get("STMS_VIDEO_WORKER_THREADS", min(4, os.cpu_count() or 1)))
        torch.set_num_threads(threads)
        cv2.setNumThreads(min(2, threads))
        self.path, self.size = path, size
        self.model = YOLO(str(weights))
        self.tracker = BYTETracker(IterableSimpleNamespace(**YAML.load(check_yaml("bytetrack.yaml"))))
        self.checkpoint = weights.name
        mapping = load_video_mapping()
        self.classes = {name: mapping.get(name, name) for name in self.model.names.values()}
        self.ids = [key for key, name in self.model.names.items() if self.classes[name] in KINDS]
        if not self.ids:
            raise ValueError("The detector has none of the supported vehicle classes")
        self.crossings = Crossings(profile, policy)
        self.policy = policy
        self.signal = None
        self.signal_problem = None
        if not self.crossings.whole_frame:
            try:
                config = signal_config(profile.camera_id, tuple(profile.lane_map.values()), policy)
                lined = {line["approach"] for line in self.crossings.lines}
                self.signal = AdaptiveSignal(config, profile.lane_map, lined)
            except (ValueError, OSError, TypeError, KeyError, AttributeError):
                self.signal_problem = "Signal configuration is invalid or infeasible. Check phase compatibility, coverage and timing bounds."
                self.crossings.alerts.append(alert("Signal configuration refused", 0, "Warning", self.signal_problem))
        self.frames_processed = 0
        self.track_ids = []
        self.last_media_t = 0
        self.started = perf_counter()

    def frames(self):
        import cv2

        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            capture.release()
            raise ValueError("Video could not be opened")
        next_track, next_sample, index = 0.0, 0, 0
        fps = capture.get(cv2.CAP_PROP_FPS)
        self.resolution = [int(capture.get(k)) for k in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)]
        try:
            while capture.grab():
                t = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if t <= 0 and index and fps > 0:
                    t = index / fps
                index += 1
                self.last_media_t = t
                if t < min(next_track, next_sample):
                    continue
                ok, frame = capture.retrieve()
                if not ok:
                    raise ValueError(f"Could not decode a frame at {t:.2f} s")
                wait_for_worker()
                detections, ids = self.track(frame, t)
                next_track = (int(t * 4) + 1) / 4
                if t >= next_sample:
                    self.track_ids.append(ids)
                    yield next_sample, detections
                    next_sample += 2
        finally:
            capture.release()

    def track(self, frame, t):
        result = self.model.predict(frame, conf=.10, imgsz=self.size, classes=self.ids, verbose=False)[0]
        height, width = result.orig_shape
        boxes = result.boxes.cpu().numpy()
        tracks = self.tracker.update(boxes, result.orig_img)

        def detection(coords, score, cls):
            x1, y1, x2, y2 = (max(0., min(1., float(value) / scale))
                              for value, scale in zip(coords, (width, height, width, height)))
            return Detection(self.model.names[int(cls)], float(score), x1, y1, x2, y2)

        # An unassociated detection still contributes to occupancy if it meets the
        # detector threshold. Crossings only use established tracks.
        visible = [detection(coords, score, cls) for coords, score, cls in zip(boxes.xyxy, boxes.conf, boxes.cls)]
        ids = [None] * len(visible)
        tracked_detections, tracked_ids = [], []
        for x1, y1, x2, y2, track_id, score, cls, index in tracks:
            identifier = int(track_id)
            ids[int(index)] = identifier
            tracked_detections.append(detection((x1, y1, x2, y2), score, cls))
            tracked_ids.append(identifier)
        self.frames_processed += 1
        self.crossings.observe(t, tracked_detections, tracked_ids, self.classes)
        return visible, ids

    def signal_sample(self, sample):
        if self.signal:
            previous = self.signal.active
            sample["signal"] = self.signal.observe(sample, self.crossings.events)
            phase = self.signal.active
            if phase is not previous and phase["red_wait_s"] >= self.signal.max_red / 2:
                self.crossings.alerts.append(alert("Simulated long red", sample["t"], "Info",
                    f"{phase['phase']} received priority after {phase['red_wait_s']:g} s of simulated red.",
                    approach=phase["phase"], red_wait_s=phase["red_wait_s"]))
            if phase is not previous:
                warning = self.timing_warning(phase, sample["t"])
                if warning:
                    self.crossings.alerts.append(warning)

    def timing_warning(self, phase, t):
        if not phase["pedestrian"] and phase["green_s"] > self.policy.previous_green:
            return alert("Adaptive timing above baseline", t, "Info",
                         f"{phase['phase']} was assigned {phase['green_s']} s versus the configured "
                         f"{self.policy.previous_green} s baseline. {phase['reason']}",
                         approach=phase["phase"], green=phase["green_s"], visible=phase["visible"])

    def finish(self, result, *, source_name=None, final=True):
        for sample, ids in zip(result["samples"], self.track_ids):
            sample["track_ids"] = ids
        result["traffic"] = summarize(result, self.crossings, self.policy, legacy_signal_advice=False)
        if self.signal_problem:
            result["traffic"]["signal_problem"] = self.signal_problem
        if self.signal and final:
            controller = self.signal
            config = controller.phases, controller.yellow, controller.red, controller.refresh, controller.max_red
            result["traffic"]["signal_schedule"] = offline_schedule(
                config, controller.lanes, controller.lined, result["traffic"], result["duration_s"])
            if not controller.active:
                alerts = result["traffic"]["alerts"]
                for phase in result["traffic"]["signal_schedule"]["phases"]:
                    if phase["start"] >= result["duration_s"]:
                        break
                    warning = self.timing_warning(phase, phase["start"])
                    if warning:
                        alerts.append(warning)
                alerts.sort(key=lambda event: (event["t"], event["id"]))
        result["processing"] = self.processing(source_name)
        result["known_limits"].extend([
            ("Track IDs are counted once after confirmation. Occlusion can cause IDs to change."
             if self.crossings.whole_frame else
             "A track is counted once after crossing an inbound line. Occlusion and track ID changes can cause errors."),
            "Density is estimated from visible vehicles. Signal timing is advisory.",
            "Red-light violations, physical speed, queue length and current signal phase require verified inputs.",
        ])
        return result

    def processing(self, source_name=None):
        seconds = perf_counter() - self.started
        return {
            "filename": source_name or self.path.name, "resolution": self.resolution,
            "seconds": round(seconds, 3), "frames": self.frames_processed,
            "fps": round(self.frames_processed / max(seconds, .001), 2),
            "model": self.checkpoint, "imgsz": self.size, "tracker": "ByteTrack",
            "supported_classes": sorted({self.classes[self.model.names[key]] for key in self.ids}),
            "source_size": 0 if source_name else self.path.stat().st_size,
            "source": "camera" if source_name else "recording",
        }
