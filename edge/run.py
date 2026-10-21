"""The edge program: camera or video in, counts and forecasts out (D3).

    python -m edge.run --source clip.mp4 --lanes lanes.json \\
        --approaches lane_0=W lane_1=N lane_2=E --camera NE8th \\
        --intersection-id ne8th --broker-host 127.0.0.1 --broker-port 1883

    set STMS_CAMERA_URL=rtsp://...      then   --source camera

Before this module the deployed path ran only inside the Phase C harness,
which is not in the repository (HLD §9-C1). This is that path, committed:

    detector -> counting -> persistence + ridge -> publish -> fallback

It adds no logic of its own. Counting is `mfstnet.corpus.counting`, the
forecasters are `edge.persistence` and `edge.count_forecast` (ADR-027), and
publishing, the class mapping (D1) and FR-A06 are `EdgeNode`'s.

**Two counts leave one frame, and neither stands in for the other** (SAD §4.3).
The forecasters get each lane's raw total, bicycles included, because that is
what their thresholds and coefficients were calibrated on. The `vehicle_count`
topic gets the per-class breakdown, which `EdgeNode` maps to the contract's
classes, dropping bicycles.

**Everything is refused at start-up that can be.** A bad intersection id
(P142), an unreviewed lane file, an approach mapping that does not cover the
lanes, a camera with no thresholds: each would otherwise run for minutes and
publish into a refusal, or forecast against the wrong calibration.

**Frames stay in memory** (NFR-13). A frame is detected on and dropped in the
same step. Nothing here opens a file for writing, and the camera URL is read
from `STMS_CAMERA_URL` so it never reaches the command line or the log.

**The link is not the only thing that can stop.** While the camera is
reconnecting there are no frames, but the node is still ticked once a step, so
FR-A06's timeout is still measured from `last_ack` and the local cycle still
runs. This program does not drive signal hardware, and no forecast feeds signal
timing (ADR-027, P97a).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from contracts.mqtt import ContractError, Mode, check_intersection_id
from edge.classes import MAPPING_FILE
from edge.count_forecast import RidgeCountForecaster
from edge.node import EdgeNode
from edge.persistence import APPROACHES, PersistenceForecaster
from edge.samples import STEP_S, SampleError
from mfstnet.corpus.counting import Detection, count_frame
from mfstnet.corpus.lanes import LaneCentres

__all__ = ["Settings", "EdgeLoop", "load_counting", "load_lanes", "parse_args", "run",
           "main"]

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "experiments" / "results" / "bellevue_pilot"
CAMERA_ENV = "STMS_CAMERA_URL"
CAMERA_SOURCE = "camera"
# The counting settings (detector, threshold, input size) live once, in the
# `counting` block of class_mapping.yaml: the persistence thresholds and the
# ridge coefficients were calibrated under them (P97, P103, P105), so they are
# configuration, not script defaults (D5).
COUNTING_FILE = MAPPING_FILE
RECONNECT_S = (1, 2, 4, 8, 10)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    source: str                 # a video file, or CAMERA_SOURCE
    lanes: LaneCentres
    approaches: dict[str, str]  # lane -> N/S/E/W
    camera: str                 # the persistence spec's key for this camera
    intersection_id: str
    broker_host: str
    broker_port: int
    weights: Path
    conf: float
    imgsz: int
    persistence_spec: Path
    ridge_spec: Path
    samples: int | None
    realtime: bool


def load_lanes(path: Path) -> LaneCentres:
    """A reviewed lane file (`import_lane_centres.py`) or a corpus manifest.

    Automatic centres move with the detector (P23), so a lane file must say it
    was reviewed. A corpus manifest's centres are the ones its labels came from.
    """
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if "lane_centres" in spec:
        entries = spec["lane_centres"]
    elif spec.get("reviewed"):
        entries = spec["lanes"]
    else:
        raise ValueError(f"{path} is not a reviewed lane file or a corpus manifest; "
                         f"automatic lane centres are never used unreviewed (P23)")
    return LaneCentres(names=tuple(e["name"] for e in entries),
                       centres=tuple(tuple(e["centre"]) for e in entries),
                       max_radius=float(spec.get("max_radius", 0.25)))


def load_counting(path: Path) -> tuple[Path, float, int]:
    """The detector weights, confidence threshold and input size, from the
    `counting` block. A missing key is refused, never filled in."""
    import yaml

    block = (yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}).get("counting") or {}
    missing = sorted({"detector_weights", "confidence_threshold", "imgsz"} - set(block))
    if missing:
        raise ValueError(f"{path}: the counting block has no {', '.join(missing)}")
    return (ROOT / block["detector_weights"], float(block["confidence_threshold"]),
            int(block["imgsz"]))


def _port(text: str) -> int:
    port = int(text)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 1 to 65535, got {port}")
    return port


def _positive(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {n}")
    return n


def parse_args(argv: list[str] | None = None) -> Settings:
    """Read and check the command line. Anything wrong ends the program here."""
    parser = argparse.ArgumentParser(prog="python -m edge.run",
                                     description=__doc__.split("\n")[0])
    try:
        weights, conf, imgsz = load_counting(COUNTING_FILE)
    except (OSError, ValueError, TypeError) as error:
        parser.error(f"counting settings: {error}")
    parser.add_argument("--source", required=True,
                        help=f"a video file, or '{CAMERA_SOURCE}' to read the stream "
                             f"URL from {CAMERA_ENV}")
    parser.add_argument("--lanes", required=True, type=Path,
                        help="reviewed lane centres, or a corpus manifest")
    parser.add_argument("--approaches", required=True, nargs="+", metavar="LANE=DIR",
                        help="every lane mapped to a distinct approach, N S E or W")
    parser.add_argument("--camera", required=True,
                        help="this camera's key in the persistence spec")
    parser.add_argument("--intersection-id", required=True)
    parser.add_argument("--broker-host", default="127.0.0.1")
    parser.add_argument("--broker-port", type=_port, default=1883)
    parser.add_argument("--weights", type=Path, default=weights,
                        help="default: the counting block of class_mapping.yaml")
    parser.add_argument("--conf", type=float, default=conf,
                        help="default: the counting block of class_mapping.yaml")
    parser.add_argument("--imgsz", type=_positive, default=imgsz,
                        help="default: the counting block of class_mapping.yaml")
    parser.add_argument("--persistence-spec", type=Path,
                        default=PILOT / "persistence_v1.json")
    parser.add_argument("--ridge-spec", type=Path, default=PILOT / "p105_ridge_v1.json")
    parser.add_argument("--samples", type=_positive, default=None,
                        help="stop after this many 2 s samples")
    parser.add_argument("--realtime", action="store_true",
                        help="pace a video file at one sample per 2 s, like a camera")
    args = parser.parse_args(argv)

    try:
        check_intersection_id(args.intersection_id)
    except ContractError as error:
        parser.error(str(error))
    if args.source == CAMERA_SOURCE:
        if not os.environ.get(CAMERA_ENV, "").strip():
            parser.error(f"--source {CAMERA_SOURCE} reads the stream URL from {CAMERA_ENV}, "
                         f"which is not set")
    elif not Path(args.source).is_file():
        parser.error(f"--source {args.source}: no such video file")
    if not 0.0 < args.conf <= 1.0:
        parser.error(f"--conf must be in (0, 1], got {args.conf}")
    for path, flag in ((args.weights, "--weights"), (args.persistence_spec, "--persistence-spec"),
                       (args.ridge_spec, "--ridge-spec"), (args.lanes, "--lanes")):
        if not path.is_file():
            parser.error(f"{flag} {path}: no such file")
    try:
        lanes = load_lanes(args.lanes)
    except (ValueError, KeyError, TypeError) as error:
        parser.error(f"--lanes {args.lanes}: {error}")

    approaches = {}
    for item in args.approaches:
        lane, sep, approach = item.partition("=")
        if not sep or approach not in APPROACHES or lane in approaches:
            parser.error(f"--approaches {item!r}: expected LANE=DIR once per lane, "
                         f"DIR one of {' '.join(APPROACHES)}")
        approaches[lane] = approach
    if set(approaches) != set(lanes.names):
        parser.error(f"--approaches covers {sorted(approaches)}, the lane file has "
                     f"{sorted(lanes.names)}; every lane needs exactly one approach")
    if len(set(approaches.values())) != len(approaches):
        parser.error(f"--approaches maps two lanes to one approach: {approaches}")

    spec = json.loads(args.persistence_spec.read_text(encoding="utf-8"))
    entry = spec.get("cameras", {}).get(args.camera)
    if entry is None:
        parser.error(f"--camera {args.camera} has no thresholds in {args.persistence_spec}; "
                     f"calibrate it first (ADR-017)")
    if "lanes" in entry and entry["lanes"] != len(lanes.names):
        parser.error(f"--camera {args.camera} was calibrated on {entry['lanes']} lanes, "
                     f"the lane file has {len(lanes.names)}")

    return Settings(source=args.source, lanes=lanes, approaches=approaches,
                    camera=args.camera, intersection_id=args.intersection_id,
                    broker_host=args.broker_host, broker_port=args.broker_port,
                    weights=args.weights, conf=args.conf, imgsz=args.imgsz,
                    persistence_spec=args.persistence_spec, ridge_spec=args.ridge_spec,
                    samples=args.samples, realtime=args.realtime)


class EdgeLoop:
    """One 2 s step: detections in, both counts out, forecasts published.

    Takes detections, never a frame, so nothing it keeps can hold one.
    """

    def __init__(self, node: EdgeNode, lanes: LaneCentres, approaches: dict[str, str],
                 persistence: PersistenceForecaster, ridge: RidgeCountForecaster, *,
                 min_confidence: float) -> None:
        self.node, self.lanes, self.approaches = node, lanes, dict(approaches)
        self.persistence, self.ridge = persistence, ridge
        self.min_confidence = min_confidence
        self.mode = node.mode
        self.refused = 0                 # samples a forecaster would not take

    def step(self, detections: list[Detection], ts: float,
             now: float | None = None) -> dict:
        now = time.time() if now is None else now
        counts = count_frame(detections, self.lanes, min_confidence=self.min_confidence)
        # The forecasters' input: each lane's raw total, bicycles included, as
        # calibrated. Every lane the geometry knows is passed as it was counted;
        # a lane the forecasters expect and the counts lack is refused by
        # SampleBuffer, never filled in as zero (P97a).
        totals = {lane: int(n) for lane, n in counts.per_lane.items()}
        # The wire's input: the per-class breakdown, mapped by the node (D1).
        breakdown = {lane: dict(by_class) for lane, by_class in counts.per_lane_class.items()}
        out = self.node.tick(breakdown, fps=1.0 / STEP_S, now=now)
        out["totals"] = totals
        out["prediction"] = self._forecast(self.persistence, totals, ts, now,
                                           self.node.publish_prediction)
        out["count_forecast"] = self._forecast(self.ridge, totals, ts, now,
                                               self.node.publish_count_forecast)
        self._note_mode(out)
        return out

    def idle(self, now: float | None = None) -> dict:
        """A step with no frame (the camera is reconnecting). Nothing is counted
        or forecast, but FR-A06 is still decided."""
        out = self.node.tick({}, fps=1.0 / STEP_S, now=now)
        self._note_mode(out)
        return out

    def _forecast(self, forecaster, totals, ts, now, publish) -> str:
        try:
            forecast = forecaster.step(totals, ts)
        except SampleError as error:
            # Dropped, and the window is kept: one bad sample is not a gap.
            self.refused += 1
            log.warning("sample refused by %s: %s", type(forecaster).__name__, error)
            return "refused"
        except ValueError as error:          # a ridge value out of range
            log.warning("forecast refused by %s: %s", type(forecaster).__name__, error)
            return "refused"
        if forecast is None:
            return "warming up"
        return "published" if publish(forecast, now) else "not delivered"

    def _note_mode(self, out: dict) -> None:
        if out["mode"] != self.mode:
            if out["mode"] is Mode.LOCAL:
                log.warning("%s", out["reason"])
            else:
                log.info("link restored; the server is driving again")
            self.mode = out["mode"]


class YoloDetector:
    """The counting detector, at the calibrated settings. A frame goes in and
    only boxes come out."""

    def __init__(self, weights: Path, conf: float, imgsz: int) -> None:
        from ultralytics import YOLO

        from scripts.pilot_a17 import vehicle_ids

        self.model = YOLO(str(weights))
        self.ids = vehicle_ids(self.model)
        names = self.model.names
        self.names = names if isinstance(names, dict) else dict(enumerate(names))
        self.conf, self.imgsz = conf, imgsz

    def __call__(self, frame) -> list[Detection]:
        result = self.model.predict(source=frame, conf=self.conf, imgsz=self.imgsz,
                                    verbose=False)[0]
        h, w = result.orig_shape
        return [Detection(cls=self.names[int(c)], confidence=float(p), x1=b[0] / w,
                          y1=b[1] / h, x2=b[2] / w, y2=b[3] / h)
                for b, c, p in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(),
                                   result.boxes.conf.tolist()) if int(c) in self.ids]


def _stride(source: str) -> int:
    import cv2

    capture = cv2.VideoCapture(source)
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    finally:
        capture.release()
    return max(1, int(round(fps * STEP_S)))


def file_frames(path: str, *, realtime: bool = False) -> Iterator[tuple[float, object]]:
    """A video file, one frame per 2 s of video time."""
    from mfstnet.corpus.video import iter_sampled_frames

    started = time.monotonic()
    for k, frame in enumerate(iter_sampled_frames(path, _stride(path))):
        if realtime:
            time.sleep(max(0.0, started + k * STEP_S - time.monotonic()))
        yield k * STEP_S, frame


def camera_frames(url: str) -> Iterator[tuple[float, object | None]]:
    """A live stream, timestamped on arrival. While it is down, yields
    `(ts, None)` once a step so the caller can keep FR-A06 running; the gap
    resets the forecast windows."""
    from mfstnet.corpus.video import iter_sampled_frames

    while True:
        try:
            stride = _stride(url)
        except Exception:                    # noqa: BLE001 - OpenCV raises anything
            stride = 0
        if stride:
            for frame in iter_sampled_frames(url, stride):
                yield time.monotonic(), frame
        log.warning("camera stream ended; reconnecting")
        for wait in RECONNECT_S:
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                time.sleep(min(STEP_S, max(0.0, deadline - time.monotonic())))
                yield time.monotonic(), None


def run(settings: Settings, *, node: EdgeNode,
        detector: Callable[[object], list[Detection]],
        frames: Iterator[tuple[float, object | None]]) -> EdgeLoop:
    """The loop, with its parts handed in, so it is testable without a camera,
    a detector or a broker."""
    loop = EdgeLoop(node, settings.lanes, settings.approaches,
                    PersistenceForecaster(settings.persistence_spec, settings.camera,
                                          settings.approaches),
                    RidgeCountForecaster(settings.ridge_spec, settings.approaches),
                    min_confidence=settings.conf)
    taken = 0
    for ts, frame in frames:
        if frame is None:
            loop.idle()
            continue
        detections = detector(frame)
        del frame                            # NFR-13: counted, then dropped
        loop.step(detections, ts)
        taken += 1
        if settings.samples is not None and taken >= settings.samples:
            break
    return loop


def main(argv: list[str] | None = None) -> int:
    from edge.classes import load_itd_mapping
    from edge.mqtt_transport import MqttTransport
    from scripts.console import use_utf8

    use_utf8()
    settings = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if settings.source == CAMERA_SOURCE:
        # OpenCV's FFmpeg backend can quote the stream URL, credentials and
        # all, in its own error messages; silence them before cv2 is imported.
        os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")
        os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
    detector = YoloDetector(settings.weights, settings.conf, settings.imgsz)
    transport = MqttTransport(settings.broker_host, settings.broker_port,
                              client_id=f"edge-{settings.intersection_id}")
    node = EdgeNode(intersection_id=settings.intersection_id, transport=transport,
                    detector_classes=load_itd_mapping())
    if not transport.start():
        # Not fatal: FR-A06 exists for a node that cannot reach the server.
        log.warning("broker %s:%d not reachable; continuing, and the local cycle "
                    "takes over after %.0f s without an acknowledgement",
                    settings.broker_host, settings.broker_port, node.timeout_s)
    if settings.source == CAMERA_SOURCE:
        frames = camera_frames(os.environ[CAMERA_ENV].strip())
        log.info("source: the camera in %s", CAMERA_ENV)
    else:
        frames = file_frames(settings.source, realtime=settings.realtime)
        log.info("source: %s", Path(settings.source).name)
    try:
        loop = run(settings, node=node, detector=detector, frames=frames)
        log.info("stopped; %d sample(s) refused by a forecaster, excluded classes %s",
                 loop.refused, dict(node.excluded))
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        transport.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
