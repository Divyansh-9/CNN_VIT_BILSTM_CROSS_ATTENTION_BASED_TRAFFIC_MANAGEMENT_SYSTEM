"""The local workbench's work: find a video, analyse it, store a checked result (D40, D41).

`scripts/demo_launcher.py` serves the dashboard on 127.0.0.1 and routes the
dashboard's workbench actions here. The viewer opens a video in the page; this
finds the same file on disk, runs the existing tool (`scripts/analyze_video.py`)
over it for the camera the viewer declares, checks what the tool wrote, and keeps
it by key so the page can read it.

**What it adds, and what it does not.** It runs the same tool, with the same
detector, counting and forecasters, in a child process. It adds a pre-flight that
refuses with a reason, progress read from the tool itself, a validation of what the
tool wrote, and a store keyed by what the result depends on. It adds no model and
no new kind of output.

**Finding the file (D41).** The browser holds the video and cannot say where it
lives; this process knows paths and never sends one. So the page sends the file's
name, size and fingerprint, and `Locator` looks for a file matching all three in
the folders it knows. When it cannot see the folder, this computer's own folder
window asks the viewer, and only the folder's name goes back to the page.

**A camera is declared, never inferred** (ADR-028). The viewer picks a reviewed
profile from `cameras/`, or places a new camera's lanes on their own video. A new
camera is **provisional**: it is kept beside the results, never in `cameras/`, and
its levels are set from the first recording analysed with it by ADR-017's rule as
P103 ran it. Every result it produces says that its lanes are unreviewed and that
its levels flatter that recording and are not evidence.

**What crosses the browser.** Numbers from the lists, camera ids, a file's name,
size and fingerprint, lane positions, text about the job, and the finished results
file, which holds counts, boxes and forecasts and never a frame. Never a path: an
error that names a file is cut down to the file's name. The video plays in the page
from the viewer's own file; this process never serves it (NFR-13).

**The store.** A result is kept under a key made from the video (its size, name and
sampled bytes), the profile's canonical hash, and the analysis inputs (the detector
weights, the counting settings, the ridge spec and the tool itself). Change any of
them and the key changes, so a stale result is never reopened as current. The
video part is a fingerprint, not a full hash: reading whole recordings to hash them
would cost minutes, and a fingerprint is enough to tell recordings apart here.

**What it does not establish:** "then" comes from the same detector's counts, so it
is not accuracy; a recording is not a live camera (S65); and nothing here drives a
signal (P97a).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge.profile import CameraProfile, ProfileError, canonical_hash, load_profile  # noqa: E402
from scripts.recording_profile import WHOLE_FRAME, WHOLE_FRAME_PATH, load_recording_profile  # noqa: E402

__all__ = ["Analyses", "Cameras", "Check", "Locator", "Recording", "Refused", "analysis_key", "calibration_limits",
           "catalogue", "choose_folder", "fingerprint", "preflight", "progress_line", "redact", "relevel",
           "validate_result"]

TOOL = ROOT / "scripts" / "analyze_video.py"
VIDEO_SUFFIXES = (".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi")
KEY = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20                 # bytes read at each of three places for a fingerprint
MIN_S = 2.0                     # same minimum as analyze_video.MIN_S
MAX_VIDEO_BYTES = 2 * 1024 ** 3
STEP_S = 2.0                    # as edge.samples.STEP_S: one detected frame per 2 s of video
KIND, SCHEMA = "stms-video-analysis", 2
ETA_AFTER = 10                  # samples measured before an estimate of the time left is shown
PROGRESS = re.compile(r"^PROGRESS (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)$")
WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"<>|]*")
POSIX_PATH = re.compile(r"(?<![\w.])/(?:[^\s/'\"<>|]+/)+[^\s'\"<>|]*")
STAGES = (("check", "Check the recording and its camera"),
          ("analyse", "Decode frames, detect and track vehicles"),
          ("levels", "Set this new camera's levels from this recording"),
          ("validate", "Validate and store the results"),
          ("open", "Results ready"))


class Refused(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


@dataclass(frozen=True)
class Recording:
    path: Path
    upload_key: str | None = None

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class Check:
    """One pre-flight line. `ok` is True, False (refused), or None (a note)."""
    name: str
    ok: bool | None
    detail: str


def catalogue(roots) -> list[Recording]:
    """Every video file under the given folders, each once, by name."""
    seen, found = set(), []
    for root in roots:
        for path in Path(root).rglob("*"):
            if path.suffix.lower() in VIDEO_SUFFIXES and path.is_file():
                real = path.resolve()
                if real not in seen:
                    seen.add(real)
                    found.append(Recording(real))
    return sorted(found, key=lambda r: (r.name.lower(), str(r.path)))


def fingerprint(path: Path, chunk: int = CHUNK) -> str:
    """The size and three sampled stretches of the file: start, middle and end."""
    size = path.stat().st_size
    digest = hashlib.sha256(f"size:{size}".encode())
    with open(path, "rb") as handle:
        for offset in sorted({0, max(0, size // 2 - chunk // 2), max(0, size - chunk)}):
            handle.seek(offset)
            digest.update(handle.read(chunk))
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def tool_inputs() -> dict:
    """What a result depends on besides the video and the profile."""
    from scripts.analyze_video import RIDGE_SPEC
    from scripts import adaptive_signal, recording_profile, scene_forecast, tracked_video, video_traffic
    from edge import classes
    from dataclasses import asdict

    weights, conf, imgsz = tracked_video.detector_settings()
    if not weights.is_file():
        raise ValueError(f"Missing detector weights: {weights.name}")
    signal_path = os.environ.get("STMS_SIGNAL_CONFIG")
    try:
        signal_hash = file_sha256(Path(signal_path)) if signal_path else None
    except OSError:
        signal_hash = "unreadable"
    return {"detector_sha256": file_sha256(weights), "confidence_threshold": conf, "imgsz": imgsz,
            "ridge_sha256": file_sha256(RIDGE_SPEC), "tool_sha256": file_sha256(TOOL), "schema": SCHEMA,
            "tracking_sha256": file_sha256(Path(tracked_video.__file__)),
            "recording_profile_sha256": file_sha256(Path(recording_profile.__file__)),
            "class_mapping_sha256": file_sha256(classes.MAPPING_FILE),
            "class_mapping_code_sha256": file_sha256(Path(classes.__file__)),
            "traffic_sha256": file_sha256(Path(video_traffic.__file__)),
            "scene_forecast_sha256": file_sha256(Path(scene_forecast.__file__)),
            "policy": asdict(tracked_video.policy_settings()),
            "signal_sha256": file_sha256(Path(adaptive_signal.__file__)), "signal_config_sha256": signal_hash}


def analysis_key(video_fingerprint: str, clip: str, profile_hash: str, inputs: dict) -> str:
    return canonical_hash({"video": video_fingerprint, "clip": clip, "profile": profile_hash, "inputs": inputs})


def profile_hash(profile: CameraProfile) -> str:
    return canonical_hash(profile.raw)


def probe_video(path: Path) -> tuple[int, int] | None:
    """Width and height from one decoded frame, held in memory and dropped (NFR-13)."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        height, width = frame.shape[:2]
        del frame
        return int(width), int(height)
    finally:
        capture.release()


