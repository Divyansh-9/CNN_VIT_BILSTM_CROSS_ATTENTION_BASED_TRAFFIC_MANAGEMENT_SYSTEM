"""Run one recorded clip through the deployed path, for an evaluator to watch (D28).

    python scripts/demo_live.py --mosquitto <mosquitto.exe> --clips-root <footage folder> --list
    python scripts/demo_live.py --mosquitto <mosquitto.exe> --clips-root <footage folder>
    python scripts/demo_live.py --mosquitto <exe> --clips-root <dir> --clip 1 --hold 0

It adds a menu, a readiness gate and a run sheet to `scripts/demo_e2e.py`'s
`Stack`, and no logic of its own: the broker, the server, the ingest and
`python -m edge.run` run exactly as deployed.

**Only clips that can run are offered.** A camera needs thresholds in the frozen
persistence spec and lane geometry in `data/corpus_p103/<camera>/`, and the edge
refuses to start without them. The hour its thresholds were calibrated on is
left out, so a demonstration never runs on its own calibration data.

**Nothing starts on a stack that is not ready.** `Stack` would answer a health
check from an old server still holding the port, so a busy port is refused
first. A started ingest proves nothing, so one heartbeat goes through TLS, the
broker, the ingest and the store, and is read back from the API before the edge
starts. Each failure names the part that failed, and the exit status is 1.

**A short clip shows nothing.** The forecasters need history first: the first
class forecast comes after 1 min, the first count forecast and ribbon cell after
2, the first count comparison after 3. Less than 5 minutes is refused.

**What it does not establish:** the same as `demo_e2e.py`. Replay is not a live
camera (S65), and the ribbon is agreement with the detector's own counts, not
accuracy. The dashboard shows no video, and none leaves the edge (NFR-13).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.broker import PASSWORD_ENV, USERNAME_ENV, Credentials  # noqa: E402
from contracts.mqtt import Heartbeat, Mode, Topic  # noqa: E402
from scripts.console import use_utf8  # noqa: E402
from scripts.demo_e2e import APPROACHES, Stack  # noqa: E402

use_utf8()

__all__ = ["Clip", "NotReady", "available_clips", "main", "readiness", "run_demo", "run_sheet"]

SPEC = ROOT / "experiments" / "results" / "bellevue_pilot" / "persistence_v1.json"
CORPUS = ROOT / "data" / "corpus_p103"
DATABASE = ROOT / "data" / "server" / "stms.sqlite"
LIVE_ID = "live"
PROBE_ID = "readiness-probe"
#: The clip every integration run used, so it is offered first and marked.
REHEARSED = "Bellevue_150th_Eastgate__2017-09-11_10-08-31"
NAME = re.compile(r"^Bellevue_(?P<camera>.+?)__(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2})-\d{2}$")
CALIBRATED_ON = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2})")
MIN_MINUTES = 5.0
DEFAULT_MINUTES = 7.0
READY_TIMEOUT_S = 60.0
EDGE_START_S = 120.0
MILESTONES = ("the edge reports a replay", "first class forecast", "first count forecast",
              "first ribbon cell", "first count comparison")


class NotReady(RuntimeError):
    """A part of the stack failed before the edge started. Says which."""


@dataclass(frozen=True)
class Clip:
    path: Path
    camera: str

    @property
    def id(self) -> str:
        return self.path.stem


def supported_cameras(spec_path: Path = SPEC, corpus: Path = CORPUS) -> dict[str, str | None]:
    """Camera -> the hour its thresholds were calibrated on, for each camera with
    thresholds and with lane geometry covering the stack's lane map."""
    lanes = sorted(item.split("=")[0] for item in APPROACHES)
    cameras = {}
    for camera, entry in json.loads(spec_path.read_text(encoding="utf-8"))["cameras"].items():
        manifest = corpus / camera / "manifest.json"
        if not manifest.is_file():
            continue
        if sorted(json.loads(manifest.read_text(encoding="utf-8")).get("lanes", [])) != lanes:
            continue
        hour = CALIBRATED_ON.search(entry.get("source", ""))
        cameras[camera] = f"{hour[1]}_{hour[2]}-{hour[3]}" if hour else None
    return cameras


