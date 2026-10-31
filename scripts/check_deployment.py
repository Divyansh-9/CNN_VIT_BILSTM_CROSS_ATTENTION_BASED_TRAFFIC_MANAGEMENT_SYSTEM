"""Is this machine able to run STMS, and this camera and source on it? (D30)

    python scripts/check_deployment.py --mosquitto <mosquitto.exe>
    python scripts/check_deployment.py --mosquitto <exe> --camera 150th_Eastgate --source clip.mp4 \\
        --approaches lane_0=N lane_1=S lane_2=E lane_3=W
    python scripts/check_deployment.py --camera 150th_Eastgate --source camera --approaches ...   # reads STMS_CAMERA_URL

Two levels. Without `--source` it checks the installation: runtime, detector, frozen
specs, broker, secrets tool, dashboard build, storage, ports, and which cameras are
configured. With `--source`, `--camera` and `--approaches` it also checks that exact
combination. `scripts/check_env.py` comes earlier: it runs on a bare interpreter
before anything is installed.

**Each line says how strong its evidence is.** PASS means what its text says and no
more. A FAIL is `missing`, `invalid` or `unreachable`, because the remedies differ. A
file that exists is weaker than a model that loaded, so `--quick` reports the stronger
checks as NOT CHECKED rather than passing them, and the result line counts them.

**It does not repeat the edge's rules.** The camera level calls `edge.run.parse_args`
and builds the two forecasters, so what it refuses is exactly what the edge would
refuse, in the edge's own words, and the two cannot drift apart.

**READY does not mean the system works.** It means nothing was found that stops it
starting. Only `scripts/demo_e2e.py` shows the deployed path working, and neither says
anything about forecast quality (S67) or a real camera's timing (S65).

**A lane map is declared, not verified.** Nothing in a video says which approach a
lane feeds, so the check says so rather than passing it.

No frame is written or sent: one is decoded to prove the source is readable, and
dropped (NFR-13). The stream URL is never printed: it can carry credentials.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

__all__ = ["Check", "installation", "main", "result_of", "selected"]

PASS, WARN, FAIL, NOT_CHECKED = "PASS", "WARN", "FAIL", "NOT CHECKED"
MISSING, INVALID, UNREACHABLE = "missing", "invalid", "unreachable"
SUPPORTED_PY = (3, 12)              # D4
PACKAGES = {"fastapi": "fastapi", "pydantic": "pydantic", "uvicorn": "uvicorn", "paho-mqtt": "paho.mqtt",
            "pyyaml": "yaml", "numpy": "numpy", "opencv-python-headless": "cv2", "ultralytics": None,
            "psutil": "psutil"}
SPEC_DIR = ROOT / "experiments" / "results" / "bellevue_pilot"
CORPUS = ROOT / "data" / "corpus_p103"
DIST = ROOT / "dashboard" / "dist"
STORE = ROOT / "data" / "server"
MIN_FREE_BYTES = 1024 ** 3
#: Samples a forecaster needs, at the 2 s step, before it says anything (edge.persistence, edge.count_forecast).
FIRST_CLASS_S, FIRST_COUNT_S, FIRST_COMPARISON_S = 60, 120, 180
PROBE_TIMEOUT_S = 20


@dataclass(frozen=True)
class Check:
    area: str
    status: str
    what: str
    kind: str = ""                  # for a FAIL: missing, invalid or unreachable
    action: str = ""                # what to do about it


def passed(area, what):
    return Check(area, PASS, what)


def warned(area, what, action=""):
    return Check(area, WARN, what, action=action)


def failed(area, kind, what, action=""):
    return Check(area, FAIL, what, kind, action)


def skipped(area, what):
    return Check(area, NOT_CHECKED, what)


# ---------------------------------------------------------------- installation --

def check_python(version=sys.version_info) -> Check:
    found = f"{version[0]}.{version[1]}"
    if tuple(version[:2]) == SUPPORTED_PY:
        return passed("runtime", f"Python {found}, the supported version")
    return warned("runtime", f"Python {found}; {SUPPORTED_PY[0]}.{SUPPORTED_PY[1]} is the supported version (D4)")


def pins(path: Path = ROOT / "requirements.txt") -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, version = line.split("#")[0].strip().partition("==")
        if sep:
            found[name.lower()] = version.strip()
    return found


def check_packages(pinned=None, version_of=importlib.metadata.version, importer=importlib.import_module) -> list[Check]:
    pinned = pins() if pinned is None else pinned
    out = []
    for package, module in PACKAGES.items():
        try:
            installed = version_of(package)
        except importlib.metadata.PackageNotFoundError:
            out.append(failed("runtime", MISSING, f"{package} is not installed", "pip install -r requirements.txt"))
            continue
        if module:
            try:
                importer(module)
            except Exception as error:  # noqa: BLE001 - a broken install raises anything, OSError on Windows
                out.append(failed("runtime", INVALID, f"{package} {installed} is installed but does not import "
                                                      f"({type(error).__name__})"))
                continue
        want = pinned.get(package)
        if want and want != installed:
            out.append(warned("runtime", f"{package} {installed}; requirements.txt pins {want}"))
        else:
            out.append(passed("runtime", f"{package} {installed}"))
    return out


def counting_block(mapping=None):
    """The detector settings, read the way the edge reads them. Raises what it raises."""
    from edge.classes import MAPPING_FILE
    from edge.run import load_counting

    return load_counting(mapping or MAPPING_FILE)


def check_detector(quick: bool, load=None, settings=counting_block) -> list[Check]:
    try:
        weights, conf, imgsz = settings()
    except Exception as error:      # noqa: BLE001 - reported, whatever the install raised
        return [failed("detector", INVALID, f"the counting settings cannot be read ({type(error).__name__}: {error})")]
    out = [passed("detector", f"counting settings: {Path(weights).name}, confidence {conf}, input size {imgsz}")]
    if not Path(weights).is_file():
        return out + [failed("detector", MISSING, f"weights not found: {weights}",
                             "weights are not in the repository; restore them (scripts/backup_models.py)")]
    out.append(passed("detector", "weights file exists"))
    if quick:
        return out + [skipped("detector", "weights not loaded (--quick)")]
    try:
        names = (load or load_detector)(weights)
    except Exception as error:      # noqa: BLE001 - a file can exist and still not load
        return out + [failed("detector", INVALID, f"weights exist but do not load ({type(error).__name__})")]
    return out + [passed("detector", f"weights load, {names} classes")]


def load_detector(weights) -> int:
    from ultralytics import YOLO

    return len(YOLO(str(weights)).names)


def check_compute(cuda_available=None) -> Check:
    try:
        if cuda_available is None:
            import torch

            cuda_available = torch.cuda.is_available()
    except Exception as error:      # noqa: BLE001 - a broken torch raises OSError, not ImportError
        return failed("runtime", INVALID, f"PyTorch does not import ({type(error).__name__})",
                      "python scripts/check_env.py")
    if cuda_available:
        return passed("runtime", "a CUDA GPU is available")
    return warned("runtime", "no CUDA GPU: the detector will run on CPU, and whether it keeps the 2 s step here is unmeasured")


def check_specs(spec_dir: Path = SPEC_DIR) -> list[Check]:
    from edge.count_forecast import RIDGE_V1_SHA256

    out = []
    persistence = spec_dir / "persistence_v1.json"
    try:
        cameras = json.loads(persistence.read_text(encoding="utf-8"))["cameras"]
        out.append(passed("config", f"persistence spec: {len(cameras)} cameras have thresholds"))
    except FileNotFoundError:
        out.append(failed("config", MISSING, f"persistence spec not found: {persistence}"))
    except (ValueError, KeyError, TypeError):
        out.append(failed("config", INVALID, f"persistence spec is not readable: {persistence}"))
    ridge = spec_dir / "p105_ridge_v1.json"
    if not ridge.is_file():
        out.append(failed("config", MISSING, f"ridge spec not found: {ridge}"))
    else:
        import hashlib

        digest = hashlib.sha256(ridge.read_bytes()).hexdigest()
        out.append(passed("config", "ridge spec is the frozen one (P105)") if digest == RIDGE_V1_SHA256
                   else failed("config", INVALID, "ridge spec is not the frozen one: only P105's is served"))
    return out


def check_cameras(spec_dir: Path = SPEC_DIR, corpus: Path = CORPUS) -> list[Check]:
    """What is configured. A camera with thresholds and no lanes here is not a fault of
    the installation, so it is a note; the camera level is where it would stop a run."""
    try:
        cameras = json.loads((spec_dir / "persistence_v1.json").read_text(encoding="utf-8"))["cameras"]
    except (OSError, ValueError, KeyError, TypeError):
        return [skipped("cameras", "no persistence spec to read")]
    out = []
    for camera in cameras:
        if (corpus / camera / "manifest.json").is_file():
            out.append(passed("cameras", f"{camera}: thresholds and lane geometry present"))
        else:
            out.append(warned("cameras", f"{camera}: thresholds present, no lane geometry at {corpus / camera}",
                              "pass --lanes at the camera level, or restore the corpus"))
    return out


def find_mosquitto(given: Path | None) -> Path | None:
    if given:
        return given
    found = shutil.which("mosquitto")
    return Path(found) if found else None


def check_broker(given: Path | None, quick: bool, connect_timeout_s: float = 8.0) -> list[Check]:
    exe = find_mosquitto(given)
    if exe is None:
        return [failed("broker", MISSING, "Mosquitto not found on PATH", "install it, or pass --mosquitto")]
    if not exe.is_file():
        return [failed("broker", MISSING, f"Mosquitto not found: {exe}")]
    out = [passed("broker", f"Mosquitto found: {exe.name}")]
    if not exe.with_name("mosquitto_passwd" + exe.suffix).is_file():
        out.append(failed("broker", MISSING, "mosquitto_passwd is not beside it: the broker's logins cannot be made"))
    if quick:
        return out + [skipped("broker", "Mosquitto not started (--quick)")]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="stms-check-", ignore_cleanup_errors=True) as tmp:
        conf = Path(tmp) / "probe.conf"
        conf.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\n", encoding="utf-8")
        try:
            broker = subprocess.Popen([str(exe), "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error:
            return out + [failed("broker", INVALID, f"Mosquitto does not start ({type(error).__name__})")]
        try:
            deadline = time.monotonic() + connect_timeout_s
            while time.monotonic() < deadline:
                if broker.poll() is not None:
                    return out + [failed("broker", INVALID, "Mosquitto exited during start-up")]
                with socket.socket() as attempt:
                    attempt.settimeout(0.5)
                    if attempt.connect_ex(("127.0.0.1", port)) == 0:
                        return out + [passed("broker", "Mosquitto starts and accepts a connection (no TLS or login in this probe)")]
                time.sleep(0.2)
            return out + [failed("broker", UNREACHABLE, "Mosquitto started but never accepted a connection")]
        finally:
            broker.terminate()
            try:
                broker.wait(5)
            except subprocess.TimeoutExpired:
                broker.kill()


def check_secrets_tool(which=shutil.which) -> Check:
    if which("openssl"):
        return passed("broker", "openssl found: local TLS secrets can be made")
    return warned("broker", "openssl not found: deploy/make_local_secrets.py cannot make local TLS secrets",
                  "only needed when generating them here")


def check_dashboard(dist: Path = DIST) -> Check:
    index = dist / "index.html"
    if not index.is_file():
        return failed("dashboard", MISSING, "no build: dashboard/dist/index.html", "cd dashboard && npm ci && npm run build")
    html = index.read_text(encoding="utf-8")
    assets = re.findall(r'(?:src|href)="[^"]*?/?(assets/[^"]+)"', html)
    absent = [a for a in assets if not (dist / a).is_file()]
    if absent or not assets:
        return failed("dashboard", INVALID, f"the build is incomplete: {absent or 'it references no assets'}",
                      "cd dashboard && npm run build")
    return passed("dashboard", f"built, all {len(assets)} referenced assets present")


def check_storage(store: Path = STORE, free_of=lambda p: shutil.disk_usage(p).free) -> list[Check]:
    try:
        store.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=store):
            pass
    except OSError as error:
        return [failed("storage", INVALID, f"{store} is not writable ({type(error).__name__})")]
    out = [passed("storage", f"{store} is writable")]
    free = free_of(store)
    if free < MIN_FREE_BYTES:
        out.append(warned("storage", f"{free / 1024 ** 3:.1f} GB free; raw counts alone grow by about 170,000 rows a day until pruned at 48 h"))
    else:
        out.append(passed("storage", f"{free / 1024 ** 3:.0f} GB free"))
    return out


def holder_of(port: int) -> str:
    """Who holds a port, when the system will say."""
    try:
        import psutil

        for connection in psutil.net_connections(kind="inet"):
            if connection.laddr and connection.laddr.port == port and connection.status == psutil.CONN_LISTEN and connection.pid:
                return f"{psutil.Process(connection.pid).name()} (pid {connection.pid})"
    except Exception:               # noqa: BLE001 - naming it is a courtesy, not the check
        pass
    return "an unidentified process"


def check_ports(ports: dict[str, int]) -> list[Check]:
    from scripts.demo_live import port_free

    out = []
    for name, port in ports.items():
        if port_free(port):
            out.append(passed("ports", f"{name} port {port} is free"))
        else:
            out.append(failed("ports", INVALID, f"{name} port {port} is held by {holder_of(port)}",
                              "stop it, or choose another port"))
    return out


def installation(args) -> list[Check]:
    return [check_python(), *check_packages(), check_compute(), *check_detector(args.quick), *check_specs(),
            *check_cameras(), *check_broker(args.mosquitto, args.quick), check_secrets_tool(), check_dashboard(),
            *check_storage(), *check_ports({"server": args.http_port, "broker": args.mqtt_port})]


# ------------------------------------------------------------------ one camera --

def edge_argv(args) -> list[str]:
    lanes = args.lanes or CORPUS / args.camera / "manifest.json"
    return ["--source", str(args.source), "--lanes", str(lanes), "--camera", args.camera,
            "--intersection-id", args.intersection_id, "--approaches", *args.approaches]


def check_edge_accepts(args):
    """The edge's own refusal, in its own words. Returns (check, settings or None)."""
    from edge.run import parse_args

    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            settings = parse_args(edge_argv(args))
    except SystemExit:
        lines = [line for line in err.getvalue().splitlines() if "error:" in line]
        reason = lines[-1].split("error:", 1)[1].strip() if lines else "refused"
        kind = MISSING if "no such" in reason or "not set" in reason else INVALID
        return failed("camera", kind, f"the edge would refuse this: {reason}", configured_note()), None
    return passed("camera", f"the edge accepts {args.camera}: lanes, approaches and thresholds agree"), settings


