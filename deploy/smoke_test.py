"""The Compose stack's smoke test: the real service path, not "containers are up" (D15).

    python deploy/smoke_test.py                  # after: docker compose up -d --build
    python deploy/smoke_test.py --after-restart  # after: docker compose restart server ingest

It publishes as the edge would and reads back as the dashboard would:
- a class forecast and a count forecast, published over MQTT with TLS and the
  edge's login (from `deploy/secrets/edge.env`);
- the ingest stores them, and the server returns them, latest and history;
- the built dashboard is served;
- an anonymous MQTT client is refused, and an HTTP write without the token is
  refused;
- the evidence panel names real commits, not "uncommitted".

With `--after-restart` it publishes nothing. The forecasts written before the
restart must still be there, which is what a persistent store means.

Exits 1 on the first failed check. Prints no secret.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contracts.broker import Credentials  # noqa: E402
from contracts.mqtt import CongestionClass, CongestionPrediction, CountForecast, Topic  # noqa: E402
from edge.mqtt_transport import MqttTransport  # noqa: E402

ID = "smoke"
CLASS = {"N": "HIGH", "S": "LOW", "E": "MEDIUM"}          # W absent on purpose
COUNTS = {"N": 6.5, "S": 0.0, "E": 3.25}                  # a real zero, W absent


def read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)


def http(method: str, url: str, body: bytes | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except OSError:
        return 0, b""


def check(ok: bool, what: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {what}", flush=True)
    if not ok:
        sys.exit(1)


def wait_for(probe, what: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if probe():
            check(True, what)
            return
        time.sleep(1)
    check(False, f"{what} (gave up after {timeout_s:.0f} s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--broker-host", default="localhost")
    ap.add_argument("--broker-port", type=int, default=8883)
    ap.add_argument("--secrets", type=Path, default=ROOT / "deploy" / "secrets")
    ap.add_argument("--after-restart", action="store_true")
    ap.add_argument("--timeout", type=float, default=180)
    args = ap.parse_args(argv)
    get = lambda path: http("GET", args.base + path)                     # noqa: E731

    wait_for(lambda: get("/health")[0] == 200, "server answers /health", args.timeout)

    if not args.after_restart:
        ca = args.secrets / "ca.crt"
        anonymous = MqttTransport(args.broker_host, args.broker_port, client_id="smoke-anon", ca_file=ca)
        connected = anonymous.start(wait_s=10)
        anonymous.stop()
        check(not connected and anonymous.connect_refused is not None,
              f"broker refuses an anonymous client over TLS ({anonymous.connect_refused})")

        env = read_env(args.secrets / "edge.env")
        edge = MqttTransport(args.broker_host, args.broker_port, client_id="smoke-edge", ca_file=ca,
                             credentials=Credentials(env["STMS_MQTT_USERNAME"], env["STMS_MQTT_PASSWORD"]))
        wait_for(lambda: edge.start(wait_s=5), "edge login accepted over verified TLS", args.timeout)
        prediction = CongestionPrediction(
            predictions={a: CongestionClass(c) for a, c in CLASS.items()},
            confidences={a: 0.7 for a in CLASS}, gate_value=None, model="persistence@0123456789ab")
        forecast = CountForecast(counts=COUNTS, model="ridge@0123456789ab")

        def published() -> bool:
            # The ingest may still be connecting; QoS 0 is fire-and-forget, so
            # publish until the server has stored one.
            edge.publish(Topic.PREDICTION.render(ID), prediction.encode(), int(Topic.PREDICTION.qos))
            edge.publish(Topic.COUNT_FORECAST.render(ID), forecast.encode(), int(Topic.COUNT_FORECAST.qos))
            time.sleep(1)
            return (get(f"/prediction/{ID}/latest")[0] == 200
                    and get(f"/count_forecast/{ID}/latest")[0] == 200)

        wait_for(published, "ingest stores both forecasts; the server returns them", args.timeout)
        edge.stop()

    status, body = get(f"/prediction/{ID}/latest")
    latest = json.loads(body) if status == 200 else {}
    check(latest.get("predictions") == CLASS and latest.get("missing_approaches") == ["W"],
          "class forecast read back exactly, W listed as missing")
    status, body = get(f"/count_forecast/{ID}/history")
    rows = json.loads(body).get("rows", []) if status == 200 else []
    check(bool(rows) and rows[0]["counts"] == COUNTS and rows[0]["missing_approaches"] == ["W"],
          "count history read back, the real 0.0 kept, W missing")

    status, body = get("/dashboard/")
    check(status == 200 and b"<div id=\"root\">" in body, "the built dashboard is served at /dashboard/")
    status, _ = http("POST", args.base + "/observation", b"{}")
    check(status == 401, f"an HTTP write without the token is refused ({status})")
    status, body = get("/evidence")
    studies = json.loads(body).get("studies", []) if status == 200 else []
    check(bool(studies) and all(s["commit"] != "uncommitted" for s in studies),
          f"evidence names real commits: {[s.get('commit') for s in studies]}")
    print("smoke test passed" + (" after restart: the store persisted" if args.after_restart else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
