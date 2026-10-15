"""The live link: `Transport` over MQTT, with paho (PRD §17.1, ADR-026).

`EdgeNode` depends on a two-method protocol, and `RecordingTransport` is the
test double. This is the real one. It adds nothing to the node's logic — FR-A06
is still decided by `EdgeNode` from whether publishes succeed — so the
behaviour tested against the recording transport is the behaviour deployed.

**A publish either reaches the broker or raises.** At QoS 1 and 2 the call
waits for the broker's acknowledgement, up to `ack_timeout_s`, and raises
`ConnectionError` if it does not come. That is what lets `EdgeNode` count a
publish as an acknowledgement; a fire-and-forget publish would make FR-A06's
timeout measure the speed of the local socket buffer instead of the link.

QoS is never chosen here. It arrives from `Topic.qos` through the node, so
emergency traffic cannot be downgraded by a transport (contracts/mqtt.py).
"""

from __future__ import annotations

import threading

__all__ = ["MqttTransport"]


class MqttTransport:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883, *,
                 client_id: str, keepalive_s: int = 30,
                 ack_timeout_s: float = 2.0) -> None:
        import paho.mqtt.client as mqtt

        self._mqtt = mqtt
        self.host, self.port = host, port
        self.ack_timeout_s = ack_timeout_s
        self._up = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.keepalive_s = keepalive_s

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if not reason_code.is_failure:
            self._up.set()

    def _on_disconnect(self, client, userdata, flags, reason_code,
                       properties=None):
        self._up.clear()

    def start(self, wait_s: float = 5.0) -> bool:
        """Connect and run the network loop; True once the broker accepts."""
        self.client.connect_async(self.host, self.port, self.keepalive_s)
        self.client.loop_start()
        return self._up.wait(wait_s)

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def connected(self) -> bool:
        return self._up.is_set()

    def publish(self, topic: str, payload: str, qos: int) -> None:
        if not self.connected():
            raise ConnectionError(f"not connected to {self.host}:{self.port}")
        info = self.client.publish(topic, payload, qos=qos)
        if info.rc != self._mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"publish to {topic} failed: rc={info.rc}")
        if qos > 0:
            try:
                info.wait_for_publish(timeout=self.ack_timeout_s)
            except (RuntimeError, ValueError) as error:
                raise ConnectionError(str(error)) from error
            if not info.is_published():
                raise ConnectionError(
                    f"no broker acknowledgement for {topic} within "
                    f"{self.ack_timeout_s} s at QoS {qos}")