def available_clips(root: Path, spec_path: Path = SPEC, corpus: Path = CORPUS) -> list[Clip]:
    """Every clip that can run, the rehearsed one first."""
    cameras = supported_cameras(spec_path, corpus)
    clips = []
    for path in root.rglob("*.mp4"):
        name = NAME.match(path.stem)
        if name and name["camera"] in cameras and name["stamp"] != cameras[name["camera"]]:
            clips.append(Clip(path, name["camera"]))
    return sorted(clips, key=lambda c: (c.id != REHEARSED, c.id))


def choose(clips: list[Clip], clip: str | None, ask=input) -> Clip:
    """By number or by id; asked for when not given. Raises ValueError."""
    if clip is None:
        print_menu(clips)
        clip = ask(f"Clip number [1-{len(clips)}]: ").strip()
    if clip.isdigit() and 1 <= int(clip) <= len(clips):
        return clips[int(clip) - 1]
    for candidate in clips:
        if candidate.id == clip:
            return candidate
    raise ValueError(f"{clip!r} is not one of the {len(clips)} clips that can run; see --list")


def print_menu(clips: list[Clip]) -> None:
    for number, clip in enumerate(clips, 1):
        mark = "  (rehearsed)" if clip.id == REHEARSED else ""
        print(f"  {number:2d}. {clip.id}{mark}", flush=True)


def port_free(port: int) -> bool:
    """Whether this port could be bound now, which is what starting a service needs.
    Connecting cannot say: a socket bound but not listening refuses, and so, measured
    on Windows, did a listener with a backlog of 1 (D30). This is a snapshot: a service
    that loses the port afterwards exits, and `readiness` names it."""
    with socket.socket() as probe:
        if os.name != "nt":          # POSIX: a closed socket's TIME_WAIT is not a holder.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # On Windows this would allow a hijack.
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def connect_broker(stack):
    """A logged-in TLS connection, with the edge's own account. Raises NotReady."""
    from edge.mqtt_transport import MqttTransport

    env = stack.env("edge.env")
    transport = MqttTransport("localhost", stack.args.mqtt_port, client_id="demo-readiness",
                              credentials=Credentials(env[USERNAME_ENV], env[PASSWORD_ENV]),
                              ca_file=stack.work / "secrets" / "ca.crt")
    if not transport.start(10.0):
        refused = transport.connect_refused
        transport.stop()
        raise NotReady(f"broker: refused the connection ({refused})" if refused
                       else "broker: not reachable over TLS")
    return transport


def tail(stack, name: str, lines: int = 5) -> str:
    """The end of one part's log. These logs hold no secret (D17's E9 checks)."""
    log = stack.work / f"{name}.log"
    if not log.is_file():
        return ""
    return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def alive(stack, *names: str) -> None:
    for name in names:
        if stack.procs[name].poll() is not None:
            raise NotReady(f"{name}: exited during start-up\n{tail(stack, name)}")


def readiness(stack, connect=connect_broker, *, timeout_s: float = READY_TIMEOUT_S, sleep=time.sleep) -> None:
    """Broker, server and ingest, each proven to work, or NotReady naming it."""
    alive(stack, "broker", "server", "ingest")
    transport = connect(stack)
    try:
        if not stack.wait_until(lambda: stack.get("/health")[0] == 200, timeout_s):
            raise NotReady("server: no answer on /health")
        topic = Topic.HEARTBEAT.render(PROBE_ID)
        waited = 0.0
        while stack.get(f"/heartbeat/{PROBE_ID}/latest")[0] != 200:
            alive(stack, "broker", "server", "ingest")
            if waited >= timeout_s:
                raise NotReady("ingest: running, but a message through the broker was never stored")
            transport.publish(topic, Heartbeat("online", Mode.NORMAL, False, False).encode(), Topic.HEARTBEAT.qos)
            sleep(1.0)
            waited += 1.0
    finally:
        transport.stop()


