"""The server's side of the prediction topic (ADR-026).

    python -m server.mqtt_ingest --host 127.0.0.1 --port 1883

Subscribes to `stms/+/congestion/prediction`, since ADR-027
`stms/+/count/forecast`, since D21 the observed per-lane counts on
`stms/+/+/vehicle_count`, and since D22 the edge's heartbeat on
`stms/+/system/heartbeat`, which names its source and lane map. Every message
goes to the store function its HTTP endpoint uses (`store_prediction`,
`store_count_forecast`, `store_vehicle_count`, `store_heartbeat`), so a
payload refused over HTTP is refused over MQTT too. The intersection id, and for counts the lane, are read from the topic,
which the contract renders, never from the payload.

A refused payload is counted and logged by topic and reason, and its content is
never logged: a malformed message is exactly the one that must not be echoed
anywhere (NFR-13).

**Credentials come from the environment** (NFR-11, `contracts/broker.py`):
`STMS_MQTT_USERNAME` and `STMS_MQTT_PASSWORD`, both or neither. A broker that
refuses the connection is reported by its reason code, never with the
credentials. With `STMS_MQTT_CA_FILE` set, the connection is TLS, verified
against that CA (D10).

**It stops cleanly** (D12). Ctrl+C, SIGTERM or, on Windows, Ctrl+Break
disconnects from the broker, prints what was stored, refused and failed, and
exits 0. Before D12 it ended in a `KeyboardInterrupt` traceback without
disconnecting.
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from pathlib import Path

from contracts.broker import (CredentialError, Credentials, TlsConfigError, ca_file_from_env,
                             client_tls_context, credentials_from_env)
from contracts.mqtt import ContractError, Topic, check_intersection_id, check_lane

__all__ = ["PredictionIngest", "serve_until_stopped", "stop_on_signals", "subscription_summary"]

log = logging.getLogger(__name__)


INGESTED = (Topic.PREDICTION, Topic.COUNT_FORECAST, Topic.VEHICLE_COUNT, Topic.HEARTBEAT)


#: What the records and the log say instead of a topic that did not route. The
#: topic level carries the sender's intersection id, which is free text of any
#: length until it has been checked (P142).
UNROUTED = "<unrouted topic>"


def route(topic: str) -> tuple[str, Topic]:
    """`stms/{id}/…` -> (`id`, the contract topic it renders), or refuse.

    The id must match the contract's pattern (P142): it is stored with every
    message, and before this check any text of any length was. Neither refusal
    quotes the topic."""
    parts = topic.split("/")
    for candidate in INGESTED:
        if len(parts) != 4:
            break
        if candidate is Topic.VEHICLE_COUNT:
            # Per lane: the lane is checked like the id, before it is stored (D21).
            if candidate.render(parts[1], parts[2]) == topic:
                check_lane(parts[2])
                return check_intersection_id(parts[1]), candidate
        elif candidate.render(parts[1]) == topic:
            return check_intersection_id(parts[1]), candidate
    raise ContractError("not an ingested topic")


def render_any(which: Topic, identifier: str) -> str:
    """A topic's subscription or label form: `+` stands for the lane where the
    template has one."""
    return which.render(identifier, "+") if "{lane}" in which.template else which.render(identifier)


def subscription_summary(host: str, port: int) -> str:
    """The start-up line: every topic the ingest subscribes to, not just one."""
    names = [render_any(t, "+") for t in INGESTED]
    return f"subscribed to {', '.join(names[:-1])} and {names[-1]} on {host}:{port}"


def intersection_of(topic: str) -> str:
    """`stms/{id}/congestion/prediction` -> `id`, checked against the contract."""
    identifier, which = route(topic)
    if which is not Topic.PREDICTION:
        raise ContractError("not a prediction topic")
    return identifier


class PredictionIngest:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883, *,
                 client_id: str = "stms-server-ingest",
                 credentials: Credentials | None = None,
                 ca_file: Path | None = None) -> None:
        import paho.mqtt.client as mqtt

        self.host, self.port = host, port
        self.stored = 0
        # perf_counter at each successful store. Comparable with a sender's
        # perf_counter only inside one process, which is how verify_edge.py
        # uses it to measure delivery separately from send time.
        self.arrivals: list[float] = []
        self.refused: list[tuple[str, str]] = []
        # A valid message the server could not process, a locked database say.
        # Kept apart from `refused`: that one is the producer's fault, this one
        # is ours, and the message may well have been good (P140).
        self.failed: list[tuple[str, str]] = []
        self._subscribed = threading.Event()
        # The broker's reason for refusing the last connection, if it did.
        self.connect_refused: str | None = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = lambda *a, **k: self._subscribed.set()
        self.client.on_message = self._on_message
        if credentials is not None:
            self.client.username_pw_set(credentials.username, credentials.password)
        self.tls = ca_file is not None
        if self.tls:
            self.client.tls_set_context(client_tls_context(ca_file))

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            self.connect_refused = str(reason_code)
            return
        self.connect_refused = None
        client.subscribe([(render_any(t, "+"), t.qos) for t in INGESTED])

    def _on_message(self, client, userdata, message):
        from server.app import (store_count_forecast, store_heartbeat, store_prediction,
                                store_vehicle_count)

        # The topic is named in records and logs only once it has routed, as
        # the contract re-renders it from a checked id; until then it is
        # `UNROUTED` (P142).
        label = UNROUTED
        try:
            identifier, which = route(message.topic)
            if which is Topic.VEHICLE_COUNT:
                lane = message.topic.split("/")[2]
                label = which.render(identifier, lane)
                store_vehicle_count(identifier, lane, message.payload)
            else:
                label = which.render(identifier)
                store = {Topic.PREDICTION: store_prediction,
                         Topic.COUNT_FORECAST: store_count_forecast,
                         Topic.HEARTBEAT: store_heartbeat}[which]
                store(identifier, message.payload)
            self.stored += 1
            self.arrivals.append(time.perf_counter())
        except ContractError as error:
            # Type and size only. Contract errors quote the offending value
            # for the producer's benefit, so even the message is not logged
            # here: a refused payload is exactly the one that must not be
            # written anywhere (NFR-13).
            self.refused.append((label,
                                 f"{type(error).__name__}, "
                                 f"{len(message.payload)} bytes"))
            # Logged too (P142): an edge with a bad id used to have every
            # message dropped with nothing in the log to say so. The label is
            # `<unrouted topic>` unless the id checked out.
            log.warning("ingest refused a message on %s: %s, %d bytes",
                        label, type(error).__name__, len(message.payload))
        except Exception as error:  # noqa: BLE001
            # Anything else is a processing failure, not a refusal. It must not
            # escape: paho re-raises a callback's exception in its network
            # thread (suppress_exceptions is False by default), which would stop
            # all ingest silently (P140). Recorded and logged with the topic,
            # the exception type and the size only; never the content.
            self.failed.append((label,
                                f"{type(error).__name__}, "
                                f"{len(message.payload)} bytes"))
            log.error("ingest failed to process a message on %s: %s, %d bytes",
                      label, type(error).__name__, len(message.payload))

    def start(self, wait_s: float = 5.0) -> bool:
        self.client.connect_async(self.host, self.port)
        self.client.loop_start()
        return self._subscribed.wait(wait_s)

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


def stop_on_signals(stop: threading.Event) -> None:
    """SIGTERM, and Ctrl+Break on Windows, set `stop`. Ctrl+C arrives as
    `KeyboardInterrupt` and is handled by the caller."""
    for name in ("SIGTERM", "SIGBREAK"):
        number = getattr(signal, name, None)
        if number is not None:
            signal.signal(number, lambda signum, frame: stop.set())


def serve_until_stopped(ingest: "PredictionIngest", stop: threading.Event,
                        poll_s: float = 0.5) -> str:
    """Wait until `stop` is set or Ctrl+C, then disconnect. Returns the summary.

    The wait polls: an untimed `Event.wait()` is not interrupted by Ctrl+C on
    Windows."""
    try:
        while not stop.wait(poll_s):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        ingest.stop()
    return (f"stopped; {ingest.stored} stored, {len(ingest.refused)} refused, "
            f"{len(ingest.failed)} failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args(argv)
    try:
        credentials = credentials_from_env()
        ca_file = ca_file_from_env()
    except (CredentialError, TlsConfigError) as error:
        raise SystemExit(str(error)) from None
    if ca_file is None:
        print("  STMS_MQTT_CA_FILE not set; connecting over plain TCP, without TLS")
    if credentials is None:
        print("  no MQTT credentials set; connecting anonymously, which only a development "
              "broker accepts (NFR-11)")
    ingest = PredictionIngest(args.host, args.port, credentials=credentials, ca_file=ca_file)
    if not ingest.start():
        if ingest.connect_refused:
            raise SystemExit(f"the broker at {args.host}:{args.port} refused the connection: "
                             f"{ingest.connect_refused}")
        raise SystemExit(f"could not subscribe at {args.host}:{args.port}"
                         + (" over TLS: unreachable, or its certificate failed verification"
                            if ingest.tls else ""))
    # Flushed, so the line is visible when the output goes to a file too.
    print(f"  {subscription_summary(args.host, args.port)}", flush=True)
    stop = threading.Event()
    stop_on_signals(stop)
    print(f"  {serve_until_stopped(ingest, stop)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