def duration_of(path: Path) -> float | None:
    from edge.run import clip_duration

    return clip_duration(str(path))


def preflight(recording: Recording, profile_path: Path, *, probe=probe_video, duration=duration_of,
              load=load_recording_profile) -> tuple[list[Check], CameraProfile | None, float | None]:
    """Every reason not to start, each with what to do about it. Nothing is written."""
    checks: list[Check] = []
    try:
        profile = load(profile_path)
        detail = "Whole-frame vehicle counts" if profile.camera_id == WHOLE_FRAME else (
            f"{profile.camera_id}: {len(profile.lanes)} lanes, calibrated limits")
        checks.append(Check("Camera profile", True, detail))
    except ProfileError as error:
        profile = None
        checks.append(Check("Camera profile", False, f"refused: {redact(str(error))}. Choose another camera, "
                                                     "or make this one's profile with scripts/camera_profile.py"))
    size = probe(recording.path)
    if size is None:
        checks.append(Check("Video can be read", False, "no picture could be decoded. MP4 with H.264 usually works"))
    else:
        checks.append(Check("Video can be read", True, f"{size[0]} × {size[1]}"))
    length = duration(recording.path) if size is not None else None
    if length is None:
        checks.append(Check("Long enough", False, "its length cannot be read from the file"))
    elif length < MIN_S:
        checks.append(Check("Long enough", False, f"The recording must be at least {MIN_S:g} seconds long"))
    else:
        checks.append(Check("Long enough", True, f"{length / 60:.1f} min of footage"))
    if profile is not None and profile.camera_id != WHOLE_FRAME and profile.calibrated_on and profile.calibrated_on in recording.path.stem:
        checks.append(Check("Calibration hour", None, "this is the hour this camera's limits were calibrated on, "
                                                     "so its levels flatter it"))
    return checks, profile, length


def progress_line(text: str) -> tuple[float, float] | None:
    """`PROGRESS <t> <duration>` from analyze_video --progress, or None."""
    match = PROGRESS.match(text.strip())
    return (float(match[1]), float(match[2])) if match else None


def redact(text: str) -> str:
    """A path reduced to its file name, so no folder reaches the browser."""
    text = WINDOWS_PATH.sub(lambda m: Path(m[0].replace("\\", "/")).name or "...", text)
    return POSIX_PATH.sub(lambda m: Path(m[0]).name or "...", text)


def validate_result(path: Path, *, camera: str, clip: str, duration_s: float) -> str | None:
    """Why this file is not the result asked for, or None when it is."""
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "the results file is missing or is not JSON"
    if not isinstance(result, dict) or result.get("kind") != KIND or result.get("schema") != SCHEMA:
        return f"it is not a schema {SCHEMA} analysis results file"
    if result.get("camera") != camera or result.get("clip") != clip:
        return "it names a different camera or clip"
    samples = result.get("samples")
    if not isinstance(samples, list) or not samples:
        return "it holds no samples"
    expected = duration_s / STEP_S
    if abs(len(samples) - expected) > max(3.0, 0.01 * expected):
        return f"it holds {len(samples)} samples where the video's length implies about {expected:.0f}"
    return None