def run_sheet(clip: Clip, minutes: float, url: str) -> str:
    return "\n".join([
        "",
        "RUN SHEET",
        f"  Open now:   {url}",
        f"  Clip:       {clip.id}, {minutes:g} minutes, played in real time",
        "",
        "  Say first:",
        "    - This is recorded footage being replayed, not a camera. The page says REPLAY.",
        "      A real camera stream has not been qualified yet (S65).",
        "    - It forecasts the traffic of the next 60 s, per approach: a congestion class and a count.",
        "      It does not predict or control the signal. The signal heads read 'not connected' (P97a).",
        "",
        "  What appears, and when:",
        "    about 1 min   first congestion class forecast",
        "    about 2 min   first count forecast; first ribbon cell (class only)",
        "    about 3 min   first count comparison in the ribbon",
        "    each minute   one more ribbon cell",
        "    (these follow the edge reporting a replay, which took 12 to 57 s; a cold start is the slow end)",
        "",
        "  If asked about the ribbon: it is agreement with the detector's own later counts, not accuracy.",
        "  Do not restart the edge during the demo: for up to 60 s the old forecast can look fresh (D27).",
        "",
        "  Optional, only if your guide has cleared showing this footage (its licence is unresolved):",
        f"    open {clip.path}",
        "    in a video player beside the page. It is a local file, so no frame crosses the network.",
        "    The player is only a picture: pausing or seeking it does not move the system.",
        "",
    ])


def reached(stack) -> set[str]:
    """Which milestones the API shows now. Read-only, like the page."""
    done = set()
    status, beat = stack.get(f"/heartbeat/{LIVE_ID}/latest")
    if status == 200 and (beat.get("source") or {}).get("kind") == "replay":
        done.add(MILESTONES[0])
    if stack.get(f"/prediction/{LIVE_ID}/latest")[0] == 200:
        done.add(MILESTONES[1])
    if stack.get(f"/count_forecast/{LIVE_ID}/latest")[0] == 200:
        done.add(MILESTONES[2])
    status, checks = stack.get(f"/forecast_check/{LIVE_ID}/recent")
    if status == 200:
        cells = [s for s in checks["slots"] if s["kind"] == "check"]
        if cells:
            done.add(MILESTONES[3])
        if any(s["counts"] for s in cells):
            done.add(MILESTONES[4])
    return done


def watch(stack, edge, *, poll_s: float = 2.0, edge_start_s: float = EDGE_START_S, sleep=time.sleep) -> tuple[int, set[str]]:
    """Report each milestone as it happens, until the edge ends."""
    seen: set[str] = set()
    waited = 0.0
    while True:
        running = edge.poll() is None
        now = reached(stack)
        for milestone in MILESTONES:
            if milestone in now and milestone not in seen:
                seen.add(milestone)
                stack.mark(milestone)
        if not running:
            return edge.returncode, seen
        if MILESTONES[0] not in seen and waited >= edge_start_s:
            edge.terminate()
            edge.wait(10)
            return 1, seen
        sleep(poll_s)
        waited += poll_s


def hold(stack, seconds: float, *, step_s: float = 30.0, sleep=time.sleep) -> None:
    """Keep the page up after the footage ends: staleness is part of the story."""
    remaining = seconds
    while remaining > 0:
        stack.mark(f"stopping in {remaining:.0f} s; Ctrl+C stops now")
        sleep(min(step_s, remaining))
        remaining -= step_s


