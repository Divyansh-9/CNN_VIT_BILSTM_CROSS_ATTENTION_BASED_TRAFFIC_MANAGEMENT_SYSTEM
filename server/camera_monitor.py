"""One loopback camera session, with a bounded latest-frame preview."""

import base64
import json
import logging
import threading
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4


def camera_source(value):
    if not isinstance(value, str) or not value or len(value) > 300:
        raise ValueError("Enter an RTSP, HTTP or HTTPS camera URL, or webcam:0")
    if value.startswith("webcam:") and value[7:] in {str(i) for i in range(10)}:
        return int(value[7:])
    url = urlsplit(value)
    if url.scheme not in {"rtsp", "http", "https"} or not url.hostname or any(c.isspace() for c in value):
        raise ValueError("Enter an RTSP, HTTP or HTTPS camera URL, or webcam:0")
    return value


class CameraMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.state = {"status": "Disconnected"}
        self.updated = 0

    def connect(self, store, profile, source):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return False
            self.stop = threading.Event()
            self.state = {"status": "Connecting"}
            self.thread = threading.Thread(target=self.run, args=(store, profile, source), daemon=True)
            self.thread.start()
            return True

    def running(self):
        with self.lock:
            return self.thread is not None and self.thread.is_alive()

    def snapshot(self):
        with self.lock:
            state = dict(self.state)
            if state["status"] == "Connected" and monotonic() - self.updated > 6:
                state.update(status="Connecting", frame=None, message="Waiting for a fresh camera frame.")
            return state

    def publish(self, **state):
        with self.lock:
            self.state.update(state)
            self.updated = monotonic()

    def disconnect(self):
        self.stop.set()
        self.publish(status="Disconnected", frame=None)

    def run(self, store, profile, source):
        import cv2
        from scripts.analyze_video import SampleAnalyzer, analysis_result, RIDGE_SPEC
        from scripts.tracked_video import TrackedVideo, detector_settings, policy_settings
        from scripts.video_traffic import alert

        name = f"Camera {profile.camera_id}"
        job, key, problem = None, None, None
        samples, classes = [], set()
        try:
            job = store.history.start(name, 0, profile.camera_id, pending_replay=True, mode="camera")
            weights, conf, size = detector_settings()
            tracker = TrackedVideo(Path("camera"), profile, weights, size, policy_settings(),
                                   worker_threads=getattr(store, "worker_threads", None))
            analyzer = SampleAnalyzer(profile, RIDGE_SPEC, conf)
            started, last_frame, failures = monotonic(), -1.0, 0
            while not self.stop.is_set() and monotonic() - started < 3600:
                capture = cv2.VideoCapture(source) if isinstance(source, int) else cv2.VideoCapture(
                    source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3500, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3500])
                try:
                    while not self.stop.is_set() and monotonic() - started < 3600:
                        ok, frame = capture.read()
                        if not ok:
                            break
                        elapsed = monotonic() - started
                        if elapsed - last_frame < .25:
                            continue
                        failures, last_frame = 0, elapsed
                        tracked, ids = tracker.track(frame, elapsed)
                        sample = analyzer.step(int(elapsed // 2) * 2, tracked) if not samples or int(elapsed // 2) * 2 > samples[-1]["t"] else None
                        if sample is None:
                            continue
                        sample["track_ids"] = ids
                        tracker.signal_sample(sample)
                        samples.append(sample)
                        tracker.track_ids.append(ids)
                        classes.update(item.cls for item in tracked)
                        tracker.resolution = [int(frame.shape[1]), int(frame.shape[0])]
                        result = tracker.finish(analysis_result(profile, analyzer, name, elapsed, samples[:], classes),
                                                source_name=name, final=False)
                        scale = min(1, 960 / frame.shape[1])
                        if scale < 1:
                            frame = cv2.resize(frame, None, fx=scale, fy=scale)
                        rendered, jpg = cv2.imencode(".jpg", frame)
                        if rendered and not self.stop.is_set():
                            self.publish(status="Connected", frame=base64.b64encode(jpg).decode("ascii"),
                                         result=result, elapsed=elapsed, source=name, message=None)
                finally:
                    capture.release()
                if self.stop.is_set():
                    break
                failures += 1
                if failures == 1 and samples:
                    tracker.crossings.alerts.append(alert("Camera connection lost", round(last_frame, 2), "Warning",
                                                        "The camera stopped returning frames; reconnecting."))
                if failures >= 3:
                    problem = "Could not receive frames from this camera. Check the address and stream settings."
                    break
                self.publish(status="Connecting", frame=None, message="Reconnecting to the camera.")
                self.stop.wait(1)
            if samples:
                key = uuid4().hex * 2
                result = tracker.finish(analysis_result(profile, analyzer, name, max(2, last_frame), samples, classes), source_name=name)
                store.results_dir.mkdir(parents=True, exist_ok=True)
                partial = store.results_dir / f"{key}.partial.json"
                partial.write_text(json.dumps(result), encoding="utf-8")
                partial.replace(store.results_dir / f"{key}.json")
        except Exception:
            # Camera URLs can include credentials. Keep exception text out of logs and API responses.
            logging.getLogger(__name__).warning("Camera monitoring failed")
            problem = "Camera monitoring failed. Check the camera, decoder and detector setup."
            key = None
        finally:
            try:
                if job:
                    store.history.finish(job, key, problem or (None if key else "stopped"), result if key else None)
                if key:
                    store.history.reveal_replay(job)
                self.publish(status="Error" if problem else "Disconnected", message=problem, frame=None,
                             saved_job=job if key else None)
            finally:
                if getattr(store, "on_release", None):
                    store.on_release()


camera = CameraMonitor()
