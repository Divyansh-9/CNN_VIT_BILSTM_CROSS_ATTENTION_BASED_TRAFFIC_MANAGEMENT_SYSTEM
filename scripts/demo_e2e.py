"""The deployed path, end to end, on real footage (D17).

    python scripts/demo_e2e.py --mosquitto <mosquitto.exe> --clips-root <footage folder>
    python scripts/demo_e2e.py --mosquitto <exe> --clips-root <dir> --live 20

Runs the services natively: Mosquitto with login and TLS (`deploy/mosquitto.conf`),
the server, the ingest, and the deployed edge (`python -m edge.run`) on one
Bellevue clip with that camera's own lane geometry. `scripts/demo_pipeline.py`
is the other demonstration: it runs the corpus chain on synthetic data, while
this one runs the deployed runtime on real footage.

**Verify mode** (the default) runs nine checks and exits 1 if any fails:
- E1: the stack starts with no manual step;
- E2: the edge finishes its samples;
- E3: both forecasts arrive;
- E4: every forecast the server stored equals an independent replay of the
  offline corpus counts (`data/corpus_p103`) through the same forecasters;
- E5: the dashboard is served;
- E6: a stopped edge reads stale;
- E7: the store survives a restart;
- E8: the edge recovers;
- E9: no secret is in any log, and no file is written into the repository.

**`--live MINUTES`** runs the stack and the edge for you to watch at
`/dashboard/?id=live`, and checks nothing.

**What it does not establish.**
- **Not accuracy:** a dashboard can show forecasts that are wrong. That is
  P103, P105 and S67's human labels.
- **No live camera** (S65), **no Indian traffic,** and **not a fresh
  machine.**
- **Not MFSTNet:** the live forecasts come from persistence and ridge
  (ADR-027).

**Throwaway secrets.** They come from `deploy/make_local_secrets.py`, are
written to a temporary folder outside the repository, and are deleted at the
end. Frames are counted and dropped in memory (NFR-13).

Needs `data/corpus_p103/<camera>/` (the lane geometry and the offline counts),
the detector weights, and the footage, none of which is committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
APPROACHES = ("lane_0=N", "lane_1=S", "lane_2=E", "lane_3=W")
CHECKS = ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9")


CAMERA_SOURCE = "camera"   # as edge.run.CAMERA_SOURCE; that module is not imported here


class Stack:
    """The native services, their logs, and the secrets they share."""

    def __init__(self, args, work: Path):
        self.args, self.work, self.procs = args, work, {}
        self.base = f"http://127.0.0.1:{args.http_port}"
        self.started = time.monotonic()

    def mark(self, text: str) -> None:
        print(f"[{time.monotonic() - self.started:7.1f}s] {text}", flush=True)

    def env(self, name: str) -> dict[str, str]:
        text = (self.work / "secrets" / name).read_text(encoding="utf-8")
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def prepare_broker(self) -> None:
        """deploy/mosquitto.conf with this run's paths and port; passwords hashed by mosquitto_passwd."""
        from deploy.make_local_secrets import main as make_secrets

        if make_secrets(["--out", str(self.work / "secrets")]) != 0:
            raise SystemExit("could not generate the throwaway secrets (openssl missing?)")
        broker = self.work / "broker"
        broker.mkdir()
        for name in ("broker.crt", "broker.key"):
            shutil.copyfile(self.work / "secrets" / name, broker / name)
        shutil.copyfile(self.work / "secrets" / "passwd.plain", broker / "passwd")
        passwd = self.args.mosquitto.with_name("mosquitto_passwd" + self.args.mosquitto.suffix)
        subprocess.run([str(passwd), "-U", str(broker / "passwd")], check=True, capture_output=True)
        conf = (ROOT / "deploy" / "mosquitto.conf").read_text(encoding="utf-8")
        conf = (conf.replace("listener 8883 0.0.0.0", f"listener {self.args.mqtt_port} 127.0.0.1")
                .replace("/mosquitto/broker/", broker.as_posix() + "/")
                .replace("persistence_location /mosquitto/data/",
                         f"persistence_location {(self.work / 'data').as_posix()}/")
                .replace("log_dest stdout", f"log_dest file {(self.work / 'broker.log').as_posix()}"))
        (self.work / "data").mkdir()
        (self.work / "mosquitto.conf").write_text(conf, encoding="utf-8")

    def start(self, name: str, argv: list[str], env: dict[str, str] | None = None) -> None:
        log = (self.work / f"{name}.log").open("a", encoding="utf-8")
        self.procs[name] = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                            env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})})

    def stop(self, name: str) -> None:
        proc = self.procs.pop(name, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def start_broker(self) -> None:
        self.start("broker", [str(self.args.mosquitto), "-c", str(self.work / "mosquitto.conf")])

    def start_server(self) -> None:
        self.start("server", [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1",
                              "--port", str(self.args.http_port)], self.env("server.env"))

    def start_ingest(self) -> None:
        ca = str(self.work / "secrets" / "ca.crt")
        self.start("ingest", [sys.executable, "-m", "server.mqtt_ingest", "--host", "localhost",
                              "--port", str(self.args.mqtt_port)], {**self.env("ingest.env"), "STMS_MQTT_CA_FILE": ca})

    def start_edge(self, intersection: str, samples: int | None) -> None:
        """A clip is paced in real time and stops after `samples`. The source
        `camera` (D42) is the live stream named by STMS_CAMERA_URL, which the edge
        reads from the environment it inherits; it runs until it is stopped."""
        ca = str(self.work / "secrets" / "ca.crt")
        profile = getattr(self.args, "profile", None)
        config = (["--profile", str(profile)] if profile else
                  ["--lanes", f"data/corpus_p103/{self.args.camera}/manifest.json",
                   "--approaches", *APPROACHES, "--camera", self.args.camera])
        live = str(self.args.clip) == CAMERA_SOURCE
        self.start("edge", [sys.executable, "-m", "edge.run", "--source", str(self.args.clip), *config,
                            "--intersection-id", intersection, "--broker-host", "localhost",
                            "--broker-port", str(self.args.mqtt_port),
                            *([] if samples is None else ["--samples", str(samples)]),
                            *([] if live else ["--realtime"])],
                   {**self.env("edge.env"), "STMS_MQTT_CA_FILE": ca})

    def get(self, path: str):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as response:
                body = response.read()
                try:
                    return response.status, json.loads(body)
                except ValueError:
                    return response.status, body
        except urllib.error.HTTPError as error:
            return error.code, None
        except OSError:
            return 0, None

    def wait_until(self, probe, timeout_s: float) -> bool:
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if probe():
                return True
            time.sleep(1)
        return False

    def secrets(self) -> list[str]:
        return [self.env("server.env")["STMS_API_TOKEN"], self.env("ingest.env")["STMS_MQTT_PASSWORD"],
                self.env("edge.env")["STMS_MQTT_PASSWORD"]]


def replay(camera: str, clip_id: str, samples: int) -> tuple[list[dict], list[dict]]:
    """The offline corpus counts for the clip, through the same forecasters the edge runs."""
    from edge.count_forecast import RidgeCountForecaster
    from edge.persistence import PersistenceForecaster
    from edge.samples import SampleError

    lanes = dict(a.split("=") for a in APPROACHES)
    pilot = ROOT / "experiments" / "results" / "bellevue_pilot"
    forecasters = (PersistenceForecaster(pilot / "persistence_v1.json", camera, lanes),
                   RidgeCountForecaster(pilot / "p105_ridge_v1.json", lanes))
    out: tuple[list[dict], list[dict]] = ([], [])
    with (ROOT / "data" / "corpus_p103" / camera / "counts.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["clip_id"] == clip_id][:samples]
    for row in rows:
        totals = {lane: int(row[f"count_{lane}"]) for lane in lanes}
        for i, forecaster in enumerate(forecasters):
            try:                                   # as EdgeLoop._forecast: refused publishes nothing
                forecast = forecaster.step(totals, float(row["t_s"]))
            except (SampleError, ValueError):
                forecast = None
            if forecast is not None:
                out[i].append({a: v.value for a, v in forecast.predictions.items()} if i == 0
                              else dict(forecast.counts))
    return out


def untracked() -> set[str]:
    return set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
                              capture_output=True, text=True).stdout.split())


