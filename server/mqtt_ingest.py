"""The server's side of the prediction topic (ADR-026).

    python -m server.mqtt_ingest --host 127.0.0.1 --port 1883

Subscribes to `stms/+/congestion/prediction` and, since ADR-027,
`stms/+/count/forecast`, and hands every message to the store function its
HTTP endpoint uses (`store_prediction`, `store_count_forecast`), so a payload
refused over HTTP is refused over MQTT too. The intersection id is read
from the topic, which the contract renders, never from the payload.

A refused payload is counted and logged by topic and reason, and its content is
never logged: a malformed message is exactly the one that must not be echoed
anywhere (NFR-13).
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from contracts.mqtt import ContractError, Topic, check_intersection_id

__all__ = ["PredictionIngest"]

log = logging.getLogger(__name__)


INGESTED = (Topic.PREDICTION, Topic.COUNT_FORECAST)


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
        if len(parts) == 4 and candidate.render(parts[1]) == topic:
            return check_intersection_id(parts[1]), candidate
    raise ContractError("not an ingested topic")


def intersection_of(topic: str) -> str:
    """`stms/{id}/congestion/prediction` -> `id`, checked against the contract."""
    identifier, which = route(topic)
    if which is not Topic.PREDICTION:
        raise ContractError("not a prediction topic")
    return identifier


class PredictionIngest:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883, *,
                 client_id: str = "stms-server-ingest") -> None:
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
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = lambda *a, **k: self._subscribed.set()
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if not reason_code.is_failure:
            client.subscribe([(t.render("+"), t.qos) for t in INGESTED])

    def _on_message(self, client, userdata, message):
        from server.app import store_count_forecast, store_prediction

        # The topic is named in records and logs only once it has routed, as
        # the contract re-renders it from a checked id; until then it is
        # `UNROUTED` (P142).
        label = UNROUTED
        try:
            identifier, which = route(message.topic)
            label = which.render(identifier)
            store = store_prediction if which is Topic.PREDICTION else store_count_forecast
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args(argv)
    ingest = PredictionIngest(args.host, args.port)
    if not ingest.start():
        raise SystemExit(f"could not subscribe at {args.host}:{args.port}")
    print(f"  subscribed to {Topic.PREDICTION.render('+')} on "
          f"{args.host}:{args.port}")
    threading.Event().wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