def run_demo(args, stack, connect=connect_broker, sleep=time.sleep) -> int:
    """The whole run. Returns the exit status; the caller stops what was started."""
    stack.start_broker(), stack.start_server(), stack.start_ingest()
    try:
        readiness(stack, connect, sleep=sleep)
    except NotReady as error:
        stack.mark(f"NOT READY, the edge was not started. {error}")
        return 1
    stack.mark("ready: broker, server and ingest each carried a real message")
    url = f"{stack.base}/dashboard/?id={LIVE_ID}"
    print(run_sheet(args.chosen, args.minutes, url), flush=True)
    stack.start_edge(LIVE_ID, int(args.minutes * 30))
    code, seen = watch(stack, stack.procs["edge"], sleep=sleep)
    if code != 0:
        stack.mark(f"FAILED: the edge ended with status {code}\n{tail(stack, 'edge')}")
        return 1
    missing = [m for m in MILESTONES if m not in seen]
    if missing:
        stack.mark(f"FAILED: the replay ended without: {', '.join(missing)}\n{tail(stack, 'edge')}")
        return 1
    stack.mark("replay finished; the page now shows the streams going stale")
    hold(stack, args.hold, sleep=sleep)
    stack.mark("DONE")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mosquitto", type=Path, required=True, help="mosquitto executable; mosquitto_passwd beside it")
    ap.add_argument("--clips-root", type=Path, required=True, help="folder holding the clips; nothing is copied from it")
    ap.add_argument("--list", action="store_true", help="print the clips that can run, and stop")
    ap.add_argument("--clip", help="a number from --list, or a clip id; asked for when omitted")
    ap.add_argument("--minutes", type=float, default=DEFAULT_MINUTES,
                    help=f"footage to play, at least {MIN_MINUTES:g} (default {DEFAULT_MINUTES:g})")
    ap.add_argument("--hold", type=float, default=180.0, help="seconds to keep the page up afterwards; 0 for none")
    ap.add_argument("--http-port", type=int, default=18000)
    ap.add_argument("--mqtt-port", type=int, default=18883)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    if not args.clips_root.is_dir():
        ap.error(f"--clips-root is not a folder: {args.clips_root}")
    clips = available_clips(args.clips_root)
    if not clips:
        ap.error(f"no clip that can run under {args.clips_root}: it needs a camera with thresholds and lane geometry")
    if args.list:
        print_menu(clips)
        return 0
    if not args.mosquitto.is_file():
        ap.error(f"--mosquitto is not a file: {args.mosquitto}")
    if args.minutes < MIN_MINUTES:
        ap.error(f"--minutes {args.minutes:g} would show almost nothing: the first count comparison takes "
                 f"about 3 minutes, so at least {MIN_MINUTES:g} is needed")
    try:
        args.chosen = choose(clips, args.clip)
    except (ValueError, EOFError) as error:
        ap.error(str(error) or "no clip chosen; pass --clip")
    for port, flag in ((args.http_port, "--http-port"), (args.mqtt_port, "--mqtt-port")):
        if not port_free(port):
            print(f"NOT READY, nothing was started. {flag} {port} is already in use: stop what holds it "
                  f"(an earlier demo?) or choose another port.", file=sys.stderr, flush=True)
            return 1
    args.clip, args.camera = args.chosen.path, args.chosen.camera
    return run_with_cleanup(args)


def run_with_cleanup(args, stack_class=None, sleep=time.sleep) -> int:
    """Stops only what this run started, and puts an existing database back.
    `stack_class` and `sleep` let `demo_launcher` report and stop a run."""
    aside = DATABASE.with_name(DATABASE.name + ".before-demo")
    if DATABASE.exists():
        os.replace(DATABASE, aside)
    # ignore_cleanup_errors: on Windows a log can still be held as the last child exits.
    with tempfile.TemporaryDirectory(prefix="stms-demo-", ignore_cleanup_errors=True) as tmp:
        stack = (stack_class or Stack)(args, Path(tmp))
        try:
            stack.prepare_broker()
            return run_demo(args, stack, sleep=sleep)
        except KeyboardInterrupt:
            stack.mark("interrupted; stopping what this run started")
            return 130
        finally:
            for name in list(stack.procs):
                stack.stop(name)
            DATABASE.unlink(missing_ok=True)
            if aside.exists():
                os.replace(aside, DATABASE)


if __name__ == "__main__":
    raise SystemExit(main())
