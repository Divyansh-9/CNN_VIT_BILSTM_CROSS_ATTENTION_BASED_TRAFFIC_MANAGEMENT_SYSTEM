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
import threading
import time

from contracts.mqtt import ContractError, Topic

__all__ = ["PredictionIngest"]


INGESTED = (Topic.PREDICTION, Topic.COUNT_FORECAST)


def route(topic: str) -> tuple[str, Topic]:
    """`stms/{id}/…` -> (`id`, the contract topic it renders), or refuse."""
    parts = topic.split("/")
    for candidate in INGESTED:
        if len(parts) == 4 and candidate.render(parts[1]) == topic:
            return parts[1], candidate
    raise ContractError(f"not an ingested topic: {topic!r}")


def intersection_of(topic: str) -> str:
    """`stms/{id}/congestion/prediction` -> `id`, checked against the contract."""
    identifier, which = route(topic)
    if which is not Topic.PREDICTION:
        raise ContractError(f"not a prediction topic: {topic!r}")
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

        try:
            identifier, which = route(message.topic)
            store = store_prediction if which is Topic.PREDICTION else store_count_forecast
            store(identifier, message.payload)
            self.stored += 1
            self.arrivals.append(time.perf_counter())
        except ContractError as error:
            # Type and size only. Contract errors quote the offending value
            # for the producer's benefit, so even the message is not logged
            # here: a refused payload is exactly the one that must not be
            # written anywhere (NFR-13).
            self.refused.append((message.topic,
                                 f"{type(error).__name__}, "
                                 f"{len(message.payload)} bytes"))

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