def run_tool(video: Path, profile: Path, out: Path, on_progress: Callable[[float, float], None],
             stopping: threading.Event, *, on_frame=None, worker_threads=None, background=False, pause_file=None) -> tuple[int, list[str]]:
    """analyze_video.py in a child process: its own interpreter, so a stop is a kill
    and the GPU is handed back whole. Returns its exit status and its last lines."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if worker_threads is not None:
        threads = str(worker_threads)
        env.update(STMS_VIDEO_WORKER_THREADS=threads, OMP_NUM_THREADS=threads, MKL_NUM_THREADS=threads,
                   OPENBLAS_NUM_THREADS=threads)
    if background:
        env["CUDA_VISIBLE_DEVICES"] = ""
    if pause_file:
        env["STMS_VIDEO_PAUSE_FILE"] = str(pause_file)
    process = subprocess.Popen(
        [sys.executable, str(TOOL), "--video", str(video), "--profile", str(profile), "--out", str(out),
         "--force", "--progress", *(["--monitor"] if on_frame else [])],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace")
    tail: deque[str] = deque(maxlen=20)

    def read() -> None:
        for line in process.stdout:
            seen = progress_line(line)
            if seen:
                on_progress(*seen)
            elif on_frame and line.startswith("MONITOR "):
                on_frame(json.loads(line[8:]))
            elif line.strip():
                tail.append(line.rstrip())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    while process.poll() is None:
        if stopping.wait(0.5):
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            reader.join(5)
            return 130, list(tail)
    reader.join(5)
    return process.returncode, list(tail)


# ------------------------------------------------------------ finding a video ---

STANDARD_FOLDERS = ("Videos", "Downloads", "Desktop", "Documents")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "$Recycle.Bin", "AppData",
             "System Volume Information", "Windows", "Program Files", "Program Files (x86)", "ProgramData"}
LOCATE_BUDGET_S = 8.0
FOLDER_DIALOG = """\
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
print(filedialog.askdirectory(parent=root, mustexist=True,
                              title="Show the STMS workbench the folder that holds your video") or "")