def configured_note(spec_dir: Path = SPEC_DIR) -> str:
    """A new camera needs reviewed lanes and its own calibrated thresholds first (ADR-017)."""
    try:
        cameras = json.loads((spec_dir / "persistence_v1.json").read_text(encoding="utf-8"))["cameras"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return f"cameras with thresholds: {', '.join(cameras)}. Any other needs reviewed lanes and its own calibration first"


def check_forecasters(settings) -> list[Check]:
    from edge.count_forecast import RidgeCountForecaster
    from edge.persistence import PersistenceForecaster

    out = []
    try:
        persistence = PersistenceForecaster(settings.persistence_spec, settings.camera, settings.approaches)
        out.append(passed("camera", f"class forecaster builds for this camera (LOW up to {persistence.low:.3g}, MEDIUM up to {persistence.med:.3g})"))
    except Exception as error:      # noqa: BLE001 - reported in its own words
        out.append(failed("camera", INVALID, f"class forecaster refused: {error}"))
    try:
        RidgeCountForecaster(settings.ridge_spec, settings.approaches)
        out.append(passed("camera", "count forecaster builds on the frozen spec"))
    except Exception as error:      # noqa: BLE001
        out.append(failed("camera", INVALID, f"count forecaster refused: {error}"))
    return out


def check_calibration_overlap(camera: str, source, spec_dir: Path = SPEC_DIR) -> list[Check]:
    """Running on the hour the thresholds came from says nothing about new traffic."""
    from scripts.demo_live import CALIBRATED_ON

    try:
        entry = json.loads((spec_dir / "persistence_v1.json").read_text(encoding="utf-8"))["cameras"][camera]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    hour = CALIBRATED_ON.search(entry.get("source", ""))
    if hour and f"{hour[1]}_{hour[2]}-{hour[3]}" in Path(str(source)).stem:
        return [warned("camera", "this clip is the hour this camera's thresholds were calibrated on")]
    return []


PROBE = """
import os, sys
os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF"); os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
import cv2
capture = cv2.VideoCapture(os.environ["STMS_PROBE_SOURCE"])
ok, frame = capture.read() if capture.isOpened() else (False, None)
if not ok:
    sys.exit(3)
fps, frames = capture.get(cv2.CAP_PROP_FPS), capture.get(cv2.CAP_PROP_FRAME_COUNT)
print(f"{frame.shape[1]} {frame.shape[0]} {fps} {frames}")
"""


def read_source(source: str, timeout_s: float = PROBE_TIMEOUT_S):
    """(width, height, fps, frames) from one decoded frame, in a child process, because
    OpenCV can block on a dead stream. The frame is dropped there. The source travels
    in the environment, so a URL never reaches a command line or a message."""
    env = {**os.environ, "STMS_PROBE_SOURCE": source}
    result = subprocess.run([sys.executable, "-c", PROBE], env=env, capture_output=True, text=True, timeout=timeout_s)
    if result.returncode != 0:
        return None
    width, height, fps, frames = result.stdout.split()
    return int(width), int(height), float(fps), float(frames)


def check_source(args, reader=read_source) -> list[Check]:
    if args.source == "camera":
        url = os.environ.get("STMS_CAMERA_URL", "").strip()
        if not url:
            return [failed("source", MISSING, "STMS_CAMERA_URL is not set")]
        name, source, kind = "the camera stream", url, UNREACHABLE
    else:
        name, source, kind = Path(str(args.source)).name, str(args.source), INVALID
    if args.quick:
        return [skipped("source", f"{name} not decoded (--quick)")]
    try:
        read = reader(source)
    except subprocess.TimeoutExpired:
        return [failed("source", UNREACHABLE, f"{name} gave no frame within {PROBE_TIMEOUT_S} s")]
    if read is None:
        return [failed("source", kind, f"{name} gives no frame")]
    width, height, fps, frames = read
    out = [passed("source", f"{name}: one frame decoded, {width}x{height} at {fps:.1f} fps, and dropped")]
    if args.source == "camera":
        return out + [skipped("source", "whether the stream keeps the 2 s step is S65's to measure, not this check's")]
    duration = frames / fps if fps > 0 and frames > 0 else None
    if duration is None:
        return out + [warned("source", "its length cannot be read")]
    for need, what in ((FIRST_CLASS_S, "a class forecast"), (FIRST_COUNT_S, "a count forecast"),
                       (FIRST_COMPARISON_S, "a count comparison")):
        if duration < need:
            return out + [warned("source", f"{duration:.0f} s long: too short for {what} (about {need} s of history)")]
    return out + [passed("source", f"{duration / 60:.0f} minutes long, enough for every forecast and check")]


def selected(args) -> list[Check]:
    accepted, settings = check_edge_accepts(args)
    out = [accepted]
    if settings is None:
        out.append(skipped("camera", "forecasters not built: the edge would not start"))
    else:
        out += check_forecasters(settings)
        out += check_calibration_overlap(args.camera, args.source)
        out.append(warned("camera", "the lane map is as you declared it: nothing here can tell which approach a lane feeds"))
    return out + check_source(args)


# ------------------------------------------------------------------- reporting --

def result_of(checks: list[Check]) -> str:
    counts = {s: sum(c.status == s for c in checks) for s in (PASS, WARN, FAIL, NOT_CHECKED)}
    tally = f"{counts[PASS]} passed, {counts[WARN]} warnings, {counts[FAIL]} failed, {counts[NOT_CHECKED]} not checked"
    return f"{'BLOCKED' if counts[FAIL] else 'READY'}: {tally}"


def render(checks: list[Check]) -> str:
    lines, area = [], None
    for check in checks:
        if check.area != area:
            area = check.area
            lines.append(f"\n{area}")
        kind = f"{check.kind}: " if check.kind else ""
        lines.append(f"  [{check.status}] {kind}{check.what}")
        if check.action:
            lines.append(f"      -> {check.action}")
    lines += ["", result_of(checks),
              "READY means nothing was found that stops it starting. It does not show the system working",
              "(scripts/demo_e2e.py does that), forecast quality (S67) or a real camera's timing (S65)."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mosquitto", type=Path, help="mosquitto executable; otherwise looked for on PATH")
    ap.add_argument("--source", help="a video file, or 'camera' for the stream in STMS_CAMERA_URL")
    ap.add_argument("--camera", help="the camera's key in the persistence spec")
    ap.add_argument("--approaches", nargs="+", metavar="LANE=DIR", help="every lane's approach, e.g. lane_0=N")
    ap.add_argument("--lanes", type=Path, help="a reviewed lane file; default data/corpus_p103/<camera>/manifest.json")
    ap.add_argument("--intersection-id", default="check")
    ap.add_argument("--quick", action="store_true", help="do not load the detector, start Mosquitto or decode the source")
    ap.add_argument("--json", action="store_true", help="print the checks as JSON")
    ap.add_argument("--http-port", type=int, default=18000)
    ap.add_argument("--mqtt-port", type=int, default=18883)
    args = ap.parse_args(argv)
    given = [args.source, args.camera, args.approaches]
    if any(given) and not all(given):
        ap.error("--source, --camera and --approaches go together: they name one combination")
    checks = installation(args)
    if args.source:
        checks += selected(args)
    if args.json:
        print(json.dumps({"result": result_of(checks), "checks": [asdict(c) for c in checks]}, indent=1))
    else:
        print(render(checks))
    return 1 if any(c.status == FAIL for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