def verify(stack: Stack, samples: int) -> dict:
    results: dict[str, dict] = {}

    def check(key: str, ok: bool, detail: str) -> None:
        results[key] = {"pass": bool(ok), "detail": detail}
        stack.mark(f"{key} {'PASS' if ok else 'FAIL'}: {detail}")

    ident, before = "demo", untracked()
    stack.start_broker(), stack.start_server(), stack.start_ingest()
    up = stack.wait_until(lambda: stack.get("/health")[0] == 200, 60)
    check("E1", up and stack.procs["ingest"].poll() is None, "broker, server and ingest up with no manual step")
    t0 = time.monotonic()
    stack.start_edge(ident, samples)
    got_c = stack.wait_until(lambda: stack.get(f"/prediction/{ident}/latest")[0] == 200, 150)
    t_c = time.monotonic() - t0
    got_k = stack.wait_until(lambda: stack.get(f"/count_forecast/{ident}/latest")[0] == 200, 200)
    t_k = time.monotonic() - t0
    check("E3", got_c and got_k, f"first class forecast after {t_c:.0f} s, first count forecast after {t_k:.0f} s")
    status, body = stack.get("/dashboard/")
    check("E5", status == 200 and b'id="root"' in (body if isinstance(body, bytes) else b""),
          "the built dashboard is served at /dashboard/ (browse it to see the panels)")
    stack.procs["edge"].wait()
    check("E2", stack.procs["edge"].returncode == 0, f"edge exited {stack.procs['edge'].returncode} after {samples} samples")

    time.sleep(3)
    stored_c = [r["predictions"] for r in reversed(stack.get(f"/prediction/{ident}/history?limit=500")[1]["rows"])]
    stored_k = [r["counts"] for r in reversed(stack.get(f"/count_forecast/{ident}/history?limit=500")[1]["rows"])]
    exp_c, exp_k = replay(stack.args.camera, stack.args.clip.stem, samples)
    same = lambda a, b: sum(x == y for x, y in zip(a, b))           # noqa: E731
    check("E4", (len(stored_c), same(stored_c, exp_c), len(stored_k), same(stored_k, exp_k))
          == (len(exp_c), len(exp_c), len(exp_k), len(exp_k)) and bool(exp_c and exp_k),
          f"class {same(stored_c, exp_c)}/{len(exp_c)} equal to the replay (stored {len(stored_c)}), "
          f"count {same(stored_k, exp_k)}/{len(exp_k)} (stored {len(stored_k)})")

    stale = stack.wait_until(lambda: (stack.get(f"/prediction/{ident}/latest")[1] or {}).get("stale") is True, 120)
    check("E6", stale and stack.get("/health")[0] == 200, "class stream stale after its 60 s horizon, server up")

    rows = len(stack.get(f"/prediction/{ident}/history?limit=500")[1]["rows"])
    stack.stop("ingest"), stack.stop("server")
    # The restart must be real: a server that survived its stop would serve the
    # same rows and pass this check without anything having restarted.
    down = stack.wait_until(lambda: stack.get("/health")[0] == 0, 15)
    stack.start_server(), stack.start_ingest()
    up = stack.wait_until(lambda: stack.get("/health")[0] == 200, 60)
    after = len(stack.get(f"/prediction/{ident}/history?limit=500")[1]["rows"]) if up else -1
    check("E7", down and up and after == rows,
          f"server down after its stop: {down}; history {rows} rows before the restart, {after} after")

    t0 = time.monotonic()
    stack.start_edge(ident, 40)
    fresh = stack.wait_until(lambda: (stack.get(f"/prediction/{ident}/latest")[1] or {}).get("stale") is False, 150)
    check("E8", fresh, f"fresh class forecast again {time.monotonic() - t0:.0f} s after the edge restarted")
    stack.procs["edge"].wait()

    for name in list(stack.procs):
        stack.stop(name)
    leaked = [f.name for f in stack.work.glob("*.log") for s in stack.secrets()
              if s in f.read_text(encoding="utf-8", errors="replace")]
    new = sorted(untracked() - before)
    check("E9", not leaked and not new,
          f"secrets in logs: {leaked or 'none'}; new files in the repository: {new or 'none'}")
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mosquitto", type=Path, required=True, help="mosquitto executable; mosquitto_passwd beside it")
    ap.add_argument("--clips-root", type=Path, required=True, help="folder searched for <clip-id>.mp4; never recorded")
    ap.add_argument("--camera", default="150th_Eastgate")
    ap.add_argument("--clip-id", default="Bellevue_150th_Eastgate__2017-09-11_10-08-31")
    ap.add_argument("--samples", type=int, default=180, help="2 s samples for the verify run (default 6 minutes)")
    ap.add_argument("--live", type=float, metavar="MINUTES", help="run for watching, checking nothing")
    ap.add_argument("--http-port", type=int, default=18000)
    ap.add_argument("--mqtt-port", type=int, default=18883)
    ap.add_argument("--results", type=Path, help="write the checks as JSON here (outside the repository)")
    args = ap.parse_args(argv)
    if not args.mosquitto.is_file():
        ap.error(f"--mosquitto is not a file: {args.mosquitto}")
    args.clip = next(args.clips_root.rglob(f"{args.clip_id}.mp4"), None)
    if args.clip is None:
        ap.error(f"{args.clip_id}.mp4 not found under --clips-root")
    if not (ROOT / "data" / "corpus_p103" / args.camera / "manifest.json").is_file():
        ap.error(f"data/corpus_p103/{args.camera}/ is missing: the lane geometry and offline counts")
    (ROOT / "data" / "server" / "stms.sqlite").unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="stms-demo-") as tmp:
        stack = Stack(args, Path(tmp))
        stack.prepare_broker()
        try:
            if args.live:
                samples = int(args.live * 30)
                stack.start_broker(), stack.start_server(), stack.start_ingest()
                if not stack.wait_until(lambda: stack.get("/health")[0] == 200, 60):
                    raise SystemExit("the server did not come up")
                stack.start_edge("live", samples)
                stack.mark(f"LIVE: open {stack.base}/dashboard/?id=live  (first forecast in about 60 s; "
                           f"{args.live:g} min of footage, then the streams go stale)")
                stack.procs["edge"].wait()
                stack.mark("edge finished; the page now shows the streams going stale. Stopping in 3 minutes.")
                time.sleep(180)
                return 0
            results = verify(stack, args.samples)
            if args.results:
                args.results.write_text(json.dumps(results, indent=1), encoding="utf-8")
            passed = sum(r["pass"] for r in results.values())
            stack.mark(f"DONE: {passed} of {len(results)} checks pass")
            return 0 if passed == len(CHECKS) else 1
        finally:
            for name in list(stack.procs):
                stack.stop(name)
            (ROOT / "data" / "server" / "stms.sqlite").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