"""


class Locator:
    """Finds, on this computer, the file a viewer opened in the browser (D41).

    The browser holds the video and cannot say where it lives; this process knows
    paths and must never send one. So the browser sends the file's name, size and
    fingerprint (the same three sampled stretches as `fingerprint`), and this looks
    for a file that matches all three in the folders it knows: those it was started
    with, those the viewer has shown it, and the usual user folders. Nothing is
    matched on the name alone."""

    def __init__(self, roots, remembered: Path | None = None, standard: bool = True) -> None:
        self.roots = [Path(r) for r in roots]
        self.remembered = remembered
        self.shown: list[Path] = []
        if remembered and remembered.is_file():
            try:
                self.shown = [Path(p) for p in json.loads(remembered.read_text(encoding="utf-8"))]
            except (OSError, ValueError):
                self.shown = []
        self.standard = [Path.home() / name for name in STANDARD_FOLDERS] if standard else []

    def remember(self, folder: Path) -> None:
        folder = Path(folder).resolve()
        self.shown = [folder] + [f for f in self.shown if f != folder]
        if self.remembered:
            self.remembered.parent.mkdir(parents=True, exist_ok=True)
            self.remembered.write_text(json.dumps([str(f) for f in self.shown[:20]]), encoding="utf-8")

    def folders(self) -> list[Path]:
        seen, out = set(), []
        for folder in [*self.shown, *self.roots, *self.standard]:
            key = str(folder).casefold()
            if key not in seen and folder.is_dir():
                seen.add(key)
                out.append(folder)
        return out

    def find(self, name: str, size: int, fp: str, *, fingerprint_of=None, budget_s: float = LOCATE_BUDGET_S,
             clock=time.monotonic) -> tuple[Path | None, bool]:
        """(the matching file or None, whether every known folder was searched)."""
        fingerprint_of = fingerprint_of or fingerprint
        end, want = clock() + budget_s, name.casefold()
        for folder in self.folders():
            for dirpath, dirnames, filenames in os.walk(folder):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                for file in filenames:
                    if file.casefold() != want:
                        continue
                    path = Path(dirpath) / file
                    try:
                        if path.stat().st_size == size and fingerprint_of(path) == fp:
                            return path.resolve(), True
                    except OSError:
                        continue
                if clock() > end:
                    return None, False
        return None, True


def choose_folder(timeout_s: float = 600.0) -> Path | None:
    """This computer's own folder dialog, in a child process so Tk owns its thread.
    The chosen path stays here; the browser is told the folder's name only."""
    try:
        done = subprocess.run([sys.executable, "-c", FOLDER_DIALOG], capture_output=True, text=True,
                              timeout=timeout_s, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = done.stdout.strip()
    return Path(text) if text and Path(text).is_dir() else None


# ------------------------------------------------------------ cameras ---

CALIBRATION_STRIDE, CALIBRATION_T = 15, 60      # as P103: a window every 15 samples, 60 behind each
NEW_CAMERA = re.compile(r"[A-Za-z0-9_-]{1,32}")
PROVISIONAL_PRECISION = {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0}


def calibration_limits(samples: list[dict], lanes: list[str]) -> tuple[float, float]:
    """ADR-017's rule as P103 ran it: q33/q67 of each lane's next-60 s means, a window
    every 15 samples, pooled over lanes. Raises when the recording cannot set levels."""
    import numpy as np

    n, values = len(samples), []
    for start in range(0, n, CALIBRATION_STRIDE):
        end = start + CALIBRATION_T - 1
        if end + WINDOW >= n:
            continue
        for lane in lanes:
            values.append(sum(s["counts"][lane] for s in samples[end + 1:end + WINDOW + 1]) / WINDOW)
    if len(values) < 3:
        raise ValueError("the recording is too short to set this camera's levels")
    low, med = (float(v) for v in np.percentile(values, [33, 67]))
    if not low < med:
        raise ValueError(f"traffic barely varies in this recording (q33 = q67 = {low:.2f} vehicles), so it "
                         "cannot set LOW, MEDIUM and HIGH. Use a busier recording for this camera's first analysis")
    return round(low, 4), round(med, 4)


WINDOW = 30                      # as edge.persistence.WINDOW: 60 s of 2 s samples


def relevel(result: dict, profile: CameraProfile) -> dict:
    """The class forecasts and 'what then happened' again, from the stored counts,
    with the profile's current limits, through the real forecaster. Counts and the
    count forecast do not depend on the limits and are left as they are."""
    from edge.persistence import PersistenceForecaster, classify

    forecaster = PersistenceForecaster(profile.spec_path, profile.spec_key, profile.lane_map)
    samples = result["samples"]
    for sample in samples:
        level = forecaster.step(sample["counts"], sample["t"])
        sample["level"] = {a: c.value for a, c in level.predictions.items()} if level else None
    for k, sample in enumerate(samples):
        after = samples[k + 1:k + 1 + WINDOW]
        if len(after) == WINDOW:
            for lane, approach in profile.lane_map.items():
                mean = sum(s["counts"][lane] for s in after) / WINDOW
                sample["then"][approach]["level"] = classify(mean, forecaster.low, forecaster.med).value
    result["limits"] = {"low": forecaster.low, "med": forecaster.med}
    result["models"]["level"] = forecaster.model_id
    result["known_limits"] = list(profile.limitations)
    return result


class Cameras:
    """The committed profiles (`cameras/`, ADR-028) and this computer's provisional ones.

    A provisional profile is made in the dashboard: the viewer places each lane on
    their own video and names its approach. It is kept beside the results, never in
    `cameras/`, and says what it is in its limitations. Its levels are set from the
    first recording analysed with it (ADR-017's rule), so they flatter that
    recording and are not evidence. A camera id is a short public name, so the
    browser addresses a camera by it."""

    def __init__(self, committed: list[CameraProfile], folder: Path, root: Path = ROOT) -> None:
        self.committed, self.folder, self.root = list(committed), Path(folder), root
        self.lock = threading.Lock()

    def provisional(self) -> list[CameraProfile]:
        good = []
        for path in sorted(self.folder.glob("*.json")) if self.folder.is_dir() else []:
            try:
                good.append(load_profile(path, self.root))
            except ProfileError:
                continue
        return good

    def all(self) -> list[CameraProfile]:
        return [*self.committed, *self.provisional()]

    def get(self, camera_id) -> CameraProfile:
        for profile in self.all():
            if profile.camera_id == camera_id:
                return profile
        raise Refused(HTTPStatus.BAD_REQUEST, "that is not a camera on the list")

    def is_provisional(self, profile: CameraProfile) -> bool:
        return profile.path.resolve().parent == self.folder.resolve()

    def needs_levels(self, profile: CameraProfile) -> bool:
        if not self.is_provisional(profile):
            return False
        entry = json.loads(profile.spec_path.read_text(encoding="utf-8"))["cameras"][profile.spec_key]
        return not entry.get("calibrated", False)

    def listing(self) -> list[dict]:
        return [{"id": p.camera_id, "lanes": len(p.lanes), "directions_verified": p.directions_verified,
                 "provisional": self.is_provisional(p), "levels_set": not self.needs_levels(p),
                 # D42: so the page can lay the lanes over the viewer's own video before analysing.
                 "geometry": {"max_radius": p.max_radius,
                              "lanes": [{"name": name, "centre": list(centre), "approach": p.lane_map[name]}
                                        for name, centre in p.lanes]}}
                for p in self.all()]

    def _write(self, camera_id: str, lanes, max_radius: float, low: float, med: float, calibrated: bool,
               source: str, made_from: str) -> CameraProfile:
        spec = {"name": "workbench provisional levels",
                "method": "forecast for the next 60 s = class of the mean of each lane's last 30 counts (2 s step); "
                          "LOW if mean <= low, MEDIUM if <= med, else HIGH",
                "decision": "none: a provisional camera made in the workbench (D41), not reviewed",
                "cameras": {camera_id: {"low": low, "med": med, "source": source, "lanes": len(lanes),
                                        "calibrated": calibrated}},
                "confidence_is_measured_precision": PROVISIONAL_PRECISION,
                "confidence_source": "not measured for this camera; zeros because the forecaster needs the field, "
                                     "and the workbench never shows a confidence",
                "not_established": "anything: provisional levels, set on the recording they are shown on"}
        spec_bytes = json.dumps(spec, indent=2).encode("utf-8")
        digest = hashlib.sha256(spec_bytes).hexdigest()
        spec_path = self.folder / f"{camera_id}.{digest[:16]}.levels.json"
        profile = {
            "schema_version": 1, "camera_id": camera_id,
            "geometry": {"coordinates": "normalised_image", "max_radius": max_radius,
                         "lanes": [{"name": f"lane_{i}", "centre": [round(x, 4), round(y, 4)]}
                                   for i, (x, y, _) in enumerate(lanes)]},
            "lane_map": {f"lane_{i}": approach for i, (_, _, approach) in enumerate(lanes)},
            "calibration": {"persistence_spec": str(spec_path.resolve()),
                            "spec_sha256": digest, "key": camera_id},
            "limitations": [
                "Provisional camera made in the workbench: its lanes were placed by eye on one recording and "
                "have not been reviewed (ADR-028)",
                "Its levels were set from the first recording analysed with it, so they flatter that recording "
                "and are not evidence of anything" if calibrated else
                "Its levels are not set yet: the first analysis sets them from that recording"],
            "provenance": {"placed_by": "workbench user", "how": f"lane centres placed on {made_from} in the "
                                                                 "dashboard's Analyze a video page",
                           "record": "D41 provisional camera, kept on this computer, not committed"},
            "direction": {"status": "declared"}, "evidence": []}
        self.folder.mkdir(parents=True, exist_ok=True)
        if not spec_path.exists():
            pending_spec = spec_path.with_suffix(".tmp")
            pending_spec.write_bytes(spec_bytes)
            pending_spec.replace(spec_path)
        path = self.folder / f"{camera_id}.json"
        pending_profile = path.with_suffix(".tmp")
        pending_profile.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        pending_profile.replace(path)
        return load_profile(path, self.root)

    def create(self, camera_id, lanes, max_radius, made_from: str) -> CameraProfile:
        """`lanes` as [{"centre": [x, y], "approach": "N"}, ...] from the page. Refuses rather than repairs."""
        if not isinstance(camera_id, str) or not NEW_CAMERA.fullmatch(camera_id):
            raise Refused(HTTPStatus.BAD_REQUEST, "a camera name is 1 to 32 letters, digits, - or _")
        if not isinstance(lanes, list) or not 1 <= len(lanes) <= 4:
            raise Refused(HTTPStatus.BAD_REQUEST, "place one to four lanes")
        parsed = []
        for lane in lanes:
            centre = lane.get("centre") if isinstance(lane, dict) else None
            approach = lane.get("approach") if isinstance(lane, dict) else None
            if (not isinstance(centre, list) or len(centre) != 2
                    or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in centre)):
                raise Refused(HTTPStatus.BAD_REQUEST, "each lane needs a centre inside the picture")
            if approach not in ("N", "S", "E", "W"):
                raise Refused(HTTPStatus.BAD_REQUEST, "each lane needs one of N, S, E or W")
            parsed.append((float(centre[0]), float(centre[1]), approach))
        if len({a for _, _, a in parsed}) != len(parsed):
            raise Refused(HTTPStatus.BAD_REQUEST, "two lanes cannot share an approach")
        if isinstance(max_radius, bool) or not isinstance(max_radius, (int, float)) or not 0.02 <= max_radius <= 0.5:
            raise Refused(HTTPStatus.BAD_REQUEST, "the lane reach must be between 0.02 and 0.5 of the picture")
        with self.lock:
            if any(p.camera_id.casefold() == camera_id.casefold() for p in self.all()):
                raise Refused(HTTPStatus.CONFLICT, "a camera with that name exists; choose another name")
            return self._write(camera_id, parsed, float(max_radius), 0.0, 0.5, False,
                               "not set: waiting for the first analysis", made_from)

    def set_levels(self, profile: CameraProfile, low: float, med: float, clip: str) -> CameraProfile:
        raw = json.loads(profile.path.read_text(encoding="utf-8"))
        lanes = [(lane["centre"][0], lane["centre"][1], raw["lane_map"][lane["name"]])
                 for lane in raw["geometry"]["lanes"]]
        with self.lock:
            return self._write(profile.camera_id, lanes, raw["geometry"]["max_radius"], low, med, True,
                               f"workbench, set from {clip} (q33/q67 of 60 s means, ADR-017's rule)",
                               raw["provenance"]["how"].split(" on ", 1)[1].split(" in the ", 1)[0])


# ------------------------------------------------------------ the jobs ---

class VideoQueue:
    """A bounded FIFO for hosted offline jobs. Live uses its own worker."""

    def __init__(self, capacity=8):
        self.capacity = capacity
        self.jobs = deque()
        self.changed = threading.Condition()

    def reserve(self):
        with self.changed:
            if len(self.jobs) >= self.capacity:
                raise Refused(HTTPStatus.SERVICE_UNAVAILABLE,
                              "The analysis queue is full. Try again when a slot opens.")
            ticket = object()
            self.jobs.append(ticket)
            return ticket, len(self.jobs) > 1

    def wait(self, ticket, stopping):
        with self.changed:
            while not stopping.is_set() and self.jobs[0] is not ticket:
                self.changed.wait(timeout=.1)
            return not stopping.is_set()

    def release(self, ticket):
        with self.changed:
            self.jobs.remove(ticket)
            self.changed.notify_all()


class Analyses:
    """One analysis at a time. `runner` is `run_tool` except in the tests, and
    `inputs` is `tool_inputs` (hashing the detector weights once, on first use).
    A recording is addressed by its number and a camera by its id: never a path."""

    def __init__(self, recordings: list[Recording], cameras: Cameras, results_dir: Path, *,
                 runner=run_tool, inputs: Callable[[], dict] = tool_inputs, check=preflight,
                 fingerprint_of=fingerprint, clock=time.monotonic, locator: Locator | None = None, history=None,
                 catalogue_from=None, on_release=None, pause_file=None, queue=None) -> None:
        self.recordings, self.cameras, self.results_dir = list(recordings), cameras, Path(results_dir)
        if os.name == "nt":
            absolute = os.path.abspath(self.results_dir)
            # Hash-based result names add 78 characters, including the partial suffix.
            if len(absolute) + 79 >= 260 and not absolute.startswith("\\\\?\\"):
                absolute = "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
                self.results_dir = Path(absolute)
        self.runner, self._inputs_of, self.check = runner, inputs, check
        self.fingerprint_of, self.clock = fingerprint_of, clock
        self.locator = locator or Locator([], standard=False)
        self.history = history
        self._inputs: dict | None = None
        #: A recording that is also a replay clip, by its resolved path: the clip's number.
        self.replay: dict[Path, int] = {}
        self.lock = threading.Lock()
        self.catalogue_lock = catalogue_from.catalogue_lock if catalogue_from else threading.Lock()
        if catalogue_from:
            self.recordings = catalogue_from.recordings
        self.on_release = on_release
        self.pause_file = pause_file
        self.queue = queue
        self.thread: threading.Thread | None = None
        self.stopping = threading.Event()
        self._reset(None, None)

    def _reset(self, recording, profile) -> None:
        self.recording, self.profile = recording, profile
        self.stage_state = {key: "waiting" for key, _ in STAGES}
        self.stage_detail = {key: "" for key, _ in STAGES}
        self.levels_stage = False
        self.checks: list[Check] = []
        self.problem: str | None = None
        self.key: str | None = None
        self.partial: Path | None = None
        self.job_id: str | None = None
        self.cached = False
        self.waiting_for_slot = False
        self.monitor_updates = None
        self.started = self.clock()
        self.done = self.total = 0
        self.first: tuple[float, int] | None = None
        self.last_at: float | None = None

    # ------------------------------------------------------------------ lists ---
    def listing(self) -> dict:
        """Numbers and names only: a path never reaches the browser."""
        return {"recordings": [{"number": n, "name": r.name, "replay": self.replay.get(r.path)}
                               for n, r in enumerate(self.recordings, 1)],
                "cameras": self.cameras.listing()}

    def add(self, path: Path, *, upload_key=None) -> int:
        """The recording's number, adding it to the list if it is new."""
        path = Path(path).resolve()
        with self.catalogue_lock:
            for n, recording in enumerate(self.recordings, 1):
                if recording.path == path:
                    return n
            self.recordings.append(Recording(path, upload_key))
            return len(self.recordings)

    def locate(self, name, size, fp) -> dict:
        """Where the browser's file is on this computer, as a recording number."""
        if (not isinstance(name, str) or not 0 < len(name) <= 255 or "/" in name or "\\" in name
                or isinstance(size, bool) or not isinstance(size, int) or size <= 0
                or not isinstance(fp, str) or not KEY.fullmatch(fp)):
            raise Refused(HTTPStatus.BAD_REQUEST, "send the file's name, size and fingerprint")
        if Path(name).suffix.lower() not in VIDEO_SUFFIXES:
            raise Refused(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Use an MP4, MOV, AVI, MKV, M4V or WebM recording")
        if size > MAX_VIDEO_BYTES:
            raise Refused(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "The recording exceeds the 2 GB limit")
        for n, recording in enumerate(self.recordings, 1):
            if recording.name.casefold() == name.casefold():
                try:
                    if recording.path.stat().st_size == size and self.fingerprint_of(recording.path) == fp:
                        return {"found": True, "recording": n}
                except OSError:
                    continue
        path, complete = self.locator.find(name, size, fp, fingerprint_of=self.fingerprint_of)
        if path is None:
            return {"found": False, "searched_everything": complete}
        return {"found": True, "recording": self.add(path)}

    @staticmethod
    def _pick(number, items, what: str):
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(items):
            raise Refused(HTTPStatus.BAD_REQUEST, f"that is not a {what} on the list")
        return items[number - 1]

    # ------------------------------------------------------------------- jobs ---
    def start(self, recording_number, camera_id, *, pending_replay=False):
        recording = self._pick(recording_number, self.recordings, "recording")
        if not isinstance(camera_id, str):
            raise Refused(HTTPStatus.BAD_REQUEST, "that is not a camera on the list")
        profile = load_recording_profile(WHOLE_FRAME_PATH) if camera_id == WHOLE_FRAME else self.cameras.get(camera_id)
        with self.lock:
            if self.running():
                raise Refused(HTTPStatus.CONFLICT, "an analysis is in progress; stop it first")
            ticket, queued = self.queue.reserve() if self.queue else (None, False)
            try:
                self._reset(recording, profile)
                self.waiting_for_slot = queued
                self.levels_stage = profile.camera_id != WHOLE_FRAME and self.cameras.needs_levels(profile) and not pending_replay
                if self.history:
                    self.job_id = self.history.start(recording.name, recording.path.stat().st_size, profile.camera_id,
                                                     pending_replay=pending_replay, upload_key=recording.upload_key)
                self.monitor_updates = [] if pending_replay else None
                self.stopping = threading.Event()
                self.thread = threading.Thread(target=self._run, args=(recording, profile, self.stopping, ticket),
                                               daemon=True)
                self.thread.start()
            except Exception:
                if self.queue:
                    self.queue.release(ticket)
                if self.job_id:
                    self.history.finish(self.job_id, None, "The analysis worker could not start.")
                raise
            return self.job_id

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def stop(self, wait_s: float | None = None, *, identifier=None) -> bool:
        with self.lock:
            if identifier is not None and self.job_id != identifier:
                return False
            self.stopping.set()
            worker = self.thread
        if wait_s is not None and worker is not None:
            worker.join(wait_s)
        return True

    def clear_offline_workspace(self):
        self.stop(wait_s=10)
        with self.lock:
            if self.running():
                raise Refused(HTTPStatus.CONFLICT, "The offline analysis is still stopping. Try again in a moment.")
            key = self.key
            self._reset(None, None)
            self.thread = None
            self.stopping = threading.Event()
            return key

    def remove_cached_report(self, key):
        if KEY.fullmatch(key):
            for suffix in (".json", ".partial.json"):
                (self.results_dir / f"{key}{suffix}").unlink(missing_ok=True)

    def _set(self, stage: str, state: str, detail: str = "") -> None:
        with self.lock:
            self.stage_state[stage], self.stage_detail[stage] = state, detail

    def _fail(self, stage: str, reason: str) -> None:
        with self.lock:
            self.stage_state[stage], self.stage_detail[stage] = "failed", reason
            self.problem = reason

    def _progress(self, t: float, duration: float) -> None:
        with self.lock:
            self.done = int(round(t / STEP_S)) + 1
            self.total = max(self.done, int(math.ceil(duration / STEP_S)))
            now = self.clock()
            if self.first is None:
                self.first = (now, self.done)
                self.stage_detail["analyse"] = ""        # the detector is loaded: frames are arriving
            self.last_at = now

    def _monitor_frame(self, update):
        with self.lock:
            self.monitor_updates.append(update)

    def monitor_batch(self, identifier, offset):
        with self.lock:
            if identifier != self.job_id or self.monitor_updates is None:
                return None
            items = self.monitor_updates[offset:offset + 64]
            return {"items": items, "next": offset + len(items)}

    def _run(self, recording: Recording, profile: CameraProfile, stopping: threading.Event, ticket) -> None:
        try:
            if self.queue:
                admitted = self.queue.wait(ticket, stopping)
                with self.lock:
                    self.waiting_for_slot = False
                if not admitted:
                    self._fail("check", "stopped")
                    return
            self._steps(recording, profile, stopping)
        except Exception as error:      # noqa: BLE001 - shown on the page, not lost in a thread
            stage = next((k for k, _ in STAGES if self.stage_state[k] == "running"), "check")
            logging.getLogger(__name__).warning("Video job %s failed in %s (%s)", self.job_id, stage, type(error).__name__)
            self._fail(stage, f"{type(error).__name__}: {redact(str(error))}")
        finally:
            if self.partial:
                try:
                    self.partial.unlink(missing_ok=True)
                except OSError:
                    logging.getLogger(__name__).exception("Could not remove incomplete analysis %s", self.job_id)
            if self.history:
                complete = self.stage_state["open"] == "done"
                try:
                    path = self.result_path(self.key) if complete else None
                    result = json.loads(path.read_text(encoding="utf-8")) if path else None
                    self.history.finish(self.job_id, self.key if complete else None, self.problem, result)
                except Exception:
                    logging.getLogger(__name__).exception("Could not save analysis job %s", self.job_id)
                    self._fail("open", "Could not save the analysis job. Check local storage and retry.")
            if self.queue:
                self.queue.release(ticket)
            if self.on_release:
                self.on_release()

    def _key(self, recording: Recording, profile: CameraProfile) -> str:
        inputs = self._inputs if self.monitor_updates is None else {**self._inputs, "streaming_session": self.job_id}
        return analysis_key(recording.upload_key or self.fingerprint_of(recording.path), recording.path.stem, profile_hash(profile),
                            inputs)

    def _steps(self, recording: Recording, profile: CameraProfile, stopping: threading.Event) -> None:
        self._set("check", "running", "reading the video and the camera profile")
        if recording.path.is_file() and (recording.path.suffix.lower() not in VIDEO_SUFFIXES
                or not 0 < recording.path.stat().st_size <= MAX_VIDEO_BYTES):
            return self._fail("check", "Unsupported video format or file size. Use a non-empty video up to 2 GB.")
        checks, loaded, length = self.check(recording, profile.path)
        with self.lock:
            self.checks = checks
        refused = [c for c in checks if c.ok is False]
        if refused:
            return self._fail("check", f"{refused[0].name}: {refused[0].detail}")
        if self._inputs is None:
            self._set("check", "running", "fingerprinting the detector and the tool (once per session)")
            self._inputs = self._inputs_of()
        key = self._key(recording, loaded)
        final = self.results_dir / f"{key}.json"
        with self.lock:
            self.key = key
        self._set("check", "done", f"{loaded.camera_id}, {length / 60:.1f} min")
        if self.monitor_updates is None and final.exists() and validate_result(final, camera=loaded.camera_id, clip=recording.path.stem,
                                              duration_s=length) is None:
            with self.lock:
                self.cached = True
            self._set("analyse", "done", "analysed before with the same video, camera and detector")
            self._set("validate", "done", "the stored results passed the checks")
            self._set("open", "done", "")
            return None
        if stopping.is_set():
            return self._fail("analyse", "stopped")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        partial = self.results_dir / f"{key}.partial.json"
        self.partial = partial
        self._set("analyse", "running", "loading the detector")
        options = {"on_frame": self._monitor_frame} if self.monitor_updates is not None else {}
        code, tail = self.runner(recording.path, loaded.path, partial, self._progress, stopping, **options)
        if code == 130 or stopping.is_set():
            partial.unlink(missing_ok=True)
            return self._fail("analyse", "stopped")
        if code != 0:
            partial.unlink(missing_ok=True)
            last = next((line for line in reversed(tail) if line.strip() and not line.startswith("[h264 @")),
                        "no message")
            for path in (recording.path, loaded.path, partial):
                last = last.replace(str(path).replace("\\", "\\\\"), path.name).replace(str(path), path.name)
            return self._fail("analyse", f"the analysis tool exited with {code}: {redact(last)}")
        with self.lock:
            self.done = self.total       # the last progress line falls short of the end by up to 10 s
        self._set("analyse", "done", "")
        if self.levels_stage:
            self._set("levels", "running", "q33/q67 of 60 s means, as ADR-017 sets every camera's levels")
            try:
                result = json.loads(partial.read_text(encoding="utf-8"))
                low, med = calibration_limits(result["samples"], [name for name, _ in loaded.lanes])
            except ValueError:
                self._set("levels", "done", "Provisional limits retained. This recording has too little usable history or variation.")
            else:
                loaded = self.cameras.set_levels(loaded, low, med, recording.path.stem)
                partial.write_text(json.dumps(relevel(result, loaded), separators=(",", ":")), encoding="utf-8")
                key = self._key(recording, loaded)
                final = self.results_dir / f"{key}.json"
                with self.lock:
                    self.key, self.profile = key, loaded
                self._set("levels", "done", f"LOW up to {low:g}, MEDIUM up to {med:g} vehicles; set from this recording")
        self._set("validate", "running", "")
        reason = validate_result(partial, camera=loaded.camera_id, clip=recording.path.stem, duration_s=length)
        if reason:
            partial.unlink(missing_ok=True)
            return self._fail("validate", reason)
        os.replace(partial, final)
        self._set("validate", "done", "")
        self._set("open", "done", "")
        return None

    def snapshot(self) -> dict:
        with self.lock:
            stages = [{"id": key, "name": name, "state": self.stage_state[key], "detail": self.stage_detail[key]}
                      for key, name in STAGES if key != "levels" or self.levels_stage]
            checks = [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks]
            done, total, first, last_at = self.done, self.total, self.first, self.last_at
            state = dict(running=self.running(), stopping=self.stopping.is_set() and self.running(),
                         recording=self.recording.name if self.recording else None,
                         camera=self.profile.camera_id if self.profile else None,
                         problem=self.problem, cached=self.cached, stages=stages, checks=checks, job_id=self.job_id)
            ready = self.stage_state["open"] == "done" and self.key is not None
            key = self.key
            if self.waiting_for_slot:
                state["queued"] = True
        eta = None
        if first is not None and last_at is not None and done - first[1] >= ETA_AFTER and done < total:
            rate = (last_at - first[0]) / (done - first[1])
            eta = round(rate * (total - done))
        state["progress"] = {"done": done, "total": total, "eta_s": eta} if total else None
        state["key"] = key if ready else None
        if self.pause_file:
            state["queued"] = bool(state["running"] and not state["stopping"] and not state["problem"]
                                   and self.pause_file.exists() and not ready)
        state["status"] = status_text(state)
        return state

    def result_path(self, key: str) -> Path | None:
        """The stored results for this key, or None. Only a key, never a path, is accepted."""
        if not KEY.fullmatch(key or ""):
            return None
        path = self.results_dir / f"{key}.json"
        return path if path.is_file() else None


def status_text(s: dict) -> str:
    states = {stage["id"]: stage["state"] for stage in s["stages"]}
    if s["problem"] == "stopped":
        return "Stopped"
    if s["problem"]:
        return "Analysis refused or failed: see why below"
    if s["stopping"]:
        return "Stopping"
    if s.get("queued"):
        return "Queued — waiting for processing capacity"
    if states["open"] == "done":
        return "Analysed before: ready at once" if s["cached"] else "Analysis finished and checked"
    if states["validate"] == "running":
        return "Checking what the tool wrote"
    if states.get("levels") == "running":
        return "Setting this camera's levels"
    if states["analyse"] == "running":
        return "Analysing the recording"
    if states["check"] == "running":
        return "Checking the recording and its camera"
    return "Choose a video and the camera that recorded it"
